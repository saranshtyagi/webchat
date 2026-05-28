import re
import time
import requests
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

API_BASE = "https://webchat-api-441y.onrender.com"

# 10 URLs × 3 questions each = 30 questions total
CASES = [
    {
        "url": "https://en.wikipedia.org/wiki/Large_language_model",
        "qas": [
            {"q": "What is a large language model?", "expect_any": ["language model", "neural", "trained on", "text"]},
            {"q": "What architecture are many LLMs based on?", "expect_any": ["transformer"]},
            {"q": "Name one capability of LLMs.", "expect_any": ["summary", "translate", "generate", "answer", "image", "multimodal"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/FastAPI",
        "qas": [
            {"q": "What is FastAPI?", "expect_any": ["framework", "api"]},
            {"q": "Which language is FastAPI written in?", "expect_any": ["python"]},
            {"q": "Name one FastAPI feature.", "expect_any": ["async", "openapi", "type", "performance", "validation"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/Server-sent_events",
        "qas": [
            {"q": "What are Server-Sent Events (SSE)?", "expect_any": ["server sent", "events", "event", "updates"]},
            {"q": "What kind of connection does SSE use?", "expect_any": ["http"]},
            {"q": "Is SSE unidirectional or bidirectional?", "expect_any": ["unidirectional"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/Chrome_extension",
        "qas": [
            {"q": "What is a Chrome extension?", "expect_any": ["extension", "add on", "add-on", "browser"]},
            {"q": "Where can extensions be distributed from?", "expect_any": ["chrome web store", "web store"]},
            {"q": "Name one capability of browser extensions.", "expect_any": ["add on", "add-on", "custom", "functionality", "modify", "integrat", "api", "web page", "browser"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/Representational_state_transfer",
        "qas": [
            {"q": "What does REST stand for?", "expect_any": ["representational state transfer"]},
            {"q": "What protocol is REST commonly used with?", "expect_any": ["http"]},
            {"q": "Name one common REST constraint.", "expect_any": ["stateless", "cache", "client server", "client/server", "layered", "uniform interface"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/Prompt_engineering",
        "qas": [
            {"q": "What is prompt engineering?", "expect_any": ["prompt", "instruction"]},
            {"q": "What is one goal of prompt engineering?", "expect_any": ["desired", "avoid", "steer", "control", "guide", "better", "improve"]},
            {"q": "Name one technique used in prompting.", "expect_any": ["few shot", "few-shot", "zero shot", "zero-shot", "chain of thought", "chain-of-thought", "role", "examples"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/Information_retrieval",
        "qas": [
            {"q": "What is information retrieval about?", "expect_any": ["search", "information", "documents", "retrieval"]},
            {"q": "Name one common IR concept.", "expect_any": ["relevance", "ranking", "query", "document", "index", "search"]},
            {"q": "Name one IR model or approach.", "expect_any": ["bm25", "tf idf", "tf-idf", "vector space", "probabilistic"]},
        ],
    },
    # BM25 page can be short; keep questions very basic
    {
        "url": "https://en.wikipedia.org/wiki/BM25",
        "qas": [
            {"q": "What is BM25 used for?", "expect_any": ["ranking", "retrieval", "information retrieval"]},
            {"q": "BM25 is used in which field?", "expect_any": ["information retrieval", "retrieval"]},
            {"q": "What is BM25 (briefly)?", "expect_any": ["ranking", "function", "retrieval"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/Web_scraping",
        "qas": [
            {"q": "What is web scraping?", "expect_any": ["extract", "data", "web", "gather"]},
            {"q": "Name one common use of web scraping.", "expect_any": ["research", "monitor", "price", "collect", "data", "market"]},
            {"q": "Name one challenge of web scraping.", "expect_any": ["bot", "bots", "block", "blocked", "captcha", "robots", "rate", "javascript", "disallow"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/OpenAPI_Specification",
        "qas": [
            {"q": "What is the OpenAPI Specification used for?", "expect_any": ["describe", "api", "interface", "specification"]},
            {"q": "What is one benefit of OpenAPI?", "expect_any": ["documentation", "code generation", "client", "server", "sync"]},
            {"q": "What format are OpenAPI documents commonly written in?", "expect_any": ["yaml", "json"]},
        ],
    },
]

NOT_FOUND_MARKERS = [
    "i could not find that on this page",
    "could not find that on this page",
]

def normalize_text(s: str) -> str:
    """
    Normalize text so simple substring checks become robust:
    - lowercase
    - normalize unicode quotes
    - replace slashes/hyphens with spaces (client/server vs client-server)
    - collapse whitespace
    - remove most punctuation
    """
    if not s:
        return ""
    s = s.lower()
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("/", " ").replace("-", " ")
    # keep alphanumerics + spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def contains_any(answer: str, expected: List[str]) -> bool:
    a = normalize_text(answer)
    for x in expected:
        if normalize_text(x) in a:
            return True
    return False

def is_not_found(answer: str) -> bool:
    a = normalize_text(answer)
    return any(normalize_text(m) in a for m in NOT_FOUND_MARKERS)

@dataclass
class EvalResult:
    url: str
    question: str
    answer: str
    passed: bool
    reason: str  # "pass" | "not_found" | "mismatch"
    expected_any: List[str]

def run_case(url: str, qas: List[Dict[str, Any]]) -> List[EvalResult]:
    print(f"\n== Scrape: {url}")
    r = requests.post(f"{API_BASE}/scrape", json={"url": url}, timeout=180)
    r.raise_for_status()
    s = r.json()
    sid = s["session_id"]
    print(f"   session_id={sid} chunks={s['chunks_stored']} title={s['page_title']!r}")

    results: List[EvalResult] = []
    for qa in qas:
        q = qa["q"]
        exp = qa["expect_any"]

        rr = requests.post(
            f"{API_BASE}/chat",
            json={"session_id": sid, "question": q},
            timeout=180
        )
        rr.raise_for_status()
        ans = rr.json()["answer"]

        if is_not_found(ans):
            ok = False
            reason = "not_found"
        else:
            ok = contains_any(ans, exp)
            reason = "pass" if ok else "mismatch"

        print(f"\nQ: {q}")
        print(f"A: {ans}")
        print(f"EXPECT any: {exp} -> {'PASS' if ok else 'FAIL'} ({reason})")

        results.append(EvalResult(
            url=url,
            question=q,
            answer=ans,
            passed=ok,
            reason=reason,
            expected_any=exp
        ))

        time.sleep(0.6)
    return results

def summary_table(results: List[EvalResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    not_found = sum(1 for r in results if r.reason == "not_found")
    mismatch = sum(1 for r in results if r.reason == "mismatch")

    print("\n" + "=" * 72)
    print(f"RESULT: {passed}/{total} passed ({(passed/total)*100:.1f}%)")
    print(f"Breakdown: not_found={not_found}, mismatch={mismatch}")
    print("=" * 72)

    if passed != total:
        print("\nFailed questions:")
        for r in results:
            if r.passed:
                continue
            print(f"- [{r.reason}] {r.url} :: {r.question}")

def main():
    all_results: List[EvalResult] = []
    total_questions = sum(len(c["qas"]) for c in CASES)
    print(f"Running eval: {len(CASES)} URLs, {total_questions} questions total.\n")

    for case in CASES:
        all_results.extend(run_case(case["url"], case["qas"]))

    summary_table(all_results)

if __name__ == "__main__":
    main()