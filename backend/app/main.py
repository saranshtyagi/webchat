import uuid
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from app.scraper import scrape_and_store
from app.chat import answer_question, build_context, RAG_PROMPT
from app.store import delete_session
from langchain_groq import ChatGroq

load_dotenv()

app = FastAPI(
    title="WebChat API",
    description="Chat with any webpage using LangChain + Groq",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
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

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequest):
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
    try:
        answer = answer_question(session_id=request.session_id, question=request.question)
        return ChatResponse(answer=answer, session_id=request.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found. Please scrape the page first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _sse(data: str) -> str:
    return f"data: {data}\n\n"

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    SSE streaming endpoint:
    - Builds BM25 context
    - Streams Groq tokens as SSE events
    """
    try:
        context = build_context(request.session_id, request.question, k=6)
    except KeyError:
        # stream a JSON error event
        def err_gen():
            yield _sse(json.dumps({"type": "error", "message": "Session not found. Please scrape the page first."}))
            yield _sse("[DONE]")
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    prompt = RAG_PROMPT.format(context=context, question=request.question)

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        max_tokens=512,
        streaming=True
    )

    def gen():
        try:
            for chunk in llm.stream(prompt):
                token = getattr(chunk, "content", None)
                if token:
                    yield _sse(json.dumps({"type": "token", "text": token}))
            yield _sse("[DONE]")
        except Exception as e:
            yield _sse(json.dumps({"type": "error", "message": str(e)}))
            yield _sse("[DONE]")

    return StreamingResponse(gen(), media_type="text/event-stream")

@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    if delete_session(session_id):
        return {"message": f"Session {session_id} cleared."}
    raise HTTPException(status_code=404, detail="Session not found.")