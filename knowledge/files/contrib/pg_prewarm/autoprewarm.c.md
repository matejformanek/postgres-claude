# `pg_prewarm/autoprewarm.c` — background-worker dump-and-reload prewarmer

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_prewarm/autoprewarm.c`)

## Role

Two-tier bgworker that periodically (`pg_prewarm.autoprewarm_interval`,
default 300s) dumps the relfilenode/blocknum of every valid shared buffer
to a fixed file `autoprewarm.blocks` under the data directory, and on
restart reads it back to repopulate `shared_buffers`. The leader worker
runs from server start; per-database workers are launched on demand to
hold the per-database connection needed to resolve relfilenumber →
reloid.

Also exposes two SQL functions to launch / dump explicitly.

## Public API

- `autoprewarm_start_worker() -> void` — `source/contrib/pg_prewarm/autoprewarm.c:814`
- `autoprewarm_dump_now() -> int8` (blocks dumped) — `source/contrib/pg_prewarm/autoprewarm.c:846`

Plus two bgworker entrypoints (called via the bgworker framework, not
SQL): `autoprewarm_main`, `autoprewarm_database_main`.

GUCs (`_PG_init`):

- `pg_prewarm.autoprewarm_interval` (PGC_SIGHUP, GUC_UNIT_S, default 300)
- `pg_prewarm.autoprewarm` (PGC_POSTMASTER, default true)

## Invariants

- The dump file is a **fixed path**: `AUTOPREWARM_FILE
  "autoprewarm.blocks"` — relative to PGDATA via `AllocateFile`
  [verified-by-code] (`source/contrib/pg_prewarm/autoprewarm.c:53,322`).
- Only one leader bgworker may be running; concurrent attempt logs and
  exits [verified-by-code]
  (`source/contrib/pg_prewarm/autoprewarm.c:197-205`).
- A `pid_using_dumpfile` LWLock-protected field ensures exactly one
  reader/writer of the dump file at a time
  (`source/contrib/pg_prewarm/autoprewarm.c:305-316,
   676-693`).
- Leader uses `BGWORKER_SHMEM_ACCESS` only (no DB connection); per-DB
  worker adds `BGWORKER_BACKEND_DATABASE_CONNECTION`
  (`source/contrib/pg_prewarm/autoprewarm.c:914,953-954`).
- Per-DB worker `bgw_restart_time = BGW_NEVER_RESTART` so a crash
  doesn't loop [verified-by-code]
  (`source/contrib/pg_prewarm/autoprewarm.c:956`).
- Leader is started either via `RegisterBackgroundWorker` (in
  postmaster) or `RegisterDynamicBackgroundWorker` (from the SQL
  function) [verified-by-code]
  (`source/contrib/pg_prewarm/autoprewarm.c:921-934`).
- Dump caps records at `NBuffers` (sized for `MCXT_ALLOC_HUGE`)
  (`source/contrib/pg_prewarm/autoprewarm.c:702-703`).
- `apw_state` is a `GetNamedDSMSegment("autoprewarm", ...)` — relies on
  the DSM registry to give the same segment to all workers
  (`source/contrib/pg_prewarm/autoprewarm.c:881-887`).

## Notable internals

- The dump-file format is plain text:
  `<<N>>\n` followed by `%u,%u,%u,%u,%u\n` per record
  (database, tablespace, filenumber, forknum, blocknum)
  (`source/contrib/pg_prewarm/autoprewarm.c:339-361, 745-768`).
- Reading is via `fscanf("%u,%u,...")` — narrow trust boundary because
  the file lives under PGDATA and is written by the same module, but
  any byte that doesn't match emits an `ERROR` "block dump file is
  corrupted at line %d" (line 358).
- Records are sorted by (database, tablespace, filenumber, forknum,
  blocknum) and dispatched per database
  (`source/contrib/pg_prewarm/autoprewarm.c:366-438`). Records with
  `database == InvalidOid` (global objects, e.g. shared catalogs) are
  merged into the first per-DB worker's batch.
- Per-DB worker connects via `BackgroundWorkerInitializeConnectionByOid`
  with `InvalidOid` for the user, granting superuser-equivalent rights
  inside the worker [verified-by-code]
  (`source/contrib/pg_prewarm/autoprewarm.c:519`).
- Read-stream callback fast-forwards through invalid blocks (out-of-
  range), tracking position so the outer loop knows where the next
  relation/fork starts (`source/contrib/pg_prewarm/autoprewarm.c:458-494`).
- `try_relation_open` lets the worker silently skip relations that have
  been dropped between dump and load
  (`source/contrib/pg_prewarm/autoprewarm.c:546`).
- Final dump (on shutdown) is suppressed if `apw_load_buffers` was
  interrupted by a shutdown request — to avoid truncating the file
  to a partial state [from-comment lines 215-221].

## Trust-boundary / Phase D surface

1. **Per-DB worker bypasses ACLs.**
   `BackgroundWorkerInitializeConnectionByOid(apw_state->database,
   InvalidOid, 0)` connects without an effective user, so
   `try_relation_open` + `read_stream_begin_relation` succeed regardless
   of what role originally caused those buffers to be cached. This is
   safe because (a) only previously-cached blocks are touched, and (b)
   data is loaded back into shared_buffers (not exposed). But it does
   mean a buffer that was loaded by a privileged session can be re-loaded
   into the cache after a restart, which can affect timing-channel
   observability for less-privileged users.
   [ISSUE-defense-in-depth: per-DB worker uses InvalidOid user
   (effectively bootstrap superuser), so cached blocks survive across
   role-permission changes between dump and reload — small leak of
   "what was hot before" (nit)]
   (`source/contrib/pg_prewarm/autoprewarm.c:519`).
2. **`autoprewarm.blocks` is a privileged write target in PGDATA.**
   Path is fixed; symlink attack is the standard PGDATA story (data dir
   is mode 0700). Not an issue *if* PGDATA permissions are intact, but
   no extra sanitation here. [ISSUE-defense-in-depth: dump file path is
   not validated as a regular file; if PGDATA is breached, replacing
   autoprewarm.blocks with a crafted file lets you steer prewarm I/O
   patterns. Already requires PGDATA write — low marginal impact
   (nit)] (`source/contrib/pg_prewarm/autoprewarm.c:53,322,737-738`).
3. **`fscanf` on the dump file does no overflow check on `%u`** beyond
   what the type allows. Maximum well-formed input is the line count
   `N` at top; if `N` is set huge, the `dsm_create(sizeof(BlockInfoRecord) * num_elements)`
   call allocates `20 * N` bytes via DSM, which can fail OOM but not
   silently. [ISSUE-resource: dump file's leading <<N>> line dictates
   a dsm_create of `20*N` bytes; a corrupted dump file can OOM the
   leader (still needs PGDATA write) (nit)]
   (`source/contrib/pg_prewarm/autoprewarm.c:339-346`).
4. **`autoprewarm_start_worker` and `autoprewarm_dump_now` have NO
   superuser/role check.** They are not REVOKE'd in any of the install
   scripts (`pg_prewarm--1.1.sql`, `--1.1--1.2.sql`) — verified with
   `grep REVOKE` returning empty for pg_prewarm. So anyone with EXECUTE
   on these (default: PUBLIC) can trigger a full-shared-buffers dump or
   launch the leader bgworker.
   [ISSUE-audit-gap: autoprewarm_start_worker and autoprewarm_dump_now
   have no permission check at C or SQL level — any logged-in user can
   trigger a full NBuffers dump, holding the dump-file lock and
   competing for header spinlocks across all buffers (likely)]
   (`source/contrib/pg_prewarm/autoprewarm.c:814,846`).
5. **`apw_detach_shmem` is registered with `before_shmem_exit`** because
   "DSM segments are detached before calling the on_shmem_exit callbacks"
   [from-comment lines 184-191] — correct, but if the autoprewarm
   leader is killed *before* before_shmem_exit fires, `bgworker_pid`
   stays as the stale PID, blocking re-start until manual fixup.
   [ISSUE-correctness: stale bgworker_pid possible after SIGKILL of
   leader; restart will refuse with "already running under PID %d"
   even though the worker is dead (nit)]
   (`source/contrib/pg_prewarm/autoprewarm.c:197-205,892-901`).
6. **Per-DB worker's outer while loop** (lines 575-649) re-runs
   `read_stream_begin_relation` etc. for each (tablespace, filenumber,
   forknum) tuple; the loop variable `i` is advanced inside the read
   stream callback via `p.pos`, which is then copied back at line 647.
   Subtle but appears correct [verified-by-code].
7. **`fscanf("<<%d>>\n", ...)`** uses `%d` (signed int) for a count that
   could be unsigned. Negative values get into `num_elements` and skip
   the loop or trigger `dsm_create(negative)` via signed→size_t
   promotion. [ISSUE-correctness: dump-file count read as %d not %u;
   negative N silently allowed, gets multiplied by sizeof(record) in
   dsm_create call (maybe)]
   (`source/contrib/pg_prewarm/autoprewarm.c:339,346`).

## Cross-refs

- `knowledge/files/contrib/pg_prewarm/pg_prewarm.c.md` — synchronous companion
- `knowledge/idioms/gucs-bgworker-parallel.md` — bgworker registration patterns
- `knowledge/subsystems/storage-buffer.md` — `BufferDesc.tag` semantics
- `knowledge/subsystems/replication-overview.md` — N/A (autoprewarm is standalone)

<!-- issues:auto:begin -->
- [Issue register — `pg_prewarm`](../../../issues/pg_prewarm.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-audit-gap: autoprewarm_start_worker / autoprewarm_dump_now have NO permission check (PUBLIC by default) (likely)] — `source/contrib/pg_prewarm/autoprewarm.c:814,846` and `pg_prewarm/pg_prewarm--1.1.sql` (no REVOKE)
2. [ISSUE-defense-in-depth: per-DB worker connects with InvalidOid user; cached blocks survive role-perm changes across restart (nit)] — `source/contrib/pg_prewarm/autoprewarm.c:519`
3. [ISSUE-defense-in-depth: dump file path is unvalidated; symlink/replace attack on PGDATA can steer prewarm I/O (nit)] — `source/contrib/pg_prewarm/autoprewarm.c:53,322,737-738`
4. [ISSUE-resource: leading <<N>> line drives a dsm_create of 20*N bytes; corrupted file can OOM the leader (nit)] — `source/contrib/pg_prewarm/autoprewarm.c:339-346`
5. [ISSUE-correctness: stale bgworker_pid after SIGKILL of leader blocks re-start (nit)] — `source/contrib/pg_prewarm/autoprewarm.c:197-205,892-901`
6. [ISSUE-correctness: <<N>> read as signed %d, negative N silently allowed and propagated to size calculation (maybe)] — `source/contrib/pg_prewarm/autoprewarm.c:339,346`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_prewarm.md](../../../subsystems/contrib-pg_prewarm.md)
