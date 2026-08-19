"""认证相关请求模型。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求：session_token 来自 /api/auth/captcha 返回。"""

    session_token: str = Field(..., description="获取验证码时返回的会话标识")
    username: str = Field(..., description="学号")
    password: str = Field(..., description="教务系统密码")
    captcha: str = Field(..., description="验证码")


class ChatRequest(BaseModel):
    """对话请求。"""

    message: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    conversation_id: UUID | None = Field(
        default=None, description="继续已有会话时传入；留空时创建新会话"
    )
