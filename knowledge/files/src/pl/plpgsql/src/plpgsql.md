# plpgsql.h

## One-line summary

The single canonical header for the PL/pgSQL language implementation — declares every AST node type (`PLpgSQL_stmt_*`, `PLpgSQL_datum`, `PLpgSQL_expr`), the compiled-function and runtime-execstate structs, the instrumentation `PLpgSQL_plugin` hook interface, all extern globals, and every function prototype shared between `pl_handler.c`, `pl_comp.c`, `pl_exec.c`, `pl_funcs.c`, `pl_scanner.c`, `pl_gram.y`. The "landmark" file for understanding plpgsql's shape.

Source pin: `e18b0cb7344`. File length: 1333 lines. [verified-by-code]

## Public API

### Enums driving tagged unions

- `PLpgSQL_nsitem_type` — `plpgsql.h:42` — LABEL/VAR/REC for the compile-time namespace stack. [verified-by-code]
- `PLpgSQL_label_type` — `plpgsql.h:52` — BLOCK/LOOP/OTHER, stored as `itemno` in LABEL nsitems. [verified-by-code]
- `PLpgSQL_datum_type` — `plpgsql.h:62` — VAR/ROW/REC/RECFIELD/PROMISE. The discriminator for every `PLpgSQL_datum`. [verified-by-code]
- `PLpgSQL_promise_type` — `plpgsql.h:74` — 11 values: NONE plus all the trigger context promises (TG_NAME, TG_WHEN, TG_OP, TG_RELID, TG_TABLE_NAME, TG_TABLE_SCHEMA, TG_NARGS, TG_ARGV, TG_EVENT, TG_TAG, TG_LEVEL). Lazily computed on first read. [verified-by-code]
- `PLpgSQL_type_type` — `plpgsql.h:93` — SCALAR/REC/PSEUDO classification of a `PLpgSQL_type`. [verified-by-code]
- `PLpgSQL_stmt_type` — `plpgsql.h:103` — 26-value statement tag enum: BLOCK, ASSIGN, IF, CASE, LOOP, WHILE, FORI, FORS, FORC, FOREACH_A, EXIT, RETURN, RETURN_NEXT, RETURN_QUERY, RAISE, ASSERT, EXECSQL, DYNEXECUTE, DYNFORS, GETDIAG, OPEN, FETCH, CLOSE, PERFORM, CALL, COMMIT, ROLLBACK. [verified-by-code]
- Anonymous return-code enum — `plpgsql.h:137` — `PLPGSQL_RC_OK`, `PLPGSQL_RC_EXIT`, `PLPGSQL_RC_RETURN`, `PLPGSQL_RC_CONTINUE`. [verified-by-code]
- `PLpgSQL_getdiag_kind` — `plpgsql.h:148` — 13 items used by `GET DIAGNOSTICS`. [verified-by-code]
- `PLpgSQL_raise_option_type` — `plpgsql.h:168` — ERRCODE/MESSAGE/DETAIL/HINT/COLUMN/CONSTRAINT/DATATYPE/TABLE/SCHEMA. [verified-by-code]
- `PLpgSQL_resolve_option` — `plpgsql.h:184` — ERROR/VARIABLE/COLUMN (mirrored by the `plpgsql.variable_conflict` GUC). [verified-by-code]
- `PLpgSQL_rwopt` — `plpgsql.h:194` — UNKNOWN/NOPE/TRANSFER/INPLACE; tracks read-write expanded-datum optimization status for an expression. [verified-by-code]
- `PLpgSQL_trigtype` — `plpgsql.h:948` — DML_TRIGGER/EVENT_TRIGGER/NOT_TRIGGER, stored in `PLpgSQL_function.fn_is_trigger`. [verified-by-code]
- `IdentifierLookup` — `plpgsql.h:1178` — NORMAL/DECLARE/EXPR mode the scanner uses to decide whether an identifier should resolve against the plpgsql namespace. [verified-by-code]

