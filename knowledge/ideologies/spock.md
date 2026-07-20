# spock — multi-master active-active replication that ships as an extension *plus* a patched Postgres core

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgedge/spock` @ branch `main`. All `file:line` cites below point into
> that repo (raw.githubusercontent.com), NOT into PG `source/`, since this doc
> characterizes an *external* extension's divergence from core idioms. Fetched
> 2026-07-19 (see Sources footer).
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.

## Domain & purpose

Spock is pgEdge's **multi-master (active-active) logical replication** extension:
every node in a cluster accepts writes and replicates them to every peer, with
conflict detection + resolution, replication sets, automatic DDL replication,
Snowflake sequences, and a read-only mode `[from-README: README.md:1,46-48]`. It
targets PostgreSQL 15–19 `[from-README: README.md:48]`. Architecturally it is the
direct successor / fork of **pgLogical2** (2ndQuadrant), and the README states an
old node "can be running a recent version of pgLogical2 before upgrading it to
become a Spock node" `[from-README: README.md:50]` — the same output-plugin +
bgworker + apply-worker skeleton as [[pglogical]], evolved into a full
active-active engine. The control file still describes it as
`comment = 'PostgreSQL Logical Replication'` `[verified-by-code:
spock.control.in:2]`.

The load-bearing divergence, and the thing that separates Spock from **every
other replication extension in this corpus**, is that Spock **does not build
against stock PostgreSQL**. It requires version-specific `.diff` patches applied
to the Postgres *source tree* before you compile the server, and only then do you
build the extension against that patched install.

## How it hooks into PG

Spock bolts onto core through the full extension seam surface, and then reaches
*past* it into patched-core hooks that stock PG does not expose:

- **`shared_preload_libraries` + `_PG_init`.** `_PG_init()`
  (`src/spock.c:1004`) refuses to load unless preloaded —
  `if (!process_shared_preload_libraries_in_progress) elog(ERROR, "spock is not
  in shared_preload_libraries")` `[verified-by-code: src/spock.c:1008-1009]` —
  then defines ~30 `spock.*` GUCs via `DefineCustom*Variable`
  (`src/spock.c:1011-1341`) `[verified-by-code]`.
- **A logical-decoding output plugin, built as a *separate* module.** The
  Makefile builds `spock` as `MODULE_big` but compiles `spock_output` as a
  standalone `MODULES` object (`src/spock_output.c`), filtered out of the main
  `OBJS` list `[verified-by-code: Makefile:7,11,19,48]`. This is the *send* side:
  a walsender running the plugin decodes one node's WAL into the Spock wire
  protocol. `[inferred]` from the build wiring; the plugin body was not fetched
  this run.
- **A static supervisor background worker.** `_PG_init` registers one static
  bgworker with `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
  `bgw_start_time = BgWorkerStart_RecoveryFinished`, `bgw_function_name =
  "spock_supervisor_main"`, and `bgw_restart_time = 5`
  `[verified-by-code: src/spock.c:1356-1368]`. The supervisor records itself in
  shmem (`SpockCtx->supervisor = MyProc`, `src/spock.c:811`) and spawns
  per-database managers + per-subscription apply workers — the same
  supervisor→manager→apply tree [[pglogical]] and [[pgactive]] build
  `[inferred]`.
- **Apply workers as ordinary backends writing tagged changes.** The apply side
  dispatches remote begin/commit/insert/update/delete
  (`handle_commit` `src/spock_apply.c:833`, `handle_insert` `:1422`,
  `handle_update` `:1607`, `handle_delete` `:1741`) and applies rows through the
  heap (`spock_apply_heap_insert`, `src/spock_apply.c:1517`) `[verified-by-code]`.
  A `spock.use_spi` GUC path exists as an alternate apply backend
  (`include/spock.h:42`) `[verified-by-code]`, mirroring pglogical's heap-vs-SPI
  vtable.
- **A custom WAL resource manager + own shmem.** `_PG_init` calls
  `spock_rmgr_init()` then `spock_shmem_init()` and `spock_executor_init()`
  before launching the supervisor `[verified-by-code: src/spock.c:1347-1353]`.
  The custom `rmgr` is itself a patched-core-adjacent facility (custom rmgrs are
  a PG 15+ core feature, but Spock also ships a failover-slot hook,
  `spock_init_failover_slot()`, `src/spock.c:1370`) `[verified-by-code]`.
- **`emit_log_hook` chaining.** It saves and chains the previous
  `emit_log_hook` to install `log_message_filter`
  `[verified-by-code: src/spock.c:184,1373-1374,937-938]`.
- **Custom catalogs in a `spock` schema** (`schema = spock`, `relocatable =
  false`, `src/spock.control.in:5-6`): `spock.node` (with a per-node
  `tiebreaker`), `spock.exception_log`, and a conflict/resolutions log table
  `[verified-by-code: src/spock_node.c:188,334-367;
  src/spock_exception_handler.c:75,114; src/spock_conflict.c:623-757]`.

## Where it diverges from core idioms

### 1. Core-patching: Spock does not build against stock Postgres — THE headline divergence

Almost every other extension in this corpus ([[pglogical]], [[pgactive]],
[[synchdb]]) loads into an *unmodified* core server through the documented
extension ABI. Spock breaks that contract at the root. The README's "Building the
Spock Extension" section is explicit: "You will need to build the Spock extension
on a **patched PostgreSQL source tree** to which you have applied version-specific
`.diff` files from the `spock/patches/Postgres-version` directory"
`[from-README: README.md:106-108]`. The build order is: get the Postgres source,
copy the patch files, `patch -p1 < path_to_patch/patch_name` **in numerical
prefix order** (`pg16-015-…`, then `pg16-020-…`, then `pg16-025-…`), then
`configure`/`make`/`make install` the *server*, and only then build Spock against
the resulting `pg_config` `[from-README: README.md:108-128]`.

The Makefile corroborates that these patches are a real dependency of behavior,
not documentation boilerplate: a comment notes a build tweak "allows spock tests
to run without the `pg*-090-init_template_fix.diff` patch applied to PostgreSQL"
`[verified-by-code + from-comment: Makefile:90-91]` — i.e. the patch set is
version-prefixed (`pgNN-NNN-name.diff`) and normally assumed present.

**What the patches are for `[inferred from cite evidence; patch bodies not
fetched]`:** the code reaches for facilities core does not hand an out-of-tree
extension cleanly — WAL-reader / decoding internals, commit-timestamp lookup on
arbitrary xids, replication-origin plumbing, and failover-slot support. Direct
evidence of the "past the ABI" reach: `get_tuple_origin` calls
`TransactionIdGetCommitTsData(*xmin, …)` directly on a heap tuple's xmin
(`src/spock_conflict.c:253,267`) and even documents a core bug it works around —
"Pg emits an ERROR if you try to pass FrozenTransactionId (2) or
BootstrapTransactionId (1) to TransactionIdGetCommitTsData, per RT#46983 . This
seems like an oversight in the core function" `[verified-by-code + from-comment:
src/spock_conflict.c:234-246]`. `spock_init_failover_slot()`
(`src/spock.c:1370`) and the custom rmgr (`spock_rmgr_init()`, `src/spock.c:1347`)
are the other tells. This is the corpus's clearest example of an extension that
treats core as *co-modifiable*, not a fixed platform.

### 2. Conflict *resolution* (not just detection), driven by commit timestamps

Core logical replication is deliberately single-master and resolves nothing;
core PG 16+ added `track_commit_timestamp`-based conflict **detection** but not
automatic **resolution**. Spock ships full resolution. The
`spock.conflict_resolution` GUC is a `DefineCustomEnumVariable` defaulting to
`SPOCK_RESOLVE_LAST_UPDATE_WINS` with a check hook
`[verified-by-code: src/spock.c:1011-1019]`. `try_resolve_conflict` switches on
the resolver and, for last/first-update-wins, calls
`conflict_resolve_by_timestamp` `[verified-by-code: src/spock_conflict.c:278-325]`,
which compares commit timestamps with `timestamptz_cmp_internal(remote_ts,
local_ts)` and inverts the comparison for first-update-wins
`[verified-by-code: src/spock_conflict.c:108-116]`.

The conflict taxonomy is a 7-value enum — `insert_exists`,
`update_origin_differs`, `update_exists`, `update_missing`,
`delete_origin_differs`, `delete_missing`, `delete_exists`
`[verified-by-code: src/spock_conflict.c:63-86]` — richer than core's model. Two
design details stand out:

- **Deterministic tiebreak on equal timestamps.** When commit timestamps tie,
  Spock breaks the tie on a per-node `tiebreaker` integer read from
  `spock.node.info` JSONB (falling back to the node id)
  `[verified-by-code: src/spock_conflict.c:163-198; src/spock_node.c:334-367]`.
  Equal tiebreakers trigger a `WARNING` and apply-remote
  `[verified-by-code: src/spock_conflict.c:163-183]`. This is the same
  converge-identically-on-all-nodes discipline [[pgactive]] implements with
  `node_seq_id`.
- **Same-origin changes are not conflicts.** `spock_report_conflict` early-returns
  for `UPDATE_EXISTS` / `DELETE_ORIGIN_DIFFERS` when the local tuple's origin
  equals `replorigin_session_origin`, or when the row was written in the current
  transaction `[verified-by-code: src/spock_conflict.c:391-404]` — loop / echo
  suppression via replication origins, the multi-master cornerstone.

The check hook enforces the commit-timestamp dependency: `apply_remote` and
`error` are the only resolvers allowed with `track_commit_timestamp` off, because
otherwise "there is no way to know where the local tuple originated from"
`[verified-by-code + from-comment: src/spock_conflict.c:793-810]`. The README
correspondingly requires `track_commit_timestamp = on` for conflict resolution
`[from-README: README.md:134,193]`. Note the shipped GUC currently exposes only
`last_update_wins`; `error`, `apply_remote`, `keep_local`, and
`first_update_wins` are compiled but commented out of the enum-options table
"until we can clearly define their desired behavior. Jan Wieck 2024-08-12"
`[verified-by-code + from-comment: src/spock.c:81-92]`.

### 3. Exception handler: apply errors are logged + skipped, not fatal

Core's apply worker treats an error as terminal: the change fails, the worker
errors out, the subscription stalls and retries the same transaction forever.
Spock instead has a configurable **exception handler**
(`spock.exception_behaviour` / `spock.exception_logging` GUCs,
`src/spock.c:1030-1046`) that lets a failed apply be *skipped* and recorded. The
behaviours are `DISCARD`, `TRANSDISCARD`, and `SUB_DISABLE` (defaults
`exception_behaviour = TRANSDISCARD`, `exception_logging = LOG_ALL`,
`src/spock_exception_handler.c:78-79`) `[verified-by-code]`.

- **`DISCARD` wraps each DML in an internal subtransaction.** `handle_insert`
  (and update/delete) run `BeginInternalSubTransaction(NULL)` →
  `spock_apply_heap_insert` → `ReleaseCurrentSubTransaction` inside `PG_TRY`, and
  on `PG_CATCH` set `failed`/`xact_had_exception`, `CopyErrorData()`,
  `FlushErrorState()`, `RollbackAndReleaseCurrentSubTransaction()`, then
  `log_insert_exception(...)` — the worker survives, the row is skipped
  `[verified-by-code: src/spock_apply.c:1485-1547]`. This is the exact
  longjmp-safe subtransaction-rollback idiom core uses for savepoints, repurposed
  to make apply errors non-fatal.
- **`TRANSDISCARD` / `SUB_DISABLE` skip the DML and log directly**, marking the
  apply transaction read-only but still writing to `spock.exception_log`, which
  is flagged `user_catalog_table = true` so `CatalogTupleInsert` works in a
  read-only xact `[verified-by-code + from-comment: src/spock_apply.c:1487-1508]`.
- **The exception log is a 16-column catalog table.** `add_entry_to_exception_log`
  captures remote origin, remote/local commit timestamps, remote xid, schema /
  table / operation, the local tuple and remote old/new tuples rendered as
  `jsonb`, DDL statement/user, and the error message; it `table_openrv`s
  `spock.exception_log`, `CatalogTupleInsert`s, then `FlushErrorState()` +
  `CommandCounterIncrement()` `[verified-by-code:
  src/spock_exception_handler.c:56-72,86-214]`.
- **`SUB_DISABLE` suspends the subscription** rather than skipping: it sets
  `sub->enabled = false`, `alter_subscription(sub)`, logs a `SUB_DISABLE`
  exception row with the `skip_lsn`, and warns
  `[verified-by-code: src/spock_exception_handler.c:231-277]`. A dedicated
  `spock.restart_delay_on_exception` GUC (default 0 ms) tunes the apply-worker
  restart delay on exception `[verified-by-code: src/spock.c:1226-1237;
  include/spock.h:50]`.

### 4. Read-only mode via the `transaction_read_only` GUC + parse/executor hooks

`spock_readonly.c` makes a node reject writes by *reusing core's own read-only
machinery* rather than inventing one. The `spock.readonly` GUC
(`DefineCustomEnumVariable`, `src/spock.c:1287`) has `OFF` / `LOCAL` / `ALL`
levels (`spock_readonly = READONLY_OFF` default,
`src/spock_readonly.c:42`). The mechanism: a post-parse-analyze hook
(`spock_ropost_parse_analyze`) and an `ExecutorStart` hook
(`spock_roExecutorStart`) set core's `XactReadOnly = true` for non-superusers
when `spock_readonly >= READONLY_LOCAL`, and restore it otherwise
`[verified-by-code: src/spock_readonly.c:82-138]`. The file comment is explicit
that it "employs the `transaction_read_only` GUC to disable attempts to execute
DML or DDL", and in `ALL` mode blocks even Spock's own apply workers
`[from-comment: src/spock_readonly.c:1-11]`. It relies on the fact that "core uses
the `XactReadOnly` value directly, not through the `GetConfigOption` function"
`[verified-by-code + from-comment: src/spock_readonly.c:89-97]` — a deliberate
piggyback on a core internal. `spockro_terminate_active_transactions()` force-cancels
in-flight writers via `GetCurrentVirtualXIDs` +
`SignalRecoveryConflictWithVirtualXID` (PG 19) / `CancelVirtualTransaction`
(pre-19) `[verified-by-code: src/spock_readonly.c:50-80]`.

### 5. Memory / locking / WAL implications

- **Commit-timestamp reads on arbitrary xids** are on the hot apply path
  (`get_tuple_origin`, `src/spock_conflict.c:216-271`), which is why
  `track_commit_timestamp` is a hard operational requirement, not an optimization
  — with it off, `get_tuple_origin` returns "all local tuples came from remote"
  and UPDATEs are silently not detected as conflicts
  `[verified-by-code + from-comment: src/spock_conflict.c:202-232]`.
- **Subtransaction-per-DML in DISCARD mode** means each skipped row costs a real
  `BeginInternalSubTransaction`/`Rollback` cycle and a subxid
  `[verified-by-code: src/spock_apply.c:1513-1533]` — an XID-consumption / SLRU
  pressure profile core apply never incurs.
- **A replay queue with spill-to-disk.** The apply worker buffers changes in an
  `ApplyReplayEntry` linked list bounded by `spock.exception_replay_queue_size`,
  spilling to a `BufFile` when large, so a transaction can be *re-played* in
  read-only dry-run form during exception handling
  `[verified-by-code: src/spock_apply.c:130-148,282-283; src/spock.c:1272-1284]`.
- **Custom WAL rmgr + failover slots** (`spock_rmgr_init`, `src/spock.c:1347`;
  `spock_init_failover_slot`, `:1370`) put Spock into the WAL/recovery path in a
  way a pure output-plugin+apply extension does not `[verified-by-code]`.
- **`IsBinaryUpgrade` early-out.** `_PG_init` skips rmgr/shmem/executor init and
  supervisor launch under `pg_upgrade` `[verified-by-code: src/spock.c:1343-1344]`.

## Notable design decisions

- **Supervisor restarts (`bgw_restart_time = 5`), like pglogical's supervisor**
  `[verified-by-code: src/spock.c:1366]`; workers below are relaunched by the
  supervisor/manager (`SpockCtx->subscriptions_changed` signalling,
  `src/spock.c:812,833-840`) `[verified-by-code]`.
- **Per-node integer `tiebreaker` stored in `spock.node.info` JSONB**, extracted
  with a `jsonb`-field lookup and defaulted to the node id when absent
  `[verified-by-code: src/spock_node.c:334-367]`.
- **Conflict resolutions optionally persisted** to a `spock.resolutions` table,
  gated by `spock.save_resolutions` (default off) with a
  `spock.resolutions_retention_days` (default 100) retention GUC
  `[verified-by-code: src/spock.c:1062-1079; src/spock_conflict.c:623-757]`.
- **`spock.log_verbosity` promotes Spock's own DEBUG1/DEBUG2 to LOG** rather than
  flipping global `log_min_messages`, via the `SPOCK_DEBUG1/2` macros — a
  workaround for PG having "only a single, global log threshold"
  `[verified-by-code + from-comment: include/spock.h:61-112]`.
- **Automatic DDL replication** via `spock.enable_ddl_replication` /
  `spock.include_ddl_repset` GUCs (`src/spock.c:1186-1202`) and a
  `hooks.setup_function 'spock.spock_hooks_setup'` output-plugin hook string
  `[verified-by-code: src/spock.c:629,1186-1202]` — the hooks-on-hooks pattern
  inherited from pglogical.
- **Snowflake sequences** are a first-class node concept
  (`src/spock_node.c:123-145`), the multi-master answer to `serial` collisions,
  same idea as [[pgactive]]'s Snowflake id generator `[verified-by-code]`.
- **Version-compat shims** (`src/compat/$(PGVER)/`) plus `#if PG_VERSION_NUM`
  branches for PG 18/19 signature changes (e.g. read-only cancel API,
  `post_parse_analyze` `JumbleState` const-ness)
  `[verified-by-code: Makefile:13-17; src/spock_readonly.c:28-31,65-77,83-87]`.

## Links into corpus

- **Sibling ideologies:**
  - [[pglogical]] — Spock's direct ancestor (README says a pgLogical2 node
    upgrades into a Spock node, `README.md:50`). Same supervisor→manager→apply
    worker tree, same output-plugin + `hooks.setup_function` layering, same
    heap-vs-SPI apply option. **Contrast:** pglogical is fundamentally
    single-master/fan-in and builds against *stock* core; Spock is active-active
    and requires *patched* core.
  - [[pgactive]] — the other active-master extension. Both do last-update-wins on
    commit timestamps with a deterministic node tiebreak
    (`node_seq_id` there, `tiebreaker` here), both hard-require
    `track_commit_timestamp`, both use replication origins for loop suppression.
    **Contrast:** pgactive loads into unmodified core (its whole thesis is
    "multi-master without forking the server"); Spock explicitly patches core.
  - [[synchdb]] — the replication-apply cousin whose *source* is a foreign DB, not
    PG WAL. Both apply through low-level table-modify paths and offer an SPI apply
    backend gated by a GUC (`spock.use_spi` ↔ `synchdb.dml_use_spi`).
