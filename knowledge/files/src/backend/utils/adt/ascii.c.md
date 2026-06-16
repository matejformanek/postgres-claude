# `src/backend/utils/adt/ascii.c`

- **File:** `source/src/backend/utils/adt/ascii.c` (199 lines)
- **Header:** `source/src/include/utils/ascii.h`
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

SQL `to_ascii(text [, enc])` plus an internal `ascii_safe_strlcpy`.
Converts ISO-8859-1/2/15 and CP1250 bytes in the upper-128 range to a
best-effort ASCII letter (or `'?'`) via fixed lookup tables. Operates
**in-place** — the result is always the same length as the input.
(`ascii.c:96-112` [verified-by-code])

## Key functions

- `pg_to_ascii(src, src_end, dest, enc)` (`:28`) — fixed-table dispatch
  over four supported source encodings. Raises
  `ERRCODE_FEATURE_NOT_SUPPORTED` for anything else (`:75`).
- `to_ascii_encname` (`:118`), `to_ascii_enc` (`:137`),
  `to_ascii_default` (`:155`) — three SQL bindings differing only in how
  the encoding argument is supplied.
- `ascii_safe_strlcpy(dest, src, destsiz)` (`:173`) — postmaster-safe
  scrub of a string to printable-ASCII (or `\n\r\t`), replacing
  everything else with `'?'`. The comment is explicit: **must not
  trigger ereport(ERROR), as it is called in postmaster.**
  (`:170-171` [from-comment])

## Layout note

The lookup tables (e.g. `"  cL Y  \"Ca …"`) are hand-written
approximations of accented Latin chars → unaccented ASCII. They are
read-only constants.

## Phase D notes

- `chr(int)` — the constructive cousin — lives in `oracle_compat.c`,
  NOT here.
- `pg_to_ascii` is **encoding-restricted**: only PG_LATIN1, PG_LATIN2,
  PG_LATIN9, PG_WIN1250 (`:41-72`). Anything else (notably any
  multi-byte encoding) errors out. The in-place 1-byte-per-codepoint
  contract is what enforces that limitation.
- The function silently maps 128..range to `' '` (`:89-90`) without
  error — a "bogus" undocumented byte becomes a space.

## Potential issues

- [ISSUE-undocumented-invariant: `to_ascii` callers never see the raw
  byte for 128..159 in LATIN1/LATIN9 — they get a space, with no
  warning (maybe)]
- [ISSUE-info-disclosure: `ascii_safe_strlcpy` is called from the
  postmaster's signal-handler-adjacent path; a long src with no NUL
  could still walk to destsiz, but loop bounds via `--destsiz > 0`
  protect against runaway. No real concern. (maybe)]

## Cross-references

- `source/src/include/mb/pg_wchar.h` — `PG_LATIN1` etc.
- `source/src/backend/utils/adt/oracle_compat.c` — `chr()`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 1
