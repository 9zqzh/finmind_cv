"""应用配置：所有外部密钥与可调参数统一走环境变量 / .env 文件。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理环境变量配置，禁止在代码中硬编码密钥。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # DeepSeek（OpenAI 兼容接口）
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")

    # Knowledge retrieval
    knowledge_retrieval_mode: str = Field(
        default="auto", alias="KNOWLEDGE_RETRIEVAL_MODE"
    )
    chroma_dir: str = Field(default="data/chroma", alias="CHROMA_DIR")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_timeout_seconds: float = Field(
        default=30.0, alias="EMBEDDING_TIMEOUT_SECONDS"
    )

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

    # 数据目录（相对 backend 目录）
    knowledge_dir: str = Field(default="data/knowledge", alias="KNOWLEDGE_DIR")
    information_dir: str = Field(default="data/information", alias="INFORMATION_DIR")
    # 原始资料文件目录（相对 backend 目录，默认为项目根下的 resources）
    resources_dir: str = Field(default="../../resources", alias="RESOURCES_DIR")

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
                self.embedding_api_key,
                self.embedding_model,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
