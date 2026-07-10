# pg_stat_monitor — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `percona/pg_stat_monitor` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> blobs fetched 2026-07-10 (see Sources footer). Line numbers are for the `main`
> blobs as fetched.

pg_stat_monitor is pg_stat_statements' more-opinionated cousin: it is explicitly
"developed on the basis of `pg_stat_statements` as its more advanced
replacement" (`README.md:45`) `[from-README]`, reusing pgss's hook shape,
query-jumbling, and per-statement counters — but bolting on a fundamentally
different *retention model*. **Headline divergence:** where in-core pgss keeps a
single monotonically-accumulating hash of `(userid,dbid,queryid,toplevel)`,
pg_stat_monitor shards every statistic into a **ring of time-based buckets** — a
`bucket_id` is the first field of the hash key (`hash_query.h:57-68`), a new
bucket is opened on a wall-clock schedule and the *oldest* bucket's rows are
bulk-evicted when the ring wraps (`pg_stat_monitor.c:2542-2548`) — and it widens
the identity of a statement with client IP, application-name hash, and plan id,
while recording a per-statement response-time **histogram** alongside the mean
(`hash_query.h:192-194`, `pg_stat_monitor.c:1305-1306`) `[verified-by-code]`.

## Domain & purpose

pg_stat_monitor answers: *what did my workload look like over the last N time
windows, sliced by client, application, user, database, plan, and command type,
with a latency distribution rather than a single mean?* (`README.md:70-77`)
`[from-README]`. It is a drop-in-shaped superset of pg_stat_statements aimed at
DBAs who want time-bounded aggregates ("buckets") instead of counters that only
ever grow, so that min/max/mean are meaningful for a recent interval rather than
since-reset (`README.md:47`) `[from-README]`. The control-file comment states the
lineage and the extra dimensions outright: "based on PostgreSQL contrib module
pg_stat_statements … provides aggregated statistics, client information, plan
details … and histogram information" (`pg_stat_monitor.control:2`)
`[verified-by-code]`.

## How it hooks into PG

pg_stat_monitor **requires** `shared_preload_libraries`: `_PG_init` returns
early unless `process_shared_preload_libraries_in_progress`
(`pg_stat_monitor.c:287-288`) `[verified-by-code]`.

- **Ten hook installs, prior pointer saved each time**
  (`pg_stat_monitor.c:307-331`) `[verified-by-code]`: `shmem_request_hook`,
  `shmem_startup_hook`, `post_parse_analyze_hook`, `planner_hook`,
  `ExecutorStart_hook`, `ExecutorRun_hook`, `ExecutorFinish_hook`,
  `ExecutorEnd_hook`, `ProcessUtility_hook`, plus two that pgss does *not* take:
  `emit_log_hook` (to capture error-level events as pseudo-statements) and
  `ExecutorCheckPerms_hook` (to harvest the relation list of each query)
  (`pg_stat_monitor.c:328-331`) `[verified-by-code]`.
- **`EnableQueryId()`** is called in `_PG_init` so core query-id jumbling is
  always on even when `compute_query_id = auto` (`pg_stat_monitor.c:299`)
  `[verified-by-code]`.
- **Shmem request.** `pgsm_shmem_request` calls
  `RequestAddinShmemSpace(pgsm_ShmemSize())` and
  `RequestNamedLWLockTranche("pg_stat_monitor", 1)` — a *single* named tranche
  for the whole hash table (`pg_stat_monitor.c:376-377`) `[verified-by-code]`.
- **Shmem startup.** `pgsm_startup` carves ONE `ShmemInitStruct("pg_stat_monitor")`
  region, then lays a **DSA area in place** immediately after the shared-state
  struct for the variable-length query texts (`dsa_create_in_place`,
  `hash_query.c:87-107`) and builds a single `ShmemInitHash` bucket hash table
  (`hash_query.c:109`, `137-146`) `[verified-by-code]`.
- **GUCs.** 17 `DefineCustom*Variable` calls in `init_guc`
  (`guc.c:56-278`), including the bucketing knobs (`pgsm_max_buckets`,
  `pgsm_bucket_time`), the histogram knobs (`pgsm_histogram_min/max/buckets`),
  and the extra-dimension toggles (`pgsm_track_application_names`,
  `pgsm_enable_pgsm_query_id`) `[verified-by-code]`. Placeholders are flushed
  with the legacy `EmitWarningsOnPlaceholders("pg_stat_monitor")`
  (`pg_stat_monitor.c:301`) rather than `MarkGUCPrefixReserved`
  `[verified-by-code]`.
