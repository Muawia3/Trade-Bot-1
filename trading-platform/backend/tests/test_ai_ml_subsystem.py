"""
Unit and integration test suite for the AI/ML subsystem and Economic News module.
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
try:
    import pytest
except ImportError:
    pytest = None  # type: ignore

from app.ai.feature_engineering import FeatureEngineer
from app.ai.models.base_model import ModelMetrics
from app.ai.models.random_forest import RandomForestModel
from app.ai.models.gradient_boost import GradientBoostModel
from app.ai.models.lstm_model import PyTorchLSTMModel, is_pytorch_available
from app.ai.model_manager import ModelManager
from app.ai.prediction_service import PredictionService
from app.ai.sentiment import MockSentimentAnalyzer, ExternalAPISentimentAnalyzer
from app.services.news_provider import EconomicEvent, EventImpact, MockNewsProvider
from app.services.news_service import NewsService
from app.ai.agents.base_agent import AgentRecommendation
from app.ai.agents.market_analysis_agent import MarketAnalysisAgent, MarketRegime
from app.ai.agents.technical_agent import TechnicalAgent
from app.ai.agents.risk_agent import RiskAgent
from app.ai.agents.agent_coordinator import AgentCoordinator


def generate_synthetic_ohlcv(bars: int = 150) -> pd.DataFrame:
    """Helper to generate realistic synthetic OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=bars, freq="15min")
    base_price = 2000.0
    returns = np.random.normal(0.0001, 0.001, bars)
    prices = base_price * np.exp(np.cumsum(returns))

    highs = prices * (1 + np.abs(np.random.normal(0, 0.0008, bars)))
    lows = prices * (1 - np.abs(np.random.normal(0, 0.0008, bars)))
    opens = prices * (1 + np.random.normal(0, 0.0004, bars))
    volumes = np.random.randint(50, 500, bars).astype(float)

    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": prices,
            "volume": volumes,
        },
        index=dates,
    )
    return df


def test_feature_engineering():
    """Verify feature extraction, technical indicators, and normalization."""
    df = generate_synthetic_ohlcv(100)
    fe = FeatureEngineer()

    features = fe.extract_features(df, include_labels=True)
    assert not features.empty
    assert "return_1" in features.columns
    assert "log_return_1" in features.columns
    assert "rsi_14" in features.columns
    assert "macd_hist" in features.columns
    assert "bb_position" in features.columns
    assert "atr_14" in features.columns
    assert "garman_klass_vol" in features.columns
    assert "hour_sin" in features.columns
    assert "target_direction" in features.columns

    # Test normalization
    scaled = fe.normalize_features(features, fit=True)
    assert scaled.shape == features.shape
    assert fe.is_fitted
    feature_names = fe.get_feature_names()
    assert len(feature_names) > 0
    assert "target_direction" not in feature_names


def test_random_forest_model():
    """Verify RandomForestModel training, CV, prediction, importance, and serialization."""
    df = generate_synthetic_ohlcv(120)
    fe = FeatureEngineer()
    features = fe.extract_features(df, include_labels=True)

    X = features.drop(columns=["target_direction", "target_return"])
    y = features["target_direction"]

    rf = RandomForestModel(model_name="rf_test", n_estimators=20, max_depth=4)
    metrics = rf.train(X, y)

    assert isinstance(metrics, ModelMetrics)
    assert metrics.accuracy >= 0.0
    assert metrics.samples_count == len(X)

    # Predictions
    preds = rf.predict(X)
    assert len(preds) == len(X)
    assert set(preds).issubset({0, 1})

    probas = rf.predict_proba(X)
    assert probas.shape == (len(X), 2)

    # Feature importance
    importances = rf.get_feature_importance()
    assert len(importances) == X.shape[1]
    assert abs(sum(importances.values()) - 1.0) < 1e-4

    # Cross validation
    cv_res = rf.cross_validate(X, y, n_splits=3)
    assert "cv_accuracy_mean" in cv_res

    # Serialization test
    temp_dir = tempfile.mkdtemp()
    try:
        model_file = os.path.join(temp_dir, "rf_test.joblib")
        rf.save_model(model_file)
        assert os.path.exists(model_file)

        rf2 = RandomForestModel(model_name="rf_test_loaded")
        rf2.load_model(model_file)
        preds2 = rf2.predict(X)
        np.testing.assert_array_equal(preds, preds2)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_gradient_boost_model():
    """Verify GradientBoostModel with feature selection and interpretation."""
    df = generate_synthetic_ohlcv(120)
    fe = FeatureEngineer()
    features = fe.extract_features(df, include_labels=True)

    X = features.drop(columns=["target_direction", "target_return"])
    y = features["target_direction"]

    gb = GradientBoostModel(model_name="gb_test", n_estimators=20, max_depth=3)
    metrics = gb.train(X, y, perform_feature_selection=True, max_features_to_select=10)

    assert metrics.samples_count == len(X)
    assert gb.selected_features is not None
    assert len(gb.selected_features) <= 10

    # Interpretation
    interpretation = gb.interpret_prediction(X.iloc[-1])
    assert "direction" in interpretation
    assert "confidence" in interpretation
    assert len(interpretation["key_factors"]) > 0


