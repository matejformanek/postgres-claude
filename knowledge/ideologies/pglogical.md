# pglogical — a complete logical-replication stack built as an extension, predating core pub/sub

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `2ndQuadrant/pglogical` @ branch `REL2_x_STABLE`. All `file:line` cites
> below point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> files fetched on 2026-06-06 (see Sources footer).

## Domain & purpose

pglogical 2 implements **logical streaming replication** for PostgreSQL with a
publish/subscribe model: a *provider* node decodes its WAL into a logical change
stream, and *subscriber* nodes apply those changes, with replication sets (table
collections), row/column filtering, conflict detection and resolution, and
sequence replication (`docs/README.md:1-30`). It descends from the BDR
multi-master project and is the ancestor of EDB's Postgres Distributed
(`docs/README.md:6-13`). The crucial context for an anthropologist: pglogical
was built **before core PostgreSQL had built-in logical replication** (core
pub/sub landed in PG10; pglogical targets PG 9.4+). So it is a near-complete
re-implementation, *as an out-of-tree extension*, of a subsystem that core later
absorbed — the single best case study in this corpus of "extension as
proving-ground for a future core feature". Almost everything it does diverges
from core idioms simply because core hadn't yet defined the idiom.

## How it hooks into PG

It hooks in along **two independent axes** that core's logical replication keeps
internal:

1. **As a logical-decoding output plugin** (the provider side).
   `_PG_output_plugin_init` (`pglogical_output_plugin.c:94-105`) registers the
   standard decoding callbacks — `startup_cb`/`begin_cb`/`change_cb`/`commit_cb`/
   `shutdown_cb` plus `filter_by_origin_cb` (`pglogical_output_plugin.c:98-105`)
   `[verified-by-code]`. This is the same plugin contract `test_decoding` and
   core's `pgoutput` use.

2. **As a tree of background workers** (the subscriber/control side).
   `_PG_init` *insists* on being in `shared_preload_libraries` —
   `if (!process_shared_preload_libraries_in_progress) elog(ERROR, "pglogical is
   not in shared_preload_libraries")` (`pglogical.c:777-778`) — then defines a
   stack of GUCs (`pglogical.conflict_resolution`, `.conflict_log_level`,
   `.synchronous_commit`, `.use_spi`, `.batch_inserts`, `.temp_directory`,
   `.extra_connection_options`, `pglogical.c:780-861`), chains
   `shmem_request_hook` to reserve its worker registry
   (`pglogical.c:862-863`), and registers **one static supervisor bgworker**
   (`pglogical.c:873-884`, `BgWorkerStart_RecoveryFinished`, `bgw_restart_time =
   5`) `[verified-by-code]`.

The control file pins `schema = pglogical`, `relocatable = false`
(`pglogical.control.in:5-7`).

## Where it diverges from core idioms

### 1. A three-tier background-worker supervision tree, hand-built

Core's logical replication has a `LogicalRepLauncher` → per-subscription apply
worker model. pglogical builds its own deeper hierarchy by hand: the static
**supervisor** (one per cluster, from `_PG_init`) spawns a per-database
**manager**, which spawns per-subscription **apply** and **sync** workers, all
as *dynamic* bgworkers. The dispatcher is `pglogical_worker_register`
(`pglogical_worker.c:146-188`): it fills a `BackgroundWorker` whose
`bgw_function_name` is chosen by worker type — `pglogical_manager_main`,
`pglogical_sync_main`, or `pglogical_apply_main`
(`pglogical_worker.c:151-174`) — with `bgw_restart_time = BGW_NEVER_RESTART` and
`bgw_notify_pid = MyProcPid`, then `RegisterDynamicBackgroundWorker`
(`:176-188`). Worker slots live in a fixed shmem array `PGLogicalCtx->workers[]`
guarded by an LWLock (`pglogical_worker.c:87-143`, with
`Assert(LWLockHeldByMe(PGLogicalCtx->lock))`), and each worker `attach`es to its
slot under `LW_EXCLUSIVE` (`:308-353`). This is a full process-supervision
framework — slot allocation, startup handshake (`wait_for_worker_startup`,
`:188`), crash bookkeeping — re-implementing what core later baked into
`logical/launcher.c`. Cross-ref `[[knowledge/subsystems/replication]]`,
`.claude/skills/gucs-bgworker-parallel/SKILL.md`,
`.claude/skills/locking/SKILL.md`.

