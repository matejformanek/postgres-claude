# pl_gram.y

**Source pin:** `e18b0cb7344`. Lines read: 1–4255 (complete).

## One-line summary

Bison grammar (4255 raw lines, expands to `pl_gram.c`) for the plpgsql
procedural language: recognises the plpgsql control-flow skeleton
(BEGIN/EXCEPTION/END blocks, IF/CASE/LOOP/WHILE/FOR/FOREACH, RAISE,
RETURN, OPEN/FETCH/MOVE/CLOSE, COMMIT/ROLLBACK) and uses a "read SQL
fragment via the core scanner" trick to slice arbitrary SQL text out
between plpgsql tokens, deferring real parsing to `raw_parser()` at
syntax-check time and to `pg_analyze_and_rewrite_*` at execution time.

## Public API / entry points

This file's only external entry is the bison-generated `plpgsql_yyparse`
(via `%name-prefix="plpgsql_yy"` at line 128); declared in
`source/src/pl/plpgsql/src/plpgsql.h`. The caller is
`do_compile()` in `pl_comp.c` (see `pl_comp.md`). The whole rest of the
file is `static` helpers consumed only by the grammar's semantic
actions.

Bison parameters (lines 123–129):

- `%parse-param {PLpgSQL_stmt_block **plpgsql_parse_result_p}` — result
  pointer, written by the `pl_function` reduction at line 376.
- `%parse-param {yyscan_t yyscanner}` — re-entrant scanner state owned
  by `pl_scanner.c`.
- `%pure-parser`, `%expect 0`, `%locations` — pure (no globals), zero
  shift-reduce conflicts allowed, location tracking on.

Static helpers worth naming (prototypes at lines 59–119):

- `tok_is_keyword(tok, lval, kw_token, kw_str)` — case-insensitive
  match against an unreserved keyword. Used everywhere in semantic
  actions to recognise context-sensitive words (NEXT, QUERY, EXECUTE,
  REVERSE, FIRST, LAST, ABSOLUTE, RELATIVE, FORWARD, BACKWARD, ALL,
  NO/SCROLL, ROW_COUNT, …).
- `make_plpgsql_expr(query, parsemode)` — factory at lines 2670–2685.
  Wraps an extracted SQL substring in a `PLpgSQL_expr`, capturing
  `func = plpgsql_curr_compile` and `ns = plpgsql_ns_top()`.
- `mark_expr_as_assignment_source(expr, target)` — at lines 2688–2712;
  optimistically sets `target_is_local = true`; later refined by
  `plpgsql_mark_local_assignment_targets` in `pl_funcs.c`.
- `read_sql_construct(...)` — the central token-slice routine; lines
  2759–2864. See dedicated section below.
- `read_sql_expression`, `read_sql_expression2`, `read_sql_stmt` —
  convenience wrappers around `read_sql_construct` (lines 2714–2743).
- `read_datatype(tok, ...)` — DECLARE-section type parser; understands
  `%TYPE`, `%ROWTYPE`, and array decoration; defers everything else to
  `parse_datatype` → `typeStringToTypeName` + `typenameTypeIdAndMod`
  (lines 2870–3024).
- `make_execsql_stmt(firsttoken, location, word, ...)` — the
  catch-all SQL-statement node builder; identifies an optional INTO
  clause and runs `check_sql_expr` against the redacted text. Lines
  3031–3194.
- `read_fetch_direction` / `complete_direction` — parse the optional
  direction keywords of FETCH/MOVE. Lines 3200–3355.
- `make_return_stmt` / `make_return_next_stmt` / `make_return_query_stmt`
  — assemble the three RETURN flavours with the right
  retset / rettype / OUT-parameter validation. Lines 3358–3580 (approx).
- `read_into_target` / `read_into_scalar_list` / `make_scalar_list1` —
  parse the variable list after INTO. Lines 3590–3758.
- `check_sql_expr(stmt, parseMode, location, yyscanner)` — run the core
  parser on a freshly-cut SQL substring under an error-context
  callback that transposes the syntax error back into the function
  source. Lines 3782–3806.