### Tagged-union base structs

- `PLpgSQL_datum` (`plpgsql.h:298`) — `{dtype, dno}`. Common header of all variable-style nodes; the discriminator is `dtype`. [verified-by-code]
- `PLpgSQL_variable` (`plpgsql.h:310`) — `{dtype, dno, refname, lineno, isconst, notnull, default_val}`. Common header of `PLpgSQL_var`, `PLpgSQL_row`, `PLpgSQL_rec`. The first seven fields are repeated verbatim at the top of each child struct (`plpgsql.h:332-342`, `:386-396`, `:412-422`) — classic PG "embed by repetition" pattern. [verified-by-code]
- `PLpgSQL_stmt` (`plpgsql.h:476`) — `{cmd_type, lineno, stmtid}`. Same trick: every `PLpgSQL_stmt_<x>` struct repeats these three fields as its first members. [verified-by-code]

### Variant datum structs

- `PLpgSQL_var` (`plpgsql.h:332`) — scalar; also used for `DTYPE_PROMISE`. Carries `value`/`isnull`/`freeval` runtime triple, and cursor-specific fields (`cursor_explicit_expr`, `cursor_options`) when declared as `CURSOR FOR`. [verified-by-code]
- `PLpgSQL_row` (`plpgsql.h:386`) — multi-target list (INTO clause, multi-OUT). `refname` set to literal `"(unnamed row)"` per comment. [from-comment]
- `PLpgSQL_rec` (`plpgsql.h:412`) — composite/RECORD. Backed at runtime by an `ExpandedRecordHeader *erh`. [verified-by-code]
- `PLpgSQL_recfield` (`plpgsql.h:443`) — handle to a single field of a `PLpgSQL_rec`, cached by name with a tupdesc-id validity check. [verified-by-code]
- `PLpgSQL_type` (`plpgsql.h:210`) — the plpgsql wrapper around a pg_type entry, with `ttype` discriminator and a `TypeCacheEntry` pointer for composites. [verified-by-code]
- `PLpgSQL_expr` (`plpgsql.h:230`) — a SQL string + its parsed `SPIPlanPtr` + the "simple expression" fast-path cache (`expr_simple_expr`, `expr_simple_state`, `expr_simple_lxid`). This is *the* central object in plpgsql performance. [verified-by-code]
- `PLpgSQL_nsitem` (`plpgsql.h:460`) — single namespace stack entry. Uses `FLEXIBLE_ARRAY_MEMBER` for the name. [verified-by-code]

### Statement structs (every entry of the `PLpgSQL_stmt_type` enum has one)

