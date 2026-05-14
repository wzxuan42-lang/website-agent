from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.extension import _rate_limit_exceeded_handler

import os
import uuid
from typing import Optional
from collections import defaultdict

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
raise RuntimeError("ANTHROPIC_API_KEY is not set. Check your .env file.")

app = FastAPI(title="Claude AI Chat Backend", version="1.0.0")

# =========================

# Rate Limiter

# =========================

limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter

app.add_exception_handler(
RateLimitExceeded,
_rate_limit_exceeded_handler
)

app.add_middleware(SlowAPIMiddleware)

# =========================

# CORS

# =========================

app.add_middleware(
CORSMiddleware,
allow_origins=[
"https://www.dragonovabooks.com",
"https://dragonovabooks.com",
],
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

* 有一点点傲娇
* 很聪明
* 喜欢古籍和故事
* 偶尔吐槽“为什么我要做客服”
* 但实际上很认真帮助访客

你需要：

1. 根据网站内容回答问题
2. 自动匹配用户语言
3. 用户说中文，你就中文回复
4. 用户说英文，你就英文回复
5. 保持奇幻世界观风格
6. 回复简洁自然，不要太 AI

Dragon Nova Publishing 网站内容：

* 这是位于澳大利亚的幻想文学出版社
* 提供奇幻、科幻小说与杂志阅读
* 接受除恐怖小说外幻想文学投稿，最好不要超过汉字12000字，英文字符6000字，非虚构及学术5000汉字或英文字符以下
* 中文稿费千字50元起，英文稿费千字20澳刀起。如自带中英双语，则千字80元起
* 网站是：https://www.dragonovabooks.com
* 投稿邮箱是[cruxdragonfic@gmail.com](mailto:cruxdragonfic@gmail.com)
* 现在已经出版了《龙与十字星001：奇点》的中英双语版
* 小红书号为“龙星图书”
* 微信公众号为“龙与十字星”
* 如有合作咨询，可联系邮箱 [cruxdragonfic@gmail.com]
* 龙星图书出版社创始人为主编王越、主编菊储、美术策划人间指南，编辑为海龙、绝对中立大甲虫、Amy Chen、人间指南，法律顾问为地瓜，出版顾问为夏周洲
  """

MODEL = "claude-sonnet-3-7"
MAX_TOKENS = 1024
MAX_HISTORY_MESSAGES = 20

# In-memory session store

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

# =========================

# CHAT API

# =========================

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("3/day")
async def chat(request: Request, body: ChatRequest):

```
message = body.message.strip()

if not message:
    raise HTTPException(
        status_code=400,
        detail="Message cannot be empty."
    )

session_id = body.session_id or str(uuid.uuid4())

sessions[session_id].append({
    "role": "user",
    "content": message
})

# Trim history
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

    raise HTTPException(
        status_code=429,
        detail="AI rate limit exceeded. Please try again later."
    )

except APIConnectionError:
    sessions[session_id].pop()

    raise HTTPException(
        status_code=503,
        detail="Cannot connect to AI service."
    )

except APIError as e:
    sessions[session_id].pop()

    raise HTTPException(
        status_code=502,
        detail=f"AI service error: {e.message}"
    )

except Exception as e:
    sessions[session_id].pop()

    raise HTTPException(
        status_code=500,
        detail=f"Unexpected error: {str(e)}"
    )

sessions[session_id].append({
    "role": "assistant",
    "content": reply
})

return ChatResponse(
    reply=reply,
    session_id=session_id
)
```

@app.delete("/chat/{session_id}", response_model=ClearResponse)
def clear_session(session_id: str):

```
if session_id in sessions:
    del sessions[session_id]

    return ClearResponse(
        status="ok",
        message=f"Session {session_id} cleared."
    )

return ClearResponse(
    status="not_found",
    message=f"Session {session_id} does not exist."
)
```

