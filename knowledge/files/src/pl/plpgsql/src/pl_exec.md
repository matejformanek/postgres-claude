# pl_exec.c

PL/pgSQL statement-by-statement executor: dispatches every PLpgSQL_stmt
node, evaluates expressions via SPI (with a fast "simple expression"
bypass that calls `ExecEvalExpr` directly), manages per-call/per-stmt
memory contexts, runs subtransactions for EXCEPTION blocks, and shepherds
trigger/event-trigger/procedure entry and exit. Source pin
`e18b0cb7344`, 9218 lines.

## One-line summary

`pl_exec.c` is the runtime: it walks a compiled PL/pgSQL function
(produced by `pl_comp.c` from a `pl_gram.y` parse) one statement at a
time, marshals expressions through SPI plans, captures errors in
subtransactions, and returns either a scalar, a tuplestore, or — for
procedures — control after a possible mid-function `COMMIT`/`ROLLBACK`.

## Top-level dispatch

Entry points called by `pl_handler.c`:

- `plpgsql_exec_function` — `source/src/pl/plpgsql/src/pl_exec.c:493`. Sets up `PLpgSQL_execstate`, copies datums, installs args (with R/W expanded-object commandeering for varlena args, `:548`-`:586`), pushes a `plpgsql_exec_error_callback` traceback frame (`:516`), runs `exec_toplevel_block` (`:636`), then handles SRF/composite/scalar return-value coercion (`:652`-`:790`). `[verified-by-code]`
- `plpgsql_exec_trigger` — `source/src/pl/plpgsql/src/pl_exec.c:935`. Builds expanded-record `OLD`/`NEW` from `tg_relation`'s tupdesc, nulls out BEFORE-trigger STORED-generated columns (`:1013`-`:1023`), calls `SPI_register_trigger_data` for transition tables (`:1034`), runs the body, validates returned tuple shape against the trigger's relation, conditionally `SPI_copytuple`s out. `[verified-by-code]`
- `plpgsql_exec_event_trigger` — `source/src/pl/plpgsql/src/pl_exec.c:1175`. Bare-bones: no OLD/NEW/return-value handling, just runs `exec_toplevel_block`.
- `exec_toplevel_block` — `source/src/pl/plpgsql/src/pl_exec.c:1664`. Thin wrapper around `exec_stmt_block` that fires plugin `stmt_beg`/`stmt_end` callbacks and sets `err_stmt`.
- `exec_stmts` — `source/src/pl/plpgsql/src/pl_exec.c:2026`. Iterates a `List *stmts`; for every node fires plugin callbacks, `CHECK_FOR_INTERRUPTS`, then a giant `switch(stmt->cmd_type)` (`:2056`-`:2171`) dispatching to all 26 `exec_stmt_*` functions. Early-returns on any rc != `PLPGSQL_RC_OK`. Empty `stmts` lists still run `CHECK_FOR_INTERRUPTS` (`:2032`-`:2041`) — important for empty `LOOP` bodies.
- `exec_stmt_block` — `source/src/pl/plpgsql/src/pl_exec.c:1693`. Initializes declared vars (`:1704`-`:1792`), then either bare-runs the body or runs it inside a `BeginInternalSubTransaction`/PG_TRY/PG_CATCH frame when EXCEPTION handlers exist (`:1796`-`:1975`). Final switch (`:1996`) implements label-aware EXIT propagation (CONTINUE never matches a block, EXIT matches only on label).

The result code protocol (`PLPGSQL_RC_OK`, `_EXIT`, `_CONTINUE`, `_RETURN`) is propagated through `exec_stmts` and intercepted by loops via the `LOOP_RC_PROCESSING(label, action)` macro (`source/src/pl/plpgsql/src/pl_exec.c:204`-`:253`). `[verified-by-code]`

## Statement families

### Assignment

- **dispatch**: `case PLPGSQL_STMT_ASSIGN` → `exec_stmt_assign` (`source/src/pl/plpgsql/src/pl_exec.c:2194`). Trivial: `exec_assign_expr(estate, estate->datums[stmt->varno], stmt->expr)`.
- **PERFORM**: `PLPGSQL_STMT_PERFORM` → `exec_stmt_perform` (`source/src/pl/plpgsql/src/pl_exec.c:2210`). Runs `exec_run_select` discarding rows, sets `FOUND` from `eval_processed != 0`.
- **core assignment helper**: `exec_assign_value` (`source/src/pl/plpgsql/src/pl_exec.c:5161`) handles DTYPE_VAR/PROMISE (cast → notnull check → expand arrays to R/W → `assign_simple_var`), DTYPE_ROW, DTYPE_REC (composite via `exec_move_row_from_datum`), and DTYPE_RECFIELD (field lookup with `recfield->rectupledescid` cache invalidation, system-column refusal at `:5345`).
- **assign_simple_var** (`source/src/pl/plpgsql/src/pl_exec.c:8879`): the canonical setter. **Non-atomic detoasting**: when `!estate->atomic` and the new value is an external (non-expanded) varlena, force-detoasts (`:8896`-`:8918`) so a later COMMIT can't leave a dangling TOAST pointer. Disarms PROMISE.
- **Set-INTO single-target fast path** in `exec_stmt_execsql` (`source/src/pl/plpgsql/src/pl_exec.c:4300`-`:4356`): when the SELECT is "simple" and the target is a 1-field row, bypasses SPI and goes straight through `exec_eval_expr` + `exec_assign_value`. Sets FOUND=true, `eval_processed=1` unconditionally — does **not** verify cardinality.

### Control flow

