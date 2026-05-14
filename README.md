# Claude AI Chat Backend

基于 FastAPI + Anthropic Claude Sonnet 4 的聊天后端，支持多轮对话，可直接部署到 Railway。

## 项目结构

```
website-agent/
├── main.py            # FastAPI 应用主文件
├── requirements.txt   # Python 依赖
├── .env.example       # 环境变量模板
├── .env               # 本地环境变量（不提交 Git）
├── .gitignore
├── Procfile           # Railway / Heroku 启动文件
├── railway.json       # Railway 部署配置
└── README.md
```

## 快速启动（本地）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 Anthropic API Key
```

`.env` 内容：

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
```

### 3. 启动服务

```bash
uvicorn main:app --reload --port 8000
```

服务启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

---

## API 说明

### POST /chat — 发送消息

**请求体：**

```json
{
  "message": "你好，请介绍一下你自己",
  "session_id": "可选，用于多轮对话"
}
```

**响应：**

```json
{
  "reply": "你好！我是本网站官方 AI 助手...",
  "session_id": "abc123-xxxx-xxxx"
}
```

> 首次请求不传 `session_id`，服务会自动生成并在响应中返回。后续请求传入相同的 `session_id` 即可保持对话上下文。

---

### DELETE /chat/{session_id} — 清除会话历史

```bash
curl -X DELETE http://localhost:8000/chat/your-session-id
```

---

### GET /health — 健康检查

```bash
curl http://localhost:8000/health
```

---

## 多轮对话示例

```bash
# 第一轮
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "我叫小明"}'

# 响应中获取 session_id，比如 "abc-123"

# 第二轮（传入 session_id）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "我叫什么名字？", "session_id": "abc-123"}'

# AI 会记得上文，回答"你叫小明"
```

---

## 部署到 Railway

### 方式一：GitHub 自动部署

1. 将项目推送到 GitHub
2. 在 [Railway](https://railway.app) 创建新项目，选择 **Deploy from GitHub repo**
3. 在 Railway 项目的 **Variables** 中添加：
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
   ```
4. Railway 自动检测 `Procfile` 并完成部署

### 方式二：Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

---

## 错误码说明

| 状态码 | 含义 |
|--------|------|
| 400 | 请求消息为空 |
| 429 | Anthropic API 速率限制，稍后重试 |
| 503 | 无法连接 AI 服务 |
| 502 | AI 服务返回错误 |
| 500 | 服务器内部错误 |