def test_lstm_model():
    """Verify PyTorchLSTMModel handles sequence generation, training or graceful fallback."""
    df = generate_synthetic_ohlcv(80)
    fe = FeatureEngineer()
    features = fe.extract_features(df, include_labels=True)

    X = features.drop(columns=["target_direction", "target_return"]).values
    y = features["target_direction"].values

    lstm = PyTorchLSTMModel(model_name="lstm_test", sequence_length=10, hidden_size=16, epochs=2)
    X_seq, y_seq = lstm.create_sequences(X, y)
    assert X_seq.shape == (len(X) - 10, 10, X.shape[1])
    assert len(y_seq) == len(X) - 10

    if is_pytorch_available():
        metrics = lstm.train(X, y)
        assert metrics.samples_count > 0
        preds = lstm.predict(X[-10:])
        assert len(preds) > 0


def test_model_manager():
    """Verify ModelManager lifecycle, training, inference routing, and drift detection."""
    temp_dir = tempfile.mkdtemp()
    try:
        manager = ModelManager(models_dir=temp_dir)
        df = generate_synthetic_ohlcv(120)
        fe = FeatureEngineer()
        features = fe.extract_features(df, include_labels=True)

        X = features.drop(columns=["target_direction", "target_return"])
        y = features["target_direction"]

        train_res = manager.train_model(
            model_type="random_forest",
            symbol="XAUUSD",
            timeframe="M15",
            features=X,
            labels=y,
            hyperparams={"n_estimators": 15, "max_depth": 3},
        )
        assert train_res.status == "success"
        assert os.path.exists(train_res.artifact_path)

        # Active model query
        active_model = manager.get_active_model_for("XAUUSD", "M15")
        assert active_model == train_res.model_name

        # Inference
        pred_out = manager.predict(active_model, X.iloc[[-1]])
        assert pred_out.symbol == "XAUUSD"
        assert pred_out.direction in ("BUY", "SELL", "NEUTRAL")
        assert 0.0 <= pred_out.confidence <= 1.0

        # Drift detection stub check
        drift_report = manager.detect_drift(active_model)
        assert "drift_detected" in drift_report
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_prediction_service_and_signal_merging():
    """Verify PredictionService merges AI advisory with strategy signals without overriding risk."""
    temp_dir = tempfile.mkdtemp()
    try:
        manager = ModelManager(models_dir=temp_dir)
        service = PredictionService(model_manager=manager)

        # 1. Standalone test when AI prediction is None
        merged_standalone = service.merge_with_strategy_signal("EURUSD", "buy", None)
        assert merged_standalone.final_action == "BUY"
        assert merged_standalone.alignment == "STANDALONE"

        # 2. Strategy HOLD: AI must NEVER force trade
        from app.ai.prediction_service import AIPrediction
        mock_ai = AIPrediction(
            symbol="EURUSD",
            timeframe="H1",
            direction="BUY",
            confidence=0.90,
            probabilities={"up": 0.90, "down": 0.10},
            model_name="mock_rf",
            model_type="rf",
            reasoning=["Strong uptrend"],
        )
        merged_hold = service.merge_with_strategy_signal("EURUSD", "hold", mock_ai)
        assert merged_hold.final_action == "HOLD"

        # 3. Confirmation test: Strategy BUY and AI BUY
        merged_buy_confirmed = service.merge_with_strategy_signal("EURUSD", "buy", mock_ai)
        assert merged_buy_confirmed.final_action == "BUY"
        assert merged_buy_confirmed.alignment == "CONFIRMED"

        # 4. Contradiction test: Strategy BUY and AI SELL
        mock_ai_sell = AIPrediction(
            symbol="EURUSD",
            timeframe="H1",
            direction="SELL",
            confidence=0.85,
            probabilities={"up": 0.15, "down": 0.85},
            model_name="mock_rf",
            model_type="rf",
            reasoning=["Bearish reversal"],
        )
        merged_contradicted = service.merge_with_strategy_signal("EURUSD", "buy", mock_ai_sell)
        assert merged_contradicted.final_action == "HOLD"
        assert merged_contradicted.alignment == "CONTRADICTED"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_sentiment_analyzers():
    """Verify MockSentimentAnalyzer and fallback API analyzer."""
    analyzer = MockSentimentAnalyzer()
    res_pos = analyzer.analyze_text("US Dollar surges to record high amid hawkish Federal Reserve rate hike")
    assert res_pos.label == "BULLISH"
    assert res_pos.score > 0

    res_neg = analyzer.analyze_text("Stock market plunges into crash as recession fear sparks massive selloff")
    assert res_neg.label == "BEARISH"
    assert res_neg.score < 0

    ext_analyzer = ExternalAPISentimentAnalyzer(api_key=None)
    res_fallback = ext_analyzer.analyze_text("Economic growth steady")
    assert res_fallback.confidence >= 0.5


