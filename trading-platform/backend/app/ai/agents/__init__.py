"""
Multi-Agent Analysis Architecture.

Coordinates specialized autonomous analytical agents:
- MarketAnalysisAgent: Market regime, session, and macroeconomic backdrop
- TechnicalAgent: Multi-indicator confluence and price action signals
- RiskAgent: Independent risk guardian with ULTIMATE VETO AUTHORITY over all trade proposals
- AgentCoordinator: Synthesizes multi-agent assessments while rigorously enforcing risk vetoes
"""

from app.ai.agents.base_agent import AnalysisAgent, AgentResult, AgentRecommendation
from app.ai.agents.market_analysis_agent import MarketAnalysisAgent, MarketRegime
from app.ai.agents.technical_agent import TechnicalAgent
from app.ai.agents.risk_agent import RiskAgent, RiskAssessment
from app.ai.agents.agent_coordinator import AgentCoordinator, ConsolidatedDecision

__all__ = [
    "AnalysisAgent",
    "AgentResult",
    "AgentRecommendation",
    "MarketAnalysisAgent",
    "MarketRegime",
    "TechnicalAgent",
    "RiskAgent",
    "RiskAssessment",
    "AgentCoordinator",
    "ConsolidatedDecision",
]
