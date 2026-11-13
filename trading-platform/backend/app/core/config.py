"""
Core configuration module using Pydantic BaseSettings.
Loads settings from environment variables and .env file.
Compatible with both Pydantic v1 and v2.
"""

from enum import Enum
from functools import lru_cache
from typing import List, Optional
import json

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import field_validator
    HAS_PYDANTIC_V2 = True
except ImportError:
    from pydantic import BaseSettings, validator
    SettingsConfigDict = None
    HAS_PYDANTIC_V2 = False


class TradingMode(str, Enum):
    """Trading execution mode."""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # ---- Database ----
    DATABASE_URL: str = "postgresql+asyncpg://trading_user:trading_pass@localhost:5432/trading_platform"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://trading_user:trading_pass@localhost:5432/trading_platform"

    # ---- API ----
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = "your-secret-key-change-in-production"
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    DEBUG: bool = True

    # ---- MetaTrader 5 ----
    MT5_PATH: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    MT5_LOGIN: Optional[int] = None
    MT5_PASSWORD: Optional[str] = None
    MT5_SERVER: Optional[str] = None
    MT5_TIMEOUT: int = 60000

    # ---- Trading ----
    TRADING_MODE: TradingMode = TradingMode.PAPER
    DEFAULT_RISK_PERCENT: float = 1.0
    MAX_DAILY_LOSS_PERCENT: float = 5.0
    MAX_OPEN_POSITIONS: int = 5
    MAX_DRAWDOWN_PERCENT: float = 10.0
    LIVE_TRADING_ENABLED: bool = False

    # ---- Paper Trading ----
    PAPER_TRADING_INITIAL_BALANCE: float = 10000.0
    PAPER_TRADING_CURRENCY: str = "USD"

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/trading_platform.log"

    # ---- AI/ML ----
    AI_ENABLED: bool = False
    PYTORCH_ENABLED: bool = False

    # ---- News (optional) ----
    NEWS_API_KEY: Optional[str] = None
    NEWS_API_PROVIDER: Optional[str] = None

    # ---- Redis (optional) ----
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"

    # ---- Computed Properties ----
    @property
    def async_database_url(self) -> str:
        """Return the async database URL (asyncpg driver)."""
        return self.DATABASE_URL

    @property
    def sync_database_url(self) -> str:
        """Return the sync database URL (psycopg2 driver)."""
        return self.DATABASE_URL_SYNC

    @property
    def is_paper_trading(self) -> bool:
        return self.TRADING_MODE == TradingMode.PAPER

    @property
    def is_live_trading(self) -> bool:
        return self.TRADING_MODE == TradingMode.LIVE and self.LIVE_TRADING_ENABLED

    @property
    def is_backtesting(self) -> bool:
        return self.TRADING_MODE == TradingMode.BACKTEST

    @property
    def mt5_configured(self) -> bool:
        """Check if MT5 credentials are configured."""
        return all([self.MT5_LOGIN, self.MT5_PASSWORD, self.MT5_SERVER])

    if HAS_PYDANTIC_V2 and SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

        @field_validator("CORS_ORIGINS", mode="before")
        @classmethod
        def parse_cors_origins(cls, v):
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return [i.strip() for i in v.split(",") if i.strip()]
            return v
    else:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False
            extra = "ignore"

        @validator("CORS_ORIGINS", pre=True, always=True)
        def parse_cors_origins_v1(cls, v):
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return [i.strip() for i in v.split(",") if i.strip()]
            return v


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
