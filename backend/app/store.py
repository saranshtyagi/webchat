import time
from dataclasses import dataclass
from typing import Dict, List

from langchain_core.documents import Document

@dataclass
class SessionEntry:
    docs: List[Document]
    last_access: float

# 512MB-safe defaults
MAX_SESSIONS_IN_MEMORY = 4
SESSION_TTL_SECONDS = 20 * 60  # 20 minutes

session_store: Dict[str, SessionEntry] = {}

def _now() -> float:
    return time.time()

def _purge_expired() -> None:
    cutoff = _now() - SESSION_TTL_SECONDS
    expired = [sid for sid, entry in session_store.items() if entry.last_access < cutoff]
    for sid in expired:
        session_store.pop(sid, None)

def _evict_lru_if_needed() -> None:
    if len(session_store) <= MAX_SESSIONS_IN_MEMORY:
        return
    oldest_sid, _ = min(session_store.items(), key=lambda kv: kv[1].last_access)
    session_store.pop(oldest_sid, None)

def set_session(session_id: str, docs: List[Document]) -> None:
    _purge_expired()
    session_store[session_id] = SessionEntry(docs=docs, last_access=_now())
    _evict_lru_if_needed()

def get_session_docs(session_id: str) -> List[Document]:
    _purge_expired()
    entry = session_store[session_id]  # KeyError if missing
    entry.last_access = _now()
    return entry.docs

def delete_session(session_id: str) -> bool:
    _purge_expired()
    return session_store.pop(session_id, None) is not None

def stats():
    _purge_expired()
    return (len(session_store), MAX_SESSIONS_IN_MEMORY)