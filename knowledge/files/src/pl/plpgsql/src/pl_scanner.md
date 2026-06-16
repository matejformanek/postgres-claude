# pl_scanner.c

**Source pin:** `e18b0cb7344`. Lines read: 1–657 (complete).

## One-line summary

Thin wrapper around the core SQL scanner (`parser/scan.l` via `scanner.h`)
that layers PL/pgSQL keyword tables on top, peeks 1-2 tokens ahead, looks
up identifiers against the live namespace stack so they can be returned
as `T_DATUM`, and provides a 4-deep pushback ring so the grammar can
backtrack.

## Public API

Cites are `source/src/pl/plpgsql/src/pl_scanner.c:<line>`:

- `IdentifierLookup plpgsql_IdentifierLookup` — module global (line 26),
  declared in `plpgsql.h`. Three states: `IDENTIFIER_LOOKUP_NORMAL`,
  `IDENTIFIER_LOOKUP_DECLARE` (skip var lookup; pure keyword/word mode),
  `IDENTIFIER_LOOKUP_EXPR` (used during expression sub-parses). Set by the
  grammar around `DECLARE` sections.
- `int plpgsql_yylex(YYSTYPE *yylvalp, YYLTYPE *yyllocp, yyscan_t)` — the
  yylex called from `pl_gram.y`. Recognizes `A`, `A.B`, `A.B.C` compound
  references via 1-token lookahead chains. Lines 159–319. [verified-by-code]
- `int plpgsql_token_length(yyscan_t)` — length of the most-recently
  returned compound token, in source bytes. Lines 326–330.
- `void plpgsql_push_back_token(int token, YYSTYPE *, YYLTYPE *, yyscan_t)` —
  external pushback (bison's `unput`). Lines 400–409.
- `bool plpgsql_token_is_unreserved_keyword(int token)` — linear scan over
  `UnreservedPLKeywordTokens[]`. Lines 417–428.
- `void plpgsql_append_source_text(StringInfo, int startlocation, int endlocation, yyscan_t)`
  — slice the **original** source string (`scanorig`, NOT scanbuf) by byte
  offsets. Used by `pl_gram.y` to capture SQL expression substrings
  verbatim. Lines 434–442. [verified-by-code]
- `int plpgsql_peek(yyscan_t)` — 1-token lookahead, returns token code only.
  Lines 451–460.
- `void plpgsql_peek2(int *tok1_p, int *tok2_p, int *tok1_loc, int *tok2_loc, yyscan_t)` —
  2-token lookahead with locations. Lines 470–490.
- `int plpgsql_scanner_errposition(int location, yyscan_t)` — for `ereport()`
  inside parse-time errors; converts byte offset to character position using
  `pg_mbstrlen_with_len`, sets `internalerrposition` and
  `internalerrquery(scanorig)`. Lines 503–517. [verified-by-code]
- `void plpgsql_yyerror(YYLTYPE *, PLpgSQL_stmt_block **, yyscan_t, const char *message)`
  — bison's yyerror; ereports `ERRCODE_SYNTAX_ERROR`. Lines 533–562.
- `int plpgsql_location_to_lineno(int location, yyscan_t)` — byte offset →
  line number; cached cur_line_{start,end,num} for forward-only sweeps.
  Lines 572–593.
- `int plpgsql_latest_lineno(yyscan_t)` — return cached lineno. Lines 606–610.
- `yyscan_t plpgsql_scanner_init(const char *str)` — palloc a
  `plpgsql_yy_extra_type`, spin up the core scanner against the reserved
  keyword table, and remember `scanorig = str` (caller MUST keep alive
  until `plpgsql_scanner_finish`). Lines 620–647. [verified-by-code]
- `void plpgsql_scanner_finish(yyscan_t)` — releases the core scanner. Line 652.

## Key invariants

- **`scanorig` must outlive the scanner.** The init comment (line 616) is
  explicit: although not fed to flex, the original string is used for
  error-context messages and for `plpgsql_append_source_text`'s verbatim
  slicing — so the compile callback's `proc_source` (`pl_comp.c:204`) is
  pfree'd only AFTER `plpgsql_scanner_finish` (lines 686–687 in pl_comp.c).
  [verified-by-code]
- **MAX_PUSHBACKS = 4.** A `push_back_token` overrun is a defensive
  `elog(ERROR, "too many tokens pushed back")` (line 388). The 4-slot ring
  is justified by the grammar's worst-case (`A.B.C` rejection in the
  3-word lookahead path). [verified-by-code]
