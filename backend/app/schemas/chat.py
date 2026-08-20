"""对话响应模型（与技术文档 5.3 节约定一致）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# 前端按 result_type 渲染不同卡片
ResultType = Literal[
    "text",
    "schedule",
    "classroom_schedule",
    "grades",
    "grade_detail",
    "training_plan",
    "knowledge",
    "information",
    "map_places",
    "map_route",
]

CitationType = Literal["map_place", "map_route"]


class CitationInfo(BaseModel):
    """AI 正文中引用标签对应的可信结构化数据。"""

    ref: str = Field(..., description="仅在当前回答内有效的不透明引用编号")
    type: CitationType
    title: str
    url: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ToolCallInfo(BaseModel):
    """单次工具调用摘要，便于前端展示"AI 做了什么"。"""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_type: ResultType = "text"


class ChatResponse(BaseModel):
    """Agent 对话统一返回结构。"""

    answer: str = Field(..., description="自然语言回答")
    intent: str = Field(default="unknown", description="识别到的意图")
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    result_type: ResultType = Field(default="text")
    data: Any = Field(default=None, description="结构化结果，供前端渲染卡片")
    sources: list[str] = Field(default_factory=list, description="知识来源")
    citations: list[CitationInfo] = Field(
        default_factory=list, description="正文 citation 标签对应的结构化引用"
    )
    playbook: str | None = Field(
        default=None, description="本轮命中的操作手册标题，未命中为空"
    )
    conversation_id: str | None = Field(
        default=None,
        description="数据库会话标识；后续请求携带它以继续多轮对话",
    )
