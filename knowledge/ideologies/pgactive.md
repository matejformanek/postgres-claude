# pgactive — ideology

How the **pgactive** extension (`aws/pgactive`, branch `main`, control
`default_version = 2.1.8`) diverges from core PostgreSQL design. pgactive is the
AWS-maintained descendant of the 2ndQuadrant **BDR** ("BiDirectional
Replication") lineage; the file headers still carry `Copyright (c) 2012-2015,
PostgreSQL Global Development Group` and the original BDR architecture is largely
intact under renamed symbols.

## Domain & purpose

pgactive provides **active-active (multi-master) logical replication**: multiple
PostgreSQL databases in a cluster each accept writes and replicate them to every
peer, built entirely as an extension on top of PG's native logical decoding
(available since PG 10). `[from-README]` The README is explicit that this is not
free lunch — applications must be designed to tolerate "conflicting changes,
replication lag, and the lack of certain convenient database features such as
incremental integer sequences." `[from-README]` The core ideological bet,
stated in the README, is that "PostgreSQL's design makes it possible to build the
necessary components for supporting active-active replication in an extension"
`[from-README]` — i.e. multi-master is achievable without forking the server,
purely via the output-plugin + bgworker + hook surface.

## How it hooks into PG

pgactive bolts onto core through every extension seam PG offers:

- **Logical decoding output plugin.** `src/pgactive_output.c` registers the
  standard callback set in `_PG_output_plugin_init()` — `startup_cb`,
  `begin_cb`, `change_cb`, `commit_cb`, `message_cb`, `shutdown_cb`
  (`src/pgactive_output.c:144-153`) `[verified-by-code]`. This is the *send*
  side: a walsender running the plugin decodes the WAL of one node and streams a
  pgactive-private wire protocol to a peer.
- **Replication slots + walsender.** Each peer connection is fed by a logical
  slot; the apply side creates slots and connects as a logical replication
  client (`pgactive_apply_main()`, `src/pgactive_apply.c:3520-3556`)
  `[verified-by-code]`.
- **Background workers, three tiers.** A static **supervisor** worker
  (`pgactive_supervisor_register()`, called from `_PG_init`,
  `src/pgactive.c:1838`) `[verified-by-code]`; a **per-database (perdb)** worker
  (`pgactivePerdbWorker`, `include/pgactive.h:340-355`) that manages pgactive
  for a single DB and launches/maintains apply workers
  (`pgactive_maintain_db_workers()`, `include/pgactive.h:868`)
  `[verified-by-code]`; and one **apply worker per peer connection**
  (`pgactiveApplyWorker`, `include/pgactive.h:306-335`) that connects to a
  remote node and replays its stream. The worker structs live in a shmem array
  and therefore "can't have any pointers" (`include/pgactive.h:306-310`)
  `[from-comment]`.
- **`_PG_init` hook chain.** `_PG_init()` (`src/pgactive.c:1583`) requires
  `shared_preload_libraries`, refuses to load unless `track_commit_timestamp` is
  on and `wal_level >= logical` (`src/pgactive.c:1585-1598`)
  `[verified-by-code]`; installs a security-label provider
  (`src/pgactive.c:1834`), a `shmem_request_hook` (`src/pgactive.c:1841-1845`),
  and a `ProcessUtility_hook` via `init_pgactive_commandfilter()`
  (`src/pgactive.c:1850`) `[verified-by-code]`.
- **Custom catalogs (`pgactive.*`).** Everything lives in a `pgactive` schema
  inside `pg_catalog` (control `schema = pg_catalog`,
  `pgactive_SCHEMA_NAME "pgactive"`, `include/pgactive.h`). Key tables:
  `pgactive.pgactive_nodes` (node metadata incl. `node_seq_id`,
  `src/pgactive_seq.c:103`), `pgactive.pgactive_queued_commands` (DDL queue,
  `src/pgactive_ddlrep.c:72`), `pgactive.pgactive_conflict_history` (conflict
  log; the in-memory `pgactiveApplyConflict` struct is "closely related to" it,
  `include/pgactive.h:729-731`) `[verified-by-code]`.
- **GUCs.** Registered under the `pgactive.` prefix in `_PG_init`
  (`src/pgactive.c:1600-1832`) and `extern`-declared in
  `include/pgactive.h:531-548`: e.g. `pgactive.log_conflicts_to_table`,
  `pgactive.log_conflicts_to_logfile`, `pgactive.skip_ddl_replication`,
  `pgactive.max_ddl_lock_delay`, `pgactive.ddl_lock_timeout`,
  `pgactive.do_not_replicate` `[verified-by-code]`.
- **Custom WAL logical messages.** pgactive reserves the logical-message prefix
  `pgactive_LOGICAL_MSG_PREFIX "pgactive"` (`include/pgactive.h`) and handles a
  `'M'` (message) decoding/apply path (`pg_decode_message`,
  `src/pgactive_output.c:153`; message action `'M'` in the apply dispatcher,
  `src/pgactive_apply.c:3246-3276`) — the `LogicalDecodingProcessMessage` /
  `pg_logical_emit_message` mechanism used for out-of-band coordination
  signalling `[verified-by-code]`.

## Where it diverges from core idioms

Core PG logical replication (the `pgoutput` plugin + `CREATE SUBSCRIPTION`) is
deliberately **single-master, no-conflict-handling**: a subscriber applies a
publisher's stream and resolves nothing. Sibling [[pglogical]] (same 2ndQuadrant
lineage) is also fundamentally single-master / fan-in. pgactive's whole reason to
exist is the things core refuses to do:

1. **Conflict resolution.** Multi-master means two nodes can edit the same row
   concurrently. pgactive enumerates conflict *types*
   (`pgactiveConflictType`: InsertInsert, InsertUpdate, UpdateUpdate,
   UpdateDelete, DeleteDelete, UnhandledTxAbort,
   `include/pgactive.h:343-351`) and conflict *resolutions*
   (`pgactiveConflictResolution`: ConflictTriggerSkipChange,
   ConflictTriggerReturnedTuple, LastUpdateWins_KeepLocal,
   LastUpdateWins_KeepRemote, DefaultApplyChange, DefaultSkipChange,
   UnhandledTxAbort, `include/pgactive.h:358-366`) `[verified-by-code]`. The
   apply worker detects conflicts by probing unique indexes with a dirty
   snapshot on INSERT (`process_remote_insert`,
   `src/pgactive_apply.c:561-824`) and missing-tuple cases on UPDATE/DELETE
   (`src/pgactive_apply.c:831-1290`) `[verified-by-code]`.
2. **Last-update-wins with deterministic tiebreak.**
   `check_apply_update()` (`src/pgactive_apply.c:1426-1503`) first tries a
   user-defined conflict trigger (line 1468) and otherwise falls through to
   `pgactive_conflict_last_update_wins()` (`src/pgactive_apply.c:1372-1420`),
   which compares commit timestamps via `timestamptz_cmp_internal()`
   (line 1380) and breaks ties on `node_seq_id` (lines 1384-1413) so all nodes
   converge identically `[verified-by-code]`. Crucially it *skips* conflict
   handling when the local change already originated from the same node
   (`src/pgactive_apply.c:1426-1503`) `[verified-by-code]`.
3. **Commit-timestamp dependency.** Last-update-wins needs the per-tuple commit
   time, so pgactive hard-requires `track_commit_timestamp` at load
   (`src/pgactive.c:1585-1598`) and reads it via
   `TransactionIdGetCommitTsData()` in `get_local_tuple_origin()`
   (`src/pgactive_apply.c:1331-1342`) `[verified-by-code]`. Core logical
   replication has no such dependency.
4. **Loop avoidance via replication origins.** In a mesh, a change must not
   echo forever. The output plugin's `should_forward_changeset()`
   (`src/pgactive_output.c:395-441`) rejects any change carrying a valid
   `RepOriginId` unless explicit forwarding is enabled, passing only
   `InvalidRepOriginId` (truly local) and `DoNotReplicateId`
   (`src/pgactive_output.c:436`) `[verified-by-code]`. The apply side sets the
   origin session in `process_remote_begin()` (`src/pgactive_apply.c:172-334`)
   and advances origins (including forwarded "catchup"/multi-hop sources) in
   `process_remote_commit()` (`src/pgactive_apply.c:341-440`, `replorigin_advance`
   at 419-424) `[verified-by-code]`. The apply worker thus writes *as an ordinary
   backend* but tagged so its own output plugin won't re-emit the change.
5. **DDL replication.** Core logical replication does **not** replicate DDL at
   all. pgactive intercepts utility statements in its `ProcessUtility_hook`
   (`pgactive_capture_ddl()`, `src/pgactive_ddlrep.c:197-248`), serialises the
   command text + reconstructed `search_path` + perpetrator role into
   `pgactive.pgactive_queued_commands` (`pgactive_queue_ddl_command()`,
   `src/pgactive_ddlrep.c:47-97`), and on the apply side replays it via
   `pgactive_execute_ddl_command()` (`src/pgactive_apply.c:1558-1636`); drops go
   through `process_queued_drop()` → `performMultipleDeletions()`
   (`src/pgactive_apply.c:1706-1930`) `[verified-by-code]`. A global DDL-lock is
   gated by GUCs (`pgactive.max_ddl_lock_delay`, `pgactive.ddl_lock_timeout`,
   `src/pgactive.c:1650-1665`) `[inferred]`.
6. **Global / "global-less" sequences.** Plain `serial`/`bigserial` would
   collide across masters. pgactive replaces them with a **Snowflake-style ID
   generator** (`pgactive_snowflake_id_nextval_oid()`,
   `src/pgactive_seq.c:48`): 40 bits ms-timestamp (epoch 2016-10-07) | 10 bits
   node id | 14 bits per-ms sequence, giving 8192 ids/ms/node with **no
   distributed consensus or chunk pre-allocation** — collision avoidance is by
   bit-partitioning the node id, read from `pgactive.pgactive_nodes.node_seq_id`
   (`global_seq_read_nodeid()`, `src/pgactive_seq.c:103`; generation errors if
   `node_seq_id` is unallocated, lines 106-107) `[verified-by-code]`. This is a
   sharper divergence than BDR's older voted-range "global sequences."
7. **Node bootstrap via dump+restore.** Joining a node is not a core concept;
   pgactive has `pgactive_init_replica()` (`include/pgactive.h:825`) and a
   `pgactive.synchronous_commit`-style init path, with a temp dump directory GUC
   and `pgactive_init_node_parallel_jobs` (`include/pgactive.h:546`) implying a
   parallel dump/restore seeding step `[inferred]`.

## Notable design decisions

- **Architecture-fingerprinted wire protocol.** The output plugin's startup
  negotiates PG version, catalog version, `sizeof(int/long/Datum)`, alignment,
  endianness and float format (`src/pgactive_output.c:264-341`) and picks among
  binary / send-recv / text tuple encodings in `decide_datum_transfer()`
  (`src/pgactive_output.c:754-781`), disabling binary for datetime mismatches
  and send-recv for version differences (`write_tuple()`,
  `src/pgactive_output.c:807-958`) `[verified-by-code]`. Heterogeneous-arch
  meshes still work, just slower.
- **Node identity as (sysid, timeline, dboid).** `pgactiveNodeId` encodes a
  triple (`include/pgactive.h:575-577`) with dedicated wire (de)serialisers
  `pgactive_getmsg_nodeid()` / `pgactive_send_nodeid()`
  (`include/pgactive.h:979-983`) `[verified-by-code]` — richer than core's
  single subscription OID, because a mesh must name peers globally.
- **Conflict logging is first-class.** `pgactiveApplyConflict`
  (`include/pgactive.h:743-768`) plus `pgactive_conflict_log_serverlog()` /
  `pgactive_conflict_log_table()` (`include/pgactive.h:903-908`) persist every
  conflict to server log and/or `pgactive.pgactive_conflict_history`, gated by
  `pgactive.log_conflicts_to_*` GUCs `[verified-by-code]`.
- **User conflict handlers are partly stubbed.** `src/pgactive_conflict_handlers.c`
  still has `pgactive_create_conflict_handler()` /
  `pgactive_drop_conflict_handler()` erroring with "feature is not implemented
  yet" (lines 133, 249); the resolver `pgactive_conflict_handlers_resolve()`
  (lines 469-583) exists and is invoked, but registration is incomplete
  `[verified-by-code]`. So in practice last-update-wins is the live default.
- **Multi-hop / catchup origins.** `process_remote_begin/commit` carry a
  separate "catchup" origin so a node can forward another node's changes during
  catch-up without breaking loop detection (`src/pgactive_apply.c:3102-3110`,
  `pgactive_nodeid_eq()` guard) `[verified-by-code]`.

## Links into corpus

- Subsystems: [[logical-decoding]], [[replication]], [[wal-and-xlog]] — pgactive
  is a pure consumer of the logical-decoding callback API and replication-origin
  machinery.
- Idioms: [[bgworker-and-extensions]] (supervisor + perdb + per-peer apply
  worker registration), [[gucs-config]] (the `pgactive.` GUC family),
  [[catalog-conventions]] (the `pgactive.*` catalog tables).
- Sibling ideologies: [[pglogical]] (single-master logical replication, same
  2ndQuadrant heritage — pgactive is the multi-master cousin), [[wal2json]]
  (the logical-decoding output-plugin family; wal2json is a read-only
  change-feed plugin, pgactive a full bidirectional one).

## Sources

All fetched via `raw.githubusercontent.com/aws/pgactive/main/<path>` on
2026-06-14T00:00:00Z. (`api.github.com` tree listing returned HTTP 403 to
WebFetch; paths were instead verified by direct raw fetch and one
`mcp__github__search_code` lookup that located the header at `include/pgactive.h`
rather than `src/pgactive.h`.)

- `https://raw.githubusercontent.com/aws/pgactive/main/README.md` — 200
- `https://raw.githubusercontent.com/aws/pgactive/main/pgactive.control` — 200
- `https://raw.githubusercontent.com/aws/pgactive/main/include/pgactive.h` — 200
  (manifest substitution: hinted `src/pgactive.h` returned 404, as did bare
  `pgactive.h` and `src/include/pgactive.h`; correct path `include/pgactive.h`
  found via `mcp__github__search_code`)
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive.c` — 200
  (the `_PG_init` / hook-chain / bgworker-registration site)
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive_apply.c` — 200
  (manifest hint `src/pgactive_apply.c` confirmed)
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive_output.c` — 200
  (manifest hint `src/pgactive_output.c` confirmed)
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive_conflict_handlers.c` — 200
  (manifest hint was `src/pgactive_conflict*.c`; actual file is
  `pgactive_conflict_handlers.c`)
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive_seq.c` — 200
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive_ddlrep.c` — 200
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive_apply.c` (re-cited above)

Failed/404 during path discovery (noted for the record):
- `https://raw.githubusercontent.com/aws/pgactive/main/src/pgactive.h` — 404
- `https://raw.githubusercontent.com/aws/pgactive/main/pgactive.h` — 404
- `https://raw.githubusercontent.com/aws/pgactive/main/src/include/pgactive.h` — 404
- `https://api.github.com/repos/aws/pgactive/git/trees/main?recursive=1` — 403 (WebFetch)
