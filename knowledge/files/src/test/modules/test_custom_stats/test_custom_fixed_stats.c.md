---
path: src/test/modules/test_custom_stats/test_custom_fixed_stats.c
anchor_sha: e18b0cb7344
loc: 226
depth: read
---

# src/test/modules/test_custom_stats/test_custom_fixed_stats.c

## Purpose

Demonstrates the **fixed-amount** flavor of the custom-pgstats API
introduced for extensions to publish their own counters through the
cumulative statistics framework. Registers a `PgStat_KindInfo` with
`fixed_amount = true` (exactly one entry, no key) and wires the
`init_shmem` / `reset_all` / `snapshot` callbacks. Three SQL functions
let the regression suite update, reset, and read the single counter.
`[verified-by-code]` `test_custom_fixed_stats.c:48-60`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:72` | Registers the kind via `pgstat_register_kind`; only when `process_shared_preload_libraries_in_progress` |
| `test_custom_stats_fixed_update()` | `:155` | Bump `numcalls` under exclusive lock + changecount-write |
| `test_custom_stats_fixed_reset()` | `:179` | Calls `pgstat_reset_of_kind` |
| `test_custom_stats_fixed_report() returns (numcalls int8, stats_reset timestamptz)` | `:191` | Snapshot + return current counters with reset offset applied |
| Kind ID `PGSTAT_KIND_TEST_CUSTOM_FIXED_STATS = 26` | `:65` | Test-reserved custom kind id |

## Internal landmarks

- `PgStatShared_CustomFixedEntry` (`:35-41`) — wraps the real
  `PgStat_StatCustomFixedEntry` with an LWLock, a `changecount` (for
  lock-free reads via `pgstat_*_changecount_*`), and a `reset_offset`
  baseline used to compute "since last reset" counters.
- `init_shmem_cb` (`:88`) — initializes the LWLock under
  `LWTRANCHE_PGSTATS_DATA` (shared tranche reserved for pgstats).
- `reset_all_cb` (`:101`) — copies current stats into `reset_offset`
  using `pgstat_copy_changecounted_stats`, records the reset timestamp;
  follows the protocol documented above `PgStatShared_Archiver`
  (`[from-comment]` `:106`).
- `snapshot_cb` (`:121`) — copies current counters into the per-process
  snapshot, then under shared lock reads `reset_offset` and subtracts
  via a `FIXED_COMP` macro for each field. Demonstrates the standard
  "snapshot with reset offset" pattern.

## Invariants & gotchas

- TEST MODULE — must be loaded via `shared_preload_libraries`; loading
  any other way silently does nothing (`:75-77`).
- Kind ID 26 is hard-coded; in real extensions, IDs are allocated from a
  reserved range. Collisions with another custom kind on the same ID
  would crash at registration.
- The `fixed_amount = true` flag means the framework allocates one
  shared entry per cluster, accessed via `pgstat_get_custom_shmem_data`.
- Writers must wrap the modify with
  `pgstat_begin_changecount_write` / `pgstat_end_changecount_write`
  (`:164-166`) so concurrent snapshotters can detect torn reads.
- `write_to_file = true` (`:51`) means counters persist across restarts
  via the pgstats file at shutdown.

## Cross-refs

- `source/src/backend/utils/activity/pgstat.c` — registration + snapshot
  machinery.
- `source/src/include/utils/pgstat_internal.h` — `PgStat_KindInfo`,
  `pgstat_register_kind`, `pgstat_get_custom_shmem_data`,
  `pgstat_get_custom_snapshot_data`, the changecount helpers.
- `knowledge/files/src/test/modules/test_custom_stats/test_custom_var_stats.c.md`
  — variable-amount (keyed) sibling test.
