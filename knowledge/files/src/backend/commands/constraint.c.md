# `src/backend/commands/constraint.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~207
- **Source:** `source/src/backend/commands/constraint.c`

Implements `unique_key_recheck`, the AFTER ROW trigger that performs
deferred uniqueness and exclusion-constraint checks. Used both for
end-of-statement, commit-time, and `SET CONSTRAINTS IMMEDIATE` revalidation.
File is intentionally tiny — just this one trigger function plus the
required protocol checks. [verified-by-code]

## API / entry points

- `unique_key_recheck(PG_FUNCTION_ARGS)` — trigger entry point. Wired
  in as the function for the per-index uniqueness/exclusion deferred
  trigger. Returns `PointerGetDatum(NULL)`; the work is purely
  side-effectful. [verified-by-code]

## Notable invariants / details

- Trigger-protocol guards at lines 58-85: must be AFTER ROW, must be
  INSERT or UPDATE, else `ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED`.
  Translatable strings are shared with `ri_triggers.c`; comment
  warns reviewers not to fold the function name into the message.
  [from-comment]
- HOT-update subtlety (lines 89-106): the trigger queues only on index
  insertion. If the queued row was killed by a HOT update, its live
  HOT child may still satisfy the index entry for our values. We must
  still perform the check; we re-fetch via `SnapshotSelf` using
  `table_index_fetch_tuple`. If nothing live, skip — but this is for
  *correctness*, not just optimization, because the index AM would
  also fail to find the entry (it may have been dead-pruned).
  [from-comment]
- For pure uniqueness (no exclusion ops): `index_insert` is called
  with `UNIQUE_CHECK_EXISTING`; this is not a real insert, only a
  conflict re-check on the already-inserted entry, addressed by the
  *original* TID (`checktid`) regardless of HOT child. [from-comment]
- For exclusion constraints: `check_exclusion_constraint` is called
  with the live (HOT-walked) TID `tmptid` to avoid self-conflict on a
  HOT child. [from-comment]
- `EState` is allocated only if index has expressions or is an
  exclusion constraint (line 141-149).
- Locks: `RowExclusiveLock` on the index for the duration; the comment
  notes this guards index-schema changes, not concurrent updates.

## Potential issues

- File has no surprising bugs; very stable for a long time. The
  HOT-update correctness comment is itself the documentation of the
  invariant. No issues raised in `knowledge/issues/commands.md`.

## Synthesized by
<!-- backlinks:auto -->
