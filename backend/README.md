# 考研 AI 平台 — FastAPI 后端

## 功能模块

| 模块 | 路由前缀 | 说明 |
|------|----------|------|
| AI 聊天 | `/api/chat` | 多轮对话、SSE 流式输出、图片题识别 |
| 错题本 | `/api/wrong-questions` | 分类管理、图片上传、AI 解析、一键追问 |
| RAG | `scripts/init_knowledge.py` | Chroma + LlamaIndex 公共/私有知识库 |

## 快速启动

```bash
# 1. 配置 API Key（项目根目录 .env）
DASHSCOPE_API_KEY=sk-xxx

# 2. 安装依赖
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 3. 初始化知识库（可选，需先放入 data/public/ 资料）
python scripts/init_knowledge.py

# 4. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

## 目录结构

```
kaoyan-ai-platform/
├── .env                          # 环境变量（含百炼 API Key）
├── data/public/                  # 公共考研资料 → RAG 公共库
├── uploads/
│   ├── wrong_questions/          # 错题图片
│   └── chat/                     # 聊天上传图片
├── chroma_db/                    # Chroma 向量库持久化
├── kaoyan.db                     # SQLite 业务数据
└── backend/
    ├── app/
    │   ├── main.py               # FastAPI 入口
    │   ├── config.py             # 配置
    │   ├── database.py           # ORM 模型
    │   ├── routers/
    │   │   ├── chat.py           # 聊天路由
    │   │   └── wrong_questions.py
    │   └── services/
    │       ├── ai_service.py     # 百炼 LLM / VL
    │       ├── rag_service.py    # LlamaIndex + Chroma
    │       ├── agent_service.py  # LangGraph Agent
    │       ├── chat_service.py
    │       └── wrong_question_service.py
    └── scripts/
        └── init_knowledge.py     # 知识库初始化
```
