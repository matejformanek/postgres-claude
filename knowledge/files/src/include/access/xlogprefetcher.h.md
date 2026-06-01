# xlogprefetcher.h

- **Source path:** `source/src/include/access/xlogprefetcher.h`
- **Lines:** 52
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogprefetcher.c`, `xlogreader.h`.

## Purpose

Declarations for the recovery-side WAL prefetcher: a drop-in
replacement for `XLogReader` that issues async `PrefetchBuffer` calls
for blocks ahead of replay. [from-comment] `xlogprefetcher.h:3-4`.

## Top-of-file comment (verbatim)

```
xlogprefetcher.h
    Declarations for the recovery prefetching module.
```
[verified-by-code] `xlogprefetcher.h:3-4`.

## Key types

- `RecoveryPrefetchValue` enum — `RECOVERY_PREFETCH_OFF`, `_ON`, `_TRY`.
  [verified-by-code] `xlogprefetcher.h:24-29`.
- `XLogPrefetcher` — opaque (defined in `xlogprefetcher.c`).
  [verified-by-code] `xlogprefetcher.h:31-32`.

## Public surface

- GUC extern `recovery_prefetch`. [verified-by-code]
  `xlogprefetcher.h:21`.
- `XLogPrefetchReconfigure()`, `XLogPrefetchResetStats()` —
  GUC-change hooks. [verified-by-code] `xlogprefetcher.h:35-37`.
- `XLogPrefetcherAllocate(reader)`, `XLogPrefetcherFree(prefetcher)` —
  `xlogprefetcher.h:39-40` [verified-by-code]
- `XLogPrefetcherGetReader(prefetcher)` — `xlogprefetcher.h:42`
  [verified-by-code]
- `XLogPrefetcherBeginRead(prefetcher, recPtr)` — `xlogprefetcher.h:44`
  [verified-by-code]
- `XLogPrefetcherReadRecord(prefetcher, **errmsg)` —
  `xlogprefetcher.h:47` [verified-by-code]
- `XLogPrefetcherComputeStats(prefetcher)` — `xlogprefetcher.h:50`
  [verified-by-code]

## Cross-references

- `xlogprefetcher.c` is the implementation.
- `xlogrecovery.c` allocates and uses one prefetcher.

## Confidence tag tally

- `[verified-by-code]`: 9
- `[from-comment]`: 1
