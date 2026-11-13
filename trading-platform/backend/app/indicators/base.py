"""
Base classes and data structures for technical indicators.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import pandas as pd


@dataclass
class IndicatorResult:
    """Represents a computed indicator snapshot or latest values."""
    name: str
    values: Dict[str, float] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseIndicator(ABC):
    """Abstract Base Class for all technical indicators."""

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates indicator values and appends them as new columns to the DataFrame.

        Args:
            df: DataFrame containing market data with standard OHLCV columns:
                ['open', 'high', 'low', 'close', 'tick_volume' / 'volume']

        Returns:
            DataFrame with indicator columns appended.
        """
        pass

    def get_latest(self, df: pd.DataFrame) -> IndicatorResult:
        """
        Helper method to extract the latest values of the indicator from a computed DataFrame.

        Args:
            df: DataFrame after calculate() has been executed.

        Returns:
            IndicatorResult with current latest float values.
        """
        if df.empty:
            return IndicatorResult(name=self.name, values={})

        latest_row = df.iloc[-1]
        timestamp = df.index[-1] if isinstance(df.index[-1], datetime) else None
        if "time" in df.columns:
            timestamp = latest_row["time"]

        extracted_values: Dict[str, float] = {}
        for col in df.columns:
            if col.startswith(self.name) or col in self.params.get("output_columns", []):
                val = latest_row[col]
                if pd.notna(val):
                    extracted_values[col] = float(val)

        return IndicatorResult(
            name=self.name,
            values=extracted_values,
            timestamp=timestamp,
            metadata=self.params,
        )