- **No background worker.** Unlike [[pgsentinel]] / [[pg_tracing]], there is no
  bgworker: bucket rotation is done *lazily inside the storing backend*, on the
  first `pgsm_store` after a bucket's wall-clock lifetime expires
  (`pg_stat_monitor.c:1697`, `2503-2564`) `[verified-by-code]`.

## Where it diverges from core idioms — vs in-core pg_stat_statements

### 1. Rotating time-buckets vs pgss's single accumulating hash

The load-bearing divergence. pgss's hash key is
`(userid,dbid,queryid,toplevel)`; pg_stat_monitor prepends **`bucket_id`** and
appends **`planid`, `appid`, `ip`, `parentid`** to the key
(`hash_query.h:57-68`) `[verified-by-code]`. `get_next_wbucket` reads wall-clock
`gettimeofday`, and when `tv.tv_sec - prev_bucket_sec >= pgsm_bucket_time` it
CAS-advances `prev_bucket_sec`, computes
`new_bucket_id = (tv.tv_sec / pgsm_bucket_time) % pgsm_max_buckets`, and —
holding `pgsm->lock` exclusively — calls `hash_entry_dealloc(new_bucket_id)` to
**wipe every hash entry belonging to the bucket it is about to reuse**
(`pg_stat_monitor.c:2527-2560`) `[verified-by-code]`. So the same
`pgsm_max_buckets`-slot ring is overwritten cyclically; a statement seen in two
different windows produces two distinct hash entries. This is a wholly different
retention philosophy from core's grow-until-reset counters.

### 2. Per-bucket eviction is a full hash-table sequential scan

`hash_entry_dealloc` walks the *entire* shared hash with `hash_seq_search` and
`HASH_REMOVE`s every entry whose `key.bucket_id` matches the bucket being
recycled (or all entries when `bucket_id == INVALID_BUCKET_ID`), freeing each
row's DSA-held query text and parent-query text as it goes
(`hash_query.c:235-266`) `[verified-by-code]`. Core pgss never does per-slice
mass eviction; here it happens on the unlucky backend that trips the bucket
boundary, under the single exclusive tranche lock.

### 3. A response-time histogram carried inside every Counters struct

Each `Counters` embeds `int resp_calls[MAX_RESPONSE_BUCKET + 2]`
(`hash_query.h:192-194`, `MAX_RESPONSE_BUCKET == 50` at `guc.h:21`)
`[verified-by-code]`. On every store, `get_histogram_bucket(exec_total_time)`
finds the matching latency band and bumps `resp_calls[index]`
(`pg_stat_monitor.c:1305-1306`) `[verified-by-code]`. Band edges are
**exponential**: `histogram_bucket_timings` computes
`bucket_size = log(q_max - q_min) / bucket_count` and places bounds at
`q_min + exp(bucket_size * i)`, with two extra "outlier" buckets for values
below `pgsm_histogram_min` and above `pgsm_histogram_max`
(`pg_stat_monitor.c:3044-3083`, `3033`) `[verified-by-code]`. The min/max GUCs
carry check hooks enforcing `max >= min + 1.0` (`guc.c:281-295`)
`[verified-by-code]`. pgss has no latency distribution at all — this is a pure
addition.

### 4. It re-implements pgss's constant query-jumbling to normalize text

To emit `SELECT $1`-style normalized text, `pgsm_post_parse_analyze_internal`
runs `generate_normalized_query(jstate, …)` when
`jstate->clocations_count > 0` (`pg_stat_monitor.c:469-491`), which drives
`fill_in_constant_lengths` over the core flex scanner and substitutes constants
at the jumble's `clocations` — near-verbatim borrowed pgss code (the "We've
copied up until the last ignorable constant" comment block is the upstream one,
`pg_stat_monitor.c:2759`) `[inferred]` `[from-comment]`. This is idiom
duplication, not a shared API — the same copy-the-jumbler pattern
[[pg_tracing]] uses.

### 5. A second, text-based "pgsm_query_id" independent of core's queryid

