# Iteration 1 — Answers

## Eval 1: orient-new-sql-fn

### with_skill
For adding a new built-in SQL function:
- Start with the `catalog-conventions` skill (any pg_proc.dat edit) and `fmgr-and-spi` skill (PG_FUNCTION_INFO_V1, fmgr machinery).
- Background reading: `knowledge/idioms/fmgr.md` and `knowledge/idioms/catalog-conventions.md`.
- For the C code itself: `coding-style` skill (postgres.h first, tabs, C99 subset), `error-handling` (ereport/elog), `memory-contexts` (palloc lifetimes).
- Work happens in `dev/src/backend/...`. Use `/setup-pg` to build, `/pg-restart` to pick up the new binary, `/pg-psql` to test, `/pg-test` for regression.
- When you're ready to send upstream: `patch-submission` + `review-checklist` + `commit-message-style` skills.

### baseline
To add a built-in SQL function in PostgreSQL, you typically add an entry to `pg_proc.dat`, write the C function with the PG_FUNCTION_INFO_V1 macro, and bump catversion. You'll want to look at existing built-ins under `src/backend/utils/adt/` for examples. Build with meson/ninja, install, restart the cluster, and write regression tests under `src/test/regress/`.

---

## Eval 2: debug-deadlock

### with_skill
For debugging a deadlock:
- Reach for the `debugging` skill (gdb/lldb attach, single-user mode, fork-model implications) and the `locking` skill (LWLocks, heavyweight locks, ordering).
- To attach lldb to a live backend, run `/pg-attach`. Tail server log with `/pg-tail-log`.
- Background: `knowledge/idioms/locking-overview.md` is the deep reference; `knowledge/subsystems/storage-lmgr.md` for the lock-manager subsystem.
- Remember the per-connection fork model — each psql connection is a fresh backend pid, so attach AFTER connecting.

### baseline
For debugging a deadlock in PostgreSQL, you can query `pg_locks` and `pg_stat_activity` to see what's blocking what. Increase `log_lock_waits` and check the server log. Attach gdb/lldb to the backend PID. The lock manager code lives in `src/backend/storage/lmgr/`.

---

## Eval 3: learn-mvcc

### with_skill
Suggested reading order in this repo:
1. `knowledge/architecture/overview.md` — PG-wide concepts framing.
2. `knowledge/architecture/mvcc.md` — the MVCC deep-dive.
3. `knowledge/architecture/wal.md` — durability side of the story.
4. `knowledge/subsystems/access-heap.md` — how MVCC plays out in the heap AM (xmin/xmax/HOT).
5. `knowledge/subsystems/access-transam.md` — transaction id management, clog, snapshots.
6. For the lock-ordering / SSI angle: `knowledge/idioms/locking-overview.md`.

All cites in those docs use `source/...` paths so file:line refs stay stable. Use the `wal-and-xlog` skill if you start touching durability code.

### baseline
To learn PostgreSQL MVCC, read the official docs chapter on concurrency control, then dig into `src/backend/access/heap/heapam.c` and look at xmin/xmax handling. Tom Lane's talks and the PG wiki have good overviews. The HOT-updates README is also worthwhile.