def test_news_service_and_blackout_windows():
    """Verify NewsService detects upcoming tier-1 releases and restricts trading."""
    mock_provider = MockNewsProvider(simulate_upcoming_high_impact=True, minutes_offset=10)
    news_service = NewsService(provider=mock_provider, pre_event_buffer_minutes=30)

    # Check high impact upcoming
    assert news_service.is_high_impact_upcoming("XAUUSD", minutes_before=30) is True

    # Check trading restriction triggered
    restricted, reason = news_service.should_restrict_trading("XAUUSD")
    assert restricted is True
    assert "US Consumer Price Index" in reason or "High-impact release" in reason

    # Test symbol currency extraction
    currs = news_service.get_currencies_for_symbol("EURUSD")
    assert currs == ["EUR", "USD"]
    currs_gold = news_service.get_currencies_for_symbol("XAUUSD")
    assert currs_gold == ["USD"]


def test_multi_agent_risk_veto():
    """Verify RiskAgent exercises absolute veto authority in AgentCoordinator."""
    df = generate_synthetic_ohlcv(50)

    # 1. Normal safe context
    safe_context = {
        "symbol": "EURUSD",
        "daily_loss_pct": 1.0,
        "open_positions_count": 2,
        "current_spread_pips": 1.2,
        "proposed_trade": {
            "side": "buy",
            "entry_price": 1.0800,
            "stop_loss": 1.0770,  # 30 pips risk
            "take_profit": 1.0860, # 60 pips reward -> 2.0 R:R
        },
    }

    mock_news_safe = MockNewsProvider(simulate_upcoming_high_impact=False)
    risk_agent_safe = RiskAgent(news_service=NewsService(provider=mock_news_safe))
    coordinator_safe = AgentCoordinator(risk_agent=risk_agent_safe)

    decision_safe = coordinator_safe.coordinate(df, safe_context)
    assert not decision_safe.vetoed_by_risk

    # 2. Dangerous context: Daily drawdown exceeded
    risk_agent_drawdown = RiskAgent(max_daily_loss_pct=3.0)
    coordinator_veto = AgentCoordinator(risk_agent=risk_agent_drawdown)
    veto_context = {
        "symbol": "EURUSD",
        "daily_loss_pct": 3.5,  # Exceeds max daily loss!
        "open_positions_count": 1,
    }
    decision_vetoed = coordinator_veto.coordinate(df, veto_context)
    assert decision_vetoed.vetoed_by_risk is True
    assert decision_vetoed.action == "VETO"
    assert decision_vetoed.is_approved is False
    assert "Daily drawdown limit REACHED" in (decision_vetoed.veto_reason or "")

    # 3. News blackout veto
    mock_news_danger = MockNewsProvider(simulate_upcoming_high_impact=True, minutes_offset=10)
    risk_agent_news = RiskAgent(news_service=NewsService(provider=mock_news_danger))
    coordinator_news_veto = AgentCoordinator(risk_agent=risk_agent_news)
    decision_news_veto = coordinator_news_veto.coordinate(df, {"symbol": "XAUUSD"})
    assert decision_news_veto.vetoed_by_risk is True
    assert "Macroeconomic News Blackout" in (decision_news_veto.veto_reason or "")
