---
path: src/interfaces/ecpg/include/pgtypes_timestamp.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 31
depth: read
---

# `pgtypes_timestamp.h` — client-side timestamp type API

## Purpose
Defines the client `timestamp` / `TimestampTz` types (both `typedef int64`) and
the `PGTYPEStimestamp_*` API: text in/out, subtraction to an `interval`,
format-driven parse/print, current-time, and interval add/sub. [verified-by-code]
Part of the standalone pgtypes library.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `typedef int64 timestamp` / `TimestampTz` | pgtypes_timestamp.h:10-11 | microsecond int64 epoch [verified-by-code] |
| `PGTYPEStimestamp_from_asc/_to_asc` | pgtypes_timestamp.h:18-19 | text I/O [verified-by-code] |
| `PGTYPEStimestamp_sub` | pgtypes_timestamp.h:20 | ts − ts → interval [verified-by-code] |
| `PGTYPEStimestamp_fmt_asc/_defmt_asc` | pgtypes_timestamp.h:21,23 | format print / parse [verified-by-code] |
| `PGTYPEStimestamp_current` | pgtypes_timestamp.h:22 | now() [verified-by-code] |
| `PGTYPEStimestamp_add_interval/_sub_interval` | pgtypes_timestamp.h:24-25 | [verified-by-code] |

## Invariants & gotchas
- `int64` here comes transitively from [[pgtypes_interval.h]] (included at
  pgtypes_timestamp.h:8), which is where `int64` is typedef'd under `#ifndef
  C_H`. So `pgtypes_timestamp.h` cannot stand alone without the interval
  header. [verified-by-code]
- `PGTYPEStimestamp_fmt_asc` takes a length (`int str_len`,
  pgtypes_timestamp.h:21) — unlike its date/Informix siblings it is **bounded**.
  [verified-by-code]
- `timestamp` is always `int64` µs-since-2000 — there is no float-timestamp
  fork here (the legacy `HAVE_INT64_TIMESTAMP` is forced on; see
  [[pgtypes_interval.h]]). [verified-by-code]

## Cross-refs
- [[pgtypes_interval.h]] — defines `int64` + the `interval` struct used by `_sub`.
- [[pgtypes_date.h]] — `PGTYPESdate_from_timestamp` consumes this type.
- `knowledge/files/src/interfaces/ecpg/pgtypeslib/timestamp.c.md`.
