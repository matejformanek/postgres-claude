---
source_url: https://www.postgresql.org/docs/current/transactions.html
also_referenced:
  - https://www.postgresql.org/docs/current/transaction-id.html
  - https://www.postgresql.org/docs/current/xact-locking.html
  - https://www.postgresql.org/docs/current/subxacts.html
  - https://www.postgresql.org/docs/current/two-phase.html
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 67: Transaction Processing

The internals-facing transaction chapter: how PG names transactions (VXID vs
XID), why writes are what cost an XID, how subtransactions and two-phase commit
are represented. This is the doc that makes the `snapshot-lifecycle` and
`access-transam` corpus material legible. Constants below verified at the anchor.

## VXID vs XID (67.1) — the key distinction

- **Every transaction has a `VirtualTransactionId` (vxid) immediately**, formed as
  `procNumber/localXID`. Exact docs phrasing: "Every transaction is identified by
  a unique `VirtualTransactionId` … comprised of a backend's process number (or
  `procNumber`) and a sequentially-assigned number local to each backend, known as
  `localXID`. For example, the virtual transaction ID `4/12532` has a `procNumber`
  of `4` and a `localXID` of `12532`." [from-docs — exact]
- **A real `xid` is assigned lazily — only on first write.** "Non-virtual
  `TransactionId`s … are assigned sequentially … from a global counter used by all
  databases … This assignment happens when a transaction first writes to the
  database." So **read-only transactions never consume an XID** — that is the whole
  reason VXIDs exist (a counter shared cluster-wide must not burn through 2^32 on
  read traffic). [from-docs — exact]
- **First-write order ≠ start order.** "the order in which transactions perform
  their first database write might be different from the order in which the
  transactions started, particularly if the transaction started with statements
  that only performed database reads." Lower xid ⇒ started *writing* earlier, not
  necessarily *started* earlier. [from-docs — exact]
- **xid is 32-bit and wraps; xid8 is 64-bit and doesn't.** "The internal
  transaction ID type `xid` is 32 bits wide and wraps around every 4 billion
  transactions. A 32-bit epoch is incremented during each wraparound. There is also
  a 64-bit type `xid8` which includes this epoch and therefore does not wrap around
  during the life of an installation; it can be converted to xid by casting."
  [from-docs — exact]
- **Special reserved XIDs** (not in the prose, but the values these comparisons
  rest on): `InvalidTransactionId = 0`, `BootstrapTransactionId = 1`,
  `FrozenTransactionId = 2`, `FirstNormalTransactionId = 3`.
  [verified-by-code, source/src/include/access/transam.h:31-34]

## Locking (67.2)

- Locking is **relation-level and tuple-level**; `pg_locks` exposes current locks.
  [from-docs]
- **Locking a specific tuple takes an XID lock**: a row lock is implemented by the
  locker advertising its (real) transaction ID against the tuple, so a waiter
  blocks on the holder's XID. This is why `SELECT ... FOR UPDATE` forces an XID to
  be assigned even though the surrounding statement "only reads." [from-docs/inferred]
  [via knowledge/subsystems/storage-lmgr.md, knowledge/data-structures/pgproc-fields.md]

## Subtransactions (67.3)

- Subtransactions = **savepoints**; each gets its own XID when it writes, with a
  parent/child relationship to the enclosing (sub)transaction. [from-docs]
- **Each backend caches up to `PGPROC_MAX_CACHED_SUBXIDS = 64` subxids in its
  PGPROC**; beyond that the cache **overflows** and lookups must fall back to
  `pg_subtrans` on disk — the well-known "subxid overflow" performance cliff.
  [from-docs] [verified-by-code, source/src/include/storage/proc.h:43 —
  `#define PGPROC_MAX_CACHED_SUBXIDS 64 /* XXX guessed-at value */`]
  [via knowledge/data-structures/pgproc-fields.md]

## Two-phase commit (67.4)

- `PREPARE TRANSACTION '<gid>'` dissociates the transaction from the session and
  persists its state so it survives restart; the **GID** is a free-text global
  identifier the client chooses. [from-docs]
- Prepared state is written under **`pg_twophase/`** and replayed/recovered at
  startup; a prepared xact holds its locks and XID until `COMMIT PREPARED` /
  `ROLLBACK PREPARED`. [from-docs] [via knowledge/subsystems/access-transam.md]

## Links into corpus

- [[knowledge/data-structures/snapshot-lifecycle.md]] — how xmin/xmax horizons and
  the in-progress XID set (incl. cached subxids) drive visibility.
- [[knowledge/data-structures/pgproc-fields.md]] — the PGPROC subxid cache and
  `xid`/`xmin` advertisement this chapter describes.
- [[knowledge/subsystems/access-transam.md]] — `xact.c`/`xlog.c`/`twophase.c`,
  the code behind XID assignment and 2PC.
- [[knowledge/subsystems/storage-lmgr.md]] — the tuple/relation lock machinery of
  §67.2.
- [[knowledge/docs-distilled/mvcc.md]] — the visibility side that consumes these IDs.

## Gaps / follow-ups

- The xact-locking (67.2) and two-phase (67.4) subpages were read at chapter depth
  only; the deep file-level treatment lives in `access-transam.md`. The
  `xid8`/`FullTransactionId` epoch handling and `pg_current_xact_id*` SRFs are
  worth a focused `knowledge/data-structures/fullxid.md` note (not yet written).
