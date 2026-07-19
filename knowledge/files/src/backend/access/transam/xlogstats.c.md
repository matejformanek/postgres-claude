# xlogstats.c

- **Source path:** `source/src/backend/access/transam/xlogstats.c`
- **Lines:** 96
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogstats.h`,
  `pg_waldump` (consumer), `contrib/pg_walinspect`.

## Purpose

Tiny utility module: per-record byte counting for tools that compute
WAL statistics. Compiles into both backend and front-end. [from-comment]
`xlogstats.c:3-4`.

## Top-of-file comment (verbatim)

```
xlogstats.c
    Functions for WAL Statistics
```
[verified-by-code] `xlogstats.c:3-4`.

## Public surface

- `XLogRecGetLen(record, *rec_len, *fpi_len)` — `xlogstats.c:22`
  [verified-by-code]
- `XLogRecStoreStats(XLogStats *stats, record)` — `xlogstats.c:54`
  [verified-by-code]

## Key types

- `XLogStats` — declared in `xlogstats.h`: per-rmgr counters
  `count[RM_MAX_ID+1]`, `rec_len[]`, `fpi_len[]`. Fed by
  `XLogRecStoreStats`.

## Key invariants and locking

1. **Front-end safe.** No backend-only headers; compiles for
   `pg_waldump`. [inferred] (not stated in file but the
   thin utility nature is consistent with the xlogreader.c pattern).

## Functions of note

### `XLogRecGetLen` — `xlogstats.c:22-…` [verified-by-code]

Splits a record's total size into "record" (non-FPI) bytes and FPI
bytes by walking the block headers.

### `XLogRecStoreStats` — `xlogstats.c:54-…` [verified-by-code]

Increments per-rmgr counters using `XLogRecGetLen`.

## Cross-references

- `contrib/pg_walinspect` and `pg_waldump` consume these helpers to
  produce the WAL-stats SRFs.

## Open questions

None.

## Confidence tag tally

- `[verified-by-code]`: 4
- `[from-comment]`: 1
- `[inferred]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)

- [subsystems/access-transam.md](../../../../../subsystems/access-transam.md)