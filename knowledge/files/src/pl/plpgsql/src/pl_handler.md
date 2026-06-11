# pl_handler.c

## One-line summary

The PL/pgSQL language handler — the three SQL-visible entrypoints (`plpgsql_call_handler`, `plpgsql_inline_handler`, `plpgsql_validator`) that the core function manager dispatches to whenever a PL/pgSQL function, anonymous `DO` block, or `CREATE FUNCTION ... LANGUAGE plpgsql` validation runs, plus the module's GUC registration and `_PG_init` library load.

Source pin: `e18b0cb7344`. File length: 550 lines. [verified-by-code]

## Public API

All three handlers are wrapped with `PG_FUNCTION_INFO_V1` and exposed via the `language_handler` / `inline_handler` / `function_validator` rows in `pg_language`/`pg_proc`. They are not declared in `plpgsql.h`; the fmgr dispatch table reaches them through `_PG_init`-installed lookup.

- `void _PG_init(void)` — `source/src/pl/plpgsql/src/pl_handler.c:148` — library load-time init. Registers all five `plpgsql.*` GUCs, marks the `plpgsql` prefix reserved, hooks `RegisterXactCallback(plpgsql_xact_cb, NULL)` and `RegisterSubXactCallback(plpgsql_subxact_cb, NULL)`, and resolves the optional `PLpgSQL_plugin` rendezvous variable. Guarded by a static `inited` flag (`pl_handler.c:151`). [verified-by-code]
- `Datum plpgsql_call_handler(PG_FUNCTION_ARGS)` — `pl_handler.c:223` — function/trigger dispatch entry. Connects SPI (nonatomic if called as `CALL` from a procedure context, atomic otherwise), `plpgsql_compile` to find-or-build the function, increments `func->cfunc.use_count`, optionally creates a procedure-lifespan `ResourceOwner`, then dispatches to one of `plpgsql_exec_trigger` / `plpgsql_exec_event_trigger` / `plpgsql_exec_function` in a `PG_TRY`/`PG_FINALLY`. [verified-by-code]
- `Datum plpgsql_inline_handler(PG_FUNCTION_ARGS)` — `pl_handler.c:315` — anonymous `DO` block entry. Takes a single `InlineCodeBlock` argument, compiles via `plpgsql_compile_inline`, builds a private `EState` and `ResourceOwner` whose lifetime is *not* tied to the calling transaction (so they survive `COMMIT`/`ROLLBACK` inside the DO block), runs `plpgsql_exec_function`, and unconditionally frees the function's subsidiary memory at the end. [verified-by-code]
- `Datum plpgsql_validator(PG_FUNCTION_ARGS)` — `pl_handler.c:441` — `CREATE FUNCTION` validator. Calls `CheckFunctionValidatorAccess` first; returns `VOID` silently if access is denied. Otherwise validates return/argument types against PL/pgSQL's pseudotype rules and, if `check_function_bodies = on`, sets up a fake fcinfo and test-compiles the body via `plpgsql_compile(..., true)`. [verified-by-code]
- `PG_MODULE_MAGIC_EXT(.name = "plpgsql", .version = PG_VERSION)` — `pl_handler.c:34` — magic block for dynamic-loader compatibility. [verified-by-code]

GUCs registered (all in `_PG_init`):

- `plpgsql.variable_conflict` — `PGC_SUSET` enum (`error|use_variable|use_column`), default `error`. `pl_handler.c:158`. [verified-by-code]
- `plpgsql.print_strict_params` — `PGC_USERSET` bool, default `false`. `pl_handler.c:167`. [verified-by-code]
- `plpgsql.check_asserts` — `PGC_USERSET` bool, default `true`. `pl_handler.c:175`. [verified-by-code]
- `plpgsql.extra_warnings` — `PGC_USERSET` `GUC_LIST_INPUT` string, default `"none"`. `pl_handler.c:183`. [verified-by-code]
- `plpgsql.extra_errors` — `PGC_USERSET` `GUC_LIST_INPUT` string, default `"none"`. `pl_handler.c:193`. [verified-by-code]

Module-scope globals exported to other plpgsql .c files (declared `extern` in `plpgsql.h`):

- `int plpgsql_variable_conflict = PLPGSQL_RESOLVE_ERROR` — `pl_handler.c:47`. [verified-by-code]
- `bool plpgsql_print_strict_params = false` — `pl_handler.c:49`. [verified-by-code]
- `bool plpgsql_check_asserts = true` — `pl_handler.c:51`. [verified-by-code]
- `int plpgsql_extra_warnings`, `plpgsql_extra_errors` — `pl_handler.c:55-56`. [verified-by-code]
- `PLpgSQL_plugin **plpgsql_plugin_ptr` — `pl_handler.c:59`. The rendezvous pointer plugin libraries set in their own `_PG_init`. [verified-by-code]

## Key invariants

