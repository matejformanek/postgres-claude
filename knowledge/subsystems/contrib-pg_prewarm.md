# contrib-pg_prewarm (load pages into the buffer cache)

- **Source path:** `source/contrib/pg_prewarm/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.2` (per `pg_prewarm.control`)
- **Trusted:** no (touches shared buffers + smgr directly)

## 1. Purpose

Load a relation's pages into PostgreSQL's shared buffer cache (or
OS page cache) on demand, plus an optional bgworker that persists
the cache contents at shutdown and reloads them at startup. Used
to amortize cold-cache latency after planned restarts and to
pre-stage data for benchmarks.

## 2. Mental model

- **Two top-level entry points.**
  - `pg_prewarm(relation, mode, fork, first_block, last_block)`
    — SQL function in `pg_prewarm.c`. Reads pages and returns the
    block count actually warmed.
  - **`autoprewarm`** bgworker — `autoprewarm.c`. Registered via
    `RegisterBackgroundWorker` from `_PG_init`. On normal shutdown
    it dumps the current shared-buffer pageref list to
    `autoprewarm.blocks` (under `$PGDATA`); on startup it reads
    that file and replays the warming.

- **Three modes for `pg_prewarm`** (defined in `pg_prewarm.c`):
  - `prefetch` — issues `PrefetchBuffer` calls; pages may land in
    the OS page cache but not in shared buffers.
  - `read` — calls `smgrread` directly into a temp buffer; warms
    the OS page cache only.
  - `buffer` — calls `ReadBufferExtended` to put pages into shared
    buffers. The most common choice.

- **Read streams.** Modern versions use `read_stream.h` (from
  `storage/read_stream.c`) for batched I/O — see the include in
  `pg_prewarm.c`.

## 3. Key files

- `pg_prewarm.c` — the SQL function (~250 LOC); mode dispatch and
  read-stream loop.
- `autoprewarm.c` — bgworker (~1000 LOC); shared-memory state,
  dump file format, postmaster registration.
- `pg_prewarm.control`, `pg_prewarm--1.0--1.1.sql` etc. — install
  + upgrade SQL.

## 4. Key data structures (autoprewarm)

- **`AutoPrewarmSharedState`** (in `autoprewarm.c`) — shmem-resident
  state: lock, dump-in-progress flag, last-dump time, signal flags
  for the leader → worker interaction.
- **`BlockInfoRecord`** — one row of the dump file: relfilenode
  components (db OID, tablespace OID, rel OID), fork number,
  block number. Sorted before warming so reads of adjacent blocks
  on the same relation cluster.

## 5. SQL surface

- `pg_prewarm(regclass, mode text DEFAULT 'buffer', fork text
  DEFAULT 'main', first_block int8 DEFAULT NULL, last_block int8
  DEFAULT NULL)` — returns `int8` (blocks warmed).
- `autoprewarm_start_worker()` — start the autoprewarm bgworker
  on demand (if not started by `_PG_init`).
- `autoprewarm_dump_now()` — force an immediate dump of the
  current buffer pageref list.

## 6. Invariants and gotchas

- **[INV-1]** `mode='buffer'` requires that the calling backend
  has a recovery-finished consistent state; the function uses
  `RelationGetSmgr` + `ReadBufferExtended`, both of which need
  shared buffers to be initialized.
- **[INV-2]** The autoprewarm bgworker registers with
  `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`
  flags and `BgWorkerStart_ConsistentState` — it can run on a
  standby (warming the standby's cache too).
- **[INV-3]** The `autoprewarm.blocks` dump file is in
  `$PGDATA` root — `pg_basebackup` includes it by default,
  which means a cloned standby starts with the primary's warmth
  baked in.
- The bgworker holds a shmem lock briefly while it scans the
  buffer pageref list — don't extend that hold without careful
  thought; it can stall buffer-pin contention probes.

## 7. Owners (as of 2026-06-12)

Historical author: Robert Haas (per `git log` author list).
Touched by Andres Freund (read-stream conversion), Thomas Munro
(modern I/O), various others.

## 8. Local reviewer reflexes

- Any change to `autoprewarm.c`'s dump format → bump a version
  marker; the dump file is persistent across restarts but not
  meant to survive cross-major-version upgrades.
- Any new mode for `pg_prewarm` → confirm function volatility
  is `volatile` (the function reads buffer state, not pure).
- Any addition that holds a shmem lock across `smgr*` calls
  → reject; same constraint as the existing main path.
- Concurrent autoprewarm workers must NOT exist — the function
  asserts that only one is running. Don't break that assertion.


## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**2 files.**

| File |
|---|
| [`contrib/pg_prewarm/autoprewarm.c`](../files/contrib/pg_prewarm/autoprewarm.c.md) |
| [`contrib/pg_prewarm/pg_prewarm.c`](../files/contrib/pg_prewarm/pg_prewarm.c.md) |

<!-- /files-owned:auto -->

## Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` — `autoprewarm.c` is a canonical static-registration bgworker example.
- `.claude/skills/extension-development/SKILL.md` — `_PG_init` `process_shared_preload_libraries_in_progress` guard.
- `knowledge/subsystems/storage-buffer.md` — `ReadBufferExtended` / `PrefetchBuffer` / buffer-pin semantics.
- `knowledge/files/contrib/pg_prewarm/autoprewarm.c.md` — per-file deep-dive (if present).
- `doc/src/sgml/pgprewarm.sgml` — user-facing reference.