### 2. The apply side is a vtable with two interchangeable backends (heap vs SPI)

Core's apply path applies changes by calling the heap/table-AM directly.
pglogical abstracts apply behind a function-pointer table,
`PGLogicalApplyFunctions` (`pglogical_apply.c:103`), with members
`.on_begin`/`.on_commit`/`.do_insert`/`.do_update`/`.do_delete` plus a
multi-insert sub-API (`.can_multi_insert`/`.multi_insert_add_tuple`/
`.multi_insert_finish`, `:100-114`). The default binding is the **heap** backend
(`pglogical_apply_heap_*`, `:105-115`), but a parallel **SPI** backend
(`pglogical_apply_spi.c`, gated by the `pglogical.use_spi` GUC,
`pglogical.c:811`) applies the same changes by issuing SQL through SPI instead.
Shipping two complete apply implementations — one low-level table-AM, one
SPI/SQL — behind a vtable, selectable at runtime, is a design core never needed
because core only ever had the one. Cross-ref `[[knowledge/subsystems/executor]]`,
`.claude/skills/fmgr-and-spi/SKILL.md`, `[[knowledge/idioms/tableam]]`.

### 3. Configurable conflict *resolution*, years before core had conflict *detection*

pglogical ships `pglogical.conflict_resolution` as a
`DefineCustomEnumVariable` with a `pglogical_conflict_resolver_check_hook`
(`pglogical.c:780-792`) and a whole `pglogical_conflict.h` machinery
(`pglogical_apply.c:62`). On commit it stamps the apply session's origin
identity and timestamp (`replorigin_session_origin_timestamp`/`_lsn`,
`pglogical_apply.c:295-296,343-354`) so last-update-wins style resolution can
compare commit times across nodes. Core only grew *conflict detection* (not
automatic resolution) much later and more narrowly; pglogical offered
user-selectable resolution policies as a first-class GUC from early on.
Cross-ref `[[knowledge/subsystems/replication]]`.

### 4. Hooks layered on top of the output-plugin hooks

The output plugin is not the bottom of pglogical's extensibility — it exposes a
*second* pluggable layer. The provider can name a `"hooks.setup_function"`
(`pglogical.c:552`) that installs row/origin/transaction filter callbacks the
decoder then invokes per change. So pglogical stacks its own user-pluggable hook
framework on top of the logical-decoding callback framework — hooks on hooks —
to let downstream tools (BDR) inject filtering without forking the plugin.
Cross-ref `.claude/skills/extension-development/SKILL.md` (hook chaining).

### 5. Origin-filtered decoding for multi-master loop prevention

`pg_decode_origin_filter` (`pglogical_output_plugin.c:785`) is wired as the
`filter_by_origin_cb` so a node can refuse to re-emit changes that originated
elsewhere — the cornerstone of avoiding infinite replication loops in a mesh.
The apply worker correspondingly sets `replorigin_session_origin` and replays
the origin LSN/timestamp (`pglogical_apply.c:228-231,295-296`). Replication
origins are a core facility, but pglogical's use of them to build *multi-master*
topologies on top of single-source logical decoding is well beyond the
single-publisher model core's pub/sub assumes. Cross-ref
`[[knowledge/subsystems/replication]]`.

## Notable design decisions (cited)

