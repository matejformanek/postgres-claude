# Iteration 2 — Answers (re-run after edits)

## Eval 1: orient-new-sql-fn

### with_skill
For adding a new built-in SQL function, the flowchart row "add a built-in SQL fn" lays out the recipe:
- `catalog-conventions` skill — `pg_proc.dat` entry, catversion bump.
- `fmgr-and-spi` skill — `PG_FUNCTION_INFO_V1` and the calling convention.
- `knowledge/idioms/fmgr.md` and `knowledge/idioms/catalog-conventions.md` as background reading.
- `coding-style` skill applies to any C edit (postgres.h first, tabs, C99 subset). `error-handling` for ereport, `memory-contexts` for palloc.
- Place the C code under `dev/src/backend/utils/adt/`. Then the build loop is `/setup-pg → /pg-restart → /pg-psql → /pg-test`.
- When mailing it: `patch-submission` + `review-checklist` + `commit-message-style`.

---

## Eval 2: debug-deadlock

### with_skill
The flowchart has a dedicated "debug a deadlock" row:
- Attach with `/pg-attach`, tail the server log with `/pg-tail-log`.
- `locking` skill plus the `debugging` skill cover the mechanics.
- Background: `knowledge/idioms/locking-overview.md` (deep), `knowledge/subsystems/storage-lmgr.md` (lock-manager subsystem).
- Per-connection fork-model gotcha: attach AFTER the psql connect — the backend pid is fresh per session.

---

## Eval 3: learn-mvcc

### with_skill
From the "Suggested reading orders" section:
1. `knowledge/architecture/overview.md` — PG-wide framing.
2. `knowledge/architecture/mvcc.md` — the MVCC deep-dive.
3. `knowledge/architecture/wal.md` — durability side of the story.
4. `knowledge/subsystems/access-heap.md` — heap AM (xmin/xmax/HOT).
5. `knowledge/subsystems/access-transam.md` — txid management, clog, snapshots.

All cites in those docs use `source/...` so file:line refs stay stable across upstream pulls. For SSI / lock-ordering angle: `knowledge/idioms/locking-overview.md`. For code edits touching durability: `wal-and-xlog` skill.
