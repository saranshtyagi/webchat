# WebChat API — Backend

FastAPI backend for the **WebChat Chrome Extension**.  
Chat with any webpage using LangChain + FAISS + Groq.

## How it works

```
User opens a tab
  → Extension sends URL to /scrape
  → WebBaseLoader fetches the page
  → Text is split into chunks, embedded, stored in FAISS
  → Extension sends question to /chat
  → FAISS retrieves the most relevant chunks (RAG)
  → Groq (Llama 3.1 8B) generates an answer
  → Answer appears in the popup
```

## Local setup

```bash
# 1. Clone and enter directory
git clone <your-repo-url>
cd webchat-backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# → Paste your GROQ_API_KEY inside .env

# 5. Run the server
uvicorn app.main:app --reload
```

API docs available at: http://localhost:8000/docs

## API Reference

### `POST /scrape`
Load and index a webpage for a session.

**Request:**
```json
{ "url": "https://en.wikipedia.org/wiki/Python_(programming_language)" }
```

**Response:**
```json
{
  "session_id": "abc-123",
  "page_title": "Python (programming language)",
  "chunks_stored": 42,
  "message": "Page loaded and indexed successfully."
}
```

### `POST /chat`
Ask a question about the indexed page.

**Request:**
```json
{
  "session_id": "abc-123",
  "question": "Who created Python?"
}
```

**Response:**
```json
{
  "answer": "Python was created by Guido van Rossum.",
  "session_id": "abc-123"
}
```

### `DELETE /session/{session_id}`
Free memory for a session.

## Deploying to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
5. Add `GROQ_API_KEY` in the Environment tab
6. Deploy — your API will be live at `https://webchat-api.onrender.com`

## Project structure

```
webchat-backend/
├── app/
│   ├── main.py      ← FastAPI routes (/scrape, /chat)
│   ├── scraper.py   ← WebBaseLoader → chunks → FAISS
│   ├── chat.py      ← RAG chain: retrieve → Groq → answer
│   └── store.py     ← In-memory session store
├── requirements.txt
├── render.yaml      ← Render deployment config
└── .env.
```
