# `src/backend/utils/adt/formatting.c`

- **File:** `source/src/backend/utils/adt/formatting.c` (6873 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

The `to_char()` / `to_date()` / `to_timestamp()` / `to_number()` family
— Oracle-compatible formatting and parsing of timestamps, intervals,
and numerics via picture strings like `'YYYY-MM-DD HH24:MI:SS'` or
`'999,990.00'`. (`formatting.c:1-58` [from-comment])

Three format domains:
- **DCH** (date/character/hour): timestamp/interval ↔ string.
- **NUM** (number): numeric/int/float ↔ string.
- **STD** (standard): subset enforced under `strict` parsing mode.

## Top-level layout

1. Keyword tables and `FormatNode` typedef (`:111-163`).
2. Localized month/day names (`:166-300`).
3. **Format picture cache** (`:352-408`).
4. The keyword index (~700 lines).
5. `parse_format` (`:1371`) — picture-string → `FormatNode[]`.
6. `DCH_to_char` / `DCH_from_char` — render and parse.
7. `NUM_processor` — numeric render/parse machinery.
8. SQL entry points at the end (`:3956`+).

## SQL entry points

- `timestamp_to_char` (`:3956`), `timestamptz_to_char` (`:3991`),
  `interval_to_char` (`:4031`).
- `to_timestamp` (`:4072`), `to_date` (`:4110`) — both call
  `do_to_timestamp` (`:4381`).
- `numeric_to_number` (`:6266`), `numeric_to_char` (`:6324`),
  `int4_to_char` (`:6451`), `int8_to_char` (`:6544`),
  `float4_to_char`, `float8_to_char`.

## Format picture cache (`:352-408`)

- `DCHCacheEntry` (`:382`): fixed-size buffer holding the parsed
  `FormatNode[]` for one picture string.
- `DCH_CACHE_SIZE` (`:374`) ≈ 2048 bytes minus overhead — pictures
  longer than this **bypass the cache and re-parse every call**
  (`:3910-3922`).
- `DCH_CACHE_ENTRIES = 20` (`:379`) — fixed-size LRU-by-age (`age`
  field + `DCHCounter`).
- Same structure for `NUMCacheEntry` (`:391-398`) with
  `NUM_CACHE_SIZE` derived from 1024 bytes.
- Caches are **process-global** (`static DCHCacheEntry *DCHCache[…]`,
  `:401`); persist across transactions, NOT across backend lifetimes
  (per-backend cache).

## The format parser — `parse_format` (`:1371`)

- Walks the picture string char-by-char, hashes each token via the
  `KeyWord_INDEX` table for fast keyword recognition, emits a
  `FormatNode` per logical unit.
- Output array is exactly `fmt_len + 1` nodes — one per input byte
  worst case. **No recursion**; the picture grammar is regular.
- Suffixes (`FM`, `TH`, `th`, `SP`) attach to preceding keywords.

## DCH_MAX_ITEM_SIZ and result allocation (`:103`)

- `DCH_MAX_ITEM_SIZ = 12` — bound on the maximum output bytes from a
  single keyword (e.g. localized day name).
- Result buffer is allocated as `palloc(mul_size(fmt_len,
  DCH_MAX_ITEM_SIZ) + 1)` (`:3907`) — uses `mul_size` which raises
  `ERRCODE_PROGRAM_LIMIT_EXCEEDED` on overflow before palloc. So:
  - Picture string of length L → result buffer of 12·L bytes.
  - L > MaxAllocSize/12 ≈ 89 MB → mul_size raises.
- Localized item caps (`:2666` and many others) — when reading from a
  format string, if `strlen(str) <= (n->key->len + TM_SUFFIX_LEN) *
  DCH_MAX_ITEM_SIZ` then error "localized string format value too long"
  (`:2671`).

## NUM_TOCHAR_prepare (`:6232`) — the numeric cap

```c
int len = VARSIZE_ANY_EXHDR(fmt);
if (len <= 0 || len >= (INT_MAX-VARHDRSZ)/NUM_MAX_ITEM_SIZ)
    PG_RETURN_TEXT_P(cstring_to_text(""));
result = palloc0((len * NUM_MAX_ITEM_SIZ) + 1 + VARHDRSZ);
```
- `NUM_MAX_ITEM_SIZ = 8`.
- A numeric picture longer than `INT_MAX/8` → silently returns `''`
  (no error). [verified-by-code]

## Phase D notes — the critical answers

### Q: Is there a format-string length cap?

**No explicit cap.** The text varlena limit (1 GB - VARHDRSZ) bounds
the input. After that:
- DCH: result palloc'd at `12 * fmt_len` via `mul_size` which raises
  on uint64 overflow, but **for fmt_len up to ~89 MB the multiplication
  is legal**, so a 50 MB format string forces a 600 MB output palloc.
- NUM: silently truncated to "" when `fmt_len >= INT_MAX/8`.

So the practical input cap is "whatever palloc can satisfy", which
under `work_mem` / no overall cap can be hundreds of MB.

### Q: Does it cap output size?

**No.** Output is `fmt_len * DCH_MAX_ITEM_SIZ` (or `NUM_MAX_ITEM_SIZ`),
and the `mul_size` guard at `:3907` only catches the **uint64 overflow
case** — not "this would exhaust shared_buffers." A 100 MB DCH format
string asks for ~1.2 GB result palloc which **will be rejected by
MaxAllocSize** (`mul_size` → ereport in `palloc`), so practically
output is capped at MaxAllocSize.

### Q: Recursion?

`parse_format` is iterative; `DCH_to_char` walks the FormatNode array
linearly. No recursion → no stack DoS via deeply nested patterns.
[verified-by-code]

### Q: Localization bombs?

Localized day/month names are looked up via `pg_strxfrm` / collation;
no untrusted-input pump (only the database's own locale data). The
"localized string format value too long" error (`:2671` and many) caps
input strings during from_char parsing.

### Q: Format-string injection?

`to_char` is widely used in user-facing SQL. Picture strings are
parsed safely; the keyword set is fixed. There's no way to escape
into shell or SQL via a picture string.

## Cache aging — possible cross-session info leak

The DCH/NUM caches are **per-backend**, NOT cross-connection. Each
forked backend has its own arrays. No info leak across users.
(`:401-407` [verified-by-code])

## Potential issues

- [ISSUE-dos: a 50 MB format-picture string in `to_char(ts,
  big_string)` forces a 600 MB palloc; `mul_size` overflow guard is
  only at uint64 boundary, not at a sensible byte limit. Should
  probably enforce `DCH_CACHE_SIZE * something` or a hard 64 KB cap.
  (medium)]
- [ISSUE-dos: same for NUM: `(INT_MAX-VARHDRSZ)/8` ≈ 256 MB picture
  is silently returned as empty string, but anything under that
  pallocs `8 * fmt_len`. (medium)]
- [ISSUE-correctness: NUM_TOCHAR_prepare's silent return of empty
  string on oversize picture (`:6236`) is surprising behavior; an
  error would be more honest. (low)]
- [ISSUE-undocumented-invariant: `DCH_CACHE_SIZE` is computed from a
  2048-byte budget per entry; if `sizeof(FormatNode)` grows (e.g. new
  fields), the cache shrinks silently. (low)]
- [ISSUE-stale-todo: TODO list at `:48-56` includes "use Assert()" and
  "add support for number spelling" — open since Karel's original
  commit. (informational)]

## Cross-references

- `source/src/backend/utils/adt/datetime.c` — `tm2timestamp`,
  `DetermineTimeZoneOffset`, `date2j`.
- `source/src/backend/utils/adt/numeric.c` — `numeric_int4_safe`,
  `numeric_out_sci`.
- `source/src/include/utils/pg_locale.h` — collation-aware case
  folding via `pg_locale_t`.
- `source/src/include/utils/datetime.h` — `pg_tm`, `fmt_tm`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 12
- `[from-comment]` × 4
- `[inferred]` × 1
