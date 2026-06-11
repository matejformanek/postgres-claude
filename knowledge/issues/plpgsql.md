# Issues — `pl/plpgsql` (src/pl/plpgsql/src/)

Per-subsystem issue register for the **PL/pgSQL trusted procedural
language** — the in-process language interpreter that runs as part of
the backend, inherits the function definer's privileges, and is the
single most-used PL in the PostgreSQL ecosystem.

**Parent docs:** `knowledge/files/src/pl/plpgsql/src/*` — one per
source file (`pl_comp.md`, `pl_exec.md`, `pl_funcs.md`, `pl_gram.md`,
`pl_handler.md`, `pl_scanner.md`, `plpgsql.md`,
`pl_reserved_kwlist.h.md`, `pl_unreserved_kwlist.h.md`); the legacy
combined `pl_kwlists.md` is retained as a deep-dive on the x-macro
machinery.

**Source:** 87 entries surfaced 2026-06-04 by the A9 foreground sweep
(4 parallel batches B1-B4); refreshed 2026-06-11 by the A20 sweep
against pin `e18b0cb7344` (cites spot-checked, no drift). Each entry
is mirrored in the per-file doc's `## Potential issues` block.

This sweep covers the **privileged sandbox boundary** — what the
trusted PL relies on, what it does not validate, and where its
"trusted" claim is structurally enforced vs. delegated.

## The headlines

1. **The trusted-PL boundary is enforced exactly twice in pl_handler.c**
   — `CheckFunctionValidatorAccess` (`pl_handler.c:456`, silent no-op
   on denial) and `plpgsql.variable_conflict` being PGC_SUSET
   (`pl_handler.c:164`). Everything else about plpgsql's "trusted PL"
   status is delegated to fmgr / `pg_language` ACL machinery. The
   handler has NO in-handler role checks; SECURITY DEFINER is honored
   purely via the standard fmgr context-switch.

2. **EXECUTE has zero injection defenses for the query body** —
   `exec_stmt_dynexecute` (`pl_exec.c:4541`) and
   `exec_dynquery_with_params` feed the user-computed text directly to
   `SPI_execute_extended`. USING params ARE parameterized; the query
   **body** is never auto-quoted. EXECUTE plans are re-parsed every
   call so no plancache protection either. Combined with the lack of
   any `quote_*`-strongly-typed wrapper in the language, this is the
   canonical PL/pgSQL injection vector and it has no structural guard.

3. **`WHEN OTHERS` swallows everything except `QUERY_CANCELED` and
   `ASSERT_FAILURE`** (`pl_exec.c:1637`) — by design, but creates a
   rich audit-evasion / error-hiding surface. Combined with subxact
   rollback semantics (`pl_exec.c:1918`), an EXCEPTION block can hide
   a failed DDL/DML mid-function while still committing prior SRF
   tuples to the caller's tuplestore (`pl_exec.c:3722`).

4. **COMMIT-inside-procedure breaks "one snapshot per command"** —
   `exec_stmt_commit` (`pl_exec.c:5057`) destroys simple-eval
   infrastructure; the next expression eval acquires a **fresh
   snapshot** via `EnsurePortalSnapshotExists` (`pl_exec.c:6154`),
   making post-COMMIT visibility differ materially from the rest of
   PL/pgSQL. Non-holdable cursors silently die; SECURITY DEFINER
   chains see effects committed by inner CALL boundaries.

5. **Two never-invalidated session caches** — `cast_expr_hash` is
   explicitly never invalidated on `pg_cast` changes
   (`pl_exec.c:138`, file-header comment admits it), and the
   simple-expr fast path's correctness is entirely delegated to
   `plancache.c`'s `CachedPlanIsSimplyValid` (`pl_exec.c:6161`). Any
   missed plancache invalidation (search_path / role / function
   redef) silently runs a stale expression. These are the two trust
   boundaries any "stale-plan" CVE-class issue would land on.

