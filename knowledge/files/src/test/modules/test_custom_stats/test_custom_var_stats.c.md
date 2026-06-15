---
path: src/test/modules/test_custom_stats/test_custom_var_stats.c
anchor_sha: e18b0cb7344
loc: 694
depth: read
---

# src/test/modules/test_custom_stats/test_custom_var_stats.c

## Purpose

Demonstrates the **variable-amount** flavor of the custom-pgstats API:
keyed entries, backend-local pending counters that flush to shared
memory, and the secondary-statistics-file mechanism for entries whose
data does not fit cleanly inside the shared stats record. Adds a
"description" string per stat that is stored in a named DSA and
serialized on shutdown to a side file `pg_stat/test_custom_var_stats_desc.stats`.
`[verified-by-code]` `test_custom_var_stats.c:108-122`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:129` | Registers the kind; preload only |
| `test_custom_stats_var_create(name text, description text)` | `:512` | Creates a shared entry under the hashed name; allocates description in DSA |
| `test_custom_stats_var_update(name text)` | `:571` | Increments the backend-local pending counter |
| `test_custom_stats_var_drop(name text)` | `:595` | Drops the entry; requests GC if refs still held |
| `test_custom_stats_var_report(name text) returns (name, numcalls, description)` | `:616` | SRF returning at most one row |
| Kind ID `PGSTAT_KIND_TEST_CUSTOM_VAR_STATS = 25` | `:38` | Test-reserved id |

## Internal landmarks

- `PgStatShared_CustomVarEntry` (`:60-65`) — has the standard
  `PgStatShared_Common` header, the counter, and a `dsa_pointer
  description`. The DSA is named (`"test_custom_stat_dsa"`) and obtained
  via `GetNamedDSA`.
- `PGSTAT_CUSTOM_VAR_STATS_IDX(name)` (`:46`) — `hash_bytes_extended` of
  the name; used as the `objid` in the standard `(kind, dboid, objid)`
  key triple. `dboid` is always `InvalidOid` because the kind is
  `accessed_across_databases = true` (`:113`).
- `flush_pending_cb` (`:154`) — adds the backend's pending counter into
  the shared entry under `pgstat_lock_entry`; returns false on
  `nowait`-lock failure, letting pgstat retry later.
- `to_serialized_data` (`:194`) — writes a magic number + offset to the
  main stats file; writes `(key, len, description)` triple to the
  secondary file. The main file's offset value is what later allows
  reload to seek into the secondary file `[from-comment]` `:181-192`.
- `from_serialized_data` (`:279`) — reverse path: reads magic, validates
  it equals `TEST_CUSTOM_VAR_MAGIC_NUMBER`, reads offset, opens
  secondary file, seeks, reads + validates key, then reads description
  into a fresh DSA allocation.
- `finish` (`:408`) — three operations: `STATS_WRITE` closes the file
  and unlinks on ferror; `STATS_READ` closes + unlinks (the file is
  consumed exactly once at startup); `STATS_DISCARD` unconditional unlink.

## Invariants & gotchas

- TEST MODULE — must be loaded via `shared_preload_libraries`.
- Hash collisions on the name → same entry. The test does not detect or
  warn about collisions; `pgstat_get_entry_ref_locked(create=true)` will
  silently reuse an existing entry, overwriting its description
  (`:545-557`).
- Magic-number check on reload allows the framework to refuse partial
  data when the secondary file is corrupt or absent.
- The secondary file is **deleted after read** (`STATS_READ` branch at
  `:439-446`) — startup is destructive; if reload fails midway, the
  remaining data is unrecoverable.
- Name length capped at `NAMEDATALEN-1` (`:524-528`) so the typed
  parameter mirrors normal PG identifier semantics, even though the
  storage is keyed by hash.

## Cross-refs

- `source/src/backend/utils/activity/pgstat.c` — kind registration and
  the standard `flush_pending_cb` / serialization protocol.
- `source/src/include/utils/pgstat_internal.h` — `PgStat_KindInfo`,
  `pgstat_fetch_entry`, `pgstat_prep_pending_entry`,
  `pgstat_get_entry_ref{,_locked}`, `pgstat_drop_entry`, the
  `pgstat_write_chunk{,_s}` / `pgstat_read_chunk{,_s}` helpers, the
  `PgStat_StatsFileOp` enum.
- `knowledge/files/src/test/modules/test_custom_stats/test_custom_fixed_stats.c.md`
  — fixed-amount sibling.
