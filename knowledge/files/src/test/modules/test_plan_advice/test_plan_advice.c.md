---
path: src/test/modules/test_plan_advice/test_plan_advice.c
anchor_sha: e18b0cb7344
loc: 143
depth: read
---

# src/test/modules/test_plan_advice/test_plan_advice.c

## Purpose

Self-feedback exerciser for the `pg_plan_advice` extension's planner-hint
machinery. When loaded, every query gets planned twice: once to generate an
advice string, then a second time using that advice string as input.
Disagreement between the two plans, or any failure in the second plan, points
to a bug where advice round-tripping is lossy or incorrect. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `test_plan_advice.c:41` | Looks up `pg_plan_advice_add_advisor` via `load_external_function` and registers `test_plan_advice_advisor` |
| `test_plan_advice_advisor` (static) | `:60` | The advisor hook — re-plans the query, extracts the advice string from `extension_state`, returns it |
| `find_defelem_by_defname` (static) | `:133` | Walk a `List<DefElem>` looking for `defname` |

## Internal landmarks

- `in_recursion` static flag (`:29`, `:74`, `:79`, `:109`) prevents infinite
  recursion when the advisor's `planner()` call triggers the planner hook
  chain again.
- `PG_TRY` / `PG_FINALLY` ensures `in_recursion` is reset to false on error
  (`:77-111`).
- The advisor sets two SUSET GUCs via `set_config_option(.. GUC_ACTION_SAVE)`
  inside a `NewGUCNestLevel` (`:91-97`) and rolls them back via
  `AtEOXact_GUC(false, save_nestlevel)` (`:115`):
  - `client_min_messages = error` — suppress NOTICEs from expression
    evaluation that would otherwise differ from the no-module baseline.
  - `pg_plan_advice.always_store_advice_details = true` — forces
    `pg_plan_advice` to attach the advice string to the result so the
    advisor can extract it.
- The advice string lives in `pstmt->extension_state`, a `List<DefElem>`
  keyed by extension name (`pg_plan_advice` → inner `List<DefElem>` →
  `advice_string`, `:118-127`).

## Invariants & gotchas

- **Test module — never load in production.** Doubling every query's
  planning time is unacceptable outside CI.
- Requires the `pg_plan_advice` contrib/extension to be installed; the
  `load_external_function` call (`:50`) errors otherwise.
- `copyObject(parse)` on `:104` is mandatory because the planner mutates its
  input Query.
- `extension_state` is a relatively new mechanism for plans to carry
  extension-private payload; this test is one of the few in-tree consumers.

## Cross-refs

- `source/src/backend/optimizer/plan/planner.c` — `planner_hook` API.
- `source/src/include/nodes/plannodes.h` — `PlannedStmt.extension_state`.
- `source/src/backend/utils/fmgr/dfmgr.c` — `load_external_function`.
