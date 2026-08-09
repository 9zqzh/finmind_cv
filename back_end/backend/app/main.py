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

from app.api import auth, chat, competitions, information, jwxt, knowledge, resources
from app.config import get_settings
from app.knowledge import KnowledgeService
from app.knowledge.factory import build_knowledge_service
from app.schemas.common import INVALID_PARAM, ApiError, fail, ok
from app.services.conversation import ConversationManager
from app.services.session import SessionManager

BASE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化会话管理器、临时对话记忆与知识库。"""
    settings = get_settings()
    app.state.sessions = SessionManager(settings)
    app.state.conversations = ConversationManager(settings)
    app.state.knowledge = build_knowledge_service(
        BASE_DIR / settings.knowledge_dir,
        settings,
        collection_name="knowledge",
    )
    app.state.information = KnowledgeService.from_directory(
        BASE_DIR / settings.information_dir
    )
    yield


app = FastAPI(
    title="学院教学小助手 Backend",
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
app.include_router(competitions.router)
app.include_router(information.router)
app.include_router(jwxt.router)
app.include_router(knowledge.router)
app.include_router(resources.router)


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
