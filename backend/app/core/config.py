"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central configuration for the student assistant backend."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "College AI Student Assistant"
    debug: bool = True

    database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'student_assistant.db'}"

    jwt_secret: str = "change-me-to-a-secure-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # OTP / Email service settings
    otp_expiry_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    email_service_url: str = "http://localhost:3001"
    email_service_timeout: int = 10
    email_dev_mode: bool = False
    email_provider_mode: str = "smtp"  # or 'mock' for tests

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""

    embedding_model: str = "all-MiniLM-L6-v2"
    use_fake_embeddings: bool = False
    vector_store_directory: str = str(BACKEND_ROOT / "data" / "vector_store")
    top_k: int = 5
    similarity_threshold: float = 0.35

    intent_model_path: str = str(BACKEND_ROOT / "data" / "models" / "intent_classifier.joblib")
    intent_metrics_path: str = str(BACKEND_ROOT / "data" / "models" / "intent_metrics.json")
    intents_dataset_path: str = str(BACKEND_ROOT / "training" / "intents.csv")

    upload_directory: str = str(BACKEND_ROOT / "data" / "documents")
    processed_directory: str = str(BACKEND_ROOT / "data" / "processed")
    chunk_size: int = 500
    chunk_overlap: int = 75
    max_upload_size_mb: int = 15
    allowed_document_types: str = "pdf,txt,docx,csv"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def allowed_extensions(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_document_types.split(",") if ext.strip()}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
