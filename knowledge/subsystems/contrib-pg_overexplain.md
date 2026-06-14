# contrib-pg_overexplain (extended EXPLAIN diagnostics)

- **Source path:** `source/contrib/pg_overexplain/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` (no `.control` file)
- **Surface:** zero SQL functions; activated via EXPLAIN options

## 1. Purpose

Add `DEBUG` and `RANGE_TABLE` options to `EXPLAIN` that surface
internals normally hidden — alias mappings, range-table entries
with their full set of attributes, per-node bitmapsets like
`extParam` / `allParam` / `chgParam`, integer-list quals. Used
for planner-debugging and educational deep-dives, not normal
production observability.

Like `auto_explain`, it's a **hook installer** — `_PG_init`
registers two new EXPLAIN options and two explain-time hooks.

## 2. The two new EXPLAIN options

Activate via standard `EXPLAIN (...)` syntax:

```sql
EXPLAIN (DEBUG) SELECT ...;
EXPLAIN (RANGE_TABLE) SELECT ...;
EXPLAIN (DEBUG, RANGE_TABLE, ANALYZE) SELECT ...;  -- combinable
```

- **DEBUG** — per-node deep state: extParam, allParam,
  chgParam bitmapsets; plan-node flags; planner-pass markers.
- **RANGE_TABLE** — the planner's range table dumped
  verbatim: every RTE with its alias, eref, rtekind,
  permission info, and securityQuals.

## 3. The hook installation pattern

[verified-by-code `pg_overexplain.c:70-87`]

```c
void _PG_init(void) {
    es_extension_id = GetExplainExtensionId("pg_overexplain");

    RegisterExtensionExplainOption("debug", overexplain_debug_handler,
                                   GUCCheckBooleanExplainOption);
    RegisterExtensionExplainOption("range_table",
                                   overexplain_range_table_handler,
                                   GUCCheckBooleanExplainOption);

    prev_explain_per_node_hook = explain_per_node_hook;
    explain_per_node_hook = overexplain_per_node_hook;
    prev_explain_per_plan_hook = explain_per_plan_hook;
    explain_per_plan_hook = overexplain_per_plan_hook;
}
```

Three primitives at play:

- **`GetExplainExtensionId(name)`** — allocates a per-extension
  state slot inside `ExplainState`. Used so multiple
  EXPLAIN-extending modules don't collide on shared state.
- **`RegisterExtensionExplainOption(name, handler, check)`** —
  registers an option name (parsed inside `EXPLAIN (...)`),
  its parse handler, and an optional check function.
- **`explain_per_node_hook` / `explain_per_plan_hook`** —
  two hooks the EXPLAIN machinery calls per plan node /
  per top-level plan. The hooks chain via `prev_*` saves.

## 4. The extension-state pattern

[verified-by-code `pg_overexplain.c:93-100`]

```c
static overexplain_options *
overexplain_ensure_options(ExplainState *es)
{
    overexplain_options *options = GetExplainExtensionState(es, es_extension_id);
    if (options == NULL)
        /* allocate + attach */;
    return options;
}
```

Per-EXPLAIN state (which options the user enabled this time)
is stored against the `es_extension_id` slot. The hook fires
for every node and the hook reads the options from
ExplainState.

This is the canonical pattern for any module that adds
EXPLAIN options + per-node behavior — get a unique extension
id at `_PG_init`, attach state per `ExplainState`.

## 5. What DEBUG actually surfaces

`overexplain_debug` walks the plan node and emits:

- Boolean flags from `Plan` struct.
- Per-node bitmapsets:
  - **`extParam`** — params from outside this subplan
    (correlation).
  - **`allParam`** — params referenced anywhere in this
    subtree.
  - **`chgParam`** — params that, when changed, force a
    re-execute (subplan rescan trigger).
- Initialization-time vs run-time markers.

These are normally invisible because they're planner internals
that don't change query semantics — only debugging value.

## 6. What RANGE_TABLE surfaces

`overexplain_range_table` walks `plannedstmt->rtable` and
dumps each `RangeTblEntry`:

- `rtekind` — RTE_RELATION, RTE_SUBQUERY, RTE_JOIN, etc.
- `relid` + `relkind` for relations.
- `alias` and `eref` (the explicit alias + the planner's
  internal "effective reference").
- `securityQuals` if any (row-level security clauses).
- `selectedCols` / `insertedCols` / `updatedCols`
  bitmapsets (column-level permission info).

The range table is what the planner uses to resolve column
references. Surfacing it is invaluable for "why is my query
not using the index I expect" debugging where alias
shadowing is suspected.

## 7. Production-use guidance

- **Load via `shared_preload_libraries`** to make the options
  permanently available. Per-session `LOAD` works but
  requires `SET shared_preload_libraries` reload.
- **Production deployment is rare**, since the output is dev-
  oriented. Acceptable in staging for planner-research work.
- **Combine with `EXPLAIN (FORMAT JSON)`** if you want to
  pipe the output to a script — the debug/range_table fields
  appear as structured JSON keys.
- **NOT a replacement for `auto_explain`** — that one
  observes runtime; pg_overexplain extends format. They
  compose: use `auto_explain` to capture slow queries +
  `EXPLAIN (DEBUG)` to re-explain interesting ones.

## 8. Hook composition

`explain_per_node_hook` is a single global function pointer.
Multiple modules that install it must chain via `prev_*`.
pg_overexplain follows the canonical pattern
[verified-by-code `pg_overexplain.c:83-86`]:

- Save `prev_explain_per_node_hook` and
  `prev_explain_per_plan_hook`.
- Call them from inside the new hook (typically at the end of
  per-module output).

Loading order matters; last-loaded runs first. For
deterministic output across reloads, document the expected
load order.

## 9. Invariants

- **[INV-1]** No SQL surface; activation is via EXPLAIN
  options.
- **[INV-2]** Hook chaining via `prev_*` preserves other
  EXPLAIN-extending modules.
- **[INV-3]** Extension state is keyed by `es_extension_id`;
  unique per `_PG_init` call.
- **[INV-4]** DEBUG + RANGE_TABLE are independent; both can
  be enabled in one `EXPLAIN (...)`.
- **[INV-5]** Output is internal-state-only; no semantic
  change to query behavior.

## 10. Useful greps

- The init / registration:
  `grep -n 'RegisterExtensionExplainOption\|GetExplainExtensionId' source/contrib/pg_overexplain/pg_overexplain.c`
- The hook implementations:
  `grep -n 'overexplain_per_node_hook\|overexplain_per_plan_hook' source/contrib/pg_overexplain/pg_overexplain.c`
- Companion API in core:
  `grep -n 'RegisterExtensionExplainOption\|explain_per_node_hook' source/src/include/commands/`

## 11. Cross-references

- `knowledge/subsystems/contrib-auto_explain.md` — companion
  EXPLAIN-extending module; auto-logs slow queries.
- `knowledge/subsystems/executor.md` — the executor that
  EXPLAIN observes.
- `knowledge/subsystems/optimizer.md` — the planner whose
  internals DEBUG / RANGE_TABLE surface.
- `.claude/skills/debugging/SKILL.md` — pg_overexplain is the
  recommended next step after `EXPLAIN (ANALYZE, BUFFERS)`.
- `.claude/skills/executor-and-planner/SKILL.md` — context
  for the bitmapsets DEBUG dumps.
- `source/src/include/commands/explain.h` — the EXPLAIN
  extension API this module uses.
- `source/contrib/pg_overexplain/pg_overexplain.c` —
  implementation.