Beyond core's `queryid`, it computes its own `pgsm_query_id` via
`get_pgsm_query_id_hash`, which strips comments and collapses whitespace from
the *normalized* text and hashes the result with `hash_bytes_extended`
(`pg_stat_monitor.c:2573-2645`, `pgsm_hash_string` at `1185-1189`)
`[verified-by-code]`. Its stated purpose is a stable id "useful in comparing
same query across databases and clusters" (`guc.c:196`) `[verified-by-code]` —
a portability id core deliberately does not provide (core's queryid folds in
OIDs).

### 6. Query text lives in an in-place DSA arena, optionally spilling to swap

Rather than pgss's external on-disk query-text file, query strings and
parent-query strings are stored in a **DSA area created in place** inside the
shmem segment (`dsa_create_in_place`, `hash_query.c:103`), and each `pgsmEntry`
holds a `dsa_pointer query_pos` into it (`hash_query.h:214-218`)
`[verified-by-code]`. When `pgsm_enable_overflow` is on (default `true`,
`guc.c:219-229`), the DSA size limit is set to `-1` so the arena "can grow
beyond the shared memory space into the swap area" (`hash_query.c:112-116`)
`[verified-by-code]`. Allocation uses `DSA_ALLOC_NO_OOM` so a full arena
degrades gracefully instead of erroring (`pg_stat_monitor.c:1784-1789`)
`[verified-by-code]`.

### 7. Extra identity dimensions harvested from places pgss ignores

- **Relations.** The `ExecutorCheckPerms_hook` collects up to `REL_LST` (10,
  `hash_query.h:30`) `schema.relname` strings per query, marking views with a
  trailing `*` (`pg_stat_monitor.c:800-815`) `[verified-by-code]`.
- **Client IP** is captured once per backend via `pg_getnameinfo_all` on
  `MyProcPort->raddr` and stored as a `uint32` in the key
  (`pg_stat_monitor.c:1209-1230`, `1624-1627`) `[verified-by-code]`.
- **Application name** is hashed (`pgsm_hash_string(app_name)`) into
  `key.appid` (`pg_stat_monitor.c:1616-1621`) `[verified-by-code]`.
- **Command type**, **JIT counters**, **WAL usage**, and **parallel-worker
  launch counts** are all fields of `Counters` (`hash_query.h:135-199`)
  `[verified-by-code]`.

## Notable design decisions (with cites)

- **Per-entry spinlock, table-wide LWLock.** Each `pgsmEntry` has its own
  `slock_t mutex` "protects the counters only" (`hash_query.h:213`),
  `SpinLockInit`'d at alloc (`hash_query.c:223`); the hash structure itself is
  guarded by the single named tranche `pgsm->lock` (`hash_query.h:226`,
  `hash_query.c:96`) `[verified-by-code]`. Store takes the LWLock `LW_SHARED`
  first and only escalates to `LW_EXCLUSIVE` to create a new entry
  (`pg_stat_monitor.c:1768-1799`) `[verified-by-code]`.
- **OOM is a sticky, self-reporting flag.** When `hash_entry_alloc` returns
  NULL (hash full), `pgsm_store` sets `pgsm->pgsm_oom = true` and warns exactly
  once (guarded by the prior flag value) to avoid log floods; the flag clears
  when a bucket is deallocated or an alloc later succeeds
  (`pg_stat_monitor.c:1804-1833`, `hash_query.c:263`, `IsSystemOOM` at
  `hash_query.c:268-272`) `[verified-by-code]`.
- **Errors become pseudo-statements.** `pgsm_emit_log_hook` →
  `pgsm_store_error` synthesizes an entry keyed by a `pgsm_hash_string` of the
  errant query, storing sqlcode / elevel / message in the `ErrorInfo` sub-struct
  (`pg_stat_monitor.c:1476-1493`, `hash_query.h:84-89`) `[verified-by-code]` —
  observability core pgss has no analogue for.
- **Nested-query lineage.** Under `pgsm_track = all`, a child entry's
  `key.parentid` is set from a per-nesting-level `nested_queryids[]` stack and
  the parent's text is copied into the DSA arena
  (`pg_stat_monitor.c:1329-1350`, `1755-1758`) `[verified-by-code]`.
- **Bucket start-time is a flexible array member.** `pgsmSharedState` ends with
  `TimestampTz bucket_start_time[]` sized `pgsm_max_buckets`, filled at rotation
  time (`hash_query.h:233`, `pg_stat_monitor.c:2557-2559`) `[verified-by-code]`.