- `PLpgSQL_stmt_block` (`plpgsql.h:525`) — DECLARE/BEGIN/EXCEPTION/END.
- `PLpgSQL_stmt_assign` (`plpgsql.h:540`).
- `PLpgSQL_stmt_perform` (`plpgsql.h:552`).
- `PLpgSQL_stmt_call` (`plpgsql.h:563`) — `is_call` distinguishes `CALL` from in-procedure `DO`; `target` holds INTO targets for procedures with OUT args.
- `PLpgSQL_stmt_commit` / `_rollback` (`plpgsql.h:576,587`) — both carry a `chain` bool for `COMMIT/ROLLBACK AND CHAIN`.
- `PLpgSQL_stmt_getdiag` (`plpgsql.h:607`) — items are `PLpgSQL_diag_item` (`plpgsql.h:598`).
- `PLpgSQL_stmt_if` (`plpgsql.h:619`) plus `PLpgSQL_if_elsif` (`plpgsql.h:633`).
- `PLpgSQL_stmt_case` (`plpgsql.h:643`) plus `PLpgSQL_case_when` (`plpgsql.h:658`).
- `PLpgSQL_stmt_loop` / `_while` (`plpgsql.h:668,680`).
- `PLpgSQL_stmt_fori` (`plpgsql.h:693`) — integer FOR.
- `PLpgSQL_stmt_forq` (`plpgsql.h:712`) — common supertype of the three query-driven FOR variants; the first seven fields up through `body` must match.
- `PLpgSQL_stmt_fors` (`plpgsql.h:725`) — FOR over SELECT.
- `PLpgSQL_stmt_forc` (`plpgsql.h:740`) — FOR over cursor.
- `PLpgSQL_stmt_dynfors` (`plpgsql.h:756`) — FOR over EXECUTE.
- `PLpgSQL_stmt_foreach_a` (`plpgsql.h:772`).
- `PLpgSQL_stmt_open` / `_fetch` / `_close` (`plpgsql.h:787,803,820`).
- `PLpgSQL_stmt_exit` (`plpgsql.h:831`) — `is_exit` flag distinguishes EXIT vs CONTINUE.
- `PLpgSQL_stmt_return` / `_return_next` / `_return_query` (`plpgsql.h:844,856,868`).
- `PLpgSQL_stmt_raise` (`plpgsql.h:881`) plus `PLpgSQL_raise_option` (`plpgsql.h:896`).
- `PLpgSQL_stmt_assert` (`plpgsql.h:905`).
- `PLpgSQL_stmt_execsql` (`plpgsql.h:917`) — static SQL with optional INTO.
- `PLpgSQL_stmt_dynexecute` (`plpgsql.h:933`) — EXECUTE of dynamic SQL string.
- Exception machinery: `PLpgSQL_condition` (`plpgsql.h:492`), `PLpgSQL_exception_block` (`plpgsql.h:505`), `PLpgSQL_exception` (`plpgsql.h:515`). `#define PLPGSQL_OTHERS (-1)` (`plpgsql.h:500`).

### Top-level runtime structs

- `PLpgSQL_function` (`plpgsql.h:958`) — the compiled-once-per-signature object. Wraps a `CachedFunction cfunc` (the funccache.c handle), has `fn_oid`, `fn_is_trigger`, the canonical `datums` array, the parsed `action` body, plus the *transient* `cur_estate` pointer that nests across recursive calls. Flags: `requires_procedure_resowner`, `has_exception_block`. [verified-by-code]
- `PLpgSQL_execstate` (`plpgsql.h:1012`) — one per active call. Pointers to the trigger data, the SRF tuplestore, the simple-expression `EState`/resowner, the optional procedure resowner, the cast hash, statement-lifespan memory context, ParamListInfo for executor handoff, and the `cur_error` set inside an EXCEPTION handler. [verified-by-code]
- `PLpgSQL_plugin` (`plpgsql.h:1124`) — instrumentation hook table. Plugin sets the first five callbacks (`func_setup`/`func_beg`/`func_end`/`stmt_beg`/`stmt_end`); PL/pgSQL fills in the next five so the plugin can reuse internals (`error_callback`, `assign_expr`, `assign_value`, `eval_datum`, `cast_value`). [verified-by-code]

### Parse-time helper structs

- `PLword` (`plpgsql.h:1155`), `PLcword` (`plpgsql.h:1161`), `PLwdatum` (`plpgsql.h:1166`) — the three identifier-resolution result types the scanner hands to the grammar. [verified-by-code]

### Externs

- `IdentifierLookup plpgsql_IdentifierLookup` — `plpgsql.h:1185`. [verified-by-code]
- `int plpgsql_variable_conflict`, `bool plpgsql_print_strict_params`, `bool plpgsql_check_asserts` — `plpgsql.h:1187-1191` (defined in `pl_handler.c`). [verified-by-code]
- Extra-check bitmask: `PLPGSQL_XCHECK_NONE`, `_SHADOWVAR (1<<1)`, `_TOOMANYROWS (1<<2)`, `_STRICTMULTIASSIGNMENT (1<<3)`, `_ALL ((int) ~0)` — `plpgsql.h:1194-1198`. [verified-by-code]
- `int plpgsql_extra_warnings`, `plpgsql_extra_errors` — `plpgsql.h:1200-1201`. [verified-by-code]
- Compile-state externs: `bool plpgsql_check_syntax`, `bool plpgsql_DumpExecTree`, `int plpgsql_nDatums`, `PLpgSQL_datum **plpgsql_Datums`, `char *plpgsql_error_funcname`, `PLpgSQL_function *plpgsql_curr_compile`, `MemoryContext plpgsql_compile_tmp_cxt` — `plpgsql.h:1203-1212`. [verified-by-code]
- `PLpgSQL_plugin **plpgsql_plugin_ptr` — `plpgsql.h:1214`. [verified-by-code]