6. **`variable_conflict` policy is locked at first-compile-in-this-backend**
   (`pl_comp.c:250`) — once a function is cached for this session, a
   later `SET plpgsql.variable_conflict = use_column` has no effect on
   it. Default is `PLPGSQL_RESOLVE_ERROR`. Phase D persona gotcha for
   anyone debugging "why did my SET not take effect".

7. **NAME→OID for `%TYPE` / `%ROWTYPE` is baked at compile** —
   `pl_comp.c:1648-1652` literally says "we treat the type as being
   found-by-OID; no attempt to re-look-up the type name will happen
   during invalidations." Combined with `RangeVarGetRelid(... NoLock
   ...)` at `:1630` and `:1739`, schema/search_path changes between
   compile and execute can drift silently. **Joins the corpus-wide
   NAME-vs-OID Phase D pattern (A3 + A6 + A7 + A8 + A9).**

8. **Grammar admits known-fragile parsing heuristics in its own
   comments** — INTO disambiguation (`pl_gram.y:3059-3092`, author
   wrote "will doubtless break this logic again ... beware!"),
   integer-FOR vs query-FOR uses textual `..`-lookahead
   (`pl_gram.y:1467-1505`), and `PERFORM` rewrite assumes
   `strlen("PERFORM") == strlen(" SELECT")` (`pl_gram.y:920-924`).

9. **`PLpgSQL_function` struct is intentionally never freed**
   (`pl_funcs.c:760-768`) because external `fn_extra` pointers may
   still reference it — slow leak vector under high-churn function
   recompilation. Combined with the function-main-context leaks
   acknowledged at `pl_exec.c:108`, plpgsql is structurally
   leak-tolerant by design.

10. **Three load-bearing struct-prefix conventions in `plpgsql.h`
    enforced purely by copy-paste** — `CachedFunction cfunc` first in
    `PLpgSQL_function` (no `StaticAssertDecl`), seven `PLpgSQL_variable`
    fields duplicated across VAR/ROW/REC, seven `PLpgSQL_stmt_forq`
    fields duplicated across fors/forc/dynfors. One wrong reorder =
    silent miscompile.

## Cross-sweep references

- **Phase D NAME-vs-OID cluster:** A3 (pg_dump archive `te->defn`) +
  A6 (pg_upgrade `check_loadable_libraries`, pg_rewind null-bytea) +
  A7 (utils `pg_upgrade_support`) + A8 (subscriber resolves table by
  `nspname.relname`) + **A9 (`%TYPE`/`%ROWTYPE` baked at compile via
  NAME)**. Single corpus-wide idiom doc proposed.
- **Phase D "load arbitrary code from untrusted name" cluster:** A6
  pg_upgrade + A7 utils + A3 pg_dump + A6 pg_rewind + A8 output_plugin
  = 5 primitives. A9 plpgsql does NOT add a 6th — plpgsql itself
  doesn't `dlopen`, it inherits trust from the fmgr/pg_language ACL
  upstream. **A9 instead documents the consumer side of that trust:
  once you call a plpgsql function, the trust boundary is gone.**
- **Phase D session-cache-staleness cluster (new in A9):**
  `cast_expr_hash` + simple-expr plancache trust. Future sweeps of
  `utils/cache/typcache.c` and `executor/spi.c` should cross-link.

---

## Entries

### pl_handler.c (privileged entrypoint, 550 LOC)

- [ISSUE-error-handling: `plpgsql_extra_checks_check_hook` frees
  `elemlist` on `SplitIdentifierString` failure though that path
  leaves it unspecified (nit)] —
  `source/src/pl/plpgsql/src/pl_handler.c:81-87` — relies on the
  implementation always returning `NIL`; harmless today but couples
  to internals.
- [ISSUE-defense-in-depth: `plpgsql.check_asserts` is PGC_USERSET, so
  any caller can disable every `ASSERT` for the session before
  invoking a SECURITY DEFINER function (maybe)] —
  `source/src/pl/plpgsql/src/pl_handler.c:175-181` — by design, but
  documents that ASSERT is not a security guard.
- [ISSUE-defense-in-depth: `plpgsql.variable_conflict` is PGC_SUSET;
  non-superuser DB owners cannot lower the default (maybe)] —
  `source/src/pl/plpgsql/src/pl_handler.c:164` — rationale: changing
  var/column resolution can silently shift query meaning.
- [ISSUE-correctness: `_PG_init` guard relies on per-process
  single-threaded execution; no atomic/barrier (nit)] —
  `source/src/pl/plpgsql/src/pl_handler.c:150-154` — correct under PG
  fork model; flagged for any future threaded port.
- [ISSUE-audit-gap: validator returns silently when
  `CheckFunctionValidatorAccess` denies, with no LOG (maybe)] —
  `source/src/pl/plpgsql/src/pl_handler.c:456-457` — audit logs cannot
  distinguish skipped vs passed validation.
- [ISSUE-error-handling: inline-handler `PG_CATCH` calls
  `plpgsql_free_function_memory(func)` assuming compile completed;
  only safe because use-count++ also lives before the try (nit)] —
  `source/src/pl/plpgsql/src/pl_handler.c:404` — fragile to refactor.
- [ISSUE-documentation: the "procedure_resowner = simple_eval_resowner"
  reuse trick for DO blocks is only documented in code, not in
  `PLpgSQL_execstate` (nit)] —
  `source/src/pl/plpgsql/src/pl_handler.c:357-360`.

### plpgsql.h (landmark header, 1333 LOC)

- [ISSUE-api-shape: `PLpgSQL_function.cfunc` must be the first field
  for `CachedFunction` cast compatibility; no `StaticAssertDecl`
  enforces it (maybe)] — `source/src/pl/plpgsql/src/plpgsql.h:958-960`.
- [ISSUE-api-shape: `PLpgSQL_variable` seven-field substructure is
  copy-pasted into VAR/ROW/REC instead of using a shared macro
  (maybe)] —
  `source/src/pl/plpgsql/src/plpgsql.h:310-319, 332-340, 386-394, 412-420`
  — typo would silently break cross-casting in pl_exec.c.
- [ISSUE-api-shape: same copy-paste invariant for `PLpgSQL_stmt_forq`
  across fors/forc/dynfors (maybe)] —
  `source/src/pl/plpgsql/src/plpgsql.h:712-768`.
- [ISSUE-documentation: `PLPGSQL_XCHECK_SHADOWVAR = (1 << 1)` skips
  bit 0 with no comment (nit)] —
  `source/src/pl/plpgsql/src/plpgsql.h:1194-1198`.
- [ISSUE-defense-in-depth: `PLpgSQL_expr.expr_simple_state`
  LXID-staleness check is the only safety; no magic sentinel — a
  missed gate dereferences garbage (maybe)] —
  `source/src/pl/plpgsql/src/plpgsql.h:282-289`.
- [ISSUE-api-shape: `plpgsql_plugin_ptr` is a global
  `PLpgSQL_plugin **` with no documented thread-safety contract
  (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1214`.
