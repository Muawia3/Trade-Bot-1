"""
Base classes and schemas for Multi-Agent Trading Analysis.

Defines the contract for specialized agents contributing independent analytical
assessments of market state, indicators, and risk exposure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd


class AgentRecommendation(str, Enum):
    """Actionable recommendations emitted by analytical agents."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STAND_ASIDE = "STAND_ASIDE"
    VETO = "VETO"


@dataclass
class AgentResult:
    """
    Standardized payload delivered by an AnalysisAgent.

    Contains findings, qualitative rationale, statistical confidence, and optional veto flags.
    """
    agent_name: str
    recommendation: AgentRecommendation
    confidence: float  # 0.0 to 1.0
    findings: Dict[str, Any] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)
    veto: bool = False
    veto_reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        res = asdict(self)
        res["recommendation"] = self.recommendation.value
        return res


class AnalysisAgent(ABC):
    """
    Abstract Base Class for analysis agents.

    Each agent inspects market data and system context to yield an independent AgentResult.
    """

    def __init__(self, name: str, description: str = "") -> None:
        """
        Initialize the analysis agent.

        Args:
            name: Agent identifier.
            description: Concise explanation of the agent's analytical focus.
        """
        self.name = name
        self.description = description

    @abstractmethod
    def analyze(
        self,
        market_data: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Perform domain-specific analysis on market data and execution context.

        Args:
            market_data: OHLCV DataFrame for the instrument under review.
            context: Environment dictionary containing account state, open positions,
                     upcoming news, or current pending trade signals.

        Returns:
            AgentResult detailing recommendation, confidence, and granular findings.
        """
        pass
