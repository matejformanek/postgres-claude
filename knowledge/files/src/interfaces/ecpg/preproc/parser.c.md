---
path: src/interfaces/ecpg/preproc/parser.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 312
depth: deep
---

# `parser.c` — ECPG preprocessor's lexer/grammar glue driver

## Purpose
This is the ECPG preprocessor's hand-written driver layer that sits between the
flex scanner (`pgc.l`, which exposes `base_yylex`) and the bison grammar
(`preproc.y` → generated `preproc.c`, which calls `base_yyparse`). Its central
job is `filtered_base_yylex`, a one-token-lookahead filter that rewrites certain
tokens so the SQL grammar stays LALR(1) despite needing multi-word lookahead in
spots (e.g. `NOT BETWEEN`, `WITH TIME`, `NULLS FIRST`) `parser.c:39-55`
`[from-comment]`. It is deliberately structured to mirror the backend's
`src/backend/parser/parser.c`, minus re-entrancy `parser.c:6-7` `[from-comment]`.
It also collapses Unicode-escaped identifier/string sequences (`UIDENT`/`USCONST`
+ optional `UESCAPE`) into plain `IDENT`/`SCONST`, and synthesizes `yylloc`
location strings that `pgc.l` does not bother to set.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `filtered_base_yylex(void)` | `parser.c:56` | The token the grammar actually calls (via `preproc.y`); declared `extern` in `preproc_extern.h:128` `[verified-by-code]` |

All other functions in this file are `static` (`base_yylex_location`,
`check_uescapechar`, `ecpg_isspace`) `parser.c:34-36` `[verified-by-code]`.
There is no separately-exposed `parser_init` here — `parser_init` is declared in
`preproc_extern.h:127` but lives elsewhere (likely generated `ecpg.header`/
`preproc.y` glue) `[inferred]`.

## Internal landmarks

### Lookahead token buffer (file-static state)
A single-token lookahead buffer held in five file-static variables
`parser.c:28-32` `[verified-by-code]`:
- `have_lookahead` — validity flag for the buffer `parser.c:28`
- `lookahead_token` — the buffered token code `parser.c:29`
- `lookahead_yylval` / `lookahead_yylloc` / `lookahead_yytext` — the scanner
  output snapshot for the buffered token `parser.c:30-32`

These shadow the scanner's global outputs (`base_yylval`, `base_yylloc`,
`base_yytext`), which are declared extern in `preproc_extern.h:41` (for
`base_yytext`) `[verified-by-code]`.

### `filtered_base_yylex` token-rewriting state machine
1. **Acquire current token** — reuse the lookahead buffer if `have_lookahead`,
   else call `base_yylex_location` `parser.c:65-75` `[verified-by-code]`.
2. **Fast path** — only `FORMAT`, `NOT`, `NULLS_P`, `WITH`, `WITHOUT`, `UIDENT`,
   `USCONST` need lookahead; everything else returns immediately
   `parser.c:80-92` `[verified-by-code]`.
3. **Save/peek/restore** — the scanner globals are saved into locals, the next
   token is fetched into the lookahead buffer, and the globals are restored to
   the *current* token's values; `have_lookahead = true` `parser.c:94-111`
   `[verified-by-code]`.
4. **Conditional rewrite** by `(cur_token, next_token)` pair `parser.c:113-220`:
   - `FORMAT` + `JSON` → `FORMAT_LA` `parser.c:116-124`
   - `NOT` + `{BETWEEN,IN_P,LIKE,ILIKE,SIMILAR}` → `NOT_LA` `parser.c:126-138`
   - `NULLS_P` + `{FIRST_P,LAST_P}` → `NULLS_LA` `parser.c:140-149`
   - `WITH` + `{TIME,ORDINALITY}` → `WITH_LA` `parser.c:151-160`
   - `WITHOUT` + `TIME` → `WITHOUT_LA` `parser.c:162-170`
   - `UIDENT`/`USCONST` → `IDENT`/`SCONST`, with optional 3-token `UESCAPE`
     absorption `parser.c:171-219`
   `[verified-by-code]`

