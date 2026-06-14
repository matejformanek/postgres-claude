---
path: src/interfaces/ecpg/include/pgtypes_date.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 32
depth: read
---

# `pgtypes_date.h` — client-side date type API

## Purpose
Defines the client `date` type (a `typedef long`) and the `PGTYPESdate_*` API:
construction, text in/out, Julian-day conversions, day-of-week, today, and
format-driven parse/print. [verified-by-code] Part of the standalone pgtypes
library.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `typedef long date` | pgtypes_date.h:9 | the client date type [verified-by-code] |
| `PGTYPESdate_new/_free` | pgtypes_date.h:16-17 | lifecycle [verified-by-code] |
| `PGTYPESdate_from_asc/_to_asc` | pgtypes_date.h:18-19 | text I/O [verified-by-code] |
| `PGTYPESdate_from_timestamp` | pgtypes_date.h:20 | down-cast from `timestamp` [verified-by-code] |
| `PGTYPESdate_julmdy/_mdyjul` | pgtypes_date.h:21-22 | Julian ⇄ m/d/y arrays [verified-by-code] |
| `PGTYPESdate_dayofweek/_today` | pgtypes_date.h:23-24 | [verified-by-code] |
| `PGTYPESdate_defmt_asc/_fmt_asc` | pgtypes_date.h:25-26 | format-driven parse / print [verified-by-code] |

## Invariants & gotchas
- **`date` is `long`** (pgtypes_date.h:9), whose width differs across platforms:
  64-bit on LP64 Unix, **32-bit on LLP64 Windows**. The on-the-wire/struct size
  of a `date` host variable thus varies by platform — a portability footgun for
  cross-platform data exchange. [verified-by-code] See `knowledge/issues/ecpg.md`.
- `PGTYPESdate_fmt_asc` writes into a caller-supplied `char *outbuf` with **no
  length argument** (pgtypes_date.h:26) — the caller must size for the worst
  case (the subsystem-wide unbounded-buffer theme). [verified-by-code]
- The include guard is misleadingly named `PGTYPES_DATETIME` (pgtypes_date.h:3),
  not `PGTYPES_DATE`. [verified-by-code]

## Cross-refs
- [[pgtypes.h]], [[pgtypes_timestamp.h]] — included here.
- [[pgtypes_error.h]] — `PGTYPES_DATE_*` failure codes.
- `knowledge/files/src/interfaces/ecpg/pgtypeslib/dt_common.c.md`.

## Potential issues
- **[ISSUE-portability: `date`/`interval.month` are `long`]** `pgtypes_date.h:9`
  (and `pgtypes_interval.h:22`) — `long`-typed fields change width LP64 vs LLP64
  (Win64), so the public `date`/`interval` ABI size is platform-dependent.
  Mirrored to `knowledge/issues/ecpg.md`.
