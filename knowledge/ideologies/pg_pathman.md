# pg_pathman — ideology / divergence-from-core notes

> Extension: `postgrespro/pg_pathman` @ `master` (`pg_pathman.control` reports
> `default_version = '1.5'`, `comment = 'Partitioning tool for PostgreSQL'`).
> One durable "how this diverges from core PG design" doc. All line cites are
> into the upstream **pg_pathman** tree (`src/...`, `pg_pathman.control`), NOT
> into PG `source/`. Confidence tags: `[verified-by-code]` `[from-README]`
> `[from-comment]` `[inferred]` `[unverified]`. Single-line cites are exact
> against the fetched `master` blobs; treat as ±5 lines pending a local clone.
> Project status: upstream README declares it **no longer under development**;
> supports PG 11..15 only, "won't be ported to later releases" because native
> declarative partitioning has matured `[from-README: README.md:5]`.

## Domain & purpose

pg_pathman is the classic **pre-declarative-partitioning** partitioning
extension: it predates and parallels core PG's `PARTITION BY` (PG 10+). It
implements RANGE and HASH partitioning on top of PG's old **table-inheritance**
mechanism (child tables `INHERITS` a parent), but replaces the slow planner
path — core's constraint-exclusion over `CHECK` constraints — with a fast,
purpose-built partition-pruning engine driven by a cached description of each
partitioned table. It stores its partitioning configuration in its own heap
table `pathman_config` (one row per partitioned relation: regclass,
partitioning expression, type, range interval) `[verified-by-code:
pg_pathman.control` semantics in `src/include/pathman.h:47-52]`, caches the
derived partition bounds per-backend, and at plan time walks the query's
`WHERE` tree to select exactly the partitions a query can touch. Its headline
runtime feature is two custom executor nodes — `RuntimeAppend` /
`RuntimeMergeAppend` — that prune partitions **at execution time** when the
partitioning key is compared to a not-yet-known parameter
`[from-README: README.md:69,495-499]`.

## How it hooks into PG

- **Must be in `shared_preload_libraries`.** `_PG_init()` hard-errors if
  `!process_shared_preload_libraries_in_progress`
  `[verified-by-code: src/pg_pathman.c:326-331]`, because it needs shmem and to
  install global hooks at postmaster start.

- **The planner-hook chain.** `_PG_init()` saves the previous value of each
  global hook pointer into a `*_next` slot, then overwrites it — the standard
  cooperative-chaining idiom `[verified-by-code: src/pg_pathman.c:348-361]`:
  - `set_rel_pathlist_hook` → `pathman_rel_pathlist_hook` — the heart of the
    extension (see below).
  - `set_join_pathlist_hook` → `pathman_join_pathlist_hook`.
  - `planner_hook` → `pathman_planner_hook`.
  - `post_parse_analyze_hook` → `pathman_post_parse_analyze_hook`.
  - `ProcessUtility_hook` → `pathman_process_utility_hook` (intercepts COPY,
    and DDL like partition creation/`ALTER`).
  - `ExecutorStart_hook` → `pathman_executor_start_hook`.
  - `shmem_startup_hook` → `pathman_shmem_startup_hook`.

- **`pathman_rel_pathlist_hook` rewrites the append plan by hand.** For a
  partitioned parent it: gets the cached `PartRelationInfo`
  (`get_pathman_relation_info`), walks every `baserestrictinfo` clause through
  `walk_expr_tree()` to build an `IndexRange` set, intersects them to the
  surviving partitions, then **manually expands `root->simple_rel_array` /
  `simple_rte_array` / `append_rel_array`** with `repalloc`+`memset`, calls
  `append_child_relation()` per surviving child, **frees the parent's existing
  pathlist** (`list_free_deep(rel->pathlist); rel->pathlist = NIL;`) and
  rebuilds it with a private copy of core's `set_append_rel_pathlist`
  `[verified-by-code: src/hooks.c:462-561]`. This is far more invasive than a
  typical path-adding hook — it surgically edits the planner's core arrays.

