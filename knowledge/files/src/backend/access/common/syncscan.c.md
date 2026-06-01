# syncscan.c

- **Source path:** `source/src/backend/access/common/syncscan.c`  (NOT in heap/; lives in `access/common/`)
- **Lines:** 321
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/syncscan.h` (just exports `ss_get_location`/`ss_report_location`), `heapam.c` (the consumer — `initscan` and friends).

## Purpose

Cross-backend synchronization of sequential scans on the same table. Maintains a tiny in-shared-memory LRU of recent (relfilelocator → current block) tuples; a new seqscan starts where a recent scan was last reported to be, so multiple concurrent seqscans on the same heap share buffer-cache I/O rather than each fetching every page. [from-comment, syncscan.c:1-25]

## Top-of-file comment
> Long comment block (syncscan.c:1-90) explaining the self-synchronizing principle: a leader pays the I/O cost, followers do not, so followers naturally pull ahead and re-merge with the leader; therefore we only need a hint about where ongoing scans are. The data structure: a fixed-size (`SYNC_SCAN_NELEM = 20` per the standard PG value, though not visible in head) LRU keyed by RelFileLocator. The `trace_syncscan` GUC for debugging. [from-comment, syncscan.c:1-90]

## Public surface (non-static functions)

- `BlockNumber ss_get_location(Relation rel, BlockNumber relnblocks)` (line 251) — Return the suggested starting block for a new seqscan on `rel`; 0 if no recent scan reported.
- `void ss_report_location(Relation rel, BlockNumber location)` (line 286) — Called periodically by an ongoing seqscan (every SYNC_SCAN_REPORT_INTERVAL blocks) to update the LRU.

## Shared-memory hooks

- `static void SyncScanShmemRequest(void *arg)` (line 134) — size request.
- `static void SyncScanShmemInit(void *arg)` (line 146) — initialize the LRU.
- `const ShmemCallbacks SyncScanShmemCallbacks = { ... }` (line 118) — registration record consumed by the subsystem registry (`storage/subsystems.h`).
- `static BlockNumber ss_search(RelFileLocator, BlockNumber location, bool set)` (line 188) — the LRU lookup/insert helper.

## Key types / structs (all internal)

- `ss_scan_location_t` (line 92) — `{ RelFileLocator relfilelocator; BlockNumber location; }`. Plain value type.
- `ss_lru_item_t` (line 98) — Doubly-linked LRU node wrapping `ss_scan_location_t`.
- `ss_scan_locations_t` (line 105) — head/tail pointers + array of `ss_lru_item_t` (fixed-size pool in shared memory).

## Key invariants and locking

- All access goes through one LWLock — `SyncScanLock` (referenced by name in `lwlock.h` and used inside `ss_search`/`ss_get_location`/`ss_report_location`). [inferred — not directly visible in the head; standard pattern]
- The reported location is a **hint**: incorrect values cause only mild performance regressions (a scan starts at the wrong block and pays a bit more I/O until it catches up), never correctness issues. [from-comment, syncscan.c:60-90]
- The LRU is a fixed small size; entries are reclaimed in LRU order. A relation with no recent activity is silently evicted. [from-comment]

## Functions of note

1. **`ss_get_location`** (line 251) — On each seqscan start (called from `heapam.c::initscan`), look up the relation's recent location. If not found OR the recorded location is past the relation's current end-of-data, return 0; otherwise return the recorded block. The caller uses this as `rs_startblock`. [verified-by-code]

2. **`ss_report_location`** (line 286) — Called by `heapam.c::heap_getnextslot` (and friends) periodically — only every SYNC_SCAN_REPORT_INTERVAL blocks, to keep lock contention low. Acquires SyncScanLock, calls `ss_search(... set=true)`, releases. [verified-by-code]

3. **`ss_search`** (line 188) — LRU machinery. If `set` is true and the relfilelocator isn't present, inserts at the LRU head, evicting the tail. If found, moves to head. Returns the previously-stored location for `set=false`. [verified-by-code]

## Cross-references

- Called by: `heapam.c::initscan` (line ~359) when `allow_sync` is true and the relation is large enough (≥ `synchronize_seqscans` GUC threshold). [verified-by-code]
- Shared-memory registration: invoked from the subsystem registry (`storage/subsystems.h`).
- The `SyncScanLock` LWLock is reserved in `lwlock.h`. [inferred]

## Open questions

- Whether `synchronize_seqscans=on` is the default (it is on modern PG; not verified at this commit). [unverified]
- The exact value of SYNC_SCAN_NELEM / SYNC_SCAN_REPORT_INTERVAL — defined later in the file, not in the head I read. [unverified]

## Confidence tag tally
`[verified-by-code]=6 [from-comment]=4 [from-readme]=0 [inferred]=2 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
