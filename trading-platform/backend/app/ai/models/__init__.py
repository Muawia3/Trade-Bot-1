"""
Machine Learning models package for Forex and Gold market prediction.

Models provided:
- BaseMLModel: Abstract base class defining common ML interface
- RandomForestModel: Random forest classifier with tuning & importance
- GradientBoostModel: Gradient boosted decision trees with feature selection
- PyTorchLSTMModel: Recurrent deep learning model for temporal sequences (optional)
"""

from app.ai.models.base_model import BaseMLModel, ModelMetrics
from app.ai.models.random_forest import RandomForestModel
from app.ai.models.gradient_boost import GradientBoostModel
from app.ai.models.lstm_model import PyTorchLSTMModel, is_pytorch_available

__all__ = [
    "BaseMLModel",
    "ModelMetrics",
    "RandomForestModel",
    "GradientBoostModel",
    "PyTorchLSTMModel",
    "is_pytorch_available",
]
