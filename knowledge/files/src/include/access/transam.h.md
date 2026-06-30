# transam.h

- **Source path:** `source/src/include/access/transam.h`
- **Lines:** 478
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `transam.c`, `varsup.c`, `xlogdefs.h`.

## Purpose

The lowest-level transaction-ID arithmetic and shared `TransamVariables`
struct. Defines the special XIDs, the `FullTransactionId` 64-bit
wrapper, all wraparound-safe comparison primitives, and the prototypes
for `transam.c` / `varsup.c` / `xact.c`. [from-comment] `transam.h:3-4`.

## Top-of-file comment (verbatim)

```
transam.h
   postgres transaction access method support code
```
[verified-by-code] `transam.h:3-4`.

## Public surface

### Special XIDs (`transam.h:31-35`) [verified-by-code]

```
InvalidTransactionId       = 0
BootstrapTransactionId     = 1
FrozenTransactionId        = 2
FirstNormalTransactionId   = 3
MaxTransactionId           = 0xFFFFFFFF
```

### Macros (`transam.h:41-58`) [verified-by-code]

`TransactionIdIsValid`, `TransactionIdIsNormal`, `TransactionIdEquals`,
`TransactionIdStore`, `StoreInvalidTransactionId`,
`EpochFromFullTransactionId`, `XidFromFullTransactionId`,
`U64FromFullTransactionId`, `FullTransactionIdEquals`,
`FullTransactionIdPrecedes(OrEquals)`, `FullTransactionIdFollows(OrEquals)`,
`FullTransactionIdIsValid`, `InvalidFullTransactionId`,
`FirstNormalFullTransactionId`, `FullTransactionIdIsNormal`.

### Inline arithmetic (`transam.h:70-138`) [verified-by-code]

`FullTransactionIdFromEpochAndXid`, `FullTransactionIdFromU64`,
`TransactionIdAdvance` (macro, skips back to `FirstNormal`),
`FullTransactionIdRetreat` / `FullTransactionIdAdvance`
(skip XIDs that look special only at 32-bit),
`TransactionIdRetreat`.

### Normal-only fast comparisons (`transam.h:147-154`) [verified-by-code]

`NormalTransactionIdPrecedes(id1, id2) = (int32)(id1 - id2) < 0` with
asserts. `NormalTransactionIdFollows` likewise.

### Wraparound-safe comparisons (`transam.h:262-321`) [verified-by-code]

`TransactionIdPrecedes`, `TransactionIdPrecedesOrEquals`,
`TransactionIdFollows`, `TransactionIdFollowsOrEquals`. Each falls
back to unsigned compare if either operand is non-Normal; otherwise
modulo-2^32 signed diff.

### OID generator constants (`transam.h:195-197`) [verified-by-code]

```
FirstGenbkiObjectId      = 10000
FirstUnpinnedObjectId    = 12000
FirstNormalObjectId      = 16384
```

### Inline helpers (`transam.h:374-475`, backend only) [verified-by-code]

`ReadNextTransactionId`, `TransactionIdRetreatedBy`,
`TransactionIdOlder`, `NormalTransactionIdOlder`,
`FullTransactionIdNewer`, `FullTransactionIdFromAllowableAt`.

### Extern prototypes

- `transam.c`: `TransactionIdDidCommit`, `TransactionIdDidAbort`,
  `TransactionIdCommitTree`, `TransactionIdAsyncCommitTree`,
  `TransactionIdAbortTree`, `TransactionIdLatest`,
  `TransactionIdGetCommitLSN`. [verified-by-code]
  `transam.h:338-345`.
- `varsup.c`: `GetNewTransactionId`,
  `AdvanceNextFullTransactionIdPastXid`, `ReadNextFullTransactionId`,
  `SetTransactionIdLimit`, `AdvanceOldestClogXid`,
  `ForceTransactionIdLimitUpdate`, `GetNewObjectId`,
  `StopGeneratingPinnedObjectIds`,
  `AssertTransactionIdInAllowableRange` (`#ifdef
  USE_ASSERT_CHECKING`). [verified-by-code] `transam.h:347-362`.
- `xact.c`: `TransactionStartedDuringRecovery`. [verified-by-code]
  `transam.h:330`.

## Key types / structs

### `FullTransactionId` (`transam.h:65-68`) [verified-by-code]

`struct FullTransactionId { uint64 value; }` — opaque wrapper that
prevents implicit conversion to/from `TransactionId`. Top 32 bits are
the epoch, low 32 bits the XID.

### `TransamVariablesData` (`transam.h:209-255`) [verified-by-code]

Shared-memory state partitioned by lock:

- **OidGenLock**: `nextOid`, `oidCount`.
- **XidGenLock**: `nextXid`, `oldestXid`, `xidVacLimit`,
  `xidWarnLimit`, `xidStopLimit`, `xidWrapLimit`, `oldestXidDB`.
- **CommitTsLock**: `oldestCommitTsXid`, `newestCommitTsXid`.
- **ProcArrayLock**: `latestCompletedXid`, `xactCompletionCount`.
- **XactTruncationLock**: `oldestClogXid`.

[from-comment] `transam.h:200-208` ("For largely historical reasons,
there is just one struct with different fields protected by different
LWLocks.").

## Key invariants and locking

1. **Wraparound-safe comparison rule.** When both XIDs are normal,
   compare via `(int32)(a - b)` signed diff. Otherwise fall back to
   unsigned. [verified-by-code] `transam.h:262-321`.

2. **Skipping special XIDs on advance/retreat.** Both
   `TransactionIdAdvance` and `FullTransactionIdAdvance` jump over
   XIDs 0/1/2 when wrapping. [verified-by-code] `transam.h:91-138`.

3. **`xactCompletionCount` is monotonic and ≥1.** Used by
   `GetSnapshotData` to skip recomputation when nothing changed.
   [from-comment] `transam.h:241-247`.

4. **OID generator categories** — 0/InvalidOid, 1-9999 manual,
   10000-11999 genbki, 12000-16383 initdb-post-bootstrap, ≥16384
   normal. Wrap skips back to 16384 so no user object is mistaken
   for pinned. [from-comment] `transam.h:156-193`.

5. **`FullTransactionIdFromAllowableAt`** comment proves correctness:
   "we must remove (by freezing) an XID before assigning the XID half
   an epoch ahead of it." [from-comment] `transam.h:453-458`.

## Cross-references

- `varsup.c` implements all the prototypes.
- `transam.c` implements the commit-log fetches.
- `procarray.c` reads `latestCompletedXid` and
  `xactCompletionCount`.
- `xlogdefs.h` provides `XLogRecPtr` used here in `LSN`-returning
  protos.

## Open questions

- `FrozenTransactionId`'s significance vs FRoZEN tuples (heap-level
  concept) — implementation detail in heap visibility, not here.
  [inferred]

## Confidence tag tally

- `[verified-by-code]`: 26
- `[from-comment]`: 5
- `[inferred]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [idioms/catalog-conventions.md](../../../../idioms/catalog-conventions.md)
- [idioms/heap-tuple-freeze.md](../../../../idioms/heap-tuple-freeze.md)
