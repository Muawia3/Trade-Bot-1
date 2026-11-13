"""
Random Forest Classifier for financial market direction forecasting.

Implements ensemble decision trees with out-of-bag validation, time-series
cross-validation, hyperparameter optimization, and feature importance attribution.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from app.ai.models.base_model import BaseMLModel, ModelMetrics
from app.core.logging_config import get_logger

logger = get_logger("app.ai.models.random_forest")


class RandomForestModel(BaseMLModel):
    """
    Random Forest ensemble model specifically configured for financial time series.

    Guards against lookahead bias by using TimeSeriesSplit for cross-validation
    and hyperparameter optimization.
    """

    def __init__(
        self,
        model_name: str = "rf_market_direction",
        n_estimators: int = 150,
        max_depth: Optional[int] = 8,
        min_samples_split: int = 10,
        min_samples_leaf: int = 5,
        max_features: Union[str, float] = "sqrt",
        random_state: int = 42,
        class_weight: Optional[str] = "balanced",
    ) -> None:
        """
        Initialize the Random Forest model.

        Args:
            model_name: Unique model identifier.
            n_estimators: Number of trees in the forest.
            max_depth: Maximum tree depth to control overfitting.
            min_samples_split: Minimum samples required to split an internal node.
            min_samples_leaf: Minimum samples required at leaf node.
            max_features: Number of features to consider per split.
            random_state: Reproducibility seed.
            class_weight: 'balanced' or None.
        """
        super().__init__(model_name=model_name)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.random_state = random_state
        self.class_weight = class_weight

        self.classifier = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_split=self.min_samples_split,
            min_samples_leaf=self.min_samples_leaf,
            max_features=self.max_features,
            random_state=self.random_state,
            class_weight=self.class_weight,
            n_jobs=-1,
            oob_score=True,
        )

    def train(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        """
        Train Random Forest model and compute in-sample / validation metrics.

        Args:
            X: Feature matrix.
            y: Target binary/multi-class labels.
            validation_data: Optional tuple of (X_val, y_val).
            **kwargs: Ignored additional kwargs.

        Returns:
            ModelMetrics object.
        """
        X_arr, y_arr = self._prepare_data(X, y)

        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
        elif not self.feature_names:
            self.feature_names = [f"feat_{i}" for i in range(X_arr.shape[1])]

        logger.info(
            "Training %s with %d samples and %d features",
            self.model_name,
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
            "Model %s trained successfully. Accuracy: %.4f, F1: %.4f",
            self.model_name,
            self.metrics.accuracy,
            self.metrics.f1_score,
        )
        return self.metrics

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict directional class labels."""
        self._ensure_trained()
        X_arr = self._to_numpy(X)
        return self.classifier.predict(X_arr)

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class probabilities."""
        self._ensure_trained()
        X_arr = self._to_numpy(X)
        return self.classifier.predict_proba(X_arr)

    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> ModelMetrics:
        """Compute comprehensive performance metrics on test data."""
        self._ensure_trained()
        X_arr, y_arr = self._prepare_data(X, y)
        preds = self.classifier.predict(X_arr)
        probas = self.classifier.predict_proba(X_arr)

        acc = float(accuracy_score(y_arr, preds))
        prec = float(precision_score(y_arr, preds, average="weighted", zero_division=0))
        rec = float(recall_score(y_arr, preds, average="weighted", zero_division=0))
        f1 = float(f1_score(y_arr, preds, average="weighted", zero_division=0))

        roc_auc: Optional[float] = None
        loss: Optional[float] = None

        unique_classes = np.unique(y_arr)
        if len(unique_classes) == 2 and probas.shape[1] == 2:
            try:
                roc_auc = float(roc_auc_score(y_arr, probas[:, 1]))
                loss = float(log_loss(y_arr, probas))
            except Exception as e:
                logger.debug("ROC-AUC / Log-Loss computation skipped: %s", e)

        additional: Dict[str, Any] = {}
        if hasattr(self.classifier, "oob_score_") and self.classifier.oob_score_:
            additional["oob_score"] = float(self.classifier.oob_score_)

        return ModelMetrics(
            accuracy=acc,
            precision=prec,
            recall=rec,
            f1_score=f1,
            roc_auc=roc_auc,
            log_loss=loss,
            samples_count=len(y_arr),
            additional_info=additional,
        )

    def cross_validate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        n_splits: int = 5,
    ) -> Dict[str, float]:
        """
        Perform TimeSeriesSplit cross-validation to prevent temporal lookahead leakage.

        Args:
            X: Feature matrix.
            y: Target array.
            n_splits: Number of temporal splits.

        Returns:
            Dict containing mean accuracy, precision, recall, and f1.
        """
        X_arr, y_arr = self._prepare_data(X, y)
        tscv = TimeSeriesSplit(n_splits=n_splits)

        accuracies: List[float] = []
        f1s: List[float] = []

        for fold, (train_idx, test_idx) in enumerate(tscv.split(X_arr)):
            X_tr, y_tr = X_arr[train_idx], y_arr[train_idx]
            X_te, y_te = X_arr[test_idx], y_arr[test_idx]

            temp_clf = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                random_state=self.random_state,
                n_jobs=-1,
            )
            temp_clf.fit(X_tr, y_tr)
            preds = temp_clf.predict(X_te)
            accuracies.append(accuracy_score(y_te, preds))
            f1s.append(f1_score(y_te, preds, average="weighted", zero_division=0))

        results = {
            "cv_accuracy_mean": float(np.mean(accuracies)),
            "cv_accuracy_std": float(np.std(accuracies)),
            "cv_f1_mean": float(np.mean(f1s)),
            "cv_f1_std": float(np.std(f1s)),
        }
        logger.info("TimeSeriesSplit CV results: %s", results)
        return results

    def tune_hyperparameters(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        param_grid: Optional[Dict[str, List[Any]]] = None,
        n_splits: int = 3,
    ) -> Dict[str, Any]:
        """
        Perform grid search with TimeSeriesSplit to find optimal hyperparameters.

        Args:
            X: Feature matrix.
            y: Labels.
            param_grid: Parameter dictionary for grid search.
            n_splits: Time series folds.

        Returns:
            Best parameter dictionary.
        """
        X_arr, y_arr = self._prepare_data(X, y)

        if param_grid is None:
            param_grid = {
                "n_estimators": [100, 200],
                "max_depth": [5, 8, 12],
                "min_samples_split": [5, 10],
                "min_samples_leaf": [2, 5],
            }

        tscv = TimeSeriesSplit(n_splits=n_splits)
        grid_search = GridSearchCV(
            estimator=RandomForestClassifier(random_state=self.random_state, n_jobs=-1),
            param_grid=param_grid,
            cv=tscv,
            scoring="f1_weighted",
            n_jobs=-1,
        )

        logger.info("Starting hyperparameter tuning with %d combinations...", len(param_grid))
        grid_search.fit(X_arr, y_arr)

        best_params = grid_search.best_params_
        logger.info("Optimal parameters found: %s with score: %.4f", best_params, grid_search.best_score_)

        # Update internal classifier with best params
        self.classifier.set_params(**best_params)
        return best_params

    def get_feature_importance(self) -> Dict[str, float]:
        """Return dictionary of feature names mapped to Gini importance scores."""
        self._ensure_trained()
        importances = self.classifier.feature_importances_

        if not self.feature_names or len(self.feature_names) != len(importances):
            names = [f"feat_{i}" for i in range(len(importances))]
        else:
            names = self.feature_names

        importance_dict = {
            name: float(val)
            for name, val in sorted(zip(names, importances), key=lambda x: x[1], reverse=True)
        }
        return importance_dict

    def save_model(self, path: Union[str, Path]) -> str:
        """Save model object and metadata."""
        self._ensure_trained()
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model_name": self.model_name,
            "classifier": self.classifier,
            "feature_names": self.feature_names,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "hyperparams": {
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "min_samples_split": self.min_samples_split,
                "min_samples_leaf": self.min_samples_leaf,
                "random_state": self.random_state,
            },
        }

        joblib.dump(payload, str(target_path))
        logger.info("Saved %s artifact to %s", self.model_name, target_path)
        return str(target_path)

    def load_model(self, path: Union[str, Path]) -> None:
        """Load model object and metadata."""
        src_path = Path(path)
        if not src_path.exists():
            raise FileNotFoundError(f"Model file not found at {src_path}")

        payload = joblib.load(str(src_path))
        self.model_name = payload["model_name"]
        self.classifier = payload["classifier"]
        self.feature_names = payload["feature_names"]
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
    # Internal validation helpers
    # -------------------------------------------------------------------------

    def _ensure_trained(self) -> None:
        if not self.is_trained:
            raise RuntimeError(f"Model '{self.model_name}' has not been trained yet.")

    @staticmethod
    def _to_numpy(data: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        if isinstance(data, (pd.DataFrame, pd.Series)):
            return data.values
        return np.asarray(data)

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
