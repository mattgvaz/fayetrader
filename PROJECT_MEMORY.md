# FayeTrader Project Memory (Charter)

Last updated: 2026-03-10

## Vision
Build an app where the user supervises an AI day-trading agent that researches off-hours and trades autonomously during market hours, starting in paper/practice mode.

## Product Charter
- User role: portfolio manager and risk owner.
- Agent role: autonomous trader that proposes and executes strategies within strict constraints.
- Safety baseline: practice mode first; no live trading path until paper performance and controls are proven.

## Core Outcomes
1. Autonomous intraday trading loop with auditable decisions.
2. Research-to-execution workflow (off-hours research, market-hours execution, post-market review).
3. Strategy experimentation via A/B testing of methodologies in paper trading.
4. Trade feedback loop that learns from every closed position.
5. Strong risk controls configurable by the user.
6. Clear UX for oversight, intervention, and explanation.
7. Real-time catalyst capture for volatility events (especially AI disruption) with fast opportunity ranking.
8. Immediate user notifications for high-priority opportunities when user is away from the dashboard.

## Required User Controls
- Daily trading budget limit.
- Max daily loss limit.
- Position sizing and order rate limits.
- Optional market bias/direction instructions.
- Pause/resume and kill switch.
- Notification thresholds and channel preferences for urgent opportunity alerts.
- Alert quiet-hours and rate-limit controls.

## Strategy Principles
- Use proven day-trading methodologies as pluggable strategies.
- Track each strategy with explicit metadata (signal type, assumptions, regime fit).
- Evaluate strategies by risk-adjusted metrics, not only raw return.
- Keep strategy logic explainable per trade.
- Learn from realized outcomes and adapt strategy weights over time.
- Explicitly model catalyst-driven setups (news/event shocks) and map them to likely impacted symbols/sectors.

## Learning Feedback Loop
- Every closed trade must emit a learning event with context and outcome.
- Learning features should include setup conditions, market regime, execution quality, and risk context.
- A learning model updates strategy confidence/weights on a controlled cadence (for example daily post-market).
- Learning updates must be versioned, auditable, and reversible.
- A/B experiment results should feed the same learning pipeline.

## Non-Negotiables
- All execution requests must pass risk gating first.
- Every decision path (executed, blocked, skipped) is persisted.
- Every trade has rationale, confidence, and strategy attribution.
- Every closed trade contributes to a measurable learning dataset.
- Paper trading validation is required before any live execution support.

## UX Principles
- Operator-first dashboard for pre-market, intraday, and post-market workflows.
- Real-time visibility into positions, PnL, decisions, and risk events.
- "Why this trade?" must be easy to answer from the UI.
- Session replay should support debugging and trust-building.
- If the user is not actively watching, urgent opportunities must still reach them via notifications.
- Agent chat is a cross-cutting surface across workflows and should support multi-session continuity.

## Definition of POC Done
- End-to-end loop works: signal -> risk gate -> order -> fill -> persist -> visualize.
- Strategy A/B testing works in paper mode.
- Trade feedback loop works: close -> evaluate -> learn -> update strategy scoring.
- Controls and safeguards are enforced and tested.
- A user can monitor and audit a full trading session from the app.

## Working Agreements
- This file and `docs/BUILD_PLAN.md` are the source of truth.
- Update both files when scope or priorities change.
- Prefer small iterative milestones with explicit acceptance criteria.

## Current Program State
- M7 hardening and launch-readiness work is complete for practice/paper mode.
- Timestamp handling is timezone-aware in the current codebase, and the test harness now isolates runtime state with clean resource shutdown.
