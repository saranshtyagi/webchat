import os 
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from app.store import session_store

os.environ.setdefault("USER_AGENT", "Mozilla/5.0 (WebChat Extension)")

def scrape_and_store(url: str, session_id: str) -> dict:
    """
    Load a webpage, chunk it, embed it, and cache the vector store. 
    Returns:
        dict with 'title' and 'chunks' count.
    """

    # Step 1: Load the webpage

    loader = WebBaseLoader(url)
    docs = loader.load()

    page_title = docs[0].metadata.get("title", url) if docs else url

    #Step 2: Split into chunks 

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, 
        chunk_overlap=80, 
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks =  splitter.split_documents(docs)

    # Step 3: Embed the chunks

    embeddings= HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )

    # Step 4: Store in FAISS
    vectorstore = FAISS.from_documents(chunks, embeddings)

    session_store[session_id] = vectorstore

    return {
        "title": page_title, 
        "chunks": len(chunks)
    }