- `plpgsql_sql_error_callback` — the errcontext callback used by
  `check_sql_expr` and `parse_datatype`. Lines 3808–3837.
- `parse_datatype` — equivalent of `check_sql_expr` for DECLARE-section
  type names. Lines 3848–3882.
- `check_labels` — block-label start/end-match enforcer. Lines 3887–3906.
- `read_cursor_args` — handle the comma-separated `(arg [, ...])` after
  a cursor name, supporting both positional and named (`name := val`,
  `name => val`) notation; emits a synthesised SELECT-list-shaped
  expression. Lines 3918–4076.
- `read_raise_options` — parse RAISE … USING `keyword = expr [, ...]`
  list. Lines 4081–4139.
- `check_raise_parameters` — `%`-counter that verifies the number of
  comma-separated args matches the placeholders. Lines 4145–4174.
- `make_case` — fix up `CASE expr WHEN val THEN …` into the more
  uniform `WHEN __Case__Variable_N__ IN (val) THEN …`. Lines 4179–4254.

## Key invariants

- **Zero shift-reduce conflicts.** `%expect 0` at line 127 — any new
  rule that introduces ambiguity will fail the build. The "lookahead
  + keyword-by-text" pattern is the workaround the grammar uses
  whenever a clean LALR(1) rule would conflict.
- **All allocation is palloc, not malloc.** `#define YYMALLOC palloc` /
  `#define YYFREE pfree` at lines 45–46. Comment at lines 41–44:
  *"Bison doesn't allocate anything that needs to live across parser
  calls, so we can easily have it use palloc instead of malloc. This
  prevents memory leaks if we error out during parsing."*
  [verified-by-code]
