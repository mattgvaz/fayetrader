# ADR: M5 Multi-Agent Gate (Draft)

Status: `proposed`
Date: 2026-03-09

## Context
- M1-M4 established a stable single-orchestrator architecture with persistent audit/replay/chat/learning foundations.
- M5 now has versioned strategy scoring, guarded model updates, and rollback support.
- The open decision is whether to switch from single-orchestrator to multi-agent control flow after M5.

## Decision Options
1. Keep single orchestrator as primary runtime architecture through M6.
2. Move to hybrid architecture: deterministic orchestrator plus specialized reasoning agents.
3. Move to fully multi-agent runtime orchestration.

## Current Recommendation
- Choose option 2 (`hybrid`) only after:
  - 2+ weeks of stable M5 update cycles.
  - no critical replay/audit gaps.
  - measured gain in decision quality from agent decomposition in paper mode.

## Consequences
- Positive:
  - keeps risk controls deterministic while allowing selective agent specialization.
  - limits migration risk while preserving extensibility.
- Negative:
  - introduces orchestration complexity.
  - requires strict message contracts and replay coverage.

## Required Morning Decision
- Select one option (1/2/3) as the M5 exit gate result.
