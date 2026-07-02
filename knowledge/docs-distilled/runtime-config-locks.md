---
source_url: https://www.postgresql.org/docs/current/runtime-config-locks.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Lock Management configuration

The lock-table GUC reference. Companion: `knowledge/subsystems/storage-lmgr.md`,
`knowledge/idioms/locking-overview.md`, skill `locking`.

## deadlock_timeout does double duty

- **`deadlock_timeout` (default 1s, SIGHUP) is the delay before the deadlock
  detector runs** — deadlock checking is expensive, so PG optimistically waits,
  assuming most lock waits resolve on their own. **It is ALSO the delay before
  `log_lock_waits` emits its "still waiting" log line.** Ideally set above your
  typical transaction time. [from-docs]

## max_locks_per_transaction is a misnomer

- **`max_locks_per_transaction` (default 64, restart-only) does NOT cap a single
  transaction.** The shared lock table is sized once as
  `max_locks_per_transaction × (max_connections + max_prepared_transactions)`,
  and *any* transaction may use more than 64 as long as the whole cluster fits
  in that shared pool. It counts distinct **objects** (relations), not rows —
  row locks are stored in tuples and are unlimited. Raising it needs a restart
  (it resizes shared memory), and a **standby must match or exceed the
  primary's value** or it rejects queries. [from-docs]

## Predicate (SSI) locks + granularity promotion

- **`max_pred_locks_per_transaction` (64, restart-only)** sizes the shared
  predicate-lock table the same way, for SERIALIZABLE isolation. [from-docs]
- **`max_pred_locks_per_relation` (default −2)** controls page/tuple → relation
  promotion: **≥ 0 is an absolute page/tuple count; < 0 means
  `max_pred_locks_per_transaction / abs(value)`** (so −2 = 50% of the per-xact
  limit). **`max_pred_locks_per_page` (default 2)**: once more than this many
  rows on one page are predicate-locked, the whole **page** is locked. These are
  the SSI false-positive-vs-memory tradeoff knobs. [from-docs]

## Links into corpus

- [[knowledge/subsystems/storage-lmgr.md]] — heavyweight lock manager, LOCKTAG.
- [[knowledge/idioms/locking-overview.md]] — the six-layer lock taxonomy.
- [[knowledge/data-structures/lock-partitions.md]] — partitioned lock tables.
- Skill: `locking` — picking a primitive, debugging LWLock/deadlock hangs.

## Confidence note

All claims `[from-docs]` (Lock Management chapter, fetched 2026-07-01). Note:
`log_lock_waits` / `log_lock_failures` / `lock_timeout` are referenced but
documented under Client Connection Defaults, not this page. The
`max_locks_per_transaction` sizing formula lives in `lock.c` /
`LockShmemSize()`; `[from-docs]`-only here.
