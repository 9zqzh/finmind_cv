"""FastAPI 应用入口。

启动方式（在 backend 目录下）：
    .venv\\Scripts\\python -m uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import admin, auth, chat, competitions, conversations, information, jwxt, knowledge, playbooks, resources
from app.agent.evolution_scheduler import start_scheduler, stop_scheduler
from app.config import get_settings
from app.db import build_engine, build_session_factory
from app.knowledge import KnowledgeService
from app.knowledge.factory import build_knowledge_service
from app.schemas.common import INVALID_PARAM, ApiError, fail, ok
from app.services.conversation import ConversationManager
from app.services.crypto import CookieCipher
from app.services.session import SessionManager

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时验证数据库并初始化会话管理器、对话服务与知识库。"""
    settings = get_settings()
    if not settings.database_url.strip():
        raise RuntimeError("DATABASE_URL is required")
    cipher = CookieCipher(settings.encryption_keys)
    engine = build_engine(settings.database_url)
    sessions = build_session_factory(engine)
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    app.state.db_engine = engine
    app.state.db_sessions = sessions
    app.state.sessions = SessionManager(settings, cipher)
    app.state.conversations = ConversationManager()
    app.state.knowledge = build_knowledge_service(
        BASE_DIR / settings.knowledge_dir,
        settings,
        collection_name="knowledge",
    )
    app.state.information = KnowledgeService.from_directory(
        BASE_DIR / settings.information_dir
    )
    # 定时自进化后台任务（产出草稿，仍需管理员审核）
    app.state.evolution_task = start_scheduler(sessions)
    try:
        yield
    finally:
        await stop_scheduler(app.state.evolution_task)
        await app.state.sessions.close()
        await engine.dispose()


app = FastAPI(
    title="数智金院 FinMind Backend",
    description="PydanticAI Agent + 教务接口 + 轻量知识库",
    version="0.1.0",
    lifespan=lifespan,
)

# 原型阶段放开跨域，便于前端本地联调；生产环境应收紧 origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(competitions.router)
app.include_router(information.router)
app.include_router(jwxt.router)
app.include_router(knowledge.router)
app.include_router(playbooks.router)
app.include_router(resources.router)
app.include_router(admin.router)


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=fail(INVALID_PARAM, f"请求参数不合法：{exc.errors()[:3]}"),
    )


@app.get("/", tags=["health"])
async def health():
    """健康检查。"""
    settings = get_settings()
    return ok(
        {
            "service": "college-assistant-backend",
            "env": settings.app_env,
            "model_configured": settings.model_configured,
        }
    )