- **Version compat by inline `#if PG_VERSION_NUM`** everywhere (14→18): the
  `ExecutorRun`/`ExecutorCheckPerms` signatures, the buffer/WAL timing field
  renames, the `wal_buffers_full` and JIT `deform_counter` additions, and the
  PG17 utility-nesting `PG_TRY` guard are all inline ifdefs
  (`pg_stat_monitor.c:1140-1176`, `1719-1752`, `790-822`) `[verified-by-code]`.

## Links into corpus

- [[process-utility-hook-chain]] — pg_stat_monitor is one more
  `ProcessUtility_hook` link; the save-prior-pointer chain idiom
  (`pg_stat_monitor.c:324-325`, `1152-1163`) is shared.
- [[guc-variables]] — the 17 `DefineCustom*Variable` calls + histogram
  check-hooks + legacy `EmitWarningsOnPlaceholders` (`guc.c:56-295`).
- [[memory-contexts]] — the per-backend `PgsmMemoryContext` staging entries and
  the DSA attach pinned to `TopMemoryContext` (`hash_query.c:159-178`,
  `pg_stat_monitor.c:1606-1607`).
- [[locking-overview]] / [[spinlock-discipline]] — single named LWLock tranche
  guarding the hash, per-entry spinlock guarding counters, shared→exclusive
  escalation on entry creation (`hash_query.c:96`, `pg_stat_monitor.c:1768-1799`).
- [[fmgr]] / [[spi]] — SRF output (`pg_stat_monitor`, `get_histogram_timings`)
  via `PG_FUNCTION_INFO_V1` set-returning functions
  (`pg_stat_monitor.c:2050-2328`).
- Sibling ideologies: [[pgsentinel]] (also a pgss-adjacent shmem observability
  extension, but a bgworker sampler that snapshots the pgss *view*; PSM instead
  re-implements pgss inline and rotates buckets in-backend), [[pg_tracing]]
  (closest on the query-jumble-copy and shmem-arena axes — both lift pgss's
  `fill_in_constant_lengths`), [[pg_qualstats]] (another `_PG_init` hook-chain
  observer layered on the executor). The in-tree analogue is
  `contrib/pg_stat_statements` itself, which PSM forks in spirit.

> Corpus gap: there is no idiom doc for the **"rotating time-bucket ring as the
> retention model"** pattern (bucket_id as the leading hash-key field + lazy
> in-backend rotation + full-scan per-bucket eviction) — pg_stat_monitor is the
> canonical example; worth an `idioms/time-bucket-retention.md`.
> Corpus gap: no idiom doc for **copying pgss's constant query-jumbling**
> (`generate_normalized_query` / `fill_in_constant_lengths` over the core flex
> scanner); [[pg_tracing]] and pg_stat_monitor both duplicate it, and the note
> was already flagged in `pg_tracing.md`.

## Sources

All fetched 2026-07-10 (branch `main`).

- `https://raw.githubusercontent.com/percona/pg_stat_monitor/main/README.md` — 200 (306 lines)
- `https://raw.githubusercontent.com/percona/pg_stat_monitor/main/src/pg_stat_monitor.c` — 200 (3210 lines)
- `https://raw.githubusercontent.com/percona/pg_stat_monitor/main/src/hash_query.c` — 200 (272 lines)
- `https://raw.githubusercontent.com/percona/pg_stat_monitor/main/src/guc.c` — 200 (295 lines)
- `https://raw.githubusercontent.com/percona/pg_stat_monitor/main/pg_stat_monitor.control` — 200 (5 lines)
- **404 gap:** the manifest path `src/pg_stat_monitor.h` returned 404 (also
  probed `include/`, `src/include/`, repo-root, `hdr/` — all 404). The shared
  data-structure definitions the manifest expected there actually live in
  `src/hash_query.h`, which was fetched instead (200, 246 lines) and carries the
  `pgsmHashKey` / `Counters` / `pgsmEntry` / `pgsmSharedState` structs. The GUC
  externs live in `src/guc.h` (200, 50 lines, fetched). Both substitutes are
  cited above in place of the missing `pg_stat_monitor.h`.

Cites verified against blobs fetched 2026-07-10.
