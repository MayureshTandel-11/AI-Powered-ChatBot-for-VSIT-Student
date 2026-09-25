"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _resolve_backend_relative_path(value: str) -> str:
    """Resolve ./relative paths against the backend root regardless of process CWD."""
    if value.startswith("./"):
        return str((BACKEND_ROOT / value[2:]).resolve())
    path = Path(value)
    if not path.is_absolute():
        return str((BACKEND_ROOT / value).resolve())
    return value


def _resolve_sqlite_url(value: str) -> str:
    if value.startswith("sqlite:///./"):
        rel_path = value.removeprefix("sqlite:///./")
        return f"sqlite:///{(BACKEND_ROOT / rel_path).resolve()}"
    if value.startswith("sqlite:///") and not value.startswith("sqlite:////"):
        raw_path = value.removeprefix("sqlite:///")
        path = Path(raw_path)
        if not path.is_absolute():
            return f"sqlite:///{(BACKEND_ROOT / raw_path).resolve()}"
    return value


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

    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""

    embedding_model: str = "all-MiniLM-L6-v2"
    use_fake_embeddings: bool = False
    vector_store_directory: str = str(BACKEND_ROOT / "data" / "vector_store")
    top_k: int = 5
    broad_query_top_k: int = 8
    similarity_threshold: float = 0.35
    intent_confidence_threshold: float = 0.45
    intent_category_boost: float = 0.05
    hybrid_keyword_weight: float = 0.15
    chat_history_window: int = 5
    rag_debug: bool = False

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

    @field_validator(
        "llm_provider",
        "llm_model",
        "llm_base_url",
        "embedding_model",
        mode="before",
    )
    @classmethod
    def strip_whitespace(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _resolve_sqlite_url(value)
        return value

    @field_validator(
        "vector_store_directory",
        "intent_model_path",
        "intent_metrics_path",
        "intents_dataset_path",
        "upload_directory",
        "processed_directory",
        mode="before",
    )
    @classmethod
    def normalize_relative_paths(cls, value: object) -> object:
        if isinstance(value, str):
            return _resolve_backend_relative_path(value)
        return value

    @model_validator(mode="after")
    def validate_llm_provider(self) -> "Settings":
        if self.llm_api_key and self.llm_api_key.startswith("gsk_") and self.llm_provider.lower() == "openai":
            object.__setattr__(self, "llm_provider", "groq")
        return self

    @property
    def llm_chat_completions_url(self) -> str:
        provider = self.llm_provider.lower()
        if provider == "groq":
            base_url = self.llm_base_url or "https://api.groq.com/openai/v1"
        elif provider == "openai":
            base_url = self.llm_base_url or "https://api.openai.com/v1"
        else:
            base_url = self.llm_base_url
        if not base_url:
            raise ValueError(f"LLM_BASE_URL is required for provider '{self.llm_provider}'")
        return f"{base_url.rstrip('/')}/chat/completions"

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