### `UESCAPE` 3-token absorption
When a `UIDENT`/`USCONST` is followed by `UESCAPE`, the filter fetches a *third*
token (must be `SCONST`, else `mmerror`) `parser.c:188-191`, validates the escape
char via `check_uescapechar` (length-3 quoted string, `escstr[1]` is the char)
`parser.c:198-199`, then fuses all three into one string with
`make3_str(value, " UESCAPE ", escstr)` and sets `have_lookahead = false` to
consume all three `parser.c:205-212` `[verified-by-code]`. This is the one place
the lookahead buffer holds, conceptually, two consumed tokens beyond the current.

### `base_yylex_location` — yylloc synthesis
Wraps `base_yylex` and fills `base_yylloc` `parser.c:238-278` `[verified-by-code]`:
- For tokens whose `base_yylval.str` is set by `pgc.l` (`Op`, `CSTRING`,
  `CPP_LINE`, `CVARIABLE`, `BCONST`, `SCONST`, `USCONST`, `XCONST`, `FCONST`,
  `IDENT`, `UIDENT`, `IP`): `loc_strdup` the string value `parser.c:246-260`.
- Otherwise: `loc_strdup(base_yytext)` then ASCII-only downcase in place
  `parser.c:262-275`. The downcasing is cosmetic but also load-bearing because
  ecpglib and pre-v18 regression outputs expect downcased keywords
  `parser.c:233-236` `[from-comment]`.

### `check_uescapechar` / `ecpg_isspace`
Helpers that the file comment explicitly says must stay in sync with their
equivalents in `pgc.l` `parser.c:280-283` `[from-comment]`. `check_uescapechar`
rejects hex digits, `+`, `'`, `"`, and whitespace `parser.c:286-297`;
`ecpg_isspace` enumerates the flex whitespace set ` \t\n\r\f` `parser.c:302-312`
`[verified-by-code]`.

## Invariants & gotchas
- **One-token lookahead only.** The whole filter exists to reduce the grammar's
  multi-word needs to a single buffered token so `preproc.y` stays LALR(1)
  `parser.c:42-44` `[from-comment]`.
- **Scanner globals must be saved/restored around every peek.** Because
  `base_yylex` overwrites `base_yylval`/`base_yylloc`/`base_yytext`, the filter
  carefully swaps them so the returned token's outputs are the ones visible to
  the parser `parser.c:94-111`, `parser.c:183-203` `[verified-by-code]`.
- **`have_lookahead = false` after `UESCAPE` fusion** is what makes a 3-token
  sequence collapse cleanly — forgetting it would leak the third token
  `parser.c:212` `[inferred]`.
- **Keep these helpers in lockstep with `pgc.l`.** `check_uescapechar` and
  `ecpg_isspace` are duplicated logic; drift would silently change which escape
  chars or whitespace the preprocessor accepts vs. the scanner `parser.c:280-283`
  `[from-comment]`.
- **No error-location reporting.** Unlike the backend, ECPG does not report error
  positions; the header comment flags this as future work `parser.c:9-10`
  `[from-comment]`.
- **Mirror-of-backend constraint.** This file is meant to track
  `src/backend/parser/parser.c`; the LA-token list (`FORMAT_LA`, `NOT_LA`, etc.)
  should be kept in sync when the backend grammar changes `parser.c:6-7`
  `[from-comment]`.

## Cross-refs
- [[src/interfaces/ecpg/preproc/preproc_extern.h]] — declares `filtered_base_yylex`
  `:128`, `base_yylex` `:80`, `base_yyparse` `:79`, `base_yytext` `:41`,
  `make3_str` `:90`, `loc_strdup` `:85`, `mmerror` `:91`, and `PARSE_ERROR` `:134`.
- [[src/backend/parser/parser.c]] — the backend twin this file deliberately
  mirrors (`parser.c:6-7`).
- `pgc.l` — the flex scanner providing `base_yylex` and setting `base_yylval`.
  **Generated/flex source, not separately documented in this corpus.**
- [[idioms/parser-pipeline]] — the scanner → filter → bison driver pattern shared
  with the backend.

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-maintenance: duplicated whitespace/escape logic]** `parser.c:280-283`
  — `check_uescapechar` and `ecpg_isspace` are hand-copied from `pgc.l` with only
  a comment to enforce the invariant; there is no compile-time link, so the two
  copies can drift. Low severity (well-flagged, rarely changing), but a real
  latent maintenance hazard `[from-comment]`.
