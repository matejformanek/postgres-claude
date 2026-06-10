# src/include/nodes/subscripting.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 168 [verified-by-code]

## Role

PG14+ pluggable type-subscripting API. The `arr[1:3]` syntax used to
be hard-coded to arrays; now any type can register a SQL-level
subscript handler returning a `SubscriptRoutines` table.

## Public API

- Forward decls: `ParseState`, `SubscriptingRefState`,
  `SubscriptExecSteps` (`:19-21`).
- `SubscriptTransform` callback — parse-analysis stage; transforms
  raw subscript expressions, fills `refupperindexpr`, `reflowerindexpr`,
  `refrestype`, `reftypmod` on the `SubscriptingRef` node
  (`:95-99`).
- `SubscriptExecSetup` callback — executor-startup compile;
  populates a `SubscriptExecSteps` struct with the per-call
  execution methods and optionally allocates `sbsrefstate->workspace`
  (`:153-155`).
- `SubscriptRoutines` — the returned table: `transform`, `exec_setup`,
  three bool flags `fetch_strict`, `fetch_leakproof`, `store_leakproof`
  (`:158-166`).

## Invariants

- INV-SBS-IMMUTABLE: header `:54-56` [from-comment] — all
  SubscriptingRefs are expected to be **immutable** and
  **parallel-safe**, regardless of flag values. Implementer can't
  vary results between calls.
- INV-SBS-NO-STRICT-STORE: comment `:50-53` [from-comment] —
  deliberately no `store_strict` flag; NULL subscript in assignment
  would NULL the whole container, which is undesired.
- INV-SBS-SLICE-LENGTH: `reflowerindexpr` is either NIL (element
  op) or same length as `refupperindexpr` (slice op), with NULL
  Lisp-empty entries for omitted bounds (`:67-72` [from-comment]).
- INV-SBS-METHODS-NULLABLE: implementations may set methods to
  NULL for unsupported ops; `sbs_check_subscripts` is optional —
  if NULL, `sbs_fetch` must do its own subscript validation
  (`:144-151` [from-comment]).
- INV-SBS-LEAKPROOF-CONTRACT: a "leakproof" fetch must NEVER
  raise a data-value-dependent error; typical resolution is
  silent NULL on invalid subscript. Otherwise RLS / security
  barrier bypass is possible.

## Notable internals

- The SQL signature is `subscripting_function(internal) returns
  internal`. The argument is unused — the function returns a
  pointer to a static-const SubscriptRoutines.
- `array_subscripting_handler` in `arrayfuncs.c` is the
  reference implementation.
- `jsonb_subscript_handler` in `jsonbsubs.c` is the second
  in-tree user.
- Type wiring: `pg_type.typsubscript` column points to the SQL
  function.

## Trust boundary / Phase D surface

- **Leakproof contract is security-critical (A7 echo).** RLS
  policies use `LEAKPROOF` functions to determine which quals
  can be evaluated before the security qual. A custom
  subscript handler claiming `fetch_leakproof=true` but actually
  raising errors on invalid subscripts can be used to probe
  for row existence behind a row-security barrier — classic
  oracle.
- **Custom AM/extension surface.** Any extension registering a
  type can attach a custom subscripter. Trust posture:
  function-pointer dispatch with no introspection. An
  extension's `exec_setup` could install methods that re-enter
  the executor in surprising ways (e.g. invoke arbitrary SQL).
- **`workspace` lifetime.** Allocated in caller's memory
  context; `exec_setup` doesn't see lifetime hints. Cross-
  partition execution may invalidate cached catalog OIDs in
  workspace.
- **Parse-analysis trust.** `transform` runs during parse, with
  full ACL / RLS context of the issuing role. A custom
  subscripter can do arbitrary SQL-callable work at parse time
  (similar to a check constraint or default expression).

## Cross-references

- `nodes/primnodes.h` — `SubscriptingRef` node definition.
- `executor/execExpr.h` — `SubscriptingRefState`,
  `SubscriptExecSteps`.
- `utils/array.h` — array subscripter reference.
- `utils/jsonb.h` — jsonb subscripter.
- `nodes/supportnodes.h` — sister "support function" mechanism
  (different SQL signature but same plug-in spirit).

## Issues / drift

- `[ISSUE-TRUST: A7 — leakproof flag self-asserted by extension; no runtime check; mis-flagged custom subscripter breaks RLS qual ordering (high)] — source/src/include/nodes/subscripting.h:39-48`
- `[ISSUE-DOC: workspace lifetime not described — implicit "ExecutorState context" relies on reader to know (medium)] — source/src/include/nodes/subscripting.h:101-110`
- `[ISSUE-CODE: SubscriptTransform can invoke arbitrary SQL at parse-time; not documented as a constraint, parallels other parse-callable hooks (low)] — source/src/include/nodes/subscripting.h:60-94`
