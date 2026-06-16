---
path: src/interfaces/ecpg/pgtypeslib/interval.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 1091
depth: deep
---

# `interval.c` — client-side (ECPG/pgtypeslib) `interval` parse/encode + ctor/dtor

## Purpose
Implements the `PGTYPESinterval_*` client API for ECPG's standalone `interval`
type: parse a textual interval into the binary `interval` struct
(`from_asc`), render the struct back to text (`to_asc`), and the
new/free/copy lifecycle helpers. The heavy lifting (`DecodeInterval`,
`DecodeISO8601Interval`, `EncodeInterval` and their `Adjust*`/`Add*IntPart`
helpers) is **copy&pasted from the backend's `utils/adt/datetime.c`** and
adapted: `struct pg_tm` → `struct tm`, the `range` parameter and
`IntervalStyle` global are stubbed to local constants since ECPG lacks the
backend's GUC machinery `[from-comment]` (interval.c:15-18, 311-325, 327-331).

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `int DecodeInterval(char **field, int *ftype, int nf, int *dtype, struct tm *tm, fsec_t *fsec)` | interval.c:326 | Non-`static` (linked across pgtypeslib); `range`/`IntervalStyle` hardcoded locally `[verified-by-code]` |
| `void EncodeInterval(struct tm *tm, fsec_t fsec, int style, char *str)` | interval.c:760 | Renders into caller `str`; style switch SQL_STANDARD/ISO_8601/POSTGRES/VERBOSE `[verified-by-code]` |
| `interval *PGTYPESinterval_new(void)` | interval.c:989 | `pgtypes_alloc(sizeof(interval))`; may return NULL on OOM `[verified-by-code]` |
| `void PGTYPESinterval_free(interval *intvl)` | interval.c:999 | Bare `free()` `[verified-by-code]` |
| `interval *PGTYPESinterval_from_asc(char *str, char **endptr)` | interval.c:1005 | Parse text → struct; sets `errno`, returns NULL on error `[verified-by-code]` |
| `char *PGTYPESinterval_to_asc(interval *span)` | interval.c:1064 | Returns `pgtypes_strdup` buffer; VERBOSE style hardcoded `[verified-by-code]` |
| `int PGTYPESinterval_copy(interval *intvlsrc, interval *intvldest)` | interval.c:1084 | Field-by-field copy of `time`+`month`; always returns 0 `[verified-by-code]` |

`DecodeISO8601Interval` (interval.c:111) is `static` here per the porting
comment (interval.c:108-110) — in the backend it is exported `[from-comment]`.

## Internal landmarks
- **Field-accumulation parse:** `DecodeInterval` walks `field[]`/`ftype[]`
  *backwards* (interval.c:347) so unit suffixes are seen before bare values,
  switching on `DTK_TIME/DTK_TZ/DTK_DATE/DTK_NUMBER/DTK_STRING/DTK_SPECIAL`
  and accumulating into `tm` fields + `*fsec` (interval.c:349-594).
- **Fractional carry helpers:** `AdjustFractSeconds` / `AdjustFractDays`
  spread a fractional field into seconds/days+fsec via `rint` (interval.c:19-50).
- **ISO-8601 path:** `DecodeISO8601Interval` parses `P…T…` duration strings,
  including the 8-digit / 6-digit "basic format" special cases
  (interval.c:174-185, 257-264).
- **month/day/time split:** the binary `interval` is `{int32 month; int64 time}`.
  `tm2interval` packs year*12+mon into `month` and the day/hour/min/sec/fsec
  chain into `time` (usec) (interval.c:974-987); `interval2tm` reverses it
  (interval.c:944-972).
- **Encode styles:** four output dialects in `EncodeInterval`'s switch
  (interval.c:779-936); `to_asc` always picks VERBOSE (interval.c:1071).
- **from_asc flow:** `ParseDateTime` → try `DecodeInterval`, else
  `DecodeISO8601Interval`; then `tm2interval` (interval.c:1034-1058).

## Invariants & gotchas
- **Doc-drift risk (the central one):** every Decode/Encode/Adjust/Add routine
  is a verbatim fork of `source/src/backend/utils/adt/datetime.c`
  `[from-comment]` (interval.c:16, 35, 52, 89, 105, 312, 679, 699, 722, 732,
  755). When upstream `datetime.c` fixes interval handling, this copy does
  **not** track automatically and silently diverges. Treat any change to
  backend interval parse/encode as a candidate for mirroring here.
- **`fsec` normalization:** after decode, fractional seconds ≥ 1 sec are
  carried into `tm_sec` so `*fsec` stays sub-second (interval.c:600-608)
  `[verified-by-code]`.
- **`free` contract asymmetry:** `from_asc`/`to_asc` allocate via
  `pgtypes_alloc`/`pgtypes_strdup`, but `PGTYPESinterval_free` is a plain
  `free()` (interval.c:1002). Callers must not mix allocators; the struct
  must come from this library. `[verified-by-code]`
- **errno protocol:** error paths set `errno = PGTYPES_INTVL_BAD_INTERVAL` and
  return NULL; success sets `errno = 0` (interval.c:1030, 1038, 1048, 1055,
  1060) `[verified-by-code]`. `DecodeInterval` itself returns `DTERR_*` codes,
  not errno (interval.c:438, 447, 555, 592, 598).
- **`int64` time arithmetic:** `tm2interval` builds `time` with explicit
  `INT64CONST(24/60/60)` factors to force 64-bit multiply (interval.c:981-984)
  `[verified-by-code]`.
- **Length guard:** `from_asc` rejects `strlen(str) > MAXDATELEN` up front
  (interval.c:1028) but the scratch `lowstr` is `MAXDATELEN + MAXDATEFIELDS`
  (interval.c:1016) `[verified-by-code]`.

## Cross-refs
- [[dt_common.c]], [[datetime.c]], [[timestamp.c]]

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-overflow: month packing unchecked in DecodeInterval]**
  `interval.c:486` (and siblings 500-552) — `tm->tm_*` accumulation via `+=`
  with `int`-typed fields has no overflow check during decode; only the final
  `tm2interval` guards `month` via a `double` comparison (interval.c:977-979).
  `span->time` packing (interval.c:981-984) is **never** range-checked, so a
  large day/hour count can silently overflow the int64 usec product. The
  backend equivalent has had overflow hardening added over time; this fork may
  lag. Severity: low-moderate (client-side, attacker would need to feed a long
  literal that passes the `MAXDATELEN` gate). `[inferred]` — needs a diff vs
  current backend `tm2interval`/`DecodeInterval` to confirm drift.
- **[ISSUE-robustness: `strtoint` errno not reset on years-months branch]**
  `interval.c:445-446` — after the first `strtoint` (interval.c:436), the
  `val2 = strtoint(cp + 1, …)` path checks `errno == ERANGE` (interval.c:446)
  without an intervening `errno = 0`, so a stale `ERANGE` from an unrelated
  prior libc call could be observed. Low severity; mirrors backend pattern so
  may be intentional. `[inferred]`
