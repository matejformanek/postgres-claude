---
path: src/interfaces/ecpg/compatlib/informix.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 1054
depth: deep
---

# `informix.c` — Informix ESQL/C compatibility shim (libcompat) over pgtypes

## Purpose
This is the entire implementation of the Informix ESQL/C compatibility
library (`libcompat` / `libecpg_compat`) for ecpg's INFORMIX mode. It
re-exports the Informix decimal (`dec*`), date (`r*date`, `rjulmdy`, …),
datetime (`dt*`), interval (`intoasc`), and misc (`rfmtlong`, `rupshift`,
`byleng`, `ldchar`, `rtyp*`) APIs as thin wrappers on top of the
`pgtypes` library (`PGTYPESnumeric_*`, `PGTYPESdate_*`,
`PGTYPEStimestamp_*`, `PGTYPESinterval_*`). The Informix `decimal` type is
treated as an alias-ish of the pgtypes `numeric` type, with conversion
through `PGTYPESnumeric_from_decimal` / `PGTYPESnumeric_to_decimal`
(`informix.c:63`, `informix.c:139`). Each wrapper translates pgtypes' errno
conventions (`PGTYPES_NUM_OVERFLOW`, `PGTYPES_DATE_BAD_DAY`, …) into Informix
`ECPG_INFORMIX_*` return codes so that Informix ESQL/C source compiles and
runs against ecpg unchanged.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `int decadd(decimal *, decimal *, decimal *sum)` | informix.c:151 | add; maps overflow/underflow errno → `ECPG_INFORMIX_NUM_*` |
| `int deccmp(decimal *, decimal *)` | informix.c:167 | compare via `deccall2` → `PGTYPESnumeric_cmp` |
| `void deccopy(decimal *src, decimal *target)` | informix.c:173 | raw `memcpy(sizeof(decimal))` |
| `int deccvasc(const char *cp, int len, decimal *np)` | informix.c:198 | ASCII → decimal; null/overflow/bad-numeric handling |
| `int deccvdbl(double, decimal *)` | informix.c:246 | double → decimal |
| `int deccvint(int, decimal *)` | informix.c:268 | int → decimal |
| `int deccvlong(long, decimal *)` | informix.c:290 | long → decimal |
| `int decdiv(decimal *, decimal *, decimal *)` | informix.c:312 | divide; maps DIVIDE_ZERO/OVERFLOW/UNDERFLOW |
| `int decmul(decimal *, decimal *, decimal *)` | informix.c:337 | multiply |
| `int decsub(decimal *, decimal *, decimal *)` | informix.c:359 | subtract |
| `int dectoasc(decimal *np, char *cp, int len, int right)` | informix.c:381 | decimal → ASCII into caller buffer (`len`-checked) |
| `int dectodbl(decimal *, double *)` | informix.c:432 | decimal → double |
| `int dectoint(decimal *, int *)` | informix.c:453 | decimal → int; overflow mapped |
| `int dectolong(decimal *, long *)` | informix.c:480 | decimal → long; overflow mapped |
| `int rdatestr(date, char *str)` | informix.c:508 | date → string into caller buffer (no len) |
| `int rstrdate(const char *, date *)` | informix.c:529 | string (`mm/dd/yyyy`) → date |
| `void rtoday(date *)` | informix.c:535 | today's date |
| `int rjulmdy(date, short *mdy)` | informix.c:541 | julian → m/d/y shorts |
| `int rdefmtdate(date *, const char *fmt, const char *str)` | informix.c:553 | formatted parse → date; errno→`ECPG_INFORMIX_*` |
| `int rfmtdate(date, const char *fmt, char *str)` | informix.c:579 | date → formatted string |
| `int rmdyjul(short *mdy, date *)` | informix.c:592 | m/d/y → julian |
| `int rdayofweek(date)` | informix.c:604 | day-of-week |
| `void dtcurrent(timestamp *)` | informix.c:612 | now |
| `int dtcvasc(char *str, timestamp *)` | informix.c:618 | ASCII → timestamp; extra-chars check |
| `int dtcvfmtasc(char *inbuf, char *fmtstr, timestamp *)` | informix.c:644 | formatted ASCII → timestamp |
| `int dtsub(timestamp *, timestamp *, interval *)` | informix.c:650 | timestamp diff |
| `int dttoasc(timestamp *, char *output)` | informix.c:656 | timestamp → ASCII into caller buffer (no len) |
| `int dttofmtasc(timestamp *, char *output, int str_len, char *fmtstr)` | informix.c:666 | formatted timestamp → ASCII (len-aware) |
| `int intoasc(interval *, char *str)` | informix.c:672 | interval → ASCII into caller buffer (no len) |
| `int rfmtlong(long, const char *fmt, char *outbuf)` | informix.c:768 | format long per Informix picture string |
| `void rupshift(char *str)` | informix.c:964 | in-place uppercase |
| `int byleng(char *str, int len)` | informix.c:972 | length minus trailing blanks |
| `void ldchar(char *src, int len, char *dest)` | informix.c:979 | copy stripping trailing blanks, NUL-terminate |
| `int rgetmsg(int, char *, int)` | informix.c:988 | stub, returns 0 |
| `int rtypalign(int, int)` | informix.c:997 | stub, returns 0 |
| `int rtypmsize(int, int)` | informix.c:1005 | stub, returns 0 |
| `int rtypwidth(int, int)` | informix.c:1013 | stub, returns 0 |
| `void ECPG_informix_set_var(int, void *, int)` | informix.c:1021 | forwards to `ECPGset_var` |
| `void *ECPG_informix_get_var(int)` | informix.c:1027 | forwards to `ECPGget_var` |
| `void ECPG_informix_reset_sqlca(void)` | informix.c:1033 | resets sqlca from local `sqlca_init` |
| `int rsetnull(int t, char *ptr)` | informix.c:1044 | forwards to `ECPGset_noind_null` |
| `int risnull(int t, const char *ptr)` | informix.c:1051 | forwards to `ECPGis_noind_null` |