- **IF**: `exec_stmt_if` (`source/src/pl/plpgsql/src/pl_exec.c:2556`). Evaluates `cond` (NULL → false), then each ELSIF, else `else_body`.
- **CASE**: `exec_stmt_case` (`source/src/pl/plpgsql/src/pl_exec.c:2586`). For simple-CASE, evaluates `t_expr` and stores it into a hidden temp var (`t_var`); if datatype-changed, **rebuilds** the per-execution datatype (`:2613`-`:2618`) — comment acknowledges this can leak fn-lifespan memory if types churn (`:2607`-`:2611`). Throws `ERRCODE_CASE_NOT_FOUND` if no WHEN matched and no ELSE (`:2657`).
- **LOOP**: `exec_stmt_loop` (`source/src/pl/plpgsql/src/pl_exec.c:2673`). Bare `for(;;)` with `LOOP_RC_PROCESSING`.
- **WHILE**: `exec_stmt_while` (`source/src/pl/plpgsql/src/pl_exec.c:2695`). NULL condition is treated as false (terminates loop, `:2708`).
- **FOR-integer (FORI)**: `exec_stmt_fori` (`source/src/pl/plpgsql/src/pl_exec.c:2726`). Casts lower/upper/step bounds to var's datatype; rejects NULL bounds; rejects step ≤ 0; detects int32 overflow on increment (`:2836`-`:2847`) and exits silently rather than wrapping.
- **FOR-query (FORS)**: `exec_stmt_fors` (`source/src/pl/plpgsql/src/pl_exec.c:2869`). `exec_run_select` → `exec_for_query` → `SPI_cursor_close`.
- **FOR-cursor (FORC)**: `exec_stmt_forc` (`source/src/pl/plpgsql/src/pl_exec.c:2898`). Verifies portal name not in use (`:2925`), processes cursor args by faking a `PLpgSQL_stmt_execsql` SELECT-INTO (`:2946`-`:2963`) — note the "XXX historically this has not been STRICT" comment at `:2958`. `exec_for_query` runs with `prefetch_ok=false` because the user can `WHERE CURRENT OF` inside the body (`:3012`-`:3014`).
- **FOREACH-array**: `exec_stmt_foreach_a` (`source/src/pl/plpgsql/src/pl_exec.c:3038`). NULL array → ERROR (`:3058`-`:3061`); validates slice dim ≤ array dim; uses `array_create_iterator` + `array_iterate`; in slice mode, `pfree`s each element (`:3156`-`:3157`).
- **EXIT/CONTINUE**: `exec_stmt_exit` (`source/src/pl/plpgsql/src/pl_exec.c:3194`). Sets `estate->exitlabel` then returns RC_EXIT or RC_CONTINUE; resolution happens in `LOOP_RC_PROCESSING` and in `exec_stmt_block`'s tail switch.
- **shared loop driver**: `exec_for_query` (`source/src/pl/plpgsql/src/pl_exec.c:5937`). Pins the portal (`:5956`); refuses to prefetch in non-atomic context (`:5966`-`:5967`) — comment notes prefetched toasted data could turn into dangling refs after a COMMIT. Optimizes record-var assignment when consecutive tupdescs match via `er_tupdesc_id` (`:6010`-`:6046`).

### Returns

- **RETURN**: `exec_stmt_return` (`source/src/pl/plpgsql/src/pl_exec.c:3227`). For SRF, bare RETURN just signals "no more rows" (`:3235`-`:3236`). Special fast-path for `RETURN varname` (`:3255`-`:3310`) preserves R/W expanded-object ownership so the caller gets it cheaply; refuses scalar var as composite (`:3283`-`:3286`). Falls through to `exec_eval_expr` for arbitrary expressions, with the same composite check (`:3325`). VOID special case (`:3339`-`:3345`): functions get a non-null VOID datum; procedures get NULL.
- **RETURN NEXT**: `exec_stmt_return_next` (`source/src/pl/plpgsql/src/pl_exec.c:3356`). Requires `retisset`; lazily creates `tuple_store` via `exec_init_tuple_store` (`:3702`). For DTYPE_VAR forces R/O via `MakeExpandedObjectReadOnly` before casting (`:3412`-`:3414`) to avoid the cast step mutating the object in place. For DTYPE_REC instantiates empty rec if needed, maps tupdesc, puts tuple; for DTYPE_ROW makes a tuple via `make_tuple_from_row`; for non-tuple expr path casts the single column.
- **RETURN QUERY**: `exec_stmt_return_query` (`source/src/pl/plpgsql/src/pl_exec.c:3576`). Wires a `DestTuplestore` DestReceiver pointing at `estate->tuple_store` (`:3601`-`:3609`), then either runs the static plan with `SPI_execute_plan_extended(..., must_return_tuples=true)` (`:3611`-`:3642`) or evaluates the dynquery expression and runs `SPI_execute_extended(..., dest=treceiver)` (`:3643`-`:3685`). Computes processed-this-call as `tuple_count - tcount` (`:3692`-`:3695`).
- **tuple_store_owner** is captured at `estate_setup` from the caller's `CurrentResourceOwner` (`source/src/pl/plpgsql/src/pl_exec.c:4046`); `exec_init_tuple_store` temporarily switches to it so the tuplestore lives past any subtransaction inside an EXCEPTION block (`:3722`-`:3741`). `[verified-by-code]`

### Diagnostics

- **RAISE**: `exec_stmt_raise` (`source/src/pl/plpgsql/src/pl_exec.c:3757`). Three modes:
  1. Bare `RAISE;` re-throws `estate->cur_error` via `ReThrowError` (`:3774`-`:3782`); outside a handler → `ERRCODE_STACKED_DIAGNOSTICS_ACCESSED_WITHOUT_ACTIVE_HANDLER`.
  2. Walks format string `%`-by-`%` (`:3808`-`:3851`) substituting `convert_value_to_string` (NULL → `<NULL>`), `%%` → `%`. Parameter count mismatch is an `elog(ERROR, ...)` ("should have been checked at compile time", `:3830`, `:3854`).
  3. RAISE options (ERRCODE/MESSAGE/DETAIL/HINT/COLUMN/CONSTRAINT/DATATYPE/TABLE/SCHEMA) at `:3860`-`:3920`. Each opt is rejected if duplicated; NULL option value → ERROR (`:3873`-`:3876`).
  - The actual throw uses `errmsg_internal("%s", err_message)` (`:3944`) — the user-supplied message is **not** treated as a gettext format string, so `%`-injection from format is structurally safe at the ereport level. (See ISSUE list below for the prior-stage substitution behavior.)
