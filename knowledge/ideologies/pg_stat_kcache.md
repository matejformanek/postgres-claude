# pg_stat_kcache — a resource-accounting extension with no query identity of its own, borrowed wholesale from pg_stat_statements

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `powa-team/pg_stat_kcache` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> blobs fetched 2026-07-10 (see Sources footer). Line numbers are for the
> `master` blobs as fetched.

pg_stat_kcache measures the **OS-level resource cost of each query** — user/system
CPU time, filesystem reads/writes, page faults, context switches, IPC messages —
by bracketing execution with `getrusage(2)` and attributing the delta to a
`queryid`. **Headline divergence:** the extension has no notion of query identity
of its own. It *requires* pg_stat_statements at the catalog level
(`pg_stat_kcache.control:4`) `[verified-by-code]`, reads pgss's computed
`queryId` straight off the `PlannedStmt` / `Query`
(`pg_stat_kcache.c:1062,1157,961`) `[verified-by-code]`, sizes its own shmem hash
by scraping the `pg_stat_statements.max` GUC string at startup
(`pg_stat_kcache.c:694-718`) `[verified-by-code]`, and reuses pgss's exact
`{userid, dbid, queryid, top}` hash-key shape (`pg_stat_kcache.c:146-155`)
`[verified-by-code]`. It is a deliberate parasite on another extension's
identifier space — a design core Postgres would never sanction, since core
subsystems own their keys rather than reading a sibling module's GUCs and plan
fields to reconstruct them.

## Domain & purpose