- **Pushed-back tokens are NOT re-resolved.** Lines 303–311 comment:
  "we also come through here if the grammar pushed back a T_DATUM, T_CWORD,
  T_WORD … pushbacks do not incur extra lookup work, since we'll never do
  the above code twice for the same token." This is what makes the
  `is-this-start-of-statement` test at line 282 safe — the
  `plpgsql_yytoken` field is the PREVIOUSLY returned token, never the
  same token re-arriving via pushback. [from-comment]
- **Unreserved-keyword recognition runs AFTER variable lookup.** Variable
  match is tried first (`plpgsql_parse_word(..., lookup=true, ...)`);
  only on miss does `ScanKeywordLookup` for unreserved keywords fire.
  This is what lets PL/pgSQL variable names shadow unreserved keywords.
  Lines 240–253, 280–295. [verified-by-code]
- **Quoted identifiers never match unreserved keywords.** Lines 246, 288:
  `!aux1.lval.word.quoted` gates the unreserved-keyword lookup. So
  `"begin"` (quoted) becomes T_WORD even though `begin` (unquoted) is
  reserved. [verified-by-code]
- **`AT_STMT_START` is hardcoded to 5 tokens.** `';'`, `K_BEGIN`, `K_THEN`,
  `K_ELSE`, `K_LOOP` (lines 82–87). The comment at lines 78–80 says "there
  are not very many, so hard-coding in this fashion seems sufficient" —
  if a new statement-introducing token is added without updating this
  macro, the start-of-statement unreserved-keyword preference will silently
  break for that token. [from-comment]

## Notable internals

### The big lookahead chain

`plpgsql_yylex` (line 159) implements progressive lookahead up to 5 tokens
for compound references:

```
A      → plpgsql_parse_word    (T_DATUM | T_WORD | unreserved keyword)
A.B    → plpgsql_parse_dblword (T_DATUM | T_CWORD)
A.B.C  → plpgsql_parse_tripword(T_DATUM | T_CWORD)
```

Each level peeks past the dot, and on failure pushes back the unconsumed
tokens. The compound token's `lloc + leng` is reconstructed so error
positions point to the start of the whole compound (lines 202, 217, 232).

### Statement-start unreserved-keyword preference

The single most subtle lookup rule is at lines 280–286: when the previous
token was a statement separator AND the next token is NOT an assignment
(`:=`, `=`, `[`), prefer interpreting an identifier as an unreserved
keyword rather than a variable. This is what makes
`SELECT comment FROM t` legal inside a function body even though `comment`
could be a variable name — it lets statement-introducing keywords stay
unreserved. The condition is composed of `AT_STMT_START(prev_token)`
AND NOT (assignment or `[` lookahead).

### Why `core_yylex`'s PARAM is repackaged

Line 372–375: the core lexer returns `PARAM` ($n) as an integer literal in
ival, but plpgsql treats `$1` as just another identifier (so it goes
through the same namespace lookup that turns user-declared identifiers into
T_DATUMs). The line `auxdata->lval.str = pstrdup(yytext)` re-packs it as a
string token so the rest of the wrapper code can treat `IDENT` and `PARAM`
identically (line 167).

### Operator shuffling for `<<`, `>>`, `#`

Line 360–369: the core lexer classifies `<<`, `>>`, `#` as generic
operators (Op token). Plpgsql wants them as distinct grammar tokens
`LESS_LESS`, `GREATER_GREATER`, `#` (used for block labels and
`#variable_conflict` pragmas). The translation happens on every fresh
`core_yylex` call but NOT on pushback (because pushed-back tokens have
already been translated).

### Pushback ring growth strategy

There is no growth — `MAX_PUSHBACKS` is a fixed `#define 4` (line 98).
The compile-time bound on how far the grammar needs to back up. Any future
n>3-token lookahead in the grammar would have to bump this constant.

### Identifier lookup states

`IdentifierLookup` (the enum is in `plpgsql.h`):

- `IDENTIFIER_LOOKUP_NORMAL` — full lookup; T_DATUM possible.
- `IDENTIFIER_LOOKUP_DECLARE` — used inside DECLARE sections: skip var
  lookup, so the parser sees a clean stream of IDENT/keyword tokens for
  variable-name declarations. This is what lets you say `DECLARE x int;`
  even when `x` was already declared in an enclosing block (a fresh shadow
  declaration; no false-positive variable lookup).
