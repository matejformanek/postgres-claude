# `src/include/executor/spi.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

The Server Programming Interface — backend C API for running SQL
from inside other C code: triggers, PL handlers, contrib modules,
background workers. The canonical *text-to-SQL injection sink*
documented in A9/A10/A13 "5-sweep cluster".

## Public API surface

### Result globals [verified-by-code: lines 104-106]

```c
extern uint64        SPI_processed;   /* row count of last command */
extern SPITupleTable *SPI_tuptable;   /* rows of last SELECT-like */
extern int           SPI_result;      /* per-thread last result code */
```

### Result-code constants [lines 68-101]

Errors: `SPI_ERROR_CONNECT=-1`, `SPI_ERROR_COPY=-2`,
`SPI_ERROR_OPUNKNOWN=-3`, `SPI_ERROR_UNCONNECTED=-4`,
`SPI_ERROR_CURSOR=-5` (unused), `SPI_ERROR_ARGUMENT=-6`,
`SPI_ERROR_PARAM=-7`, `SPI_ERROR_TRANSACTION=-8`,
`SPI_ERROR_NOATTRIBUTE=-9`, `SPI_ERROR_NOOUTFUNC=-10`,
`SPI_ERROR_TYPUNKNOWN=-11`, `SPI_ERROR_REL_DUPLICATE=-12`,
`SPI_ERROR_REL_NOT_FOUND=-13`.
OK: `SPI_OK_CONNECT=1` … `SPI_OK_MERGE_RETURNING=19`.

Connect flag: `SPI_OPT_NONATOMIC = 1 << 0` [line 102].

### Connect / finish [lines 108-110]

`SPI_connect()`, `SPI_connect_ext(options)`, `SPI_finish()`.

### Execute — TEXT-INPUT (the injection-sink family)

[verified-by-code: lines 111-132]
- `SPI_execute(const char *src, bool read_only, long tcount)` —
  **THE canonical text-to-SQL sink**.
- `SPI_execute_extended(src, SPIExecuteOptions *options)` —
  modern variant; options struct (lines 46-55) carries
  `params`, `read_only`, `allow_nonatomic`,
  `must_return_tuples`, `tcount`, `dest`, `owner`.
- `SPI_exec(src, tcount)` — older 2-arg wrapper.
- `SPI_execute_with_args(src, nargs, argtypes, Values, Nulls,
  read_only, tcount)` — parameterized; `$1..$N` substitution.

### Execute — PLAN-INPUT (the safe family)

- `SPI_execute_plan(plan, Values, Nulls, read_only, tcount)`
- `SPI_execute_plan_extended(plan, SPIExecuteOptions *)`
- `SPI_execute_plan_with_paramlist(plan, ParamListInfo, read_only,
  tcount)`
- `SPI_execp(plan, Values, Nulls, tcount)` — shorthand.
- `SPI_execute_snapshot(plan, …, snapshot, crosscheck_snapshot,
  read_only, fire_triggers, tcount)` — full control.

### Prepare [lines 133-141]

- `SPI_prepare(src, nargs, argtypes)`
- `SPI_prepare_cursor(src, nargs, argtypes, cursorOptions)`
- `SPI_prepare_extended(src, SPIPrepareOptions *)` —
  `SPIPrepareOptions` (lines 37-43) has `parserSetup`,
  `parserSetupArg`, `parseMode` (RawParseMode enum from parser.h),
  `cursorOptions`.
- `SPI_prepare_params(src, ParserSetupHook, ParserSetupArg,
  cursorOptions)`.
- Plan lifetime: `SPI_keepplan(plan)`, `SPI_saveplan(plan)`,
  `SPI_freeplan(plan)`.

### Plan inspection [lines 146-153]

`SPI_getargtypeid`, `SPI_getargcount`, `SPI_is_cursor_plan`,
`SPI_plan_is_valid`, `SPI_result_code_string`,
`SPI_plan_get_plan_sources`, `SPI_plan_get_cached_plan`.

### Tuple manipulation [lines 155-172]

`SPI_copytuple`, `SPI_returntuple`, `SPI_modifytuple`,
`SPI_fnumber`, `SPI_fname`, `SPI_getvalue`, `SPI_getbinval`,
`SPI_gettype`, `SPI_gettypeid`, `SPI_getrelname`, `SPI_getnspname`,
`SPI_palloc`, `SPI_repalloc`, `SPI_pfree`, `SPI_datumTransfer`,
`SPI_freetuple`, `SPI_freetuptable`.

### Cursors [lines 174-191]

`SPI_cursor_open`, `SPI_cursor_open_with_args`,
`SPI_cursor_open_with_paramlist`, `SPI_cursor_parse_open`
(`SPIParseOpenOptions` lines 58-63), `SPI_cursor_find`,
`SPI_cursor_fetch`, `SPI_cursor_move`,
`SPI_scroll_cursor_fetch`, `SPI_scroll_cursor_move`,
`SPI_cursor_close`.

