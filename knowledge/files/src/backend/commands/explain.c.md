# explain.c

- **Source path:** `source/src/backend/commands/explain.c`
- **Lines:** 5324
- **Last verified commit:** `419ce13b7019` (re-verified 2026-06-28 by
  pg-quality-auditor AUDIT mode after anchor-bump
  `f0a4f280b4d3..419ce13b7019`; clean re-pin. Triggering commit
  `b43f8aa4cb30` (ModifyTable FDW-array re-index on result-relation
  pruning) touched this file but was line-neutral — LOC unchanged 5324,
  top comment :3-4 intact, all named entry points present
  (`ExplainQuery` :181, `ExplainOneQuery` :299, `ExplainOnePlan` :500,
  `ExplainPrintPlan` :767, `ExplainNode` :1363). Prior pin
  `ef6a95c7c64`.)
- **Companion files:** `explain_format.c` (text/JSON/YAML/XML writers), `explain_state.c` (ExplainState lifecycle), `explain_dr.h`+`explain_dr.c` (the `(SERIALIZE)` option's DestReceiver).

## Purpose

"Explain query execution plans." [from-comment, explain.c:3-4] Walks a `PlannedStmt` tree producing per-node descriptions; with `ANALYZE` runs the executor and captures per-node `Instrumentation` (rows, time, buffers, I/O); with `BUFFERS`/`WAL`/`SETTINGS`/`SERIALIZE`/`MEMORY` adds extra dimensions.

## Public surface (a partial list — this file has many `ExplainOne*` and `show_*` helpers)

- `ExplainQuery` — top-level entry from utility; parses options and either calls `ExplainOneUtility` (for utility statements like CREATE TABLE AS) or `ExplainOneQuery` (after planning).
- `ExplainOneQuery_hook` — extension hook (e.g. for auto_explain) to intercept.
- `ExplainOnePlan` — plan an instrumented executor run if ANALYZE; otherwise just describe.
- `ExplainPrintPlan`, `ExplainNode` — the recursive node-walk. `ExplainNode` is enormous because each plan-node type has its own per-node display (Scan filter, Hash buckets, Sort method/memory, Bitmap Heap recheck, Foreign Scan via FDW callback).
- `ExplainPropertyText` / `ExplainPropertyInteger` / `ExplainPropertyFloat` / `ExplainPropertyList` / etc. — format-agnostic property writers; the actual emission is in `explain_format.c`.
- `show_buffer_usage`, `show_wal_usage`, `show_memory_counters`, `show_sort_info`, `show_hash_info` — per-feature renderers.

## SERIALIZE option (PG 17+)

`EXPLAIN (ANALYZE, SERIALIZE)` runs the query and **actually serialises** each output row through a special DestReceiver (`explain_dr.c`), reporting the bytes-written and time. Without SERIALIZE, ANALYZE reports executor time but skips the per-row protocol encoding cost — which can be a significant fraction for wide rows or text output.

## Extension points

`ExplainOneQuery_hook` is the documented hook; auto_explain uses it. Custom plan nodes get their own `ExplainCustomScan` callback; foreign tables use the FDW's `ExplainForeignScan`.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/jit-provider-and-context.md](../../../../idioms/jit-provider-and-context.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->

