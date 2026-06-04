# pl_comp.c

**Source pin:** `4b0bf0788b0`. Lines read: 1–2351 (complete).

## One-line summary

Compiler that turns a function's `pg_proc.prosrc` text into a long-lived
`PLpgSQL_function` AST: drives the bison parser, builds the namespace
stack and `Datums[]` table, registers parser callbacks (`p_pre_columnref_hook` /
`p_post_columnref_hook` / `p_paramref_hook`) for the embedded SQL queries,
and arranges per-function memory contexts for caching.

## Public API

Externally callable (declared in `plpgsql.h`); cites are `source/src/pl/plpgsql/src/pl_comp.c:<line>`:

- `plpgsql_compile(FunctionCallInfo, bool forValidator)` — entry from the call
  handler. Thin wrapper around `cached_function_compile()` with
  `plpgsql_compile_callback` as the slow-path producer. Lines 105–136.
  [verified-by-code]
- `plpgsql_compile_inline(char *proc_source)` — the DO-statement compiler;
  builds a one-shot `PLpgSQL_function` that is **not** added to any cache
  (`function = palloc0_object(PLpgSQL_function)` at line 775). Lines 742–880.
  [verified-by-code]
- `plpgsql_parser_setup(ParseState *, PLpgSQL_expr *)` — wires the four parse
  hooks (`p_pre_columnref_hook`, `p_post_columnref_hook`, `p_paramref_hook`,
  `p_ref_hook_state`) used by the core parser when (re-)planning the embedded
  SQL expressions inside the function body. Lines 988–996. [verified-by-code]
- `plpgsql_parse_word(char *word1, const char *yytxt, bool lookup, PLwdatum *, PLword *)`
  — namespace lookup of a single identifier, called from the scanner. Lines
  1302–1349. [verified-by-code]
- `plpgsql_parse_dblword(char *, char *, PLwdatum *, PLcword *)` — `A.B` lookup
  (block-qualified scalar, record-field, or block-qualified record). Lines
  1357–1430. [verified-by-code]
- `plpgsql_parse_tripword(...)` — `A.B.C` lookup (must be a record reference,
  optionally sub-field). Lines 1438–1512. [verified-by-code]
- `plpgsql_parse_wordtype(char *ident)` — resolves `word%TYPE`. Lines
  1522–1552. [verified-by-code]
- `plpgsql_parse_cwordtype(List *idents)` — resolves `composite.word%TYPE`,
  including the table-column fallback case. Lines 1563–1668. [verified-by-code]
- `plpgsql_parse_wordrowtype(char *ident)` — resolves `word%ROWTYPE`. Lines
  1675–1713. [verified-by-code]
- `plpgsql_parse_cwordrowtype(List *idents)` — resolves
  `schema.tab%ROWTYPE`. Lines 1720–1755. [verified-by-code]
- `plpgsql_build_variable(refname, lineno, dtype, add2namespace)` — generic
  factory dispatching on `dtype->ttype` to either a `PLpgSQL_var` (scalar) or
  `PLpgSQL_rec` (composite). Lines 1766–1824. [verified-by-code]
- `plpgsql_build_record(refname, lineno, dtype, rectypeid, add2namespace)` —
  scalar-RECORD constructor. Lines 1829–1850. [verified-by-code]
- `plpgsql_build_recfield(PLpgSQL_rec *, fldname)` — idempotent factory
  for a `PLpgSQL_recfield` datum; reuses an existing one for the same
  field, linked through `rec->firstfield`. Lines 1925–1958. [verified-by-code]
- `plpgsql_build_datatype(typeOid, typmod, collation, origtypname)` — public
  entry into `build_datatype()`; does the syscache lookup. Lines 1974–1990.
  [verified-by-code]
- `plpgsql_build_datatype_arrayof(PLpgSQL_type *)` — `dtype[]` constructor;
  inherits typmod and collation from element type. Lines 2108–2130.
  [verified-by-code]
