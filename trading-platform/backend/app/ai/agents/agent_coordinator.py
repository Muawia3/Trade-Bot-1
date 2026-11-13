"""
Multi-Agent Coordinator.

Orchestrates communication among specialized analysis agents (Market, Technical, Risk).
Synthesizes independent perspectives into an actionable consensus while strictly
upholding the Risk Agent's supreme veto mandate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from app.ai.agents.base_agent import AgentRecommendation, AgentResult, AnalysisAgent
from app.ai.agents.market_analysis_agent import MarketAnalysisAgent
from app.ai.agents.risk_agent import RiskAgent
from app.ai.agents.technical_agent import TechnicalAgent
from app.core.logging_config import get_logger

logger = get_logger("app.ai.agents.agent_coordinator")


@dataclass
class ConsolidatedDecision:
    """Consensus decision generated across all active analysis agents."""
    symbol: str
    action: str              # "BUY", "SELL", "HOLD", "VETO"
    confidence: float        # Aggregate weighted confidence (0.0 to 1.0)
    is_approved: bool        # True only if action in ("BUY", "SELL") and not vetoed
    vetoed_by_risk: bool
    veto_reason: Optional[str]
    agent_results: Dict[str, Dict[str, Any]]
    synthesis_rationale: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to dictionary representation."""
        return asdict(self)


class AgentCoordinator:
    """
    Coordinates multi-agent evaluations and enforces consensus rules.

    Architecture rules:
    1. Risk Agent has SOVEREIGN VETO POWER. If Risk Agent triggers a veto,
       the trade is immediately killed (action="VETO", is_approved=False).
    2. Technical and Market agents provide directional signals and confidence weighting.
    3. Trade approval requires alignment between technical and market regime or
       exceptional technical confluence.
    """

    def __init__(
        self,
        market_agent: Optional[MarketAnalysisAgent] = None,
        technical_agent: Optional[TechnicalAgent] = None,
        risk_agent: Optional[RiskAgent] = None,
    ) -> None:
        """
        Initialize the AgentCoordinator with standard or custom agent instances.

        Args:
            market_agent: Instance of MarketAnalysisAgent.
            technical_agent: Instance of TechnicalAgent.
            risk_agent: Instance of RiskAgent.
        """
        self.market_agent = market_agent or MarketAnalysisAgent()
        self.technical_agent = technical_agent or TechnicalAgent()
        self.risk_agent = risk_agent or RiskAgent()

        self._auxiliary_agents: List[AnalysisAgent] = []
        logger.info("Initialized AgentCoordinator with Market, Technical, and Risk agents")

    def register_auxiliary_agent(self, agent: AnalysisAgent) -> None:
        """Register an additional specialized analysis agent."""
        self._auxiliary_agents.append(agent)
        logger.info("Registered auxiliary agent: %s", agent.name)

    def coordinate(
        self,
        market_data: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> ConsolidatedDecision:
        """
        Execute concurrent multi-agent analysis and produce a consolidated verdict.

        Args:
            market_data: OHLCV DataFrame for the instrument.
            context: Environment dictionary containing symbol, proposed trade, account metrics.

        Returns:
            ConsolidatedDecision reflecting consensus with strict risk veto enforcement.
        """
        ctx = context or {}
        symbol = str(ctx.get("symbol", "UNKNOWN")).upper()

        logger.debug("Coordinating multi-agent assessment for %s", symbol)

        # ---------------------------------------------------------------------
        # Step 1: Collect individual agent analyses
        # ---------------------------------------------------------------------
        market_res: AgentResult = self.market_agent.analyze(market_data, ctx)
        tech_res: AgentResult = self.technical_agent.analyze(market_data, ctx)
        risk_res: AgentResult = self.risk_agent.analyze(market_data, ctx)

        aux_results: Dict[str, AgentResult] = {}
        for aux_agent in self._auxiliary_agents:
            try:
                aux_results[aux_agent.name] = aux_agent.analyze(market_data, ctx)
            except Exception as e:
                logger.error("Error executing auxiliary agent %s: %s", aux_agent.name, e)

        # ---------------------------------------------------------------------
        # Step 2: Enforce Risk Agent Sovereign Veto
        # ---------------------------------------------------------------------
        if risk_res.veto or risk_res.recommendation == AgentRecommendation.VETO:
            reason = risk_res.veto_reason or "Vetoed by RiskAgent due to safety boundary violation."
            logger.warning("Trade on %s VETOED by RiskAgent: %s", symbol, reason)

            all_results = {
                market_res.agent_name: market_res.to_dict(),
                tech_res.agent_name: tech_res.to_dict(),
                risk_res.agent_name: risk_res.to_dict(),
                **{k: v.to_dict() for k, v in aux_results.items()},
            }

            return ConsolidatedDecision(
                symbol=symbol,
                action="VETO",
                confidence=0.0,
                is_approved=False,
                vetoed_by_risk=True,
                veto_reason=reason,
                agent_results=all_results,
                synthesis_rationale=f"RISK VETO: {reason}",
            )

        # ---------------------------------------------------------------------
        # Step 3: Directional Consensus Synthesis (Technical + Market Regime)
        # ---------------------------------------------------------------------
        # Weights: Technical 60%, Market Regime 40%
        tech_rec = tech_res.recommendation
        market_rec = market_res.recommendation

        tech_score = 0.0
        if tech_rec == AgentRecommendation.BUY:
            tech_score = tech_res.confidence
        elif tech_rec == AgentRecommendation.SELL:
            tech_score = -tech_res.confidence

        market_score = 0.0
        if market_rec == AgentRecommendation.BUY:
            market_score = market_res.confidence
        elif market_rec == AgentRecommendation.SELL:
            market_score = -market_res.confidence

        # Combined consensus score (-1.0 to +1.0)
        consensus_score = (0.60 * tech_score) + (0.40 * market_score)

        if consensus_score >= 0.40:
            final_action = "BUY"
            aggregate_confidence = float(min(consensus_score + 0.1, 0.95))
            is_approved = True
            rationale = (
                f"Bullish consensus achieved ({consensus_score:+.2f}). "
                f"Technical: {tech_rec.value} ({tech_res.confidence:.1%}), "
                f"Market: {market_rec.value} ({market_res.confidence:.1%})."
            )
        elif consensus_score <= -0.40:
            final_action = "SELL"
            aggregate_confidence = float(min(abs(consensus_score) + 0.1, 0.95))
            is_approved = True
            rationale = (
                f"Bearish consensus achieved ({consensus_score:+.2f}). "
                f"Technical: {tech_rec.value} ({tech_res.confidence:.1%}), "
                f"Market: {market_rec.value} ({market_res.confidence:.1%})."
            )
        else:
            final_action = "HOLD"
            aggregate_confidence = float(1.0 - abs(consensus_score))
            is_approved = False
            rationale = (
                f"No decisive directional consensus ({consensus_score:+.2f}). "
                f"Technical is {tech_rec.value}, Market is {market_rec.value}."
            )

        all_results = {
            market_res.agent_name: market_res.to_dict(),
            tech_res.agent_name: tech_res.to_dict(),
            risk_res.agent_name: risk_res.to_dict(),
            **{k: v.to_dict() for k, v in aux_results.items()},
        }

        return ConsolidatedDecision(
            symbol=symbol,
            action=final_action,
            confidence=round(aggregate_confidence, 2),
            is_approved=is_approved,
            vetoed_by_risk=False,
            veto_reason=None,
            agent_results=all_results,
            synthesis_rationale=rationale,
        )
