# `src/include/access/syncscan.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**29 lines.**

## Role

Coordination primitives for **synchronized sequential scans** — when
multiple backends seq-scan the same large relation concurrently, the
later scan starts where the earlier one currently is, so they share
buffer-cache hits. The mechanism is a small shared hash keyed by
relation, holding the most recent reported block location.
[verified-by-code] `source/src/include/access/syncscan.h:1-13`

## Public API

Two externs (lines 25-26):
- `ss_report_location(rel, location)` — current scanner publishes
  "I'm at block N" for `rel`.
- `ss_get_location(rel, relnblocks)` → `BlockNumber` — new scanner
  asks "where should I start?".

One conditionally-extern GUC: `trace_syncscan` (only when
`TRACE_SYNCSCAN` is `#define`d, line 22).

## Invariants

- `ss_get_location` returns a block in `[0, relnblocks)`. It clamps
  / wraps as needed (the seq-scan executor wraps around to 0 after
  the end and stops at the start block).
- The hash is best-effort: collisions on a shared bucket are silent —
  another rel's location may be returned. Since seq-scan wraps, the
  worst case is "started a bit late, scanned a bit more"; never
  incorrect results.
- The shared hash has fixed size (`SYNC_SCAN_NELEM` = 20 with
  `SS_CHE_HASH_SIZE` chains in `syncscan.c`). Beyond ~20 large rels
  being concurrently scanned, the cache starts evicting and the
  sync-scan optimization degrades.

## Notable internals

The hash and tranche live in shared memory; lookups are LWLock-free
on the read path (atomics + occasional under-lock update). The block
location is reported on every `SYNC_SCAN_REPORT_INTERVAL` (currently
128 blocks) rather than every block, to keep update traffic down.

## Trust-boundary / Phase D surface

**This is the Phase-D side-channel.** The shared hash makes one
backend's seq-scan position observable to other sessions on the same
cluster (even cross-database, since the hash key is `RelFileLocator`
including dboid). A low-privilege observer who:

1. Knows the relfilenode of a target relation in another database
   (discoverable via `pg_class.relfilenode` if the row is readable,
   or by educated guess), AND
2. Can call `ss_get_location` indirectly — i.e. start a seq-scan on
   ANY relation that happens to hash-collide into the same bucket,

can probe whether a high-privilege session is currently seq-scanning
some big table. Granularity: 128-block report interval, so they see
the other session's progress in 128-page steps (1 MB at 8 KB pages).

This is a **read-pattern leak**: no row contents leak, but presence
and rough progress of a concurrent large scan does. New echo for the
A11/A12/A14 "monitoring as extraction" theme.

Mitigations possible (but not implemented at this layer): per-role
hash partitioning, or just not publishing locations when the scan is
on a relation the asking role can't read.

## Cross-refs

- `src/backend/access/common/syncscan.c` — implementation,
  `SYNC_SCAN_NELEM`, `SS_CHE_HASH_SIZE`, `SYNC_SCAN_REPORT_INTERVAL`.
- `access/heapam.c` — `initscan` callers of `ss_get_location`.
- `storage/block.h` — `BlockNumber`.
- `utils/relcache.h` — `Relation`.
- `subsystems/access-heap.md` (if written) — heap seq-scan narrative.

## Issues

- **ISSUE-leak (Phase D)**: shared sync-scan hash is a cross-tenant
  observation channel. Not security-critical, but worth a register
  entry as a new echo of the monitoring-side-channel theme.
- **ISSUE-doc**: header doesn't mention the report interval or the
  hash size; both are operational tuning knobs.
