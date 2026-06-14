---
source_url: https://www.postgresql.org/docs/current/transaction-id.html
fetched_at: 2026-06-14T19:20:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Transactions and Identifiers (§67.1)

The user-facing orientation for the xid / vxid / xid8 identifier zoo. The
code-level detail (counter advance, special xids, wraparound thresholds) lives
in the `access-transam` subsystem doc and the `varsup.c` / `transam.c` per-file
docs — quote those for anything load-bearing.

## Two identifiers per transaction: vxid and xid

- **Every** transaction — read-only included — gets a **virtual transaction ID
  (`VirtualTransactionId`, vxid)**, written `procNumber/localXID`, e.g. `4/12532`:
  the backend's `procNumber` plus a per-backend sequentially-assigned `localXID`.
  This is the identifier read-only transactions are known by. [from-docs]
- A **real `TransactionId` (xid, 32-bit)** is assigned **only when a transaction
  first writes** to the database. Read-only transactions never consume one — the
  design that lets a read-mostly workload run for a long time without burning
  through the 32-bit xid space. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/varsup.c.md]]]
- xids come from a **single global counter shared across all databases** in the
  cluster, so "lower-numbered xid started writing before higher-numbered xid" —
  but note this is *first-write* order, not transaction-*start* order. [from-docs]

## 32-bit wraparound and the epoch / xid8 escape hatch

- The xid counter is **32 bits**, so it **wraps every ~4 billion transactions**.
  A 32-bit **epoch** is bumped on each wrap. [from-docs]
- **`xid8`** is the 64-bit type that splices epoch + xid; it **does not wrap**
  within an installation's lifetime and **casts down to `xid`**. SQL functions
  that need a monotone transaction number (e.g. `pg_current_xact_id`) return
  `xid8`. [from-docs]
- The wraparound counter is why freezing / anti-wraparound VACUUM exists; the
  special frozen/bootstrap xids and the "always-visible" comparison live in
  the corpus, not on this page. [inferred]
  [cross: knowledge/subsystems/access-transam.md]

## Where commit state and prepared-xact mapping live

- **`pg_xact/`** records which xids committed (the CLOG SLRU); **`pg_commit_ts/`**
  additionally records commit timestamps when `track_commit_timestamp` is on. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/clog.c.md]]]
- **Prepared (two-phase) transactions** carry a string **GID** (a "global
  transaction identifier", up to **200 bytes**, unique among currently-prepared
  xacts), surfaced in **`pg_prepared_xacts`**. [from-docs]
  [cross: knowledge/docs-distilled/two-phase.md]

## Links into corpus
- [[knowledge/subsystems/access-transam.md]] — xid lifecycle, CLOG, snapshot building.
- [[knowledge/files/src/backend/access/transam/varsup.c.md]] — `GetNewTransactionId`, xid counter advance, wraparound limits.
- [[knowledge/files/src/backend/access/transam/transam.c.md]] — `TransactionIdDidCommit/DidAbort`, xid comparison.
- [[knowledge/data-structures/snapshot-lifecycle.md]] — how xmin/xmax/xip use these xids for visibility.
- [[knowledge/data-structures/pgproc-fields.md]] — where the vxid (`procNumber`/`lxid`) lives in PGPROC.
- Skill: `wal-and-xlog` / subsystem `access-transam` — for freezing + wraparound code.

## Gaps / follow-ups
- The page is deliberately thin: it does NOT enumerate the special xids
  (`InvalidTransactionId`=0, `BootstrapTransactionId`=1, `FrozenTransactionId`=2),
  nor xmin/xmax/cid tuple-header fields. Those are corpus-only — cite
  `access-heap.md` / `access-transam.md` for them, not this doc.