- `IDENTIFIER_LOOKUP_EXPR` — for SQL expression sub-parses. Variable
  matches turn into RECFIELD datums on demand, but DECLARE-mode shortcuts
  do not apply.

### Re-entrancy

The scanner is per-`yyscan_t`, so multiple scanner instances can coexist
(unlike `plpgsql_Datums`). However `plpgsql_IdentifierLookup` is a single
module-scope global (line 26), so two concurrently-active scanners would
race on its value. In practice `plpgsql_compile_callback` is non-reentrant,
so this is moot — but it's a hidden coupling.

## Cross-references

Siblings:

- `pl_comp.c` — calls `plpgsql_scanner_init`/`_finish`; provides
  `plpgsql_parse_word`/`_dblword`/`_tripword`.
- `pl_gram.y` — calls `plpgsql_yylex`, `plpgsql_peek`, `plpgsql_peek2`,
  `plpgsql_push_back_token`, `plpgsql_yyerror`, `plpgsql_token_length`,
  `plpgsql_append_source_text`.
- `pl_reserved_kwlist.h`, `pl_unreserved_kwlist.h` — keyword tables
  included for token-code arrays (lines 66–72) and for the
  `ScanKeywordList` lookup data (lines 60–61, via the `_d.h` generated
  headers).
- `plpgsql.h` — declares `IdentifierLookup` enum and `plpgsql_IdentifierLookup`.

Backend touch-points:

- `parser/scanner.h` and `parser/scan.l` — `core_yylex`, `scanner_init`,
  `scanner_finish`, `core_yy_extra_type`, `ScanKeywordLookup`,
  `GetScanKeyword`. The plpgsql scanner is a thin layer over these.
- `mb/pg_wchar.h` — `pg_mbstrlen_with_len` for byte→char offset in
  `plpgsql_scanner_errposition`.

<!-- issues:auto:begin -->
- [Issue register — `plpgsql`](../../../../../issues/plpgsql.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-correctness: `AT_STMT_START` is hardcoded; adding a new
  statement-introducing token without updating the macro silently breaks
  the "prefer unreserved keyword" rule (maybe)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:82-87` — Comment explicitly
  flags the hard-coding. A future grammar extension that adds e.g. a new
  block-introducing keyword would need to remember to add it here too.
  No compile-time check. Worth an `Assert(false && "remember to update
  AT_STMT_START")` test, or unification with a table.

- [ISSUE-defense-in-depth: 5-token-deep `internal_yylex` recursion via
  pushback ring depends on `MAX_PUSHBACKS=4`; a single extra layer of
  lookahead would `elog(ERROR)` at runtime (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:98,387-392` — The fail-fast
  `elog(ERROR)` is correct, but the only signal that the constant needs
  bumping is a runtime error — no compile-time guard.

- [ISSUE-concurrency: module-global `plpgsql_IdentifierLookup` couples
  concurrent scanner instances (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:26` — In current code only one
  compile is ever active per backend, so this is harmless. But the
  decision to keep the lookup-mode global rather than per-`yyextra` is
  invisible to anyone trying to allow nested compiles.

- [ISSUE-correctness: `plpgsql_yyerror` modifies `scanbuf` in place
  (writes `\0` at line 554) (nit)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:548-554` — Comment acknowledges:
  "this modifies scanbuf but we no longer care about that." Correct in
  current control flow (we're about to ereport ERROR), but it's a sharp
  edge — anything that tries to continue scanning after a yyerror would
  see corrupted text. Defensive only.

- [ISSUE-error-handling: `plpgsql_scanner_errposition`'s
  `pg_mbstrlen_with_len` walks the entire prefix on every error position
  computation (nit)] — `source/src/pl/plpgsql/src/pl_scanner.c:512` —
  O(n) per error; for a multi-MB function body this is wasteful, but
  errors are rare so it doesn't matter.

- [ISSUE-audit-gap: dollar-quoting and very-long-identifier handling are
  100% delegated to `core_yylex` — no plpgsql-side cap on identifier
  length, no special-case escaping (documentation)] —
  `source/src/pl/plpgsql/src/pl_scanner.c:352` — The core scanner enforces
  `NAMEDATALEN` truncation and dollar-quote nesting rules. Reviewers
  auditing PL/pgSQL's lexer attack surface need to look at
  `src/backend/parser/scan.l`; nothing here. (Note: this is a
  pointer-to-the-real-code observation, not a defect.)
