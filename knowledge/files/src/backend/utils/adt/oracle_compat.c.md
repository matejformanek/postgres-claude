# `src/backend/utils/adt/oracle_compat.c`

- **File:** `source/src/backend/utils/adt/oracle_compat.c` (1182 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

Oracle-compatibility string builders that don't fit naturally in
`varlena.c`: case-folding (`lower`, `upper`, `initcap`, `casefold`),
padding (`lpad`, `rpad`), trimming (`btrim`, `ltrim`, `rtrim` plus
bytea variants), `translate`, `ascii`, `chr`. (`oracle_compat.c:1-32`)

## Functions and SQL bindings

- `lower` (`:48`), `upper` (`:79`), `initcap` (`:113`), `casefold`
  (`:129`) — delegate to `str_tolower` / `str_toupper` / `str_initcap`
  / `str_casefold` from `pg_locale.c`, which dispatch on the
  collation's provider.
- `lpad(string, len, fill)` (`:162`), `rpad(string, len, fill)` (`:260`)
  — multi-byte-aware padding. Length overflow guarded by
  `pg_mul_s32_overflow` + `AllocSizeIsValid` (`:200-206`) → error
  `"requested length too large"`.
- `dotrim` (`:394`), wrapper SQL fns `btrim` (`:358`), `ltrim` (`:378`),
  `rtrim`; bytea variants via `dobyteatrim`.
- `translate(string, from, to)` — character-by-character substitution
  with multi-byte support; allocates worst-case output length.
- `chr(int)` (`:1030`) — the Phase-D-interesting one (see below).
- `ascii(text) → int` (`:1145`) — first codepoint of a string.

## Phase D notes

### `chr(0)` (`:1030-1145`)

`chr(0)` is **explicitly rejected** with
`ERRCODE_PROGRAM_LIMIT_EXCEEDED` and message `"null character not
permitted"` (`:1046-1049` [verified-by-code]). Negative arg →
`"character number must be positive"`. The strict ASCII range (1-127)
is enforced for non-UTF8 multi-byte encodings; UTF-8 allows up to
U+10FFFF (`:1064-1068`). Result is validated via the encoding's own
verifier — meaning `chr()` cannot inject invalid bytes into the DB.

### `lpad` / `rpad` overflow

The bytelen computation (`:200-206`) uses three guards:
1. `pg_mul_s32_overflow(max_char_len, len)` — catches multiplication
   overflow.
2. `pg_add_s32_overflow(bytelen, VARHDRSZ)` — adds the header.
3. `AllocSizeIsValid(bytelen)` — caps at MaxAllocSize.

So an attacker passing `lpad('a', 2^30, 'x')` gets a clean error, not
a corrupted palloc.

### Length-bound discipline

Every output-allocating function computes worst-case bytes first,
errors on overflow, then pallocs. No "compute as we go" growing
buffers; consistent discipline.

### Case-folding

The actual transformation happens in `str_tolower` etc. in
`pg_locale.c`. For UTF-8 + ICU, this can grow the string slightly
(e.g. German ß → SS in upper) — handled by destination-buffer
double-allocation discipline in those routines.

## Potential issues

- [ISSUE-dos: `translate(string, from, to)` allocates worst-case
  output as `strlen(string) * max_char_len`. For a 1 GB input the
  intermediate may approach MaxAllocSize. Bounded but tight. (low)]
- [ISSUE-undocumented-invariant: `lpad/rpad` returning padded text
  uses `pg_mblen_unbounded` for the input (`:231`) — assumes input is
  valid; relies on database encoding-validity invariant. If a bug
  upstream let invalid UTF-8 through, this loop can over-read. (low)]
- [ISSUE-info-disclosure: error messages don't echo the input, good.
  The `chr` error path includes the requested codepoint
  (`:1067`) — acceptable; not user-controlled secret data. (low)]
- [ISSUE-correctness: `casefold` (`:129`) is the newer Unicode
  case-folding function (PG 17+); it depends on Unicode tables baked
  into the build. Behavior changes across Unicode versions could be
  surprising for user data persisted with old folds. (informational)]

## Cross-references

- `source/src/backend/utils/adt/pg_locale.c` — `str_tolower` etc.
- `source/src/backend/utils/adt/varlena.c` — overlapping
  string-builder helpers.
- `source/src/include/common/int.h` — `pg_mul_s32_overflow` etc.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 2
