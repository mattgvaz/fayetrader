# FayeTrader Build Plan (Living)

Last updated: 2026-03-09
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
Status: `done`
Owner: `codex`

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
Status: `done`
Owner: `unassigned`

Deliverables:
- Event contract for decisions, risk events, orders, fills, metrics.
- SSE or WebSocket stream endpoint and client wiring.
- Live updates in dashboard timeline and key metrics panels.
- Live intraday research monitor surfacing newly ranked trade candidates.
- Real-time catalyst ingestion pipeline (news/chatter/events) with AI-disruption tagging.
- Hot-opportunity notification channel with live webhook dispatch, retries/backoff, and observability metrics.

Acceptance criteria:
- New decisions/fills appear in UI without manual refresh.
- Stream reconnect behavior is handled and visible in UI health state.
- A catalyst event (for example major model launch) appears in intraday monitor with affected symbol set and rationale.
- User receives an immediate alert when opportunity score crosses configured threshold while away from dashboard.

### M3: Strategy Lab + A/B Experiment Harness (Week of 2026-03-23)
Status: `done`
Owner: `unassigned`

Deliverables:
- Strategy interface and registry (pluggable methodologies).
- Experiment runner assigning symbols/time windows to strategy variants.
- Per-strategy attribution for outcomes (PnL, hit rate, drawdown).
- Catalyst-to-sector impact mapper (for example AI model release -> SaaS/infra beneficiary and risk baskets).

Acceptance criteria:
- At least 2 strategy variants run concurrently in paper simulation.
- Results are attributable by strategy ID and variant in metrics/logs.
- Catalyst-driven opportunities are traceable from event -> impacted symbols -> decision outcome.

### M4: Persistence + Replay (Week of 2026-03-30)
Status: `done`
Owner: `unassigned`

Deliverables:
- SQLite persistence for decisions/orders/fills/risk events/metrics snapshots.
- Learning-event persistence for closed-position outcomes and feature context.
- Session model and replay endpoint/view.
- Audit trail for executed/blocked/skipped actions.
- Multi-chat session persistence (create/search/reopen/continue) with conversation history.

Acceptance criteria:
- Full session history can be queried and replayed.
- "Why was this trade blocked/executed?" is answerable from stored records.
- Closed trades are queryable as learning samples for model updates.
- Chat conversations survive restarts and can be searched/reopened by title or content.

### M5: Learning Loop + Strategy Adaptation (Week of 2026-04-06)
Status: `in_progress`
Owner: `unassigned`

Deliverables:
- Define learning sample schema (`trade_id`, `strategy_id`, `features`, `outcome`, `regime`).
- Build post-trade evaluator that scores trade quality and expected-vs-actual performance.
- Build model update job (post-market) to adjust strategy weights/confidence.
- Add guardrails to prevent unstable model jumps (caps, rollback, versioning).
- Architecture decision record (ADR) evaluating single-orchestrator vs multi-agent design, informed by M1-M4 outcomes and OpenClaw-style concepts.

Acceptance criteria:
- Every closed position produces a learning sample.
- Strategy scoring updates are visible, versioned, and attributable to data.
- The agent uses updated strategy scoring on the next session.
- M5 exit gate passed: documented go/no-go decision on adopting multi-agent architecture for post-M5 work, with rationale and migration scope if approved.

