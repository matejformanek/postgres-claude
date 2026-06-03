---
source_url: https://www.postgresql.org/docs/current/mvcc.html
fetched_at: 2026-06-02T20:47:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 13: Concurrency Control

The official MVCC chapter. This run mines the chapter index (13.1–13.7) with
emphasis on the parts a backend hacker most needs precise: the isolation-level
phenomenon matrix (where PG deviates from the SQL standard), the snapshot
timing rule, SSI, the table/row lock-mode taxonomy + conflict matrix, and the
per-index-type locking notes.

## Chapter map (13.1–13.7)

- **13.1 Introduction** — MVCC: "each SQL statement sees a snapshot of data (a
  *database version*) as it was some time ago, regardless of the current state."
  Readers never block writers and writers never block readers. [from-docs]
- **13.2 Transaction Isolation** — the four SQL levels and the phenomena each
  prevents. Detailed below.
- **13.3 Explicit Locking** — table-level, row-level, page-level, advisory
  locks; deadlock detection. Detailed below.
- **13.4 Data Consistency Checks at the Application Level** — when Read
  Committed isn't enough; using SSI or explicit locks for app-level invariants.
- **13.5 Serialization Failure Handling** — apps must retry transactions that
  abort with `serialization_failure` (SQLSTATE 40001) or `deadlock_detected`
  (40P01). [from-docs]
- **13.6 Caveats** — e.g. a transaction always sees its own uncommitted writes;
  some DDL is not MVCC-safe; `pg_dump`'s snapshot interaction.
- **13.7 Locking and Indexes** — per-AM locking behavior. Detailed below.

## Isolation levels — the phenomenon matrix (13.2)

PostgreSQL implements all four standard levels but **internally uses only two
distinct snapshot regimes**: Read Uncommitted behaves as Read Committed, and
Serializable adds SSI on top of the Repeatable Read snapshot. [from-docs]

| Level | Dirty read | Nonrepeatable read | Phantom read | Serialization anomaly |
|---|---|---|---|---|
| Read Uncommitted | **not possible in PG** (allowed by standard) | possible | possible | possible |
| Read Committed (default) | not possible | possible | possible | possible |
| Repeatable Read | not possible | not possible | **not possible in PG** (standard allows it) | possible |
| Serializable | not possible | not possible | not possible | not possible |

- **PG never permits dirty reads at any level** — even the "Read Uncommitted"
  request is silently upgraded to Read Committed. [from-docs]
- **PG's Repeatable Read is stronger than the SQL standard**: because it is built
  on snapshot isolation, it also blocks phantom reads, which the standard leaves
  permissible at that level. The remaining gap vs Serializable is the
  *serialization anomaly* (e.g. write skew). [from-docs]
- **Default level is Read Committed.** [from-docs]

## The snapshot-timing rule (13.2.1–13.2.2)

This is the single most load-bearing distinction:

- **Read Committed takes a NEW snapshot at the start of each statement.** Within
  one transaction, two successive `SELECT`s can see different committed data.
  An `UPDATE`/`DELETE`/`SELECT FOR UPDATE` that finds a row already updated by a
  concurrently-committed transaction will *re-evaluate* its `WHERE` against the
  **latest** row version (the "EvalPlanQual" walk), not the snapshot version —
  so a Read Committed write can act on rows its own snapshot couldn't see.
  [from-docs]
  [verified-by-code, snapshot semantics in
  knowledge/data-structures/snapshot-lifecycle.md: `xmin`/`xmax`/`xip` define
  the visible set]
- **Repeatable Read and Serializable take ONE snapshot at transaction start**
  (technically at the first non-transaction-control statement) and use it for
  every statement. A concurrent-update collision here does **not** re-evaluate;
  it aborts with `could not serialize access due to concurrent update`
  (serialization failure), and the app must retry. [from-docs]

## Serializable Snapshot Isolation — SSI (13.2.3)

- **SSI = Repeatable Read snapshot + runtime detection of dangerous read/write
  dependency cycles** ("pivots"). Added in PG 9.1. No extra blocking on reads;
  instead it tracks **SIREAD ("predicate") locks** — flags, not blocking locks —
  recording what each serializable transaction read. [from-docs]
  [verified-by-code, source/src/backend/storage/lmgr/predicate.c — SIREAD locks
  are "more like flags than locks", non-blocking, and **must survive a
  successful COMMIT** until all overlapping transactions finish; this is why
  shared state spills to the `pg_serial` SLRU,
  via knowledge/files/src/backend/storage/lmgr/predicate.c.md]
