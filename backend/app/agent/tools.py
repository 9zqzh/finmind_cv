"""Agent 工具定义：把教务适配层与知识库检索注册为 PydanticAI 工具。

约定：
- 工具内部不抛业务异常给模型循环，而是返回 {"error": ...} 结构，
  由模型组织可操作的错误提示（例如"请先登录"）。
- 每次成功调用都会把 (result_type, data) 记录到 deps，供编排层输出结构化卡片。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any

from pydantic import Field
from pydantic_ai import Agent, RunContext

from app.adapters import academic as academic_adapter
from app.adapters import amap as amap_adapter
from app.adapters import gduf_web as gduf_web_adapter
from app.adapters import jwxt as jwxt_adapter
from app.knowledge import KnowledgeService
from app.schemas.common import ApiError
from app.services.session import JwxtSession

# 工具名 -> 前端结果卡片类型
RESULT_TYPES: dict[str, str] = {
    "query_schedule": "schedule",
    "query_classroom_schedule": "classroom_schedule",
    "query_empty_classrooms": "empty_classrooms",
    "query_grades": "grades",
    "query_grade_detail": "grade_detail",
    "query_training_plan": "training_plan",
    "search_knowledge": "knowledge",
    "search_information": "information",
    "search_website": "website",
    "get_website_detail": "website_detail",
    "search_academic": "academic",
    "query_competitions": "competition",
    "query_competition_detail": "competition_detail",
    "query_competition_notices": "competition_notice",
    "query_competition_clubs": "competition_club",
    "search_map_places": "map_places",
    "query_map_route": "map_route",
}


@dataclass
class AgentDeps:
    """Agent 运行时依赖：由编排层在每次对话时构造。"""

    session: JwxtSession | None = None
    knowledge: KnowledgeService | None = None
    information: KnowledgeService | None = None
    # 运行过程记录
    tool_events: list[dict[str, Any]] = field(default_factory=list)
    last_result_type: str = "text"
    last_data: Any = None
    sources: list[str] = field(default_factory=list)
    # 本轮命中的操作手册标题（未命中为 None）
    playbook: str | None = None


def _record_success(ctx: RunContext[AgentDeps], tool: str, data: Any) -> None:
    result_type = RESULT_TYPES.get(tool, "text")
    ctx.deps.tool_events.append({"tool": tool, "result_type": result_type, "ok": True})
    ctx.deps.last_result_type = result_type
    ctx.deps.last_data = data


def _record_failure(ctx: RunContext[AgentDeps], tool: str, message: str) -> dict[str, Any]:
    ctx.deps.tool_events.append(
        {"tool": tool, "result_type": "text", "ok": False, "error": message}
    )
    return {"error": message}


def register_tools(agent: Agent) -> None:
    """把全部工具注册到 Agent 上。"""

    @agent.tool
    async def query_schedule(
        ctx: RunContext[AgentDeps],
        term: Annotated[
            str, Field(description="学期，格式 YYYY-YYYY-1 或 YYYY-YYYY-2，如 2025-2026-1")
        ],
        week: int | None = Field(
            default=None, description="教学周次（1-30），不传表示整学期课表"
        ),
    ) -> dict[str, Any]:
        """查询当前登录学生本人的课表。返回课程名、上课时间、教室、教师、周次。"""
        try:
            data = await jwxt_adapter.get_schedule(ctx.deps.session, term, week)
        except ApiError as exc:
            return _record_failure(ctx, "query_schedule", exc.message)
        _record_success(ctx, "query_schedule", data)
        return data

    @agent.tool
    async def query_classroom_schedule(
        ctx: RunContext[AgentDeps],
        term: Annotated[
            str, Field(description="学期，格式 YYYY-YYYY-1 或 YYYY-YYYY-2")
        ],
        campus: str = Field(default="", description="校区代码，可为空"),
        building: str = Field(default="", description="教学楼代码，可为空"),
        start_week: int | None = Field(default=None, description="起始周次"),
        end_week: int | None = Field(default=None, description="结束周次"),
    ) -> dict[str, Any]:
        """查询教室课表：某校区/教学楼内各教室的占用课程详情（数据量大）。仅用于查询具体教室的课程安排；若用户想找空闲教室，请改用 query_empty_classrooms，它只返回空闲教室名单，更简洁。"""
        try:
            data = await jwxt_adapter.get_classroom_schedule(
                ctx.deps.session,
                term,
                campus=campus,
                building=building,
                start_week=start_week,
                end_week=end_week,
            )
        except ApiError as exc:
            return _record_failure(ctx, "query_classroom_schedule", exc.message)
        _record_success(ctx, "query_classroom_schedule", data)
        return data

    @agent.tool
    async def query_empty_classrooms(
        ctx: RunContext[AgentDeps],
        term: Annotated[
            str, Field(description="学期，格式 YYYY-YYYY-1 或 YYYY-YYYY-2")
        ],
        weekday: int = Field(
            description="星期几，1-7（1 为星期一，7 为星期日）"
        ),
        start_period: int = Field(description="起始节次，如上午第一大节为 1"),
        end_period: int = Field(description="结束节次，如上午第二大节为 4"),
        campus: str = Field(default="", description="校区代码，可为空"),
        building: str = Field(default="", description="教学楼代码，可为空"),
        week: int | None = Field(default=None, description="周次，如第 3 周传 3；不传表示不限周次"),
    ) -> dict[str, Any]:
        """查询空闲教室：返回指定学期/校区/教学楼在指定星期、节次（可选周次）内没有课程占用的教室名单。只返回空闲教室名称列表与数量，不包含课程详情；用户想找空教室自习、讨论或活动时优先使用本工具。若查询条件缺少星期或节次，请先向用户确认。注意：本工具结果仅供你组织回复，前端不会展示原始数据，请用自然语言汇总空闲教室，不要输出 JSON。"""
        try:
            data = await jwxt_adapter.get_empty_classrooms(
                ctx.deps.session,
                term,
                campus=campus,
                building=building,
                weekday=weekday,
                week=week,
                start_period=start_period,
                end_period=end_period,
            )
        except ApiError as exc:
            return _record_failure(ctx, "query_empty_classrooms", exc.message)
        _record_success(ctx, "query_empty_classrooms", data)
        return data

    @agent.tool
    async def query_grades(
        ctx: RunContext[AgentDeps],
        term: str | None = Field(
            default=None,
            description="按学期过滤，格式 YYYY-YYYY-1；不传表示查询全部学期成绩",
        ),
    ) -> dict[str, Any]:
        """查询当前登录学生的成绩列表、学分与绩点统计。"""
        try:
            data = await jwxt_adapter.get_grades(ctx.deps.session, term)
        except ApiError as exc:
            return _record_failure(ctx, "query_grades", exc.message)
        _record_success(ctx, "query_grades", data)
        return data

    @agent.tool
    async def query_grade_detail(
        ctx: RunContext[AgentDeps],
        index: Annotated[
            int,
            Field(
                description="成绩列表中该科目的 index 编号（必须先调用 query_grades 获取）"
            ),
        ],
    ) -> dict[str, Any]:
        """查询单科成绩明细（平时/期中/期末占比与分数）。需要先查询过成绩列表。"""
        try:
            data = await jwxt_adapter.get_grade_detail(ctx.deps.session, index)
        except ApiError as exc:
            return _record_failure(ctx, "query_grade_detail", exc.message)
        _record_success(ctx, "query_grade_detail", data)
        return data

    @agent.tool
    async def query_training_plan(ctx: RunContext[AgentDeps]) -> dict[str, Any]:
        """查询当前登录学生所在专业的培养方案课程列表（课程、学分、属性）。"""
        try:
            data = await jwxt_adapter.get_training_plan(ctx.deps.session)
        except ApiError as exc:
            return _record_failure(ctx, "query_training_plan", exc.message)
        _record_success(ctx, "query_training_plan", data)
        return data

    @agent.tool
    async def search_knowledge(
        ctx: RunContext[AgentDeps],
        query: Annotated[
            str, Field(description="要在学院知识库中检索的问题或关键词")
        ],
    ) -> dict[str, Any]:
        """检索学院知识库：学生手册、培养方案说明、制度流程、社团工作室信息等。调用时机：用户消息以自然语言表达了查知识库的语义（如“查知识库”“知识库里有没有”），或问题与教务/学院信息相关但其他工具都无法解决时作为兜底手段；检索后用自己的话总结提炼回答，不要照搬原文。"""
        service = ctx.deps.knowledge
        if service is None:
            return _record_failure(ctx, "search_knowledge", "知识库尚未初始化")
        results = service.search(query, top_k=3)
        if not results:
            return _record_failure(
                ctx, "search_knowledge", "当前知识库没有找到相关依据"
            )
        ctx.deps.sources.extend(
            r.resource_path or f"{r.source}#{r.title}" for r in results
        )
        data = {
            "query": query,
            "results": [
                {
                    "text": r.text,
                    "source": r.source,
                    "title": r.title,
                    "score": r.score,
                    "resource_path": r.resource_path,
                }
                for r in results
            ],
        }
        _record_success(ctx, "search_knowledge", data)
        return data

    @agent.tool
    async def search_information(
        ctx: RunContext[AgentDeps],
        query: Annotated[
            str, Field(description="要检索的学院网站资讯或竞赛信息关键词")
        ],
    ) -> dict[str, Any]:
        """检索学院网站资讯与竞赛平台信息（当前为静态导入数据）。仅当用户消息以自然语言表达了查资讯的语义（如“查资讯”“有什么资讯”）时才调用；检索后用自己的话总结提炼回答，不要照搬原文。"""
        service = ctx.deps.information
        if service is None:
            return _record_failure(ctx, "search_information", "资讯库尚未初始化")
        results = service.search(query, top_k=3)
        if not results:
            return _record_failure(
                ctx, "search_information", "当前资讯库没有找到相关依据"
            )
        ctx.deps.sources.extend(f"{r.source}#{r.title}" for r in results)
        data = {
            "query": query,
            "results": [
                {"text": r.text, "source": r.source, "title": r.title} for r in results
            ],
        }
        _record_success(ctx, "search_information", data)
        return data

    @agent.tool
    async def search_website(
        ctx: RunContext[AgentDeps],
        keyword: Annotated[
            str, Field(description="要在学院官网检索的关键词，如新闻、通知、老师姓名、专业等")
        ],
        page: int = Field(default=1, description="结果页码，默认第 1 页"),
    ) -> dict[str, Any]:
        """关键词搜索学院官网的公开内容（学院新闻、通知公告、学生活动、师资队伍、专业介绍等，实时来自官网）。返回结果的标题与链接列表（个别条目可能带简短摘要）。调用时机：用户询问学院官网上的公开信息（如“学院最近有什么通知”“某位老师是谁”“学院有哪些专业”），且课表/成绩/培养方案/知识库等其他工具不适用时；用户只想知道有哪些内容时，直接用本工具结果汇总回答即可，不必再查详情；若用户需要了解某条结果的详细内容（如某位老师的研究方向、通知的具体安排），请用返回结果中的 url 调用 get_website_detail 获取正文。检索后用自己的话总结提炼回答，不要照搬原文。注意：本工具结果仅供你组织回复，前端不会展示原始数据，请用自然语言汇总，不要输出 JSON。"""
        try:
            data = await gduf_web_adapter.search_website(keyword, page=page)
        except ApiError as exc:
            return _record_failure(ctx, "search_website", exc.message)
        _record_success(ctx, "search_website", data)
        return data

    @agent.tool
    async def get_website_detail(
        ctx: RunContext[AgentDeps],
        url: Annotated[
            str,
            Field(
                description="要查看正文的官网页面链接：优先传 search_website 返回结果中的 url 字段，不要凭空猜测"
            ),
        ],
    ) -> dict[str, Any]:
        """获取学院官网某个页面的正文内容（新闻/通知全文、教师个人主页的简介与研究方向、专业详细介绍等，实时来自官网）。调用时机：search_website 返回结果后，用户需要了解某条结果的具体内容时（如“这个老师的研究方向是什么”“这篇通知具体怎么安排”“详细介绍下这个专业”），用对应结果的 url 调用本工具；用户只是浏览标题列表、不需要具体内容时不要调用。调用后用自己的话提炼正文要点回答，不要照搬原文。注意：本工具结果仅供你组织回复，前端不会展示原始数据，请用自然语言总结，不要输出 JSON。"""
        try:
            data = await gduf_web_adapter.get_website_detail(url)
        except ApiError as exc:
            return _record_failure(ctx, "get_website_detail", exc.message)
        _record_success(ctx, "get_website_detail", data)
        return data

    @agent.tool
    async def search_academic(
        ctx: RunContext[AgentDeps],
        query: Annotated[
            str,
            Field(
                description="要在学术平台检索的关键词，学术论文建议优先用英文关键词（如 deep learning）"
            ),
        ],
        sources: list[str] | None = Field(
            default=None,
            description="限定搜索平台，可选 arxiv、semantic_scholar；不传表示全部平台",
        ),
        max_results: int = Field(
            default=5, description="每个平台返回的最大条目数（1-10）"
        ),
    ) -> dict[str, Any]:
        """搜索学术资源平台（arXiv、Semantic Scholar）获取论文与文献资料，返回标题、作者、年份、摘要、论文页面链接与 PDF 下载入口。调用时机：用户需要查找学术论文、研究资料、文献综述、学术资源等（如“有没有关于深度学习的论文”“帮我找几篇强化学习的文献”）。调用后用自己的话总结推荐结果：逐篇说明论文主题与研究要点，并给出页面链接与 PDF 下载地址，不要输出原始 JSON。本工具结果仅供你组织回复，前端不展示结构化数据。"""
        try:
            data = await academic_adapter.search_academic_resources(
                query, sources=sources, max_results=min(max(max_results, 1), 10)
            )
        except ApiError as exc:
            return _record_failure(ctx, "search_academic", exc.message)
        _record_success(ctx, "search_academic", data)
        return data

    @agent.tool
    async def query_competitions(
        ctx: RunContext[AgentDeps],
        keyword: Annotated[
            str | None,
            Field(
                default=None,
                description="按比赛标题与简介模糊匹配的关键词（如“软件设计”“数学建模”），不限关键词时不传",
            ),
        ] = None,
        year: Annotated[
            int | None, Field(description="比赛年份（如 2026），不限年份时不传")
        ] = None,
        status: Annotated[
            str | None,
            Field(
                description=(
                    "比赛状态筛选：registration_open（报名中）、upcoming（即将开始）、"
                    "in_progress（进行中）、finished（已结束）、previous_recording（往期补录中）；"
                    "不限状态时不传"
                )
            ),
        ] = None,
        category: Annotated[
            str | None, Field(description="按平台分类精确匹配（如“软件设计类”“计算机类”），不限分类时不传")
        ] = None,
        department: Annotated[
            str | None, Field(description="按归属学院精确匹配（如“大数据与人工智能学院”），不限学院时不传")
        ] = None,
    ) -> dict[str, Any]:
        """查询学院竞赛平台的比赛列表（实时来自竞赛管理与问答平台），返回比赛名称、分类、年份、状态、报名起止时间、承办学院与链接。调用时机：用户询问竞赛/比赛相关信息（如“最近有什么竞赛可以参加”“有没有软件设计类的比赛”“现在哪些比赛在报名”）；用户说“现在能报名的比赛”时应传 status=registration_open。调用后用自己的话汇总推荐：逐场介绍比赛名称、报名状态与截止时间，并附上比赛页面链接，不要输出原始 JSON。本工具结果仅供你组织回复，前端不展示结构化数据。"""
        try:
            data = await gduf_web_adapter.get_competitions(
                year=year,
                status=status,
                category=category,
                department=department,
                keyword=keyword,
            )
        except ApiError as exc:
            return _record_failure(ctx, "query_competitions", exc.message)
        _record_success(ctx, "query_competitions", data)
        return data

    @agent.tool
    async def query_competition_detail(
        ctx: RunContext[AgentDeps],
        competition_id: Annotated[
            str,
            Field(
                description=(
                    "要查询详情的比赛标识：优先传 query_competitions 返回结果中的 id 字段，"
                    "也可传比赛页面 URL"
                )
            ),
        ],
    ) -> dict[str, Any]:
        """查询某一场比赛的详细信息（时间线、地点、赛道、报名要求、附件资料等，实时来自竞赛平台）。调用时机：用户在看过比赛列表后追问某一场具体比赛的详情（如“这个比赛怎么报名”“软件设计大赛的时间安排”）。必须先通过 query_competitions 拿到比赛列表后再用其中的 id 调用，不要凭空猜测 id。调用后用自己的话介绍详情要点并附链接，不要输出原始 JSON。本工具结果仅供你组织回复，前端不展示结构化数据。"""
        try:
            data = await gduf_web_adapter.get_competition_detail(competition_id)
        except ApiError as exc:
            return _record_failure(ctx, "query_competition_detail", exc.message)
        _record_success(ctx, "query_competition_detail", data)
        return data

    @agent.tool
    async def query_competition_notices(
        ctx: RunContext[AgentDeps],
        limit: int = Field(default=20, description="获取的通知条数（1-50），默认 20"),
    ) -> dict[str, Any]:
        """查询学院竞赛平台的最新通知公告（实时来自竞赛管理与问答平台），返回通知标题、发布时间与链接。调用时机：用户询问竞赛平台的公告动态（如“竞赛平台有什么新通知”“比赛平台最近发布了什么公告”）。调用后按时间由近到远用自然语言归纳通知要点并附链接，不要输出原始 JSON。本工具结果仅供你组织回复，前端不展示结构化数据。"""
        try:
            data = await gduf_web_adapter.get_competition_notices(
                limit=min(max(limit, 1), 50)
            )
        except ApiError as exc:
            return _record_failure(ctx, "query_competition_notices", exc.message)
        _record_success(ctx, "query_competition_notices", data)
        return data

    @agent.tool
    async def query_competition_clubs(
        ctx: RunContext[AgentDeps],
    ) -> dict[str, Any]:
        """查询学院竞赛平台的学生竞赛社团列表（实时来自竞赛管理与问答平台），返回社团名称、简介与链接。调用时机：用户询问竞赛社团/竞赛团队信息（如“学院有哪些竞赛社团”“想参加竞赛该加入什么社团”）。调用后逐个用自然语言介绍社团定位并附链接，不要输出原始 JSON。本工具结果仅供你组织回复，前端不展示结构化数据。"""
        try:
            data = await gduf_web_adapter.get_competition_clubs()
        except ApiError as exc:
            return _record_failure(ctx, "query_competition_clubs", exc.message)
        _record_success(ctx, "query_competition_clubs", data)
        return data

    @agent.tool
    async def search_map_places(
        ctx: RunContext[AgentDeps],
        keywords: Annotated[
            str,
            Field(description="要搜索的地点或美食类型关键词，如“烤肉”“游乐园”“奶茶店”"),
        ],
        location: str | None = Field(
            default=None,
            description="搜索中心位置（文字地名或“经度,纬度”），不传表示以广东金融学院清远校区为中心",
        ),
        radius: int = Field(
            default=5000, description="搜索半径（米），默认 5000"
        ),
        city: str = Field(default="清远", description="城市名，用于无坐标时的城市限定搜索"),
    ) -> dict[str, Any]:
        """搜索地图周边地点（美食、景点、娱乐等），返回地点名称、地址、电话、星级评分、人均消费、距校距离与导航链接。调用时机：用户询问学校周边有什么好吃的/好玩的、想找某类地方（如“学校附近有什么烤肉店”“清远哪里好玩”）。调用后基于返回结果推荐评分高、距离近的地点，用自己的话介绍并附上高德导航链接，不要输出原始 JSON。注意：高德接口只提供星级评分与人均消费、不提供顾客评论文本；本工具结果会以卡片展示，请如实引用数据。"""
        try:
            data = await amap_adapter.search_map_places(
                keywords, location=location, radius=radius, city=city
            )
        except ApiError as exc:
            return _record_failure(ctx, "search_map_places", exc.message)
        _record_success(ctx, "search_map_places", data)
        return data

    @agent.tool
    async def query_map_route(
        ctx: RunContext[AgentDeps],
        destination: Annotated[
            str,
            Field(description="目的地：优先传 search_map_places 返回结果中的 location 字段（“经度,纬度”精确坐标，避免长店名被地理编码到错误位置）；也可传地点名称（如“万达广场”），名称解析失败或超距时会自动回退搜索"),
        ],
        mode: str = Field(
            default="walking",
            description="出行方式：walking 步行 / driving 驾车 / bicycling 骑行 / transit 公交，默认 walking",
        ),
    ) -> dict[str, Any]:
        """规划从广东金融学院清远校区到目的地的出行路线，返回距离、预计耗时、路线步骤与高德导航链接。调用时机：用户询问去某地怎么走/多远/要多久（如“想去万达广场怎么走”“学校到清远站多远”），或看过 search_map_places 结果后要为某个地点规划路线。出行方式选择：3 公里内建议步行或骑行，更远建议公交或驾车。本工具结果会以卡片展示，请基于返回数据用自己的话说明。"""
        try:
            data = await amap_adapter.query_map_route(destination, mode=mode)
        except ApiError as exc:
            return _record_failure(ctx, "query_map_route", exc.message)
        _record_success(ctx, "query_map_route", data)
        return data


__all__ = ["RESULT_TYPES", "AgentDeps", "register_tools"]