- **`IdentifierLookup` is the scanner's mode switch.** Three states:
  `IDENTIFIER_LOOKUP_NORMAL` (default, in proc_sect),
  `IDENTIFIER_LOOKUP_DECLARE` (no variable resolution inside DECLARE,
  set at line 480), `IDENTIFIER_LOOKUP_EXPR` (lookup but never expand,
  used inside `read_sql_construct` so that variables encountered in the
  SQL text aren't mistaken for plpgsql tokens — line 2784).
  Save/restore around `read_sql_construct` at 2782–2832 is the discipline
  every helper must follow.
- **Block label scope is opened by `opt_block_label` / `opt_loop_label`
  and closed by `plpgsql_ns_pop` in the OUTER reduction.** See lines
  441 (`pl_block` action), 1362 (`stmt_for` action). The grammar
  itself never directly calls `plpgsql_ns_pop`; control-flow rules
  push in their prologue mid-rule action and pop in their wrap-up.
- **Every reduction that builds a statement bumps `nstatements`.**
  Pattern: `new->stmtid = ++plpgsql_curr_compile->nstatements`. Repeats
  ~30 times in the file. Used as a per-function statement identifier
  for execution-stats / cache keying. [verified-by-code]
- **`plpgsql_curr_compile` is the parse-time global function pointer.**
  Set by `pl_comp.c` before calling `plpgsql_yyparse`; semantic actions
  read its `fn_retset` / `fn_rettype` / `out_param_varno` /
  `fn_prokind` to emit the right "RETURN cannot have a parameter in …"
  errors (`make_return_stmt`, lines 3370–3403). Single-threaded
  backend means no concurrency, but recursive compile (a function whose
  default expression triggers compile of another function) would
  clobber it — handled by `pl_comp.c` via save/restore around the
  inner compile.
- **Empty-input is an error in `read_sql_construct`.** Line 2840:
  `if (startlocation >= endlocation)` → `yyerror "missing expression"`
  or `"missing SQL statement"`. Prevents propagating zero-length SQL
  strings into `raw_parser`.
- **Mismatched parens fail before EOF.** Line 2802: `parenlevel < 0`
  triggers `yyerror "mismatched parentheses"`; line 2813 also checks at
  EOF/semicolon.
- **`%expect 0` interacts with INTO ambiguity.** The grammar can't tell
  whether INTO inside `INSERT … INTO …` belongs to the SQL or to the
  plpgsql INTO-target clause. Resolved by ad-hoc lookback at
  `make_execsql_stmt:3141-3156`: skip INTO if `prev_tok == K_INSERT` or
  `K_MERGE`, or if `firsttoken == K_IMPORT`. The 86-line comment
  block at 3059–3092 spells out the three known exceptions and
  warns *"Any future additional uses of INTO in the main grammar will
  doubtless break this logic again ... beware!"*

## Grammar structure

The grammar is rooted at:

```
pl_function : comp_options pl_block opt_semi
```

(line 374). `comp_options` (382–410) handles the `#option dump`,
`#print_strict_params`, and `#variable_conflict` pragmas — they set
fields on `plpgsql_curr_compile` rather than building AST. The
result is `*plpgsql_parse_result_p = (PLpgSQL_stmt_block *) $2;`.

### Block structure

```
pl_block        : decl_sect K_BEGIN proc_sect exception_sect K_END opt_label
decl_sect       : opt_block_label
                | opt_block_label decl_start
                | opt_block_label decl_start decl_stmts
proc_sect       : /* empty */ | proc_sect proc_stmt
```

`pl_block` (425–445) is where the namespace is popped (line 441) and
the block-label match enforced (`check_labels`). `decl_start` flips
`plpgsql_IdentifierLookup` to `IDENTIFIER_LOOKUP_DECLARE` (line 480)
so identifiers in the DECLARE section don't resolve as variables.

### Statement dispatch

`proc_stmt` (846–894) is a simple alternation across every statement
type. The rule names mirror `PLPGSQL_STMT_*` cmd-types one-to-one.
Of these, the SQL-cutting statements are:

- `stmt_assign` (972–1011) — `target := expr;`. Uses `RAW_PARSE_PLPGSQL_ASSIGN{1,2,3}` based on whether the target is a single name, `a.b`, or `a.b.c`; calls `read_sql_construct` with `';'` as terminator.
- `stmt_perform` (896–931) — reads everything up to `;` and then
  **rewrites the prefix** `PERFORM` → ` SELECT` (then memmoves to
  delete the leading space). See "The PERFORM hack" below.
- `stmt_call` (933–970) — `CALL` and `DO` share the same struct;
  push back the K_CALL/K_DO token and let `read_sql_stmt` slurp the
  whole thing.
- `stmt_execsql` (1999–2033) — the catch-all for anything starting with
  `INSERT`, `MERGE`, `IMPORT`, or a non-variable identifier. Delegates
  to `make_execsql_stmt`.
- `stmt_dynexecute` (2035–2098) — `EXECUTE expr [INTO …] [USING …]`.
- `stmt_open` (2101–2178) — handles the bound-cursor case
  (`OPEN c (args)`), the unbound-with-static-query case
  (`OPEN c FOR SELECT …`), and the dynamic case
  (`OPEN c FOR EXECUTE … USING …`). The three paths converge in a
  single `PLpgSQL_stmt_open` struct that has separate `query`,
  `dynquery`, and `argquery` slots.
- `stmt_return` (1785–1809) — dispatches to `make_return_stmt`,
  `make_return_next_stmt`, or `make_return_query_stmt` based on the
  optional NEXT/QUERY keyword.
- `stmt_raise` (1811–1955) — three forms parsed in-line: re-raise
  (`RAISE;`), `RAISE [level] condition`, and
  `RAISE [level] 'format', args USING opt = expr, …`.

The pure-plpgsql control-flow statements are simpler:

- `stmt_if` (1190–1205), `stmt_elsifs` (1207–1222), `stmt_else`
  (1224–1232).
- `stmt_case` (1234–1238) — semantic action delegates to `make_case`,
  which does the WHEN-list rewrite.
- `stmt_loop` (1295), `stmt_while` (1313), `stmt_for` (1332),
  `stmt_foreach_a` (1674) — all share `loop_body` (1981).
- `stmt_exit` (1722) — `EXIT` and `CONTINUE` share a struct with an
  `is_exit` flag. The optional label resolves via
  `plpgsql_ns_find_nearest_loop` at execution time.
- `stmt_assert` (1957–1979) — `ASSERT cond[, message];`.

### FOR-control disambiguation (`for_control`, 1366–1605)

The most painful rule in the file. After `FOR var IN`, the next token
could open four entirely different statements:

1. `EXECUTE expr LOOP …` → dynamic-FOR (`PLpgSQL_stmt_dynfors`).
2. `cursor_var` (a `DTYPE_VAR` of `REFCURSOROID`) → cursor-FOR
   (`PLpgSQL_stmt_forc`).
3. `[REVERSE] expr1 .. expr2 [BY exprN] LOOP …` → integer-FOR
   (`PLpgSQL_stmt_fori`).
4. `expr LOOP …` where expr is an arbitrary query → query-FOR
   (`PLpgSQL_stmt_fors`).

Cases 3 and 4 are ambiguous **at the token level** because the query
in case 4 needn't start with SELECT — `WITH ...`, `VALUES (...)`, etc.
are all valid. The grammar's response (comment at 1467–1478): scan
the text token-by-token via `read_sql_construct` with TWO terminators
(`DOT_DOT` and `K_LOOP`); whichever is hit first decides the case.
If `DOT_DOT` is seen, retro-actively re-parse the slurped text under
`RAW_PARSE_PLPGSQL_EXPR` mode (line 1515). The author's gloss at 1473:
*"We use the ugly hack of looking for two periods after the first token."*

### Exception-block handling

```
exception_sect  : /* empty */
                | K_EXCEPTION { mid-rule: build sqlstate/sqlerrm vars } proc_exceptions
proc_exception  : K_WHEN proc_conditions K_THEN proc_sect
proc_conditions : proc_conditions K_OR proc_condition
                | proc_condition
proc_condition  : any_identifier { lookup condition name, or SQLSTATE 'xxxxx' }
```

The mid-rule action at 2329–2354 is the only place where `sqlstate`
and `sqlerrm` magic variables are introduced; they have block scope
and are marked `isconst = true`. The reduction at 2356–2361 wires the
parsed exception list onto the same `new` struct.

`proc_condition` (2402–2436) routes name → `plpgsql_parse_err_condition`
(in `pl_comp.c`) for symbolic conditions like `division_by_zero`, OR
parses `SQLSTATE '22012'` literally — validating the 5-char alphanumeric
shape at 2418–2421.

### Cursor declarations

`decl_cursor_query` (593–597) immediately calls `read_sql_stmt`
without bothering to enumerate a grammar for SELECT. Cursor args are
optional and parsed by `decl_cursor_args` (599–632) into a synthetic
`PLpgSQL_row` whose fields are the named parameters.

### GET DIAGNOSTICS

`stmt_getdiag` (1013–1074) enforces the rule that some kinds are only
valid in `CURRENT` mode (`ROW_COUNT`, `PG_ROUTINE_OID`) and others
only in `STACKED` mode (`MESSAGE_TEXT`, `RETURNED_SQLSTATE`, column /
constraint / datatype / table / schema names, error context / detail
/ hint). `PG_CONTEXT` works in both. `getdiag_item` (1112–1158) uses
`tok_is_keyword` extensively because these identifiers are unreserved.

### Transactional statements

`stmt_commit` (2249) and `stmt_rollback` (2263) build trivial
`PLpgSQL_stmt_commit` / `PLpgSQL_stmt_rollback` nodes;
`opt_transaction_chain` (2277) picks up the optional `AND CHAIN` /
`AND NO CHAIN`.

## The "read SQL fragment" trick (`read_sql_construct`)

This is the seam where every SQL substring inside a plpgsql function
enters the AST. Signature (line 2760):

```c
static PLpgSQL_expr *
read_sql_construct(int until, int until2, int until3,
                   const char *expected,
                   RawParseMode parsemode,
                   bool isexpression, bool valid_sql,
                   int *startloc, int *endtoken,
                   YYSTYPE *yylvalp, YYLTYPE *yyllocp,
                   yyscan_t yyscanner);
```

Algorithm:

1. **Switch identifier-lookup mode** to `IDENTIFIER_LOOKUP_EXPR` (line
   2784); save the previous mode in `save_IdentifierLookup`. This
   means the scanner *will* still recognise plpgsql variables (so
   `T_DATUM` tokens fire and the scanner can mark them as
   parameters), but it won't treat their names as plpgsql keywords.
2. **Pump the scanner forward** via `yylex(yylvalp, yyllocp, yyscanner)`
   in a tight loop (line 2786 onwards). For each token:
   - If `tok == until` (or `until2`, `until3`) AND `parenlevel == 0`,
     break. The three terminators handle the common shapes (one for
     simple expressions, two for `FETCH … FROM|IN`, three for
     `USING ... , … ;`).
   - Maintain `parenlevel` by counting `(`/`[` vs `)`/`]` (lines
     2797–2804). Both shapes count uniformly — important so that
     `array[idx]` and `func(a, b)` don't terminate early on internal
     commas.
   - On `tok == 0` or `tok == ';'` outside a paren, raise either
     `"missing %s at end of SQL expression"` or `… "SQL statement"`
     (lines 2811–2827). `;` is fatal because the statement is
     unterminated.
   - Remember `endlocation = *yyllocp + plpgsql_token_length(yyscanner)`
     after each accepted token (line 2829). `plpgsql_token_length` is
     a `pl_scanner.c` helper that knows how to report the byte length
     of the most recently lexed token.
3. **Slice the source text.** `plpgsql_append_source_text(&ds,
   startlocation, endlocation, yyscanner)` (line 2855) does the
   substring extraction directly from the scanner's source buffer.
   The comment at 2848–2854 is important: the slice deliberately
   *includes* trailing comments adjacent to the last accepted token
   (because earlier `;` stripping was tripped up by `-- comment`
   right before whitespace before the `;`).
4. **Restore lookup mode.** Line 2832.
5. **Build expression.** `make_plpgsql_expr(ds.data, parsemode)` at
   line 2857 wraps the text + parse-mode + captured ns chain into a
   `PLpgSQL_expr`.
6. **Syntax-check.** If `valid_sql`, run `check_sql_expr(expr->query,
   expr->parseMode, startlocation, yyscanner)` immediately (line
   2861). This invokes `raw_parser()` under the error-context
   callback that transposes positions back into function source.

What this guarantees about the slice:

- It's **paren-balanced**. (`mismatched parentheses` would have
  fired.)
