# xlogstats.h

- **Source path:** `source/src/include/access/xlogstats.h`
- **Lines:** 43
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogstats.c`, `pg_waldump`, `pg_walinspect`.

## Purpose

Per-rmgr, per-info counter struct for WAL statistics.

## Top-of-file comment (verbatim)

```
xlogstats.h
    Definitions for WAL Statistics
```
[verified-by-code] `xlogstats.h:3-4`.

## Key types / constants

- `MAX_XLINFO_TYPES = 16` — the four-bit rmgr info field gives at most
  16 sub-record types. [verified-by-code] `xlogstats.h:19`.
- `XLogRecStats { uint64 count; uint64 rec_len; uint64 fpi_len; }` —
  per-bucket. [verified-by-code] `xlogstats.h:21-26`.
- `XLogStats` — `{ uint64 count; [FRONTEND-only XLogRecPtr
  startptr/endptr]; XLogRecStats rmgr_stats[RM_MAX_ID + 1];
  XLogRecStats record_stats[RM_MAX_ID + 1][MAX_XLINFO_TYPES]; }`.
  [verified-by-code] `xlogstats.h:28-37`.

## Public surface

- `XLogRecGetLen(record, *rec_len, *fpi_len)` — `xlogstats.h:39`
  [verified-by-code]
- `XLogRecStoreStats(*stats, record)` — `xlogstats.h:41` [verified-by-code]

## Cross-references

- `xlogstats.c` is the implementation.

## Confidence tag tally

- `[verified-by-code]`: 5
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
