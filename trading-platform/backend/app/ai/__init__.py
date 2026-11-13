"""
AI/ML subsystem package for the Forex & Gold Trading Platform.

Provides:
- Machine Learning models (Random Forest, Gradient Boosting, PyTorch LSTM)
- Feature Engineering for financial time series
- Multi-Agent Market & Risk analysis architecture
- Advisory prediction services integrated with risk controls

SAFETY DISCLAIMER:
AI and Machine Learning predictions are inherently probabilistic and uncertain.
All models serve in an ADVISORY capacity only and can NEVER override or bypass
risk management rules, hard stop losses, or daily drawdown limits.
Past performance and model predictions do not guarantee future results or profits.
"""

from app.ai.feature_engineering import FeatureEngineer
from app.ai.model_manager import ModelManager, TrainingResult, ModelRegistryEntry
from app.ai.prediction_service import PredictionService, AIPrediction

__all__ = [
    "FeatureEngineer",
    "ModelManager",
    "TrainingResult",
    "ModelRegistryEntry",
    "PredictionService",
    "AIPrediction",
]