- **Idioms:**
  - [[apply-conflict-resolution]] / [[apply-handlers-insert-update-delete]] /
    [[apply-worker-loop-and-dispatch]] — the core apply model Spock extends into
    conflict-resolving multi-master.
  - [[replication-origin-tracking]] — the `replorigin_session_origin` /
    commit-timestamp plumbing behind loop suppression and last-update-wins.
  - [[abort-transaction-cleanup]] / [[subtransaction-stack]] — the
    `BeginInternalSubTransaction`/`RollbackAndReleaseCurrentSubTransaction`
    exception-skip idiom.
  - [[guc-variables]] — the ~30 `spock.*` GUCs.
  - [[catalog-conventions]] — the `spock.*` catalog tables (`node`,
    `exception_log`, `resolutions`).
  - [[error-handling]] — `PG_TRY/PG_CATCH`, `CopyErrorData`, `FlushErrorState`
    around apply.
  - [[wal-record-construction]] — the custom WAL rmgr (`spock_rmgr_init`).
- **Subsystems:** [[replication]] — logical decoding, replication origins, apply
  workers, the output-plugin contract Spock consumes and extends.
- **Skills:** `.claude/skills/bgworker-and-extensions/SKILL.md` (static
  supervisor + dynamic workers), `.claude/skills/logical-replication/SKILL.md`,
  `.claude/skills/replication-overview/SKILL.md`,
  `.claude/skills/error-handling/SKILL.md`,
  `.claude/skills/gucs-config/SKILL.md`.

