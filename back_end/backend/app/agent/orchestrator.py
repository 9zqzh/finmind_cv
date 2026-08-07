"""Agent 编排层：构建 Agent、执行对话、包装统一响应。

超时控制说明：不用 asyncio.wait_for 包裹 agent.run（与 pydantic-ai 内部
任务图不兼容），而是依赖 AsyncOpenAI 客户端自带的请求超时。
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.messages import ModelMessagesTypeAdapter

from app.agent.model_client import build_model
from app.agent.prompts import build_system_prompt
from app.agent.tools import AgentDeps, register_tools
from app.config import Settings, get_settings
from app.knowledge import KnowledgeService
from app.schemas.chat import ChatResponse, ToolCallInfo
from app.schemas.common import MODEL_ERROR, ApiError
from app.services.session import ChatTurn, JwxtSession

_AGENT: Agent | None = None

# 以下结果在对话界面只呈现文字总结，不渲染结构化卡片、不把原始数据发给前端：
# - knowledge/information：不展示知识库 markdown 原文卡片与源文件清单
# - empty_classrooms：空闲教室名单已由模型用自然语言汇总，不渲染原始 JSON
# - website：官网搜索结果由模型总结提炼，不展示结构化条目
# - academic：学术资源搜索结果由模型总结并附上链接与下载地址，不展示结构化条目
# - competition/competition_detail：竞赛列表与详情由模型逐场汇总并附链接，不展示结构化条目
# - competition_notice/competition_club：竞赛平台通知与社团由模型归纳介绍并附链接，不展示结构化条目
_TEXT_ONLY_RESULT_TYPES = {
    "knowledge",
    "information",
    "empty_classrooms",
    "website",
    "academic",
    "competition",
    "competition_detail",
    "competition_notice",
    "competition_club",
}

# 对话记忆滑动窗口：最多保留最近 6 轮（12 条消息），超出丢弃最早轮次
HISTORY_MAX_TURNS = 6


def _event_result_type(event: dict) -> str:
    """工具事件的对外结果类型：纯文本降级类统一规范化为 text，避免泄露到前端 schema。"""
    result_type = event.get("result_type", "text")
    return "text" if result_type in _TEXT_ONLY_RESULT_TYPES else result_type


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
    session: JwxtSession | None = None,
    settings: Settings | None = None,
) -> ChatResponse:
    """执行一轮对话并返回统一结构的 ChatResponse。

    若传入了登录会话，则启用多轮记忆：把会话中的历史轮次作为
    message_history 传入模型，并把本轮结果存回会话（滑动窗口裁剪）。
    """
    settings = settings or get_settings()
    agent = get_agent(settings)
    history = _load_history(session)
    try:
        result = await agent.run(message, deps=deps, message_history=history or None)
    except AgentRunError as exc:
        raise ApiError(MODEL_ERROR, f"模型服务请求失败：{exc}", status_code=502) from exc
    except TimeoutError as exc:
        raise ApiError(MODEL_ERROR, "模型响应超时，请稍后重试", status_code=504) from exc

    answer = str(result.output)
    _save_turn(session, message, answer, result)

    tool_calls = [
        ToolCallInfo(
            tool=event["tool"],
            result_type=_event_result_type(event),
        )
        for event in deps.tool_events
    ]
    result_type = deps.last_result_type if deps.tool_events else "text"
    if result_type in _TEXT_ONLY_RESULT_TYPES:
        # 此类结果降级为纯文本：Agent 的 answer 已包含总结提炼内容，
        # 不再把原始结构化数据（如空闲教室 JSON、知识库原文）返回到对话界面
        result_type = "text"
        data = None
        sources: list[str] = []
    else:
        data = deps.last_data if deps.tool_events else None
        sources = deps.sources
    return ChatResponse(
        answer=answer,
        intent=deps.last_result_type if deps.tool_events else "chat",
        tool_calls=tool_calls,
        result_type=result_type,
        data=data,
        sources=sources,
        conversation_id=session.token if session else None,
    )


def _load_history(session: JwxtSession | None):
    """从会话恢复历史模型消息；反序列化失败时静默降级为空历史。"""
    if session is None or not session.chat_history:
        return []
    try:
        return ModelMessagesTypeAdapter.validate_json(
            session.chat_history[-1].model_messages_json
        )
    except Exception:
        # 历史不可用（如 pydantic-ai 升级导致格式不兼容）不影响本轮对话
        session.chat_history.clear()
        return []


def _save_turn(
    session: JwxtSession | None,
    message: str,
    answer: str,
    result,
) -> None:
    """把本轮对话存入会话记忆，并裁剪至最近 HISTORY_MAX_TURNS 轮。"""
    if session is None:
        return
    try:
        messages_json = ModelMessagesTypeAdapter.dump_json(result.all_messages())
    except Exception:
        return
    session.chat_history.append(
        ChatTurn(
            user_message=message,
            assistant_message=answer,
            model_messages_json=messages_json.decode(),
        )
    )
    if len(session.chat_history) > HISTORY_MAX_TURNS:
        del session.chat_history[:-HISTORY_MAX_TURNS]
from typing import Any, AsyncGenerator

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    TextPartDelta,
    ThinkingPartDelta,
)
from pydantic_ai.run import AgentRunResultEvent


async def run_chat_stream(
    message: str,
    deps: AgentDeps,
    settings: Settings | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """流式执行对话，逐步产出事件 dict。

    产出的事件类型：
    - thinking: {"type": "thinking", "content": str}
    - tool_call: {"type": "tool_call", "tool_name": str}
    - tool_result: {"type": "tool_result", "tool_name": str, "status": "ok"}
    - text: {"type": "text", "content": str}
    - done: {"type": "done", "chat": ChatResponse dict}
    - error: {"type": "error", "message": str}
    """
    settings = settings or get_settings()
    agent = get_agent(settings)
    try:
        async with agent.run_stream_events(message, deps=deps) as stream:
            async for ev in stream:
                if isinstance(ev, PartDeltaEvent) and isinstance(ev.delta, ThinkingPartDelta):
                    yield {"type": "thinking", "content": ev.delta.content_delta}
                elif isinstance(ev, FunctionToolCallEvent):
                    yield {"type": "tool_call", "tool_name": ev.part.tool_name}
                elif isinstance(ev, FunctionToolResultEvent):
                    yield {"type": "tool_result", "tool_name": ev.part.tool_name, "status": "ok"}
                elif isinstance(ev, PartDeltaEvent) and isinstance(ev.delta, TextPartDelta):
                    yield {"type": "text", "content": ev.delta.content_delta}
                elif isinstance(ev, AgentRunResultEvent):
                    # 构建最终结构化响应
                    tool_calls = [
                        ToolCallInfo(
                            tool=evt["tool"],
                            result_type=_event_result_type(evt),
                        )
                        for evt in deps.tool_events
                    ]
                    result_type = deps.last_result_type if deps.tool_events else "text"
                    if result_type in _TEXT_ONLY_RESULT_TYPES:
                        data = None
                        sources: list[str] = []
                        final_result_type = "text"
                    else:
                        data = deps.last_data if deps.tool_events else None
                        sources = deps.sources
                        final_result_type = result_type
                    response = ChatResponse(
                        answer=str(ev.result.output),
                        intent=deps.last_result_type if deps.tool_events else "chat",
                        tool_calls=tool_calls,
                        result_type=final_result_type,
                        data=data,
                        sources=sources,
                    )
                    yield {"type": "done", "chat": response.model_dump()}
    except AgentRunError as exc:
        yield {"type": "error", "message": f"模型服务请求失败：{exc}"}
    except TimeoutError as exc:
        yield {"type": "error", "message": "模型响应超时，请稍后重试"}