### ENR / transitions [lines 193-195]

`SPI_register_relation(EphemeralNamedRelation)`,
`SPI_unregister_relation(name)`,
`SPI_register_trigger_data(TriggerData *)`.

### Transactions [lines 197-205]

`SPI_start_transaction`, `SPI_commit`, `SPI_commit_and_chain`,
`SPI_rollback`, `SPI_rollback_and_chain`. Hooks:
`AtEOXact_SPI(isCommit)`, `AtEOSubXact_SPI(isCommit, mySubid)`,
`SPI_inside_nonatomic_context()`.

## Invariants

- **INV-CONNECT** [inferred] Every call requires a prior
  `SPI_connect`/`SPI_connect_ext`; functions return
  `SPI_ERROR_UNCONNECTED` otherwise.
- **INV-OWN-CONTEXT** [from common knowledge — SPI README]
  `SPI_connect` switches to a private memory context; results live
  there until `SPI_finish` or until `SPI_palloc`-promoted to the
  caller's context.
- **INV-PLAN-LIFETIME** [verified-by-code: lines 142-144]
  Plans freed at `SPI_finish` unless `SPI_keepplan` or
  `SPI_saveplan`.
- **INV-READ-ONLY** [inferred from signatures] `read_only=true`
  promises no side-effecting statement; planner may use a
  shared cached plan.
- **INV-NONATOMIC** [verified-by-code: lines 50, 102] `SPI_commit`
  / `SPI_rollback` only valid in a non-atomic context
  (procedures with COMMIT/ROLLBACK, top-level CALL); else
  `SPI_ERROR_TRANSACTION`.

## Trust boundary (Phase D — THE injection sink)

This header is the **canonical Phase D "text-to-SQL injection sink"**
referenced across A9/A10/A13.

### Sinks (take TEXT)

1. `SPI_execute(src, ...)`
2. `SPI_execute_extended(src, ...)`
3. `SPI_exec(src, ...)`
4. `SPI_execute_with_args(src, ...)` — safer when used correctly:
   the `src` should be a fixed query with `$1..$N`, values bound
   separately.
5. `SPI_prepare(src, ...)` / variants
6. `SPI_cursor_open_with_args(name, src, ...)`,
   `SPI_cursor_parse_open(name, src, ...)`

### Safer paths (take a plan + Datum args)

1. `SPI_execute_plan*`
2. `SPI_execp`
3. `SPI_execute_snapshot`
4. `SPI_cursor_open`, `SPI_cursor_open_with_paramlist`

### Attack patterns documented in A9/A10/A13

- **String concatenation into `SPI_execute`**: classic SQL injection
  vector inside a `SECURITY DEFINER` function/trigger that receives
  a user-supplied identifier. Mitigation: use `quote_ident()` or
  `format()` server-side, or use the plan family.
- **`fire_triggers=true` in `SPI_execute_snapshot`** with attacker-
  controlled snapshot: lets caller observe stale-row state. Niche.
- **`read_only=true` lie**: passing `read_only=true` for a
  side-effecting statement silently breaks the planner's
  shared-plan-cache assumption — corruption-class bug, not a
  privilege bug.
- **`SPI_register_relation`**: injects an ENR into the caller's
  query environment. Used by trigger code with the table-owner's
  privilege; safe by construction in trigger paths but exposed to
  any C-callable.

### Privilege context

SPI calls run with **the calling backend's role and search_path**
unless the caller already swapped them (e.g. `SECURITY DEFINER`
function entry). The header does not enforce or document this —
callers must know.

## Cross-refs

- `executor/spi_priv.h` — `SPIPlanPtr` internals.
- `parser/parser.h` — `RawParseMode`, `ParserSetupHook`.
- `utils/portal.h` — `SPI_cursor_*` return Portal.
- `commands/trigger.h` — `TriggerData`; SPI is the standard
  pl-trigger executor entry.
- A9/A10/A13 — text-to-SPI injection-sink cluster.
- A11 (`pg_stat_statements`) — sees the queries SPI executes,
  potentially leaking constants.

## Issues

- [ISSUE-PHASE-D: text-input family (`SPI_execute`,
  `SPI_execute_extended`, `SPI_exec`, `SPI_prepare`,
  `SPI_cursor_open_with_args`, `SPI_cursor_parse_open`) is the
  classic SQL-injection surface inside SECURITY DEFINER C functions;
  no header-level guidance steers callers to the plan/paramlist
  family (high, A9/A10/A13 cluster headline)] — lines 111-141, 174-185.
- [ISSUE-API: `read_only=true` is a *promise*, not a check — the
  planner trusts it for plan caching. A mislabeled side-effect call
  causes silently incorrect behavior (medium)] — passim.
- [ISSUE-DOC: privilege/search_path context inheritance is invisible
  from this header; SECURITY DEFINER + SPI is one of the most
  common PG security gotchas (medium)] — entire file.
