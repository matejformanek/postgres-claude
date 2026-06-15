---
source_url: https://www.postgresql.org/docs/current/two-phase.html
fetched_at: 2026-06-14T19:23:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Two-Phase Transactions (§67.4)

The orientation page for PREPARE TRANSACTION and the on-disk/shmem split of
prepared-xact state. The state-file format, the dummy PGPROC, and recovery
re-acquisition of locks live in `twophase.c.md` — cite that for the gory parts.

## The three commands and the frozen state

- 2PC is driven by **`PREPARE TRANSACTION`**, **`COMMIT PREPARED`**, and
  **`ROLLBACK PREPARED`**. After `PREPARE TRANSACTION`, the **only** valid
  follow-ups are `COMMIT PREPARED` / `ROLLBACK PREPARED` — the session is
  otherwise out of a transaction. [from-docs]
- The prepared state is **meant to be short-lived**, but external coordinator
  (XA transaction-manager) availability problems can leave a transaction
  prepared for a long time — which is operationally dangerous (see cliff below). [from-docs]

## Where prepared state lives: shmem + WAL, then pg_twophase

- A freshly-prepared transaction's state is held in **shared memory and WAL**. If
  it survives a **checkpoint** (i.e. becomes long-lived), its state is written
  out to the **`pg_twophase/`** directory so it persists across server restart
  and is no longer pinned to a WAL segment. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/twophase.c.md]]]
- This shmem→file migration on checkpoint is why a prepared xact survives a crash
  *and* doesn't hold WAL hostage forever — recovery rebuilds the in-memory
  prepared-xact entries (and re-acquires their locks) from these files. [inferred]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/twophase_rmgr.c.md]]]

## Why an abandoned prepared xact is dangerous

- A prepared transaction **retains its xid and continues to hold all its locks**
  via a stand-in (dummy) PGPROC entry. An abandoned one therefore **blocks
  VACUUM from advancing the xmin horizon** → table bloat and, eventually,
  **transaction-ID wraparound risk** — the standard "orphaned prepared xact"
  outage. Monitor **`pg_prepared_xacts`**. [inferred]
  [cross: knowledge/data-structures/pgproc-fields.md]
- Capacity is bounded by **`max_prepared_transactions`** (0 disables 2PC
  entirely; must be ≥ the number of concurrent prepared xacts you expect, and is
  often set equal to `max_connections`). [inferred]

## Standard conformance

- PostgreSQL implements the **X/Open XA** distributed-transaction protocol for
  2PC, omitting some rarely-used XA aspects. Each prepared xact carries the
  string **GID** introduced in §67.1. [from-docs]
  [cross: knowledge/docs-distilled/transaction-id.md]

## Links into corpus
- [[knowledge/files/src/backend/access/transam/twophase.c.md]] — PREPARE/COMMIT PREPARED, the pg_twophase state file, dummy PGPROC, lock re-acquire on recovery.
- [[knowledge/files/src/backend/access/transam/twophase_rmgr.c.md]] — the 2PC rmgr callbacks replayed during recovery.
- [[knowledge/data-structures/pgproc-fields.md]] — the stand-in PGPROC that holds the prepared xact's xid + locks.
- [[knowledge/subsystems/access-transam.md]] — how 2PC fits the CLOG/commit machinery.
- [[knowledge/docs-distilled/transaction-id.md]] — GID and the xid the prepared xact retains.

## Gaps / follow-ups
- The page does not name `max_prepared_transactions`, the dummy-PGPROC
  mechanism, or the wraparound consequence explicitly — those are inferred from
  the corpus and tagged as such. The pg_twophase file format is `twophase.c`
  corpus-only.
