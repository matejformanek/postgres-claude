# kwlookup.c

- **Source:** `source/src/common/kwlookup.c` (~70 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

The shared keyword-table lookup function used by **all** PG scanners:
backend, psql (`psqlscan.l`), ecpg (`pgc.l`), and pg_dump. Lives in
`src/common/` (not `src/backend/parser/`) precisely so frontend tools can
link it. The parser/README points here. [from-README]
`src/backend/parser/README:33-35`

## Function

`int ScanKeywordLookup(const char *str, const ScanKeywordList *keywords)`

Returns the keyword index (`0..numKeywords-1`) or `-1` if `str` is not a
keyword. The list is a sorted array of `(offset, length)` pairs into a
single concatenated string buffer (the layout produced by
`gen_keywordlist.pl` at build time from `src/include/parser/kwlist.h`).
Lookup is binary search.

## Why this layout

Concatenated buffer + offset table avoids per-keyword pointer storage and
gives the binary search good cache locality — measured to matter for
parser throughput.

## Callers

- backend: `scan.l` (`yyextra->keywords`).
- `src/fe_utils/psqlscan.l` — same lookup, separate keyword list with
  the psql backslash-commands hidden.
- `src/interfaces/ecpg/preproc/pgc.l` — also shares the table.

## Related

- `src/include/common/kwlookup.h` — declarations.
- `src/include/parser/kwlist.h` — the canonical PG SQL keyword list,
  used by `gen_keywordlist.pl` to produce the concatenated buffer +
  category tables.
