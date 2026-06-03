# scan.l

- **Source:** `source/src/backend/parser/scan.l` (39 KB; generated to `scan.c` at build time)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim (top-of-file design notes only)

## Purpose

Flex specification for the SQL lexer. Produces the `core_yylex()` token
function that the bison grammar calls via `base_yylex()` (`parser.c:111`).

## Two load-bearing invariants

1. **Kept in sync by hand with `src/fe_utils/psqlscan.l` and
   `src/interfaces/ecpg/preproc/pgc.l`.** The header comment is explicit:
   "The rules in this file must be kept in sync with..." `scan.l:9-11`
   (cited in `knowledge/idioms/parser-pipeline.md`).

2. **No-backtrack.** The lexer must never back up — flex's `-b` flag
   produces `lex.backup`, and the Makefile checks it's empty since PG 9.2.
   The header explains why: several-percent speedup on raw parsing.
   `scan.l:13-22`

## What it does NOT do

No catalog access, no UTF-8 normalization beyond `pg_wchar` conversions, no
keyword lookup (that's `src/common/kwlookup.c` called from the scanner
when `IDENT` matches).

## Entry from outside

- `scanner_init()` / `scanner_finish()` — called by `raw_parser()` in
  `parser.c:49,80`.
- `core_yylex()` — called by `base_yylex()` in `parser.c:130` to fetch the
  next token.

## Related

- `scansup.c` — escape handling for string literals (`pg_unicode_to_server`,
  `pg_strtoint*`-friendly trim helpers).
- `kwlookup.c` (in `src/common/`) — keyword table binary search.
- `scanner.h` — public scanner API.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
