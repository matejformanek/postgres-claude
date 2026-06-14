---
source_url: https://www.postgresql.org/docs/current/xact-locking.html
fetched_at: 2026-06-14T19:22:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Transactions and Locking (§67.2)

How a transaction's own xid/vxid become lock objects others can wait on — the
mechanism that lets "wait until that transaction finishes" be expressed as a
plain lock-manager wait. Code lives in `lmgr.c` (`XactLockTableInsert` /
`VirtualXactLockTableInsert` / `XactLockTableWait`) — cite that for the wait
loop.

## xid and vxid both appear in pg_locks

- A running transaction's identifiers surface in **`pg_locks`** as the
  **`virtualxid`** and **`transactionid`** columns. A **read-only** transaction
  has a `virtualxid` but a **NULL `transactionid`** (no real xid yet); a
  **read-write** transaction has both populated. [from-docs]
- **Some lock types wait on `virtualxid`, others on `transactionid`** — the two
  are distinct lockable objects, not aliases. [from-docs]

## Self-held locks: every xact locks its own identifiers

- A transaction holds an **exclusive lock on its own vxid** for its whole
  lifetime, and — once assigned — an exclusive lock on its own **xid**. Anyone
  needing to "wait for transaction T to end" simply tries to acquire a share
  lock on T's vxid/xid; they block until T releases at commit/abort. This is the
  generic "wait on a transaction" primitive. [inferred]
  [verified-by-code, via [[knowledge/files/src/backend/storage/lmgr/lmgr.c.md]]]
- Why two objects: the **vxid lock exists from transaction start** (so you can
  wait on a read-only xact), while the **xid lock only exists after first
  write**. Waiters that must work for read-only transactions (e.g. CREATE INDEX
  CONCURRENTLY waiting out old snapshots) wait on the vxid; waiters keyed on a
  specific writer (e.g. a row-update conflict) wait on the xid. [inferred]
  [cross: knowledge/files/src/backend/storage/lmgr/lock.c.md]

## Row-level locks are recorded in the rows, not the lock table

- **Row-level read/write locks are stored directly in the locked tuples** (in the
  tuple header / xmax), not in the shared lock table — inspect them with the
  **`pgrowlocks`** extension. Keeping per-row locks out of shmem is what lets a
  transaction lock millions of rows without exhausting the lock table. [from-docs]
  [cross: knowledge/subsystems/contrib-pgrowlocks.md]
- A **row-level read (share) lock may require allocating a multixact ID
  (`mxid`)** when several transactions share-lock the same row — the multixact
  machinery has its own wraparound/vacuum concern. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/multixact.c.md]]]

## Links into corpus
- [[knowledge/files/src/backend/storage/lmgr/lmgr.c.md]] — `XactLockTableInsert/Wait`, `VirtualXactLock*`, the per-xact self-lock.
- [[knowledge/files/src/backend/storage/lmgr/lock.c.md]] — the shared lock table, LOCKTAG forms for vxid vs xid.
- [[knowledge/data-structures/locktag.md]] — how a vxid / xid is encoded into a LOCKTAG.
- [[knowledge/files/src/backend/access/transam/multixact.c.md]] — mxid allocation for shared row locks.
- [[knowledge/subsystems/contrib-pgrowlocks.md]] — reading the in-tuple row locks.
- [[knowledge/docs-distilled/transaction-id.md]] — the xid/vxid identifiers being locked.

## Gaps / follow-ups
- The page names the two columns and "some types wait on each" but does NOT
  spell out which lock modes map to vxid vs xid, or the `XactLockTableWait`
  retry-on-subxid logic — that is `lmgr.c` corpus territory.
