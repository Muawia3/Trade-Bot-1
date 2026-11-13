"""
Risk Management Agent with Sovereign Veto Authority.

The RiskAgent acts as the ultimate gatekeeper for all algorithmic trade executions.
Holds unilateral authority to VETO any proposed trade, override ML predictions,
and enforce hard capital protection boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.ai.agents.base_agent import AgentRecommendation, AgentResult, AnalysisAgent
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.services.news_service import NewsService

logger = get_logger("app.ai.agents.risk_agent")


@dataclass
class RiskAssessment:
    """Detailed risk metrics evaluation."""
    is_safe: bool
    veto_triggered: bool
    violations: List[str]
    max_allowed_risk_pct: float
    current_daily_loss_pct: float
    open_positions_count: int
    spread_pips: Optional[float] = None
    news_restricted: bool = False


class RiskAgent(AnalysisAgent):
    """
    Independent Risk Guardian.

    Has ABSOLUTE FINAL AUTHORITY over all automated trade decisions.
    Even if TechnicalAgent, MarketAnalysisAgent, and ML models all indicate a high-confidence BUY,
    the RiskAgent can and must VETO the execution if safety thresholds are violated.
    """

    def __init__(
        self,
        news_service: Optional[NewsService] = None,
        max_daily_loss_pct: Optional[float] = None,
        max_open_positions: Optional[int] = None,
        max_spread_pips: float = 5.0,
        min_risk_reward_ratio: float = 1.2,
    ) -> None:
        """
        Initialize the RiskAgent.

        Args:
            news_service: NewsService for checking impending high-impact economic releases.
            max_daily_loss_pct: Max allowable daily drawdown % (defaults to settings).
            max_open_positions: Max simultaneous open positions (defaults to settings).
            max_spread_pips: Max acceptable spread before blocking execution.
            min_risk_reward_ratio: Minimum acceptable Reward-to-Risk ratio for new setups.
        """
        super().__init__(
            name="RiskAgent",
            description="Enforces strict capital protection, drawdown limits, and holds absolute trade veto power.",
        )
        self.settings = get_settings()
        self.news_service = news_service or NewsService()
        self.max_daily_loss_pct = (
            max_daily_loss_pct
            if max_daily_loss_pct is not None
            else self.settings.MAX_DAILY_LOSS_PERCENT
        )
        self.max_open_positions = (
            max_open_positions
            if max_open_positions is not None
            else self.settings.MAX_OPEN_POSITIONS
        )
        self.max_spread_pips = max_spread_pips
        self.min_risk_reward_ratio = min_risk_reward_ratio

    def analyze(
        self,
        market_data: pd.DataFrame,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Conduct full risk evaluation on execution environment and proposed signal.

        Args:
            market_data: Market price history.
            context: Environment dictionary containing:
                     - 'symbol': Instrument name
                     - 'proposed_trade': Dict with entry, sl, tp, volume
                     - 'daily_loss_pct': Current realized/unrealized loss today
                     - 'open_positions_count': Number of currently active trades
                     - 'current_spread_pips': Current live market spread

        Returns:
            AgentResult. If risk thresholds are violated, recommendation is VETO with veto=True.
        """
        ctx = context or {}
        symbol = str(ctx.get("symbol", "UNKNOWN")).upper()
        daily_loss_pct = float(ctx.get("daily_loss_pct", 0.0))
        open_positions = int(ctx.get("open_positions_count", 0))
        current_spread = ctx.get("current_spread_pips")
        proposed_trade = ctx.get("proposed_trade")

        violations: List[str] = []
        reasoning: List[str] = []

        # ---------------------------------------------------------------------
        # Check 1: Daily Drawdown / Max Daily Loss
        # ---------------------------------------------------------------------
        if daily_loss_pct >= self.max_daily_loss_pct:
            violations.append(
                f"Daily drawdown limit REACHED: Current loss {daily_loss_pct:.2f}% >= limit {self.max_daily_loss_pct:.2f}%."
            )

        # ---------------------------------------------------------------------
        # Check 2: Max Open Positions
        # ---------------------------------------------------------------------
        if open_positions >= self.max_open_positions:
            violations.append(
                f"Maximum open positions limit REACHED: {open_positions} active >= limit {self.max_open_positions}."
            )

        # ---------------------------------------------------------------------
        # Check 3: Imminent Macroeconomic News Blackout
        # ---------------------------------------------------------------------
        news_restricted, news_reason = self.news_service.should_restrict_trading(symbol)
        if news_restricted:
            violations.append(f"Macroeconomic News Blackout: {news_reason}")

        # ---------------------------------------------------------------------
        # Check 4: Spread Blowout
        # ---------------------------------------------------------------------
        if current_spread is not None and float(current_spread) > self.max_spread_pips:
            violations.append(
                f"Excessive spread detected on {symbol}: {float(current_spread):.1f} pips > max {self.max_spread_pips} pips."
            )

        # ---------------------------------------------------------------------
        # Check 5: Proposed Trade Parameter Sanity (SL, TP, Risk-Reward)
        # ---------------------------------------------------------------------
        if proposed_trade:
            entry = proposed_trade.get("entry_price")
            sl = proposed_trade.get("stop_loss")
            tp = proposed_trade.get("take_profit")
            side = proposed_trade.get("side", "").lower()

            if not sl:
                violations.append("Trade lacks mandatory STOP LOSS. Execution strictly forbidden.")
            elif entry and sl and tp:
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                if risk <= 0:
                    violations.append("Stop loss is equal to or on incorrect side of entry price.")
                else:
                    rr = reward / risk
                    if rr < self.min_risk_reward_ratio:
                        violations.append(
                            f"Risk-to-Reward ratio {rr:.2f} is below mandatory minimum of {self.min_risk_reward_ratio:.2f}."
                        )

        # ---------------------------------------------------------------------
        # Synthesize Veto Verdict
        # ---------------------------------------------------------------------
        is_vetoed = len(violations) > 0

        if is_vetoed:
            rec = AgentRecommendation.VETO
            confidence = 1.0  # Risk veto is absolute
            primary_reason = " | ".join(violations)
            reasoning.extend(violations)
            logger.warning("[RISK VETO TRIGGERED] %s: %s", symbol, primary_reason)
        else:
            rec = AgentRecommendation.BUY  # Neutral / Safe approval
            confidence = 0.95
            primary_reason = None
            reasoning.append("All risk boundaries cleared: Drawdown, position count, spread, and news check passed.")

        findings = {
            "is_safe": not is_vetoed,
            "violations_count": len(violations),
            "daily_loss_pct": daily_loss_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "open_positions": open_positions,
            "max_open_positions": self.max_open_positions,
            "news_restricted": news_restricted,
            "spread_pips": current_spread,
        }

        return AgentResult(
            agent_name=self.name,
            recommendation=rec,
            confidence=confidence,
            findings=findings,
            reasoning=reasoning,
            veto=is_vetoed,
            veto_reason=primary_reason,
        )

    def veto_trade(
        self,
        symbol: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Direct convenience query to determine if a trade is vetoed.

        Returns:
            Tuple of (is_vetoed, reason_string).
        """
        res = self.analyze(market_data=pd.DataFrame(), context={"symbol": symbol, **(context or {})})
        return res.veto, res.veto_reason
