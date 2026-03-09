# FayeTrader

Practice-mode-first proof of concept for a personal AI day-trading app.

## Scope (POC)
- FastAPI backend
- Mock market adapter (replace with Alpaca stream next)
- Paper broker simulation
- Risk gates (position sizing, daily loss limit, rate limit)
- Agent decision loop with rationale logging
- Basic metrics and decision endpoints

## Safety defaults
- `mode=practice` by default
- No live trading adapter in this scaffold
- Every action goes through the risk engine first
- Live-mode broker guardrail defaults to safe paper routing unless explicitly enabled

## Project layout
- `app/main.py`: FastAPI app entrypoint
- `app/api/routes.py`: HTTP endpoints
- `app/services/engine.py`: orchestration loop
- `app/services/risk.py`: risk controls
- `app/services/portfolio.py`: cash/positions/PnL accounting
- `app/brokers/paper.py`: simulated execution
- `app/data/market.py`: market data adapter (mock)
- `app/agents/trading_agent.py`: placeholder strategy policy

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 127.0.0.1 --port 8082 --reload
```

## Adapter config (M6)
Runtime adapter selection is environment-driven with safe defaults:

- `FAYE_MARKET_DATA_ADAPTER=mock|alpaca` (default: `mock`)
- `FAYE_BROKER_ADAPTER=paper|alpaca_paper` (default: `paper`)
- `ALPACA_API_KEY_ID=...`
- `ALPACA_API_SECRET=...`
- `ALPACA_DATA_BASE_URL=https://data.alpaca.markets`
- `ALPACA_TRADING_BASE_URL=https://paper-api.alpaca.markets`
- `FAYE_ALLOW_LIVE_TRADING=false|true` (default: `false`)

Inspect active routing at:
- `GET /api/health`
- `GET /api/adapters`

Canonical local URL for this project:
- `http://localhost:8082/` (redirects to dashboard)
- `http://localhost:8082/api/dashboard`

## Quick API checks
```bash
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/run/AAPL
curl http://127.0.0.1:8000/api/metrics
curl http://127.0.0.1:8000/api/decisions
```

## Next steps
1. Add Alpaca market data adapter (paper keys)
2. Add Alpaca paper execution adapter behind a shared interface
3. Persist decisions/fills in SQLite/Postgres
4. Add websocket stream and dashboard client
5. Add replay/backtest runner
