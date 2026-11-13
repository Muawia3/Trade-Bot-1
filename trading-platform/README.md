# 🏦 AI Forex & Gold Trading Platform

A professional-grade algorithmic trading platform for Forex and Gold (XAUUSD) markets, powered by AI/ML signal generation and integrated with MetaTrader 5.

> **⚠ DISCLAIMER:** This software is for educational and research purposes. Trading financial instruments carries significant risk. Past performance does not guarantee future results. Always use paper trading mode first.

---

## 📐 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│                    http://localhost:5173                          │
└──────────────────────┬───────────────────────────────────────────┘
                       │ REST / WebSocket
┌──────────────────────▼───────────────────────────────────────────┐
│                     FastAPI Backend                               │
│                    http://localhost:8000                           │
│  ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────────────┐ │
│  │ Market  │ │ Strategy  │ │  Signal  │ │   Risk Management   │ │
│  │  Data   │ │  Engine   │ │Generator │ │  & Position Sizing  │ │
│  └────┬────┘ └─────┬─────┘ └────┬─────┘ └──────────┬──────────┘ │
│       │            │            │                   │            │
│  ┌────▼────────────▼────────────▼───────────────────▼──────────┐ │
│  │              Execution Engine / Order Manager               │ │
│  └─────────────────────────┬───────────────────────────────────┘ │
│                            │                                     │
│  ┌─────────────────────────▼───────────────────────────────────┐ │
│  │            Paper Trading / Live Execution Switch            │ │
│  └─────────────────────────┬───────────────────────────────────┘ │
└────────────────────────────┼─────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────┐  ┌──────────────┐
│            MT5 Bridge (Windows)               │  │  PostgreSQL  │
│         MetaTrader 5 Terminal API             │  │   Database   │
└───────────────────────────────────────────────┘  └──────────────┘
```

---

## 🛠 Tech Stack

| Layer           | Technology                                       |
| --------------- | ------------------------------------------------ |
| **Backend**     | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic  |
| **Database**    | PostgreSQL 16, Alembic migrations                |
| **Frontend**    | React + TypeScript, Vite, TailwindCSS            |
| **MT5 Bridge**  | MetaTrader5 Python package (Windows native)      |
| **AI/ML**       | scikit-learn, PyTorch (optional)                 |
| **Data**        | pandas, numpy, ta (technical analysis)           |
| **DevOps**      | Docker Compose, GitHub Actions                   |

---

## 📋 Prerequisites

- **Python 3.11+**
- **PostgreSQL 16+** (or use Docker)
- **Node.js 18+** (for frontend)
- **MetaTrader 5** terminal (Windows only, for live/paper trading)
- **Docker & Docker Compose** (optional, for database)

---

## 🚀 Setup

### 1. Clone & Configure

```powershell
cd "e:\Muawia\Trading Bot\trading-platform"
copy .env.example .env
# Edit .env with your database credentials and MT5 settings
```

### 2. Database

**Option A — Docker (recommended):**
```powershell
docker-compose up -d postgres pgadmin
```

**Option B — Local PostgreSQL:**
```sql
CREATE USER trading_user WITH PASSWORD 'trading_pass';
CREATE DATABASE trading_platform OWNER trading_user;
```

### 3. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. MetaTrader 5 (Windows)

```powershell
pip install MetaTrader5
# Set MT5_LOGIN, MT5_PASSWORD, MT5_SERVER in .env
```

### 5. Frontend

```powershell
cd frontend
npm install
npm run dev
```

---

## ⚙ Environment Configuration

See [`.env.example`](.env.example) for all available settings. Key settings:

| Variable               | Description                          | Default     |
| ---------------------- | ------------------------------------ | ----------- |
| `TRADING_MODE`         | `paper`, `live`, or `backtest`       | `paper`     |
| `DEFAULT_RISK_PERCENT` | Risk per trade (% of balance)        | `1.0`       |
| `MAX_DAILY_LOSS_PERCENT` | Maximum daily loss before halt     | `5.0`       |
| `MAX_OPEN_POSITIONS`   | Max simultaneous positions           | `5`         |
| `LIVE_TRADING_ENABLED` | Enable live trading (double safety)  | `false`     |

---

## 🧪 Development Workflow

```powershell
# Run tests
cd backend
pytest -v

# Run with auto-reload
uvicorn main:app --reload

# Create a migration
alembic revision --autogenerate -m "description"
alembic upgrade head

# API docs
# http://localhost:8000/docs   (Swagger UI)
# http://localhost:8000/redoc  (ReDoc)
```

---

## 📁 Project Structure

```
trading-platform/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # REST API endpoints
│   │   ├── core/                # Config, logging, constants
│   │   ├── database/            # DB engine, sessions
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── repositories/        # Data access layer
│   │   ├── services/            # Business logic
│   │   ├── mt5/                 # MT5 integration layer
│   │   ├── market_data/         # Price feeds, OHLCV
│   │   ├── indicators/          # Technical indicators (RSI, MACD, etc.)
│   │   ├── strategies/          # Trading strategies
│   │   ├── signals/             # Signal generation & management
│   │   ├── risk/                # Risk management & position sizing
│   │   ├── execution/           # Order execution engine
│   │   ├── portfolio/           # Portfolio tracking
│   │   ├── backtesting/         # Backtesting engine
│   │   ├── paper_trading/       # Paper trading simulator
│   │   ├── ai/                  # AI/ML models & predictions
│   │   ├── notifications/       # Alerts & notifications
│   │   ├── websocket/           # Real-time WebSocket feeds
│   │   └── utils/               # Shared utilities
│   ├── migrations/              # Alembic migrations
│   ├── tests/                   # Test suite
│   ├── main.py                  # Application entry point
│   ├── requirements.txt         # Python dependencies
│   └── alembic.ini              # Alembic configuration
├── mt5-bridge/
│   ├── connector/               # MT5 terminal connection
│   ├── services/                # MT5 data & order services
│   ├── config/                  # Bridge configuration
│   └── tests/                   # Bridge tests
├── frontend/                    # React frontend (TBD)
├── database/                    # DB scripts & backups
├── infrastructure/              # Docker, deployment, scripts
├── docs/                        # Documentation
├── .env.example                 # Environment template
├── docker-compose.yml           # Docker services
└── README.md                    # This file
```

---

## 🛡 Safety Features

1. **Paper Trading Default** — Platform starts in paper mode; live trading requires explicit opt-in via `LIVE_TRADING_ENABLED=true`.
2. **Max Daily Loss** — Automatically halts trading when daily loss exceeds the configured threshold.
3. **Max Drawdown** — Stops all trading if account drawdown exceeds the configured limit.
4. **Position Limits** — Enforces maximum number of concurrent open positions.
5. **Risk Per Trade** — Each trade risks only a configurable percentage of account balance.
6. **Kill Switch** — Emergency stop to close all positions and cancel pending orders.

---

## 📄 License

Private — All rights reserved.