### Function prototypes (grouped by source file)

- pl_comp.c: `plpgsql_compile`, `plpgsql_compile_inline`, `plpgsql_parser_setup`, `plpgsql_parse_word`/`_dblword`/`_tripword`, `plpgsql_parse_wordtype`/`_cwordtype`/`_wordrowtype`/`_cwordrowtype`, `plpgsql_build_datatype`/`_datatype_arrayof`, `plpgsql_build_variable`/`_record`/`_recfield`, `plpgsql_recognize_err_condition`, `plpgsql_parse_err_condition`, `plpgsql_adddatum`, `plpgsql_add_initdatums` — `plpgsql.h:1223-1254`. [verified-by-code]
- pl_exec.c: `plpgsql_exec_function`, `plpgsql_exec_trigger`, `plpgsql_exec_event_trigger`, `plpgsql_xact_cb`, `plpgsql_subxact_cb`, `plpgsql_exec_get_datum_type`/`_info` — `plpgsql.h:1259-1277`. [verified-by-code]
- pl_funcs.c namespace handling: `plpgsql_ns_init`/`_push`/`_pop`/`_top`/`_additem`/`_lookup`/`_lookup_label`/`_find_nearest_loop` — `plpgsql.h:1282-1293`. [verified-by-code]
- pl_funcs.c other: `plpgsql_stmt_typename`, `plpgsql_getdiag_kindname`, `plpgsql_mark_local_assignment_targets`, `plpgsql_free_function_memory`, `plpgsql_delete_callback`, `plpgsql_dumptree` — `plpgsql.h:1298-1303`. [verified-by-code]
- pl_scanner.c: `plpgsql_yylex`, `plpgsql_token_length`, `plpgsql_push_back_token`, `plpgsql_token_is_unreserved_keyword`, `plpgsql_append_source_text`, `plpgsql_peek`/`_peek2`, `plpgsql_scanner_errposition`, `plpgsql_yyerror` (`pg_noreturn`), `plpgsql_location_to_lineno`, `plpgsql_latest_lineno`, `plpgsql_scanner_init`, `plpgsql_scanner_finish` — `plpgsql.h:1308-1326`. [verified-by-code]
- pl_gram.y: `plpgsql_yyparse` — `plpgsql.h:1331`. [verified-by-code]

`PGDLLEXPORT`-tagged externs (the API surface deliberately exported for plugins / external loaders): `plpgsql_compile`, `plpgsql_parser_setup`, `plpgsql_build_datatype`, `plpgsql_recognize_err_condition`, `plpgsql_exec_get_datum_type`, `plpgsql_ns_lookup`, `plpgsql_stmt_typename` — `plpgsql.h:1223, 1226, 1238, 1250, 1272, 1288, 1298`. [verified-by-code]

## Key invariants