- It **doesn't contain a top-level `;`** unless `;` was the
  terminator. (Embedded `;` inside parens is allowed — relevant for
  composite-types and subquery expressions.)
- It's **non-empty**. (Empty-input check at line 2840.)
- It's **syntactically valid SQL of the requested parse mode** (when
  `valid_sql == true` — only the integer-FOR-loop case at line 1497
  passes `false`, because we don't yet know the parse mode.)

What this does **not** guarantee:

- No semantic checking. Type errors, missing columns, function
  resolution etc. are all deferred to execution.
- `target_param` is not yet filled in for assignment sources — that
  happens later in `mark_expr_as_assignment_source` and is finalised
  by `plpgsql_mark_local_assignment_targets`.

The convenience wrappers (lines 2714–2743) just pre-bind common
argument patterns:

```c
read_sql_expression(until, expected, …)
    -> read_sql_construct(until, 0, 0, expected,
                          RAW_PARSE_PLPGSQL_EXPR,
                          isexpression=true, valid_sql=true, …)

read_sql_expression2(until, until2, expected, *endtoken, …)
    -> read_sql_construct(until, until2, 0, expected,
                          RAW_PARSE_PLPGSQL_EXPR,
                          isexpression=true, valid_sql=true, …)

read_sql_stmt(…)
    -> read_sql_construct(';', 0, 0, ";",
                          RAW_PARSE_DEFAULT,
                          isexpression=false, valid_sql=true, …)
```

