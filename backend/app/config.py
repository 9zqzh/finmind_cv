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
    # 向量分数阈值：仅过滤语义明显无关项（text-embedding-v4 相似度分布偏低，
    # 阈值过高会导致相关结果被误过滤），最终排序由混合检索融合分数决定
    knowledge_vector_min_score: float = Field(
        default=0.5, alias="KNOWLEDGE_VECTOR_MIN_SCORE"
    )
    # 关键词零命中时向量结果的置信门槛：embedding 对完全无关文本也会给出
    # 0.6-0.75 的“擦边”分数，低于该值时视为未检索到（避免无关查询返回最接近片段）
    knowledge_vector_confidence_min: float = Field(
        default=0.75, alias="KNOWLEDGE_VECTOR_CONFIDENCE_MIN"
    )
    # 混合检索时向量与关键词各自召回的最大候选数，融合后取 top_k
    knowledge_vector_top_k: int = Field(
        default=20, alias="KNOWLEDGE_VECTOR_TOP_K"
    )
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_api_key_file: str = Field(default="", alias="EMBEDDING_API_KEY_FILE")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_timeout_seconds: float = Field(
        default=30.0, alias="EMBEDDING_TIMEOUT_SECONDS"
    )
    embedding_batch_size: int = Field(default=10, alias="EMBEDDING_BATCH_SIZE")
    # 嵌入请求失败时的重试次数（指数退避），网络抖动不影响检索稳定性
    embedding_retries: int = Field(default=2, alias="EMBEDDING_RETRIES")

    # Agent 运行参数
    agent_max_iterations: int = Field(default=4, alias="AGENT_MAX_ITERATIONS")
    agent_timeout_seconds: float = Field(default=30.0, alias="AGENT_TIMEOUT_SECONDS")

    # 教务系统
    jwxt_base_url: str = Field(
        default="https://jwxt.gduf.edu.cn", alias="JWXT_BASE_URL"
    )

    # Findpapers 学术资源聚合搜索
    # 逗号分隔的启用源；OpenAlex/IEEE/Scopus/WoS 启用时必须同时配置对应 Key。
    findpapers_databases: str = Field(
        default="arxiv,pubmed,semantic_scholar", alias="FINDPAPERS_DATABASES"
    )
    # 单个 HTTP 请求超时、整次聚合搜索超时，以及普通/429 响应重试次数。
    findpapers_request_timeout_seconds: float = Field(
        default=10.0, gt=0, alias="FINDPAPERS_REQUEST_TIMEOUT_SECONDS"
    )
    findpapers_search_timeout_seconds: float = Field(
        default=30.0, gt=0, alias="FINDPAPERS_SEARCH_TIMEOUT_SECONDS"
    )
    findpapers_max_retries: int = Field(
        default=1, ge=0, alias="FINDPAPERS_MAX_RETRIES"
    )
    findpapers_rate_limit_retries: int = Field(
        default=0, ge=0, alias="FINDPAPERS_RATE_LIMIT_RETRIES"
    )
    findpapers_ieee_api_token: str = Field(
        default="", alias="FINDPAPERS_IEEE_API_TOKEN"
    )
    findpapers_scopus_api_token: str = Field(
        default="", alias="FINDPAPERS_SCOPUS_API_TOKEN"
    )
    findpapers_pubmed_api_token: str = Field(
        default="", alias="FINDPAPERS_PUBMED_API_TOKEN"
    )
    findpapers_openalex_api_token: str = Field(
        default="", alias="FINDPAPERS_OPENALEX_API_TOKEN"
    )
    findpapers_semantic_scholar_api_token: str = Field(
        default="", alias="FINDPAPERS_SEMANTIC_SCHOLAR_API_TOKEN"
    )
    findpapers_wos_api_token: str = Field(
        default="", alias="FINDPAPERS_WOS_API_TOKEN"
    )
    findpapers_email: str = Field(default="", alias="FINDPAPERS_EMAIL")
    findpapers_proxy: str = Field(default="", alias="FINDPAPERS_PROXY")
    findpapers_ssl_verify: bool = Field(default=True, alias="FINDPAPERS_SSL_VERIFY")

    # Web 服务
    app_env: str = Field(default="development", alias="APP_ENV")
    session_ttl_minutes: int = Field(default=120, alias="SESSION_TTL_MINUTES")
    login_session_ttl_days: int = Field(default=7, alias="LOGIN_SESSION_TTL_DAYS")

    # 地图服务（高德 Web 服务 API；百度地图为可选的口碑补充源）
    amap_api_key: str = Field(default="", alias="AMAP_API_KEY")
    # 路线规划默认起点，留空使用“广东金融学院清远校区”
    amap_default_origin: str = Field(
        default="广东金融学院清远校区", alias="AMAP_DEFAULT_ORIGIN"
    )
    # 默认起点经纬度兑底（“经度,纬度”）；留空表示用地理编码接口解析
    amap_default_location: str = Field(default="", alias="AMAP_DEFAULT_LOCATION")
    # 周边搜索默认半径（米）
    amap_search_radius: int = Field(default=5000, alias="AMAP_SEARCH_RADIUS")
    # 可选：百度地图开放平台 key，用于补充点评数/评分（未配置则仅用高德数据）
    baidu_map_api_key: str = Field(default="", alias="BAIDU_MAP_API_KEY")

    # PostgreSQL / sensitive session data
    database_url: str = Field(default="", alias="DATABASE_URL")
    session_encryption_keys: str = Field(default="", alias="SESSION_ENCRYPTION_KEYS")

    # 数据目录（相对 backend 目录）
    knowledge_dir: str = Field(default="data/knowledge", alias="KNOWLEDGE_DIR")
    information_dir: str = Field(default="data/information", alias="INFORMATION_DIR")
    # 操作手册（关键词触发的固定最优路径）条目目录
    playbook_dir: str = Field(default="data/playbooks", alias="PLAYBOOK_DIR")
    # 操作手册自进化：自动生成的草稿目录与高频判定参数
    playbook_draft_dir: str = Field(
        default="data/playbook_drafts", alias="PLAYBOOK_DRAFT_DIR"
    )
    evolution_min_count: int = Field(default=8, alias="EVOLUTION_MIN_COUNT")
    evolution_window_days: int = Field(default=7, alias="EVOLUTION_WINDOW_DAYS")
    evolution_top_n: int = Field(default=3, alias="EVOLUTION_TOP_N")
    evolution_cooldown_days: int = Field(default=14, alias="EVOLUTION_COOLDOWN_DAYS")
    evolution_sample_size: int = Field(default=6, alias="EVOLUTION_SAMPLE_SIZE")
    # 定时自进化：开关、执行间隔天数与本地时间小时（草稿仍需人工审核）
    evolution_schedule_enabled: bool = Field(
        default=True, alias="EVOLUTION_SCHEDULE_ENABLED"
    )
    evolution_interval_days: int = Field(default=7, alias="EVOLUTION_INTERVAL_DAYS")
    evolution_run_hour: int = Field(default=3, alias="EVOLUTION_RUN_HOUR")
    # 管理后台的配置驱动超级管理员；留空时管理后台整体禁用。
    initial_admin_student_number: str = Field(
        default="", alias="INITIAL_ADMIN_STUDENT_NUMBER"
    )
    # 评委演示模式：开启后，未携带会话令牌的请求自动复用数据库中的共享教务会话
    # （由管理员在管理台预登录共享账号后写入），评委无需登录即可体验真实个人数据。
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
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
