# transam.c

- **Source path:** `source/src/backend/access/transam/transam.c`
- **Lines:** 341
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `clog.c` (storage), `subtrans.c` (subxact parent),
  `procarray.c` (in-progress check), `heapam_visibility.c` (caller).

## Purpose

High-level "did this XID commit / abort" interface on top of pg_xact.
Implements per-backend single-item cache, `TransactionIdDidCommit`,
`TransactionIdDidAbort`, the tree-status setters used by xact.c, and
the topmost-XID resolver used by visibility checks.
[from-comment] `transam.c:3-14, 96-115`.

## Top-of-file comment (verbatim)

```
transam.c
   postgres transaction (commit) log interface routines

NOTES
   This file contains the high level access-method interface to the
   transaction system.
```
[from-comment] `transam.c:3-15`.

## Public surface

- `TransactionIdDidCommit(xid)` — `transam.c:126` [verified-by-code]
- `TransactionIdDidAbort(xid)` — `transam.c:188` [verified-by-code]
- `TransactionIdCommitTree(xid, nxids, xids)` — `transam.c:240`
  [verified-by-code]
- `TransactionIdAsyncCommitTree(xid, nxids, xids, lsn)` —
  `transam.c:252` [verified-by-code]
- `TransactionIdAbortTree(xid, nxids, xids)` — `transam.c:270`
  [verified-by-code]
- `TransactionIdLatest(mainxid, …)` — `transam.c:281` [verified-by-code]
- `TransactionIdGetCommitLSN(xid)` — `transam.c:318` [verified-by-code]

## Key types / globals

- `cachedFetchXid`, `cachedFetchXidStatus`, `cachedCommitLSN` — the
  per-backend single-entry cache. [verified-by-code] `transam.c:61-90`.

## Key invariants and locking

1. **Permanent XIDs short-circuit.** `BootstrapTransactionId` and
   `FrozenTransactionId` always return COMMITTED; anything else
   non-`Normal` returns ABORTED. [verified-by-code] `transam.c:67-74`.

2. **Cache only stable answers.** Status is cached only when not
   `IN_PROGRESS` and not `SUB_COMMITTED`. [from-comment]
   `transam.c:82-90`.

3. **Sub-committed status resolution.** `TransactionIdDidCommit`
   recurses to the parent via `SubTransGetParent`. If the parent is
   older than `TransactionXmin`, pg_subtrans cannot be consulted and
   the function emits a WARNING and assumes the parent crashed
   (returns false). [from-comment] `transam.c:138-150`.

4. **The "is in progress" check is *not* here** — `procarray.c`
   owns `TransactionIdIsInProgress`. [from-comment] `transam.c:112-115`.

## Functions of note

### `TransactionLogFetch` — `transam.c:52-94` [verified-by-code]

The pg_xact lookup helper with the single-item cache. Calls
`TransactionIdGetStatus` (`clog.c:744`).

### `TransactionIdDidCommit` — `transam.c:126-…` [verified-by-code]

The main visibility helper. Walks pg_subtrans for SUB_COMMITTED
status; returns false (with WARNING) when pg_subtrans is unreachable.

### `TransactionIdCommitTree` / `…AsyncCommitTree` / `…AbortTree` —
`transam.c:240-280` [verified-by-code]

Thin wrappers over `clog.c:TransactionIdSetTreeStatus` that select
COMMITTED / async-commit-with-LSN / ABORTED semantics. The async
variant carries the commit LSN so clog can track it for the
WAL-before-clog-page-write rule.

### `TransactionIdLatest` — `transam.c:281-…` [verified-by-code]

Given a top XID and its sorted subxid array, returns the largest
known XID in the tree. Used by `xact.c:RecordTransactionCommit` to
compute `latestXid` for `ProcArrayEndTransaction`.

## Cross-references

- `heapam_visibility.c` is the heavy reader (`HeapTupleSatisfies*`).
- `xact.c:RecordTransactionCommit` (`xact.c:1345`) calls
  `TransactionIdCommitTree` / `…AsyncCommitTree`.
- `xact.c:RecordTransactionAbort` (`xact.c:1796`) calls
  `TransactionIdAbortTree`.
- `procarray.c:TransactionIdIsInProgress` is consulted *before* this
  module in visibility logic (see `heapam_visibility.c`).
- `subtrans.c:SubTransGetParent` resolves SUB_COMMITTED parents.

## Open questions

- None significant; small file, well-anchored.

## Confidence tag tally

- `[verified-by-code]`: 14
- `[from-comment]`: 4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
