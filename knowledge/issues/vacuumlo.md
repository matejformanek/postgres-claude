# Issues — `contrib/vacuumlo`

Per-subsystem issue register for **vacuumlo**, the libpq frontend
CLI that removes orphaned large objects. Created 2026-06-11 by A21
sweep.

**Parent doc:** `knowledge/files/contrib/vacuumlo/vacuumlo.c.md`

## Headlines

1. **TOCTOU race with concurrent `lo_create` + reference INSERT.**
   The temp table `vacuum_l` is populated under one snapshot; the
   per-column DELETE FROM vacuum_l scans live tables in subsequent
   queries. An LO created between vacuum_l population and the
   reference INSERT's commit will be unlinked. Acknowledged in the
   README ("run when no one is writing LOs"); not enforced by the
   tool.

2. **Long-running wrapping transaction** holds resources across
   many user-table scans + a `WITH HOLD` cursor + periodic commits.
   Autovacuum can block on it on a hot cluster.

3. **Loose numeric parsing** of `-l` (transaction_limit) and `-p`
   (port) accepts `"100abc"` as `100`. Matches sister utilities but
   worth flagging.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:184-262 | correctness | likely | TOCTOU between vacuum_l population and per-column DELETE on concurrent lo_create | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:269-272 | style | nit | Long-running wrapping txn with no progress beyond `-v` | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:333-342 | correctness | nit | Cascading error message on lo_unlink failure inside aborted txn | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:496-499 | style | nit | strtol accepts trailing garbage for -l | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:505-507 | style | nit | Loose port parse; "5432foo" becomes 5432 | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:194-202 | correctness | maybe | Assumes every user-table `oid`-typed column references an LO | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |
| 2026-06-11 | contrib/vacuumlo/vacuumlo.c:139-147 | security | nit | ALWAYS_SECURE_SEARCH_PATH_SQL applied after BEGIN; tiny ordering window | open | knowledge/files/contrib/vacuumlo/vacuumlo.c.md §Potential issues |

## Notes

The TOCTOU issue is the only one with real-world data-loss
potential. The mitigation in the wild is "do not run vacuumlo on a
hot cluster" — but the tool has no advisory-lock or
snapshot-coordination mechanism to make that safer. A `--strict`
mode that takes an AccessExclusiveLock on pg_largeobject_metadata
during scan could close the window at the cost of blocking
lo_create.
