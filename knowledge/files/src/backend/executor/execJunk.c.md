# execJunk.c

- **Source:** `source/src/backend/executor/execJunk.c` (304 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Manages **junk attributes** — TargetEntry items with `resjunk=true` that
carry executor-internal info (CTID for UPDATE/DELETE, sort key columns, rowmark
TIDs, MERGE source markers) but must not appear in client output.
[from-comment] `:18-35`

## The JunkFilter

`JunkFilter *` (`nodes/execnodes.h`) bundles:
- `jf_cleanTupType` — TupleDesc of the row *with* junk stripped (= what the
  client should see),
- `jf_cleanMap` — array mapping clean attr i to original tlist position,
- `jf_resultSlot` — output slot for the cleaned tuple.

## Key APIs

- `ExecInitJunkFilter(targetList, slot)` — build a JunkFilter that
  strips all resjunk entries from any tuple matching the targetList shape.
- `ExecInitJunkFilterConversion(targetList, cleanTupType, slot)` — build one
  where the clean shape is *given* (used for INSERT … RETURNING into a
  rowtype that mismatches the targetlist exactly).
- `ExecFindJunkAttribute(JunkFilter*, attrName)` / `ExecFindJunkAttributeInTlist`
  — look up the position of a known junk column (e.g. "ctid", "tableoid",
  rowmark "ctid1" for FOR UPDATE).
- `ExecGetJunkAttribute(slot, attno, &isNull)` — extract one junk Datum.
- `ExecFilterJunk(JunkFilter*, srcSlot)` — produce the cleaned slot to
  return to the client.

## Where it matters

- DML: ModifyTable peels `ctid` / wholerow junk columns before doing the
  actual heap operation, and constructs the clean output slot for RETURNING.
- Sort / GroupAgg: order-by / group-by columns that don't appear in the
  SELECT list are added as resjunk by the planner and stripped at the top
  by a JunkFilter on the QueryDesc.
- SELECT FOR UPDATE: rowmark TIDs and tableoid junks (one set per locked
  RTE) ride through the plan and are consumed by `LockRows`.

## Tags

- [verified-by-code] API names.
- [from-comment] purpose statement at top of file.
