# src/include/parser/scanner.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 147 [verified-by-code]

## Role

Public-ish API of the **core flex scanner**. Shared with PL/pgSQL so
the PL parser can use the same lexer. The rest of the backend should
go through `parser.h`'s higher-level `raw_parser` — this header is for
parser-implementing modules only.

## Public API

- `core_YYSTYPE` union — `ival` / `str` / `keyword` (`:29-34`).
- `YYLTYPE` = `int` (byte-offset of token start) (`:44`).
- Token-number convention (comment `:46-57`): ASCII chars plus
  named tokens IDENT, ICONST, PARAM, etc. The first declarations
  in any consuming bison grammar must match this list for token
  numbers to align.
- `core_yy_extra_type` — the YY_EXTRA struct:
  - `scanbuf`, `scanbuflen` — physical input buffer (`:72-73`).
  - `keywordlist` + `keyword_tokens` — keyword lookup pair
    (`:78-79`).
  - `backslash_quote` — copied from GUC at init (`:87`).
  - `literalbuf` / `literallen` / `literalalloc` —
    palloc'd accumulator for multi-rule literals (`:96-98`).
  - `state_before_str_stop`, `xcdepth`, `dolqstart`,
    `save_yylloc` — flex state stash (`:103-106`).
  - `utf16_first_part` — half of a UTF16 surrogate pair waiting
    for the second (`:109`).
  - `saw_non_ascii` flag — encoding-validation marker (`:112`).
- `core_yyscan_t` opaque type (`:118`).
- `ScannerCallbackState` — for errposition reporting (`:121-126`).
- Entry points: `scanner_init`, `scanner_finish`, `core_yylex`,
  `scanner_errposition`, `setup_scanner_errposition_callback`,
  `cancel_scanner_errposition_callback`, `scanner_yyerror`
  (`pg_noreturn`) (`:133-145`).

## Invariants

- INV-SCANNER-STATIC-TOKENS: token codes in consuming bison
  grammars MUST start with IDENT=258 etc. — this header documents
  it as a contract (`:46-57` [from-comment]). PL/pgSQL's
  `pl_gram.y` adheres.
- INV-SCANBUF-OWNERSHIP: `scanner_init` copies the input string
  into `scanbuf` (it's palloc'd, owned by scanner state).
  `scanner_finish` frees it.
- INV-LITERALBUF-NOT-NUL: literalbuf is NOT necessarily
  null-terminated until `literallen` is set and a null is
  written; reading without that is UB (`:96-98` [from-comment]).
- INV-UTF16-SURROGATE-STATE: `utf16_first_part` ≠ 0 means a high
  surrogate is pending; the next escape MUST be its low
  surrogate. Stray pending state at end-of-literal is an error.

## Notable internals

- The scanner is the same one used by PL/pgSQL — `pl_scanner.c`
  wraps it with PL-specific keyword list.
- `backslash_quote` in the struct is a **snapshot** at scanner_init
  time; later GUC SET does not affect an in-flight scan
  (`:81-86` [from-comment]).

## Trust boundary / Phase D surface

- **A11 echo (cross-cluster query trust).** The scanner is the
  first place hostile bytes meet PG. Defenses:
  - Encoding validity: `saw_non_ascii` flag drives an
    encoding-check pass for the literal — if client encoding
    claims UTF-8 but bytes are not valid UTF-8, an error is
    raised. Skipping this check on a literal would be a
    classic injection vector.
  - `backslash_quote` snapshot avoids mid-query GUC change
    confusion.
  - `xcdepth` for `/*...*/` comment nesting — depth-tracked
    so attackers can't confuse via deeply-nested comments
    overflowing.
- **A11/A13/A14 echo (identifier truncation).** Scanner accepts
  arbitrarily-long identifiers but `scansup.h` /
  `downcase_truncate_identifier` then truncates to NAMEDATALEN
  — collisions can cause unintended resolution. Cross-link to
  `scansup.h` doc.
- **flex buffer DoS.** A pathological 10 GB query string would
  palloc 10 GB into scanbuf; no GUC limits this. Pre-existing
  PG behavior — clients should reject huge queries.
- **Dollar-quoting (`dolqstart`).** `$tag$...$tag$` strings can
  embed arbitrary bytes including the backslash-quote
  character; an attacker constructing nested dollar-quotes
  has to find a tag not present in the body — generally not
  a security issue but worth flagging.

## Cross-references

- `parser/parser.h` — higher-level wrapper.
- `parser/scansup.h` — identifier downcasing / truncation.
- `parser/scan.l` — flex source.
- `common/keywords.h` — `ScanKeywordList`.
- `pl/plpgsql/src/pl_scanner.c` — reuses this scanner.
- `mb/pg_wchar.h` — encoding validation called when
  `saw_non_ascii` triggers.

## Issues / drift

- `[ISSUE-TRUST: A11 echo — no GUC limits maximum query length / scanbuf size; large hostile string drives huge palloc (low — exists upstream as known DoS)] — source/src/include/parser/scanner.h:72-73`
- `[ISSUE-DOC: comment block about token numbers (lines 46-57) is binding contract but easy to miss; new grammars built atop scanner can mis-align token codes (medium)] — source/src/include/parser/scanner.h:46-57`
- `[ISSUE-CODE: backslash_quote-snapshot approach is correct but undocumented as a defense; reads as just an init copy (low)] — source/src/include/parser/scanner.h:81-87`
