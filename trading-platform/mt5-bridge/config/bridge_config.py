"""
Configuration settings for the MT5 Bridge microservice.
Supports loading from environment variables and .env file.
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


class BridgeConfig(BaseSettings):
    """MetaTrader 5 Bridge configuration settings."""

    # Server settings
    BRIDGE_HOST: str = "0.0.0.0"
    BRIDGE_PORT: int = 8001
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # MetaTrader 5 terminal settings
    MT5_PATH: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    MT5_LOGIN: Optional[int] = None
    MT5_PASSWORD: Optional[str] = None
    MT5_SERVER: Optional[str] = None
    MT5_TIMEOUT: int = 60000  # Timeout in milliseconds
    MT5_PORTABLE: bool = False

    # Operational settings
    MOCK_MODE: bool = False  # Force mock mode if True or if MT5 package unavailable
    TRADING_MODE: TradingMode = TradingMode.PAPER
    LIVE_TRADING_ENABLED: bool = False  # Master safety switch for real orders

    # Reconnection & Backoff settings
    MAX_RECONNECT_ATTEMPTS: int = 5
    INITIAL_BACKOFF_SECONDS: float = 1.0
    MAX_BACKOFF_SECONDS: float = 30.0
    BACKOFF_MULTIPLIER: float = 2.0

    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000"]

    # Target instruments
    DEFAULT_SYMBOLS: List[str] = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]

    @property
    def is_paper_mode(self) -> bool:
        """Return True if trading in paper/simulated mode."""
        return self.TRADING_MODE == TradingMode.PAPER or not self.LIVE_TRADING_ENABLED

    @property
    def is_live_mode(self) -> bool:
        """Return True if live trading is explicitly active and enabled."""
        return self.TRADING_MODE == TradingMode.LIVE and self.LIVE_TRADING_ENABLED

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
def get_bridge_config() -> BridgeConfig:
    """Return cached instance of BridgeConfig."""
    return BridgeConfig()