- **GET DIAGNOSTICS / GET STACKED DIAGNOSTICS**: `exec_stmt_getdiag` (`source/src/pl/plpgsql/src/pl_exec.c:2440`). Stacked-diag outside a handler → ERROR (`:2451`-`:2454`). 12 item kinds switched at `:2461`-`:2542`; ROUTINE_OID, ROW_COUNT, RETURNED_SQLSTATE plus the textual ERROR_CONTEXT/DETAIL/HINT/COLUMN_NAME/CONSTRAINT_NAME/DATATYPE_NAME/MESSAGE_TEXT/TABLE_NAME/SCHEMA_NAME and PG_CONTEXT (`GetErrorContextStack` at `:2532`).
- **ASSERT**: `exec_stmt_assert` (`source/src/pl/plpgsql/src/pl_exec.c:3968`). No-op when `!plpgsql_check_asserts`. NULL or false → ereport `ERRCODE_ASSERT_FAILURE`. **Important**: `OTHERS` exception handler does **not** catch ASSERT_FAILURE (`:1639`-`:1641`).

### Exception block (PG_TRY/PG_CATCH + subxact)

Implemented inline in `exec_stmt_block` (`source/src/pl/plpgsql/src/pl_exec.c:1796`-`:1978`). The mechanism:

1. Save `oldcontext`, `oldowner`, `old_eval_econtext`, `save_cur_error` (`:1801`-`:1804`).
2. Force `get_stmt_mcontext` to create the stmt context **before** `BeginInternalSubTransaction` (`:1818`) — so error data has a home outside the subxact.
3. `BeginInternalSubTransaction(NULL)` (`:1820`), then `MemoryContextSwitchTo(oldcontext)` to run body in the function's main context.
4. PG_TRY body: `plpgsql_create_econtext` (so subxact has its own `eval_econtext`), run `exec_stmts(block->body)`; if RETURN, `datumTransfer` the return value out of the subxact eval context (`:1846`-`:1856`); then `ReleaseCurrentSubTransaction` and revert econtext.
5. PG_CATCH body: switch to stmt_mcontext, `CopyErrorData` + `FlushErrorState`; `RollbackAndReleaseCurrentSubTransaction`; rebuild stmt-mcontext stack via a manufactured "push" (`:1895`-`:1896`); delete nested stmt children (`:1907`); revert econtext; null out `eval_tuptable` (SPI threw it away); walk `exception->exc_list` with `exception_matches_conditions`; on match, fill SQLSTATE/SQLERRM vars and run handler; on no-match, `ReThrowError`.
6. `exception_matches_conditions` (`source/src/pl/plpgsql/src/pl_exec.c:1625`): OTHERS does **not** match `ERRCODE_QUERY_CANCELED` or `ERRCODE_ASSERT_FAILURE` (`:1637`-`:1642`); category match supported (`:1647`-`:1649`).

Subxact callbacks for the simple-expression econtext stack live in `plpgsql_subxact_cb` (`source/src/pl/plpgsql/src/pl_exec.c:8852`): walks `simple_econtext_stack` popping any entry whose `xact_subxid == mySubid` and `FreeExprContext`s it. `[verified-by-code]`

### Cursors

- **OPEN**: `exec_stmt_open` (`source/src/pl/plpgsql/src/pl_exec.c:4757`). Three sub-modes:
  - **OPEN refcursor FOR SELECT** (`:4793`-`:4805`): pre-plans the static query.
  - **OPEN refcursor FOR EXECUTE** (`:4806`-`:4833`): dynamic via `exec_dynquery_with_params`; assigns generated portal name back to cursor var if it was NULL.
  - **OPEN bound cursor** (`:4834`-`:4881`): processes optional argquery the same SELECT-INTO trick as FORC.
  - Final: `setup_param_list` + `SPI_cursor_open_with_paramlist` (`:4891`). Cursor name reuse check at `:4783`-`:4787`.
- **FETCH/MOVE**: `exec_stmt_fetch` (`source/src/pl/plpgsql/src/pl_exec.c:4922`). NULL cursor var → ERROR. Resolves portal by name; `SPI_scroll_cursor_fetch` for FETCH, `SPI_scroll_cursor_move` for MOVE; sets target row or NULL row on n==0; updates FOUND.
- **CLOSE**: `exec_stmt_close` (`source/src/pl/plpgsql/src/pl_exec.c:5013`). Resolves portal, `SPI_cursor_close`. Cursor variable is **not** set to NULL after close — the text name lingers.
- **dynfors**: `exec_stmt_dynfors` (`source/src/pl/plpgsql/src/pl_exec.c:4730`) — `exec_dynquery_with_params` + `exec_for_query` + close, using `CURSOR_OPT_NO_SCROLL`.

### Dynamic SQL (EXECUTE)

- **EXECUTE / EXECUTE … INTO / EXECUTE … USING**: `exec_stmt_dynexecute` (`source/src/pl/plpgsql/src/pl_exec.c:4540`). Steps:
  1. Evaluate `stmt->query` (the query string expression) → text. NULL → ERROR (`:4559`-`:4562`).
  2. `convert_value_to_string` + `MemoryContextStrdup` into stmt_mcontext.
  3. `exec_eval_using_params(estate, stmt->params)` (`source/src/pl/plpgsql/src/pl_exec.c:8978`) builds a `ParamListInfo` from USING expressions. UNKNOWN-typed params get treated as TEXT (`:9018`-`:9030`).
  4. `SPI_execute_extended(querystr, &options)` — **one-shot, no saved plan**, so the user-supplied string is parsed/planned every call. `read_only` honors `estate->readonly_func`.
  5. Switch on result code: SELINTO is rejected (`:4606`-`:4619`); COPY rejected; transaction commands rejected.
  6. INTO target handling identical to static execsql: NULL row, strict cardinality enforcement.
- **dynfors / OPEN FOR EXECUTE**: route through `exec_dynquery_with_params` (`source/src/pl/plpgsql/src/pl_exec.c:9060`) using `SPI_cursor_parse_open`.
- USING params are **always** passed as $1, $2, … with `PARAM_FLAG_CONST` (`source/src/pl/plpgsql/src/pl_exec.c:9009`) — these are real parameters, not string-interpolated, so they're safe against SQL injection. The query *string* itself is whatever the user computed, however — that's the canonical PL/pgSQL dynamic-SQL injection surface. (`format`/`quote_ident`/`quote_literal` are the user's responsibility; pl_exec doesn't validate.)

