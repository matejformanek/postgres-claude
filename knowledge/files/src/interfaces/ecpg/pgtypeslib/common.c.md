---
path: src/interfaces/ecpg/pgtypeslib/common.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 148
depth: deep
---

# `common.c` — shared allocation + format-substitution helpers for pgtypeslib

## Purpose
Small grab-bag of utility routines used across the ECPG `pgtypeslib` runtime
(the client-side date/time/numeric/interval library). It provides the
zero-filling allocator `pgtypes_alloc`, the `pgtypes_strdup` wrapper, the
public `PGTYPESchar_free`, and the workhorse `pgtypes_fmt_replace` — the
single-field format-string substitution primitive that the date/timestamp
`*_fmt_asc` formatters call to render one converted value into a caller-owned
output buffer while tracking remaining space. `[verified-by-code]`

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `pgtypes_alloc` | common.c:10 | `calloc(1L, size)`; return is zero-filled. Sets `errno = ENOMEM` on failure, returns NULL `[verified-by-code]` |
| `pgtypes_strdup` | common.c:20 | thin `strdup` wrapper; sets `errno = ENOMEM` on failure `[verified-by-code]` |
| `pgtypes_fmt_replace` | common.c:30 | substitute one converted value into `*output`, advancing pointer + decrementing `*pstr_len` `[verified-by-code]` |
| `PGTYPESchar_free` | common.c:145 | public (declared in `pgtypes.h`); plain `free(ptr)` — exists mostly so Windows callers free with the same CRT that allocated `[from-comment]` (comment common.c:143) |

`pgtypes_alloc` / `pgtypes_strdup` / `pgtypes_fmt_replace` are internal
(prototyped in `pgtypeslib_extern.h`). `PGTYPESchar_free` is the only
installed/public symbol here.

## Internal landmarks
`pgtypes_fmt_replace` (common.c:30) is a switch on `replace_type` (the
`PGTYPES_TYPE_*` constants from `pgtypeslib_extern.h`) over a
`union un_fmt_comb`:

- `PGTYPES_TYPE_NOTHING` (common.c:39) — no-op.
- String cases `STRING_CONSTANT` / `STRING_MALLOCED` (common.c:41) —
  `i = strlen(...)`; only copies when `i + 1 <= *pstr_len` so the trailing NUL
  fits (the `memcpy` copies `i + 1` bytes, common.c:47). On the malloced
  variant it `free()`s the source string after copying (common.c:51).
  Returns `-1` if it would not fit.
- `PGTYPES_TYPE_CHAR` (common.c:57) — writes one char + NUL, needs
  `*pstr_len >= 2`.
- Numeric cases (common.c:69–134) — `DOUBLE_NF`, `INT64`, `UINT`, and the
  zero/space-padded `UINT_*_LZ`/`UINT_2_LS` variants. Allocates a scratch
  buffer of `PGTYPES_FMT_NUM_MAX_DIGITS` (40) via `pgtypes_alloc`, formats with
  the matching `snprintf` format, checks `snprintf` truncation/error via
  `i < 0 || i >= PGTYPES_FMT_NUM_MAX_DIGITS`, then `strcpy`s into `*output`.

The "remaining space" bookkeeping is the load-bearing logic: callers pass
`pstr_len` by pointer and the function decrements it by the rendered length on
each successful substitution, advancing `*output` past what it wrote. There is
**no buffer growth** here — the function only ever checks fit and returns `-1`
(or `ENOMEM`) on overflow; buffer sizing is the caller's responsibility (the
`MAXDATELEN`-sized buffers in the `*_to_asc` / `*_fmt_asc` callers). `[inferred]`

## Invariants & gotchas
- Return-value convention is **inconsistent across cases**: `0` on success,
  `-1` on insufficient space, but `ENOMEM` (a positive errno, common.c:80 and
  common.c:113-path returns `-1`) on the allocation-failure path of the numeric
  branch. Callers must treat any non-zero as failure rather than testing `== -1`.
  `[verified-by-code]` (common.c:80)
- Numeric branch: after formatting, `*pstr_len -= i` happens *before* the
  `*pstr_len <= 0` check (common.c:119-129), so on the overflow path `*pstr_len`
  is left already decremented (negative) — the caller is expected to abandon the
  buffer on failure, not keep using the counter. `[verified-by-code]`
- String-constant vs string-malloced differ only in the trailing `free()`;
  passing a constant as `STRING_MALLOCED` would `free()` non-heap memory.
  `[inferred]`
- `pgtypes_alloc` zero-fills (it's `calloc`); callers rely on that for clean
  string buffers. `[verified-by-code]` (comment common.c:8)
- `PGTYPESchar_free` must be used by ECPG clients to free strings returned by
  the library, especially on Windows where allocator CRTs can differ.
  `[from-comment]`

## Cross-refs
- [[pgtypeslib_extern.h]] — defines `union un_fmt_comb`, the `PGTYPES_TYPE_*`
  constants, `PGTYPES_FMT_NUM_MAX_DIGITS`, and prototypes the internal helpers.
- [[dt.h]] — `MAXDATELEN` (the output buffer size callers allocate).
- [[dt_common.c]], [[timestamp.c]], [[interval.c]], [[numeric.c]] — primary
  callers of `pgtypes_fmt_replace` / `pgtypes_alloc`.

## Potential issues
The mixed `-1` / `ENOMEM` return discipline (common.c:80) is a latent footgun
for any caller that compares strictly against `-1`; not a bug in current
callers but worth a tag.
