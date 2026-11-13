"""
Optional PyTorch LSTM Neural Network for Sequential Time-Series Market Forecasting.

Provides:
- Temporal sequence / window generator for 3D tensors: (samples, sequence_length, features)
- Recurrent Architecture: LSTM -> Dropout -> Dense -> Sigmoid
- Minibatch training loop with Adam optimizer and Binary Cross-Entropy loss
- Early stopping with best checkpoint restoration
- Graceful fallback if PyTorch is not installed in the environment
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from app.ai.models.base_model import BaseMLModel, ModelMetrics
from app.core.logging_config import get_logger

logger = get_logger("app.ai.models.lstm_model")

# Gracefully test PyTorch availability
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    PYTORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    nn = None     # type: ignore
    TensorDataset = None  # type: ignore
    DataLoader = None     # type: ignore
    PYTORCH_AVAILABLE = False
    logger.info("PyTorch is not installed or available. PyTorchLSTMModel will run in stub/disabled mode.")


def is_pytorch_available() -> bool:
    """Check if PyTorch is available in current environment."""
    return PYTORCH_AVAILABLE


if PYTORCH_AVAILABLE:
    class _LSTMCurrencyNet(nn.Module):
        """
        PyTorch Neural Network architecture:
        Multi-layer LSTM followed by Dropout, Dense projection, and Sigmoid probability.
        """

        def __init__(
            self,
            input_size: int,
            hidden_size: int = 64,
            num_layers: int = 2,
            dropout: float = 0.2,
        ) -> None:
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.dropout = nn.Dropout(dropout)
            self.fc1 = nn.Linear(hidden_size, 32)
            self.relu = nn.ReLU()
            self.fc2 = nn.Linear(32, 1)
            self.sigmoid = nn.Sigmoid()

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x shape: (batch_size, seq_len, input_size)
            out, _ = self.lstm(x)
            # Take representation of the last time step
            last_step = out[:, -1, :]
            dropped = self.dropout(last_step)
            hidden = self.relu(self.fc1(dropped))
            logits = self.fc2(hidden)
            prob = self.sigmoid(logits)
            return prob
else:
    _LSTMCurrencyNet = None  # type: ignore


class PyTorchLSTMModel(BaseMLModel):
    """
    Recurrent Neural Network model using PyTorch LSTM layers.

    Captures sequential temporal dependencies across historical bars.
    Skips operations safely if PyTorch is absent.
    """

    def __init__(
        self,
        model_name: str = "lstm_market_direction",
        sequence_length: int = 20,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        learning_rate: float = 0.001,
        batch_size: int = 64,
        epochs: int = 50,
        patience: int = 7,
        device: Optional[str] = None,
    ) -> None:
        """
        Initialize PyTorch LSTM Model.

        Args:
            model_name: Model identifier.
            sequence_length: Number of past time bars per sequence sample.
            hidden_size: Number of features in LSTM hidden state.
            num_layers: Number of recurrent layers.
            dropout: Dropout probability.
            learning_rate: Adam optimizer learning rate.
            batch_size: Minibatch size.
            epochs: Max training epochs.
            patience: Early stopping patience epochs.
            device: 'cpu', 'cuda', or auto-detected if None.
        """
        super().__init__(model_name=model_name)
        self.sequence_length = sequence_length
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.epochs = epochs
        self.patience = patience

        if PYTORCH_AVAILABLE:
            if device is None:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            else:
                self.device = torch.device(device)
        else:
            self.device = None

        self.net: Optional[_LSTMCurrencyNet] = None

    def create_sequences(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Union[pd.Series, np.ndarray]] = None,
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Transform 2D (samples, features) table into 3D (samples - seq_len, seq_len, features) sequences.

        Args:
            X: Input 2D feature matrix.
            y: Optional 1D target vector.

        Returns:
            Tuple of (X_sequences, y_aligned).
        """
        if isinstance(X, pd.DataFrame):
            X_arr = X.values
        else:
            X_arr = np.asarray(X)

        if len(X_arr) <= self.sequence_length:
            raise ValueError(
                f"Data length ({len(X_arr)}) must be greater than sequence_length ({self.sequence_length})"
            )

        X_seqs = []
        y_seqs = [] if y is not None else None

        if y is not None:
            if isinstance(y, pd.Series):
                y_arr = y.values
            else:
                y_arr = np.asarray(y)

        for i in range(self.sequence_length, len(X_arr)):
            X_seqs.append(X_arr[i - self.sequence_length : i])
            if y is not None:
                y_seqs.append(y_arr[i])

        X_out = np.array(X_seqs, dtype=np.float32)
        y_out = np.array(y_seqs, dtype=np.float32) if y is not None else None

        return X_out, y_out

    def train(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        validation_data: Optional[Tuple[Union[pd.DataFrame, np.ndarray], Union[pd.Series, np.ndarray]]] = None,
        **kwargs: Any,
    ) -> ModelMetrics:
        """
        Train LSTM using Adam optimizer with Early Stopping.

        Args:
            X: 2D or 3D feature array.
            y: Binary target vector (0 or 1).
            validation_data: Optional validation data (X_val, y_val).
            **kwargs: Extra parameters.

        Returns:
            ModelMetrics object.
        """
        if not PYTORCH_AVAILABLE:
            logger.warning("PyTorch unavailable. Returning mock/stub metrics for LSTM.")
            self.metrics = ModelMetrics(accuracy=0.5, f1_score=0.5, samples_count=len(y))
            return self.metrics

        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)

        # Convert to 3D sequences if 2D
        X_arr = np.asarray(X)
        if X_arr.ndim == 2:
            X_train_seq, y_train_seq = self.create_sequences(X_arr, y)
        else:
            X_train_seq = X_arr
            y_train_seq = np.asarray(y, dtype=np.float32)

        input_size = X_train_seq.shape[2]

        # Validation sequence setup
        X_val_seq, y_val_seq = None, None
        if validation_data is not None:
            X_v, y_v = validation_data
            X_v_arr = np.asarray(X_v)
            if X_v_arr.ndim == 2:
                X_val_seq, y_val_seq = self.create_sequences(X_v_arr, y_v)
            else:
                X_val_seq = X_v_arr
                y_val_seq = np.asarray(y_v, dtype=np.float32)

        # Initialize network
        self.net = _LSTMCurrencyNet(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            dropout=self.dropout,
        ).to(self.device)

        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(self.net.parameters(), lr=self.learning_rate)

        train_dataset = TensorDataset(
            torch.from_numpy(X_train_seq).float(),
            torch.from_numpy(y_train_seq).float().unsqueeze(1),
        )
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True)

        logger.info(
            "Starting LSTM training on device %s: %d sequences of length %d, features: %d",
            self.device,
            len(X_train_seq),
            self.sequence_length,
            input_size,
        )

        best_loss = float("inf")
        best_state_dict = None
        epochs_without_improvement = 0

        for epoch in range(1, self.epochs + 1):
            self.net.train()
            running_loss = 0.0

            for batch_x, batch_y in train_loader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                outputs = self.net(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                running_loss += loss.item() * batch_x.size(0)

            epoch_loss = running_loss / len(train_dataset)

            # Evaluate on validation or train loss for early stopping
            current_eval_loss = epoch_loss
            if X_val_seq is not None and y_val_seq is not None:
                self.net.eval()
                with torch.no_grad():
                    val_t_x = torch.from_numpy(np.ascontiguousarray(X_val_seq)).float().to(self.device)
                    val_t_y = torch.from_numpy(y_val_seq).float().unsqueeze(1).to(self.device)
                    val_preds = self.net(val_t_x)
                    val_loss = criterion(val_preds, val_t_y).item()
                    current_eval_loss = val_loss

            if current_eval_loss < best_loss:
                best_loss = current_eval_loss
                best_state_dict = self.net.state_dict().copy()
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= self.patience:
                    logger.info("Early stopping triggered at epoch %d (patience %d)", epoch, self.patience)
                    break

        if best_state_dict is not None:
            self.net.load_state_dict(best_state_dict)

        self.is_trained = True
        self.trained_at = datetime.utcnow()

        # Evaluate metrics
        if X_val_seq is not None and y_val_seq is not None:
            self.metrics = self.evaluate(X_val_seq, y_val_seq)
        else:
            self.metrics = self.evaluate(X_train_seq, y_train_seq)

        logger.info("LSTM training completed. Accuracy: %.4f, F1: %.4f", self.metrics.accuracy, self.metrics.f1_score)
        return self.metrics

    def predict(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict binary directional movement (1=UP, 0=DOWN)."""
        probas = self.predict_proba(X)
        return (probas[:, 1] >= 0.5).astype(int)

    def predict_proba(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        """Predict class probability distribution [[P(down), P(up)]]."""
        self._ensure_trained()
        if not PYTORCH_AVAILABLE or self.net is None:
            raise RuntimeError("PyTorch is not available for inference.")

        X_arr = np.asarray(X)
        if X_arr.ndim == 2:
            # If 2D, create sequences. If only single window provided:
            if len(X_arr) == self.sequence_length:
                X_seq = X_arr.reshape(1, self.sequence_length, -1)
            else:
                X_seq, _ = self.create_sequences(X_arr)
        else:
            X_seq = X_arr

        self.net.eval()
        with torch.no_grad():
            tensor_x = torch.from_numpy(np.ascontiguousarray(X_seq)).float().to(self.device)
            p_up = self.net(tensor_x).cpu().numpy().ravel()
            p_down = 1.0 - p_up
            return np.column_stack([p_down, p_up])

    def evaluate(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
    ) -> ModelMetrics:
        """Evaluate accuracy, precision, recall, and F1 score."""
        self._ensure_trained()
        X_arr = np.asarray(X)
        y_arr = np.asarray(y).ravel()

        if X_arr.ndim == 2 and len(X_arr) != len(y_arr):
            X_arr, y_arr = self.create_sequences(X_arr, y_arr)

        preds = self.predict(X_arr)
        acc = float(accuracy_score(y_arr, preds))
        prec = float(precision_score(y_arr, preds, average="weighted", zero_division=0))
        rec = float(recall_score(y_arr, preds, average="weighted", zero_division=0))
        f1 = float(f1_score(y_arr, preds, average="weighted", zero_division=0))

        return ModelMetrics(
            accuracy=acc,
            precision=prec,
            recall=rec,
            f1_score=f1,
            samples_count=len(y_arr),
        )

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Approximate feature importance via first-layer LSTM input weight magnitude.

        Returns:
            Dictionary mapping feature names to normalized weight sum.
        """
        self._ensure_trained()
        if not PYTORCH_AVAILABLE or self.net is None:
            return {}

        with torch.no_grad():
            # weight_ih_l0 shape: (4 * hidden_size, input_size)
            weights = self.net.lstm.weight_ih_l0.abs().cpu().numpy()
            feature_weights = np.sum(weights, axis=0)
            total = np.sum(feature_weights) + 1e-9
            normalized = feature_weights / total

        names = self.feature_names or [f"feat_{i}" for i in range(len(normalized))]
        return {
            name: float(val)
            for name, val in sorted(zip(names, normalized), key=lambda x: x[1], reverse=True)
        }

    def save_model(self, path: Union[str, Path]) -> str:
        """Save PyTorch weights and architecture parameters."""
        self._ensure_trained()
        if not PYTORCH_AVAILABLE or self.net is None:
            raise RuntimeError("Cannot save model: PyTorch not available.")

        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            "model_name": self.model_name,
            "state_dict": self.net.state_dict(),
            "feature_names": self.feature_names,
            "sequence_length": self.sequence_length,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }

        torch.save(checkpoint, str(target_path))
        logger.info("Saved PyTorch LSTM checkpoint to %s", target_path)
        return str(target_path)

    def load_model(self, path: Union[str, Path]) -> None:
        """Load PyTorch weights and reconstruct network."""
        if not PYTORCH_AVAILABLE:
            raise RuntimeError("Cannot load model: PyTorch is not available.")

        src_path = Path(path)
        if not src_path.exists():
            raise FileNotFoundError(f"Model file not found at {src_path}")

        checkpoint = torch.load(str(src_path), map_location=self.device)
        self.model_name = checkpoint["model_name"]
        self.feature_names = checkpoint["feature_names"]
        self.sequence_length = checkpoint["sequence_length"]
        self.hidden_size = checkpoint["hidden_size"]
        self.num_layers = checkpoint["num_layers"]
        self.dropout = checkpoint["dropout"]

        input_size = len(self.feature_names) if self.feature_names else 10
        self.net = _LSTMCurrencyNet(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            dropout=self.dropout,
        ).to(self.device)

        self.net.load_state_dict(checkpoint["state_dict"])
        self.trained_at = (
            datetime.fromisoformat(checkpoint["trained_at"])
            if checkpoint.get("trained_at")
            else None
        )
        if checkpoint.get("metrics"):
            self.metrics = ModelMetrics(**checkpoint["metrics"])

        self.is_trained = True
        logger.info("Loaded PyTorch LSTM checkpoint from %s", src_path)

    def _ensure_trained(self) -> None:
        if not self.is_trained:
            raise RuntimeError(f"LSTM Model '{self.model_name}' has not been trained yet.")