- `plpgsql_recognize_err_condition(condname, allow_sqlstate)` — name → SQLSTATE
  lookup for EXCEPTION conditions; also parses the 5-char "01000"-style
  SQLSTATE literal. Lines 2139–2166. [verified-by-code]
- `plpgsql_parse_err_condition(condname)` — builds a `PLpgSQL_condition` list
  (possibly multi-entry — some condition names map to multiple SQLSTATEs).
  Lines 2175–2216. [verified-by-code]
- `plpgsql_adddatum(PLpgSQL_datum *)` — append to growing global
  `plpgsql_Datums[]` table, assign `dno`. Lines 2239–2250. [verified-by-code]
- `plpgsql_add_initdatums(int **varnos)` — return varnos of datums created
  since last call (used to compute per-block init list). Lines 2300–2351.
  [verified-by-code]

Module-level globals (declared in `plpgsql.h`):

- `int plpgsql_nDatums` and `PLpgSQL_datum **plpgsql_Datums` — the live datum
  array under construction during a single `plpgsql_compile_callback()`
  invocation. Lines 42–43. NOT re-entrant. [verified-by-code]
- `char *plpgsql_error_funcname` — used by error-callback. Line 46.
- `bool plpgsql_DumpExecTree` — debugging knob, set to false on every compile.
  Lines 47, 276, 809. [verified-by-code]
- `bool plpgsql_check_syntax` — set true only during `forValidator` compiles
  (or when `check_function_bodies` is on for DO blocks). Line 48, 224, 772.
  [verified-by-code]
- `PLpgSQL_function *plpgsql_curr_compile` — the function currently being
  compiled. Read by various callbacks. Lines 50, 225, 777. [verified-by-code]
- `MemoryContext plpgsql_compile_tmp_cxt` — short-lived scratch context used
  for syscache results, polymorphic-type resolution, etc. The
  CurrentMemoryContext on entry into the slow path; reset to the caller's
  context after compile. Lines 53, 242, 728–729. [verified-by-code]

## Key invariants

- **Non-reentrant.** The compile callback explicitly asserts that "nothing we
  do here could result in the invocation of another plpgsql function"
  (line 163–164 comment). The mutable globals
  (`plpgsql_Datums`, `plpgsql_nDatums`, `datums_alloc`, `datums_last`,
  `plpgsql_curr_compile`) make this a hard requirement, not just a
  performance hint. [from-comment]
- **`CurrentMemoryContext` during compile == `func_cxt`.** Every `palloc()`
  inside the slow path goes into the per-function context (line 152–155
  comment). Temporary allocations must explicitly switch to
  `plpgsql_compile_tmp_cxt` or pfree. [from-comment]
- **Func cxt reparented late.** The function's `func_cxt` is first created as
  a child of the (assumed short-lived) caller context, then
  `MemoryContextSetParent(func_cxt, CacheMemoryContext)` runs only at line 718
  if compile succeeds. This makes a faulty `ereport(ERROR)` mid-compile
  automatically free everything via the caller's context teardown — no
  per-error cleanup needed. Lines 232–242, 715–718. [verified-by-code]
- **`Datums[]` is sequentially numbered.** `plpgsql_adddatum` assigns
  `newdatum->dno = plpgsql_nDatums++` (line 2248); never reused, never
  resorted. `PLpgSQL_recfield` lookup uses a linked list rooted at
  `rec->firstfield` to avoid duplicates per `(rec, fieldname)` (lines
  1932–1942). [verified-by-code]
- **Namespace stack is push/lookup, not a flat scope.** Every block opens a
  new namespace entry via `plpgsql_ns_push()` (line 275, 808). Lookup walks
  outward via `plpgsql_ns_lookup()` (lives in `pl_funcs.c`). The outermost
  scope holds function parameters, trigger pseudo-vars, and the magic `FOUND`.
- **Trigger functions use `PLpgSQL_var.dtype == PLPGSQL_DTYPE_PROMISE`** for
  `TG_NAME`/`TG_OP`/`NEW`/etc., evaluated lazily at first reference (lines
  502–620). The variable is a `PLpgSQL_var` but its `promise` enum tells the
  executor to materialize the value at use, not at block entry. [verified-by-code]