- **`_PG_init` runs exactly once per backend.** The static `inited` flag (`pl_handler.c:151-154`) makes a second call a no-op; the comment "should be redundant now" notes that fmgr already guarantees this. [from-comment]
- **Inline-block private resources MUST survive COMMIT/ROLLBACK.** The `simple_eval_estate` and `simple_eval_resowner` for a `DO` block are created with `ResourceOwnerCreate(NULL, ...)` — a NULL parent — precisely so that transaction abort cannot release them; the handler then guarantees cleanup in both the success path (`pl_handler.c:411-414`) and the `PG_CATCH` path (`pl_handler.c:395-397`). Adding allocations between resource creation and `PG_TRY` would risk a process-lifetime leak. [from-comment]
- **Procedure resowner allocation is fragile.** The same hazard applies to `plpgsql_call_handler`: if `nonatomic && func->requires_procedure_resowner`, the resowner is created at `pl_handler.c:258-260` and the comment explicitly warns "be very wary of adding any code between here and the PG_TRY block." [from-comment]
- **`use_count` is the anti-recompile lock.** `func->cfunc.use_count++` (`pl_handler.c:249`, `:336`) prevents the function-cache invalidator from yanking the compiled tree while it's executing; the decrement happens in `PG_FINALLY`/`PG_CATCH` (`pl_handler.c:286`, `:400`, `:417`). For the inline path the post-execution assert `func->cfunc.use_count == 0` (`pl_handler.c:401`, `:418`) encodes that nobody else can possibly hold a reference. [verified-by-code]
- **`cur_estate` is save-restore around the call.** `pl_handler.c:246` saves and `:287` restores `func->cur_estate`, supporting recursive entry into the same compiled function. [verified-by-code]
- **Validator early-out preserves least privilege.** If `CheckFunctionValidatorAccess` returns false (typically because the caller is not the function owner / no `USAGE` on language), the validator returns silently with no error and no body compile (`pl_handler.c:456-457`). This is a contract of all validators, not specific to plpgsql. [verified-by-code]
- **Pseudotype acceptance is whitelist-only.** Return: `TRIGGER`, `EVENT_TRIGGER`, `RECORD`, `VOID`, or any polymorphic type (`pl_handler.c:469-482`). Args: `RECORD` or polymorphic only (`pl_handler.c:490-498`). Everything else `ERRCODE_FEATURE_NOT_SUPPORTED`. [verified-by-code]
- **Body validation is gated by `check_function_bodies`.** `pl_handler.c:502` — if a DBA has set this off (common during dump restore), the validator does only signature checks; bad bodies survive `CREATE FUNCTION` and explode at first call. [verified-by-code]

## Notable internals

- **Atomic/nonatomic SPI mode selection.** `plpgsql_call_handler` derives `nonatomic` from `fcinfo->context` being a `CallContext` with `atomic == false` (`pl_handler.c:233-235`). This is what lets a procedure run `COMMIT`/`ROLLBACK` internally: SPI must be in nonatomic mode so the transaction can be ended underneath it. The inline handler reads `codeblock->atomic` from the `InlineCodeBlock` node instead (`pl_handler.c:330`). [verified-by-code]
- **GUC check hook for `extra_warnings`/`extra_errors` is shared.** Both string GUCs use `plpgsql_extra_checks_check_hook` (`pl_handler.c:62`) which parses comma-separated keywords (`shadowed_variables`, `too_many_rows`, `strict_multi_assignment`), with two reserved keywords `all` and `none` that cannot be combined with others. The parsed bitmask is stashed in `*extra` via `guc_malloc(LOG, ...)` and copied to the right module-scope `int` by the assign hooks. [verified-by-code]
- **Inline-block `PG_CATCH` does manual subxact cleanup.** Before freeing the private `EState`, the catch arm calls `plpgsql_subxact_cb(SUBXACT_EVENT_ABORT_SUB, GetCurrentSubTransactionId(), 0, NULL)` to evict any `simple_econtext_stack` entries pointing into that EState (`pl_handler.c:390-392`). The comment notes this "cheats a bit knowing that plpgsql_subxact_cb does not pay attention to its parentSubid argument" — a tight coupling between two files. [from-comment]
- **Validator builds a fake `TriggerData`/`EventTriggerData` for compile.** When the function's return type signals a DML or event trigger, the validator stuffs a zeroed `TriggerData` (or `EventTriggerData`) into `fake_fcinfo->context` so that the compiler will set up `NEW`/`OLD`/`TG_*` namespace entries instead of normal arg datums (`pl_handler.c:524-535`). [verified-by-code]
- **No real load-time work happens here.** Apart from GUCs and xact callback registration, `_PG_init` does not pre-build any caches, open any catalogs, or touch shared memory. Plugin discovery is purely passive — `find_rendezvous_variable` returns a pointer that's NULL until some other library decides to populate it. [verified-by-code]
- **`MarkGUCPrefixReserved("plpgsql")`** (`pl_handler.c:203`) is what makes `SET plpgsql.foo = ...` reject unknown sub-GUCs after this load completes, but only after — anything that runs before plpgsql loads can squat on `plpgsql.x`. [verified-by-code]

## Cross-references