### The PERFORM hack

`stmt_perform` (896–931) shows the trick at its limit. PERFORM isn't a
real SQL keyword, so the grammar:

1. Push the K_PERFORM back into the scanner (line 905) so
   `read_sql_construct` sees it as the first token of the slice.
2. Read until `;` with `valid_sql=false` (because PERFORM isn't valid
   SQL yet).
3. **Overwrite the buffer in place**: `memcpy(new->expr->query,
   " SELECT", 7)` then `memmove` to drop the leading space (lines
   921–924). PERFORM (7 chars) → " SELECT" (7 chars) → "SELECT".
4. **Manually run `check_sql_expr` with `startloc + 1`** to account
   for the position shift (line 926).

This is the kind of code that makes the file feel hand-tooled.

### The PERFORM-style "redact INTO" trick in `make_execsql_stmt`

A similar idea at lines 3161–3171: when an INTO clause is present
inside an EXECSQL statement, the function calls
`appendStringInfoSpaces(&ds, into_end_loc - into_start_loc)` to
**blank out the INTO part with spaces** so that the byte offsets in
the redacted SQL match the byte offsets in the function source. The
SPI-level error positions then transpose cleanly.

## Cross-references

- Sibling files in `src/pl/plpgsql/src/`:
  - `pl_scanner.c` — owns `plpgsql_token_length`,
    `plpgsql_push_back_token`, `plpgsql_peek`, `plpgsql_peek2`,
    `plpgsql_append_source_text`, `plpgsql_scanner_errposition`, and
    the unreserved-keyword classifier. The grammar lives upstream of
    every one of these.
  - `pl_funcs.c` — implements `plpgsql_ns_push/pop/lookup`,
    `plpgsql_stmt_typename`, the AST walker, and
    `plpgsql_mark_local_assignment_targets` (finishes the work that
    `mark_expr_as_assignment_source` here starts).
  - `pl_comp.c` — calls `plpgsql_yyparse`; implements
    `plpgsql_parse_err_condition` (called from `proc_condition` at
    line 2406), `plpgsql_recognize_err_condition` (called from
    `stmt_raise` at line 1939), `plpgsql_build_variable`,
    `plpgsql_build_datatype`, `plpgsql_adddatum`,
    `plpgsql_add_initdatums`. Provides `plpgsql_curr_compile`.
  - `plpgsql.h` — externs for everything above; defines all the
    `PLpgSQL_stmt_*` structs whose fields the semantic actions
    populate.
  - `pl_exec.c` — only the consumer; runs the AST this file produces.
