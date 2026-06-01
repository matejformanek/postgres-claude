# scansup.c

- **Source:** `source/src/backend/parser/scansup.c` (116 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim

## Purpose

Tiny set of scanner-support helpers used by both the backend lexer
(`scan.l`) and frontend scanners. [from-comment] `:3-5`

## Functions

- `downcase_truncate_identifier(ident, len, warn)` — fold to lowercase and
  truncate at `NAMEDATALEN`, with optional warning. The canonical place
  where PG's case-folding rule lives.
- `downcase_identifier(...)` — same minus truncation, used in a couple of
  places.
- `truncate_identifier(...)` — truncate only; for already-lowercase input.
- `scanner_isspace(ch)` — locale-independent whitespace check that matches
  what the scanner treats as whitespace.

## Why it's tiny

The actual escape handling for E'...' and U&'...' strings was moved long
ago into `scan.l` and `parser.c` (`check_uescapechar`, `str_udeescape`).
What remains here is the identifier-folding contract.