- **Tag-dispatch convention.** Every node that participates in a tagged dispatch starts with its discriminator field at the same offset: `PLpgSQL_datum.dtype` (`plpgsql.h:300`), `PLpgSQL_stmt.cmd_type` (`plpgsql.h:478`), `PLpgSQL_type.ttype` (`plpgsql.h:214`). Pointers are upcast/downcast based on the first field. Reordering fields in *any* variant breaks the entire compiler. [verified-by-code]
- **`PLpgSQL_variable` substructure must match across variants.** The first seven fields of `PLpgSQL_var`, `PLpgSQL_row`, `PLpgSQL_rec` are identical (`plpgsql.h:332-340`, `:386-394`, `:412-420`) and explicitly commented `/* end of PLpgSQL_variable fields */`. Code in pl_exec.c casts among these freely. [from-comment]
- **`PLpgSQL_stmt_forq` is a common prefix of three FOR variants.** `fors`, `forc`, `dynfors` repeat the first seven fields of `forq` (`plpgsql.h:712-720`) explicitly commented `/* end of fields that must match PLpgSQL_stmt_forq */` at lines 733, 748, 764. Generic code in `exec_stmt_forq` casts to `PLpgSQL_stmt_forq *`. [from-comment]
- **`stmtid` is assigned 1..N per function** (`plpgsql.h:482-486`) — 0 is reserved as "not set / invalid." Plugins index per-statement metric arrays by `stmtid`. [from-comment]
- **`PLPGSQL_OTHERS` is reserved as a sentinel.** `#define PLPGSQL_OTHERS (-1)` (`plpgsql.h:500`) is documented as mustn't-collide with any `MAKE_SQLSTATE()` output, so exception-handler matching can use a single int. [from-comment]
- **Simple-expression validity is LXID-gated.** `PLpgSQL_expr.expr_simple_state` "probably points at garbage" unless `expr_simple_lxid == MyProc->lxid`; same gate for `expr_simple_plan_lxid` controlling the plan refcount (`plpgsql.h:278-289`). [from-comment]
- **PROMISE datums share the `PLpgSQL_var` struct.** A single `dtype` value (`PLPGSQL_DTYPE_PROMISE`) selects this behavior; `var->promise != PLPGSQL_PROMISE_NONE` is the "not yet computed" signal (`plpgsql.h:324-330`, `:360-365`). [from-comment]
- **Record variables are *always* expanded.** "We always store record variables as 'expanded' records" — `PLpgSQL_rec.erh` is a hot pointer, not lazily filled (`plpgsql.h:436-437`). [from-comment]
- **`PLpgSQL_function.cfunc` MUST be the first field** — `funccache.c` reaches into a `CachedFunction *` and assumes the plpgsql-specific struct extends it (`plpgsql.h:960`). Same idiom as Relation/RangeTblEntry. [inferred]
- **`paramLI` has no `ParamExternData` array.** `PLpgSQL_execstate.paramLI` is constructed dynamically: parameters are looked up on demand by `paramid == dno` (`plpgsql.h:1056-1059`). Don't iterate it as a fixed array. [from-comment]
- **Plugin pointer table is bidirectional.** First five fields are filled by the plugin in its own `_PG_init`; last five are filled by PL/pgSQL just before each `func_setup` call (`plpgsql.h:1111-1122`). Plugin must *not* preset the last five. [from-comment]

## Notable internals

