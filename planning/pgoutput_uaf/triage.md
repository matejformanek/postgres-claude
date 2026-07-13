# Phase 1 triage — pgoutput_uaf

## Target selection

**Chosen:** `b46efe90482` — pgoutput RelationSyncCache UAF
(Vignesh C author, Sawada co-author, 2025-10-09, back-patched-through
PG15).

## Why this target

**The L7 stress test.** The commit message names
`MemoryContextRegisterResetCallback` as the fix mechanism. This is
the first calibration target whose upstream fix is *known* to be a
memory-context reset callback approach — an ideal validation venue
for L7 (the "if callback-based, name the 3 implementation details
in plan §7" sub-block that landed in commit `eb838af6` earlier
today).

If the blind trilogy:
1. Enumerates approach E under L6 as the recommended approach, AND
2. Names the L7 sub-block details (storage location + function
   shape + ownership) in plan §7, AND
3. Ships an implementation whose 3 detail choices match Tom's
   upstream fix,

then the L6+L7 codification is delivering on its intended value.
Any of those failing is diagnostic.

## Comparison against 4 prior calibration wins

|                       | jsonpath_leak | pgstat_progress | nodesubplan | fdw_directmodify | **pgoutput_uaf** |
|-----------------------|---------------|-----------------|-------------|------------------|------------------|
| Subsystem             | utils/adt/jsonpath | utils/activity | executor    | contrib/postgres_fdw | **replication/pgoutput** |
| Bug shape             | transient-lifetime leak | redundant init | ownership-boundary | PG_TRY-not-enough | **UAF (retry after error)** |
| Diff size             | +362/-233 | -2       | +33/-43     | +35/-27          | **+24/-5**        |
| Signal shape          | quadratic RSS | per-worker cumulative | per-hash-probe query lifespan | session-lifespan libpq | **crash on retry** |
| L6 approach-E trigger | n/a (struct) | n/a (2-line) | fires        | fires            | **fires**         |
| L7 callback-detail trigger | n/a    | n/a             | n/a         | fires (post-hoc) | **fires (up-front)** |

Novelty:
1. First replication-subsystem target.
2. First UAF-shape bug (all prior four were leaks).
3. First target whose fix is *documented* to use
   `MemoryContextRegisterResetCallback` — so L7 has an unambiguous
   validation criterion (does the blind plan name the same 3
   detail choices?).
4. Smallest diff so far (+24/-5) — validates the trilogy on the
   tight end of the spectrum too.

## Blast-radius estimate

- **Direct edits:** `pgoutput.c` — one struct extension (add a
  `MemoryContextCallback` field to `PGOutputData` per F34), one
  registration site in `pgoutput_startup`, one reset callback
  function that NULLs `RelationSyncCache`. Total ~20-30 lines.
- **Callers:** none — pgoutput is a plugin loaded via callback
  registration, no direct callers.
- **Sister leaks:** the commit mentions similar issues in v13/v14
  that they chose not to back-port; out of our calibration scope.
- **On-disk / catalog / WAL / concurrency:** none.

## Reproducer recipe (validated in Phase 0 baseline.md)

```sql
-- Set wal_level=logical, restart.
CREATE TABLE t (id int, val text);
INSERT INTO t VALUES (1, 'row1');
CREATE PUBLICATION p FOR TABLE t;
SELECT pg_create_logical_replication_slot('s', 'pgoutput');

-- Invocation 1: fail during pgoutput plugin invocation
SELECT * FROM pg_logical_slot_get_binary_changes(
    's', NULL, NULL,
    'proto_version', '4',
    'publication_names', 'p_nonexistent');   -- errors

-- Invocation 2: valid publication, same slot
-- On parent-pin: UAF (crash / assert / garbage)
-- On post-fix: clean output
SELECT count(*) FROM pg_logical_slot_get_binary_changes(
    's', NULL, NULL,
    'proto_version', '4',
    'publication_names', 'p');
```

Signal: crash / `FailedAssertion(MemoryContextIsValid...)` on
parent-pin invocation 2. Silent success on post-fix.

Under macOS + cassert + `MALLOC_PERTURB_=209`, freed memory is
poisoned, so the UAF is likely to trip an assertion or SIGSEGV
reliably. Under some allocator states the second invocation may
complete with silently corrupted output rather than crashing.

## Phase 2 handoff

- Read baseline.md for the semantic bug etiology.
- Read the parent-pin `pgoutput.c` freely — the fix is entirely in
  this one file per the commit's `--stat`.
- BLIND CONSTRAINT: do NOT read `b46efe90482` diff, discussion
  thread, or the 4 prior calibration outputs during Phases 2-3.
- Enter `pg-feature-brainstorm` next.
- **L6 approach-E MUST fire** (fix is documented as reset callback).
- **L7 sub-block MUST fire in plan §7** (fix is callback-based per
  commit message).
- F30 grep-pass over `RelationSyncCache` acquisition + release +
  reference sites.
- F37 target-suite: none applicable; R13 = core regress + isolation.

## Phase 1 exit condition — MET

- Target picked with explicit L7 rationale.
- Reproducer sequence carried forward from baseline.
- Blast radius mapped.
- L6+L7 relevance called out as the calibration's primary interest.
