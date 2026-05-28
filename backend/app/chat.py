# app/chat.py
import numpy as np
from typing import List, Dict

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from fastembed import TextEmbedding

from app.store import get_session

ANSWER_PROMPT = PromptTemplate(
    template="""You are a helpful assistant answering questions about a webpage the user is currently viewing.
Use the context below to answer the question. The context is extracted from the page, so trust it.
If the context genuinely does not contain the answer, say "I could not find that on this page".
Keep the answer concise and direct. Do not say "based on the context", just answer naturally.

Context:
{context}

Question: {question}
Answer:""",
    input_variables=["context", "question"],
)

EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_EMBEDDER = TextEmbedding(model_name=EMBED_MODEL_NAME)

def _embed_query(q: str) -> np.ndarray:
    v = list(_EMBEDDER.embed([q]))[0]
    return np.asarray(v, dtype=np.float32)

def _semantic_top_k(docs: List[Document], doc_vectors: np.ndarray, question: str, k: int = 12) -> List[int]:
    qv = _embed_query(question)  # (dim,)
    # cosine-ish ranking: normalize vectors once per request
    dv = doc_vectors
    qn = np.linalg.norm(qv) + 1e-8
    dn = np.linalg.norm(dv, axis=1) + 1e-8
    scores = (dv @ qv) / (dn * qn)

    # Top-k indices
    k = min(k, len(docs))
    idx = np.argpartition(-scores, kth=k-1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    return idx.tolist()

def _bm25_top_k(docs: List[Document], question: str, k: int = 12) -> List[int]:
    # BM25Retriever returns documents, but we need indices.
    # We'll build it and score by returned order, mapping back via id().
    retriever = BM25Retriever.from_documents(docs)
    retriever.k = min(k, len(docs))
    top_docs = retriever.invoke(question)

    pos = {id(d): i for i, d in enumerate(docs)}
    indices = []
    for d in top_docs:
        if id(d) in pos:
            indices.append(pos[id(d)])
    return indices

def _rrf_fuse(rank_lists: List[List[int]], k: int = 6, rrf_k: int = 60) -> List[int]:
    scores: Dict[int, float] = {}
    for ranks in rank_lists:
        for rank, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank + 1)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, _ in fused[:k]]

def answer_question(session_id: str, question: str) -> str:
    entry = get_session(session_id)
    docs = entry.docs
    vectors = entry.vectors

    # independent retrievals
    bm25_ids = _bm25_top_k(docs, question, k=12)
    sem_ids = _semantic_top_k(docs, vectors, question, k=12)

    # fuse
    chosen_ids = _rrf_fuse([bm25_ids, sem_ids], k=6)

    context = "\n\n---\n\n".join(docs[i].page_content for i in chosen_ids)

    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2, max_tokens=512)
    chain = ANSWER_PROMPT | llm | StrOutputParser()
    return chain.invoke({"context": context, "question": question})