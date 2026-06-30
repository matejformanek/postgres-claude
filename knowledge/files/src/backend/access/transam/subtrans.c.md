# subtrans.c

- **Source path:** `source/src/backend/access/transam/subtrans.c`
- **Lines:** 448
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/subtrans.h`, `slru.c`,
  `xact.c` (sets parent pointers via `AssignTransactionId`),
  `procarray.c` (consumer for snapshot xmin resolution).

## Purpose

Stores the immediate parent `TransactionId` for each transaction; used
to resolve a subxid up to its top transaction when a backend's
in-memory subxid cache has overflowed. **No XLOG**: pg_subtrans is
re-zeroed on startup since it only needs to remember open transactions.
[from-comment] `subtrans.c:3-20`.

## Top-of-file comment (verbatim)

```
subtrans.c
   PostgreSQL subtransaction-log manager

The pg_subtrans manager is a pg_xact-like manager that stores the parent
transaction Id for each transaction. ...

This code is based on xact.c, but the robustness requirements
are completely different from pg_xact, because we only need to remember
pg_subtrans information for currently-open transactions.  Thus, there is
no need to preserve data over a crash and restart.

There are no XLOG interactions since we do not care about preserving
data across crashes.  During database startup, we simply force the
currently-active page of SUBTRANS to zeroes.
```
[from-comment] `subtrans.c:3-20`.

## Public surface

- `SubTransSetParent(xid, parent)` — `subtrans.c:92` [verified-by-code]
- `SubTransGetParent(xid)` — declared `subtrans.h:14` [verified-by-code]
- `SubTransGetTopmostTransaction(xid)` — declared `subtrans.h:15`
  [verified-by-code]
- `BootStrapSUBTRANS`, `StartupSUBTRANS(oldestActiveXID)`,
  `CheckPointSUBTRANS`, `ExtendSUBTRANS(newestXact)`,
  `TruncateSUBTRANS(oldestXact)` — declared `subtrans.h:17-21`
  [verified-by-code]

## Key types / constants

- `SUBTRANS_XACTS_PER_PAGE = BLCKSZ / sizeof(TransactionId)` (4 bytes
  per xact). [verified-by-code] `subtrans.c:55`.
- `SubTransSlruDesc` — single SLRU descriptor; access via
  `SubTransCtl`. [verified-by-code] `subtrans.c:83-85`.

## Key invariants and locking

1. **No WAL.** pg_subtrans is volatile across crashes.
   `StartupSUBTRANS` re-zeros the latest page. [from-comment]
   `subtrans.c:18-20`.

2. **Parent set when XID assigned.** `xact.c:AssignTransactionId`
   calls `SubTransSetParent`; top-level transactions have parent
   `InvalidTransactionId`. [from-README] (README:378-382).

3. **Asserts parent < child.** Maintains the README's
   "child > parent" invariant. [verified-by-code]
   `subtrans.c:100`.

4. **SLRU bank-lock semantics.** Inherited from `slru.c`. The bank
   lock is taken in exclusive mode for write, shared for reads.

5. **Recovery emulation simplification.** During recovery, all
   subtransactions reference the top-level XID directly; pg_subtrans
   is updated but the tree shape is flattened.
   [from-README] (README:907-910).

## Functions of note

### `SubTransSetParent` — `subtrans.c:92-…` [verified-by-code]

Stores parent at byte offset `entryno * sizeof(TransactionId)` in
the page. Uses `SimpleLruReadPage` (exclusive) and dirties the page.

### `SubTransGetTopmostTransaction` — declared `subtrans.h:15`
[verified-by-code]

Walks the parent chain. The body (in this file but not deep-read
here) iterates until the page returns `InvalidTransactionId`.

### `ExtendSUBTRANS` — declared `subtrans.h:20` [verified-by-code]

Called from `varsup.c:GetNewTransactionId` (under `XidGenLock`) to
zero a new SUBTRANS page when crossing a page boundary.

### `TruncateSUBTRANS` — declared `subtrans.h:21` [verified-by-code]

Called by vacuum after `latestCompletedXid` and `OldestXmin` advance
sufficiently; trims old SLRU segments. No WAL record (no
crash-recovery need).

## Cross-references

- `varsup.c:GetNewTransactionId` calls `ExtendSUBTRANS`.
- `xact.c:AssignTransactionId` calls `SubTransSetParent`.
- `procarray.c` consumes `SubTransGetTopmostTransaction` when checking
  if an XID belongs to a snapshot's transaction tree (after subxid
  cache overflow).
- `slru.c` provides storage.

## Open questions

- `SubTransPagePrecedes` wraparound semantics (it returns true if
  `page1` precedes `page2` in XID-space wraparound) not re-verified
  here. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 12
- `[from-comment]`: 2
- `[from-README]`: 2
- `[unverified]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/subtransaction-stack.md](../../../../../idioms/subtransaction-stack.md)
- [idioms/subxact-subtrans-slru.md](../../../../../idioms/subxact-subtrans-slru.md)

