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
    # 单集渲染的实际 API 成本（火山/Claude/Gemini 等加权平均，6500=¥65）
    # 接入真实流水线时改为实际消耗
    EPISODE_BASE_COST_CENTS: int = 6500
    # 加价率：付费用户按 base_cost * PROFIT_MULTIPLIER 扣钱（10% 毛利）
    PROFIT_MULTIPLIER: float = 1.10
    # 免费用户每日视频数上限
    FREE_DAILY_QUOTA: int = 3

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
    # 并发 worker 数。Postgres 用 SELECT...FOR UPDATE SKIP LOCKED 互斥；
    # SQLite 单进程兜底，多 worker 也安全（只是退化为顺序）
    WORKER_CONCURRENCY: int = 3
    # 质量门槛：渲染后分数 < QUALITY_PASS 自动重试，最多 QUALITY_MAX_RETRIES 次
    QUALITY_PASS: int = 90
    QUALITY_MAX_RETRIES: int = 2

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