- **CustomScan API for runtime pruning.** `RuntimeAppend` is registered as a
  `CustomScan` node via `RegisterCustomScanMethods(&runtimeappend_plan_methods)`
  with the full method triple — `CustomPathMethods` (`PlanCustomPath`),
  `CustomScanMethods` (`CreateCustomScanState`), and `CustomExecMethods`
  (`BeginCustomScan` / `ExecCustomScan` / `EndCustomScan` / `ReScanCustomScan` /
  `ExplainCustomScan`) `[verified-by-code: src/runtime_append.c:25-55]`.
  `RuntimeMergeAppend` is a sibling registered the same way. In
  `pathman_rel_pathlist_hook`, after building the normal `AppendPath`, if the
  partitioning clauses `clause_contains_params(...)`, it wraps each
  `AppendPath`/`MergeAppendPath` in a `create_runtime_append_path` /
  `create_runtime_merge_append_path` and `add_path`s it as a competitor
  `[verified-by-code: src/hooks.c:566-611]`.

- **Runtime partition selection is in `ReScanCustomScan`.** On each rescan the
  node re-walks `canon_custom_exprs` against the live `ExprContext` (the now-known
  param values), intersects ranges, calls `get_partition_oids()`, then
  `select_required_plans()` to pick only the matching child `PlanState`s out of
  a hashtable keyed by partition Oid
  `[verified-by-code: src/nodes_common.c:824-866, 96-127]`. That per-tuple/per-
  rescan pruning is what core constraint-exclusion (plan-time only) could not do
  pre-PG11 `[from-README: README.md:495-499]`.

- **Shared memory.** The ONLY shmem allocation is the concurrent-partitioning
  bgworker's task-slot array: `_PG_init` requests it via
  `RequestAddinShmemSpace(estimate_pathman_shmem_size())` (PG<15) or the
  `shmem_request_hook` (PG≥15, commit 4f2400cb3f10)
  `[verified-by-code: src/pg_pathman.c:333-339,378-387]`;
  `estimate_pathman_shmem_size()` returns only
  `estimate_concurrent_part_task_slots_size()`
  `[verified-by-code: src/init.c:262-266]`; and `pathman_shmem_startup_hook`
  calls `init_concurrent_part_task_slots()` under `AddinShmemInitLock`
  `[verified-by-code: src/hooks.c:958-968]`.

- **Concurrent-partitioning bgworker.** A dynamic bgworker
  (`RegisterDynamicBackgroundWorker` + `WaitForBackgroundWorkerStartup`) does
  background data migration / partition spawning; it connects via
  `BackgroundWorkerInitializeConnectionByOidCompat` and reports progress through
  the shmem `ConcurrentPartSlot` array `[verified-by-code:
  src/pathman_workers.c:208-219,401,485]`. Each slot is guarded by its own
  `slock_t mutex` spinlock (`cps_check_status`/`cps_set_status` do
  `SpinLockAcquire`/`Release`) `[verified-by-code:
  src/include/pathman_workers.h:69,95-113]`.

## Where it diverges from core idioms

1. **Its own catalog, not `pg_partitioned_table`.** Core declarative
   partitioning records structure in `pg_partitioned_table` + `pg_inherits` +
   per-partition `relpartbound`. pg_pathman instead keeps user-schema heap
   tables `pathman_config` (4 attrs: partrel, expr, parttype, range_interval)
   and `pathman_config_params` (enable_parent, auto, init_callback,
   spawn_using_bgw) `[verified-by-code: src/include/pathman.h:47-66]`. The
   partition relationship itself still rides classic `INHERITS` child tables —
   it diverges from core *declarative* partitioning but reuses core
   *inheritance* `[from-README: README.md:24-29,44]`.

2. **Backend-LOCAL caches, not the relcache and (mostly) not shmem.** Core
   reads partition bounds out of the syscache/relcache. pg_pathman builds its
   own three backend-local `HTAB`s — `parents_cache`, `status_cache`,
   `bounds_cache` — in dedicated MemoryContexts (`PathmanParentsCacheContext`,
   `PathmanStatusCacheContext`, `PathmanBoundsCacheContext`) under a
   `TopPathmanContext` rooted in `TopMemoryContext`
   `[verified-by-code: src/init.c:312-359]`. A `PartRelationInfo` is built
   on-demand by reading the `pathman_config` heap row
   (`build_pathman_relation_info` → `fill_prel_with_partitions`) and cached
   locally `[verified-by-code: src/relation_info.c:330-362,388,726-753]`.
   **NOTE — README vs code drift:** README.md:44 says it "caches some
   information about child partitions in the **shared memory**", but the bounds/
   parents/status caches are per-backend HTABs, not shmem; only the concurrent-
   part task slots live in shmem `[verified-by-code: src/init.c:262-359 vs
   README.md:44]`. Treat the README's "shared memory" wording as imprecise.

