"""
Market Sentiment Analysis module.

Defines the TextSentimentAnalyzer interface and provides mock/extensible implementations
for processing financial news headlines, central bank communiqués, and social commentary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logging_config import get_logger

logger = get_logger("app.ai.sentiment")


@dataclass
class SentimentResult:
    """Standardized representation of textual sentiment analysis."""
    score: float       # Continuum from -1.0 (extremely bearish) to +1.0 (extremely bullish)
    label: str         # "BULLISH", "BEARISH", "NEUTRAL"
    confidence: float  # Confidence level 0.0 to 1.0
    source: str        # Origin identifier (e.g. "mock_analyzer", "external_api")
    sample_text: str   # Snippet or headline evaluated
    keywords_detected: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


class TextSentimentAnalyzer(ABC):
    """
    Abstract interface for Natural Language Processing sentiment analyzers.

    All real or simulated sentiment providers adhere to this contract.
    """

    @abstractmethod
    def analyze_text(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of a single financial text headline or paragraph.

        Args:
            text: Input string.

        Returns:
            SentimentResult.
        """
        pass

    @abstractmethod
    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """
        Analyze sentiment for a collection of articles or headlines.

        Args:
            texts: List of text strings.

        Returns:
            List of SentimentResult objects.
        """
        pass


class MockSentimentAnalyzer(TextSentimentAnalyzer):
    """
    Heuristic rule-based sentiment analyzer for testing and development.

    Uses financial keyword dictionaries to classify sentiment without external API calls.
    """

    BULLISH_KEYWORDS = [
        "surge", "rally", "gain", "hawkish", "hike", "strong", "outperform",
        "beat", "growth", "bullish", "jump", "record high", "optimism"
    ]

    BEARISH_KEYWORDS = [
        "plunge", "drop", "fall", "dovish", "cut", "weak", "slump",
        "miss", "recession", "bearish", "crash", "selloff", "inflation fear"
    ]

    def __init__(self) -> None:
        """Initialize mock sentiment analyzer."""
        logger.info("Initialized MockSentimentAnalyzer")

    def analyze_text(self, text: str) -> SentimentResult:
        """Evaluate text using financial sentiment lexicon."""
        if not text or not text.strip():
            return SentimentResult(
                score=0.0,
                label="NEUTRAL",
                confidence=0.5,
                source="mock_analyzer",
                sample_text="",
            )

        lower_text = text.lower()
        bullish_hits = [k for k in self.BULLISH_KEYWORDS if k in lower_text]
        bearish_hits = [k for k in self.BEARISH_KEYWORDS if k in lower_text]

        total_hits = len(bullish_hits) + len(bearish_hits)
        if total_hits == 0:
            score = 0.0
            label = "NEUTRAL"
            confidence = 0.5
        else:
            net = len(bullish_hits) - len(bearish_hits)
            score = max(min(net / float(total_hits), 1.0), -1.0)
            if score > 0.15:
                label = "BULLISH"
            elif score < -0.15:
                label = "BEARISH"
            else:
                label = "NEUTRAL"
            confidence = min(0.5 + 0.1 * total_hits, 0.95)

        return SentimentResult(
            score=round(score, 3),
            label=label,
            confidence=round(confidence, 2),
            source="mock_analyzer",
            sample_text=text[:100] + ("..." if len(text) > 100 else ""),
            keywords_detected=bullish_hits + bearish_hits,
        )

    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Evaluate multiple headlines."""
        return [self.analyze_text(t) for t in texts]


class ExternalAPISentimentAnalyzer(TextSentimentAnalyzer):
    """
    Extensible client template for external sentiment APIs (e.g. FinBERT, OpenAI, NewsAPI).

    Gracefully falls back to MockSentimentAnalyzer if API credentials are not configured.
    """

    def __init__(self, api_key: Optional[str] = None, endpoint_url: Optional[str] = None) -> None:
        """
        Initialize external API client.

        Args:
            api_key: Secret API token.
            endpoint_url: Base endpoint.
        """
        self.api_key = api_key
        self.endpoint_url = endpoint_url
        self.fallback = MockSentimentAnalyzer()

        if not self.api_key:
            logger.info("External sentiment API key not configured. Operating in fallback heuristic mode.")

    def analyze_text(self, text: str) -> SentimentResult:
        """Analyze text with external provider or fallback."""
        if not self.api_key:
            return self.fallback.analyze_text(text)

        # Placeholder: If real API configured, would call httpx/requests here
        logger.debug("API call simulated for external sentiment on text: %s...", text[:30])
        res = self.fallback.analyze_text(text)
        res.source = "external_api_simulated"
        return res

    def analyze_batch(self, texts: List[str]) -> List[SentimentResult]:
        """Analyze batch with external provider or fallback."""
        return [self.analyze_text(t) for t in texts]