- **Predicate-lock granularity collapses** tuple → page → relation as the read
  footprint grows (`TargetTagIsCoveredBy`), trading false-positive aborts for
  bounded memory. [verified-by-code, predicate.c:232-246, via per-file doc]
- Only serializable transactions create predicate locks; reads in other levels
  are gated out by `SerializationNeededForRead` (also skips temp tables and
  system catalogs). [verified-by-code, predicate.c:530,574]
- Apps should not need explicit locks under Serializable — but **must** be
  prepared to retry on 40001. `SELECT` can also abort under SSI, unlike under
  the other levels. [from-docs]

## Explicit locking — table-level modes (13.3.1)

Eight table-level lock modes, weakest → strongest. PG's internal enum makes
`AccessExclusiveLock = 8` the strongest; `MAX_LOCKMODES = 10` is just the
`LOCKMASK` bit budget, not the count of real modes. [from-docs]
[verified-by-code, knowledge/files/src/include/storage/lock.h.md:12 —
`MaxLockMode = AccessExclusiveLock = 8`]

| Mode | Typical acquirer | Conflicts with |
|---|---|---|
| ACCESS SHARE | `SELECT` | ACCESS EXCLUSIVE only |
| ROW SHARE | `SELECT … FOR UPDATE/SHARE` | EXCLUSIVE, ACCESS EXCLUSIVE |
| ROW EXCLUSIVE | `INSERT`/`UPDATE`/`DELETE` | SHARE, SHARE ROW EXCLUSIVE, EXCLUSIVE, ACCESS EXCLUSIVE |
| SHARE UPDATE EXCLUSIVE | `VACUUM` (non-FULL), `ANALYZE`, `CREATE INDEX CONCURRENTLY`, many `ALTER TABLE` | self + SHARE, SHARE ROW EXCLUSIVE, EXCLUSIVE, ACCESS EXCLUSIVE |
| SHARE | `CREATE INDEX` (non-concurrent) | ROW EXCLUSIVE, SHARE UPDATE EXCLUSIVE, SHARE ROW EXCLUSIVE, EXCLUSIVE, ACCESS EXCLUSIVE |
| SHARE ROW EXCLUSIVE | `CREATE TRIGGER`, some `ALTER TABLE` | everything except ACCESS SHARE |
| EXCLUSIVE | `REFRESH MATERIALIZED VIEW CONCURRENTLY` | everything except ACCESS SHARE |
| ACCESS EXCLUSIVE | `DROP`/`TRUNCATE`/`VACUUM FULL`/most `ALTER TABLE`/`LOCK TABLE` default | **all eight modes** |

- **Self-conflict cutoff:** SHARE UPDATE EXCLUSIVE is the weakest mode that
  conflicts with itself — that is why two `VACUUM`s (or `CREATE INDEX
  CONCURRENTLY`) on one table serialize. ACCESS SHARE and ROW
  SHARE/ROW EXCLUSIVE do **not** self-conflict, so ordinary readers and writers
  run fully concurrently. [from-docs]
- Locks are held until end of transaction; there is no `UNLOCK`. [from-docs]

## Row-level locks (13.3.2)

Four modes, weakest → strongest, all released at transaction end:

- **FOR KEY SHARE** — weakest; blocks only `DELETE` and key-changing `UPDATE`.
  This is what foreign-key checks take, so FK enforcement no longer blocks
  concurrent non-key updates of the parent. [from-docs]
- **FOR SHARE** — shared; blocks any `UPDATE`/`DELETE`, allows other FOR SHARE.
- **FOR NO KEY UPDATE** — exclusive but compatible with FOR KEY SHARE; taken by
  a plain `UPDATE` that doesn't touch key columns.
- **FOR UPDATE** — strongest; taken by `DELETE` and key-changing `UPDATE` and by
  explicit `SELECT … FOR UPDATE`. Blocks all other row locks.

Row locks live in the tuple itself (xmax + infomask bits), not in shared
memory, so they don't exhaust the lock table; a `SELECT … FOR UPDATE` does
incidentally take a ROW SHARE *table* lock. Multiple sharers of one row use a
**MultiXact** to record the set. [from-docs]
[verified-by-code, multixact in
knowledge/files/src/backend/access/transam/multixact.c.md]

