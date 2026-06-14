---
source_url: https://www.postgresql.org/docs/current/subxacts.html
fetched_at: 2026-06-14T19:21:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Subtransactions (§67.3)

The orientation page for subxids, the savepoint tree, and the 64-subxid
performance cliff. Code-level mechanics (the pg_subtrans SLRU, the PGPROC
cache and its overflow flag) live in `subtrans.c.md` and the proc data-structure
docs — cite those for anything beyond the shape below.

## What a subtransaction is and how one starts

- A **subtransaction (subxact)** is a nested transaction inside a parent; it can
  **commit or abort independently** of the parent. Started by **`SAVEPOINT`**,
  the **PL/pgSQL `EXCEPTION` clause**, or explicit subtransaction support in
  PL/Python / PL/Tcl. Subxacts can nest arbitrarily. [from-docs]
- Each `EXCEPTION` block in PL/pgSQL is a subtransaction — the reason a tight
  loop of exception-trapping blocks is a known subxid-churn pattern. [inferred]

## subxid assignment mirrors the top-level xid rule

- A **read-only subxact gets no subxid**. The moment it writes, it is assigned a
  subxid — and the assignment **cascades up**: every ancestor up to and including
  the top-level transaction gets a real (non-virtual) xid. [from-docs]
- **Invariant: a parent's xid is always lower than any of its children's
  subxids** — the tree is numbered in creation order. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/subtrans.c.md]]]

## The savepoint tree and pg_subtrans

- Top-level xact = root; subxacts = nodes. The **parentage is recorded in
  `pg_subtrans/`** (an SLRU). **No entry** is written for top-level xids (no
  parent) or for read-only subxacts (no subxid). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/transam/subtrans.c.md]]]

## Commit/abort semantics — subcommitted is provisional

- On **subxact commit**: its committed children with subxids are marked
  **subcommitted** (a provisional state, NOT durable commit). [from-docs]
- On **subxact abort**: it and its children are marked **aborted**. [from-docs]
- On **top-level commit**: all subcommitted descendants are durably recorded
  **committed** in `pg_xact/`. On **top-level abort**: *everything* aborts,
  regardless of any subcommitted state. This is why a subxact's "commit" only
  becomes real when its top-level xact commits. [from-docs]

## The 64-subxid performance cliff

- Up to **`PGPROC_MAX_CACHED_SUBXIDS` = 64** open subxids are cached in shared
  memory per backend. Beyond 64 concurrently-open subxids the cache
  **overflows**, and visibility checks must fall back to **`pg_subtrans`
  lookups** — a measurable storage-I/O cost. Keeping concurrent open
  subtransactions under 64 per backend is the practical guidance. [from-docs]
  [verified-by-code, via [[knowledge/data-structures/pgproc-fields.md]]]

## Links into corpus
- [[knowledge/files/src/backend/access/transam/subtrans.c.md]] — the pg_subtrans SLRU, `SubTransGetParent`, `SubTransGetTopmostTransaction`.
- [[knowledge/files/src/backend/access/transam/xact.c.md]] — `BeginInternalSubTransaction`, the in-memory TransactionState stack.
- [[knowledge/data-structures/pgproc-fields.md]] — the subxid cache fields + `overflowed` flag in PGPROC / its XID array.
- [[knowledge/data-structures/snapshot-lifecycle.md]] — how snapshots account for subxids (suboverflowed → consult pg_subtrans).
- [[knowledge/docs-distilled/transaction-id.md]] — the top-level xid/vxid companion.

## Gaps / follow-ups
- The page names `PGPROC_MAX_CACHED_SUBXIDS` and the cliff but not the
  `suboverflowed` snapshot flag by name, nor the SLRU page-buffer count.
  Cite `snapshot-lifecycle.md` / `subtrans.c.md` for the snapshot-side handling.
