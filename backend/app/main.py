import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from app.scraper import scrape_and_store
from app.chat import answer_question
from app.store import delete_session, stats

load_dotenv()

app = FastAPI(
    title="WebChat API",
    description="Chat with any webpage using LangChain + Groq",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten after dev
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
    return {"status": "WebChat API is running"}

@app.get("/_stats")
def _stats():
    active, max_sessions = stats()
    return {"sessions_active": active, "sessions_max": max_sessions}

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):
    try:
        session_id = str(uuid.uuid4())
        result = scrape_and_store(url=request.url, session_id=session_id)
        return ScrapeResponse(
            session_id=session_id,
            page_title=result["title"],
            chunks_stored=result["chunks"],
            message="Page loaded and indexed successfully.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        answer = answer_question(session_id=request.session_id, question=request.question)
        return ChatResponse(answer=answer, session_id=request.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found. Please scrape the page first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    if delete_session(session_id):
        return {"message": f"Session {session_id} cleared."}
    raise HTTPException(status_code=404, detail="Session not found.")