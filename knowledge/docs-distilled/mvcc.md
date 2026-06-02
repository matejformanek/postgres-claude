---
source_url: https://www.postgresql.org/docs/current/mvcc.html
also_fetched:
  - https://www.postgresql.org/docs/current/transaction-iso.html
  - https://www.postgresql.org/docs/current/explicit-locking.html
fetched_at: 2026-06-02T11:19:25Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 13: Concurrency Control

The official "concurrency control" chapter. `mvcc.html` is just the chapter
index; the substantive internals live in **13.2 Transaction Isolation**
(`transaction-iso.html`) and **13.3 Explicit Locking**
(`explicit-locking.html`), which is where this run spent its budget. MVCC is the
mechanism that lets readers never block writers and writers never block readers.

## Chapter map (13.1–13.7)

- **13.1 Introduction** — MVCC rationale: each statement sees a snapshot of data
  as it was some time ago, regardless of concurrent changes. [from-docs]
- **13.2 Transaction Isolation** — the three implemented levels. Detailed below.
- **13.3 Explicit Locking** — table/row/page/advisory locks + deadlocks.
  Detailed below.
- **13.4 Data Consistency Checks at the Application Level** — serializable vs.
  explicit-blocking-lock strategies. [from-docs]
- **13.5 Serialization Failure Handling** — retry SQLSTATE `40001`/`40P01`.
  [from-docs]
- **13.6 Caveats** / **13.7 Locking and Indexes** — index AMs take short-term
  page locks; B-tree/GiST/SP-GiST release them immediately, hash holds longer.
  [from-docs]

## Transaction isolation (13.2) — non-obvious claims

- **Four standard levels accepted, three distinct.** `READ UNCOMMITTED` maps to
  Read Committed because "it is the only sensible way to map the standard
  isolation levels to PostgreSQL's multiversion concurrency control
  architecture." There is no dirty-read mode at all. [from-docs]
- **Read Committed (13.2.1) takes a new snapshot per *statement*,** not per
  transaction — two successive `SELECT`s in one transaction can see different
  committed data. [from-docs]
- **The UPDATE/DELETE/SELECT-FOR-UPDATE re-check (EvalPlanQual):** when a write
  command's target row was changed by a transaction that committed after the
  command's snapshot, PG does *not* use the snapshot version. It walks to the
  *latest* row version, **re-evaluates the `WHERE` clause** against it, and skips
  the row if it no longer matches; if the first writer deleted the row, the
  second ignores it; if the first writer rolled back, the original row is used.
  [from-docs] [mechanism: knowledge/architecture/mvcc.md +
  knowledge/subsystems/access-heap.md — EvalPlanQual machinery]
- **Read Committed's famous hazard:** under a concurrent
  `UPDATE website SET hits = hits + 1`, a `DELETE FROM website WHERE hits = 10`
  can match *no* row even though a `hits = 10` row existed before and after — the
  pre-update value `9` is skipped and the re-evaluated post-update value is `11`.
  Read Committed gives no protection against this kind of skew. [from-docs]
- **Repeatable Read (13.2.2) is Snapshot Isolation.** The snapshot is taken at
  the **first non-transaction-control statement**, and every query in the
  transaction sees that one snapshot. It forbids dirty/nonrepeatable/phantom
  reads — *and more than the standard requires* — but still permits write skew.
  [from-docs]
- **RR's serialization failure** is raised when it tries to update/lock a row
  another transaction changed after the RR snapshot began:
  `ERROR: could not serialize access due to concurrent update`, **SQLSTATE
  40001**. The application must retry the whole transaction. [from-docs]
- **History note:** before PG 9.1 a request for `SERIALIZABLE` gave exactly
  today's Repeatable Read behavior (plain snapshot isolation). To get the old
  behavior now, ask for Repeatable Read. [from-docs]
- **Serializable (13.2.3) = Serializable Snapshot Isolation (SSI).** It is
  Repeatable Read *plus* monitoring for read/write dependency cycles that could
  diverge from every possible serial order. On detection:
  `ERROR: could not serialize access due to read/write dependencies among
  transactions`, also **SQLSTATE 40001**. [from-docs]
