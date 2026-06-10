# src/include/commands/explain_state.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 113 [verified-by-code]

## Role

Defines `ExplainState`, the per-EXPLAIN scratchpad, plus the **extension
EXPLAIN-option registration API** added in PG18.

## Public API

- `ExplainSerializeOption` enum: NONE / TEXT / BINARY (`:21-26`).
- `ExplainFormat` enum: TEXT / XML / JSON / YAML (`:28-34`).
- `ExplainWorkersState` — per-worker buffers used during parallel-plan
  ANALYZE rollup (`:36-43`).
- `ExplainState` — big bag of options, output buffer, plan context,
  and an `extension_state` pointer array (`:45-79`).
- `RegisterExtensionExplainOption` / `ApplyExtensionExplainOption` —
  hook for extensions to add new `EXPLAIN (myopt ...)` options
  (`:100-107`).
- `GetExplainExtensionId` / `Get` / `SetExplainExtensionState` — opaque
  per-extension state slots (`:95-98`).
- `explain_validate_options_hook` — global hook for additional
  post-parse option validation (`:87-89`).

## Invariants

- INV-EXPLAINSTATE-EXT-IDX: `extension_state[]` is indexed by the integer
  returned from `GetExplainExtensionId(name)`; extensions must cache that
  ID at `_PG_init` time. Re-querying per-call is allowed but slower
  (linear scan in `explain_state.c`).
- `rtable_size` excludes the synthetic `RTE_GROUP` entry — see comment
  `:72-73`. Forgetting this and iterating `rtable` to `length(rtable)`
  causes a bogus extra "GROUP BY ()" RTE to appear.
- `format == TEXT` is the only one that uses `indent`; other formats use
  `grouping_stack` (managed in `explain_format.c`).

## Notable internals

- `printed_subplans` Bitmapset (`:70`) prevents re-emitting an InitPlan
  that's referenced by multiple parent plan nodes.
- `hide_workers` toggles when a Gather is "invisible" (e.g. `force_parallel
  _mode=regress`); the worker-output reattaches to the parent (`:71`).
- `extension_state_allocated` separate from "currently used" — the array
  is sized to the highest registered ID, then null-filled.

## Trust boundary / Phase D surface

- **A14 pg_overexplain anchor.** `pg_overexplain` contrib adds `RANGE_TABLE`
  and `DEBUG` options through this API; both can dump pg_class OIDs,
  reloptions, and column data that would normally require table privileges
  to obtain. EXPLAIN is privilege-checked at the **top** (relation-level
  SELECT), but the verbose dump goes deeper. PG18 trust note: extension
  EXPLAIN options run with the EXPLAIN-issuer's privileges; no separate
  permission check.
- `ExplainOptionGUCCheckHandler` (`:82-84`) — extensions can validate
  values supplied via GUC, but **value strings come from `pg_db_role_setting`
  or `SET`** — an attacker controlling those for their role can drive
  arbitrary handler code paths.
- **A7 ruleutils echo.** Deparsing of plan quals/tlists in EXPLAIN VERBOSE
  uses `rtable_names` / `deparse_cxt` (`:67-69`); RLS / security-barrier
  qual loss bugs surface here when a user EXPLAIN-VERBOSEs a view they
  shouldn't be able to read the underlying definition of.

## Cross-references

- `commands/explain_format.h` — output writers consuming this state.
- `commands/explain.h` — top-level `ExplainOneQuery`, `ExplainPrintPlan`.
- `nodes/parsenodes.h` — `Query`, `PlannedStmt` references.
- `contrib/pg_overexplain` — primary in-tree consumer of the extension API.

## Issues / drift

- `[ISSUE-TRUST: A14 — extension EXPLAIN options bypass per-relation EXPLAIN privilege gates; pg_overexplain can dump catalog OIDs to non-owner (medium)] — source/src/include/commands/explain_state.h:100-107`
- `[ISSUE-TRUST: explain_validate_options_hook is a single global; multiple loaded extensions can fight over it (low)] — source/src/include/commands/explain_state.h:87-89`
- `[ISSUE-DOC: extension_state_allocated semantics (sized-to-highest-id vs in-use count) not documented (low)] — source/src/include/commands/explain_state.h:77-78`