- [ISSUE-security: `PLpgSQL_stmt_dynexecute` and `_dynfors` carry raw
  EXECUTE strings — the in-language SQL-injection surface — with no
  comment pointing readers at
  `quote_ident`/`quote_literal`/`format` (likely)] —
  `source/src/pl/plpgsql/src/plpgsql.h:938, 765` — surface is by
  design; documentation gap is real.
- [ISSUE-documentation: 1333-line landmark header has no top-of-file
  architectural overview block (nit)] —
  `source/src/pl/plpgsql/src/plpgsql.h:1-30`.
- [ISSUE-api-shape: `PLpgSQL_execstate` duplicates
  `fn_rettype`/`retistuple`/`retisset` from `PLpgSQL_function`
  without a comment explaining the duplication (nit)] —
  `source/src/pl/plpgsql/src/plpgsql.h:1019-1025`.
- [ISSUE-correctness: `PLpgSQL_function.cur_estate` save/restore
  contract is documented only in pl_handler.c, not in the header
  (nit)] — `source/src/pl/plpgsql/src/plpgsql.h:1005-1006`.

### pl_comp.c (compiler, 2351 LOC)

- [ISSUE-correctness: `cur_estate` reused across re-plans without
  re-resolving Param types when those types change (likely)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1101-1106` — in-source comment
  explicitly flags it as "really pretty bogus"; same trap repeated in
  `make_datum_param` at `:1257-1258`.
- [ISSUE-audit-gap: variable-conflict policy locked at
  first-compile-in-this-backend, GUC change later has no effect on
  cached function (maybe)] —
  `source/src/pl/plpgsql/src/pl_comp.c:250` —
  `function->resolve_option = plpgsql_variable_conflict` baked at
  compile time; surprises users who SET the GUC after first call.
- [ISSUE-correctness: `nspname.relname` for `%TYPE`/`%ROWTYPE`
  resolved to OID at compile time and trusted forever; search-path
  drift not re-detected (likely)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1648-1652` — comment is
  explicit; combined with NoLock at `:1630`/`:1739` the relation
  isn't even locked. **NAME-vs-OID Phase D pattern.**
- [ISSUE-defense-in-depth: `RangeVarGetRelid(... NoLock ...)` lets
  schema-mutating racer slip between compile and execute (nit)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1630` and `:1739` — justified
  by privilege concern but no compile-time lock guarantee carried to
  execute.
- [ISSUE-concurrency: globals `plpgsql_Datums` / `plpgsql_nDatums` /
  `plpgsql_curr_compile` make compile non-reentrant; any future
  nested-plpgsql-during-compile would corrupt state (confirmed)] —
  `source/src/pl/plpgsql/src/pl_comp.c:42-50,163-164` — documented
  constraint; no defensive Assert.
- [ISSUE-memory: `proc_source` pfree'd only after successful parse;
  ereport-from-yyparse leaks it conceptually (nit)] —
  `source/src/pl/plpgsql/src/pl_comp.c:687` — reclaimed in practice
  via func_cxt teardown since cxt is still child of caller at that
  point.
- [ISSUE-documentation: `cur_estate` re-use comment at `:1101` should
  cross-reference `:1249` (make_datum_param) which reads the same
  estate to compute paramtype (nit)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1257-1258` — two sites, same
  trap, one comment.
- [ISSUE-api-shape: `add_parameter_name` duplicate-detection produces
  error message naming the user alias rather than the positional
  `$n` for OUT-param naming collisions (nit)] —
  `source/src/pl/plpgsql/src/pl_comp.c:366-371,918-938` — correct
  rejection, suboptimal message.

### pl_scanner.c (lexer wrapper, 657 LOC)

- [ISSUE-correctness: `AT_STMT_START` hardcoded to 5 token kinds; new
  statement-introducing tokens added to the grammar without updating
  the macro silently break the "prefer unreserved keyword at
  statement start" rule (maybe)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:82-87` — comment
  acknowledges hard-coding; no compile-time guard.
- [ISSUE-defense-in-depth: MAX_PUSHBACKS=4; a sixth lookahead layer
  in pl_gram.y would only fail at runtime (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:98,387-392` — fail-fast
  elog(ERROR) is correct, but no compile-time sizing guard.
- [ISSUE-concurrency: module-global `plpgsql_IdentifierLookup`
  couples concurrent scanner instances; harmless today because
  compile is single-threaded but invisible to anyone trying to allow
  nested compiles (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:26` — should be per-
  `yyextra` if scanner ever goes reentrant.
- [ISSUE-correctness: `plpgsql_yyerror` mutates scanbuf in place by
  writing NUL (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:548-554` — comment
  acknowledges; safe only because we're about to ereport ERROR.
- [ISSUE-error-handling: `plpgsql_scanner_errposition` walks the full
  prefix with pg_mbstrlen_with_len on every error (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:512` — O(n) per error;
  rare enough not to matter.
- [ISSUE-audit-gap: dollar-quoting, very-long identifier, and UTF-8
  attack surface is 100% delegated to core_yylex; reviewer auditing
  PL/pgSQL lexer must read src/backend/parser/scan.l (documentation)]
  — `source/src/pl/plpgsql/src/pl_scanner.c:352` — pointer-to-real-
  code observation.

### pl_reserved_kwlist.h / pl_unreserved_kwlist.h

- [ISSUE-audit-gap: no automated check that
  `pl_unreserved_kwlist.h` matches `pl_gram.y`'s
  `unreserved_keyword` production (maybe)] —
  `source/src/pl/plpgsql/src/pl_unreserved_kwlist.h:24` — header
  comment is only enforcement; drift caught only by regression tests.
- [ISSUE-documentation: "deliberately no #ifndef" comment doesn't
  explain the multi-include-with-different-PG_KEYWORD pattern (nit)]
  — `source/src/pl/plpgsql/src/pl_reserved_kwlist.h:18` — could point
  to `pl_scanner.c:64-74` as the example use site.
- [ISSUE-correctness: ASCII-order requirement is comment-only;
  out-of-order entries break the perfect hash in
  `gen_keywordlist.pl`'s output (maybe)] —
  `source/src/pl/plpgsql/src/pl_reserved_kwlist.h:25` — presumably
  enforced by Perl script, but not visible from the header.
- [ISSUE-undocumented-invariant: unreserved keywords are shadowable by
  user-declared variables (e.g. `assert`, `commit`, `merge`) because
  the namespace lookup runs before the unreserved-keyword scan; not
  called out in `plpgsql.sgml` (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:247-253` consumes
  `source/src/pl/plpgsql/src/pl_unreserved_kwlist.h` — surprises
  users who write a local `commit` variable.
- [ISSUE-documentation: `elseif`/`elsif` synonym pair lacks an
  in-comment cross-reference (nit)] —
  `source/src/pl/plpgsql/src/pl_unreserved_kwlist.h:56-57` — both
  map to `K_ELSIF`; only documented in `plpgsql.sgml`.

### pl_exec.c (executor, 9218 LOC — the giant)

- [ISSUE-security: EXECUTE query string is whatever the user computed;
  pl_exec only parameterizes USING args, never the query body
  (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:4541` —
  `exec_stmt_dynexecute` feeds the user-computed text directly to
  `SPI_execute_extended`; no `quote_*` defense. **Textbook PL/pgSQL
  SQL-injection vector.**
- [ISSUE-defense-in-depth: EXECUTE one-shot plan is re-parsed every
  call, so search_path takeover during the dynamic build affects
  every invocation (maybe)] —
  `source/src/pl/plpgsql/src/pl_exec.c:4581`.
- [ISSUE-correctness: SELINTO inside EXECUTE rejected only at
  runtime, not parse-time (nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:4606`.
- [ISSUE-security: RAISE format string can be user-controlled; param
  substitution is unchecked at runtime, though
  `errmsg_internal("%s",...)` is the structural backstop (maybe)] —
  `source/src/pl/plpgsql/src/pl_exec.c:3808`.
- [ISSUE-error-handling: condname fallback to err_message uses
  condname text raw — user-supplied custom condition names become
  user-visible messages (nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:3929`.
- [ISSUE-audit-gap: WHEN OTHERS swallows everything except
  QUERY_CANCELED and ASSERT_FAILURE — widely-documented pitfall,
  structurally enforced (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:1637`.
- [ISSUE-correctness: PG_CATCH must null eval_tuptable because SPI
  threw it away on subxact abort — implicit contract, future reads
  without NULL check crash (nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:1918`.
- [ISSUE-correctness: SRF tuples accumulated in tuple_store survive
  subxact abort because tuple_store_owner is the caller's resowner —
  surprises users (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:3722`.
- [ISSUE-security: GET STACKED DIAGNOSTICS exposes ErrorData
  CONTEXT/DETAIL/HINT/TABLE/SCHEMA verbatim; information-flow
  surface in security-definer chains (maybe)] —
  `source/src/pl/plpgsql/src/pl_exec.c:2461`.
- [ISSUE-correctness: post-COMMIT in a procedure, the next
  simple-expr eval runs against a freshly-acquired snapshot that may
  see new data the outer transaction wouldn't (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:5057`.
- [ISSUE-defense-in-depth: non-holdable cursors silently invalidated
  by COMMIT; subsequent FETCH errors "cursor does not exist"
  (likely)] — `source/src/pl/plpgsql/src/pl_exec.c:5060`.
- [ISSUE-correctness: OPEN/CLOSE asymmetry — a procedure that OPENs
  and never CLOSEs leaks the portal until xact end (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:5013`.
- [ISSUE-correctness: FORC and OPEN-with-args use non-STRICT
  SELECT-INTO for argument processing — "XXX historically this has
  not been STRICT" (maybe)] —
  `source/src/pl/plpgsql/src/pl_exec.c:2958` and `:4863`.
- [ISSUE-security: TG_TABLE_NAME / TG_TABLE_SCHEMA are catalog-
  derived and safe in themselves, but `EXECUTE 'INSERT INTO ' ||
  TG_TABLE_NAME` is NOT safe without quote_ident (nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:1490`.
- [ISSUE-correctness: BEFORE-trigger STORED-generated columns are
  forced NULL only on UPDATE, not INSERT (from-comment)] —
  `source/src/pl/plpgsql/src/pl_exec.c:1013`.
- [ISSUE-correctness: cast_expr_hash never invalidated on pg_cast
  changes; session-wide stale entries possible (from-comment,
  likely)] — `source/src/pl/plpgsql/src/pl_exec.c:138`.
- [ISSUE-correctness: simple-expr cached-plan validity is entirely
  delegated to plancache.c — any missed invalidation (search_path /
  role / function redef) silently runs the wrong expression
  (verified-by-code)] —
  `source/src/pl/plpgsql/src/pl_exec.c:6161`.
- [ISSUE-correctness: replanning silently degrades to non-simple if
  plan no longer qualifies; no user-visible signal (nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:6213`.
- [ISSUE-defense-in-depth: simple-expr fast path skips fresh-snapshot
  push when `expr_simple_mutable` is false; mis-labeled IMMUTABLE
  functions see stale data (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:6297`.
- [ISSUE-memory: function-main-context leaks acknowledged as
  tolerated — long-running functions accumulate (from-comment, nit)]
  — `source/src/pl/plpgsql/src/pl_exec.c:108`.
- [ISSUE-memory: CASE statement rebuilds t_var->datatype on each
  type drift, leaking the old type into fn_cxt (from-comment, nit)]
  — `source/src/pl/plpgsql/src/pl_exec.c:2605`.
- [ISSUE-memory: a transaction abort inside do_cast_value leaves
  cast_entry->cast_in_use=true until next xact reset
  (verified-by-code)] —
  `source/src/pl/plpgsql/src/pl_exec.c:8209`.
- [ISSUE-correctness: non-atomic detoasting in assign_simple_var is
  the only barrier against post-COMMIT stale-TOAST-pointer bugs; any
  varlena-assign path bypassing it is a latent bug (verified-by-code,
  likely)] — `source/src/pl/plpgsql/src/pl_exec.c:8896`.
- [ISSUE-correctness: exec_for_query skips prefetch in non-atomic to
  avoid post-COMMIT dangling TOAST refs (from-comment)] —
  `source/src/pl/plpgsql/src/pl_exec.c:5959`.
- [ISSUE-correctness: composite RECORDOID return passes back as-is —
  no structural consistency enforcement (from-comment, nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:732`.
- [ISSUE-correctness: coerce_function_result_tuple duplicates
  datumCopy() guts for expanded records with wrong type ID
  (from-comment, nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:866`.
- [ISSUE-correctness: PLpgSQL_var returning as composite errors only
  when non-NULL — NULL slips through (from-comment, nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:3275`.
- [ISSUE-correctness: SELECT INTO single-target simple-fast-path
  skips cardinality check entirely and unconditionally sets
  FOUND=true (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:4300`.
- [ISSUE-correctness: too_many_rows_level is a configurable GUC
  (plpgsql.extra_errors/warnings); default silent (verified-by-code)]
  — `source/src/pl/plpgsql/src/pl_exec.c:4250`.
- [ISSUE-correctness: EnsurePortalSnapshotExists takes a fresh
  snapshot after COMMIT under the current effective user — visibility
  surprise in SD chains (verified-by-code)] —
  `source/src/pl/plpgsql/src/pl_exec.c:6154`.
- [ISSUE-correctness: need_snapshot decision rides on
  contain_mutable_functions; trust boundary (likely)] —
  `source/src/pl/plpgsql/src/pl_exec.c:6297`.
- [ISSUE-api-shape: plpgsql_destroy_econtext asserts top-of-stack
  match — a misbehaving plugin crashes the backend (verified-by-code,
  nit)] — `source/src/pl/plpgsql/src/pl_exec.c:8793`.
- [ISSUE-documentation: copy_plpgsql_datums has manual "must agree
  with plpgsql_finish_datums" cross-file coupling (from-comment, nit)]
  — `source/src/pl/plpgsql/src/pl_exec.c:1370`.
- [ISSUE-correctness: instantiate_empty_record_variable rejects
  RECORDOID with "not assigned yet" — surfaces on field access of a
  NULL `record`-declared variable (verified-by-code)] —
  `source/src/pl/plpgsql/src/pl_exec.c:7916`.
- [ISSUE-correctness: plugin pointers dereferenced everywhere
  assuming plpgsql_plugin_ptr itself is non-NULL — invariant set in
  pl_handler (verified-by-code)] —
  `source/src/pl/plpgsql/src/pl_exec.c:629`.
- [ISSUE-correctness: format_expr_params / format_preparedparamsdata
  expose parameter values in errdetail when print_strict_params is
  on — PII surface in logs (maybe)] —
  `source/src/pl/plpgsql/src/pl_exec.c:9121` and `:9178`.
- [ISSUE-correctness: paramFetch's dummy-param branch trusts
  expr->paramnos correctness; out-of-date paramnos vs. plan could
  lead the planner to see wrong types (from-comment, nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:6422`.
- [ISSUE-api-shape: exec_prepare_plan can throw after saving the plan
  in expr->plan; comment warns extra steps after the prepare are
  unsafe because re-execution skips them (from-comment, nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:4188`.
- [ISSUE-correctness: FORI overflow detection silently exits the loop
  rather than wrapping or erroring (verified-by-code, nit)] —
  `source/src/pl/plpgsql/src/pl_exec.c:2836`.

### pl_gram.y (grammar, 4255 LOC)

- [ISSUE-correctness: INTO disambiguation heuristic is explicitly
  known-fragile, breaks on any new SQL construct using INTO
  (confirmed)] —
  `source/src/pl/plpgsql/src/pl_gram.y:3059-3092,3141-3156` — author
  comment: "Any future additional uses of INTO in the main grammar
  will doubtless break this logic again ... beware!" Currently
  special-cases only INSERT, MERGE, IMPORT.
- [ISSUE-correctness: integer-FOR vs query-FOR disambiguation uses
  textual `..` lookahead (likely)] —
  `source/src/pl/plpgsql/src/pl_gram.y:1467-1505` — author comment:
  "We use the ugly hack of looking for two periods after the first
  token."
- [ISSUE-correctness: PERFORM in-place buffer rewrite silently
  depends on strlen("PERFORM") == strlen(" SELECT") (likely)] —
  `source/src/pl/plpgsql/src/pl_gram.y:920-924` — `memcpy(... 7)`
  invariant unstated.
- [ISSUE-error-handling: `read_into_scalar_list` hard-caps INTO
  targets at 1024 via on-stack arrays (likely)] —
  `source/src/pl/plpgsql/src/pl_gram.y:3662-3679` — no GUC override;
  raises ERRCODE_PROGRAM_LIMIT_EXCEEDED before any overflow, so safe
  but a sharp edge for code-generated plpgsql.
- [ISSUE-correctness: `make_case` rewrites WHEN clauses textually as
  `"VAR" IN (orig)`, allowing comma-list weirdness (maybe)] —
  `source/src/pl/plpgsql/src/pl_gram.y:4202-4250` — author comment
  admits "klugy"; a WHEN expression containing top-level commas
  becomes a row-IN test.
- [ISSUE-security: condition-name lookup is case-insensitive but
  cannot be user-shadowed (negative result, nit)] —
  `source/src/pl/plpgsql/src/pl_gram.y:2402-2436` and
  `pl_comp.c:2176` — names are matched against a hard-coded table;
  users CANNOT shadow builtins. Recorded so the next auditor doesn't
  re-investigate.
- [ISSUE-defense-in-depth: `read_raise_options` accepts unlimited
  USING-option entries (nit)] —
  `source/src/pl/plpgsql/src/pl_gram.y:4082-4139` — bounded only by
  function source size, not exploitable but unbounded loop.
- [ISSUE-api-shape: file-scope static `plpgsql_curr_compile` makes
  recursive compile risky without explicit save/restore (maybe)] —
  `source/src/pl/plpgsql/src/pl_gram.y:392,400,404,408,433,etc.` —
  handled by `pl_comp.c` but the assumption is not documented in this
  file.
- [ISSUE-documentation: `make_execsql_stmt`'s INTO-redaction
  space-padding trick is undocumented in plpgsql.h (nit)] —
  `source/src/pl/plpgsql/src/pl_gram.y:3161-3171` — the contents of
  `PLpgSQL_stmt_execsql->sqlstmt->query` (INTO span replaced by
  spaces) is non-obvious to consumers.

### pl_funcs.c (utilities + dump/free, 1694 LOC)

- [ISSUE-memory: `PLpgSQL_function` struct intentionally leaks after
  `plpgsql_free_function_memory` (documentation, maybe)] —
  `source/src/pl/plpgsql/src/pl_funcs.c:760-768` — by-design per the
  comment; slow leak vector under heavy function churn.
- [ISSUE-audit-gap: `plpgsql_dumptree` writes to raw stdout/printf
  rather than the elog stream (nit)] —
  `source/src/pl/plpgsql/src/pl_funcs.c:1606,1689,1693` — bypasses
  client RAISE LEVEL, translation, and structured-error fields. Only
  triggered by dev-only `#option dump`.
- [ISSUE-documentation: `plpgsql_stmt_typename` mixes translated and
  untranslated arms inconsistently (nit)] —
  `source/src/pl/plpgsql/src/pl_funcs.c:231-294` — pattern is markers-
  bare vs phrases-translatable but undocumented.
- [ISSUE-defense-in-depth: `#option dump` written into a SECURITY
  DEFINER function body leaks the AST to server log on every call
  (maybe)] — `source/src/pl/plpgsql/src/pl_funcs.c:1600-1694` —
  requires CREATE FUNCTION privilege so not externally exploitable,
  but a SECDEF function author can leak more than intended.
- [ISSUE-documentation: brief incorrectly placed `plpgsql_subxact_cb`
  in pl_funcs.c; it is actually in pl_exec.c:8853 (nit)] — recorded
  inline in the per-file doc so it doesn't keep being re-investigated.
