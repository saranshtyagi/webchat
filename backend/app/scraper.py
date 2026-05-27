import os
import bs4

from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.store import set_session

os.environ.setdefault("USER_AGENT", "Mozilla/5.0 (WebChat Extension)")

MAX_DOC_CHARS = 200_000
MAX_TOTAL_CHARS = 400_000
MAX_CHUNKS = 250

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())

def _trim_docs(docs):
    total = 0
    trimmed = []
    for d in docs:
        content = _normalize_whitespace(d.page_content)
        if not content:
            continue

        content = content[:MAX_DOC_CHARS]

        remaining = MAX_TOTAL_CHARS - total
        if remaining <= 0:
            break
        content = content[:remaining]
        total += len(content)

        d.page_content = content
        trimmed.append(d)
    return trimmed

def scrape_and_store(url: str, session_id: str) -> dict:
    strainer = bs4.SoupStrainer(["article", "main", "p", "h1", "h2", "h3", "h4", "li"])
    loader = WebBaseLoader(url, bs_kwargs={"parse_only": strainer})
    docs = loader.load()

    page_title = docs[0].metadata.get("title", url) if docs else url

    docs = _trim_docs(docs)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    if len(chunks) > MAX_CHUNKS:
        chunks = chunks[:MAX_CHUNKS]

    # Store chunks (Documents) in memory
    set_session(session_id, chunks)

    return {"title": page_title, "chunks": len(chunks)}