- **No locks on relations during compile.** `RangeVarGetRelid(..., NoLock, false)`
  is used for `cwordtype`/`cwordrowtype` because the user might not yet have
  privileges (lines 1629–1630, 1737–1739 comments). The schema can therefore
  drift between compile and execute. [from-comment]
- **Compile is post-cached by funccache.c.** `plpgsql_compile()` is structured
  to "fall through quickly if the function has already been compiled"
  (line 102 comment) — every call by the call handler hits the cache fast
  path; the slow path runs only on first call per backend or after invalidation.

## Notable internals

### Three-callback parser-setup pattern

`plpgsql_parser_setup()` (line 988) installs the hooks that turn a plain
`raw_parser()` invocation into a plpgsql-aware one. The hooks fire when the
**embedded SQL** inside the function body is parsed/planned (which is **at
execution time**, not at function-compile time):

- `plpgsql_pre_column_ref` — if `resolve_option == PLPGSQL_RESOLVE_VARIABLE`,
  always try plpgsql vars first.
- `plpgsql_post_column_ref` — if `resolve_option == PLPGSQL_RESOLVE_COLUMN`,
  defer to table column; if `PLPGSQL_RESOLVE_ERROR` (default), look up
  plpgsql var; if both match, throw `ERRCODE_AMBIGUOUS_COLUMN` with helpful
  detail.
- `plpgsql_param_ref` — resolves `$n` to a plpgsql Datum via namespace lookup
  on `"$n"` (line 1066).
- `p_ref_hook_state` carries the `PLpgSQL_expr *` so the hooks know the
  function and its namespace.

The state pointer is `PLpgSQL_expr *`, and the hooks reach
`expr->func->cur_estate` for parameter type info — see "Issues spotted".

### Default `variable_conflict` policy

`plpgsql.variable_conflict` GUC is enum {`error`, `use_variable`, `use_column`},
default `error` (`pl_handler.c:47`: `PLPGSQL_RESOLVE_ERROR`). Per-function
override is recorded at compile time
(`function->resolve_option = plpgsql_variable_conflict`, line 250 and 793) —
**not at execute time**. This means a `SET plpgsql.variable_conflict = use_column`
issued **after** a function has been compiled in this backend has no effect
on that already-cached function. Functions also accept an in-source
`#variable_conflict use_column` directive (handled by `pl_gram.y`) that wins.

### Namespace stack and parameter aliasing

For non-trigger functions, every parameter is added to the namespace twice
(line 366 + 370): once under `$1`, `$2`, … and once under the declared
parameter name if any. The duplicate-name check in `add_parameter_name()`
(lines 918–938) is needed precisely because plpgsql, unlike pg_proc, treats
IN and OUT parameter names as inhabiting the same namespace.

### Type resolution: OID vs Name

`plpgsql_build_datatype` and `build_datatype` (lines 1974, 1996) record only
the type OID plus, for **named composite** types, a TypeCache pointer +
`tupdesc_id` so the executor can detect tupdesc invalidation
(lines 2075–2094). The comment on line 1651–1652 is explicit: for `%TYPE`,
"we treat the type as being found-by-OID; no attempt to re-look-up the type
name will happen during invalidations." So `nspname.colname%TYPE` is
resolved **at compile time** to an OID and that OID is then trusted forever.
A subsequent `DROP TYPE … CASCADE` plus recreation under a different OID
will invalidate via the plancache machinery, but renaming a column to a
different type without dropping it will be caught only because the function's
plan cache is invalidated by relcache invalidation.

For composite types, the `tcache` + `tupdesc_id` pair (line 2092–2093) is
the post-compile drift detector — set once at compile, compared per use in
the executor.

### Memory-context discipline

- `func_cxt` (line 239): the long-lived per-function cache entry. Reparented
  to `CacheMemoryContext` on success (line 718). On failure, the caller's
  context teardown wipes everything.