- **`PLpgSQL_expr` is the workhorse.** It is *both* a parse-tree node (carries `query` text, `parseMode`, the namespace chain) *and* a runtime cache (the SPI plan, the simple-expression `Expr *`, the prepared `ExprState`, the read/write-expanded optimization fields, the LXID-stamped CachedPlan refcount). Five different pieces of state are co-located here because each instance is per-source-location and the per-execution cost of looking each up separately would be prohibitive. [verified-by-code]
- **Read/write expanded-object optimization.** `expr_rwopt` / `expr_rw_param` / `target_param` / `target_is_local` (`plpgsql.h:244-269`) implement the "assignment back into the same expanded datum can hand the value as R/W instead of forcing a copy" optimization — the reason `arr := array_append(arr, x)` is O(1) amortized for plpgsql arrays. [from-comment]
- **Two `MemoryContext` fields in execstate, used as a stack.** `stmt_mcontext` / `stmt_mcontext_parent` (`plpgsql.h:1072-1073`) — statement-lifespan scratch space that gets reset between statements; the parent pointer threads a stack so nested constructs can suspend the current scratch and use a deeper one. [verified-by-code]
- **`cur_estate` is the recursion hook.** `PLpgSQL_function.cur_estate` (`plpgsql.h:1006`) is overwritten by every call and save-restored by `plpgsql_call_handler` (see `pl_handler.md`). It exists so that error-context callbacks and other introspection can find the current execution state from the function pointer. [verified-by-code]
- **`paramLI` invariant: `paramid == dno`.** This is a tight contract with the executor: every PARAM_EXTERN Param node embedded in a compiled plan must have its `paramid` set to a valid datum index, and the executor will call back through `paramFetch` (defined elsewhere in pl_exec.c) to materialize the current value. [from-comment]
- **GUC bit assignments skip bit 0.** `PLPGSQL_XCHECK_SHADOWVAR = (1 << 1)` (`plpgsql.h:1195`) — bit 0 is unused, presumably reserved or originally meant for a since-removed check. [verified-by-code]
- **Statement and datum dispatch is by switch.** The header doesn't declare any vtable — every consumer (`pl_exec.c`, `pl_funcs.c`, `pl_funcs.c::plpgsql_free_function_memory`) does a `switch (stmt->cmd_type)` or `switch (datum->dtype)`. Adding a new node type requires touching every such switch. [inferred]

## Cross-references

- `source/src/pl/plpgsql/src/pl_handler.c` — sibling, holds the SQL-visible entry points and defines the GUCs externed here.
- `source/src/pl/plpgsql/src/pl_comp.c` — parser-tree builder, definer of `plpgsql_compile`, namespace setup; consumer of all the `PLpgSQL_stmt_*` constructors implicitly built by the grammar.
- `source/src/pl/plpgsql/src/pl_exec.c` — the giant switch on `cmd_type`; uses `PLpgSQL_execstate` as its working state.
- `source/src/pl/plpgsql/src/pl_funcs.c` — `plpgsql_free_function_memory`, namespace stack management, statement-typename strings.
- `source/src/pl/plpgsql/src/pl_scanner.c`, `pl_gram.y` — the front end declared via `plpgsql_yylex`/`plpgsql_yyparse`.
- `source/src/include/utils/funccache.h` — `CachedFunction` base struct embedded as the first field of `PLpgSQL_function`.
- `source/src/include/utils/expandedrecord.h` — `ExpandedRecordHeader` backing `PLpgSQL_rec.erh` and the `ExpandedRecordFieldInfo` in `PLpgSQL_recfield`.
- `source/src/include/utils/typcache.h` — `TypeCacheEntry` referenced by `PLpgSQL_type.tcache`.
- `source/src/include/executor/spi.h` — `SPIPlanPtr`, `SPITupleTable`.
- `source/src/include/utils/plancache.h` — `CachedPlanSource`, `CachedPlan` in `PLpgSQL_expr`.
- `source/src/include/nodes/params.h` — `ParamListInfo`.
- `source/src/include/access/xact.h`, `commands/trigger.h`, `commands/event_trigger.h` — pulled in for the callback enums and `TriggerData`/`EventTriggerData`.
- `source/src/backend/utils/cache/plancache.c` — owns the refcount discipline `PLpgSQL_expr.expr_simple_plan_lxid` participates in.