- **Predicate locks (`SIReadLock`) never block.** SSI keeps `SIReadLock`s to
  detect when a write would have changed the result of a concurrent
  transaction's earlier read. They cause **no blocking** and therefore **cannot
  participate in a deadlock** — they only *trigger* serialization failures.
  Visible in `pg_locks` with `mode = 'SIReadLock'`. [from-docs]
  [mechanism: knowledge/files/src/backend/storage/lmgr/predicate.c.md +
  knowledge/files/src/backend/storage/lmgr/README-SSI.md]
- **The only case where Serializable blocks but Repeatable Read doesn't:**
  `SERIALIZABLE READ ONLY DEFERRABLE` — it waits to acquire a snapshot provably
  free of serialization anomalies before reading anything. [from-docs]
- **SSI can still raise errors a true serial run wouldn't,** e.g. a unique-
  constraint violation from two overlapping serializable transactions inserting
  the same key even after each checked the key was absent. SSI proves
  serializability of *commits*, not absence of all errors. [from-docs]
- **Tuning knobs for SSI under contention:**
  `max_pred_locks_per_transaction`, `max_pred_locks_per_relation`,
  `max_pred_locks_per_page`. Sequential scans force *relation-level* predicate
  locks (coarse → more false-conflict serialization failures); good index usage
  keeps predicate locks fine-grained. [from-docs]

## Explicit locking (13.3) — non-obvious claims

- **Eight table-level lock modes, weakest → strongest:** `ACCESS SHARE`,
  `ROW SHARE`, `ROW EXCLUSIVE`, `SHARE UPDATE EXCLUSIVE`, `SHARE`,
  `SHARE ROW EXCLUSIVE`, `EXCLUSIVE`, `ACCESS EXCLUSIVE`. The names are about
  *conflict behavior*, not literally what the command does — e.g. `ROW
  EXCLUSIVE` is a table-level lock taken by any `INSERT`/`UPDATE`/`DELETE`/
  `MERGE`. [from-docs]
- **Who takes what (high-value rows):** `SELECT` → `ACCESS SHARE`;
  `INSERT`/`UPDATE`/`DELETE`/`MERGE` → `ROW EXCLUSIVE`;
  `VACUUM` (non-FULL)/`ANALYZE`/`CREATE INDEX CONCURRENTLY`/`CREATE STATISTICS` →
  `SHARE UPDATE EXCLUSIVE`; `CREATE INDEX` (non-concurrent) → `SHARE`;
  `CREATE TRIGGER` + some `ALTER TABLE` → `SHARE ROW EXCLUSIVE`;
  `REFRESH MATERIALIZED VIEW CONCURRENTLY` → `EXCLUSIVE`;
  `DROP`/`TRUNCATE`/`REINDEX`/`CLUSTER`/`VACUUM FULL`/most `ALTER TABLE` and the
  default `LOCK TABLE` → `ACCESS EXCLUSIVE`. [from-docs]
- **The two endpoints of the conflict matrix are the ones to memorize:**
  `ACCESS EXCLUSIVE` conflicts with **all eight** modes (so it blocks even a
  plain `SELECT`); `ACCESS SHARE` conflicts with **only** `ACCESS EXCLUSIVE`.
  Self-conflicting modes: `ACCESS EXCLUSIVE`, `SHARE ROW EXCLUSIVE`, `EXCLUSIVE`
  (and the share/update-exclusive pairings). [from-docs]
- **Four row-level lock modes, strongest → weakest:** `FOR UPDATE` >
  `FOR NO KEY UPDATE` > `FOR SHARE` > `FOR KEY SHARE`. `FOR KEY SHARE` blocks
  only `FOR UPDATE`; `FOR UPDATE` blocks all four. The key-vs-non-key split is
  what lets a plain `UPDATE` of a non-key column run concurrently with a foreign-
  key check (`FOR KEY SHARE`) on the same row. [from-docs]