## Sources

Fetched 2026-07-19 from `raw.githubusercontent.com/pgedge/spock/main/<path>`.
All manifest files returned HTTP 200.

| URL | HTTP | Note |
|---|---|---|
| …/main/README.md | 200 | build-on-patched-core section (106-139), pgLogical2 upgrade (50), config (183-201) |
| …/main/Makefile | 200 | `MODULE_big`/`MODULES=spock_output` split (7-19), patch-name comment (90-91), compat vpath (13-17) |
| …/main/spock.control.in | 200 | `relocatable=false`, `schema=spock`, `comment='PostgreSQL Logical Replication'` |
| …/main/include/spock.h | 200 | version 6.0.0, GUC externs, log-verbosity macros, readonly protos |
| …/main/src/spock.c | 200 | `_PG_init`, GUC block, supervisor bgw, resolver enum, `emit_log_hook` |
| …/main/src/spock_apply.c | 200 | 4967 lines; grepped: apply handlers, exception PG_TRY/subxact, replay queue |
| …/main/src/spock_conflict.c | 200 | conflict taxonomy, last/first-update-wins, tiebreak, commit-ts lookup, check hook |
| …/main/src/spock_exception_handler.c | 200 | 16-col exception_log, `add_entry_to_exception_log`, `spock_disable_subscription` |
| …/main/src/spock_readonly.c | 200 | `transaction_read_only`/`XactReadOnly` piggyback, parse/executor hooks |
| …/main/src/spock_node.c | 200 | 1365 lines; grepped: `create_node`, tiebreaker extraction, Snowflake |

**Fetch notes / gaps:**
- **`patches/` directory NOT fetched.** The version-specific `.diff` files
  (`patches/Postgres-<ver>/pgNN-NNN-*.diff`) are the core-patching payload; their
  exact contents were not read this run, so the "what the patches do" breakdown
  (§1) is `[inferred]` from the code sites that consume patched-core facilities
  (`TransactionIdGetCommitTsData` on raw xmin, failover slots, custom rmgr) plus
  `[from-README]` for the build procedure. A follow-up should fetch the tree
  listing and at least one `pg17-*.diff` to confirm the WAL-reader / commit-ts /
  replication-origin hook hypothesis.
- **`src/spock_output.c` (output plugin) NOT fetched** — its existence and
  separate-module build are `[verified-by-code: Makefile:11,48]`; the callback
  registration and wire protocol are `[inferred]` from pglogical lineage.
- The supervisor→manager→apply worker *tree* below the static supervisor is
  `[inferred]` (only the supervisor registration in `spock.c` was read; worker
  registration lives in `spock_worker.c`, not fetched).
- `api.github.com` tree listing was not used; paths came from the task manifest,
  all confirmed by direct raw fetch (200).
