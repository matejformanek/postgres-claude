# `src/backend/utils/adt/varlena.c`

- **File:** `source/src/backend/utils/adt/varlena.c` (5814 lines)
- **Header:** `source/src/include/utils/varlena.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Functions for variable-length built-in types — **`text`, `bytea`, the
varlena infrastructure they sit on, plus the type-NAME and BpChar
sortsupport entry points**. Also: the BMH substring-search engine,
`split_part`/`string_agg`/`regexp_*` building blocks, MD5/SHA wrappers,
and a swath of misc text operators. (`varlena.c:1-13`)

The file is split into roughly four concerns:
1. `cstring ↔ text` conversion (`:184-275`) — the C interop layer.
2. Text I/O fmgr functions (`textin/out/recv/send`, etc., `:277-…`).
3. The **BMH substring search** (`text_position_*`, `:916-1355`).
4. The **SortSupport / abbreviated-key machinery** for text-like types
   (`:1647-2270`), which is the longest and most subtle part.

## `text`, `bytea`, etc. — physical layout

These are all `varlena` subtypes — pointers to a header (1-byte short or
4-byte long varlena header) followed by raw bytes. Macros like
`VARDATA_ANY(p)`, `VARSIZE_ANY_EXHDR(p)`, `VARSIZE_ANY(p)`, `PG_GETARG_TEXT_PP`
hide the short/long/compressed/external distinction. **TOAST helpers**
(`access/detoast.h`, `access/toast_compression.h`) are imported at the
top of the file (`:20-21`) so that any datum reaching the per-type
functions is detoasted-as-needed.

## cstring ↔ text helpers

- `cstring_to_text(s)` (`:184`) / `cstring_to_text_with_len(s, len)`
  (`:196`) — palloc a text, copy in, set varlena header.
- `text_to_cstring(t)` (`:217`) — palloc + memcpy + NUL-terminate. NOT
  in-place; caller-owned.
- `text_to_cstring_buffer(src, dst, dst_len)` (`:248`) — fixed-buffer
  copy. Truncates if too long.

These are the **canonical C-side text-handling idioms** used throughout
the backend (e.g. by ereport message construction, GUC parsing, etc.).

## Text I/O

- `textin` (`:278`) — variable-length encoding of input string; just
  wraps `cstring_to_text`.
- `textout` (`:289`).
- `textrecv` (`:300`) / `textsend` (`:318`) — binary protocol.

## BMH substring search (`text_position_*`)

Boyer-Moore-Horspool implementation in
`TextPositionState` (`:52-83`). Used by `position(substr IN str)`,
`strpos`, `replace`, `split_part`, etc. The 256-byte `skiptable[]` is
indexed via `skiptablemask` AND of a possibly-multibyte char's first
byte (`:64-65`). Handles **non-deterministic collations** via the
explicit `last_match_len` because match length can differ from needle
length (`:67-73` [from-comment]). API:
- `text_position_setup(t1, t2, collid, state)` (`:962`).
- `text_position_next(state)` (`:1083`) — returns true if found,
  match accessed via `text_position_get_match_ptr` / `…_pos`.
- `text_position_reset` (`:1311`), `text_position_cleanup` (`:1319`).

For **deterministic-C-locale**, the inner loop falls into
`text_position_next_internal` (`:1150`). With multibyte chars,
character-offset reporting is amortized via the `refpoint`/`refpos`
cache (`:75-82` [from-comment]).

## SortSupport / abbreviated keys (the load-bearing part)

`bttextcmp(PG_FUNCTION_ARGS)` (`:1632`) — the legacy
`BTORDER_PROC`. `bttextsortsupport(PG_FUNCTION_ARGS)` (`:1647`) — the
`BTSORTSUPPORT_PROC`, calls into the workhorse
**`varstr_sortsupport(ssup, typid, collid)`** (`:1672-1802`):

1. `pg_newlocale_from_collation(collid)` → determines whether we're in
   C locale (`collate_is_c`).
2. **C locale path**: install `varstrfastcmp_c` (`:1808`) — pure
   `memcmp` then length tiebreak. BpChar uses `bpcharfastcmp_c` (handles
   trailing-space ignorance), NAME uses `namefastcmp_c`.
3. **Locale path**: install `varlenafastcmp_locale` (`:1890`) — uses
   `strcoll_l` (via the pg_locale abstraction). NAME → `namefastcmp_locale`.
4. **Abbreviation eligibility** is gated by `pg_strxfrm_enabled(locale)`
   (`:1739-1741`). Comment is explicit: "Unfortunately, it seems that
   abbreviation for non-C collations is broken on many common platforms…
   macOS's strxfrm() implementation is known to not effectively
   concentrate a significant amount of entropy from the original string
   in earlier transformed blobs." (`:1726-1741` [from-comment]).
5. NAME type **does not support abbreviation at all** (`:1703-1704,
   1719-1720` — "Not supporting abbreviation with type NAME, for now").
6. If abbreviation is in play:
   - **Comparator becomes `ssup_datum_unsigned_cmp`** (`:1797`) — one of
     the radix-sort-eligible comparators in
     `sortsupport.h:275-277`. Text gets radix sort automatically.
   - `abbrev_full_comparator = original comparator`,
     `abbrev_converter = varstr_abbrev_convert`,
     `abbrev_abort = varstr_abbrev_abort`.
   - `prop_card = 0.20`, HyperLogLog cardinality estimators
     (`abbr_card`, `full_card`) — `:1793-1795`.

### `varstr_abbrev_convert` (`:2035`)

The abbreviation algorithm in essence:
1. For C locale: directly take the leading bytes of the string.
2. For locale-aware: run `strxfrm` (or `pg_strnxfrm`) into a buffer to
   get a transformed binary blob whose `memcmp` order matches the
   collation order — then take the leading 8 bytes.
3. Pack into a Datum, **big-endian-ize** (so `unsigned_cmp` produces
   collation order on little-endian boxes too — uses `pg_bswap`).

### `varstr_abbrev_abort` (`:2202`)

Uses HyperLogLog to estimate how many **distinct** abbreviated keys
we've seen vs **distinct** full keys. If `abbr_card < prop_card *
full_card`, the abbreviations aren't distinguishing values well → return
true. This is the cost-model decision: pay the strxfrm cost only if it
saves comparisons.

### `VarStringSortSupport` (`:85-102`)

Two reusable scratch buffers (`buf1`, `buf2`) so per-comparison
allocations are amortized across the sort. `cache_blob` flag toggles
between "buf2 holds a strxfrm() output" (abbreviation phase) and "buf2
holds a copy of the second string" (comparison-caching phase) — the
comment at `:1768-1781` explains why this flip is needed.

## TOAST interaction

This file is the busiest non-toast-mgmt consumer of TOAST helpers:
- `pg_detoast_datum`, `pg_detoast_datum_slice`, `pg_detoast_datum_packed`
  — used implicitly via the `PG_GETARG_TEXT_*` macros.
- Functions like `text_substring` (`:1428`+) call `toast_raw_datum_size`
  and `heap_tuple_untoast_attr_slice` to pull only the requested slice
  out of a large TOAST'd value — important for performance on big
  documents.
- `bytea_substring`, `bytea_overlay`, etc., follow the same pattern.

## Other notable contents

- `varstr_levenshtein` family — edit distance (drives `levenshtein()` in
  fuzzystrmatch when in core path).
- `replace_text`, `split_part`, `string_to_array`, `array_to_string`.
- `text_overlay`, `text_substring` (`:1428`, `:1483`).
- `md5_text`, `md5_bytea` family.
- `sha224/256/384/512` for `bytea`.
- `concat`, `concat_ws` — the `||` operator path is `textcat`.
- `pg_column_size`, `pg_column_compression`, `pg_column_toast_chunk_id` —
  introspection over TOASTed columns.

## Cross-references

- `source/src/include/utils/varlena.h` — declarations.
- `source/src/backend/access/common/detoast.c`,
  `source/src/backend/access/common/toast_compression.c` — TOAST.
- `source/src/backend/utils/sort/sortsupport.c` — `SortSupport`
  framework; `ssup_datum_unsigned_cmp` is consumed here.
- `source/src/include/utils/pg_locale.h` — `pg_locale_t`,
  `pg_strxfrm`/`pg_strxfrm_enabled`.
- `source/src/backend/utils/adt/like.c` — LIKE/ILIKE on text uses pieces
  here (e.g. byte-position helpers).

## Open questions

- The exact pg_strxfrm_enabled() decision tree per platform / ICU vs
  libc — partly delegated to pg_locale.c. [unverified, not chased.]
- How `varstrfastcmp_locale`'s comparison cache interacts with sort
  passes that interleave compare and convert — comment at `:1772-1781`
  hints it's correctness-relevant but I didn't verify the cache flush
  points.
- Whether any non-text varlena types (e.g. `bytea`) reuse the
  abbreviated-key infrastructure here — `byteacmp` is its own thing.

## Confidence tag tally

- `[verified-by-code]` × ~10
- `[from-comment]` × ~10
- `[unverified]` × 3