## Page-level, advisory locks, deadlocks (13.3.3–13.3.5)

- **Page-level locks** (shared/exclusive content locks on buffers) are taken and
  released quickly during row read/write and are not under app control;
  mentioned only for completeness. [from-docs]
- **Advisory locks** — application-defined, identified by one `bigint` or two
  `int4`s. Session-level (`pg_advisory_lock`) persist until explicit unlock or
  disconnect; transaction-level (`pg_advisory_xact_lock`) auto-release at
  transaction end. They live in the same shared lock table as heavyweight locks,
  so a runaway advisory-lock workload can exhaust `max_locks_per_transaction`.
  [from-docs]
- **Deadlock detection** is *optimistic*: a waiter only runs the detector after
  its own `deadlock_timeout` (default **1 s**) elapses; the detector walks the
  waits-for graph, classifying edges soft/hard, and tries legal wait-queue
  reorderings before aborting a victim. [from-docs]
  [verified-by-code, `DeadLockCheck` at
  source/src/backend/storage/lmgr/deadlock.c:220, invoked from `CheckDeadLock`
  while holding **all 16 lock-partition LWLocks** in partition order,
  via knowledge/files/src/backend/storage/lmgr/deadlock.c.md]
  The victim gets SQLSTATE 40P01; the docs stress acquiring locks in a
  consistent order to avoid deadlocks entirely. [from-docs]

## Locking and indexes (13.7)

Per-AM concurrency behavior — the docs give explicit guidance: [from-docs]

- **B-tree, GiST, SP-GiST** — short-term page-level locks held only for the
  duration of an individual index read/insert; released immediately. Best
  concurrency; recommended for high-concurrency workloads.
- **Hash** — page-level locks, held longer than B-tree's, giving lower
  concurrency (and historically the reason hash indexes were discouraged; they
  are crash-safe + WAL-logged since PG 10).
- **GIN** — page-level locks on insert; **fast reads**. GIN's pending-list
  ("fastupdate") batches insertions, which is the relevant concurrency knob.

The takeaway the docs draw: B-tree/GiST/SP-GiST give the highest write
concurrency; hash and GIN can serialize more under heavy insert load. [from-docs]

## Links into corpus

- [[knowledge/architecture/mvcc.md]] — the PG-wide MVCC concept doc this chapter
  formalizes (snapshot model, xmin/xmax visibility).
- [[knowledge/data-structures/snapshot-lifecycle.md]] — `xmin`/`xmax`/`xip`
  snapshot fields and the visibility decision the isolation levels rest on.
- [[knowledge/subsystems/storage-lmgr.md]] — the heavyweight lock manager
  behind the table/row/advisory lock modes.
- [[knowledge/files/src/backend/storage/lmgr/lock.c.md]] — lock acquisition,
  conflict table, the recovery-mode lock-strength clamp.
- [[knowledge/files/src/backend/storage/lmgr/predicate.c.md]] — SSI / SIREAD
  predicate locks, `pg_serial` SLRU, granularity collapsing.
- [[knowledge/files/src/backend/storage/lmgr/deadlock.c.md]] — the waits-for
  graph deadlock detector (`DeadLockCheck`, soft/hard edges).
- [[knowledge/files/src/backend/access/transam/multixact.c.md]] — MultiXacts
  that record multiple row-lock sharers.
- [[knowledge/idioms/locking-overview.md]] — when to reach for which lock flavor
  from C.
- [[knowledge/subsystems/access-nbtree.md]] — B-tree page-locking detail behind
  §13.7's "short-term locks" claim.

## Gaps / follow-ups

- SSI internals (rw-conflict tracking, the "pivot"/dangerous-structure test,
  `pg_serial` SLRU) deserve their own distilled doc keyed off the
  `README-SSI` corpus note — bigger than a §13.2.3 summary can hold.
- The conflict matrix above is the canonical docs table reproduced from memory
  of §13.3.1; the *self-conflict cutoff* (SHARE UPDATE EXCLUSIVE) and "ACCESS
  EXCLUSIVE conflicts with all" rows are [verified-by-code] via lock.c, the
  interior cells are [from-docs] and should be spot-checked against
  `lockMethodTable` conflict masks in a future file-backfill.
- Line numbers cited via per-file corpus docs were last verified at an earlier
  anchor; STATE.md records the delta to `4b0bf0788b` as build-system-only with
  no corpus impact, so they are treated as current. [inferred]
