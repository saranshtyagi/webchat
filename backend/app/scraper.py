# app/scraper.py
import os
import bs4
import numpy as np

from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from fastembed import TextEmbedding

from app.store import set_session

os.environ.setdefault("USER_AGENT", "Mozilla/5.0 (WebChat Extension)")

MAX_DOC_CHARS = 200_000
MAX_TOTAL_CHARS = 400_000
MAX_CHUNKS = 300

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")

# Create embedder once
_EMBEDDER = TextEmbedding(model_name=EMBED_MODEL_NAME)

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

def _embed_texts(texts):
   
    vecs = list(_EMBEDDER.embed(texts))
    return np.asarray(vecs, dtype=np.float32)

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

    texts = [c.page_content for c in chunks]
    vectors = _embed_texts(texts)  # (n_chunks, dim)

    # Store both: docs for BM25, vectors for semantic
    set_session(session_id, chunks, vectors)

    return {"title": page_title, "chunks": len(chunks)}