## Internal landmarks
- **`deccall2` (informix.c:47)** — generic 2-arg wrapper: allocate two
  `numeric`, `PGTYPESnumeric_from_decimal` each, invoke the supplied
  `int (*)(numeric*, numeric*)` op pointer, free, return its result.
  Every alloc/convert failure path frees what was allocated and returns
  `ECPG_INFORMIX_OUT_OF_MEMORY` (`informix.c:54-75`).
- **`deccall3` (informix.c:85)** — generic 3-arg (binary op with result)
  wrapper. Two subtle invariants documented in comments: (1) it must NOT
  null the result up front because the result pointer may *alias* an
  argument (`informix.c:93-97`); (2) on success it `rsetnull`s the result
  then writes via `PGTYPESnumeric_to_decimal` (`informix.c:137-139`). The
  `dec{add,div,mul,sub}` functions wrap `deccall3` and post-translate
  `errno` → Informix codes.
- **`ecpg_strndup` (informix.c:178)** — local strndup (truncate to `len`,
  malloc `use_len+1`, sets `errno=ENOMEM` on failure). Used by `deccvasc`
  because `decimal_in`/`PGTYPESnumeric_from_asc` consumes the whole string.
- **errno-as-channel idiom** — pgtypes functions report via `errno`; each
  wrapper does `errno = 0;` before the call and reads it after
  (`decadd` informix.c:153, `rdefmtdate` informix.c:558, `intoasc`
  informix.c:676, etc.). This is the central translation mechanism.
- **`value` struct + `initValue` + `getRightMostDot` (informix.c:687-764)**
  — private state for `rfmtlong`. `initValue` decomposes a `long` into
  sign, digit count, and a malloc'd digit string `val_string`
  (informix.c:735). `rfmtlong` (informix.c:768) is the one genuinely
  complex routine: it walks the picture/format string right-to-left into a
  `temp` buffer, then reverses `temp` into `outbuf`.
- **Stubs** — `rgetmsg`, `rtypalign`, `rtypmsize`, `rtypwidth`
  (informix.c:988-1018) are unimplemented placeholders returning 0.

## Invariants & gotchas
- **decimal ≡ numeric bridge.** `decimal` is converted to/from pgtypes
  `numeric` for every arithmetic op; there is no native decimal math here.
  `PGTYPESnumeric_from_decimal` failing is treated as OOM
  (`informix.c:63`). [verified-by-code]
- **Result-aliasing rule in `deccall3`.** Do NOT null the result before
  the op runs — `result` can be the same storage as `arg1`/`arg2`
  (`informix.c:93-97`). Breaking this would corrupt an operand mid-op.
  [from-comment]
