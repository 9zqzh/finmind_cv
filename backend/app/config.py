"""应用配置：所有外部密钥与可调参数统一走环境变量 / .env 文件。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理环境变量配置，禁止在代码中硬编码密钥。"""

    model_config = SettingsConfigDict(
        # 根目录 .env 是统一配置；backend/.env 仅作为旧版兼容来源。
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek（OpenAI 兼容接口）
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    deepseek_extra_body: dict[str, Any] = Field(
        default_factory=dict,
        alias="DEEPSEEK_EXTRA_BODY",
        description="合并到模型请求体的 OpenAI 兼容服务商自定义参数",
    )

    # Knowledge retrieval
    knowledge_retrieval_mode: str = Field(
        default="auto", alias="KNOWLEDGE_RETRIEVAL_MODE"
    )
    chroma_dir: str = Field(default="data/chroma", alias="CHROMA_DIR")
    chroma_host: str = Field(default="", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")
    knowledge_vector_min_score: float = Field(
        default=0.75, alias="KNOWLEDGE_VECTOR_MIN_SCORE"
    )
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_api_key_file: str = Field(default="", alias="EMBEDDING_API_KEY_FILE")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_timeout_seconds: float = Field(
        default=30.0, alias="EMBEDDING_TIMEOUT_SECONDS"
    )
    embedding_batch_size: int = Field(default=10, alias="EMBEDDING_BATCH_SIZE")

    # Agent 运行参数
    agent_max_iterations: int = Field(default=4, alias="AGENT_MAX_ITERATIONS")
    agent_timeout_seconds: float = Field(default=30.0, alias="AGENT_TIMEOUT_SECONDS")

    # 教务系统
    jwxt_base_url: str = Field(
        default="https://jwxt.gduf.edu.cn", alias="JWXT_BASE_URL"
    )

    # 学术资源平台（arXiv/Semantic Scholar 等境外平台可能需要代理）
    # 例如：ACADEMIC_PROXY=http://127.0.0.1:7890；留空表示直连
    academic_proxy: str = Field(default="", alias="ACADEMIC_PROXY")

    # Web 服务
    app_env: str = Field(default="development", alias="APP_ENV")
    session_ttl_minutes: int = Field(default=120, alias="SESSION_TTL_MINUTES")
    login_session_ttl_days: int = Field(default=7, alias="LOGIN_SESSION_TTL_DAYS")

    # PostgreSQL / sensitive session data
    database_url: str = Field(default="", alias="DATABASE_URL")
    session_encryption_keys: str = Field(default="", alias="SESSION_ENCRYPTION_KEYS")

    # 数据目录（相对 backend 目录）
    knowledge_dir: str = Field(default="data/knowledge", alias="KNOWLEDGE_DIR")
    information_dir: str = Field(default="data/information", alias="INFORMATION_DIR")
    # 操作手册（关键词触发的固定最优路径）条目目录
    playbook_dir: str = Field(default="data/playbooks", alias="PLAYBOOK_DIR")
    # 原始资料文件目录（相对 backend 目录，默认为项目根下的 resources）
    resources_dir: str = Field(default="../resources", alias="RESOURCES_DIR")

    @property
    def model_configured(self) -> bool:
        """是否已配置可用的模型密钥。"""
        return bool(self.deepseek_api_key.strip())

    @property
    def embedding_configured(self) -> bool:
        """Whether all values needed by the embedding API are present."""
        return all(
            value.strip()
            for value in (
                self.embedding_base_url,
                self.embedding_api_key_value,
                self.embedding_model,
            )
        )

    @property
    def encryption_keys(self) -> list[str]:
        """Fernet keys, newest first, for encryption and key rotation."""
        return [key.strip() for key in self.session_encryption_keys.split(",") if key.strip()]

    @property
    def embedding_api_key_value(self) -> str:
        """Return the direct key, or the first key-like line in a local key file."""
        if self.embedding_api_key.strip():
            return self.embedding_api_key.strip()
        if not self.embedding_api_key_file.strip():
            return ""
        try:
            lines = Path(self.embedding_api_key_file).read_text(
                encoding="utf-8-sig"
            ).splitlines()
        except (OSError, UnicodeError):
            return ""
        for line in lines:
            value = line.strip()
            if (
                len(value) >= 20
                and " " not in value
                and ":" not in value
                and "：" not in value
                and not value.lower().startswith(("http://", "https://"))
            ):
                return value
        return ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
