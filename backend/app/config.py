from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    anthropic_api_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    admin_email: str
    admin_password: str
    viewer_email: str
    viewer_password: str

    database_url: str = "sqlite:///./backend/data/app.db"
    allowed_origin: str = "http://localhost:3000"
    env: str = "development"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
