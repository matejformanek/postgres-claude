# contrib-pg_stat_statements (query execution statistics)

- **Source path:** `source/contrib/pg_stat_statements/`
- **Last verified commit:** `e18b0cb7344` (2026-06-12 anchor)
- **Extension version:** `1.13` (per `pg_stat_statements.control`)
- **Trusted:** no (uses shared memory + LWLock + spinlock; requires
  `shared_preload_libraries = 'pg_stat_statements'`)
- **Main file:** `pg_stat_statements.c` (~2900 LOC)

## 1. Purpose

Track planning and execution statistics for every distinct SQL
statement run on the server. Normalizes constants into `$N`
placeholders so semantically-equivalent queries collapse into one
bucket. The canonical "what's slow?" tool — most monitoring stacks
depend on it.

## 2. Mental model

- **A shared hashtable of `pgssEntry` rows.** Capacity is set at
  postmaster startup via `pg_stat_statements.max` (default
  5000); allocated in shmem from `_PG_init`. Entries are evicted
  LRU when the table fills.
- **Query strings live in an external file**, not in shmem.
  Each entry stores a (offset, length) into
  `$PGDATA/pg_stat_tmp/pgss_query_texts.stat`. Reduces shmem
  pressure; downside is that disk reads happen on
  `pg_stat_statements()` view queries.
- **Query identification via JumbleState.** Since PG 14, the core
  query jumbler (`src/backend/nodes/queryjumblefuncs.c`) computes
  `queryId` if `compute_query_id = on`. pg_stat_statements
  consumes the existing `queryId` rather than re-hashing.
- **Five hook points.**
  - `post_parse_analyze_hook` — captures the normalized query
    string + jumble locations for later constant substitution.
  - `planner_hook` — adds plan-time stats (`plan_time`,
    `plan_calls`).
  - `ExecutorStart_hook` / `ExecutorRun_hook` /
    `ExecutorFinish_hook` / `ExecutorEnd_hook` — wraps
    each execution; `ExecutorEnd` is where final stats land.
- **Locking discipline** (from the file header comment in
  `pg_stat_statements.c`):
  - `pgss->lock` (LWLock) — protects the hashtable. Shared for
    lookup; exclusive for insert / delete.
  - per-entry spinlock — protects the counter fields within a
    single entry, so the LWLock can be held shared while many
    backends accumulate stats.
  - `pgss->mutex` (spinlock) — protects `pgss->extent` (next free
    spot in the query-text file).

## 3. Key files

- `pg_stat_statements.c` — the entire implementation. Sections:
  - `_PG_init` / `_PG_fini` — GUC registration, shmem hooks,
    hook installation.
  - `pgss_shmem_startup` — shmem hashtable setup.
  - `pgss_post_parse_analyze` — capture query + jumble locations.
  - `pgss_planner`, `pgss_ExecutorStart` / `_Run` / `_Finish` /
    `_End` — the five hooks.
  - `pgss_store` — insert-or-update an entry under the right locks.
  - `pg_stat_statements` / `pg_stat_statements_info` / `_reset`
    — SQL-callable functions returning view rows.

## 4. Key data structures

- **`pgssHashKey`** — (userid, dbid, queryid, toplevel). The
  toplevel bit distinguishes top-level statements from nested
  ones (e.g. PL function bodies); pg_stat_statements tracks both.
- **`pgssEntry`** — one row of the hashtable. Holds: hash key,
  query-text offset + length, counter struct, mutex spinlock.
- **`Counters`** — the accumulated stats: calls, plan_time,
  exec_time (mean + stddev), rows, shared_blks_*, local_blks_*,
  temp_blks_*, blk_read/write_time, wal_records / wal_fpi /
  wal_bytes, jit_*.
- **`pgssSharedState`** — the singleton in shmem: LWLock,
  mutex, current extent, garbage-collection state.

## 5. SQL surface

- View: `pg_stat_statements` — one row per (userid, dbid,
  queryid, toplevel) entry with all counters.
- View: `pg_stat_statements_info` — meta-info (dealloc count,
  last reset time).
- Functions: `pg_stat_statements(showtext bool)` — set-returning
  function backing the view. `pg_stat_statements_reset(userid,
  dbid, queryid, minmax_only)` — reset a subset of entries.

## 6. Invariants and gotchas

- **[INV-1]** `pgss->lock` (LWLock) is taken shared for lookup,
  exclusive for insert / delete / GC. The per-entry spinlock
  is taken to mutate the counters while the LWLock is held
  shared. Reordering these acquisitions deadlocks.
  [from-comment file header]
- **[INV-2]** The query-text file `pgss_query_texts.stat` is
  truncated and rebuilt during garbage collection (when too
  many entries have been evicted). `pgss->extent` is the next
  free offset; protected by `pgss->mutex` OR exclusive
  `pgss->lock`.
- **[INV-3]** `queryId == 0` means "couldn't normalize" — used
  by utility statements (DDL) where the jumbler doesn't produce
  a stable id. pgss optionally tracks these via the
  `pg_stat_statements.track_utility` GUC.
- **[INV-4]** Counters use the per-entry spinlock; that
  means **no `ereport(ERROR)` allowed inside the critical
  section**. Spinlocks are not released on error.
- The query-text-file path is under `$PGDATA/pg_stat_tmp/`, which
  is cleared on restart by default — so query texts don't survive
  a crash. Counters DO survive (via `pgss_shmem_shutdown` →
  `pgss_shmem_startup` reload from the `pgss.stat` file).

## 7. Owners (as of 2026-06-12)

- Long-term maintainer: Michael Paquier (per recent commit log).
- Heavy interaction with the in-core query jumbler (PG 14+) —
  Julien Rouhaud was the lead on that split. JIT counters
  added by Andres Freund.

## 8. Local reviewer reflexes

- Any new counter field: bump the extension version + add an
  upgrade SQL script. The view shape is user-facing surface.
- Any change to the lock-acquisition order: re-cite the file's
  locking-discipline header comment and confirm.
- Any new hook: confirm chain composition with prev_*_hook
  variables — don't clobber another extension's hook.
- Any garbage-collection change: walk `pgss_extent` invariants;
  truncating the query-text file under a concurrent reader is
  the classic bug.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/pg_stat_statements/pg_stat_statements.c`](../files/contrib/pg_stat_statements/pg_stat_statements.c.md) |

<!-- /files-owned:auto -->
## Cross-references

- `.claude/skills/bgworker-and-extensions/SKILL.md` — hook chaining (`prev_ExecutorEnd_hook` pattern); shmem hooks registration in `_PG_init`.
- `.claude/skills/locking/SKILL.md` — LWLock + per-entry spinlock composition rule; no `ereport(ERROR)` inside a spinlock.
- `.claude/skills/gucs-config/SKILL.md` — `pg_stat_statements.max` / `.track` / `.track_utility` GUCs.
- `.claude/skills/parser-and-nodes/SKILL.md` — `queryId` comes from the core query jumbler.
- `.claude/skills/extension-development/SKILL.md` — `shared_preload_libraries` registration.
- `doc/src/sgml/pgstatstatements.sgml` — user-facing reference.
- `source/src/backend/nodes/queryjumblefuncs.c` — the upstream of `queryId`.
