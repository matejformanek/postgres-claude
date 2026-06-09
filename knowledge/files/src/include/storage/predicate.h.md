# `src/include/storage/predicate.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 84

## Role

**Serializable Snapshot Isolation (SSI) public API.** Used by
access methods (heap, btree, GiST, GIN, hash, BRIN) to:

- declare predicate locks on read paths
  (`PredicateLockRelation/Page/TID`)
- detect serialization conflicts at write paths
  (`CheckForSerializableConflictIn/Out`)
- coordinate xact start/end (`GetSerializableTransactionSnapshot`,
  `ReleasePredicateLocks`)
- handle page-split/combine (so predicate locks track the data)
- participate in two-phase commit and parallel query

`predicate_internals.h` is the (large) sibling header used by
the implementation in `predicate.c`.

## Public API surface

[verified-by-code] `source/src/include/storage/predicate.h:31-83`

- **GUCs**: `max_predicate_locks_per_xact`,
  `max_predicate_locks_per_relation`,
  `max_predicate_locks_per_page` (lines 31-33)
- **Maintenance**: `CheckPointPredicate`, `PageIsPredicateLocked`
- **Snapshot**: `GetSerializableTransactionSnapshot`,
  `SetSerializableTransactionSnapshot`,
  `RegisterPredicateLockingXid`
- **Locking**: `PredicateLockRelation/Page/TID`,
  `PredicateLockPageSplit/Combine`,
  `TransferPredicateLocksToHeapRelation`,
  `ReleasePredicateLocks`
- **Conflict detection (may rollback!)**:
  `CheckForSerializableConflictOutNeeded`,
  `CheckForSerializableConflictOut`,
  `CheckForSerializableConflictIn`,
  `CheckTableForSerializableConflictIn`
- **Final commit check**:
  `PreCommit_CheckForSerializationFailure`
- **2PC**: `AtPrepare_PredicateLocks`,
  `PostPrepare_PredicateLocks`,
  `PredicateLockTwoPhaseFinish`,
  `predicatelock_twophase_recover`
- **Parallel query**: `SerializableXactHandle =
  void *` — `ShareSerializableXact()` / `AttachSerializableXact()`

## Invariants

- INV-1: Conflict-check functions can **call `ereport(ERROR,
  …)`** to abort the transaction. Callers must be transactional
  and prepared to long-jump. [from-comment] line 64.
- INV-2: Predicate locks DOWNGRADE silently as memory pressure
  hits the GUC ceilings (tuple → page → relation). The
  result is a higher false-positive rate but never missed
  conflicts. [inferred from `predicate.c` SetNewSxactGlobalXmin
  path]
- INV-3: `SerializableXactHandle` is an opaque pointer (`void *`)
  shared via DSM in parallel queries (lines 36-39, 80-83). Mis-
  attaching across unrelated xacts corrupts the SSI graph.

## Trust boundary (Phase D)

- **`max_predicate_locks_per_*` GUCs are a DoS surface**: low
  values mean predicate locks downgrade more often (higher
  serialization-failure rate); high values mean a single
  attacker xact can exhaust the predicate-lock arena and force
  downgrades on everyone. Already documented as a tuning knob.
- **SSI conflict-rollback is observable**: an attacker
  performing read patterns under SERIALIZABLE can cause
  rollback of innocent victims (DOS by induced
  serialization-failure). Already a known SSI cost.
- **`pg_locks` exposes predicate-lock TIDs** — same
  monitoring-as-oracle cluster as A11/A14. Reading the
  predicate locks of another role's xact reveals which tuples
  it has read.
- **`SerializableXactHandle` opaque void *** — when shared via
  DSM, a buggy/malicious parallel worker could mis-attach. The
  attach is `dsa_pointer`-mediated; cross-extension misuse
  could break SSI guarantees. Internal core code is correct.

## Cross-refs

- `knowledge/files/src/include/storage/predicate_internals.h.md`
- `knowledge/files/src/backend/storage/lmgr/predicate.c.md`
  (if exists)
- `knowledge/subsystems/storage-lmgr.md`
- README: `src/backend/storage/lmgr/README-SSI`

## Issues

- ISSUE-TRUST: `pg_locks` exposure of predicate-lock TIDs
  reveals read patterns of other sessions; mitigation is
  view-level filtering (already partial). (Informational.)
- ISSUE-PHASE-D: an attacker who can run SERIALIZABLE xacts
  can induce serialization-failure rollback on victims by
  contention patterns. Documented behaviour but worth tagging
  for completeness. (Low.)
