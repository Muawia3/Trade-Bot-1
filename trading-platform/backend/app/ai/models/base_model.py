"""
Abstract Base Class and metrics schema for all AI/ML models.

Enforces uniform interface across Random Forest, Gradient Boost, and Neural Networks.
Explicitly safeguards that all predictions are probabilistic estimates and must be
treated strictly as advisory signals by downstream execution engines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd


@dataclass
class ModelMetrics:
    """Standard evaluation metrics for classification and directional forecasting."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    roc_auc: Optional[float] = None
    log_loss: Optional[float] = None
    samples_count: int = 0
    calculated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics dataclass to dictionary."""
        return asdict(self)


class BaseMLModel(ABC):
    """
    Abstract Base Class for financial market classification models.

    All implementations must support training, out-of-sample evaluation,
    serialization, deserialization, and feature attribution.
    """

    def __init__(self, model_name: str) -> None:
        """
        Initialize base model.

        Args:
            model_name: Unique identifier for the model instance.
        """
        self.model_name = model_name
        self.is_trained: bool = False
        self.feature_names: List[str] = []
        self.trained_at: Optional[datetime] = None
        self.metrics: Optional[ModelMetrics] = None

    @abstractmethod
    def train(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        """
        Train the model on historical feature matrix X and target labels y.

        Args:
            X: Training features.
            y: Target binary direction or multi-class labels.
            validation_data: Optional tuple of (X_val, y_val).
            **kwargs: Additional training hyperparameters.

        Returns:
            ModelMetrics containing in-sample or cross-validated performance metrics.
        """
        pass

    @abstractmethod
    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict discrete market direction labels for input feature matrix.

        Args:
            X: Feature matrix.

        Returns:
            1D array of predicted class labels (e.g. 1 for UP/BUY, 0 for DOWN/SELL).
        """
        pass

    @abstractmethod
    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """
        Predict class probabilities for input feature matrix.

        Args:
            X: Feature matrix.

        Returns:
            2D array of class probabilities shape (n_samples, n_classes).
        """
        pass

    @abstractmethod
    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> ModelMetrics:
        """
        Evaluate model performance on unseen test data.

        Args:
            X: Test features.
            y: Ground truth labels.

        Returns:
            ModelMetrics object summarizing test set accuracy, precision, recall, and F1.
        """
        pass

    @abstractmethod
    def save_model(self, path: Union[str, Path]) -> str:
        """
        Serialize model weights, hyperparameters, and feature metadata to disk.

        Args:
            path: Destination file path or directory.

        Returns:
            String path to saved model artifact.
        """
        pass

    @abstractmethod
    def load_model(self, path: Union[str, Path]) -> None:
        """
        Deserialize model weights, hyperparameters, and feature metadata from disk.

        Args:
            path: Source file path.
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Extract feature importance scores sorted in descending order.

        Returns:
            Dictionary mapping feature column names to importance values (summing to ~1.0).
        """
        pass
