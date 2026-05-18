from __future__ import annotations

import os
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGO: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24 * 14

    DATABASE_URL: str = "sqlite:///./data.db"

    CORS_ORIGINS: str = "http://localhost:3000"

    SITE_URL: str = "http://localhost:3000"

    # Billing
    SIGNUP_BONUS_CENTS: int = 10000  # ¥100，刚好够 1 集试看片

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # AI pipeline (empty → worker uses mock)
    VOLC_ACCESS_KEY: str = ""
    VOLC_SECRET_KEY: str = ""
    VOLC_ARK_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    FAL_API_KEY: str = ""

    # Storage
    S3_ENDPOINT: str = ""
    S3_REGION: str = "auto"
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_BASE_URL: str = ""

    # Runtime
    LOG_LEVEL: str = "INFO"
    WORKER_POLL_INTERVAL: float = 2.0
    STORAGE_DIR: str = "./storage"
    PORT: int = 8000

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def use_mock_worker(self) -> bool:
        return not (self.VOLC_ACCESS_KEY and self.ANTHROPIC_API_KEY)

    @property
    def use_mock_billing(self) -> bool:
        return not self.STRIPE_SECRET_KEY


settings = Settings()
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