- `plpgsql_compile_tmp_cxt` (line 242): the **previous** CurrentMemoryContext,
  i.e. the caller's. Used for everything that should NOT survive the compile.
  `MemoryContextSwitchTo(plpgsql_compile_tmp_cxt)` at line 728 restores the
  caller's context before returning.
- Within the compile, `cwordtype`/`cwordrowtype` explicitly switch back to
  the tmp cxt before doing syscache lookups (e.g. lines 1577–1578, 1684) to
  avoid leaking sysCache-side allocations into the long-lived func_cxt.

### Datum table growth

`plpgsql_start_datums` initial-allocs 128 slots in `plpgsql_compile_tmp_cxt`
(line 2225–2229) — so the array itself is short-lived; only the
`plpgsql_Datums[i]` pointers' targets live in func_cxt. `plpgsql_finish_datums`
(line 2256) memcpys them into `function->datums[]` (which DOES live in
func_cxt) and computes `copiable_size` — the running total of MAXALIGN'd
sizes for the per-call datum copy at execute time.

### Error-callback wiring

A per-compile `compile_error_callback_arg` (line 138) holds the source text
(only for validator mode — `cbarg.proc_source = forValidator ? proc_source : NULL`,
line 212) plus the yyscanner. The callback (line 888) calls
`function_parse_error_transpose()` to remap inner-SQL parse errors back to
the right offset in the CREATE FUNCTION text, then falls back to "near line N".
Note: in non-validator mode (normal first-time-compile-on-call),
`cbarg.proc_source = NULL`, so syntax errors can only be reported as
"near line N" without the offending fragment — by design, to avoid leaking
function source to non-owners through error context.

## Cross-references

Siblings (same dir):

- `pl_handler.c` — `plpgsql_call_handler`, GUC definitions (incl.
  `plpgsql.variable_conflict`), `_PG_init`.
- `pl_gram.y` — the bison grammar; calls back into `plpgsql_parse_word` etc.
- `pl_exec.c` — the tree walker that consumes `PLpgSQL_function->action`.
- `pl_funcs.c` — namespace stack (`plpgsql_ns_push`, `plpgsql_ns_lookup`,
  `plpgsql_ns_additem`).
- `plpgsql.h` — `PLpgSQL_function`, `PLpgSQL_datum`, `PLpgSQL_var`,
  `PLpgSQL_rec`, `PLpgSQL_expr`, `PLpgSQL_type`, all enums.
- `plerrcodes.h` — generated from `errcodes.txt`; included at line 66 to
  build `exception_label_map[]`.

Backend touch-points:

- `parser/parser.c`, `parser/parse_node.h` — `ParseState` and the
  `p_pre_columnref_hook` / `p_post_columnref_hook` / `p_paramref_hook` /
  `p_ref_hook_state` slots that `plpgsql_parser_setup` writes.
- `parser/parse_param.c` — the param-ref-hook convention.
- `utils/cache/funccache.c` (new in PG 18) — `cached_function_compile`
  hash-keys functions and arranges invalidation; called from
  `plpgsql_compile`.
- `utils/cache/typcache.c` — `lookup_type_cache` for composite-type tupdesc
  tracking.
- `catalog/namespace.c` — `RangeVarGetRelid` (used without lock).
- `utils/syscache.c` — `SearchSysCache1(TYPEOID,…)`, `SearchSysCacheAttName`.
- `nodes/makefuncs.c` — `makeRangeVar`, `makeTypeName`.

## Issues spotted

