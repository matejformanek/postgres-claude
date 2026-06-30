# `pg_overexplain/pg_overexplain.c` — EXPLAIN extension dumping planner internals

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_overexplain/pg_overexplain.c`)

## Role

Adds two EXPLAIN options, `DEBUG` and `RANGE_TABLE`, that dump
planner-internal fields normally suppressed: disabled-node counts,
parallel_safe flag, plan_node_id, extParam/allParam bitmapsets, range
table entry metadata (RTI, kind, perminfoindex, alias / eref, lateral
flag, security_barrier flag, etc.). Wires into the
`explain_per_node_hook` and `explain_per_plan_hook`.

## Public API

No SQL-callable C functions. The module installs two EXPLAIN options
via `RegisterExtensionExplainOption` in `_PG_init`:

- `EXPLAIN (DEBUG)` — `source/contrib/pg_overexplain/pg_overexplain.c:76`
- `EXPLAIN (RANGE_TABLE)` — `source/contrib/pg_overexplain/pg_overexplain.c:78`

Both are gated by `GUCCheckBooleanExplainOption` per `_PG_init`.

## Invariants

- Chains `explain_per_node_hook` and `explain_per_plan_hook` correctly
  via saved `prev_explain_per_*_hook` pointers
  (`source/contrib/pg_overexplain/pg_overexplain.c:62-86, 145-148,
  323-325`).
- `overexplain_options` is stored on the `ExplainState` keyed by
  `es_extension_id` (assigned via `GetExplainExtensionId`)
  (`source/contrib/pg_overexplain/pg_overexplain.c:62, 94-107`).
- No work happens unless the user invoked one of the two options;
  early-out at line 149-151 / 327-329 [verified-by-code].
- Text-format and structured-format paths are explicitly distinguished
  for almost every emitted property.

## Notable internals

- Range-table dump iterates `plannedstmt->rtable` 1..N, fetching each
  entry via `rt_fetch`; handles RTEs cleared by `add_rte_to_flat_rtable`
  by skipping the cleared fields (functions, tablefunc, values_lists,
  joinaliasvars, subquery, tablesample, …)
  (`source/contrib/pg_overexplain/pg_overexplain.c:454-777`).
- Subplan→RTI mapping advanced lazily via `subrtinfos` list cursor
  (`source/contrib/pg_overexplain/pg_overexplain.c:448-471`).
- Bitmapsets emitted via `bms_next_member` into a `StringInfo`; lists
  via `foreach_int/oid/xid`.
- Special handling for `T_Append` / `T_MergeAppend` `apprelids` and
  `child_append_relid_sets`, `T_Result.relids`, `T_ModifyTable`'s
  `nominalRelation` and `exclRelRTI`, foreign/custom scans, elided
  nodes.
- For each RTE, schema-qualified relation name only in `es->verbose`
  mode — adheres to standard EXPLAIN convention
  (`source/contrib/pg_overexplain/pg_overexplain.c:586-596`).
- `RELKIND_PROPGRAPH` and `RTE_GRAPH_TABLE` are handled with comments
  noting that the rewriter should have converted them; if not, prints
  with correct names (defensive)
  (`source/contrib/pg_overexplain/pg_overexplain.c:511-520, 634-636`).

## Trust-boundary / Phase D surface

This module is the **least sensitive** in the slice — it only exposes
planner metadata that EXPLAIN VERBOSE already exposes in slightly
different form, plus some bitmapsets of RTIs.

1. **Schema names exposed only in `es->verbose`.** This is the standard
   convention (matches built-in EXPLAIN). No issue.
2. **Permission info index emitted as a number** (line 661-663), but
   the corresponding RTEPermissionInfo struct is NOT printed; the
   comment explicitly defers that to a separate `EXPLAIN (PERMISSIONS)`
   option. Good restraint
   (`source/contrib/pg_overexplain/pg_overexplain.c:655-663`).
3. **`security_barrier` flag is exposed.** Whether the user knows a
   view they're querying has a security_barrier is mostly meta-info,
   not a leak.
4. **No CHECK_FOR_INTERRUPTS in the RTE loop.** Bounded by the size of
   the rtable (typically small for human-written queries; can be
   thousands for partitioned tables with many partitions). For very
   large rtables, the loop could be slow to cancel.
   [ISSUE-correctness: range-table dump loop (line 455) has no
   CHECK_FOR_INTERRUPTS; partition-heavy plans with thousands of
   RTEs slow-to-cancel under EXPLAIN (RANGE_TABLE) (nit)]
   (`source/contrib/pg_overexplain/pg_overexplain.c:454-777`).
5. **Plan node ID exposed** (line 178) is normally not displayed. This
   helps with EXPLAIN-driven debuggers (e.g. attaching to a specific
   node) but is not sensitive.
6. **`extParam` / `allParam` bitmapsets** can leak references to
   PARAM_EXEC slots, which can correlate with subplan structure but
   are not data values. Not a leak in any meaningful sense.
7. **`prev_explain_per_*_hook` chaining**: the chain order is
   first-call-previous-then-self, which is the standard pattern. If
   another extension installs the same hook AFTER pg_overexplain, that
   extension will see pg_overexplain's output already in the
   ExplainState — fine.
8. **`overexplain_ensure_options` allocates in CurrentMemoryContext**
   (line 102), which during EXPLAIN should be the per-query context.
   No leak across queries.

## Cross-refs

- `knowledge/subsystems/executor-and-planner.md` — Plan / PlanState / PlannedStmt structure
- `knowledge/idioms/extension-development.md` — hook chaining pattern
- `src/backend/commands/explain.c` — the EXPLAIN core that this extends

<!-- issues:auto:begin -->
- [Issue register — `pg_overexplain`](../../../issues/pg_overexplain.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-correctness: range-table loop has no CHECK_FOR_INTERRUPTS; partition-heavy plans with thousands of RTEs cancel-slow under EXPLAIN (RANGE_TABLE) (nit)] — `source/contrib/pg_overexplain/pg_overexplain.c:454-777`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_overexplain.md](../../../subsystems/contrib-pg_overexplain.md)
