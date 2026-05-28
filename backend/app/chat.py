from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import BM25Retriever

from app.store import get_session_docs

RAG_PROMPT = PromptTemplate(
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

def build_context(session_id: str, question: str, k: int = 6) -> str:
    docs = get_session_docs(session_id)

    retriever = BM25Retriever.from_documents(docs)
    retriever.k = min(k, len(docs))
    relevant_docs = retriever.invoke(question)

    return "\n\n---\n\n".join(d.page_content for d in relevant_docs)

def answer_question(session_id: str, question: str) -> str:
    context = build_context(session_id, question, k=6)

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=512
    )

    chain = RAG_PROMPT | llm | StrOutputParser()
    return chain.invoke({"context": context, "question": question})