import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.store import get_session

RAG_PROMPT = PromptTemplate(
    template="""You are a helpful assistant answering questions about a webpage the user is currently viewing. Use the context below to answer the question. The context is extracted from the page, so trust it. If the context genuinely does not contain the answer, say "I could not find that on this page". Keep the answer concise and direct. Do not say "based on the context", just answer naturally.
Context:
{context}

Question: {question}
Answer:""",
    input_variables=["context", "question"],
)

def answer_question(session_id: str, question: str) -> str:
    """
    Retrieve relevant chunks for the question and generate an answer via Groq.

    Raises:
        KeyError: if session_id doesn't exist / expired / evicted
    """
    vectorstore = get_session(session_id)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
    relevant_docs = retriever.invoke(question)
    context = "\n\n---\n\n".join(doc.page_content for doc in relevant_docs)

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=512,
    )

    parser = StrOutputParser()
    chain = RAG_PROMPT | llm | parser

    return chain.invoke({"context": context, "question": question})