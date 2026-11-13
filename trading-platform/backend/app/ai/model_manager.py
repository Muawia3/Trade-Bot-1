"""
Model Manager for lifecycle, registry, versioning, drift detection, and inference routing.

Coordinates training, evaluation, persistence, and continuous monitoring
of machine learning models across Forex pairs and Gold.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats

from app.ai.models.base_model import BaseMLModel, ModelMetrics
from app.ai.models.gradient_boost import GradientBoostModel
from app.ai.models.lstm_model import PyTorchLSTMModel, is_pytorch_available
from app.ai.models.random_forest import RandomForestModel
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger("app.ai.model_manager")


@dataclass
class TrainingResult:
    """Summary record of a completed model training run."""
    model_name: str
    model_type: str
    symbol: str
    timeframe: str
    version: str
    artifact_path: str
    metrics: Dict[str, Any]
    feature_count: int
    train_samples: int
    trained_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "success"
    error: Optional[str] = None


@dataclass
class PredictionOutput:
    """Standardized output container for model inference."""
    model_name: str
    symbol: str
    prediction: int  # 1: Up/Buy, 0: Down/Sell, -1: Undefined
    direction: str   # "BUY", "SELL", "NEUTRAL"
    confidence: float
    probabilities: List[float]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRegistryEntry:
    """Metadata tracking entry in the registry."""
    model_name: str
    model_type: str
    symbol: str
    timeframe: str
    version: str
    artifact_path: str
    metrics: Dict[str, Any]
    created_at: str
    is_active: bool = True
    prediction_count: int = 0
    drift_score: float = 0.0


class ModelManager:
    """
    Central orchestrator for AI/ML models.

    Handles training pipelines, versioned artifact storage, registry management,
    runtime prediction routing, and data drift detection.
    """

    def __init__(self, models_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the ModelManager.

        Args:
            models_dir: Directory where model weights and registry metadata are stored.
        """
        settings = get_settings()
        base_dir = Path(models_dir) if models_dir else Path("data/models")
        self.models_dir = base_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.models_dir / "registry.json"
        self._registry: Dict[str, ModelRegistryEntry] = {}
        self._loaded_models: Dict[str, BaseMLModel] = {}
        self._prediction_history: Dict[str, List[float]] = {}
        self._reference_distributions: Dict[str, List[float]] = {}

        self._load_registry()

    # -------------------------------------------------------------------------
    # Training & Lifecycle
    # -------------------------------------------------------------------------

    def train_model(
        self,
        model_type: str,
        symbol: str,
        timeframe: str,
        features: pd.DataFrame,
        labels: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[pd.DataFrame, Union[pd.Series, np.ndarray]]] = None,
        hyperparams: Optional[Dict[str, Any]] = None,
    ) -> TrainingResult:
        """
        Train a new model version, evaluate performance, and register artifact.

        Args:
            model_type: 'random_forest', 'gradient_boost', or 'lstm'.
            symbol: Financial instrument (e.g. 'XAUUSD', 'EURUSD').
            timeframe: Bar timeframe (e.g. 'M15', 'H1').
            features: Input feature matrix.
            labels: Directional labels.
            validation_data: Optional test/validation split.
            hyperparams: Model specific kwargs.

        Returns:
            TrainingResult with performance metrics and persistence path.
        """
        model_type = model_type.lower().strip()
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        version = f"v_{timestamp_str}"
        model_name = f"{symbol}_{timeframe}_{model_type}_{version}"

        logger.info(
            "Initiating training for %s (%s, %s) with %d samples",
            model_name,
            symbol,
            timeframe,
            len(features),
        )

        params = hyperparams or {}

        try:
            model: BaseMLModel
            if model_type in ("random_forest", "rf"):
                model = RandomForestModel(model_name=model_name, **params)
            elif model_type in ("gradient_boost", "gb"):
                model = GradientBoostModel(model_name=model_name, **params)
            elif model_type == "lstm":
                if not is_pytorch_available():
                    raise RuntimeError("PyTorch is not installed. LSTM training skipped.")
                model = PyTorchLSTMModel(model_name=model_name, **params)
            else:
                raise ValueError(f"Unsupported model_type: '{model_type}'")

            # Execute training
            metrics = model.train(X=features, y=labels, validation_data=validation_data)

            # Save artifact
            extension = ".pth" if model_type == "lstm" else ".joblib"
            artifact_file = self.models_dir / f"{model_name}{extension}"
            saved_path = model.save_model(artifact_file)

            # Store in-memory and update reference prediction distribution for drift tracking
            self._loaded_models[model_name] = model

            try:
                ref_probas = model.predict_proba(features)
                self._reference_distributions[model_name] = ref_probas[:, 1].tolist()
            except Exception as e:
                logger.debug("Could not store reference probas for %s: %s", model_name, e)

            # Record in registry
            entry = ModelRegistryEntry(
                model_name=model_name,
                model_type=model_type,
                symbol=symbol,
                timeframe=timeframe,
                version=version,
                artifact_path=str(saved_path),
                metrics=metrics.to_dict(),
                created_at=datetime.utcnow().isoformat(),
                is_active=True,
            )
            self._registry[model_name] = entry
            self._save_registry()

            result = TrainingResult(
                model_name=model_name,
                model_type=model_type,
                symbol=symbol,
                timeframe=timeframe,
                version=version,
                artifact_path=str(saved_path),
                metrics=metrics.to_dict(),
                feature_count=features.shape[1],
                train_samples=len(features),
            )
            logger.info("Successfully trained and registered model: %s", model_name)
            return result

        except Exception as exc:
            logger.error("Failed to train model %s: %s", model_name, exc, exc_info=True)
            return TrainingResult(
                model_name=model_name,
                model_type=model_type,
                symbol=symbol,
                timeframe=timeframe,
                version=version,
                artifact_path="",
                metrics={},
                feature_count=features.shape[1] if isinstance(features, pd.DataFrame) else 0,
                train_samples=len(features),
                status="failed",
                error=str(exc),
            )

    # -------------------------------------------------------------------------
    # Inference
    # -------------------------------------------------------------------------

    def predict(
        self,
        model_name: str,
        features: Union[pd.DataFrame, np.ndarray, pd.Series],
    ) -> PredictionOutput:
        """
        Run inference using the specified model.

        Args:
            model_name: Registered model identifier.
            features: Input feature rows or single row.

        Returns:
            PredictionOutput with direction, probabilities, and confidence score.
        """
        model = self.get_or_load_model(model_name)
        if model is None:
            raise ValueError(f"Model '{model_name}' could not be loaded or not registered.")

        # Handle 1D single-sample series
        if isinstance(features, pd.Series):
            features_input = features.to_frame().T
        elif isinstance(features, np.ndarray) and features.ndim == 1:
            features_input = features.reshape(1, -1)
        else:
            features_input = features

        preds = model.predict(features_input)
        probas = model.predict_proba(features_input)

        # Focus on the latest observation
        latest_pred = int(preds[-1])
        latest_proba = [float(p) for p in probas[-1]]
        confidence = float(np.max(latest_proba))

        # Direction mapping (1 = BUY, 0 = SELL)
        if latest_pred == 1 and confidence >= 0.55:
            direction = "BUY"
        elif latest_pred == 0 and confidence >= 0.55:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        # Log prediction to internal history for drift monitoring
        if model_name not in self._prediction_history:
            self._prediction_history[model_name] = []
        # Store positive class probability
        pos_proba = latest_proba[1] if len(latest_proba) > 1 else latest_proba[0]
        self._prediction_history[model_name].append(pos_proba)

        # Update registry usage count
        if model_name in self._registry:
            self._registry[model_name].prediction_count += 1

        reg_entry = self._registry.get(model_name)
        symbol = reg_entry.symbol if reg_entry else "UNKNOWN"

        output = PredictionOutput(
            model_name=model_name,
            symbol=symbol,
            prediction=latest_pred,
            direction=direction,
            confidence=confidence,
            probabilities=latest_proba,
            metadata={
                "model_type": reg_entry.model_type if reg_entry else "unknown",
                "accuracy": reg_entry.metrics.get("accuracy") if reg_entry else None,
                "advisory_only": True,
            },
        )

        logger.debug(
            "Prediction generated by %s: direction=%s, confidence=%.3f",
            model_name,
            direction,
            confidence,
        )
        return output

    # -------------------------------------------------------------------------
    # Evaluation & Drift Detection
    # -------------------------------------------------------------------------

    def evaluate_model(
        self,
        model_name: str,
        test_features: Union[pd.DataFrame, np.ndarray],
        test_labels: Union[pd.Series, np.ndarray],
    ) -> ModelMetrics:
        """Evaluate an existing model against fresh out-of-sample data."""
        model = self.get_or_load_model(model_name)
        if model is None:
            raise ValueError(f"Model '{model_name}' not found.")

        metrics = model.evaluate(test_features, test_labels)
        logger.info("Evaluation metrics for %s: %s", model_name, metrics.to_dict())
        return metrics

    def detect_drift(
        self,
        model_name: str,
        recent_window: int = 100,
        significance_threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Detect concept/prediction drift using Kolmogorov-Smirnov test between
        baseline training probabilities and recent live inference probabilities.

        Args:
            model_name: Target model name.
            recent_window: Window of most recent predictions to analyze.
            significance_threshold: p-value threshold below which drift is flagged.

        Returns:
            Dict containing drift status, KS statistic, p-value, and recommendations.
        """
        ref_data = self._reference_distributions.get(model_name)
        history = self._prediction_history.get(model_name, [])

        if not ref_data or len(history) < 30:
            return {
                "model_name": model_name,
                "drift_detected": False,
                "status": "insufficient_data",
                "sample_count": len(history),
                "message": "At least 30 predictions required to perform drift analysis.",
            }

        recent_sample = history[-recent_window:]

        # Run 2-sample Kolmogorov-Smirnov test
        ks_stat, p_value = stats.ks_2samp(ref_data, recent_sample)
        drift_flag = bool(p_value < significance_threshold)

        # Update registry entry drift score
        if model_name in self._registry:
            self._registry[model_name].drift_score = float(ks_stat)
            self._save_registry()

        logger.info(
            "Drift check for %s: KS-stat=%.4f, p-value=%.4f, Drift=%s",
            model_name,
            ks_stat,
            p_value,
            drift_flag,
        )

        return {
            "model_name": model_name,
            "drift_detected": drift_flag,
            "ks_statistic": float(ks_stat),
            "p_value": float(p_value),
            "recent_sample_size": len(recent_sample),
            "baseline_sample_size": len(ref_data),
            "recommendation": "Retrain model immediately on fresh market regime"
            if drift_flag
            else "Model distribution remains statistically consistent",
        }

    # -------------------------------------------------------------------------
    # Registry & Storage Helpers
    # -------------------------------------------------------------------------

    def get_or_load_model(self, model_name: str) -> Optional[BaseMLModel]:
        """Retrieve model from memory cache or load from disk artifact."""
        if model_name in self._loaded_models:
            return self._loaded_models[model_name]

        entry = self._registry.get(model_name)
        if not entry:
            logger.warning("Model '%s' is not in registry", model_name)
            return None

        artifact_path = Path(entry.artifact_path)
        if not artifact_path.exists():
            logger.error("Artifact for '%s' does not exist at %s", model_name, artifact_path)
            return None

        try:
            model: BaseMLModel
            if entry.model_type in ("random_forest", "rf"):
                model = RandomForestModel(model_name=model_name)
            elif entry.model_type in ("gradient_boost", "gb"):
                model = GradientBoostModel(model_name=model_name)
            elif entry.model_type == "lstm":
                if not is_pytorch_available():
                    logger.error("Cannot load LSTM: PyTorch is not available.")
                    return None
                model = PyTorchLSTMModel(model_name=model_name)
            else:
                logger.error("Unknown model type: %s", entry.model_type)
                return None

            model.load_model(artifact_path)
            self._loaded_models[model_name] = model
            return model

        except Exception as exc:
            logger.error("Failed to load model '%s': %s", model_name, exc, exc_info=True)
            return None

    def get_active_model_for(self, symbol: str, timeframe: str) -> Optional[str]:
        """Find the latest active model registered for a symbol and timeframe."""
        candidates = [
            e for e in self._registry.values()
            if e.symbol == symbol and e.timeframe == timeframe and e.is_active
        ]
        if not candidates:
            return None

        # Return latest by created_at
        candidates.sort(key=lambda x: x.created_at, reverse=True)
        return candidates[0].model_name

    def list_models(self) -> List[Dict[str, Any]]:
        """Return all models in registry as dictionaries."""
        return [asdict(entry) for entry in self._registry.values()]

    def _load_registry(self) -> None:
        """Load registry from JSON file if present."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._registry[k] = ModelRegistryEntry(**v)
                logger.info("Loaded %d model entries from registry", len(self._registry))
            except Exception as e:
                logger.error("Failed reading registry file %s: %s", self.registry_file, e)

    def _save_registry(self) -> None:
        """Persist registry metadata to JSON file."""
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                serializable = {k: asdict(v) for k, v in self._registry.items()}
                json.dump(serializable, f, indent=2)
        except Exception as e:
            logger.error("Failed saving registry file %s: %s", self.registry_file, e)
