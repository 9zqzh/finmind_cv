"""Agent 编排层：构建 Agent、执行对话、包装统一响应。

超时控制说明：不用 asyncio.wait_for 包裹 agent.run（与 pydantic-ai 内部
任务图不兼容），而是依赖 AsyncOpenAI 客户端自带的请求超时。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, AsyncGenerator

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelResponse, ThinkingPart

from app.agent.model_client import build_model
from app.agent.prompts import build_system_prompt
from app.agent.tools import AgentDeps, register_tools
from app.config import Settings, get_settings
from app.knowledge import KnowledgeService
from app.schemas.chat import ChatResponse, ToolCallInfo
from app.schemas.common import MODEL_ERROR, ApiError
from app.services.conversation import ConversationMemory
from app.services.session import JwxtSession

_AGENT: Agent | None = None

# 以下结果在对话界面只呈现文字总结，不渲染结构化卡片、不把原始数据发给前端：
# - knowledge/information：不展示知识库 markdown 原文卡片与源文件清单
# - empty_classrooms：空闲教室名单已由模型用自然语言汇总，不渲染原始 JSON
# - website/website_detail：官网搜索结果与页面正文由模型总结提炼，不展示结构化条目
# - academic：学术资源搜索结果由模型总结并附上链接与下载地址，不展示结构化条目
# - competition/competition_detail：竞赛列表与详情由模型逐场汇总并附链接，不展示结构化条目
# - competition_notice/competition_club：竞赛平台通知与社团由模型归纳介绍并附链接，不展示结构化条目
_TEXT_ONLY_RESULT_TYPES = {
    "knowledge",
    "information",
    "empty_classrooms",
    "website",
    "website_detail",
    "academic",
    "competition",
    "competition_detail",
    "competition_notice",
    "competition_club",
}

# 对话记忆滑动窗口：只保留最近 4 组“用户提问 + AI 回答”。
HISTORY_MAX_TURNS = 4


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
    memory: ConversationMemory | None = None,
    settings: Settings | None = None,
) -> ChatResponse:
    """执行一轮对话并返回统一结构的 ChatResponse。

    传入持久化对话记忆时，把最近四轮作为 message_history 传入模型，
    并在本轮成功完成后保存新增消息。
    """
    settings = settings or get_settings()
    agent = get_agent(settings)
    history = _load_history(memory)
    try:
        result = await agent.run(message, deps=deps, message_history=history or None)
    except AgentRunError as exc:
        raise ApiError(MODEL_ERROR, f"模型服务请求失败：{exc}", status_code=502) from exc
    except TimeoutError as exc:
        raise ApiError(MODEL_ERROR, "模型响应超时，请稍后重试", status_code=504) from exc

    answer = str(result.output)
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
    response = ChatResponse(
        answer=answer,
        intent=deps.last_result_type if deps.tool_events else "chat",
        tool_calls=tool_calls,
        result_type=result_type,
        data=data,
        sources=sources,
        conversation_id=memory.conversation_id if memory else None,
    )
    await _save_turn(memory, message, result, response)
    return response


def _load_history(memory: ConversationMemory | None):
    """恢复最近四轮模型消息；损坏时清空临时记忆并降级为空历史。"""
    if memory is None or not memory.chat_history:
        return []
    try:
        history = []
        for turn in memory.chat_history:
            history.extend(ModelMessagesTypeAdapter.validate_json(turn.model_messages_json))
        return history
    except Exception:
        # 历史不可用（如 pydantic-ai 升级导致格式不兼容）不影响本轮对话
        memory.chat_history.clear()
        return []


async def _save_turn(
    memory: ConversationMemory | None,
    user_message: str,
    result,
    response: ChatResponse,
) -> None:
    """保存本轮新增模型消息，并裁剪至最近 HISTORY_MAX_TURNS 轮。"""
    if memory is None:
        return
    try:
        messages = [
            replace(message, parts=[part for part in message.parts if not isinstance(part, ThinkingPart)])
            if isinstance(message, ModelResponse)
            else message
            for message in result.new_messages()
        ]
        messages_json = ModelMessagesTypeAdapter.dump_json(messages)
    except Exception:
        return
    await memory.save(user_message, messages_json.decode(), response.model_dump(mode="json"))

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
    memory: ConversationMemory | None = None,
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
    history = _load_history(memory)
    try:
        async with agent.run_stream_events(
            message, deps=deps, message_history=history or None
        ) as stream:
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
                        conversation_id=memory.conversation_id if memory else None,
                    )
                    await _save_turn(memory, message, ev.result, response)
                    yield {"type": "done", "chat": response.model_dump()}
    except AgentRunError as exc:
        yield {"type": "error", "message": f"模型服务请求失败：{exc}"}
    except TimeoutError as exc:
        yield {"type": "error", "message": "模型响应超时，请稍后重试"}
