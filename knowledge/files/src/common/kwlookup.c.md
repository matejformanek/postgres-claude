# src/common/kwlookup.c

## Purpose

The actual `ScanKeywordLookup` implementation: case-insensitive
perfect-hash lookup against any `ScanKeywordList`.

## Role in PG

Shared **frontend + backend**. Called by every PG flex scanner
(SQL, plpgsql, ecpg) for each identifier. Lives in `src/common/`
(not `src/backend/parser/`) precisely so frontend tools can link it.
The parser/README explicitly points here. `[from-README]`
`source/src/backend/parser/README:33-35`

## Key functions

- `int ScanKeywordLookup(const char *str, const ScanKeywordList
  *keywords)` — early reject by length (`len > max_kw_len`), then
  call the perfect-hash function `keywords->hash(str, len)`, range
  check `0 <= h < num_keywords`, then char-by-char compare with a
  deliberately ASCII-only A-Z→a-z downcasing.
  (`kwlookup.c:37-85`)

## State / globals

None — pure function.

## Callers

- backend: `src/backend/parser/scan.l` (`yyextra->keywords`).
- `src/fe_utils/psqlscan.l` — same lookup, separate keyword list
  that hides psql backslash commands from the SQL keyword space.
- `src/interfaces/ecpg/preproc/pgc.l` — also shares the table.

## Phase D notes

- The ASCII-only downcasing is intentional (`kwlookup.c:30-35`):
  SQL99 mandates that keywords match this way regardless of locale,
  to avoid the classic "Turkish I" misfold (where `tolower('I')`
  returns dotless ı). A non-keyword `I`-identifier still goes
  through different normalization elsewhere.
  `[verified-by-code]`
- The hash is a perfect hash over the keyword set; arbitrary input
  is range-checked at `kwlookup.c:61-62` before indexing into the
  keyword pool, so a junk input can't read OOB.
- `len > max_kw_len` early-out at `kwlookup.c:50-51` bounds the work
  done per identifier; DoS via long identifiers is bounded by
  whatever the upstream lexer accepts (NAMEDATALEN).

## Potential issues

None — bounded, read-only, deterministic.
