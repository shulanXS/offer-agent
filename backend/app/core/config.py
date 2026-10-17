from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Cloud-injected environment variables override local development defaults.
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    app_name: str = "Offer Agent"
    app_env: str = "development"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    default_interview_quota: int = 5
    database_path: str = str(DATA_DIR / "offer_agent.db")
    log_file_path: str = str(BASE_DIR / "logs" / "offer_agent.log")
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    log_payload_max_chars: int = 1000
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    stream_chunk_size: int = 10
    stream_delay_ms: int = 25
    stream_interview_chunk_size: int = 2
    stream_interview_delay_ms: int = 36
    llm_timeout_seconds: int = 300
    llm_provider: str = ""
    llm_model: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    rag_enabled: bool = False
    rag_collection_name: str = "role_knowledge"
    rag_top_k: int = 4
    rag_embedding_provider: str = "local"
    rag_embedding_model: str = "hash-embedding-v1"
    rag_embedding_dimension: int = 256
    rag_knowledge_dir: str = str(BASE_DIR / "knowledge")
    milvus_lite_db_path: str = str(DATA_DIR / "milvus_lite.db")
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    volcengine_api_key: str = ""
    volcengine_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    interview_context_max_messages: int = 12
    interview_context_max_chars: int = 4000
    interview_topic_summary_llm_min_chars: int = 200
    interview_stale_reply_lock_seconds: int = 300
    max_upload_bytes: int = 5 * 1024 * 1024

    # v2.2 充值档位配置
    package_single_price_cents: int = 2000   # 20元
    package_single_interviews: int = 5
    package_sub_price_cents: int = 20000      # 200元
    package_sub_duration_days: int = 30
    # 新用户默认免费面试次数（一次性）
    new_user_free_quota: int = 1

    # v2.5 真实支付通道（当前仅支持 Stripe；未配置密钥时直接 503）
    # payment_provider: stripe（默认；不可改为其它值）
    payment_provider: str = "stripe"
    # 前端基础 URL（用于 Stripe Checkout 的 success/cancel 回调）
    frontend_base_url: str = "http://localhost:5173"
    # Stripe —— 必填项：STRIPE_SECRET_KEY（无则支付入口直接报错）
    # 可选项：STRIPE_PUBLISHABLE_KEY（用于前端 Stripe.js）、STRIPE_WEBHOOK_SECRET
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "cny"

    @property
    def database_file(self) -> Path:
        raw = Path(self.database_path)
        return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()

    @property
    def log_file(self) -> Path:
        raw = Path(self.log_file_path)
        return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()

    @property
    def rag_knowledge_path(self) -> Path:
        raw = Path(self.rag_knowledge_dir)
        return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()

    @property
    def milvus_lite_db_file(self) -> Path:
        raw = Path(self.milvus_lite_db_path)
        return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()

    @property
    def cors_origins(self) -> list[str]:
        value = self.cors_origins_raw.strip()
        if not value:
            return ["http://localhost:5173"]
        return [item.strip() for item in value.split(",") if item.strip()]


settings = Settings()
settings.database_file.parent.mkdir(parents=True, exist_ok=True)
settings.log_file.parent.mkdir(parents=True, exist_ok=True)
settings.rag_knowledge_path.mkdir(parents=True, exist_ok=True)
settings.milvus_lite_db_file.parent.mkdir(parents=True, exist_ok=True)
