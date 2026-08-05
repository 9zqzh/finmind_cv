"""知识库与资讯检索路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_information, get_knowledge
from app.knowledge import KnowledgeService
from app.schemas.common import KNOWLEDGE_NOT_FOUND, ApiError, ok

router = APIRouter(prefix="/api", tags=["knowledge"])


def _search_payload(service: KnowledgeService, query: str, top_k: int) -> dict:
    results = service.search(query, top_k=top_k)
    if not results:
        raise ApiError(
            KNOWLEDGE_NOT_FOUND,
            "当前知识库没有找到相关依据，请换一种问法或咨询教学秘书",
            status_code=404,
        )
    return {
        "query": query,
        "results": [
            {"text": r.text, "source": r.source, "title": r.title, "score": r.score}
            for r in results
        ],
        "sources": sorted({f"{r.source}#{r.title}" for r in results}),
    }


@router.get("/knowledge/search")
async def knowledge_search(
    q: str = Query(..., min_length=1, description="检索问题或关键词"),
    top_k: int = Query(default=3, ge=1, le=10),
    service: KnowledgeService = Depends(get_knowledge),
):
    """检索学院知识库（制度、培养方案说明、基本信息等）。"""
    return ok(_search_payload(service, q, top_k))


@router.get("/information/search")
async def information_search(
    q: str = Query(..., min_length=1, description="检索问题或关键词"),
    top_k: int = Query(default=3, ge=1, le=10),
    service: KnowledgeService = Depends(get_information),
):
    """检索学院网站资讯与竞赛信息（当前为静态导入数据）。"""
    return ok(_search_payload(service, q, top_k))