- **Row locks are stored *on the tuple*, not in a shared-memory lock table** — so
  there is **no limit** on how many rows one transaction can lock, and locking a
  million rows costs no shared memory. (Contrast: table/advisory locks live in
  the shared lock table sized by `max_locks_per_transaction` × `max_connections`.)
  Row locks release at transaction end or savepoint rollback. [from-docs]
  [mechanism: knowledge/subsystems/access-heap.md — xmax/infomask tuple locking;
  knowledge/subsystems/storage-lmgr.md — heavyweight lock table]
- **Page-level locks** are short-lived share/exclusive locks on buffer-pool
  pages, **released as soon as a row is fetched or updated** — application code
  never deals with them directly. [from-docs]
- **Deadlocks (13.3.4) are detected, not prevented.** A backend that has waited
  `deadlock_timeout` (default 1s) runs the deadlock detector; if a cycle is
  found, one transaction is aborted with **SQLSTATE 40P01**
  (`deadlock_detected`). The durable fix is to make all transactions acquire
  locks **in a consistent order**, and to take the most restrictive lock you'll
  need *first*. [from-docs]
  [mechanism: knowledge/files/src/backend/storage/lmgr/deadlock.c.md]
- **Advisory locks (13.3.5): two flavors.** Session-level
  (`pg_advisory_lock`) ignore transaction boundaries — a rollback does **not**
  release them, only an explicit unlock or session end does, which is how you get
  a *dangling* advisory lock. Transaction-level (`pg_advisory_xact_lock`) behave
  like normal locks and auto-release at commit/rollback. [from-docs]
- **The advisory-lock-in-a-SELECT footgun:** `LIMIT` is not guaranteed to apply
  before the locking function runs, so
  `SELECT pg_advisory_lock(id) FROM foo WHERE id > 12345 LIMIT 100` may lock far
  more than 100 ids. Push the `LIMIT` into a subquery so it's evaluated first.
  [from-docs]

## SQLSTATEs to remember

| Condition | SQLSTATE | Symbolic name | Raised by |
|---|---|---|---|
| Serialization failure (RR concurrent update, SSI r/w cycle) | `40001` | `serialization_failure` | Repeatable Read & Serializable |
| Deadlock | `40P01` | `deadlock_detected` | deadlock detector after `deadlock_timeout` |

Both belong to SQLSTATE class `40` (transaction rollback) — the canonical signal
that the *only* correct application response is to retry the whole transaction.
[from-docs]

## Links into corpus

- [[knowledge/architecture/mvcc.md]] — the long-form MVCC synthesis this chapter
  maps onto (snapshots, xmin/xmax visibility, EvalPlanQual).
- [[knowledge/subsystems/access-heap.md]] — where row-level locks physically live
  (xmax + infomask on the heap tuple) and how visibility is computed.
- [[knowledge/subsystems/storage-lmgr.md]] — the heavyweight lock manager that
  implements the eight table-level modes and the conflict matrix.
- [[knowledge/idioms/locking-overview.md]] — the decision tree across atomics /
  spinlocks / LWLocks / heavyweight / predicate locks.
- [[knowledge/files/src/backend/storage/lmgr/predicate.c.md]] +
  [[knowledge/files/src/backend/storage/lmgr/README-SSI.md]] — SSI / `SIReadLock`
  predicate-locking implementation behind Serializable.
- [[knowledge/files/src/backend/storage/lmgr/deadlock.c.md]] — the deadlock
  detector that fires after `deadlock_timeout`.
- [[knowledge/data-structures/snapshot-lifecycle.md]] — how the per-statement vs
  per-transaction snapshots distinguishing RC from RR are taken and released.

## Gaps / follow-ups

- 13.4 (application-level consistency) and 13.6 (caveats) were only summarized,
  not mined — each could seed its own note if the queue wants finer granularity.
- The exact `SIReadLock` acquisition points and the read/write-dependency cycle
  detection live in `predicate.c`; cites here are routed through the per-file
  corpus doc rather than re-verified line-by-line this run (source tree not
  mounted in the cloud routine — verify against anchor `4b0bf0788b` on a future
  file-backfill run). [inferred]
- The row-level lock conflict table (Table 13.3) and full table-level matrix
  (Table 13.2) are reproduced in prose, not as the full grids — see the source
  URL for the authoritative matrices.