3. **Cache coherency via a relcache invalidation callback.** Instead of relying
   on syscache invalidation of catalog rows, pg_pathman registers
   `CacheRegisterRelcacheCallback(pathman_relcache_hook, ...)`
   `[verified-by-code: src/init.c:227-231]`. The callback hand-invalidates its
   three local caches: a global event (`relid == InvalidOid`) flushes all three
   (`invalidate_bounds_cache` / `_parents_` / `_status_`); a per-table event
   (`relid >= FirstNormalObjectId`) calls `forget_bounds_of_rel` /
   `forget_status_of_relation` / `forget_parent_of_partition`
   `[verified-by-code: src/hooks.c:973-1017]`. Coherency is the extension's
   manual responsibility.

4. **CustomScan + planner-array surgery vs native pruning.** Core PG11+ does
   plan-time partition pruning (`PartitionPruneInfo`) and runtime pruning inside
   the regular `Append`/`MergeAppend` nodes. pg_pathman predates that and instead
   (a) edits `PlannerInfo` arrays directly to inject children, and (b) ships
   whole new `CustomScan` executor nodes (`RuntimeAppend`) that keep a hashtable
   of child plan-states and choose among them at rescan. This is "reimplement the
   Append node" rather than "extend the planner" `[verified-by-code:
   src/hooks.c:485-543; src/nodes_common.c:824-866; src/runtime_append.c:25-55]`.

5. **Copy of core planner code, version-gated.** Rather than call PG-internal
   statics, pg_pathman vendors copies of `set_append_rel_pathlist`,
   `make_inh_translation_list`, `translate_col_privs`,
   `get_cheapest_parameterized_child_path` (declared "Copied from PostgreSQL")
   `[verified-by-code: src/include/pathman.h:118-135]`, plus a heavy
   `src/compat/pg_compat.{c,h}` shim layer and `#if PG_VERSION_NUM` branches
   throughout (e.g. the `repalloc` of `append_rel_array` is PG11+-only)
   `[verified-by-code: src/hooks.c:507-520]`. Cross-version source-compat is a
   first-class concern — the cost of tracking a fast-moving core API from
   outside.

6. **Spinlocks for shmem, not LWLock tranches.** The shmem state it does own
   (task slots) is protected by per-slot `slock_t` spinlocks taken for the
   trivial status read/write `[verified-by-code:
   src/include/pathman_workers.h:69,100-112; src/pathman_workers.c:667-794]`,
   with `AddinShmemInitLock` only for the one-time allocation
   `[verified-by-code: src/hooks.c:965-967]`. It does not register a named
   LWLock tranche — its concurrency surface in shmem is small.

7. **Per-prel MemoryContext + a resowner leak-tracker.** Each `PartRelationInfo`
   gets its own `prel->mcxt`; freeing is `MemoryContextDelete(prel->mcxt)`
   `[verified-by-code: src/relation_info.c:391-451,565]`. Under
   `USE_ASSERT_CHECKING` it keeps a `prel_resowner` HTAB recording the
   acquire-site `function:line` of each open prel to catch leaks across resource
   owners `[verified-by-code: src/relation_info.c:69-80,120-142,571-605]` — a
   bespoke lifetime discipline because prels are ref-counted handles, not plain
   palloc'd structs.

## Notable design decisions (with cites)

- **Two custom nodes share one implementation core.** `RuntimeAppend` and
  `RuntimeMergeAppend` both funnel through `create_append_path_common` /
  `create_append_plan_common` / `create_append_scan_state_common` /
  `begin_append_common` / `exec_append_common` / `rescan_append_common` in
  `nodes_common.c`; the per-node files are thin wrappers
  `[verified-by-code: src/runtime_append.c:57-148; src/nodes_common.c:494-866]`.
  There is even a runtime assert that `offsetof(AppendPath, subpaths) ==
  offsetof(MergeAppendPath, subpaths)` before treating them interchangeably
  `[verified-by-code: src/hooks.c:599-603]`.

- **Each runtime node toggleable by GUC.** `init_runtime_append_static_data`
  defines `pg_pathman.enable_runtimeappend` (PGC_USERSET, default true)
  `[verified-by-code: src/runtime_append.c:43-52]`; a master
  `pg_pathman.enable` plus `enable_auto_partition` / `override_copy` gate the
  whole extension `[verified-by-code: src/include/pathman.h:39-41]`.

