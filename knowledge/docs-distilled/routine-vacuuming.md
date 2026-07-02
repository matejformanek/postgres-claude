---
source_url: https://www.postgresql.org/docs/current/routine-vacuuming.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Routine Vacuuming (the mechanism)

The internals prose behind VACUUM: why it exists, and the wraparound machine.
Companion GUC reference: `knowledge/docs-distilled/runtime-config-vacuum.md`.
Directly serves the recurring `gap:vacuum-autovacuum` / vacuum-horizon cluster
flagged by the user-question-harvester.

## The four purposes

- VACUUM does four unrelated jobs at once: (1) **reclaim** dead-tuple space,
  (2) **update planner statistics** (ANALYZE side), (3) **maintain the
  visibility map** for index-only scans + page-skipping, (4) **freeze old XIDs
  and multixacts** to prevent wraparound data-loss. Purpose (4) is the one
  that's non-negotiable. [from-docs]

## XID wraparound — the core comparison

- **XIDs are 32-bit; comparison is modulo-2³²**, so every normal XID has ~2
  billion "older" and ~2 billion "newer". After ~4B transactions the counter
  wraps and old rows would appear to be *in the future* → silently invisible →
  catastrophic loss. [from-docs]
- **`FrozenTransactionId` (value 2) breaks the rule**: a frozen tuple is
  *always* older than every normal XID, so it survives wraparound. VACUUM's job
  is to freeze rows before their age reaches the danger zone. [from-docs]
- **`relfrozenxid` (pg_class) / `datfrozenxid` (pg_database, = min of per-table
  relfrozenxid)** track the oldest unfrozen XID. Monitor with
  `age(relfrozenxid)` / `age(datfrozenxid)`. [from-docs]

## The safety ladder (thresholds a hacker must know)

- **`age(relfrozenxid) > autovacuum_freeze_max_age` (200M) ⇒ anti-wraparound
  autovacuum is forced — even when `autovacuum = off`.** This is the guaranteed
  backstop. [from-docs]
- **~40M transactions from wraparound**: server starts emitting `WARNING:
  database "x" must be vacuumed within N transactions`. [from-docs]
- **< 3M transactions to go**: server **refuses to assign new XIDs** —
  `ERROR: database is not accepting commands that assign new XIDs …`. Recovery
  is a manual VACUUM (historically single-user mode; modern versions can do it
  online). [from-docs]

## Aggressive vs normal vacuum + eager scan

- **Normal VACUUM uses the visibility map to skip all-frozen pages** and may not
  advance `relfrozenxid`. **Aggressive VACUUM scans every not-all-frozen page**
  and is guaranteed to advance it; triggered when
  `age(relfrozenxid) > vacuum_freeze_table_age`. [from-docs]
- **Eager scanning**: even a normal vacuum may opportunistically freeze
  all-visible-but-not-all-frozen pages, bounded by
  `vacuum_max_eager_freeze_failure_rate` (default 3%) — amortizes the next
  aggressive scan. [from-docs]

## Visibility map drives two optimizations

- **All-visible bit** ⇒ vacuum can skip the page and **index-only scans can skip
  the heap fetch** (check the VM instead of the tuple). **All-frozen bit** ⇒
  aggressive vacuum skips it too. The VM is tiny relative to the heap, which is
  what makes IOS win on big tables. [from-docs]

## Autovacuum daemon process model

- **Launcher (persistent) + up to `autovacuum_max_workers` workers.** Launcher
  tries one worker per database every `autovacuum_naptime / num_databases`
  seconds. Workers **don't** count against `max_connections` /
  `superuser_reserved_connections`. [from-docs]
- **Workers hold `SHARE UPDATE EXCLUSIVE`; a conflicting lock request
  auto-cancels a running autovacuum — EXCEPT anti-wraparound autovacuum** (query
  ends with `(to prevent wraparound)`), which is *not* auto-cancelled. A cron
  that keeps issuing conflicting DDL/ANALYZE can starve normal autovacuum
  forever. [from-docs]
- **Skipped entirely**: partitioned parents (only leaf partitions get
  processed), temp tables (session-only — must be vacuumed manually), and
  foreign tables (no auto-ANALYZE). [from-docs]

## Multixact wraparound (the second clock)

- **Multixacts encode "multiple transactions lock this row" into a 32-bit MXID
  in `xmax`; `relminmxid` tracks the oldest.** Same 200M/400M-style aging via
  `autovacuum_multixact_freeze_max_age` (400M). [from-docs]
- **Members-space pressure is the sneaky trigger**: the `pg_multixact/members`
  area holds the XID lists (~20 GB capacity); **once it exceeds ~10 GB,
  aggressive vacuums fire more often cluster-wide**, oldest-MXID-first, well
  before the MXID *count* is near wraparound. MXID exhaustion only blocks
  *row-locking write* transactions, and isn't visible in `pg_stat_activity` —
  inspect XIDs / `pg_get_multixact_members()`. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/runtime-config-vacuum.md]] — the GUC knobs.
- [[knowledge/subsystems/access-heap.md]] — HOT, freeze, tuple visibility.
- [[knowledge/subsystems/access-transam.md]] — clog/multixact SLRUs, XID epoch.
- [[knowledge/architecture/mvcc.md]] — snapshot visibility these XIDs feed.
- [[knowledge/docs-distilled/storage-vm.md]] — visibility-map bit layout.
- Skill: `wal-and-xlog` (freeze WAL records), `access-method-apis` (heap AM).

## Confidence note

All claims `[from-docs]` (Routine Vacuuming chapter, fetched 2026-07-01).
Thresholds (40M warning, 3M refuse, ~10 GB members) quoted from the page; the
exact source constants live in `vacuum.c` / `varsup.c` / `multixact.c` — a
future auditor pass could pin them.
