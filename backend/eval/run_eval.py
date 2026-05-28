import time
import requests

API_BASE = "https://webchat-api-441y.onrender.com"  

CASES = [
    {
        "url": "https://en.wikipedia.org/wiki/Large_language_model",
        "qas": [
            {"q": "What is a large language model?", "expect_any": ["language model", "neural", "model"]},
            {"q": "What architecture are many LLMs based on?", "expect_any": ["transformer"]},
            {"q": "Name one capability of LLMs.", "expect_any": ["summar", "translat", "generat", "answer"]},
        ],
    },
    {
        "url": "https://en.wikipedia.org/wiki/FastAPI",
        "qas": [
            {"q": "What is FastAPI?", "expect_any": ["framework", "api"]},
            {"q": "Which language is FastAPI written in?", "expect_any": ["python"]},
            {"q": "Name one FastAPI feature.", "expect_any": ["type", "async", "performance", "openapi"]},
        ],
    },
]

def contains_any(answer: str, expected):
    a = (answer or "").lower()
    return any(x.lower() in a for x in expected)

def main():
    total = 0
    passed = 0

    for case in CASES:
        url = case["url"]
        print(f"\n== Scrape: {url}")
        r = requests.post(f"{API_BASE}/scrape", json={"url": url}, timeout=120)
        r.raise_for_status()
        s = r.json()
        sid = s["session_id"]
        print(f"   session_id={sid} chunks={s['chunks_stored']} title={s['page_title']!r}")

        for qa in case["qas"]:
            total += 1
            q = qa["q"]
            exp = qa["expect_any"]

            rr = requests.post(f"{API_BASE}/chat", json={"session_id": sid, "question": q}, timeout=120)
            rr.raise_for_status()
            ans = rr.json()["answer"]

            ok = contains_any(ans, exp)
            print(f"\nQ: {q}")
            print(f"A: {ans}")
            print(f"EXPECT any: {exp} -> {'PASS' if ok else 'FAIL'}")

            if ok:
                passed += 1
            time.sleep(0.5)

    print(f"\nRESULT: {passed}/{total} passed ({(passed/total)*100:.1f}%)")

if __name__ == "__main__":
    main()