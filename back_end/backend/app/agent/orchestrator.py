"""Agent 编排层：构建 Agent、执行对话、包装统一响应。

超时控制说明：不用 asyncio.wait_for 包裹 agent.run（与 pydantic-ai 内部
任务图不兼容），而是依赖 AsyncOpenAI 客户端自带的请求超时。
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError

from app.agent.model_client import build_model
from app.agent.prompts import build_system_prompt
from app.agent.tools import AgentDeps, register_tools
from app.config import Settings, get_settings
from app.knowledge import KnowledgeService
from app.schemas.chat import ChatResponse, ToolCallInfo
from app.schemas.common import MODEL_ERROR, ApiError
from app.services.session import JwxtSession

_AGENT: Agent | None = None

# 知识库/资讯类结果在对话界面只呈现文字总结，不渲染文档卡片、不展示源文件名
_TEXT_ONLY_RESULT_TYPES = {"knowledge", "information"}


def get_agent(settings: Settings | None = None) -> Agent:
    """获取全局 Agent 单例（懒加载，避免无密钥时导入失败）。"""
    global _AGENT
    if _AGENT is None:
        settings = settings or get_settings()
        agent = Agent(
            build_model(settings),
            deps_type=AgentDeps,
            system_prompt=build_system_prompt(),
        )
        register_tools(agent)
        _AGENT = agent
    return _AGENT


def build_deps(
    session: JwxtSession | None,
    knowledge: KnowledgeService,
    information: KnowledgeService,
) -> AgentDeps:
    """为单次对话构造工具依赖。"""
    return AgentDeps(session=session, knowledge=knowledge, information=information)


async def run_chat(
    message: str,
    deps: AgentDeps,
    settings: Settings | None = None,
) -> ChatResponse:
    """执行一轮对话并返回统一结构的 ChatResponse。"""
    settings = settings or get_settings()
    agent = get_agent(settings)
    try:
        result = await agent.run(message, deps=deps)
    except AgentRunError as exc:
        raise ApiError(MODEL_ERROR, f"模型服务请求失败：{exc}", status_code=502) from exc
    except TimeoutError as exc:
        raise ApiError(MODEL_ERROR, "模型响应超时，请稍后重试", status_code=504) from exc

    tool_calls = [
        ToolCallInfo(
            tool=event["tool"],
            result_type=event.get("result_type", "text"),
        )
        for event in deps.tool_events
    ]
    result_type = deps.last_result_type if deps.tool_events else "text"
    if result_type in _TEXT_ONLY_RESULT_TYPES:
        # 检索类结果降级为纯文本：Agent 的 answer 已包含总结提炼内容，
        # 不再把知识库 markdown 原文卡片与源文件清单返回到对话界面
        result_type = "text"
        data = None
        sources: list[str] = []
    else:
        data = deps.last_data if deps.tool_events else None
        sources = deps.sources
    return ChatResponse(
        answer=str(result.output),
        intent=deps.last_result_type if deps.tool_events else "chat",
        tool_calls=tool_calls,
        result_type=result_type,
        data=data,
        sources=sources,
    )