The extension answers *what did this query actually cost the operating system?*
pg_stat_statements already tracks wall-clock time and PG-internal buffer
counters; pg_stat_kcache adds the layer beneath — the kernel's own accounting.
For each `(user, db, queryid, top-level?)` tuple it accumulates two "kinds" of
counters, **planning** and **execution**, each holding user CPU seconds, system
CPU seconds, soft/hard page faults, swaps, filesystem bytes read/written (from
the kernel's block counters), IPC message send/recv, signals, and voluntary /
involuntary context switches (`README.rst:87-313`, `pg_stat_kcache.c:453-462`)
`[from-README]` `[verified-by-code]`. The payload use is a *real* cache
hit-ratio: comparing pgss's logical block reads against pg_stat_kcache's physical
`exec_reads` tells you how much of your I/O actually hit the disk vs the OS page
cache (`pg_stat_kcache.c:4-6` header comment) `[from-comment]`. It is the
kernel-accounting sibling of pg_stat_statements within the PoWA stack.

## How it hooks into PG

`PG_MODULE_MAGIC` (`pg_stat_kcache.c:73`). `_PG_init` hard-fails unless preloaded:
`if (!process_shared_preload_libraries_in_progress) elog(ERROR, "This module can
only be loaded via shared_preload_libraries")` (`pg_stat_kcache.c:308-312`)
`[verified-by-code]`.

- **Six hooks chained** (each saving the prior pointer): `shmem_request_hook`
  (PG ≥ 15) and `shmem_startup_hook` for the shared hashtable; the **planner
  hook** (PG ≥ 13 only, for planning-time accounting); and the **full executor
  quartet** `ExecutorStart` / `ExecutorRun` / `ExecutorFinish` / `ExecutorEnd`
  (`pg_stat_kcache.c:372-389`) `[verified-by-code]`. Note it does **not** chain
  `ProcessUtility_hook` — the nesting-depth comment names
  "planner/ExecutorRun/ProcessUtility" (`pg_stat_kcache.c:182-183`) but no
  utility hook is installed, so DDL / utility statements are accounted only
  insofar as they drive the planner and executor `[verified-by-code]`.
- **The getrusage sandwich.** `pgsk_ExecutorStart` calls
  `getrusage(RUSAGE_SELF, rusage_start)` into a per-nesting-level static array
  *before* execution (`pg_stat_kcache.c:1053-1056`); `pgsk_ExecutorEnd` calls
  `getrusage(RUSAGE_SELF, &rusage_end)` *after* (`pg_stat_kcache.c:1149-1150`),
  and `pgsk_compute_counters` subtracts the two structs field by field —
  `ru_minflt`, `ru_majflt`, `ru_inblock`, `ru_oublock`, `ru_nvcsw`, … — to get
  the per-query delta (`pg_stat_kcache.c:417-464`) `[verified-by-code]`. The
  planner hook does the same bracket around `standard_planner`
  (`pg_stat_kcache.c:968,997-1002`) and stores under the `PGSK_PLAN` kind
  `[verified-by-code]`.
- **Shmem model like pgss.** A `pgskSharedState` (one `LWLock` + a
  `queryids[FLEXIBLE_ARRAY_MEMBER]` array) plus a `ShmemInitHash` of `pgskEntry`
  keyed by `pgskHashKey`, sized to `pgsk_max` (`pg_stat_kcache.c:171-178,
  516-547`) `[verified-by-code]`. Each entry carries a per-entry `slock_t mutex`
  protecting its counters, under the coarse hashtable `LWLock`
  (`pg_stat_kcache.c:160-166, 786-828`) `[verified-by-code]` — the pgss
  two-tier locking discipline.
- **GUCs.** `pg_stat_kcache.linux_hz` (int, `PGC_USERSET`),
  `pg_stat_kcache.track` (enum none/top/all, `PGC_SUSET`), and
  `pg_stat_kcache.track_planning` (bool, `PGC_SUSET`, PG ≥ 13 only)
  (`pg_stat_kcache.c:314-352`) `[verified-by-code]`. Placeholders flushed with
  the legacy `EmitWarningsOnPlaceholders` (`pg_stat_kcache.c:354`)
  `[verified-by-code]`.
- **Output.** `pg_stat_kcache()` is an `SFRM_Materialize` SRF walking the hash
  under `LW_SHARED` (`pg_stat_kcache.c:1257-1386`), plus `pg_stat_kcache_reset()`
  (superuser) (`pg_stat_kcache.c:1213-1223`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. It depends on, and coordinates load order with, pg_stat_statements — the headline

pg_stat_kcache cannot compute a `queryid` and refuses to invent one. Instead:

- The `.control` declares `requires = 'pg_stat_statements'`
  (`pg_stat_kcache.control:4`) `[verified-by-code]` — a catalog-level dependency
  on a *second extension*, uncommon even among observability modules.
- `pgsk_setmax()` reads the sibling's GUC at startup via
  `GetConfigOption("pg_stat_statements.max", ...)` and `atoi`s it into
  `pgsk_max`, so the two extensions hold the *same number of entries*
  (`pg_stat_kcache.c:694-718`) `[verified-by-code]`. If pgss is loaded *after*
  pgsk in `shared_preload_libraries`, that GUC isn't registered yet and the
  lookup fails; the code emits an `errhint` telling the admin to put
  pg_stat_kcache *after* pg_stat_statements (`pg_stat_kcache.c:708-715`)
  `[verified-by-code]`. So correct operation is contingent on **hook / preload
  ordering relative to another module** — a coupling core never imposes.
- The hash key `{userid, dbid, queryid, top}` is a verbatim copy of the pgss key,
  and the comment says so outright: "We use the same hash as pg_stat_statements"
  (`pg_stat_kcache.c:146-155`) `[from-comment]`. The `queryId` values themselves
  are read from `queryDesc->plannedstmt->queryId` /`parse->queryId`
  (`pg_stat_kcache.c:1062,1157,961`) — the jumble pgss computed. Entries with a
  zero queryid (no pgss jumbling) are silently skipped in the planner path
  (`pg_stat_kcache.c:961`) `[verified-by-code]`.

The README states the requirement plainly and even explains *why* PG ≥ 9.4:
earlier pg_stat_statements "didn't expose the queryid field" (`README.rst:7-11`)
`[from-README]`.

### 2. Its counters are OS-provided, not PG-instrumented — semantics vary by platform

Every non-CPU counter is a raw kernel `struct rusage` field difference
(`pg_stat_kcache.c:453-462`) `[verified-by-code]`. This inverts the usual
extension posture: instead of reading PG's own instrumentation, it reads the
operating system's, and inherits all of the OS's portability caveats. The README
is explicit that this is lossy and platform-dependent: on platforms **without a
native `getrusage(2)`**, "all fields except `user_time` and `system_time` will be
NULL"; and even *with* one, "some of the fields may not be maintained… please
refer to your platform `getrusage(2)` manual page" (`README.rst:341-346`)
`[from-README]`. The code encodes this: outside `HAVE_GETRUSAGE`, the block/fault
/switch counters aren't computed (`pg_stat_kcache.c:451-463`) and the SRF emits
SQL NULLs for them (`pg_stat_kcache.c:1344-1370`) `[verified-by-code]`. PG core
avoids OS-visible-behavior leakage into its stats precisely to keep them
reproducible; pg_stat_kcache accepts Linux-vs-macOS reporting differences as the
cost of measuring the real kernel.

### 3. The kernel-block-to-bytes conversion hard-codes a 512-byte block

`ru_inblock` / `ru_oublock` are in kernel blocks; the SRF multiplies by
`RUSAGE_BLOCK_SIZE` to report bytes (`pg_stat_kcache.c:1340-1341`)
`[verified-by-code]`. The README pins the constant and admits the assumption:
"We assume that a kernel block is 512 bytes. This is true for Linux, but may not
be the case for another Unix implementation" (`README.rst:336-339`)
`[from-README]`. A hard-coded magic number standing in for a kernel constant the
platform never exports is exactly the kind of assumption core would refuse to
bake in.

### 4. It busy-loops calling getrusage to auto-detect the kernel tick (`CONFIG_HZ`)

Because `getrusage` CPU time is quantised to the kernel tick, small measurements
are biased. The `linux_hz` check-hook, when left at its `-1` default, **spins
calling `getrusage(RUSAGE_SELF, …)` until `ru_utime.tv_usec` changes**, then
computes `1 / delta` as the tick frequency (`pg_stat_kcache.c:400-413`)
`[verified-by-code]`. `pgsk_compute_counters` then uses that value to suppress
system time for sub-`3/linux_hz` measurements, treating them as pure user time to
avoid amplifying quantisation noise (`pg_stat_kcache.c:441-448`)
`[verified-by-code]`. A GUC whose default value triggers a spin-loop against a
syscall at assignment time is an idiom core has no equivalent for.

### 5. queryid isn't pushed to parallel workers, so it is smuggled through shmem by ProcNumber

pgss's `queryId` lives in the leader's plan but "isn't pushed to parallel
workers" (`pg_stat_kcache.c:739-740` comment) `[from-comment]`. So the leader
writes its queryid into a shmem array at its own slot —
`pgsk->queryids[MyProcNumber] = queryid` (`pg_stat_kcache.c:467-474`) — during
`ExecutorStart`, and a worker reads it back at
`pgsk->queryids[ParallelLeaderProcNumber]` in `ExecutorEnd`
(`pg_stat_kcache.c:1152-1157`) `[verified-by-code]`. The array is sized for every
possible backend (`MaxBackends + 1`, with a pre-PG15 hand-count of
`MaxConnections + autovacuum_max_workers + max_worker_processes + max_wal_senders
+ …`) (`pg_stat_kcache.c:735-758`) `[verified-by-code]`. Indexing shared state by
backend/proc number to thread a value across the parallel leader/worker boundary
is the same low-level coordination trick pg_qualstats reaches for with its
`sampled[]` array — a pattern most extensions never need.

### 6. It exposes its *own* hook for downstream extensions to piggyback

Having borrowed pgss's identity, pg_stat_kcache in turn offers a
`pgsk_counters_hook` (`pg_stat_kcache.c:205`) that it fires from both the planner
and executor paths with the freshly computed counters, query text, nesting level,
and kind (`pg_stat_kcache.c:1004-1008, 1164-1168`) `[verified-by-code]`. A hook
provider layered on top of a hook consumer layered on top of pgss — a three-deep
observability stack — is a PoWA-ecosystem design, not a core one.

## Notable design decisions (with cites)

- **Two counter "kinds" per entry.** `counters[PGSK_NUMKIND]` splits each query's
  cost into planning (`PGSK_PLAN`) and execution (`PGSK_EXEC`); planning is only
  populated when `track_planning` is on and PG ≥ 13
  (`pg_stat_kcache.c:163, 941-1046`) `[verified-by-code]`.
- **Nesting capped at 64.** `PGSK_MAX_NESTED_LEVEL = 64` bounds the static
  per-level rusage arrays (`pg_stat_kcache.c:122, 138-141`); the README calls this
  a deliberate simplicity tradeoff "enough for reasonable use cases"
  (`README.rst:348-351`) `[verified-by-code]` `[from-README]`.
- **Usage-decay eviction, straight from pgss.** `pgsk_entry_dealloc` sorts entries
  by a `usage` score, applies a `USAGE_DECREASE_FACTOR` (0.99) decay, and evicts
  `USAGE_DEALLOC_PERCENT` (5%, min 10) of them when the hash fills
  (`pg_stat_kcache.c:89-92, 884-919`) `[verified-by-code]` — the pg_stat_statements
  eviction algorithm copied verbatim.
- **On-disk persistence across restart.** A `pgsk_shmem_shutdown` callback dumps
  the hash to `pg_stat/pg_stat_kcache.stat` with a magic header
  (`0x20240914`), and `pgsk_shmem_startup` reloads then `unlink`s it so it isn't
  captured in backups/replicas (`pg_stat_kcache.c:136, 561-617, 623-687`)
  `[verified-by-code]` — again the pgss file-dump idiom.
- **Versioned C entry points for API evolution.** `pg_stat_kcache`,
  `_2_1`, `_2_2`, `_2_3` are four separately-exported functions dispatching to one
  internal with a `pgskVersion` enum, so a new SQL definition can bind a wider
  column set while old ones keep working; the SRF gates columns (`top`,
  planning-time kind, `stats_since`) on `api_version`
  (`pg_stat_kcache.c:127-133, 239-247, 1318-1380`) `[verified-by-code]`. The
  README warns a *server restart* is needed when the SRF signature changes
  (`README.rst:315-327`) `[from-README]`.
- **Portability macro shims, including redefining a core function.** For PG ≥ 19
  it `#define`s `ShmemInitHash(n,nelem,i,f)` to inject the removed
  init/max-size split, remaps `query_instr`→`totaltime`, and aliases
  `MyProcNumber`→`MyBackendId` / `ParallelLeaderProcNumber`→
  `ParallelLeaderBackendId` for older majors (`pg_stat_kcache.c:97-120`)
  `[verified-by-code]`. Shadowing a core symbol name in-translation-unit is a
  portability hack core never performs.
- **`relocatable = true`.** Unlike many preload extensions, the control marks it
  relocatable (`pg_stat_kcache.control:6`) `[verified-by-code]`.

## Links into corpus

- [[pg_qualstats]] — the closest sibling (same powa-team, same
  `shmem_request`/`shmem_startup` + executor-hook-chain shape, and the same
  proc-number-indexed shmem array to thread a value across the parallel
  leader/worker boundary). pg_stat_kcache is the kernel-accounting analogue of
  pg_qualstats' qual-accounting.
- [[pg_stat_monitor]] — sibling ideology written this same run; another
  pg_stat_statements-adjacent per-query metrics extension, worth contrasting on
  how each relates to pgss's queryid (pg_stat_monitor forks pgss's model; kcache
  depends on and reads it live).
- [[pg_tracing]] — another executor-hook observability extension with its own
  shmem; contrast its self-owned identity against kcache's borrowed queryid.
- [[contrib-pg_stat_statements]] — the subsystem kcache parasitizes: the source
  of the `queryId`, the `{userid,dbid,queryid,top}` key, the usage-decay
  eviction, and the file-dump persistence kcache all copy.
- [[executor]] — the `ExecutorStart`/`Run`/`Finish`/`End` hook points kcache
  brackets with getrusage.
- `.claude/skills/pgstat-framework/SKILL.md` — the pgstat / cumulative-stats
  framework this extension deliberately sidesteps by rolling its own shmem hash
  rather than registering a pgstat kind.
- `.claude/skills/executor-and-planner/SKILL.md` — the executor + planner hook
  surface (`planner_hook`, the executor quartet) kcache layers on.
- [[process-utility-hook-chain]] — the idiom kcache notably does **not** use
  (no `ProcessUtility_hook` installed), despite the nesting comment naming it.

## Sources

All fetched 2026-07-10 (branch `master`; note the readme is `README.rst`, not
`README.md`):

- `https://raw.githubusercontent.com/powa-team/pg_stat_kcache/master/pg_stat_kcache.c`
  → HTTP 200 (1386 lines).
- `https://raw.githubusercontent.com/powa-team/pg_stat_kcache/master/pg_stat_kcache.control`
  → HTTP 200 (6 lines; `default_version = '2.3.2'`,
  `requires = 'pg_stat_statements'`, `relocatable = true`).
- `https://raw.githubusercontent.com/powa-team/pg_stat_kcache/master/README.rst`
  → HTTP 200 (376 lines).
- `https://raw.githubusercontent.com/powa-team/pg_stat_kcache/master/pg_stat_kcache--2.2.0.sql`
  → HTTP 200 (probed with `-w '%{http_code}'`; not read line-by-line — the
  current default is 2.3.2, so this is an older install script).

Gaps: the header `pg_stat_kcache.h` (defines `pgskCounters`, `PGSK_NUMKIND`,
`PG_STAT_KCACHE_COLS*`, and the `RUSAGE_BLOCK_SIZE` constant) was **not** fetched;
the 512-byte block value is cited from `README.rst:336-339` rather than the
`#define`. The current `pg_stat_kcache--2.3.2.sql` install script was not fetched
(only the 2.2.0 probe). All `pg_stat_kcache.c` and `.control` cites are
`[verified-by-code]` against the blobs fetched 2026-07-10; behavior claims tied
to platform (macOS vs Linux getrusage reporting) rest on the README's own caveat
text and are tagged `[from-README]`.