- **Supervisor restarts, workers don't.** The supervisor has `bgw_restart_time =
  5` (`pglogical.c:882`) so it always comes back; managers/apply workers use
  `BGW_NEVER_RESTART` (`pglogical_worker.c:176`) and are instead re-launched
  *by* the supervisor/manager — restart policy is centralized, not delegated to
  the postmaster.
- **`application_name` is set to the bgworker name** on attach
  (`pglogical_worker.c:359`, also `pglogical.c:678`) so `pg_stat_activity`
  shows which pglogical worker is which.
- **Batch / multi-insert apply.** The `pglogical.batch_inserts` GUC
  (`pglogical.c:824`) and the multi-insert vtable members let the heap backend
  COPY-style batch incoming inserts rather than row-at-a-time.
- **Own temp directory with an assign hook.** `pglogical.temp_directory` uses a
  `pglogical_temp_directory_assing_hook` (`pglogical.c:838-846`) for spooling
  sync data — managing its own on-disk scratch space outside core's temp-file
  machinery.
- **Still `PG_MODULE_MAGIC;` (bare form), not `_EXT`** (`pglogical.c:60`) —
  consistent with a codebase that must compile back to PG 9.4.

## Links into corpus

- `[[knowledge/subsystems/replication]]` — logical decoding output-plugin
  callbacks, replication origins, and the apply-worker model pglogical
  re-implements and extends into multi-master.
- `[[knowledge/idioms/tableam]]` — the heap apply backend that calls the
  table-AM directly, vs the SPI backend.
- `.claude/skills/gucs-bgworker-parallel/SKILL.md` — the static-supervisor +
  dynamic-worker registration pattern and the shmem worker registry.
- `.claude/skills/locking/SKILL.md` — the `PGLogicalCtx->lock` LWLock guarding
  the worker-slot array.
- `.claude/skills/fmgr-and-spi/SKILL.md` — the SPI apply backend.
- `[[knowledge/ideologies/pg_cron]]` — the other bgworker-centric extension in
  this corpus; pg_cron runs one launcher, pglogical runs a supervision *tree*.

## Sources

Fetched 2026-06-06 (branch `REL2_x_STABLE`). The root `README.md` is a symlink
(git mode `120000`) → `docs/README.md`, so the real readme was fetched from
`docs/README.md`. Manifest files `pglogical.h` and `pglogical_apply.c` fetched;
added `pglogical.c` (init/GUCs/supervisor), `pglogical_worker.c` (worker tree),
`pglogical_output_plugin.c` (output-plugin callbacks), and `pglogical.control.in`
to cover the worker/decoding/apply story the manifest's two files only hint at.

- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/README.md`
  @ 2026-06-06 → HTTP 200 (0 lines; symlink → `docs/README.md`).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/docs/README.md`
  @ 2026-06-06 → HTTP 200 (44 KB).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/pglogical.h`
  @ 2026-06-06 → HTTP 200 (147 lines).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/pglogical.c`
  @ 2026-06-06 → HTTP 200 (885 lines).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/pglogical_worker.c`
  @ 2026-06-06 → HTTP 200 (753 lines).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/pglogical_apply.c`
  @ 2026-06-06 → HTTP 200 (2051 lines).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/pglogical_output_plugin.c`
  @ 2026-06-06 → HTTP 200 (1071 lines).
- `https://raw.githubusercontent.com/2ndQuadrant/pglogical/REL2_x_STABLE/pglogical.control.in`
  @ 2026-06-06 → HTTP 200 (7 lines).
- Tree listing
  `https://api.github.com/repos/2ndQuadrant/pglogical/git/trees/REL2_x_STABLE?recursive=1`
  @ 2026-06-06 → HTTP 200 (238 paths).

Cites into `pglogical.c`, `pglogical_worker.c`, `pglogical_output_plugin.c`, and
the `apply_api` vtable in `pglogical_apply.c` are `[verified-by-code]` against
the fetched files. The conflict-*resolution* policy semantics are
`[verified-by-code]` for the GUC/hook wiring and `[from-README]` for the
end-to-end behavior (`docs/README.md`); the SPI apply backend
(`pglogical_apply_spi.c`) was identified via the `.use_spi` GUC and the
`pglogical_apply_spi.h` include but its body was not fetched this run.
</content>
