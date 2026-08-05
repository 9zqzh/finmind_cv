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

    # Agent 运行参数
    agent_max_iterations: int = Field(default=4, alias="AGENT_MAX_ITERATIONS")
    agent_timeout_seconds: float = Field(default=30.0, alias="AGENT_TIMEOUT_SECONDS")

    # 教务系统
    jwxt_base_url: str = Field(
        default="https://jwxt.gduf.edu.cn", alias="JWXT_BASE_URL"
    )

    # Web 服务
    app_env: str = Field(default="development", alias="APP_ENV")
    session_ttl_minutes: int = Field(default=120, alias="SESSION_TTL_MINUTES")

    # 数据目录（相对 backend 目录）
    knowledge_dir: str = Field(default="data/knowledge", alias="KNOWLEDGE_DIR")
    information_dir: str = Field(default="data/information", alias="INFORMATION_DIR")

    @property
    def model_configured(self) -> bool:
        """是否已配置可用的模型密钥。"""
        return bool(self.deepseek_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
