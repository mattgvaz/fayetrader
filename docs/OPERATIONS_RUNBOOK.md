# FayeTrader M7 Operations Runbook

Last updated: 2026-03-10

## Daily Startup
- Confirm required env vars are set: `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET`, `FAYE_MARKET_DATA_ADAPTER`, `FAYE_BROKER_ADAPTER`.
- Verify safe defaults before market open: `mode=practice`, `FAYE_BROKER_ADAPTER=alpaca_paper`, `FAYE_ALLOW_LIVE_TRADING` unset or `false`.
- Run `pytest -q` from repo root and confirm the suite passes.
- Start the API with `uvicorn app.main:app --host 127.0.0.1 --port 8082`.
- Check `GET /api/health` and confirm `status=ok`, `mode=practice`, and the expected adapter labels.

## Dry-Run Launch Checklist
- Paper trading credentials are present and current.
- Health endpoint returns `200 OK`.
- Dashboard loads and reflects the expected adapter selection.
- Risk controls are set before session open: budget, max loss, position size, order-rate limits.
- Notification configuration is reviewed to avoid alert spam.
- No open critical bugs remain in the current scope.

## Incident Handling
- Symptom: Alpaca market data or order request fails intermittently.
- Action: keep the session in practice mode; the adapters retry automatically and then degrade to deterministic fallback behavior if retries are exhausted.
- Action: inspect recent logs and the health endpoint to confirm the service itself is still healthy.
- Action: if failures persist, pause new trading activity and restart the API process.

## Scope Freeze Rules
- No new features during launch-readiness validation.
- Only ship bug fixes, test coverage, and operational documentation updates.
- Any live-trading capability remains blocked unless explicitly enabled and separately reviewed.
