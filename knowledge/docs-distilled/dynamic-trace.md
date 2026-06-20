---
source_url: https://www.postgresql.org/docs/current/dynamic-trace.html
fetched_at: 2026-06-20T19:55:00Z
anchor_sha: dc5116780846
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Dynamic Tracing — DTrace / SystemTap probe points (Monitoring §28.5)

The backend ships a set of **static trace probes** — fixed instrumentation
points compiled into the server — that DTrace (or SystemTap on Linux) can attach
to with zero source changes. This is the "observe the running backend from
outside, by named event" surface, complementary to the SQL-level stats views.

## Build + platform

- Probes are **off by default**; build with `--enable-dtrace` (autoconf) — the
  developer-options switch. [from-docs] [cite: src/include/utils/probes.h]
- Supported platforms: Solaris, macOS, FreeBSD, NetBSD, Oracle Linux; **Linux**
  uses **SystemTap**, which is probe-compatible but uses different script syntax.
  Other tracers are possible by editing macro definitions in
  `source/src/include/utils/probes.h`. [from-docs]

## How a probe is defined and fired (the three names)

- Probe definitions live in `source/src/backend/utils/probes.d`; the macros are
  pulled in by including `pg_trace.h` in the C module that fires them. [from-docs]
  [cite: src/backend/utils/probes.d]
- **One probe, three spellings** (a recurring confusion):
  - in `probes.d`: double underscores — `transaction__start`
  - in DTrace/SystemTap scripts: hyphens — `transaction-start`
  - in C source (the macro): uppercase single-underscore —
    `TRACE_POSTGRESQL_TRANSACTION_START(...)` [from-docs]
- Adding a probe = (1) add `probe foo__bar(args);` to `probes.d`, (2) include
  `pg_trace.h`, (3) drop `TRACE_POSTGRESQL_FOO_BAR(...)` at the code site, (4)
  recompile. [from-docs]
- **Argument types must match** the variable types at the call site or you get
  compile errors. Probe params use a fixed typedef set: `LocalTransactionId`
  (`unsigned int`), `LWLockMode`/`LOCKMODE`/`ForkNumber` (`int`),
  `BlockNumber`/`Oid` (`unsigned int`), `bool` (`unsigned char`). [from-docs]

## The performance gotcha (the load-bearing one)

- On most platforms, with `--enable-dtrace`, the **macro arguments are evaluated
  every time control passes the macro, even when no tracing is active.** So a
  probe whose argument calls an expensive function pays that cost
  unconditionally. [from-docs]
- Guard expensive arguments with the per-probe `..._ENABLED()` macro:
  `if (TRACE_POSTGRESQL_TRANSACTION_START_ENABLED()) TRACE_POSTGRESQL_TRANSACTION_START(expensive());`
  Every trace macro has a matching `_ENABLED()` variant. [from-docs]

## Representative probe families (Table of built-in probes)

- **Transaction:** `transaction-start` / `-commit` / `-abort`
  (`LocalTransactionId`). [from-docs]
- **Query pipeline:** `query-start`/`-done`, `query-parse-start`/`-done`,
  `query-rewrite-start`/`-done` (all `const char *` query string),
  `query-plan-start`/`-done`, `query-execute-start`/`-done` (no args). [from-docs]
- **Statement status:** `statement-status(const char *)` — fires on
  `pg_stat_activity.status` updates. [from-docs]
- **Checkpoint:** `checkpoint-start(int flags)` /
  `checkpoint-done(int,int,int,int,int)` (buffers written, total, WAL files
  added/removed/recycled), plus per-SLRU `clog-`/`subtrans-`/`multixact-`
  checkpoint pairs, `buffer-checkpoint-*`, `buffer-sync-*`,
  `twophase-checkpoint-*`. [from-docs]
- **Buffer / smgr I/O:** `buffer-read-start`/`-done`, `buffer-extend-start`/`-done`,
  `buffer-flush-start`/`-done`, and `smgr-md-read-start`/`-done`,
  `smgr-md-write-start`/`-done` — carrying `ForkNumber`, `BlockNumber`, the
  tablespace/database/relation `Oid` triple, and backend id. `buffer-read-done`'s
  trailing `bool` = "found in pool". [from-docs]
- **WAL:** `wal-buffer-write-dirty-start`/`-done` (frequent firing ⇒ `wal_buffers`
  too small), `wal-insert(rmid, info)`, `wal-switch`. [from-docs]
- **Locks:** `lwlock-acquire`/`-release`/`-wait-start`/`-wait-done`/
  `-condacquire`/`-condacquire-fail` (`char *tranche`, `LWLockMode`);
  heavyweight `lock-wait-start`/`-done` (lock-tag fields + `LOCKMODE`);
  `deadlock-found()`. [from-docs]
- **Sort:** `sort-start(int type,bool unique,int nkeys,int workmem,bool randomAccess,int parallel)`
  / `sort-done(bool external, long blocks_or_kb)`. [from-docs]

## Links into corpus

- `knowledge/docs-distilled/monitoring-stats.md` — the SQL-side statistics views
  these external probes complement.
- `knowledge/idioms/locking-overview.md`, `knowledge/idioms/lwlock-rank-discipline.md`,
  `knowledge/idioms/deadlock-detection.md` — the lock events behind the
  `lwlock-*` / `lock-wait-*` / `deadlock-found` probes.
- `knowledge/idioms/checkpoint-coordination.md` — the checkpoint phases the
  `*-checkpoint-*` probes bracket.
- `knowledge/idioms/wal-record-construction.md`,
  `knowledge/idioms/wal-buffer-state.md` — the WAL path of `wal-insert` /
  `wal-buffer-write-dirty-*`.
- `knowledge/subsystems/storage-buffer.md` — `buffer-read`/`-flush`/`-extend`
  and `smgr-md-*` map onto BufferAlloc/FlushBuffer/smgr.

## Citations

- All probe names/args: source-URL anchor
  https://www.postgresql.org/docs/current/dynamic-trace.html (PG18). The
  authoritative live list is `source/src/backend/utils/probes.d`; verify the
  exact current probe set against anchor `dc5116780846` (probes are added/removed
  between majors).