<!-- issues:auto:begin -->
- [Issue register — `plpgsql`](../../../../../issues/plpgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-api-shape: `PLpgSQL_function.cfunc` being the first field is a load-bearing convention that's nowhere asserted (maybe)] — `source/src/pl/plpgsql/src/plpgsql.h:958-960` — `funccache.c` likely casts a `CachedFunction *` to/from `PLpgSQL_function *` (or uses `offsetof(struct, cfunc)`); no `StaticAssertDecl` here forces the constraint. Reordering would compile and pass most tests, then crash. maybe.
- [ISSUE-api-shape: `PLpgSQL_variable` substructure invariant is enforced by copy-paste, not a macro or `pg_offsetof` assertion (maybe)] — `source/src/pl/plpgsql/src/plpgsql.h:310-319, 332-340, 386-394, 412-420` — the seven shared fields are repeated four times. A typo or reorder in any one copy silently breaks cross-casting in pl_exec.c. The comment `/* end of PLpgSQL_variable fields */` is the only signal. Other PG subsystems use `#define COMMON_FIELDS ...` for the same pattern. maybe.
- [ISSUE-api-shape: same copy-paste invariant for `PLpgSQL_stmt_forq` across `fors`/`forc`/`dynfors` (maybe)] — `source/src/pl/plpgsql/src/plpgsql.h:712-768`. Same rationale. maybe.
- [ISSUE-documentation: `PLPGSQL_XCHECK_SHADOWVAR = (1 << 1)` skips bit 0 with no comment explaining why (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1194-1198` — bit 0 is unused. If it's reserved for a removed check (e.g. a historical `PLPGSQL_XCHECK_ASSERTS`), a one-line comment would prevent a future patch from filling it with semantically-different meaning. nit.
- [ISSUE-defense-in-depth: `PLpgSQL_expr.expr_simple_state` is documented as "probably points at garbage" if LXID stale, but the struct has no MAGIC / sentinel so a stale read returns garbage without panic (maybe)] — `source/src/pl/plpgsql/src/plpgsql.h:282-289` — the LXID check is the only safety; a missed gate at a single caller would dereference garbage. The pattern is followed everywhere because it has to be. Worth flagging because Phase D is auditing trust boundaries — a fuzz test that skipped the LXID check would crash interestingly. maybe.
- [ISSUE-api-shape: `plpgsql_plugin_ptr` is a `PLpgSQL_plugin **` (pointer-to-pointer) with no documented thread-safety contract; PG's per-backend model makes this safe, but ports to threaded execution would race here (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1214` — fine in PG today. nit.
- [ISSUE-security: `PLpgSQL_stmt_dynexecute` (EXECUTE) and `PLpgSQL_stmt_dynfors` (FOR ... EXECUTE) hold a raw `PLpgSQL_expr *query` whose result text is passed to `pg_parse_query` at runtime — this is the SQL-injection surface inside plpgsql (likely)] — `source/src/pl/plpgsql/src/plpgsql.h:938, 765` — the data structure is correct; the security concern is that *users* writing plpgsql routinely build the `EXECUTE` string with `||` instead of `format(%I, %L, ...)`. The header offers no API hint or comment pointing at `quote_ident`/`quote_literal`/`format`. Defense-in-depth: a comment block on `PLpgSQL_stmt_dynexecute` documenting the injection model would help every reader. likely (re: documentation gap), confirmed (re: surface area).
- [ISSUE-documentation: header has no overall block comment explaining the parse tree → execstate model — readers must reverse-engineer from struct order (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1-30` — the only top comment is the standard copyright header. Given this is THE landmark file (1333 lines), a 20-line architectural overview at the top would pay back enormously. nit.
- [ISSUE-api-shape: `PLpgSQL_execstate` mixes "func metadata cache" (e.g. `fn_rettype`, `retistuple`, `retisset` at `plpgsql.h:1021-1025`) with truly per-call state — the former duplicate fields already in `PLpgSQL_function`, presumably for cache-line locality, but the duplication isn't commented (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1019-1025` — `func` is already a member at `:1014`, so `estate->func->fn_rettype` is reachable. Probably an optimization or a remnant of a refactor; the absence of a comment makes it look accidental. nit.
- [ISSUE-correctness: `PLpgSQL_function.cur_estate` is a raw mutable pointer with no documented save/restore contract in the header (the contract lives in `pl_handler.c:246-287` only) (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1005-1006` — a future caller that invokes `plpgsql_exec_function` directly without saving and restoring `cur_estate` would silently corrupt re-entrancy. A `/* Caller must save & restore around the call. */` comment in the struct would help. nit.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/spi.md](../../../../../idioms/spi.md)
