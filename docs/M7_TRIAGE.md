# M7 Hardening Triage

Last updated: 2026-03-10

## Resolved Issues
- Performance: the test harness now isolates the global engine per test, pins test adapter selection to `mock`/`paper`, and closes `TestClient`/SQLite resources deterministically, which restores fast and predictable suite execution.
- Deprecations: `datetime.utcnow()` usage has been replaced with timezone-aware UTC helpers across runtime code and tests.

## Implemented Cleanup
- Added shared UTC time helpers and migrated affected runtime/test call sites.
- Added engine reset support with isolated runtime storage for test execution.
- Fixed SQLite connection leaks by explicitly closing connections in store layers.
- Replaced pytest temp-path dependence with explicit temporary directories owned by the test harness.

## M7 Interpretation
- These items were completed as part of launch-readiness hardening.
