import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from app.scraper import scrape_and_store
from app.chat import answer_question

load_dotenv()

app = FastAPI(
    title='WebChat API', 
    description="Chat with any webpage using LangChain + Groq",
    version="1.0.0"
)

# Allow requests from Chrome extension and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten this after dev
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    url: str

class ScrapeResponse(BaseModel):
    session_id: str
    page_title: str
    chunks_stored: int
    message: str

class ChatRequest(BaseModel):
    session_id: str
    question: str

class ChatResponse(BaseModel):
    answer: str
    session_id: str


@app.get("/")
def root():
    return {"status": "WebChat API is running 🚀"}


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):
    """
    Step 1 of the flow:
    - Load the webpage using WebBaseLoader 
    - Split it into chunks
    - Embed each chunk and store in a FAISS vector store
    - Return a session_id the extension will use for follow-up questions
    """
    try:
        session_id = str(uuid.uuid4())
        result = scrape_and_store(url=request.url, session_id=session_id)
        return ScrapeResponse(
            session_id=session_id,
            page_title=result["title"],
            chunks_stored=result["chunks"],
            message="Page loaded and indexed successfully."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Step 2 of the flow:
    - Look up the FAISS store for this session
    - Retrieve the most relevant chunks for the question (RAG)
    - Pass chunks + question to Groq LLM
    - Return the answer
    """
    try:
        answer = answer_question(
            session_id=request.session_id,
            question=request.question
        )
        return ChatResponse(answer=answer, session_id=request.session_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please scrape the page first."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    """Free memory by deleting a session's vector store."""
    from app.store import session_store
    if session_id in session_store:
        del session_store[session_id]
        return {"message": f"Session {session_id} cleared."}
    raise HTTPException(status_code=404, detail="Session not found.")