- `source/src/pl/plpgsql/src/pl_comp.c` — `plpgsql_compile`, `plpgsql_compile_inline`, `plpgsql_parser_setup` (forward-declared in `plpgsql.h:1223-1227`).
- `source/src/pl/plpgsql/src/pl_exec.c` — `plpgsql_exec_function`, `plpgsql_exec_trigger`, `plpgsql_exec_event_trigger`, `plpgsql_xact_cb`, `plpgsql_subxact_cb`.
- `source/src/pl/plpgsql/src/pl_funcs.c` — `plpgsql_free_function_memory` (called from the inline handler).
- `source/src/backend/utils/fmgr/fmgr.c` — calls `CALLED_AS_TRIGGER` / `CALLED_AS_EVENT_TRIGGER` macros checked in `pl_handler.c:268,271`.
- `source/src/backend/utils/cache/funccache.c` — `CachedFunction.use_count` discipline; `RegisterXactCallback` machinery.
- `source/src/backend/utils/cache/plancache.c` — `ReleaseAllPlanCacheRefsInOwner` used at `pl_handler.c:292,396,413`.
- `source/src/backend/utils/misc/guc.c` — `DefineCustomEnumVariable`, `DefineCustomBoolVariable`, `DefineCustomStringVariable`, `MarkGUCPrefixReserved`.
- `source/src/backend/commands/functioncmds.c` — `CheckFunctionValidatorAccess` (the gatekeeper for `plpgsql_validator`).
- `source/src/backend/executor/spi.c` — `SPI_connect_ext`, `SPI_OPT_NONATOMIC`.

## Issues spotted

- [ISSUE-error-handling: `plpgsql_extra_checks_check_hook` calls `list_free(elemlist)` after the `SplitIdentifierString` failure path even though that path leaves `elemlist` in an unspecified state (nit)] — `source/src/pl/plpgsql/src/pl_handler.c:81-87` — `SplitIdentifierString` documents that it may return without initializing `elemlist` on failure. In practice it always sets `*elemlist = NIL` first, so the `list_free(NIL)` is harmless, but the pattern reads as relying on implementation detail. nit.
- [ISSUE-defense-in-depth: `plpgsql.check_asserts` is `PGC_USERSET` and default `true`, but any user can `SET plpgsql.check_asserts = off` for the session and silently disable every `ASSERT` in every function they call (maybe)] — `source/src/pl/plpgsql/src/pl_handler.c:175-181` — by design (the GUC's docstring frames asserts as a debugging aid), but worth flagging that authors who rely on `ASSERT` as a runtime invariant guard are wrong: a malicious caller can disable them per-session before invoking the function. The `PGC_USERSET` scope means even SECURITY DEFINER doesn't protect the assertion (unless the function sets the GUC itself). maybe.
- [ISSUE-defense-in-depth: `plpgsql.variable_conflict` is `PGC_SUSET` (superuser only), which means non-superuser DBs cannot change the per-database default away from `error` (maybe)] — `source/src/pl/plpgsql/src/pl_handler.c:164` — the rationale is presumably that changing variable-vs-column resolution can change query meaning silently, so it must be a superuser-vetted decision. Per-function `#variable_conflict` pragma is the escape hatch for users. Documenting here so a reviewer doesn't accidentally relax it. maybe.
- [ISSUE-correctness: `_PG_init`'s "should be redundant now" comment hints fmgr already serializes, but the guard is still a *static* without any atomic / barrier (nit)] — `source/src/pl/plpgsql/src/pl_handler.c:150-154` — in PG's per-process backend model `_PG_init` runs single-threaded so no barrier is needed; the comment is correct. Worth knowing for anyone porting plpgsql to a threaded execution model. nit.
- [ISSUE-audit-gap: validator returns silently when `CheckFunctionValidatorAccess` denies, with no LOG (maybe)] — `source/src/pl/plpgsql/src/pl_handler.c:456-457` — by validator contract this is correct (the create proceeds), but it means an audit log can't distinguish "validation skipped because caller wasn't owner" from "validation passed." Probably fine; flagged because Phase D is auditing privilege boundaries. maybe.
- [ISSUE-error-handling: `plpgsql_inline_handler`'s `PG_CATCH` does `plpgsql_free_function_memory(func)` without re-checking that `func` was assigned (nit)] — `source/src/pl/plpgsql/src/pl_handler.c:404` — `plpgsql_compile_inline` runs before the `PG_TRY` (line 333), and the use-count increment is also before the try. If `plpgsql_compile_inline` itself longjmps, control unwinds without entering the catch arm, so we never reach the `free`. The catch arm is therefore correct *only* because the try begins after both compile and use-count++. A future refactor that moves the use-count increment into the try would break this. nit.
- [ISSUE-documentation: the comment on `procedure_resowner` reuse in the inline handler (`pl_handler.c:357-360`) is the only place documenting that the simple-eval and procedure resowners can be the same object; this isn't reflected in `plpgsql.h`'s `PLpgSQL_execstate` definition where they appear as separate fields (`plpgsql.h:1063,1066`) (nit)] — `source/src/pl/plpgsql/src/pl_handler.c:357-360` — header readers may assume the two are always distinct. nit.