- Backend:
  - `source/src/backend/parser/scan.l` and
    `source/src/backend/parser/parser.c` — the core SQL scanner
    that plpgsql's scanner wraps, and the `raw_parser()` entry
    that `check_sql_expr` calls.
  - `source/src/backend/parser/parse_type.c` — `typeStringToTypeName`
    and `typenameTypeIdAndMod` consumed by `parse_datatype`.
  - `source/src/backend/utils/error/elog.c` —
    `ErrorContextCallback`, `internalerrposition`, `geterrposition`,
    `errposition` used by `plpgsql_sql_error_callback`.
  - `source/src/backend/access/xact.c` — host for the subxact
    callback that `pl_exec.c` registers; tangential to this file.

<!-- issues:auto:begin -->
- [Issue register — `plpgsql`](../../../../../issues/plpgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-correctness: INTO disambiguation is heuristic and known
  fragile (confirmed)] —
  `source/src/pl/plpgsql/src/pl_gram.y:3059-3092` and `3141-3156` —
  the prose comment explicitly says *"Any future additional uses of
  INTO in the main grammar will doubtless break this logic again ...
  beware!"*. The code special-cases `INSERT INTO`, `MERGE INTO`, and
  `IMPORT … INTO`. Any new SQL construct that uses INTO will silently
  swallow the user's INTO-target. Confirmed because the maintainer
  flagged it themselves.
