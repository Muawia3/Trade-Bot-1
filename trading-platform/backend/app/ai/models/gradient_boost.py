"""
Gradient Boosting Classifier for market direction and regime prediction.

Utilizes scikit-learn GradientBoostingClassifier with integrated feature selection,
stochastic subsampling, and model interpretability helpers.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_selection import SelectFromModel
from sklearn.metrics import accuracy_score, f1_score, log_loss, precision_score, recall_score, roc_auc_score

from app.ai.models.base_model import BaseMLModel, ModelMetrics
from app.core.logging_config import get_logger

logger = get_logger("app.ai.models.gradient_boost")


class GradientBoostModel(BaseMLModel):
    """
    Gradient Boosting model for directional market movement.

    Provides feature pruning via SelectFromModel and granular model interpretation.
    """

    def __init__(
        self,
        model_name: str = "gb_market_direction",
        n_estimators: int = 120,
        learning_rate: float = 0.05,
        max_depth: int = 4,
        subsample: float = 0.85,
        min_samples_split: int = 15,
        min_samples_leaf: int = 10,
        random_state: int = 42,
    ) -> None:
        """
        Initialize Gradient Boost model.

        Args:
            model_name: Unique model identifier.
            n_estimators: Number of boosting stages to perform.
            learning_rate: Shrinkage parameter.
            max_depth: Maximum individual tree depth.
            subsample: Fraction of samples to use for fitting individual base learners.
            min_samples_split: Minimum samples required to split an internal node.
            min_samples_leaf: Minimum samples required at leaf node.
            random_state: Reproducibility seed.
        """
        super().__init__(model_name=model_name)
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.max_depth = max_depth
        self.subsample = subsample
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.random_state = random_state

        self.classifier = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            max_depth=self.max_depth,
            subsample=self.subsample,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            random_state=self.random_state,
        )

        self.selected_features: Optional[List[str]] = None
        self.feature_selector: Optional[SelectFromModel] = None

    def train(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        perform_feature_selection: bool = False,
        max_features_to_select: Optional[int] = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        """
        Train the gradient boosting model with optional automated feature selection.

        Args:
            X: Training features.
            y: Binary or multi-class target.
            validation_data: Optional (X_val, y_val).
            perform_feature_selection: If True, prunes low-importance features prior to final training.
            max_features_to_select: Max features retained if feature selection is enabled.
            **kwargs: Extra parameters.

        Returns:
            ModelMetrics object.
        """
        X_arr, y_arr = self._prepare_data(X, y)

        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
        elif not self.feature_names:
            self.feature_names = [f"feat_{i}" for i in range(X_arr.shape[1])]

        # Optional Feature Selection step
        if perform_feature_selection:
            logger.info("Executing feature selection on %d features...", len(self.feature_names))
            selector_model = GradientBoostingClassifier(
                n_estimators=50,
                max_depth=3,
                random_state=self.random_state,
            )
            selector_model.fit(X_arr, y_arr)

            self.feature_selector = SelectFromModel(
                selector_model,
                max_features=max_features_to_select,
                prefit=True,
            )
            support_mask = self.feature_selector.get_support()
            self.selected_features = [
                name for name, selected in zip(self.feature_names, support_mask) if selected
            ]
            X_arr = self.feature_selector.transform(X_arr)
            logger.info(
                "Feature selection completed. Retained %d of %d features: %s",
                len(self.selected_features),
                len(self.feature_names),
                self.selected_features[:5],
            )
        else:
            self.selected_features = list(self.feature_names)

        logger.info(
            "Fitting GradientBoostingClassifier on %d samples with %d features",
            X_arr.shape[0],
            X_arr.shape[1],
        )

        self.classifier.fit(X_arr, y_arr)
        self.is_trained = True
        self.trained_at = datetime.utcnow()

        if validation_data is not None:
            X_val, y_val = validation_data
            self.metrics = self.evaluate(X_val, y_val)
        else:
            self.metrics = self.evaluate(X_arr, y_arr)

        logger.info(
            "GradientBoost %s training complete. Accuracy: %.4f, F1: %.4f",
            self.model_name,
            self.metrics.accuracy,
            self.metrics.f1_score,
        )
        return self.metrics

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class labels for given input data."""
        self._ensure_trained()
        X_transformed = self._transform_input(X)
        return self.classifier.predict(X_transformed)

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class probability distribution."""
        self._ensure_trained()
        X_transformed = self._transform_input(X)
        return self.classifier.predict_proba(X_transformed)

    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> ModelMetrics:
        """Evaluate model against labeled test data."""
        self._ensure_trained()
        X_transformed = self._transform_input(X)
        y_arr = self._to_numpy(y).ravel()

        preds = self.classifier.predict(X_transformed)
        probas = self.classifier.predict_proba(X_transformed)

        acc = float(accuracy_score(y_arr, preds))
        prec = float(precision_score(y_arr, preds, average="weighted", zero_division=0))
        rec = float(recall_score(y_arr, preds, average="weighted", zero_division=0))
        f1 = float(f1_score(y_arr, preds, average="weighted", zero_division=0))

        roc_auc: Optional[float] = None
        loss: Optional[float] = None

        if len(np.unique(y_arr)) == 2 and probas.shape[1] == 2:
            try:
                roc_auc = float(roc_auc_score(y_arr, probas[:, 1]))
                loss = float(log_loss(y_arr, probas))
            except Exception as e:
                logger.debug("Evaluation metrics note: %s", e)

        return ModelMetrics(
            accuracy=acc,
            precision=prec,
            recall=rec,
            f1_score=f1,
            roc_auc=roc_auc,
            log_loss=loss,
            samples_count=len(y_arr),
        )

    def get_feature_importance(self) -> Dict[str, float]:
        """Return dictionary of feature importance scores."""
        self._ensure_trained()
        importances = self.classifier.feature_importances_

        names = self.selected_features or self.feature_names
        if not names or len(names) != len(importances):
            names = [f"feat_{i}" for i in range(len(importances))]

        return {
            name: float(val)
            for name, val in sorted(zip(names, importances), key=lambda x: x[1], reverse=True)
        }

    def interpret_prediction(
        self,
        sample: Union[pd.Series, pd.DataFrame, np.ndarray],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Produce a human-readable interpretation of which features dominate the model's stance.

        Args:
            sample: Single observation row.
            top_k: Number of influential features to highlight.

        Returns:
            Dictionary with predicted class, confidence, and top driving features.
        """
        self._ensure_trained()
        if isinstance(sample, pd.Series):
            sample_df = sample.to_frame().T
        elif isinstance(sample, np.ndarray) and sample.ndim == 1:
            sample_df = sample.reshape(1, -1)
        else:
            sample_df = sample

        pred = int(self.predict(sample_df)[0])
        probas = self.predict_proba(sample_df)[0]
        confidence = float(np.max(probas))

        # Top influential features from global importance
        importances = self.get_feature_importance()
        top_features = list(importances.items())[:top_k]

        return {
            "prediction": pred,
            "direction": "BUY" if pred == 1 else ("SELL" if pred == 0 else "HOLD"),
            "confidence": confidence,
            "probabilities": [float(p) for p in probas],
            "key_factors": [
                {"feature": feat, "importance_weight": weight}
                for feat, weight in top_features
            ],
            "interpretation_notice": "Probabilistic model output. Strictly advisory.",
        }

    def save_model(self, path: Union[str, Path]) -> str:
        """Save model weights and metadata to file."""
        self._ensure_trained()
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model_name": self.model_name,
            "classifier": self.classifier,
            "feature_names": self.feature_names,
            "selected_features": self.selected_features,
            "feature_selector": self.feature_selector,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "hyperparams": {
                "n_estimators": self.n_estimators,
                "learning_rate": self.learning_rate,
                "max_depth": self.max_depth,
                "subsample": self.subsample,
                "min_samples_split": self.min_samples_split,
                "min_samples_leaf": self.min_samples_leaf,
                "random_state": self.random_state,
            },
        }

        joblib.dump(payload, str(target_path))
        logger.info("Saved %s artifact to %s", self.model_name, target_path)
        return str(target_path)

    def load_model(self, path: Union[str, Path]) -> None:
        """Load model weights and metadata from file."""
        src_path = Path(path)
        if not src_path.exists():
            raise FileNotFoundError(f"Model file not found at {src_path}")

        payload = joblib.load(str(src_path))
        self.model_name = payload["model_name"]
        self.classifier = payload["classifier"]
        self.feature_names = payload["feature_names"]
        self.selected_features = payload.get("selected_features")
        self.feature_selector = payload.get("feature_selector")
        self.trained_at = (
            datetime.fromisoformat(payload["trained_at"])
            if payload.get("trained_at")
            else None
        )
        if payload.get("metrics"):
            self.metrics = ModelMetrics(**payload["metrics"])

        self.is_trained = True
        logger.info("Loaded %s artifact from %s", self.model_name, src_path)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _ensure_trained(self) -> None:
        if not self.is_trained:
            raise RuntimeError(f"Model '{self.model_name}' has not been trained yet.")

    @staticmethod
    def _to_numpy(data: Union[pd.DataFrame, np.ndarray, pd.Series]) -> np.ndarray:
        if isinstance(data, (pd.DataFrame, pd.Series)):
            return data.values
        return np.asarray(data)

    def _transform_input(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        X_arr = self._to_numpy(X)
        if self.feature_selector is not None:
            # Only apply transformation if input matches original full feature count
            if len(self.feature_names) > 0 and X_arr.ndim == 2 and X_arr.shape[1] == len(self.feature_names):
                return self.feature_selector.transform(X_arr)
        return X_arr

    @classmethod
    def _prepare_data(
        cls,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> Tuple[np.ndarray, np.ndarray]:
        X_arr = cls._to_numpy(X)
        y_arr = cls._to_numpy(y).ravel()
        if len(X_arr) != len(y_arr):
            raise ValueError(f"Shape mismatch: X has {len(X_arr)} rows, y has {len(y_arr)} elements")
        return X_arr, y_arr
