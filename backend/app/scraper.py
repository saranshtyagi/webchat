import os
import bs4
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

    strainer = bs4.SoupStrainer(
        ["article", "main", "p", "h1", "h2", "h3", "h4", "li"],
    )

    loader = WebBaseLoader(
        url,
        bs_kwargs={"parse_only": strainer},
    )
    docs = loader.load()

    page_title = docs[0].metadata.get("title", url) if docs else url

    for doc in docs:
        doc.page_content = " ".join(doc.page_content.split())

    #Step 2: Split into chunks 

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(docs)

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