import os 
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.store import session_store

RAG_PROMPT = PromptTemplate(
    template="""You are a helpful assistant that answers questions about a webpage. Use ONLY the information in the context below to answer. 
    If the answer is not in the context, say "I could not find that on this page."
    Be concise and direct.
    Context: 
    {context}
    
    Question: {question}
    Answer:""", 
    input_variables=["context", "question"]
)

def answer_question(session_id: str, question: str) -> str:
    """
    Retrieve relevant chunks for the question and generate an answer via Groq. 

    Raises: 
        KeyError: of session_id doesn't exist in the store
    """
    # Step 1: Look up this session's vector store and raise KeyError if not found
    vectorstore = session_store[session_id]
    # Step 2: Retrieve relevant chunks: similarity search embeds the question and returns the k=4 closest chunks
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    relevant_docs = retriever.invoke(question)
    # combine the retrieved chunks into one context string
    context = "\n\n---\n\n".join(doc.page_content for doc in relevant_docs)

    llm = ChatGroq(
        model="llama-3.1-8b-instant",   
        temperature=0.2,                  
        max_tokens=512
    )

    parser = StrOutputParser()
    chain = RAG_PROMPT | llm | parser

    answer = chain.invoke({
        "context": context, 
        "question": question
    })

    return answer