- **Pruning algebra is an IndexRange set.** Partition selection is expressed as
  intersection/union of `IndexRange`s over the ordered partition array
  (`list_make1_irange_full`, `irange_list_intersection`,
  `select_range_partitions`) — a compact rangeset calculus rather than
  per-partition boolean constraint tests
  `[verified-by-code: src/hooks.c:463-477; src/include/pathman.h:172-178]`.

- **HASH pruning is `value % nparts`.** `hash_to_part_index` is literally
  `value % partitions` `[verified-by-code: src/include/pathman.h:182-186]` —
  simpler than core's hash-partition modulus/remainder scheme.

- **DDL/COPY interception via `ProcessUtility_hook`.** COPY into a partitioned
  parent and partition-management DDL are caught in
  `pathman_process_utility_hook`, which may fully handle the statement and skip
  `standard_ProcessUtility` `[verified-by-code: src/hooks.c:1032-1185]`.

- **Optional per-partition init callback + bgworker spawn.** `pathman_config_params`
  carries `init_callback` and `spawn_using_bgw` so new partitions can be created
  lazily and/or in a background worker on insert
  `[verified-by-code: src/include/pathman.h:64-66; src/pathman_workers.c:184-219]`.

## Links into corpus

- Executor: [[knowledge/subsystems/executor]] — the `CustomScan` /
  `CustomScanState` lifecycle (`BeginCustomScan` / `ExecCustomScan` /
  `ReScanCustomScan`) that `RuntimeAppend` implements; contrast with native
  `Append`/`MergeAppend` runtime pruning.
- Optimizer: [[knowledge/subsystems/optimizer]] — `set_rel_pathlist_hook`,
  `RelOptInfo`/`PlannerInfo` arrays, `add_path` cost competition, append-rel
  expansion. pg_pathman edits these arrays by hand.
- Partitioning: [[knowledge/subsystems/partitioning]] — the core
  `pg_partitioned_table` / `pg_inherits` / `relpartbound` machinery pg_pathman
  predates and replaces; useful side-by-side for the inheritance-vs-declarative
  divergence.
- Extension idioms: [[knowledge/idioms/bgworker-and-extensions]] — the dynamic
  concurrent-partitioning worker + hook-chaining on `_PG_init`.
- [[knowledge/idioms/memory-contexts]] — the per-prel `mcxt`, the three
  cache contexts, and the resowner leak-tracker.
- [[knowledge/idioms/gucs-config]] — `pg_pathman.enable*`,
  `enable_runtimeappend`, `enable_runtime_merge_append`.
- **Sibling "CustomScan / planner-hook" ideologies:** any extension that ships a
  `CustomScan` node (vs pg_pathman's append-replacement) — contrast the
  hook-and-rewrite approach here with core's later `PartitionPruneInfo`, the
  case study for "what an extension does when core hasn't shipped the feature yet."

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/postgrespro/pg_pathman/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/pg_pathman.control | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/README.md | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/pg_pathman.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/include/pathman.h | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/hooks.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/init.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/runtime_append.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/nodes_common.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/relation_info.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/pathman_workers.c | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/include/pathman_workers.h | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/include/relation_info.h | 200 |
| https://raw.githubusercontent.com/postgrespro/pg_pathman/master/src/include/runtime_append.h | 200 |

**Fetch notes / gaps:**
- No 404s. The manifest hint named `src/pg_pathman.c` and `src/include/pathman.h`
  (both present); all other paths were verified against the live tree listing.
- Key correction over the prompt's hint: the **partition-bounds dispatch cache is
  backend-LOCAL** (`parents_cache`/`status_cache`/`bounds_cache` HTABs in
  `TopMemoryContext`), built per-backend from the `pathman_config` heap table and
  kept coherent by a relcache-invalidation callback — it is NOT in shared memory.
  The README's "caches ... in the shared memory" phrasing (README.md:44) is
  imprecise; the only true shmem is the concurrent-partitioning bgworker task-slot
  array. Documented as drift above.
- `runtime_merge_append.c`, `partition_filter.c`, `partition_router.c`,
  `partition_overseer.c`, `declarative.c`, `utility_stmt_hooking.c` were seen in
  the tree and named via `_PG_init` wiring but not read line-by-line; claims about
  them are `[inferred]` from registration sites.