- [ISSUE-correctness: `cur_estate` is reused across re-plans without
  re-resolving Param types if those types change (likely)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1101-1106` —
  Comment is explicit: "We use the function's current estate to resolve
  parameter data types. This is really pretty bogus because there is no
  provision for updating plans when those types change ..." If a plpgsql
  variable's declared type happens to change (e.g. via `ALTER DOMAIN` on a
  scalar domain, or recompilation due to type alteration), the cached
  Param.paramtype may diverge from estate->datums[dno] type. The
  in-source acknowledgement is a long-standing wart.

- [ISSUE-audit-gap: variable-conflict policy is locked at first-compile-in-this-backend
  (maybe)] — `source/src/pl/plpgsql/src/pl_comp.c:250` —
  `function->resolve_option = plpgsql_variable_conflict` records the **current
  GUC value at compile time**. A later `SET plpgsql.variable_conflict = ...`
  in the same backend will not re-shape an already-cached function's
  behavior, even though users may reasonably expect it to. Not a bug per
  spec, but a sharp edge that has surprised users; worth surfacing for the
  audit layer.

- [ISSUE-correctness: `nspname.relname` for `%TYPE`/`%ROWTYPE` is resolved to
  OID at compile time and trusted forever (likely)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1648-1652` —
  Comment: "we treat the type as being found-by-OID; no attempt to re-look-up
  the type name will happen during invalidations." If the user re-creates the
  named table under a different schema with the same name (e.g. via
  `search_path` manipulation), the compiled function will still resolve to
  the original OID. This is the Phase D "NAME-vs-OID" pattern: the source
  text says one thing, the cached AST resolves it to an OID, search-path
  changes don't re-trigger resolution. Combined with `NoLock` on
  `RangeVarGetRelid` (line 1630, 1739), there is no relation-existence proof
  carried forward to execute time either.

- [ISSUE-defense-in-depth: `RangeVarGetRelid(... NoLock ...)` lets a
  schema-mutating racer slip in between compile and execute (nit)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1630` and `:1739` —
  The justification ("we might not have privileges") is correct for
  permissions, but means there is no compile-time lock guarantee that the
  relation observed is the one ultimately bound. Subsequent invalidation
  rescues this in practice, but only because the plancache below detects
  the change.

- [ISSUE-concurrency: globals `plpgsql_Datums` / `plpgsql_nDatums` /
  `plpgsql_curr_compile` make compile non-reentrant; nested-plpgsql-during-compile
  would corrupt state (confirmed)] —
  `source/src/pl/plpgsql/src/pl_comp.c:42-50,163-164` —
  Documented in-source as a known constraint ("NB: this code is not
  re-entrant. We assume that nothing we do here could result in the
  invocation of another plpgsql function."). Any future change that lets
  compile-time code invoke user-defined plpgsql (e.g. an INSTEAD OF rewrite,
  a custom operator class with a plpgsql support function, an event-trigger
  side effect) would silently corrupt the datum table. Worth a defensive
  Assert.

- [ISSUE-memory: `proc_source` is `pfree()`d at line 687 only after
  successful parse; if `plpgsql_yyparse` ereports out, the string is leaked
  in func_cxt (nit)] — `source/src/pl/plpgsql/src/pl_comp.c:687` — In practice
  the whole func_cxt is freed by the error-time cleanup (it is still
  parented to CurrentMemoryContext at that point — see lines 239 vs 718), so
  it is reclaimed. The "leak" is conceptual, not real.

- [ISSUE-documentation: the `cur_estate` re-use comment (line 1101) needs
  cross-reference to `make_datum_param` (line 1249), which reads the SAME
  estate to compute paramtype. Two sites, same trap. (nit)] —
  `source/src/pl/plpgsql/src/pl_comp.c:1257-1258` — A reader doing a
  type-tracking audit will miss the second site if they only see the first
  comment.

- [ISSUE-api-shape: `add_parameter_name` checks duplicates against
  `plpgsql_ns_top()`, NOT against the alias `$n` slot just added two lines
  above (maybe)] — `source/src/pl/plpgsql/src/pl_comp.c:366-371` — Both
  `$1` and the user's name `foo` go into the SAME namespace level, but the
  check at line 928 only fires for a duplicate-with-existing. Two parameters
  both named `foo` are correctly caught; one parameter aliased as `foo` with
  a second positional parameter also aliased `foo` is correctly caught. Fine
  in practice, but the second `add_parameter_name` will trip the check on
  the FIRST parameter's name slot, not the `$n` slot, so the resulting error
  message says "parameter name 'foo' used more than once" rather than the
  per-position number — which can be surprising for OUT-param naming
  collisions. Documentation-level nit.
