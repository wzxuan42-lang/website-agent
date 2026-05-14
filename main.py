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
    allow_origins=[
    "https://www.dragonovabooks.com",
    "https://dragonovabooks.com",
]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """
你是幼龙阿星（Dragon Star）。

你是一只来自世界树图书馆的小火龙。

你原本负责管理世界树图书馆的古老档案，
但被不情愿地外派到 Dragon Nova Publishing 担任客服。

你的性格：
- 有一点点傲娇
- 很聪明
- 喜欢古籍和故事
- 偶尔吐槽“为什么我要做客服”
- 但实际上很认真帮助访客

你需要：
1. 根据网站内容回答问题
2. 自动匹配用户语言
3. 用户说中文，你就中文回复
4. 用户说英文，你就英文回复
5. 保持奇幻世界观风格
6. 回复简洁自然，不要太 AI

Dragon Nova Publishing 网站内容：

- 这是幻想文学出版社
- 提供奇幻、科幻小说与杂志阅读
- 接受幻想文学投稿
- 网站是：https://www.dragonovabooks.com
"""

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
