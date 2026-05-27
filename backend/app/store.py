import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from langchain_community.vectorstores import FAISS


@dataclass
class SessionEntry:
    vectorstore: FAISS
    last_access: float


# Config tuned for 512MB Render
MAX_SESSIONS_IN_MEMORY = 3          # keep only last 3 sessions
SESSION_TTL_SECONDS = 20 * 60       # 20 minutes


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
    # Evict least-recently-used
    oldest_sid, _ = min(session_store.items(), key=lambda kv: kv[1].last_access)
    session_store.pop(oldest_sid, None)


def set_session(session_id: str, vectorstore: FAISS) -> None:
    _purge_expired()
    session_store[session_id] = SessionEntry(vectorstore=vectorstore, last_access=_now())
    _evict_lru_if_needed()


def get_session(session_id: str) -> FAISS:
    _purge_expired()
    entry = session_store[session_id]  # raises KeyError if missing
    entry.last_access = _now()
    return entry.vectorstore


def delete_session(session_id: str) -> bool:
    _purge_expired()
    return session_store.pop(session_id, None) is not None


def stats() -> Tuple[int, int]:
    """(active_sessions, max_sessions)"""
    _purge_expired()
    return (len(session_store), MAX_SESSIONS_IN_MEMORY)