- [ISSUE-correctness: integer-FOR vs query-FOR disambiguation uses
  textual `..` heuristic (likely)] —
  `source/src/pl/plpgsql/src/pl_gram.y:1467-1505` — comment:
  *"We use the ugly hack of looking for two periods after the first
  token."* A SQL query containing `..` outside the first-position
  context (e.g. in a string literal, a comment, or syntactically inside
  a subquery) cannot trip this because `read_sql_construct` only
  inspects the top-level token stream. Still, the rule documented as
  "ugly hack" is a long-term fragility.
- [ISSUE-correctness: PERFORM in-place buffer rewrite assumes
  `strlen("PERFORM") == strlen(" SELECT")` (likely)] —
  `source/src/pl/plpgsql/src/pl_gram.y:920-924` — relies on both
  words being exactly 7 chars. If anyone were to rename the
  substitution, the `memcpy(... 7)` and the `memmove(..., ..., strlen)`
  pair would have to be re-derived. Bug is theoretical but the
  invariant is unstated.
- [ISSUE-error-handling: `read_into_scalar_list` hard-caps at 1024
  variables via stack arrays (likely)] —
  `source/src/pl/plpgsql/src/pl_gram.y:3662-3679` — `char
  *fieldnames[1024]; int varnos[1024];` on the C stack, with an
  explicit `ereport(ERROR, ERRCODE_PROGRAM_LIMIT_EXCEEDED, "too many
  INTO variables specified")` at line 3676. Not a security issue
  (limit is enforced before overflow), but a hard cap with no GUC
  override is a sharp edge for code-generated plpgsql.
- [ISSUE-security: condition-name lookup is case-insensitive without
  schema scoping (maybe)] —
  `source/src/pl/plpgsql/src/pl_gram.y:2402-2436` (and the implementation
  at `pl_comp.c:2176` `plpgsql_parse_err_condition`). Conditions are
  matched against a hard-coded table in `pl_comp.c`; users cannot
  shadow built-ins. This is actually safe — recording as a
  negative-result: NO shadowing risk. Severity nit.
- [ISSUE-correctness: `make_case` rewrites WHEN clauses textually as
  `"VAR" IN (orig)` (maybe)] —
  `source/src/pl/plpgsql/src/pl_gram.y:4240-4250` — quotes the
  generated `__Case__Variable_N__` name with `"…"` and splices the
  user's expression as plain text. A comma-separated WHEN list
  becomes `"VAR" IN (a, b, c)` which is valid; but the comment at
  4202–4206 admits *"previous parsing won't have complained if the
  WHEN ... THEN expression contained multiple comma-separated values"*
  — meaning a WHEN clause that the user expects to be a single
  expression but written as `(1, 2)` becomes `"VAR" IN ((1, 2))`,
  a row-IN-row test. The interplay is documented as klugy.
- [ISSUE-defense-in-depth: `read_raise_options` allows unlimited
  USING-option entries (nit)] —
  `source/src/pl/plpgsql/src/pl_gram.y:4082-4139` — the `for (;;)` loop
  accepts as many `keyword = expr` clauses as there are tokens; no
  per-statement limit. Each entry palloc's a `PLpgSQL_raise_option`.
  Bounded by the function source size, so not exploitable.
- [ISSUE-api-shape: file-scope static `plpgsql_curr_compile` makes
  recursive compile risky (maybe)] —
  `source/src/pl/plpgsql/src/pl_gram.y:392,400,404,408,433,etc.` —
  semantic actions throughout reach into the global. If a default-value
  expression on a variable triggers compilation of another function,
  the inner compile must save/restore this pointer. `pl_comp.c`
  handles this, but the grammar file doesn't document the assumption.
- [ISSUE-documentation: `make_execsql_stmt`'s INTO redaction trick is
  spelled out in code but missing from `plpgsql.h` API docs (nit)] —
  `source/src/pl/plpgsql/src/pl_gram.y:3161-3171` — the space-padding
  of the INTO span (so that SPI error positions line up with function
  source) is non-obvious. Worth a sentence in plpgsql.h about
  what `PLpgSQL_stmt_execsql->sqlstmt->query` actually contains.
