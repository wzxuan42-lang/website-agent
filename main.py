from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from dotenv import load_dotenv
import os
import uuid
from typing import Optional
from collections import defaultdict

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY is not set. Check your .env file.")

app = FastAPI(title="Claude AI Chat Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """你是本网站官方 AI 助手。
请专业、简洁地回答用户问题。
如果不确定，不要编造答案。"""

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024
MAX_HISTORY_MESSAGES = 20  # keep last N messages per session

# In-memory session store: session_id -> list[{"role": ..., "content": ...}]
sessions: dict[str, list] = defaultdict(list)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ClearResponse(BaseModel):
    status: str
    message: str


@app.get("/")
def root():
    return {"status": "ok", "message": "Claude AI Chat Backend is running"}


@app.get("/health")
def health():
    return {"status": "healthy", "model": MODEL}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = request.session_id or str(uuid.uuid4())

    sessions[session_id].append({"role": "user", "content": message})

    # Trim oldest messages if history is too long (keep it even so roles stay balanced)
    if len(sessions[session_id]) > MAX_HISTORY_MESSAGES:
        trim_to = MAX_HISTORY_MESSAGES
        if trim_to % 2 != 0:
            trim_to -= 1
        sessions[session_id] = sessions[session_id][-trim_to:]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=sessions[session_id],
        )
        reply = response.content[0].text
    except RateLimitError:
        sessions[session_id].pop()
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    except APIConnectionError:
        sessions[session_id].pop()
        raise HTTPException(status_code=503, detail="Cannot connect to AI service. Please try again later.")
    except APIError as e:
        sessions[session_id].pop()
        raise HTTPException(status_code=502, detail=f"AI service error: {e.message}")
    except Exception as e:
        sessions[session_id].pop()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    sessions[session_id].append({"role": "assistant", "content": reply})

    return ChatResponse(reply=reply, session_id=session_id)


@app.delete("/chat/{session_id}", response_model=ClearResponse)
def clear_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
        return ClearResponse(status="ok", message=f"Session {session_id} cleared.")
    return ClearResponse(status="not_found", message=f"Session {session_id} does not exist.")