### Procedure / COMMIT / ROLLBACK / CALL

- **CALL (and DO)**: `exec_stmt_call` (`source/src/pl/plpgsql/src/pl_exec.c:2227`). Plans the CallStmt; builds an output-arg target row on first call (`:2253`-`:2254`, helper `make_callstmt_target` at `:2319`); sets `options.allow_nonatomic = true` (`:2270`) and uses `estate->procedure_resowner` to hold the plan refcount across a possible mid-call COMMIT (`:2260`-`:2272`). After execution, compares `before_lxid`/`after_lxid` (`:2258`, `:2279`-`:2290`); if changed, drops `simple_eval_estate`/`simple_eval_resowner` to NULL and rebuilds the econtext — the procedure committed under our feet. Output row, if any, is assigned via `exec_move_row`.
- **COMMIT**: `exec_stmt_commit` (`source/src/pl/plpgsql/src/pl_exec.c:5056`). Calls `SPI_commit_and_chain` or `SPI_commit`, then unconditionally rebuilds simple-eval infrastructure (`:5064`-`:5070`). The old `eval_econtext` is destroyed when its xact ended.
- **ROLLBACK**: `exec_stmt_rollback` (`source/src/pl/plpgsql/src/pl_exec.c:5080`) — same pattern with `SPI_rollback{,_and_chain}`.
- **make_callstmt_target** (`source/src/pl/plpgsql/src/pl_exec.c:2319`): re-fetches the CallStmt's cached plan, looks at procedure's INOUT/OUT arg positions, and builds a `PLpgSQL_row` whose `varnos[]` point at the plpgsql variables matching each output Param. Calls `exec_check_assignable` per slot to refuse non-writable args (`:2404`).

## Expression evaluation & SPI