- **Negative/zero return conventions differ from native ecpg.** These
  functions return Informix `ECPG_INFORMIX_*` codes (often negative or
  specific positive values), not the libecpg conventions. Null inputs
  generally return 0 with the output set null via `rsetnull`
  (e.g. `deccall3` informix.c:97-98, `deccvint` informix.c:273-275).
  [verified-by-code]
- **`errno` must be reset before pgtypes calls.** Several callers rely on
  reading `errno` after the call; a stale errno would mis-map the error
  code. The `errno = 0` lines (informix.c:153, 214, 316, 341, 363, 468,
  495, 558, 581, 624, 676) are load-bearing. [verified-by-code]
- **`risnull`/`rsetnull` operate on the no-indicator null sentinel** via
  `ECPGis_noind_null` / `ECPGset_noind_null` (informix.c:1044-1054), not on
  SQL indicators. [verified-by-code]
- **Caller-owned output buffers, several with no length parameter.**
  `rdatestr` (informix.c:516), `dttoasc` (informix.c:660), and `intoasc`
  (informix.c:682) `strcpy` a pgtypes-produced string into a caller buffer
  with no size argument — bounds are the Informix-API contract, not
  checked here. See Potential issues. [verified-by-code]

## Cross-refs
- [[numeric.c]], [[datetime.c]], [[timestamp.c]], [[interval.c]], [[ecpg_informix.h]]

## Potential issues
- **[ISSUE-BUFFER: `rdatestr` unbounded `strcpy`]** `informix.c:516` —
  copies `PGTYPESdate_to_asc(d)` into caller `str` with no length bound.
  Output for a valid date is bounded/short, so practically safe, but it is
  a classic no-`len` Informix-contract copy; severity LOW. [verified-by-code]
- **[ISSUE-BUFFER: `dttoasc` unbounded `strcpy`]** `informix.c:660` —
  copies `PGTYPEStimestamp_to_asc(*ts)` into caller `output` with no length
  bound, and does not check `asctime` for NULL before `strcpy` (an OOM /
  conversion failure in `PGTYPEStimestamp_to_asc` would NULL-deref).
  Severity MEDIUM (NULL-deref on allocation failure; unbounded copy).
  [verified-by-code]
- **[ISSUE-BUFFER: `intoasc` unbounded `strcpy`]** `informix.c:682` —
  copies interval ASCII into caller `str` with no length bound (NULL is
  checked here, unlike `dttoasc`). Severity LOW. [verified-by-code]
- **[ISSUE-BUFFER: `rfmtlong` fixed-size temp vs format expansion]**
  `informix.c:787,944` — `temp` is malloc'd to `fmt_len + 1`, and the
  parse loop `strcat`s one char per format position writing the `'\0'`
  terminator defensively at `temp[fmt_len]` (informix.c:944). The output
  is reversed into caller `outbuf` (informix.c:948-954) with no length
  bound and no check that `temp` never exceeds `fmt_len` chars; the
  algorithm assumes one output char per format char. A format string whose
  expansion logic emits more than `fmt_len` chars (or an `outbuf` smaller
  than the format) would overflow. Severity MEDIUM — Informix-contract
  formatter, historically a hotspot; behavior is bounded by the format
  length but `outbuf` sizing is entirely the caller's responsibility.
  [verified-by-code]
- **[ISSUE-ROBUSTNESS: `getRightMostDot` int/size_t loop on empty string]**
  `informix.c:752-762` — `len` is `size_t`; `i = len - 1` with an empty
  string makes `i` start at -1 (it's `int`, so the loop guard `i >= 0`
  handles it), returning -1 correctly. No bug, but the `size_t`→`int`
  narrowing of `len` (informix.c:760 `return len - j - 1`) is fragile for
  very long format strings. Severity LOW. [inferred]
- **[ISSUE-STUB: `rgetmsg`/`rtypalign`/`rtypmsize`/`rtypwidth` are no-ops]**
  `informix.c:988-1018` — return 0 unconditionally. Informix code relying
  on `rtypalign`/`rtypmsize`/`rtypwidth` to compute struct layout will get
  wrong (zero) answers. Severity LOW (documented stubs, not a regression).
  [verified-by-code]
