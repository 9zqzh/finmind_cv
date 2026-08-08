"""Build knowledge services from application settings."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.knowledge.embeddings import OpenAICompatibleEmbeddingProvider
from app.knowledge.service import KnowledgeService


def build_knowledge_service(
    directory: Path,
    settings: Settings,
    *,
    collection_name: str = "knowledge",
) -> KnowledgeService:
    """Create the knowledge service and enable vectors only when fully configured."""
    provider = None
    vector_store = None
    if settings.knowledge_retrieval_mode != "keyword" and settings.embedding_configured:
        try:
            from app.knowledge.chroma_store import ChromaVectorStore

            chroma_dir = Path(settings.chroma_dir)
            if not chroma_dir.is_absolute():
                chroma_dir = Path(__file__).resolve().parents[2] / chroma_dir

            provider = OpenAICompatibleEmbeddingProvider(
                base_url=settings.embedding_base_url,
                api_key=settings.embedding_api_key,
                model=settings.embedding_model,
                timeout_seconds=settings.embedding_timeout_seconds,
            )
            vector_store = ChromaVectorStore(chroma_dir, collection_name)
        except Exception:
            provider = None
            vector_store = None
    return KnowledgeService.from_directory(
        directory,
        vector_store=vector_store,
        embedding_provider=provider,
    )