### M6: Alpaca Paper Integrations (Week of 2026-04-13)
Status: `in_progress`
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
- Add notification throttles and quiet-hour controls to avoid alert spam/fatigue.

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
1. [done] Create dashboard route/page and shared layout.
2. [done] Build top health/status bar component.
3. [done] Build live decision timeline component (mock feed first).
4. [done] Build positions + PnL summary widgets.
5. [done] Add controls panel for risk and budget inputs.
6. [done] Define event payload schema shared by backend/frontend.
7. [done] Add tests for the current risk engine behavior.
8. [done] Draft learning sample schema and trade outcome scoring spec.
9. [done] Build catalyst event feed schema and mock ingestion adapter focused on AI-disruption events.
10. [done] Add catalyst impact panel linking event -> affected symbols -> thesis in plain language.
11. [done] Add "hot opportunity" notifications with configurable threshold and delivery channel.
12. [done] Add notification center and acknowledge/snooze controls in dashboard.

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
- 2026-03-08: Added runtime-editable risk controls (API + dashboard), workflow-view tabs, and dedicated risk engine tests.
- 2026-03-08: Added versioned engine event contract, event schema endpoint, and stream envelope parsing in dashboard client.
- 2026-03-08: Added learning sample schema and scoring API endpoints for post-trade evaluation scaffolding.
- 2026-03-08: Completed M1 UX foundation with mode-specific workflow panels, intraday equity/PnL chart, and explicit loading/empty/error UI states.
- 2026-03-08: Added post-market performance tracker with date-range filters (week/month/2-week/YTD/custom), timeline chart, and summary insights.
- 2026-03-08: Added intraday live research monitor panel with continuously refreshed target candidates.
- 2026-03-08: Prioritized AI-disruption catalyst detection and unattended hot-opportunity notifications in M2/M3 scope and immediate backlog.
- 2026-03-08: Completed catalyst feed schema + mock adapter and added intraday catalyst impact monitor panel with plain-language impact mapping.
- 2026-03-08: Elevated Agent Chat to cross-cutting UI panel across all workflows with multi-session management APIs; persistent storage scheduled in M4.
- 2026-03-08: Enhanced intraday UX with a plain-language Position Spotlight panel (focus symbol selector, live exposure context, and learner-friendly trade management guidance).
- 2026-03-08: Added intraday session tape, clickable decision inspector with delta/risk explanation, and richer research monitor controls (source filter, sort, severity badges, "why now" context).
- 2026-03-08: Added symbol drilldown modal launched from Position Spotlight and Research rows, including mini price trend, thesis timeline, risk history, and one-click chat prompt shortcuts.
- 2026-03-08: Routed in-app symbol hyperlinks to drilldown modal by default, with explicit "Open in Yahoo Finance" action from drilldown.
- 2026-03-08: Began M2 with real-time typed event streaming (decision/risk/order/fill/metrics/alert/snapshot), live event bus + alert center UI, stream reconnect replay/staleness indicators, configurable hot-opportunity threshold, and SQLite event persistence groundwork.
- 2026-03-08: Added notification-center backend/UI scaffold with channel settings (in-app/webhook/email), alert acknowledgments/snooze actions, and dispatch activity audit feed.
- 2026-03-08: Added M5 architecture gate requiring a documented go/no-go decision on transitioning to multi-agent design after learning-loop validation.
- 2026-03-09: Implemented notification throttles and quiet-hour controls (API + dashboard + suppression logic + tests) to reduce alert fatigue and spam.
- 2026-03-09: Added intraday suppression summary widget showing recent quiet-hour/throttle filtered alerts from dispatch activity.
- 2026-03-09: Added hot-opportunity notification dedupe (same-symbol time-window suppression) with runtime control and dispatch-log visibility.
- 2026-03-09: Upgraded notification delivery with real webhook dispatch (timeout + retry/backoff), added send-test endpoint/button, and exposed 24h notification dispatch/suppression metrics.
- 2026-03-09: Completed M2 acceptance by validating live alerting path beyond in-app feed, including delivery attempts and failure visibility.
- 2026-03-09: Completed M3 scaffold with pluggable strategy registry, experiment assignment buckets, per-strategy attribution metrics endpoint, and decision-log strategy tagging.
- 2026-03-09: Completed M4 with persistent run sessions + replay endpoints, decision audit trail persistence, SQLite-backed chat session/message durability (including content search), and learning-event persistence for closed trades.
- 2026-03-09: Started M5 with persistent versioned strategy model state, guarded post-market update job (sample thresholds + capped deltas), rollback endpoint, and model-version-aware strategy selection.
- 2026-03-09: Started M6 by adding Alpaca market-data and paper-broker adapters, adapter selection via environment config, adapter visibility endpoints, and live-mode safety guardrail defaults.
