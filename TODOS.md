# TODOS

## SC Push Worker: Bounded retry for transient failures
**Priority:** Low
**Context:** The background SC push worker (Task 01 of concurrent-squishing-salamander) is fire-and-forget — if the SC API is temporarily down, pushes are silently lost. A bounded retry (e.g., retry once after 30s, then drop) would catch transient failures without adding unbounded complexity. The manual sync button (Task 04/05) serves as the user-facing escape hatch for reconciliation.
**Depends on:** SC push worker (web/backend/sc_push_worker.py) must exist first.
**Added:** 2026-03-17 via /plan-eng-review

## Clean up `affects_global` column in playlist_comparison_history
**Priority:** P3/Low
**Context:** After the global comparison graph migration (graceful-snacking-seahorse), `affects_global` is always `False` for new rows. The column is dead weight — ~2KB for 1,956 booleans. Not causing harm, but misleading for anyone reading the schema. Fix requires SQLite table rebuild (CREATE new table, INSERT ... SELECT, DROP old, ALTER TABLE RENAME) + updating all INSERT statements that reference the column.
**Depends on:** graceful-snacking-seahorse must ship first.
**Effort:** M (human) → S (CC)
**Added:** 2026-03-18 via /plan-ceo-review
