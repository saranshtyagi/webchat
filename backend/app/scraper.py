import os
import time
import bs4
from collections import OrderedDict

from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

try:
    from app.store import session_store  # expected: dict-like
except Exception:
    session_store = {}

os.environ.setdefault("USER_AGENT", "Mozilla/5.0 (WebChat Extension)")

# ----------------------------
# Memory safety controls
# ----------------------------
MAX_SESSIONS_IN_MEMORY = 3         # keep only last N sessions
MAX_DOC_CHARS = 200_000            # cap extracted text per document
MAX_TOTAL_CHARS = 400_000          # cap total across all docs
MAX_CHUNKS = 250                   # hard cap number of chunks to embed/index
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

_session_lru = OrderedDict()


EMBEDDINGS = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cpu"},
)

def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())

def _trim_docs(docs):
    """Trim document content to avoid huge memory usage."""
    total = 0
    trimmed = []
    for d in docs:
        content = _normalize_whitespace(d.page_content)
        if not content:
            continue

        # cap per-doc
        content = content[:MAX_DOC_CHARS]

        # cap total
        remaining = MAX_TOTAL_CHARS - total
        if remaining <= 0:
            break
        content = content[:remaining]
        total += len(content)

        d.page_content = content
        trimmed.append(d)
    return trimmed

def _evict_if_needed():
    """Evict oldest sessions to keep memory bounded."""
    while len(_session_lru) > MAX_SESSIONS_IN_MEMORY:
        old_session_id, _ = _session_lru.popitem(last=False)
        # Remove from the external store too
        try:
            session_store.pop(old_session_id, None)
        except Exception:
            pass

def _touch_session(session_id: str, vectorstore):
    now = time.time()
    _session_lru.pop(session_id, None)
    _session_lru[session_id] = {"vs": vectorstore, "ts": now}

    # Keep compatibility: store vectorstore directly like your old code
    session_store[session_id] = vectorstore

    _evict_if_needed()

def scrape_and_store(url: str, session_id: str) -> dict:
    """
    Load a webpage, chunk it, embed it, and cache the vector store.

    Returns:
        dict with 'title' and 'chunks' count.
    """

    # Step 1: Load the webpage (parse only likely-content tags)
    strainer = bs4.SoupStrainer(["article", "main", "p", "h1", "h2", "h3", "h4", "li"])
    loader = WebBaseLoader(url, bs_kwargs={"parse_only": strainer})
    docs = loader.load()

    page_title = docs[0].metadata.get("title", url) if docs else url

    # Normalize + cap content to control memory/time
    docs = _trim_docs(docs)

    # Step 2: Split into chunks (cap chunk count)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    if len(chunks) > MAX_CHUNKS:
        chunks = chunks[:MAX_CHUNKS]

    # Step 3+4: Embed and store in FAISS (uses global EMBEDDINGS)
    vectorstore = FAISS.from_documents(chunks, EMBEDDINGS)

    # Store in bounded in-memory cache
    _touch_session(session_id, vectorstore)

    return {
        "title": page_title,
        "chunks": len(chunks),
    }