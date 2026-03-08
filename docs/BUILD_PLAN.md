# FayeTrader Build Plan (Living)

Last updated: 2026-03-07
Target POC launch: 2026-04-17 (tentative)
Status legend: `not_started` | `in_progress` | `blocked` | `done`

## 1) Goals and Scope
- Build a practice-first autonomous day-trading agent platform.
- Front-load UX/UI so product decisions are visible early.
- Support pluggable strategy methodologies with paper-trading A/B testing.
- Implement a per-trade feedback loop that updates strategy scoring from realized outcomes.
- Enforce user-defined risk and budget constraints at all times.

## 2) Milestones

### M1: UX/UI Foundation (Week of 2026-03-09)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- Operator dashboard shell (desktop + mobile responsive).
- Views for pre-market, intraday, and post-market workflows.
- Components: health bar, positions table, PnL/equity chart, decision timeline, controls panel.
- Mock data wiring for all major UI states (normal, loading, empty, error).

Acceptance criteria:
- User can inspect account state and latest agent decisions from one screen.
- User can set daily budget/loss controls via UI forms (local state is fine in M1).
- UI is usable on laptop and phone widths.

### M2: Real-Time Event Model + Backend/UI Wiring (Week of 2026-03-16)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- Event contract for decisions, risk events, orders, fills, metrics.
- SSE or WebSocket stream endpoint and client wiring.
- Live updates in dashboard timeline and key metrics panels.

Acceptance criteria:
- New decisions/fills appear in UI without manual refresh.
- Stream reconnect behavior is handled and visible in UI health state.

### M3: Strategy Lab + A/B Experiment Harness (Week of 2026-03-23)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- Strategy interface and registry (pluggable methodologies).
- Experiment runner assigning symbols/time windows to strategy variants.
- Per-strategy attribution for outcomes (PnL, hit rate, drawdown).

Acceptance criteria:
- At least 2 strategy variants run concurrently in paper simulation.
- Results are attributable by strategy ID and variant in metrics/logs.

### M4: Persistence + Replay (Week of 2026-03-30)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- SQLite persistence for decisions/orders/fills/risk events/metrics snapshots.
- Learning-event persistence for closed-position outcomes and feature context.
- Session model and replay endpoint/view.
- Audit trail for executed/blocked/skipped actions.

Acceptance criteria:
- Full session history can be queried and replayed.
- "Why was this trade blocked/executed?" is answerable from stored records.
- Closed trades are queryable as learning samples for model updates.

### M5: Learning Loop + Strategy Adaptation (Week of 2026-04-06)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- Define learning sample schema (`trade_id`, `strategy_id`, `features`, `outcome`, `regime`).
- Build post-trade evaluator that scores trade quality and expected-vs-actual performance.
- Build model update job (post-market) to adjust strategy weights/confidence.
- Add guardrails to prevent unstable model jumps (caps, rollback, versioning).

Acceptance criteria:
- Every closed position produces a learning sample.
- Strategy scoring updates are visible, versioned, and attributable to data.
- The agent uses updated strategy scoring on the next session.

### M6: Alpaca Paper Integrations (Week of 2026-04-13)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- Alpaca market data adapter behind existing market interface.
- Alpaca paper execution adapter behind broker interface.
- Environment-based adapter selection with safe defaults.

Acceptance criteria:
- Agent can run end-to-end against Alpaca paper endpoints.
- Practice-mode guardrails prevent accidental live routing.

### M7: Hardening + Launch Readiness (Week of 2026-04-20)
Status: `not_started`
Owner: `unassigned`

Deliverables:
- Soak tests and failure-mode tests (disconnects, retries, API errors).
- Runbook/checklist for daily operation and incident handling.
- Final bug triage and scope freeze.

Acceptance criteria:
- Stable paper sessions complete without critical failures.
- Launch checklist passes in a dry run.

## 3) Cross-Cutting Workstreams

### Risk and Safety
- Expand risk engine tests (position size, daily loss, rate limits, cash checks).
- Add circuit-breaker style kill switch behavior.
- Expose risk state/events clearly in UI.

### Explainability and Auditability
- Standardize rationale schema (`strategy_id`, `confidence`, `reason`, `features`).
- Ensure all decision paths are captured consistently.
- Track model versions and the rationale for each strategy score update.

### Learning and Evaluation
- Define trade outcome labels and reward function.
- Add drift checks and minimum sample thresholds before applying updates.
- Compare adapted strategy performance against control baseline.

### DevEx and Quality
- Add lint/format/test tasks and CI checks.
- Add fixtures and deterministic simulation utilities for tests.

## 4) Immediate Next Sprint Backlog
1. Create dashboard route/page and shared layout.
2. Build top health/status bar component.
3. Build live decision timeline component (mock feed first).
4. Build positions + PnL summary widgets.
5. Add controls panel for risk and budget inputs.
6. Define event payload schema shared by backend/frontend.
7. Add tests for the current risk engine behavior.
8. Draft learning sample schema and trade outcome scoring spec.

## 5) Risks and Mitigations
- Risk: Strategy quality overfitting in paper.
  - Mitigation: regime labeling, out-of-sample replay, risk-adjusted comparisons.
- Risk: Data/execution adapter instability.
  - Mitigation: adapter abstraction, fallback mock mode, robust reconnect logic.
- Risk: UX complexity grows too fast.
  - Mitigation: single operator workflow first, defer advanced features.

## 6) Change Log
- 2026-03-07: Initial living plan created with UX-first sequencing and strategy lab scope.
- 2026-03-07: Added explicit per-trade learning feedback loop milestone and requirements.
