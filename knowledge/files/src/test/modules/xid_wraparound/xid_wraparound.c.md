---
path: src/test/modules/xid_wraparound/xid_wraparound.c
anchor_sha: e18b0cb7344
loc: 219
depth: read
---

# src/test/modules/xid_wraparound/xid_wraparound.c

## Purpose

Test-only XID burner: consumes transaction IDs at speed so the TAP
test suite can drive the cluster up to (and past) wraparound boundaries
without waiting for natural traffic to do it. Provides two SQL-callable
functions — `consume_xids(nxids)` and `consume_xids_until(targetxid)` —
that allocate XIDs as subtransactions of the calling top-level
transaction, taking a fast-path shortcut by directly bumping
`TransamVariables->nextXid` when far from any "interesting" boundary
(SLRU page edges or the uint32 wrap point). `[verified-by-code]`
`xid_wraparound.c:1-13,164-169`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `consume_xids(int8) returns xid8` | `:32` | Consume N XIDs; returns the last `FullTransactionId` allocated |
| `consume_xids_until(xid8) returns xid8` | `:53` | Consume until `nextXid >= target`; returns last XID |

## Internal landmarks

- `consume_xids_common` (`:71`) — the workhorse. Calls
  `GetTopTransactionId()` (`:92`) to ensure the calling transaction has
  a real XID — required because `GetNewTransactionId(true)` registers
  the consumed XIDs as subxids of the top-level XID; without one, the
  subxid linkage is wrong.
- Shortcut decision (`:114-129`) — when `xids_left > 2000`, the
  progress-report cooldown hasn't fired, and `MyProc->subxidStatus`
  has **overflowed** the in-PROC subxid cache (so no more cache bloat
  per XID), call the fast-path.
- `XidSkip` (`:170`) — given the current `FullTransactionId`, compute
  the maximum number of XIDs we can safely skip without crossing into
  the "interesting zone" 5 XIDs from a `COMMIT_TS_XACTS_PER_PAGE` /
  `SUBTRANS_XACTS_PER_PAGE` / `CLOG_XACTS_PER_PAGE` boundary or
  `UINT32_MAX - 5`. Returns 0 when already in such a zone.
- `consume_xids_shortcut` (`:200`) — under `XidGenLock LW_EXCLUSIVE`,
  read `TransamVariables->nextXid`, compute `XidSkip`, advance
  `nextXid.value` by that many directly.
- SLRU page-size constants (`:159-162`) are copied from the .c files
  that own them (CLOG / commit-ts / subtrans) because they are private
  there `[from-comment]` `:156-157`.
- Progress reporting: every `REPORT_INTERVAL = 10_000_000` consumed XIDs
  emits a NOTICE with current vs target XID (`:135-149`).

## Invariants & gotchas

- TEST MODULE — never load in production. Burning XIDs is destructive:
  it advances the cluster toward wraparound, requiring expensive
  vacuum work to recover.
- Shortcut only fires once `MyProc->subxidStatus.overflowed` is true,
  i.e. after the in-memory subxid cache is full. Before that, slow-path
  `GetNewTransactionId(true)` runs and naturally fills the cache.
- Shortcut respects "interesting zones" because the SLRU extension code
  in `GetNewTransactionId` runs at page boundaries and the wraparound
  check fires near `UINT32_MAX`. Skipping these would leave SLRU pages
  un-extended and corrupt the cluster. The `+/- 5 XID` skirt is a
  conservative margin.
- `consume_xids(0)` short-circuits to `ReadNextFullTransactionId` for a
  no-op probe (`:40-41`).

## Cross-refs

- `source/src/backend/access/transam/varsup.c` — `GetNewTransactionId`,
  `TransamVariables`, `XidGenLock`.
- `source/src/include/storage/proc.h` — `MyProc->subxidStatus`.
- `source/src/backend/access/transam/clog.c`,
  `source/src/backend/access/transam/commit_ts.c`,
  `source/src/backend/access/transam/subtrans.c` — the SLRU page
  constants the shortcut must respect.
- `knowledge/subsystems/wal-and-xlog.md` — XID generation in context.