- **exec_eval_expr** (`source/src/pl/plpgsql/src/pl_exec.c:5765`): the canonical "give me one Datum" interface. First ensures `expr->plan` exists (via `exec_prepare_plan`), tries `exec_eval_simple_expr`, falls back to `exec_run_select` and unpacks the single (col, row) cell. Cardinality check at `:5831`.
- **exec_run_select** (`source/src/pl/plpgsql/src/pl_exec.c:5853`): the non-simple path. Uses `CURSOR_OPT_PARALLEL_OK` only when `portalP == NULL` (i.e., not for FOR-loop opens, since user code in the loop body might be parallel-unsafe). `SPI_execute_plan_with_paramlist`; stuffs `SPI_tuptable` into `estate->eval_tuptable` for the caller.
- **exec_eval_simple_expr** (`source/src/pl/plpgsql/src/pl_exec.c:6119`): the fast path. Requires `expr_simple_expr` non-NULL, `expr_simple_in_use` clear (else recursion-bailout returns false to let the caller use SPI), then `EnsurePortalSnapshotExists`, `CachedPlanIsSimplyValid` check (replans via `SPI_plan_get_cached_plan` + `exec_save_simple_expr` if invalid), `ExecInitExprWithParams` once per lxid, optional `PushActiveSnapshot(GetTransactionSnapshot())` when expression is `expr_simple_mutable` AND not read-only, finally `ExecEvalExpr`. The `expr_simple_in_use` flag is set around the call.
- **exec_prepare_plan** (`source/src/pl/plpgsql/src/pl_exec.c:4205`): one-shot per expression. `SPI_prepare_extended` with the PL/pgSQL `parserSetup` hook, `SPI_keepplan`, store on `expr->plan`, then `exec_simple_check_plan` to decide if the simple-eval fast path is available.
- **exec_simple_check_plan** (`source/src/pl/plpgsql/src/pl_exec.c:8233`) + **exec_is_simple_query** (`:8305`): simple = exactly one CachedPlanSource → one Query → plain `CMD_SELECT` → no rtable, no agg/window/SRF/sublink/CTE/from/qual/group/having/window/distinct/sort/limit/setop → exactly one targetlist entry. If yes, `CachedPlanAllowsSimpleValidityCheck` + `exec_save_simple_expr`.
- **exec_save_simple_expr** (`source/src/pl/plpgsql/src/pl_exec.c:8376`): peels Gather/Material wrappers (`debug_parallel_query` or scrollable cursor); requires the underlying plan to be a `Result` with no quals/initPlan/constantqual; stashes the TargetEntry expr, type, typmod, and `contain_mutable_functions` verdict (used to decide whether the fast path needs a fresh snapshot).
- **setup_param_list** (`source/src/pl/plpgsql/src/pl_exec.c:6350`): returns NULL when `expr->paramnos` is empty (so plancache.c won't build a custom plan); else returns the shared `estate->paramLI` after stashing `expr` in `parserSetupArg`.
- **plpgsql_param_fetch** (`source/src/pl/plpgsql/src/pl_exec.c:6398`): hook for `copyParamList`/`SerializeParamList`; returns a dummy when the requested dno isn't in `expr->paramnos`.
- **plpgsql_param_compile** (`source/src/pl/plpgsql/src/pl_exec.c:6525`): hook for `ExecInitExpr`; picks among five eval functions — `plpgsql_param_eval_var_check` (only the R/W-optimizable target Param), `plpgsql_param_eval_var_ro` (varlena var w/ R/O wrap), `plpgsql_param_eval_var` (no wrap), `plpgsql_param_eval_recfield`, `plpgsql_param_eval_generic_ro` / `_generic` — for performance.
- **Result coercion** to function return type happens at `plpgsql_exec_function:648`-`:790` via `exec_cast_value` (scalar) or `coerce_function_result_tuple` (composite, `source/src/pl/plpgsql/src/pl_exec.c:824`). Domains have their constraints rechecked even on NULL returns (`:782`-`:789`).

## Subxact lifecycle

Each EXCEPTION-bearing `BEGIN ... END` block opens an internal subxact:

- `BeginInternalSubTransaction(NULL)` at `source/src/pl/plpgsql/src/pl_exec.c:1820`.
- `plpgsql_create_econtext(estate)` at `:1832` creates a child ExprContext tied to `simple_eval_estate`, pushes it on `simple_econtext_stack` with `xact_subxid = GetCurrentSubTransactionId()` (`source/src/pl/plpgsql/src/pl_exec.c:8771`-`:8779`).
- On normal path: `ReleaseCurrentSubTransaction()` (`:1859`); the subxact-commit callback `plpgsql_subxact_cb` (`source/src/pl/plpgsql/src/pl_exec.c:8852`) pops the stack entry and `FreeExprContext`s the econtext.
- On error path: `RollbackAndReleaseCurrentSubTransaction()` (`:1885`); the same `plpgsql_subxact_cb` runs on abort (`event == SUBXACT_EVENT_ABORT_SUB`) and tears down any econtexts opened inside.
- `eval_tuptable` is force-nulled in the PG_CATCH path (`:1918`) because SPI's subxact-abort already freed it.

Cross-call CALL handling has its own variant: `exec_stmt_call` detects mid-procedure xact change by lxid comparison (`source/src/pl/plpgsql/src/pl_exec.c:2281`-`:2290`) and rebuilds the simple-eval infrastructure on the spot rather than relying on subxact callbacks.

Transaction-level cleanup: `plpgsql_xact_cb` (`source/src/pl/plpgsql/src/pl_exec.c:8810`) zeros `simple_econtext_stack`, frees `shared_simple_eval_estate`, releases all plan-cache refs in `shared_simple_eval_resowner` on commit; on abort just clears pointers (assumes abort recovery did the freeing). Both callbacks are registered from `pl_handler.c`.

## Memory contexts

Four-tier model documented at the top of the file (`source/src/pl/plpgsql/src/pl_exec.c:104`-`:126`):

1. **Function/SPI Proc context** (`estate->datum_context`, set to `CurrentMemoryContext` at `estate_setup`, `source/src/pl/plpgsql/src/pl_exec.c:4059`) — holds variable values and lives for the duration of the call. Leaks here are function-lifespan (the comment frankly admits the codebase tolerates "careless coding" here).
2. **stmt_mcontext** (`source/src/pl/plpgsql/src/pl_exec.c:1574`): created on-demand by `get_stmt_mcontext`, parented to `stmt_mcontext_parent`. Reset by the requesting routine. Nested statements that need their own stmt-lifespan workspace use `push_stmt_mcontext` (`:1593`) / `pop_stmt_mcontext` (`:1612`) to build a stack.
3. **eval_mcontext** = `estate->eval_econtext->ecxt_per_tuple_memory` (macros at `:127`-`:132`). Reset by `exec_eval_cleanup` (`:4168`); used for short-lived per-expression work and intermediate Datum storage.
4. **Shared simple-eval EState** (`shared_simple_eval_estate`, `:91`): one per transaction (created lazily under `TopTransactionContext`), shared across all PL/pgSQL invocations in the same xact. DO blocks get a *private* EState created by `plpgsql_inline_handler` (see file header comment `:68`-`:82`); if the DO block COMMITs, the next statement re-attaches to the shared one.
5. **Shared simple-eval resowner** (`shared_simple_eval_resowner`, `:102`): holds CachedPlan refcounts so we don't churn them per-evaluation. Cleared at xact end by `plpgsql_xact_cb`.
6. **Cast-expression hashes** (`cast_expr_hash`, `shared_cast_hash`, `:178`-`:179`): session-wide. `cast_expr_hash` keys `(srctype, srctypmod, dsttype, dsttypmod)` → compiled cast `Expr *`; `shared_cast_hash` (or a private one for DO blocks at `:4090`) holds the per-lxid `ExprState *`. Comment at `:138`-`:141` admits these are **not invalidated when `pg_cast` changes** ("at some point it might be worth invalidating them … but for the moment we don't bother").

## Error capture / rethrow

- **plpgsql_exec_error_callback** (`source/src/pl/plpgsql/src/pl_exec.c:1243`): registered on `error_context_stack` for every function entry. Reports `fn_signature`, line number (from `err_var` if set, else `err_stmt`), and an `err_text` phrase. The traceback uses `gettext_noop` for `err_text` until needed.
- **plpgsql_execsql_error_callback** (`source/src/pl/plpgsql/src/pl_exec.c:1312`): mirrors `spi.c`'s `_SPI_error_callback` so simple-INTO and SPI paths report the same way.
- **cur_error** field (`PLpgSQL_execstate`): set by `exec_stmt_block` after a matched EXCEPTION (`:1950`), saved/restored around handler so nested handlers don't see each other's data. `GET STACKED DIAGNOSTICS` and bare `RAISE` both read this.
- **SQLSTATE / SQLERRM**: vars whose dnos are stored on the block's `exceptions` struct (`block->exceptions->sqlstate_varno`/`sqlerrm_varno`). Filled by `exec_stmt_block:1937`-`:1944` from `edata->sqlerrcode` + `edata->message`.
- **err_var** (PLpgSQL_variable *): used to report a variable's declaration line during `block`-time variable init (`:1719`), so a constraint-rejection on the default expression reports the variable's line.

## Cross-references

- `pl_handler.c` (`source/src/pl/plpgsql/src/pl_handler.c`) — call-handler entry; registers `plpgsql_xact_cb` / `plpgsql_subxact_cb`; sets up `plpgsql_estate_setup`'s simple_eval_estate args for DO/CALL.
- `pl_comp.c` — produces `PLpgSQL_function`, `PLpgSQL_expr`, the `datums[]` array, and the parse tree that `exec_stmt_*` consumes. The `pl_handler` reads the cache and hands the func to `plpgsql_exec_function`.
- `pl_gram.y` — `PLpgSQL_stmt_*` node types; `cmd_type` values used in `exec_stmts`' switch.
- `executor/spi.c` — `SPI_prepare_extended`, `SPI_execute_plan_with_paramlist`, `SPI_execute_plan_extended`, `SPI_execute_extended`, `SPI_commit`, `SPI_rollback`, `SPI_cursor_open_with_paramlist`, `SPI_cursor_parse_open`, `SPI_register_trigger_data`. SPI is the only path into the executor / planner.
- `executor/execExpr.c` + `executor/execExprInterp.c` — `ExecInitExprWithParams`, `ExecEvalExpr`, the `EEOP_PARAM_CALLBACK` step used by `plpgsql_param_compile`.
- `utils/cache/plancache.c` — `CachedPlanSource`, `CachedPlan`, `CachedPlanIsSimplyValid`, `CachedPlanAllowsSimpleValidityCheck`, `GetCachedExpression`, `FreeCachedExpression`.
- `utils/cache/typcache.c` + `utils/adt/expandedrecord.c` — expanded record/`ExpandedRecordHeader` machinery; `expanded_record_set_field`, `expanded_record_lookup_field`, `make_expanded_record_from_typeid`, `er_tupdesc_id`.
- `utils/adt/array.c` + `utils/adt/expandeddatum.c` — `expand_array`, `TransferExpandedObject`, `MakeExpandedObjectReadOnly`, `DeleteExpandedObject`.
- `access/xact.c` — `BeginInternalSubTransaction`, `ReleaseCurrentSubTransaction`, `RollbackAndReleaseCurrentSubTransaction`, `GetCurrentSubTransactionId`, `RegisterSubXactCallback`.
- `tcop/postgres.c` — top-of-command snapshot management that `EnsurePortalSnapshotExists` (`source/src/pl/plpgsql/src/pl_exec.c:6154`) interacts with.
- `commands/trigger.c` — `TriggerData`, `TRIGGER_FIRED_*` macros, `tg_trigtuple`/`tg_newtuple`/`tg_relation` used by `plpgsql_exec_trigger`.
- `parser/parse_coerce.c` — `coerce_to_target_type` with the special `COERCION_PLPGSQL` mode (`source/src/pl/plpgsql/src/pl_exec.c:8140`).

## Issues spotted

The file is mature, but several behaviors deserve attention from a security/audit/correctness lens — especially because PL/pgSQL is the canonical "privileged code runs as some user, processes some other user's data" surface.

### Dynamic-SQL injection surface (the main one)

- [ISSUE-security: EXECUTE query string is whatever the user computed; pl_exec only parameterizes USING args, never the query body (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:4541`, `:9061` — `exec_stmt_dynexecute` and `exec_dynquery_with_params` take `querystr` (a Datum coerced to C string) and feed it directly to `SPI_execute_extended` / `SPI_cursor_parse_open`. There is no `quote_*` defense. This is the textbook PL/pgSQL SQL-injection vector when a user does `EXECUTE 'SELECT * FROM ' || tablename`. The docs cover it; the executor does not. Worth flagging in any audit checklist.
- [ISSUE-defense-in-depth: EXECUTE one-shot plan is re-parsed every call (maybe)] — `source/src/pl/plpgsql/src/pl_exec.c:4581`-`:4582` — `SPI_execute_extended(querystr, &options)` with no plan stash means catalog-driven (search_path-sensitive) parsing happens fresh each call. This is *correct* but it also means search-path-takeover attacks via the dynamic string get a fresh parse each time — no protection from prior plan caching. Worth noting alongside the docs.
- [ISSUE-correctness: SELINTO inside EXECUTE is rejected at runtime, not parse-time (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:4606`-`:4619` — `EXECUTE 'SELECT … INTO …'` returns `SPI_OK_SELINTO` and only then errors. Comment at `:4609` acknowledges "not a functional limitation" but the diagnostic is suboptimal.

### RAISE format-string handling

- [ISSUE-security: RAISE format string can be user-controlled and the parameter-substitution is unchecked at runtime (maybe)] — `source/src/pl/plpgsql/src/pl_exec.c:3808`-`:3851` — `stmt->message` is the format text; `%`-by-`%` substitution evaluates each USING param via `exec_eval_expr` + `convert_value_to_string`. If a user puts `RAISE NOTICE '%' USING something_user_controlled`, the value lands in the message; if a *programmer* exposes the format string itself to user input, the substitution happens server-side. The throw uses `errmsg_internal("%s", err_message)` (`:3944`) so the assembled message isn't itself re-interpreted as a printf format — that's the structural protection. **Limit**: parameter-count mismatch is an `elog(ERROR, "unexpected RAISE parameter list length")` at runtime (`:3830`, `:3854`) — comment says "should have been checked at compile time", but if compile-time validation is ever bypassed (e.g., a tweaked parse tree), this is the only guard.
- [ISSUE-error-handling: condname → err_message fallback uses condname text raw (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:3929`-`:3933` — if no MESSAGE was given but a condname was, the condname string becomes the message. Fine for builtin SQLSTATEs but a user-supplied custom condition name will become the user-visible message.

### Exception swallowing (`WHEN OTHERS`)

- [ISSUE-audit-gap: WHEN OTHERS catches every error except query-cancel and assertion-failure, which is a widely-documented but oft-forgotten pitfall (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:1637`-`:1641` — comment says "If you're foolish enough, you can match those explicitly". The implication: writing `EXCEPTION WHEN OTHERS THEN ... ; -- swallow` masks every PANIC-near-miss except assert-failure and query-cancel. Static analyzers should flag bare `WHEN OTHERS THEN NULL;` patterns. Not a bug in pl_exec, but a security-relevant runtime behavior the executor enforces.
- [ISSUE-correctness: bare RAISE in a CATCH-with-FOR-loop semantics around `eval_tuptable` is subtle (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:1918` — `estate->eval_tuptable = NULL;` is required because SPI tossed it during subxact abort; if any future code reads `eval_tuptable` after PG_CATCH without checking NULL, it crashes. The contract is implicit.
- [ISSUE-correctness: an EXCEPTION block in a SRF leaves tuplestore-state intact (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:3722`-`:3741` + `:4044`-`:4052` — `tuple_store_owner` is captured from the *caller*'s ResourceOwner so the tuplestore survives subxact abort. Means: rows already RETURN NEXT'd into the tuplestore **are not rolled back** when the subxact aborts — but the side-effects of the body are. This is the documented "SRF + exception block" semantic; worth highlighting because it surprises people. `[from-comment]`

### GET STACKED DIAGNOSTICS / security-definer chains

- [ISSUE-security: GET STACKED DIAGNOSTICS exposes the inner ereport's CONTEXT/DETAIL/HINT/COLUMN/CONSTRAINT/TABLE/SCHEMA strings to the handler (maybe)] — `source/src/pl/plpgsql/src/pl_exec.c:2461`-`:2542` — every field on `cur_error` (ErrorData *) is exposed verbatim. If a security-definer procedure calls into untrusted user code that raises, and the SD's exception handler does `GET STACKED DIAGNOSTICS … = PG_EXCEPTION_DETAIL, …`, the SD sees whatever the untrusted code put in DETAIL/HINT. Symmetrically, an untrusted handler can introspect details of a privileged call's failure (table name, schema name). Doesn't seem to be exploitable for privilege escalation per se, but it's an information-flow surface worth modeling.

### COMMIT inside a procedure

- [ISSUE-correctness: post-COMMIT, simple-eval infrastructure is rebuilt and the new evaluation runs against a brand-new snapshot (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:5057`-`:5072`, `:2280`-`:2290` — after COMMIT, the next `exec_eval_simple_expr` call hits `EnsurePortalSnapshotExists` (`:6154`) and may produce a snapshot that sees *new* data the caller's outer transaction wouldn't have. Procedures called via `CALL` from inside a top-level command thus break the usual "stable snapshot for one SQL command" invariant. This is the documented semantics for non-atomic CALL contexts; surprise-factor is high.
- [ISSUE-defense-in-depth: cursors held across COMMIT are not automatically rebuilt (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:5060`-`:5070` — `SPI_commit` invalidates non-holdable portals; subsequent FETCH on such a cursor raises "cursor does not exist" via `SPI_cursor_find == NULL` (`:4948`-`:4952`). Code is correct; user is surprised.

### Cursor leaks / abuse

- [ISSUE-correctness: close-on-error is at the subxact/transaction-abort level, not on function exit — un-closed cursors can outlive the function (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:5013`-`:5048` — `exec_stmt_close` is the only explicit close path for non-FOR cursors. A procedure that OPENs a refcursor and returns it (or simply forgets to close) leaves the portal alive until xact end. This is intentional (refcursor return is a feature) but is a leak vector if mis-used in a long-lived session.
- [ISSUE-correctness: FORC argument processing uses non-STRICT INTO with the "XXX historically this has not been STRICT" comment (maybe)] — `source/src/pl/plpgsql/src/pl_exec.c:2958` — the argquery SELECT-INTO trick treats a multi-row arg-expression result as "use the first row, silently". The comment flags this as a wart, not a fix. If the cursor's arg-row expression evaluates more than one tuple (which it shouldn't in practice), the loop quietly takes the first.
- [ISSUE-correctness: same issue for OPEN CURSOR with args (maybe)] — `source/src/pl/plpgsql/src/pl_exec.c:4863`.

### Trigger context fields

- [ISSUE-security: TG_TABLE_NAME/TG_TABLE_SCHEMA are derived from `tg_relation->rd_id` at the time of trigger fire, not a user input, so injection-via-TG-fields requires the attacker to have already changed catalog (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:1490`-`:1505` — `get_namespace_name(RelationGetNamespace(...))`. Safe in the trigger function but a function that does `EXECUTE 'INSERT INTO ' || TG_TABLE_NAME` is **not** safe — TG_TABLE_NAME can legitimately contain characters that need quoting. Static-analyzer fodder.
- [ISSUE-correctness: BEFORE-trigger STORED-generated columns are forced to NULL only on UPDATE, not INSERT (from-comment)] — `source/src/pl/plpgsql/src/pl_exec.c:1013`-`:1023` — explicit comment that on INSERT they're already NULL. Subtle if the user has a generated column with a STORED expression that produces non-NULL by default — relying on the trigger seeing NULL on UPDATE but possibly the old value on INSERT (if the heap path ever puts something there pre-trigger).
- [ISSUE-correctness: TG_LEVEL falls through to elog(ERROR) on an unrecognized event type (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:1453`-`:1464`. Good defensiveness.

### Simple-expr caching & search_path / role

- [ISSUE-correctness: cast_expr_hash is never invalidated on pg_cast change (from-comment, likely)] — `source/src/pl/plpgsql/src/pl_exec.c:138`-`:141` — explicit acknowledgment "we don't bother". Session-wide. A `CREATE CAST` mid-session won't pick up; sessions started before a cast definition see the old behavior. Probably acceptable since cast changes are rare, but a hardening project might wire an invalidation callback.
- [ISSUE-correctness: simple-expression CachedPlan validity is delegated to plancache.c (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:6161`-`:6172` — `CachedPlanIsSimplyValid` is the entire trust boundary. If plancache.c misses an invalidation (search_path change, role change, function redefinition), the fast path silently re-runs the wrong expression. Worth noting in any review of plancache.
- [ISSUE-correctness: replanning resets `expr_simple_expr` to NULL "to leave sane state with no dangling pointers in case we fail while replanning" but then re-checks via `CachedPlanAllowsSimpleValidityCheck`; if the new plan no longer qualifies as simple, we degrade to non-simple silently (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:6186`-`:6234`. The "non-SRF replaced by SRF" edge case (`:6213`) is handled, but the degradation is not visible to the user.
- [ISSUE-defense-in-depth: simple-expr fast path uses `expr_simple_mutable && !readonly_func` to decide whether to push a fresh snapshot; a buggy contain_mutable_functions verdict could let stale data leak in (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:6296`-`:6302`. `contain_mutable_functions` is the trust boundary. Functions mis-labeled IMMUTABLE will skip the snapshot push and see stale data.

### Memory & resource discipline

- [ISSUE-memory: function-main-context leaks are acknowledged as tolerated (from-comment, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:108`-`:113` — "This is usually the CurrentMemoryContext while running code in this module (which is not good, because careless coding can easily cause function-lifespan memory leaks, but we live with it for now)". A long-running function in a session that doesn't exit accumulates these.
- [ISSUE-memory: CASE statement rebuilds t_var->datatype on type drift, leaks the old PLpgSQL_type into fn_cxt (from-comment, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:2605`-`:2611` — explicit acknowledgment.
- [ISSUE-memory: shared_simple_eval_estate is per-transaction but the cast hash entries (cast_exprstate fields) are per-session, so an aborted transaction abandons exprstate trees that still live in cast_entry but with stale `cast_lxid` — re-checked at next use via `cast_entry->cast_lxid != curlxid` (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:8209`-`:8217`. Correct, but a transaction-abort that aborts inside `do_cast_value` leaves `cast_in_use=true` until the next xact reset.
- [ISSUE-concurrency: per-process state only — no shared-memory concerns, but the assumption that each backend has its own pl_exec state is implicit (nit)] — `source/src/pl/plpgsql/src/pl_exec.c:91`-`:102`, `:178`-`:179`. All session-wide globals (`shared_simple_eval_estate`, `cast_expr_hash`, `shared_cast_hash`, `simple_econtext_stack`, `shared_simple_eval_resowner`) are process-local. Correct, but assumes the backend-fork model.

### Atomic vs non-atomic context

- [ISSUE-correctness: non-atomic detoasting in assign_simple_var is the only barrier against stale-TOAST-pointer bugs after COMMIT (verified-by-code, likely)] — `source/src/pl/plpgsql/src/pl_exec.c:8896`-`:8918` — comment notes this elsewhere requires operations on expanded records to request detoasting too. Any code path that assigns a varlena to a var in non-atomic context and bypasses `assign_simple_var` is a latent bug.
- [ISSUE-correctness: exec_for_query skips prefetch in non-atomic to avoid dangling TOAST refs after COMMIT (from-comment, verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:5959`-`:5967`. Comment is explicit. Performance hit accepted.

### Polymorphic / composite return

- [ISSUE-correctness: composite-result RECORDOID return path passes back as-is, "what this means in practice is that the caller is expecting any old generic rowtype" (from-comment, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:732`-`:744`. Documented behavior; means RECORD-returning functions don't enforce structural consistency.
- [ISSUE-correctness: coerce_function_result_tuple has a "duplicating the guts of datumCopy() :-(" workaround for expanded records with wrong type ID (from-comment, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:866`-`:887`. Acknowledged code smell.
- [ISSUE-correctness: PLpgSQL_var being asked to return as composite errors only when non-NULL — NULL slips through "for consistency with historical behavior" (from-comment, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:3275`-`:3287`.

### Strict-mode / cardinality

- [ISSUE-correctness: SELECT INTO single-target fast path skips cardinality check entirely (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:4300`-`:4356` — the fast-path for "simple expression + 1-field row" never executes the underlying SQL through SPI; FOUND=true and `eval_processed=1` are set unconditionally. For a `SELECT col INTO x` whose plan was downgraded from "simple" between calls, behavior matches; but if the same statement re-routed through the slow path due to invalidation, it would suddenly start checking cardinality. Subtle behavioral inconsistency.
- [ISSUE-correctness: too_many_rows_level is a configurable level (ERROR via plpgsql.extra_errors, WARNING via plpgsql.extra_warnings) (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:4250`-`:4253`, `:4495`-`:4511`. Default is silent. Auditors should know the GUC.

### Snapshot management

- [ISSUE-correctness: EnsurePortalSnapshotExists is called once at the top of every simple-expr eval (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:6154`. After a COMMIT, this provides a snapshot — but the snapshot is taken under the *current* user/search_path/etc. Procedures that COMMIT inside a security-definer call need to be aware that subsequent simple-expr evals see a different snapshot.
- [ISSUE-correctness: need_snapshot decision uses `expr_simple_mutable`; immutable-but-actually-mutable functions skip snapshot push and may read stale data (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:6297`. Trust boundary at `contain_mutable_functions`.

### Misc

- [ISSUE-api-shape: plpgsql_destroy_econtext asserts that the top of stack matches estate->eval_econtext, so any mismatch (e.g., a plugin that mucks with the stack) crashes the backend (verified-by-code, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:8793`-`:8794`.
- [ISSUE-documentation: copy_plpgsql_datums has the comment "This must agree with plpgsql_finish_datums on what is copiable" — a manual cross-file coupling (from-comment, nit)] — `source/src/pl/plpgsql/src/pl_exec.c:1370`.
- [ISSUE-correctness: instantiate_empty_record_variable throws ERROR for `record` (RECORDOID) — "is not assigned yet" (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:7916`-`:7920`. A NULL record field access on an uninitialized `record`-declared variable trips this.
- [ISSUE-correctness: plugin pointers are dereferenced everywhere without NULL check inside the if (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:629`, `:797`, `:1047`, `:1151`, `:1672`, `:2051`. Pattern `if (*plpgsql_plugin_ptr && (*plpgsql_plugin_ptr)->func_beg)` — assumes `plpgsql_plugin_ptr` itself is non-NULL (it's initialized in pl_handler). A malformed extension could violate.
- [ISSUE-correctness: format_expr_params and format_preparedparamsdata reveal parameter values in error details when `print_strict_params` is on (verified-by-code, maybe)] — `source/src/pl/plpgsql/src/pl_exec.c:9121`, `:9178`, used at `:4481`, `:4500`, `:4670`, `:4689`. If a logging integration captures error details, parameter values appear in logs. Documented GUC behavior, but security-relevant when the parameters contain PII.
- [ISSUE-correctness: error-context callbacks use `_(estate->err_text)` — gettext on a NULL-tolerant pointer; but err_text being NULL falls into the else branch (verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:1262`-`:1302`. Looks safe.
- [ISSUE-correctness: paramFetch is no longer used during query execution (only planning/serialization), but the dummy-param branch (`ok = false`) trusts `expr->paramnos` to be correct (from-comment, verified-by-code)] — `source/src/pl/plpgsql/src/pl_exec.c:6422`-`:6430`. If `paramnos` is out-of-date relative to the plan, the planner could see wrong types.
- [ISSUE-api-shape: exec_prepare_plan can throw after saving the plan in expr->plan; the comment at `:4188`-`:4203` warns "extra steps at the end are unsafe" because re-execution would skip them. Existing callers comply by putting only the prepare call inside the `if (expr->plan == NULL)` block.
