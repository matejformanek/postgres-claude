# `utils/formatting.h` — to_char/to_date/to_number + case-conversion entry points

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/formatting.h`)

## Role

Thin (35-line) public header for `formatting.c` — Karel Zak's port of
Oracle's TO_CHAR / TO_DATE / TO_NUMBER. Also exports collation-aware
`str_tolower/toupper/initcap/casefold` and ASCII-only
`asc_tolower/toupper/initcap` (used in fast paths where collation is
irrelevant).

## Public API

- Collation-aware:
  `str_tolower(buff, nbytes, collid)`,
  `str_toupper(buff, nbytes, collid)`,
  `str_initcap(buff, nbytes, collid)`,
  `str_casefold(buff, nbytes, collid)` —
  `source/src/include/utils/formatting.h:21-24`.
- ASCII-only:
  `asc_tolower/toupper/initcap(buff, nbytes)` — `:26-28`.
- `parse_datetime(text *date_txt, text *fmt, Oid collid, bool strict,
   Oid *typid, int32 *typmod, int *tz, struct Node *escontext)` — `:30-32`.
- `datetime_format_has_tz(const char *fmt_str)` — `:33`.

## Invariants

- `nbytes` is the byte length of `buff`; the str_* functions allocate a
  fresh output buffer (size up to 3× input for full Unicode casemap).
  [inferred from pg_locale.h `UNICODE_CASEMAP_LEN = 3`]
- `collid` of `InvalidOid` means "use database default collation".
  [inferred from PG convention]
- `parse_datetime` returns a `Datum` of the type indicated by `*typid`,
  with `*typmod`/`*tz` filled in. `escontext` carries soft-error capture
  per the error-handling skill. [inferred from signature, `:30-32`]
- `strict == true` makes the parser reject inputs that have format-string
  characters the input doesn't match; `false` is permissive. [inferred]

## Notable internals

The header doesn't expose any of the internal format-code machinery — see
`src/backend/utils/adt/formatting.c`. Format string parsing is the
DoS-relevant part: every `99` / `9G99` / `MM` / `MON` token costs memory
to compile into the internal `FormatNode` array.

## Trust-boundary / Phase D surface

- **A7 echo**: `formatting.c`'s format-string compiler allocates a
  `FormatNode` per token; a `to_char` with a 50 MB format string compiles
  to ~600 MB of `FormatNode`s (12× expansion). Header is the API surface
  but the resource cap is enforced inside .c. The header exposes no
  per-call length cap. [ISSUE-resource: to_char/to_date format-string
  length has no header-documented cap; 12× compile expansion documented
  in A7 (confirmed)]
- `str_tolower(buff, nbytes, collid)` — `nbytes` is user-controlled (it's
  the length of the text Datum passed in by a SQL function call). The
  function eventually dispatches into `pg_strlower` (see pg_locale.h
  issue #1) without an intervening size cap. [ISSUE-resource: str_tolower
  / str_toupper / str_casefold pipe user-length straight through to
  pg_strlower with no cap (likely)]
- `parse_datetime` takes `text *fmt` — also user-controlled. Same
  format-string DoS as `to_char`. [ISSUE-resource: parse_datetime fmt
  length uncapped (likely)]
- ASCII variants (`asc_tolower` etc.) are not collation-aware but ALSO
  take unbounded `nbytes` — same shape, but the per-byte cost is lower.
  [ISSUE-resource: asc_* helpers also uncapped (maybe)]

## Cross-refs

- `knowledge/files/src/include/utils/pg_locale.h.md` — `str_*` dispatch
  into `pg_strlower` etc.
- `knowledge/files/src/include/utils/ascii.h.md` — ASCII validation
  used by `asc_*`.
- A7 (`pg_locale_icu` and `to_char` length-cap finding).

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-resource: `to_char` / `parse_datetime` accept unbounded format
   strings; ~12× compile expansion documented in A7 (confirmed)] —
   `source/src/include/utils/formatting.h:30`.
2. [ISSUE-resource: `str_tolower/upper/casefold` pipe caller `nbytes`
   to pg_strlower with no MaxAllocSize check (likely)] —
   `source/src/include/utils/formatting.h:21-24`.
3. [ISSUE-resource: ASCII helpers `asc_*` also uncapped (maybe)] —
   `source/src/include/utils/formatting.h:26-28`.
