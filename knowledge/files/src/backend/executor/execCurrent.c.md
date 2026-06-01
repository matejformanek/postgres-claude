# execCurrent.c

- **Source:** `source/src/backend/executor/execCurrent.c` (426 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Implements `WHERE CURRENT OF <cursor>` — given a cursor name and a target
table OID, return the CTID of the row the cursor is currently positioned on.
[from-comment] `:3-5`

## Entry point

`execCurrentOf(CurrentOfExpr*, ExprContext*, table_oid, &current_tid)` — used
by the executor when a CurrentOfExpr appears in a WHERE clause of UPDATE or
DELETE. The clause is implemented by:

1. Looking up the named Portal.
2. Walking the Portal's executor state tree via `search_plan_tree(node, table_oid, &pending_rescan)`
   to find the scan node that's currently scanning `table_oid`.
3. From that ScanState, reading `tts_tid` of the current tuple.

`search_plan_tree` handles inheritance — if the cursor's plan has an Append
of multiple child scans, the one whose `currentRelation` matches is picked.
It also rejects positions where the cursor has not yet fetched (or has run
off the end), and where a rescan is pending (post-FETCH ABSOLUTE 0 etc.).

## Param-based variant

`fetch_cursor_param_value(econtext, paramId)` — for plans where the cursor
name comes from a Param (e.g. SQL functions and plpgsql).

## Limitations baked in

- Only works on scrollable cursors whose plan top is a scan of the named
  table or an Append over scans of inheritance children — not on cursors
  over joins / aggregates / subqueries.
- For partitioned cursors the relation OID must match a *leaf*; the search
  walks past ModifyTable / Sort / Limit but draws the line at things that
  hide the underlying scan position.

## Tags

- [verified-by-code] entry-point signatures + walking strategy.
- [from-comment] purpose statement at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
