# src/include/replication/logicalctl.h

## Purpose

Cluster-wide on/off control for the "WAL carries enough info for logical
decoding" mode. The interface is small: enable/disable, query state,
and propagate the bit to every backend via a process barrier.

## Role in PG

- Sits between the `wal_level` GUC and every backend that emits WAL.
  When logical decoding is enabled, callers that write WAL must include
  extra info (full-page heap inserts under REPLICA IDENTITY FULL, origin
  data, etc.).
- Loaded at startup via `StartupLogicalDecodingStatus(last_status)`
  (line 17) from control-file persisted state.
- Each backend caches the current setting via
  `InitializeProcessXLogLogicalInfo` (line 18); the cache is invalidated
  on barrier via `ProcessBarrierUpdateXLogLogicalInfo` (line 19).
- `EnsureLogicalDecodingEnabled` (line 23) is the synchronous "flip it
  on now" path, called when creating a logical replication slot.

## Key types/struct fields

This header is API-only — no public structs. The functions split into:

- Query: `IsLogicalDecodingEnabled` (line 20), `IsXLogLogicalInfoEnabled`
  (line 21).
- Lifecycle: `EnableLogicalDecoding` (line 24),
  `RequestDisableLogicalDecoding` (line 25),
  `DisableLogicalDecodingIfNecessary` (line 26),
  `DisableLogicalDecoding` (line 27).
- Recovery / end-of-recovery: `UpdateLogicalDecodingStatusEndOfRecovery`
  (line 28), `AtEOXact_LogicalCtl` (line 22).
- Process-startup wiring: `StartupLogicalDecodingStatus`,
  `InitializeProcessXLogLogicalInfo`,
  `ProcessBarrierUpdateXLogLogicalInfo`.

## Phase D notes

- The Enable/RequestDisable/DisableIfNecessary triplet implies a
  two-phase shutdown: request, then later check whether disable is
  safe (i.e., no live slots). The header doesn't document the ordering
  contract — the .c file does.
- `ProcessBarrierUpdateXLogLogicalInfo` returning `bool` is the standard
  PG barrier-handler signature: TRUE if the barrier was successfully
  absorbed. Backends that fail to absorb keep using stale state, which
  is a hazard if the operator just disabled logical decoding to free
  disk space.

## Potential issues

- [ISSUE-state-transition: header gives no guarantee on what
  `IsLogicalDecodingEnabled()` returns mid-barrier. Backends sampling it
  between `RequestDisableLogicalDecoding` and the matching
  `ProcessBarrierUpdateXLogLogicalInfo` can race. (maybe)]
- [ISSUE-undocumented-invariant: relationship between this control flag
  and the `wal_level` GUC is invisible from the header — is it a strict
  AND? Can an operator disable logical decoding while `wal_level=logical`?
  Needs commit/log archaeology. (maybe)]
- [ISSUE-dos: `DisableLogicalDecoding` with active slots presumably
  errors out, but a stuck slot (subscriber gone) could pin the
  cluster in logical mode indefinitely; operators must drop the slot
  first. Standard PG slot-leak gotcha, but worth flagging here. (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/replication.md](../../../../subsystems/replication.md)
