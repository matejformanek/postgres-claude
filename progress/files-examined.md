# Files examined

Append-only registry of every source file the corpus has read in non-trivial
depth. Updated whenever a file gets examined — by an agent during the
file-by-file deep-corpus phase, by a session that produced a knowledge doc,
or any time a file becomes load-bearing for a claim somewhere in `knowledge/`.

## Why this exists

The user wants the file-by-file phase to be **truly thorough — every file
checked**. Without a registry we will lose track of coverage. This is the
ledger that answers: "have we read `relcache.c` yet?" / "which files in
`storage/lmgr/` have not been touched?" / "which docs cite this file?".

## Conventions

- One row per file, identified by path relative to `source/` (the stable
  read-only reference).
- **Depth values**:
  - `skim` — read the top-of-file comment + scanned function names; didn't
    follow control flow.
  - `read` — read all entry-point functions and their immediate callees;
    understood the file's purpose well enough to cite specific behaviors.
  - `deep-read` — walked through every function with attention to invariants
    and locking; treated as authoritative when writing `knowledge/` docs.
- **Last-verified commit** is the PG commit hash the read was anchored at.
  Re-verify after upstream pulls if the file appears in a `git log <sha>..master --` diff.
- **Produced doc(s)** = link(s) into `knowledge/...` where this file is
  cited or the read produced a write-up. Empty if read but not yet used.

## Registry

| File (under source/) | First examined | Last verified | Depth | By | Produced doc(s) | Notes |
|---|---|---|---|---|---|---|
| src/backend/storage/buffer/bufmgr.c | 2026-06-01 | ef6a95c7c64 | deep-read | subsystem-documenter (calibration run) | knowledge/subsystems/storage-buffer.md | Spine of buffer-mgr doc; locking section flagged 6 open questions |
| src/backend/storage/buffer/freelist.c | 2026-06-01 | ef6a95c7c64 | read | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Clock-sweep + strategy rings; §5.1 of buffer doc |
| src/backend/storage/buffer/buf_init.c | 2026-06-01 | ef6a95c7c64 | read | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Shared-mem layout |
| src/backend/storage/buffer/buf_table.c | 2026-06-01 | ef6a95c7c64 | skim | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Hash table wrapper |
| src/backend/storage/buffer/localbuf.c | 2026-06-01 | ef6a95c7c64 | skim | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Temp-table backend-local buffers |
| src/backend/storage/buffer/README | 2026-06-01 | ef6a95c7c64 | deep-read | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Highest-signal anchor; cited extensively |
| src/include/storage/buf.h | 2026-06-01 | ef6a95c7c64 | read | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Buffer typedef + handle |
| src/include/storage/buf_internals.h | 2026-06-01 | ef6a95c7c64 | read | subsystem-documenter | knowledge/subsystems/storage-buffer.md | BufferDesc + state-encoding bits |
| src/include/storage/bufmgr.h | 2026-06-01 | ef6a95c7c64 | read | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Public API |
| src/include/storage/bufpage.h | 2026-06-01 | ef6a95c7c64 | skim | subsystem-documenter | knowledge/subsystems/storage-buffer.md | Page-on-disk layout |
| src/backend/executor/README | 2026-06-01 | HEAD | deep-read | exec-planner skill session | knowledge/architecture/executor.md, .claude/skills/executor-and-planner/SKILL.md | Plan/PlanState split, memory ctxs, control flow, EPQ, async |
| src/backend/executor/execMain.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/executor.md | standard_ExecutorStart/Run/End (lines 120-540) |
| src/backend/executor/execProcnode.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/executor.md, .claude/skills/executor-and-planner/SKILL.md | ExecInitNode/ProcNode/EndNode dispatch + ExecProcNodeFirst trick |
| src/backend/executor/nodeSeqscan.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/executor.md, .claude/skills/executor-and-planner/SKILL.md | Canonical scan-node template; four ExecProcNode variants |
| src/backend/executor/nodeNestloop.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/executor.md, .claude/skills/executor-and-planner/SKILL.md | Canonical join-node template; nestParam + ExecReScan loop |
| src/include/nodes/execnodes.h | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/executor.md | PlanState, EState, ExprContext, ScanState layouts |
| src/backend/optimizer/README | 2026-06-01 | HEAD | deep-read | exec-planner skill session | knowledge/architecture/planner.md, .claude/skills/executor-and-planner/SKILL.md | Path/Plan model, RelOptInfo DP, add_path discard-safety |
| src/backend/optimizer/plan/planner.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/planner.md | standard_planner, subquery_planner, grouping_planner entries |
| src/backend/optimizer/path/allpaths.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/planner.md | set_rel_pathlist, geqo_threshold, standard_join_search |
| src/backend/optimizer/path/costsize.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/planner.md | Cost-model anchors, cost_seqscan, disabled_nodes lex-order |
| src/backend/optimizer/util/pathnode.c | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/planner.md, .claude/skills/executor-and-planner/SKILL.md | add_path dominance pruning, add_path_precheck, create_seqscan_path |
| src/backend/optimizer/plan/createplan.c | 2026-06-01 | HEAD | skim | exec-planner skill session | .claude/skills/executor-and-planner/SKILL.md | create_plan / create_plan_recurse dispatch; create_seqscan_plan template |
| src/include/nodes/pathnodes.h | 2026-06-01 | HEAD | read | exec-planner skill session | knowledge/architecture/planner.md | Path, RelOptInfo, PlannerInfo, PlannerGlobal layouts |
| src/backend/storage/smgr/README | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet (smgr+page+file+fsm+sync) | knowledge/files/src/backend/storage/smgr/README.md | Storage-manager switch overview + Relation Forks |
| src/backend/storage/smgr/smgr.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/smgr/smgr.c.md | Dispatch + SMgrRelation hashtable + HOLD_INTERRUPTS pattern |
| src/backend/storage/smgr/md.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/smgr/md.c.md | Segments, _mdfd_getseg, register_dirty_segment, mdunlink, mdtruncate |
| src/backend/storage/smgr/bulk_write.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/smgr/bulk_write.c.md | Bypass-bufmgr writer + DELAY_CHKPT_START race |
| src/backend/storage/page/README | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/page/README.md (n/a, claims in bufpage.c.md) | Checksum design, hint-bit + torn-page interactions |
| src/backend/storage/page/bufpage.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/page/bufpage.c.md | PageInit, PageIsVerified, PageAddItemExtended, compactify_tuples, PageSetChecksum |
| src/backend/storage/page/checksum.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/page/checksum.c.md | Shell over checksum_impl.h; fallback + AVX2 dispatch |
| src/backend/storage/page/itemptr.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/page/itemptr.c.md | TID compare/equals/inc/dec |
| src/backend/storage/file/fd.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/file/fd.c.md | VFD cache + LRU eviction (LruDelete/Insert/ReleaseLruFiles); pg_fsync; SyncDataDirectory |
| src/backend/storage/file/buffile.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/file/buffile.c.md | Stdio-on-VFD; 1GB segments; FileSet/SharedFileSet hooks |
| src/backend/storage/file/copydir.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/file/copydir.c.md | CREATE DATABASE / tablespace copy; file_copy_method GUC |
| src/backend/storage/file/reinit.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/file/reinit.c.md | Unlogged-rel reinit at crash recovery |
| src/backend/storage/file/sharedfileset.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/file/sharedfileset.c.md | DSM-detach-driven refcount of FileSet |
| src/backend/storage/file/fileset.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/file/fileset.c.md | Named temp-file namespace under fd.c |
| src/backend/storage/freespace/README | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/freespace/README.md | FSM data structure (in-page + cross-page trees), locking, recovery without WAL |
| src/backend/storage/freespace/freespace.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/freespace/freespace.c.md | Cross-page FSM logic, GetPageWithFreeSpace, RecordPageWithFreeSpace, VACUUM |
| src/backend/storage/freespace/fsmpage.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/freespace/fsmpage.c.md | Intra-page binary heap; fsm_search_avail/set_avail/rebuild_page |
| src/backend/storage/freespace/indexfsm.c | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/backend/storage/freespace/indexfsm.c.md | Thin wrapper using FSM with 0/255 values for index pages |
| src/backend/storage/sync/sync.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-quintet | knowledge/files/src/backend/storage/sync/sync.c.md | Checkpointer fsync queue; cycle-counter discipline; FILTER/UNLINK/FORGET request flow |
| src/include/storage/smgr.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/smgr.h.md | SMgrRelationData layout + public API |
| src/include/storage/md.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/md.h.md | mdsw vtable + sync-handler callbacks |
| src/include/storage/bulk_write.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/bulk_write.h.md | BulkWriteState/Buffer surface |
| src/include/storage/bufpage.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/bufpage.h.md | (Upgraded from skim) Full page layout, PageHeaderData, PD_* flags |
| src/include/storage/checksum.h | 2026-06-01 | ef6a95c7c64 | skim | storage-quintet | knowledge/files/src/include/storage/checksum.h.md | pg_checksum_page only |
| src/include/storage/itemptr.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/itemptr.h.md | ItemPointerData + accessors |
| src/include/storage/fd.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/fd.h.md | Full VFD/Allocate/BasicOpen surface + GUCs |
| src/include/storage/buffile.h | 2026-06-01 | ef6a95c7c64 | skim | storage-quintet | knowledge/files/src/include/storage/buffile.h.md | BufFile public ops |
| src/include/storage/copydir.h | 2026-06-01 | ef6a95c7c64 | skim | storage-quintet | knowledge/files/src/include/storage/copydir.h.md | copydir/copy_file + file_copy_method |
| src/include/storage/reinit.h | 2026-06-01 | ef6a95c7c64 | skim | storage-quintet | knowledge/files/src/include/storage/reinit.h.md | ResetUnloggedRelations |
| src/include/storage/sharedfileset.h | 2026-06-01 | ef6a95c7c64 | skim | storage-quintet | knowledge/files/src/include/storage/sharedfileset.h.md | refcount + DSM detach |
| src/include/storage/fileset.h | 2026-06-01 | ef6a95c7c64 | skim | storage-quintet | knowledge/files/src/include/storage/fileset.h.md | FileSet struct + API |
| src/include/storage/freespace.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/freespace.h.md | FSM public API |
| src/include/storage/fsm_internals.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/fsm_internals.h.md | Internal interface between freespace.c and fsmpage.c |
| src/include/storage/sync.h | 2026-06-01 | ef6a95c7c64 | read | storage-quintet | knowledge/files/src/include/storage/sync.h.md | FileTag + SyncRequestType enums + public API |

<!--
Append rows below as files get examined. Sort within a subsystem block alphabetically.
When updating an existing row to deeper read, add a new row rather than editing
(append-only spirit), and let the depth column show the progression.
-->
| src/backend/utils/mmgr/README | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/README.md | Section-map of the canonical design doc |
| src/backend/utils/mmgr/mcxt.c | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/mcxt.c.md | Type-independent API, vtable dispatch, OOM policy, iterative delete, palloc_aligned, signal-driven log dump |
| src/backend/utils/mmgr/aset.c | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/aset.c.md | Power-of-2 freelists, keeper block, context_freelists recycle cache, double-pfree detection |
| src/backend/utils/mmgr/generation.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/generation.c.md | FIFO; per-block counters; single freeblock recycle slot |
| src/backend/utils/mmgr/slab.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/slab.c.md | Fixed-size chunks; 3-bucket fullness blocklist; 10-block empty cache |
| src/backend/utils/mmgr/bump.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/bump.c.md | No chunk header in prod; pfree/repalloc are stubs that ERROR |
| src/backend/utils/mmgr/alignedalloc.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/alignedalloc.c.md | Redirection chunk (MCTX_ALIGNED_REDIRECT_ID) used by palloc_aligned |
| src/backend/utils/mmgr/dsa.c | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/dsa.c.md | Shared-mem heap; dsa_pointer = (seg, offset); per-size-class pools w/ per-pool LWLock; segments grow on demand |
| src/backend/utils/mmgr/freepage.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/freepage.c.md | Page-run allocator; bookkeeping in the managed pages; in-memory btree for coalescing |
| src/backend/utils/mmgr/portalmem.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/portalmem.c.md | Portal lifecycle; TopPortalContext; (Sub)Commit/Abort hooks; holdContext sibling-not-child |
| src/backend/utils/mmgr/memdebug.c | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/memdebug.c.md | CLOBBER_FREED_MEMORY 0x7F, MEMORY_CONTEXT_CHECKING sentinel 0x7E, randomize_mem |
| src/include/nodes/memnodes.h | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/mcxt.c.md (referenced) | MemoryContextData + Methods vtable shape |
| src/include/utils/palloc.h | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/mcxt.c.md (referenced) | Public palloc API + MemoryContextSwitchTo inline |
| src/include/utils/memutils.h | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/mcxt.c.md (referenced) | Global ctxts + AllocSet/Slab/Gen/Bump creators + MaxAllocSize/HugeSize |
| src/include/utils/memutils_memorychunk.h | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/README.md (referenced) | MemoryChunk hdrmask layout (4+1+30+30 bits with shared bit) |
| src/include/utils/memutils_internal.h | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/mcxt.c.md (referenced) | Per-impl callback prototypes + MemoryContextMethodID enum |
| src/include/utils/dsa.h | 2026-06-01 | ef6a95c7c64 | read | mmgr-file-by-file | knowledge/files/src/backend/utils/mmgr/dsa.c.md (referenced) | dsa_pointer/dsa_handle types + flags + offset-width policy |
| src/backend/postmaster/postmaster.c | 2026-06-01 | ef6a95c7c64 | deep-read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/postmaster.c.md | Postmaster main loop + fork dispatch; no-shmem invariant |
| src/backend/postmaster/launch_backend.c | 2026-06-01 | ef6a95c7c64 | deep-read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/launch_backend.c.md | child_process_kinds[] dispatch table; fork vs EXEC_BACKEND |
| src/backend/postmaster/fork_process.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/fork_process.c.md | fork() wrapper, signal blocking, OOM adjustment |
| src/backend/postmaster/auxprocess.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/auxprocess.c.md | AuxiliaryProcessMainCommon shared aux init |
| src/backend/postmaster/interrupt.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/interrupt.c.md | ProcessMainLoopInterrupts + reusable signal handlers |
| src/backend/postmaster/bgworker.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/bgworker.c.md | Bgworker registration + slot handshake (canonical in skill) |
| src/backend/postmaster/autovacuum.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/autovacuum.c.md | Launcher + worker; postmaster does the fork |
| src/backend/postmaster/bgwriter.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/bgwriter.c.md | Bg buffer writer + xl_running_xacts heartbeat |
| src/backend/postmaster/checkpointer.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/checkpointer.c.md | Singleton checkpointer + fsync forwarding |
| src/backend/postmaster/walwriter.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/walwriter.c.md | Async-commit durability SLA |
| src/backend/postmaster/walsummarizer.c | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/walsummarizer.c.md | PG17 WAL-summary aux process |
| src/backend/postmaster/startup.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/startup.c.md | Recovery driver — no main loop |
| src/backend/postmaster/syslogger.c | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/syslogger.c.md | The only aux not attached to shmem |
| src/backend/postmaster/pgarch.c | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/pgarch.c.md | WAL archiver |
| src/backend/postmaster/pmchild.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/postmaster/pmchild.c.md | Per-BackendType PMChild pools |
| src/backend/storage/ipc/pmsignal.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/storage/ipc/pmsignal.c.md | Lockless SIGUSR1-multiplex protocol |
| src/backend/tcop/postgres.c | 2026-06-01 | ef6a95c7c64 | deep-read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/postgres.c.md | PostgresMain + sigsetjmp loop + exec_simple_query + exec_execute_message |
| src/backend/tcop/pquery.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/pquery.c.md | Portal runner: Start/Run/Fetch/RunMulti |
| src/backend/tcop/dest.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/dest.c.md | DestReceiver dispatch |
| src/backend/tcop/fastpath.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/fastpath.c.md | PQfn() server side |
| src/backend/tcop/utility.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/utility.c.md | DDL/utility dispatcher; standard vs Slow |
| src/backend/tcop/cmdtag.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/cmdtag.c.md | CommandTag table + legacy InsertOid slot |
| src/backend/tcop/backend_startup.c | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/backend/tcop/backend_startup.c.md | Startup-packet + auth pre-PGPROC; cancel-request path |
| src/include/postmaster/postmaster.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/postmaster.h.md | Postmaster public API |
| src/include/postmaster/bgworker.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/bgworker.h.md | Extension-facing bgworker API |
| src/include/postmaster/bgworker_internals.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/bgworker_internals.h.md | Postmaster-private bgworker state |
| src/include/postmaster/bgwriter.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/bgwriter.h.md | BgWriter prototypes |
| src/include/postmaster/walwriter.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/walwriter.h.md | WalWriter prototypes |
| src/include/postmaster/checkpointer.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/checkpointer.h.md | Checkpointer prototypes |
| src/include/postmaster/startup.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/startup.h.md | Startup + promotion + progress |
| src/include/postmaster/interrupt.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/interrupt.h.md | Reusable interrupt helpers |
| src/include/postmaster/autovacuum.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/autovacuum.h.md | Autovac API |
| src/include/postmaster/auxprocess.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/auxprocess.h.md | AuxiliaryProcessMainCommon prototype |
| src/include/postmaster/pgarch.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/pgarch.h.md | Archiver API |
| src/include/postmaster/syslogger.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/syslogger.h.md | Pipe protocol + log GUCs |
| src/include/postmaster/walsummarizer.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/walsummarizer.h.md | WalSummarizer API |
| src/include/postmaster/proctypelist.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/postmaster/proctypelist.h.md | Canonical BackendType X-macro table |
| src/include/tcop/tcopprot.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/tcop/tcopprot.h.md | PostgresMain + pg_parse/analyze/plan API |
| src/include/tcop/pquery.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/tcop/pquery.h.md | Portal-runner API |
| src/include/tcop/dest.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/tcop/dest.h.md | DestReceiver contract + CommandDest enum |
| src/include/tcop/fastpath.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/tcop/fastpath.h.md | HandleFunctionRequest prototype |
| src/include/tcop/utility.h | 2026-06-01 | ef6a95c7c64 | skim | postmaster-tcop-file-by-file | knowledge/files/src/include/tcop/utility.h.md | ProcessUtility API |
| src/include/tcop/cmdtag.h | 2026-06-01 | ef6a95c7c64 | read | postmaster-tcop-file-by-file | knowledge/files/src/include/tcop/cmdtag.h.md | CommandTag enum + QueryCompletion |

## Coverage summary

Use `wc -l files-examined.md` / grep by directory to get coverage stats.
For the file-by-file phase, the target is "every .c and .h under
`source/src/backend/` and `source/src/include/` reached at least `skim` depth,
and every spine subsystem (storage/buffer, access/heap, access/transam,
storage/lmgr, utils/mmgr, executor, optimizer, parser, postmaster, tcop)
reached `deep-read` on every file".

Run `progress/files-examined.md`-based queries via:

```bash
# Count files in registry
grep -c '^| src/' progress/files-examined.md

# Files under a specific dir
grep '^| src/backend/storage/buffer/' progress/files-examined.md

# All deep-read files
grep '| deep-read |' progress/files-examined.md
```

<!-- storage/lmgr deep read (file-by-file phase) -->
| src/backend/storage/lmgr/README | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/README.md, knowledge/idioms/locking-overview.md | Authoritative narrative for heavyweight lockmgr |
| src/backend/storage/lmgr/README-SSI | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/README-SSI.md | SSI algorithm + index-AM rules |
| src/backend/storage/lmgr/lock.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/lock.c.md | Heavyweight lock mgr; partition LWLocks + fast path |
| src/backend/storage/lmgr/lwlock.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/lwlock.c.md | LWLock impl; state-word CAS + 4-phase race protocol |
| src/backend/storage/lmgr/proc.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/proc.c.md | PGPROC mgmt; CheckDeadLock is the canonical partition-order site |
| src/backend/storage/lmgr/deadlock.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/deadlock.c.md | WFG cycle detection + soft-edge rearrangement |
| src/backend/storage/lmgr/predicate.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/predicate.c.md | SSI; top comment is canonical LWLock-order rule for pred locks |
| src/backend/storage/lmgr/s_lock.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/s_lock.c.md | Contended-spinlock wait loop; NUM_DELAYS=1000 |
| src/backend/storage/lmgr/lmgr.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/lmgr.c.md | Object-locking facade over lock.c |
| src/backend/storage/lmgr/condition_variable.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-lmgr | knowledge/files/src/backend/storage/lmgr/condition_variable.c.md | Latch-based CVs; interruptible, DSM-safe |
| src/include/storage/lock.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-lmgr | knowledge/files/src/include/storage/lock.h.md | LOCK/PROCLOCK/LOCALLOCK + LockHashPartition* macros |
| src/include/storage/lwlock.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-lmgr | knowledge/files/src/include/storage/lwlock.h.md | LWLock types + MainLWLockArray offsets |
| src/include/storage/proc.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-lmgr | knowledge/files/src/include/storage/proc.h.md | PGPROC struct + PROC_HDR |

<!-- utils/{time,init,error} deep read (file-by-file phase) -->
| src/backend/utils/time/snapmgr.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/time/snapmgr.c.md | Snapshot lifecycle: ActiveStack + RegisteredSnapshots pairing-heap; export/import |
| src/backend/utils/time/combocid.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/time/combocid.c.md | (cmin,cmax) → combocid; backend-private, TopTransactionContext |
| src/backend/utils/init/postinit.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/init/postinit.c.md | BaseInit + InitPostgres pipeline; per-backend init ordering |
| src/backend/utils/init/globals.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/init/globals.c.md | extern storage: interrupts, MyProcPid, NBuffers, GUC defaults |
| src/backend/utils/init/miscinit.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/init/miscinit.c.md | InitPostmasterChild, 4-level userid, postmaster.pid lockfile |
| src/backend/utils/init/usercontext.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/init/usercontext.c.md | SwitchToUntrustedUser; SECURITY_RESTRICTED_OPERATION dance |
| src/backend/utils/error/elog.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/error/elog.c.md | ereport state machine, ERROR→FATAL/PANIC promotion, sinks |
| src/backend/utils/error/assert.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/error/assert.c.md | ExceptionalCondition; deliberately bypasses elog |
| src/backend/utils/error/csvlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/error/csvlog.c.md | 26-column positional CSV log format |
| src/backend/utils/error/jsonlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-utils | knowledge/files/src/backend/utils/error/jsonlog.c.md | JSON-object log format; keyed, sparse |
| src/include/utils/snapshot.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-utils | knowledge/files/src/include/utils/snapshot.h.md | SnapshotData + 7-variant SnapshotType enum |
| src/include/utils/snapmgr.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-utils | knowledge/files/src/include/utils/snapmgr.h.md | snapmgr.c API surface + GlobalVis* declarations |
| src/include/utils/combocid.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-utils | knowledge/files/src/include/utils/combocid.h.md | parallel-worker combocid transfer prototypes |
| src/include/utils/elog.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-utils | knowledge/files/src/include/utils/elog.h.md | ereport macros, level constants, PG_TRY, ErrorContextCallback |

<!-- access/nbtree deep read (file-by-file phase) -->
| src/backend/access/nbtree/README | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/README.md | Canonical L&Y narrative + deletion + dedup + WAL design |
| src/backend/access/nbtree/nbtree.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtree.c.md | AM handler vtable, scan lifecycle, parallel-scan coord, VACUUM driver |
| src/backend/access/nbtree/nbtinsert.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtinsert.c.md | _bt_doinsert → _bt_split → _bt_insert_parent; lock order at line 1908-1910 |
| src/backend/access/nbtree/nbtpage.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtpage.c.md | Page deletion 2-phase + buffer helpers + pending-FSM bookkeeping |
| src/backend/access/nbtree/nbtsearch.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtsearch.c.md | _bt_search/_bt_moveright/_bt_compare; move-left for backward scans |
| src/backend/access/nbtree/nbtxlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtxlog.c.md | btree_redo dispatch; safexid is the recycle gate, conflict at reuse |
| src/backend/access/nbtree/nbtutils.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtutils.c.md | _bt_truncate, _bt_killitems, vacuum cycle-ID slot, _bt_check_third_page |
| src/backend/access/nbtree/nbtsort.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtsort.c.md | Parallel index build, BTShared in DSM, bulk_write loader |
| src/backend/access/nbtree/nbtdedup.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtdedup.c.md | _bt_dedup_pass + _bt_bottomupdel_pass + posting-list helpers |
| src/backend/access/nbtree/nbtvalidate.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtvalidate.c.md | Opclass validator; strategies 1..5 and support fns 1..6 |
| src/backend/access/nbtree/nbtsplitloc.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtsplitloc.c.md | _bt_findsplitloc heuristic; SPLIT_DEFAULT/MANY_DUPLICATES/SINGLE_VALUE |
| src/backend/access/nbtree/nbtcompare.c | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtcompare.c.md | Built-in BTORDER_PROC for trivial datatypes |
| src/backend/access/nbtree/nbtpreprocesskeys.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/backend/access/nbtree/nbtpreprocesskeys.c.md | _bt_preprocess_keys; SAOP arrays + skip arrays; SK_BT_* flags |
| src/include/access/nbtree.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/include/access/nbtree.h.md | Page layout + tuple format + scan/insert/dedup/vacuum state structs |
| src/include/access/nbtxlog.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nbtree | knowledge/files/src/include/access/nbtxlog.h.md | 14 XLOG_BTREE_* info bytes + record formats; on-disk contract |
| src/backend/nodes/README | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nodes | knowledge/files/src/backend/nodes/README.md | "Steps to add a Node" checklist; canonical anchor |
| src/backend/nodes/list.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nodes | knowledge/files/src/backend/nodes/list.c.md | foreach hygiene, DEBUG_LIST_MEMORY_USAGE, header-stable / cells-may-move |
| src/backend/nodes/bitmapset.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nodes | knowledge/files/src/backend/nodes/bitmapset.c.md | trailing-zero invariant, REALLOCATE_BITMAPSETS, recycle-and-reassign |
| src/backend/nodes/tidbitmap.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/tidbitmap.c.md | exact + lossy pages, private/shared iterators |
| src/backend/nodes/makefuncs.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/makefuncs.c.md | makeFoo constructor catalogue |
| src/backend/nodes/value.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/value.c.md | Integer/Float/Boolean/String/BitString wrappers |
| src/backend/nodes/nodeFuncs.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/nodeFuncs.c.md | exprType/Collation/Location switches; walker/mutator engine |
| src/backend/nodes/copyfuncs.c | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/backend/nodes/copyfuncs.c.md | macros + generated bodies + custom Const/A_Const/ExtensibleNode |
| src/backend/nodes/equalfuncs.c | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/backend/nodes/equalfuncs.c.md | location fields ignored; CoercionForm ignored |
| src/backend/nodes/outfuncs.c | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/backend/nodes/outfuncs.c.md | nodeToString; WRITE_*_FIELD macros |
| src/backend/nodes/readfuncs.c | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/backend/nodes/readfuncs.c.md | stringToNode; locations reset to -1 |
| src/backend/nodes/queryjumblefuncs.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/queryjumblefuncs.c.md | queryId construction; constants squashed |
| src/backend/nodes/extensible.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/extensible.c.md | name → method-table hashtables for ExtensibleNode + CustomScan |
| src/backend/nodes/multibitmapset.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/backend/nodes/multibitmapset.c.md | List-of-Bitmapset 2-D bitset |
| src/backend/nodes/print.c | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/backend/nodes/print.c.md | pprint/elog_node_display/print_rt/print_tl/print_expr |
| src/include/nodes/nodes.h | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nodes | knowledge/files/src/include/nodes/nodes.h.md | NodeTag enum, makeNode/IsA/castNode, pg_node_attr catalogue, cross-cutting enums |
| src/include/nodes/pg_list.h | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nodes | knowledge/files/src/include/nodes/pg_list.h.md | List/ListCell layout, foreach hygiene, all iterator variants |
| src/include/nodes/bitmapset.h | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-nodes | knowledge/files/src/include/nodes/bitmapset.h.md | Bitmapset struct + full API enumeration |
| src/include/nodes/tidbitmap.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/tidbitmap.h.md | TBMIterator unified iterator API |
| src/include/nodes/extensible.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/extensible.h.md | ExtensibleNodeMethods + CustomPath/Scan/Exec method tables |
| src/include/nodes/value.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/value.h.md | five value-wrapper node types + intVal/strVal/boolVal/floatVal |
| src/include/nodes/print.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/print.h.md | tiny: debug printer prototypes |
| src/include/nodes/makefuncs.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/makefuncs.h.md | makeFoo prototypes |
| src/include/nodes/nodeFuncs.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/nodeFuncs.h.md | walker/mutator macro wrappers; QTW_* flags |
| src/include/nodes/parsenodes.h | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/include/nodes/parsenodes.h.md | Query, RangeTblEntry, all raw parse-tree A_*/Range*/utility stmts |
| src/include/nodes/primnodes.h | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/include/nodes/primnodes.h.md | Var/Const/Param/Aggref/OpExpr/SubLink/SubPlan/CaseExpr/etc |
| src/include/nodes/plannodes.h | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/include/nodes/plannodes.h.md | PlannedStmt + Plan + Scan/Join/Modify family |
| src/include/nodes/execnodes.h | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/include/nodes/execnodes.h.md | ExprState, EState, ResultRelInfo, all PlanState subclasses |
| src/include/nodes/pathnodes.h | 2026-06-01 | ef6a95c7c64 | skim | file-by-file-nodes | knowledge/files/src/include/nodes/pathnodes.h.md | PlannerInfo, RelOptInfo, IndexOptInfo, Path family, PathKey, EquivalenceClass |
| src/include/nodes/lockoptions.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/lockoptions.h.md | LockClauseStrength + LockWaitPolicy; ordinal max-wins |
| src/include/nodes/params.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/params.h.md | ParamListInfoData + static/dynamic modes; ParamExecData |
| src/include/nodes/memnodes.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/memnodes.h.md | MemoryContextData + MemoryContextMethods table |
| src/include/nodes/replnodes.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-nodes | knowledge/files/src/include/nodes/replnodes.h.md | replication-grammar parse-node carriers |
| src/backend/parser/README | 2026-06-01 | ef6a95c7c64 | deep-read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/README.md | One-screen map of the directory; cited by per-file docs |
| src/backend/parser/analyze.c | 2026-06-01 | ef6a95c7c64 | deep-read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/analyze.c.md | Dispatcher (transformStmt) + four parse_analyze_* entries |
| src/backend/parser/parse_clause.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_clause.c.md | FROM/WHERE/GROUP/ORDER/WINDOW; namespace mechanics |
| src/backend/parser/parse_expr.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_expr.c.md | transformExpr dispatcher; ~30 per-node sub-transforms |
| src/backend/parser/parse_relation.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_relation.c.md | Namespace + RTE construction + fuzzy match |
| src/backend/parser/parse_target.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_target.c.md | Target lists + star expansion + assignment subscripting |
| src/backend/parser/parser.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parser.c.md | raw_parser + base_yylex lookahead filter |
| src/backend/parser/scansup.c | 2026-06-01 | ef6a95c7c64 | skim | parser+rewrite file-by-file | knowledge/files/src/backend/parser/scansup.c.md | Identifier downcasing/truncation |
| src/backend/parser/scan.l | 2026-06-01 | ef6a95c7c64 | skim | parser+rewrite file-by-file | knowledge/files/src/backend/parser/scan.l.md | Flex lexer; no-backtrack invariant; sync with psqlscan/pgc |
| src/backend/parser/gram.y | 2026-06-01 | ef6a95c7c64 | skim | parser+rewrite file-by-file | knowledge/files/src/backend/parser/gram.y.md | Bison grammar; no catalog access |
| src/backend/parser/parse_func.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_func.c.md | Function/agg/window resolution + table.col disambiguation |
| src/backend/parser/parse_type.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_type.c.md | TypeName → (Oid, typmod, collation) |
| src/backend/parser/parse_oper.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_oper.c.md | Operator overload resolution + per-process cache |
| src/backend/parser/parse_coerce.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_coerce.c.md | Type coercion engine; CoercionContext rules |
| src/backend/parser/parse_agg.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_agg.c.md | Aggregates + windows + parseCheckAggregates |
| src/backend/parser/parse_collate.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_collate.c.md | Post-pass collation assignment |
| src/backend/parser/parse_param.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_param.c.md | $n hook setup; fixed vs variable params |
| src/backend/parser/parse_cte.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_cte.c.md | WITH; recursive CTE arm unification |
| src/backend/parser/parse_merge.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_merge.c.md | MERGE: target+source RTEs + per-WHEN MergeAction |
| src/backend/parser/parse_jsontable.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_jsontable.c.md | JSON_TABLE COLUMNS / PASSING / ON ERROR |
| src/backend/parser/parse_utilcmd.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_utilcmd.c.md | DDL parse-analysis run at EXECUTION time |
| src/backend/parser/parse_node.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_node.c.md | ParseState lifecycle + node-builder helpers |
| src/backend/parser/parse_enr.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_enr.c.md | Ephemeral named relations parser-side passthrough |
| src/backend/parser/parse_graphtable.c | 2026-06-01 | ef6a95c7c64 | skim | parser+rewrite file-by-file | knowledge/files/src/backend/parser/parse_graphtable.c.md | GRAPH_TABLE parse analysis; lowering is in rewrite/ |
| src/backend/parser/gramparse.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/parser/gramparse.h.md | Private flex+bison shared defs |
| src/common/kwlookup.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/common/kwlookup.c.md | Shared keyword binary-search; used by all PG scanners |
| src/include/parser/parse_node.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_node.h.md | ParseState + ParseNamespaceItem + ParseExprKind |
| src/include/parser/parse_clause.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_clause.h.md | parse_clause.c prototypes |
| src/include/parser/parse_expr.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_expr.h.md | transformExpr + Transform_null_equals GUC |
| src/include/parser/parse_relation.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_relation.h.md | addRangeTableEntry* family + namespace API |
| src/include/parser/parse_target.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_target.h.md | Target-list construction prototypes |
| src/include/parser/parse_func.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_func.h.md | FuncDetailCode + ParseFuncOrColumn API |
| src/include/parser/parse_type.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_type.h.md | typenameType* family |
| src/include/parser/parse_oper.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_oper.h.md | oper / make_op / LookupOperName* |
| src/include/parser/parse_coerce.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_coerce.h.md | CoercionContext / CoercionForm enums + coerce_* |
| src/include/parser/parse_agg.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_agg.h.md | transformAggregateCall / parseCheckAggregates |
| src/include/parser/parse_collate.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_collate.h.md | 4-func collation API |
| src/include/parser/parse_param.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_param.h.md | setup_parse_*_parameters hook setup |
| src/include/parser/parse_cte.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_cte.h.md | transformWithClause + analyzeCTETargetList |
| src/include/parser/parse_merge.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_merge.h.md | transformMergeStmt |
| src/include/parser/parse_utilcmd.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/parse_utilcmd.h.md | transformCreate/Alter/Index/Rule/Trigger* |
| src/include/parser/analyze.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/parser/analyze.h.md | parse_analyze_* + post_parse_analyze_hook |
| src/backend/rewrite/rewriteHandler.c | 2026-06-01 | ef6a95c7c64 | deep-read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteHandler.c.md | QueryRewrite + RewriteQuery + fireRIRrules; ordering claims |
| src/backend/rewrite/rewriteDefine.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteDefine.c.md | CREATE RULE + view _RETURN rule installation |
| src/backend/rewrite/rewriteRemove.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteRemove.c.md | DROP RULE |
| src/backend/rewrite/rewriteManip.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteManip.c.md | Var renumbering + qual splicing library |
| src/backend/rewrite/rewriteSearchCycle.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteSearchCycle.c.md | SEARCH/CYCLE clause lowering for recursive CTEs |
| src/backend/rewrite/rewriteSupport.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteSupport.c.md | relhasrules toggle + get_rewrite_oid |
| src/backend/rewrite/rowsecurity.c | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rowsecurity.c.md | RLS policy fetch + PERMISSIVE/RESTRICTIVE composition |
| src/backend/rewrite/rewriteGraphTable.c | 2026-06-01 | ef6a95c7c64 | skim | parser+rewrite file-by-file | knowledge/files/src/backend/rewrite/rewriteGraphTable.c.md | GRAPH_TABLE → subquery lowering |
| src/include/rewrite/rewriteHandler.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rewriteHandler.h.md | QueryRewrite + AcquireRewriteLocks API |
| src/include/rewrite/rewriteDefine.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rewriteDefine.h.md | DefineRule + DefineQueryRewrite API |
| src/include/rewrite/rewriteManip.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rewriteManip.h.md | Tree-manipulation library API |
| src/include/rewrite/rewriteRemove.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rewriteRemove.h.md | RemoveRewriteRuleById |
| src/include/rewrite/rewriteSearchCycle.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rewriteSearchCycle.h.md | rewriteSearchAndCycle |
| src/include/rewrite/rewriteSupport.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rewriteSupport.h.md | ViewSelectRuleName "_RETURN" + helpers |
| src/include/rewrite/rowsecurity.h | 2026-06-01 | ef6a95c7c64 | read | parser+rewrite file-by-file | knowledge/files/src/include/rewrite/rowsecurity.h.md | RowSecurityPolicy + get_row_security_policies |

<!-- utils/cache file-by-file phase -->
| src/backend/utils/cache/relcache.c | 2026-06-01 | ef6a95c7c64 | deep-read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/relcache.c.md | RelationData cache + init file; two-phase RelationCacheInvalidate; CIC retry loop |
| src/backend/utils/cache/catcache.c | 2026-06-01 | ef6a95c7c64 | deep-read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/catcache.c.md | CatCTup/CatCList; hash-only inval (VACUUM FULL safety); in-progress stack for detoast race |
| src/backend/utils/cache/syscache.c | 2026-06-01 | ef6a95c7c64 | deep-read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/syscache.c.md | Named-cache layer; SearchSysCacheLocked1 two-fetch protocol vs inplace updates |
| src/backend/utils/cache/inval.c | 2026-06-01 | ef6a95c7c64 | deep-read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/inval.c.md | SI dispatcher; commit-before-broadcast; init-file pre/post bracket; subxact append |
| src/backend/utils/cache/plancache.c | 2026-06-01 | ef6a95c7c64 | deep-read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/plancache.c.md | PREPARE/EXECUTE; generic-vs-custom 5-trial heuristic; CachedExpression |
| src/backend/utils/cache/partcache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/partcache.c.md | rd_partkey + rd_partcheck lazy build; partition keys never change |
| src/backend/utils/cache/lsyscache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/lsyscache.c.md | ~131 SearchSysCache wrappers; AttStatsSlot get/free pair |
| src/backend/utils/cache/typcache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/typcache.c.md | Immortal entries; three callbacks (Type/Opc/Rel/Constr); RelIdToTypeIdCacheHash |
| src/backend/utils/cache/attoptcache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/attoptcache.c.md | Per-attribute storage opts; hash shared with ATTNUM syscache |
| src/backend/utils/cache/spccache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/spccache.c.md | Tablespace cost opts; coarse full-wipe on any pg_tablespace inval |
| src/backend/utils/cache/evtcache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/evtcache.c.md | Event trigger cache; tri-state rebuild guard against mid-rebuild inval |
| src/backend/utils/cache/ts_cache.c | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/backend/utils/cache/ts_cache.c.md | TS parser/dict/config caches; backend-lifetime entries; subsidiary realloc caveat |
| src/include/utils/relcache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/relcache.h.md | Relation typedef + IndexAttrBitmapKind + criticalRelcachesBuilt globals |
| src/include/utils/catcache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/catcache.h.md | CatCache/CatCTup/CatCList struct layouts; CATCACHE_MAXKEYS=4 |
| src/include/utils/syscache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/syscache.h.md | SearchSysCache surface + numbered macros |
| src/include/utils/inval.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/inval.h.md | Inval dispatcher API + debug_discard_caches GUC |
| src/include/utils/plancache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/plancache.h.md | CachedPlanSource / CachedPlan / CachedExpression layouts + lifecycle API |
| src/include/utils/partcache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/partcache.h.md | PartitionKeyData struct + inline column-level accessors |
| src/include/utils/lsyscache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/lsyscache.h.md | AttStatsSlot + IOFuncSelector + OpIndexInterpretation |
| src/include/utils/typcache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/typcache.h.md | TypeCacheEntry + TYPECACHE_* flags + DomainConstraintRef |
| src/include/utils/attoptcache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/attoptcache.h.md | AttributeOpts varlena struct |
| src/include/utils/spccache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/spccache.h.md | Three tablespace cost accessors |
| src/include/utils/evtcache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/utils/evtcache.h.md | EventTriggerEvent enum + EventTriggerCacheItem |
| src/include/tsearch/ts_cache.h | 2026-06-01 | ef6a95c7c64 | read | utils-cache-file-by-file | knowledge/files/src/include/tsearch/ts_cache.h.md | TSAnyCacheEntry common header + TSParser/Dict/Config entries |
| src/backend/storage/ipc/ipc.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/ipc.c.md | proc_exit/shmem_exit + three callback registries; misnamed (no IPC) |
| src/backend/storage/ipc/ipci.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/ipci.c.md | CreateSharedMemoryAndSemaphores; refactored to use subsystemlist.h |
| src/backend/storage/ipc/shmem.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/shmem.c.md | Bump allocator + ShmemIndex + ShmemRequestStruct callback machinery |
| src/backend/storage/ipc/procarray.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/procarray.c.md | GetSnapshotData lock-free reuse via xactCompletionCount; group XID clear |
| src/backend/storage/ipc/sinval.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/sinval.c.md | sinval send/receive facade + catchup-signal daisy chain |
| src/backend/storage/ipc/sinvaladt.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/sinvaladt.c.md | 4096-slot circular sinval queue; SInvalReadLock SHARED writers own ProcState |
| src/backend/storage/ipc/latch.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/latch.c.md | Latch + thin WaitLatch wrapper over singleton LatchWaitSet |
| src/backend/storage/ipc/waiteventset.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/waiteventset.c.md | epoll/kqueue/poll/Win32 abstraction; SIGURG-based wakeup |
| src/backend/storage/ipc/dsm.c | 2026-06-01 | ef6a95c7c64 | deep-read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/dsm.c.md | DSM convenience layer + control segment refcount table |
| src/backend/storage/ipc/dsm_impl.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/dsm_impl.c.md | POSIX/SysV/Windows/mmap backends for dsm_impl_op |
| src/backend/storage/ipc/dsm_registry.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/dsm_registry.c.md | Named DSM/DSA/DSHash for late-loaded extensions |
| src/backend/storage/ipc/barrier.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/barrier.c.md | Static + dynamic process barriers (NOT memory barriers) |
| src/backend/storage/ipc/procsignal.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/procsignal.c.md | Multiplexed SIGUSR1 + global barrier generation mechanism |
| src/backend/storage/ipc/signalfuncs.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/signalfuncs.c.md | pg_cancel/terminate_backend, pg_reload_conf, pg_rotate_logfile |
| src/backend/storage/ipc/pmsignal.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/pmsignal.c.md | Children to postmaster signaling + per-slot ACTIVE/ASSIGNED/UNUSED |
| src/backend/storage/ipc/shm_mq.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/shm_mq.c.md | SPSC shared-mem queue; ring with atomic read/write cursors |
| src/backend/storage/ipc/shm_toc.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/shm_toc.c.md | Table of contents inside DSM (entries from start, allocs from end) |
| src/backend/storage/ipc/standby.c | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/backend/storage/ipc/standby.c.md | Hot standby recovery-conflict resolution + RecoveryLockHash |
| src/include/storage/procarray.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/procarray.h.md | Public procarray API |
| src/include/storage/shmem.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/shmem.h.md | ShmemStructOpts + ShmemCallbacks + legacy ShmemInitStruct |
| src/include/storage/shm_toc.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/shm_toc.h.md | TOC API + estimator macros |
| src/include/storage/shm_mq.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/shm_mq.h.md | shm_mq_send/receive + result enum |
| src/include/storage/dsm.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/dsm.h.md | dsm_create/attach/detach + pin variants + on_dsm_detach |
| src/include/storage/dsm_impl.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/dsm_impl.h.md | DSM_IMPL_* IDs + dsm_op + min_dynamic_shared_memory GUC |
| src/include/storage/dsm_registry.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/dsm_registry.h.md | GetNamedDSMSegment / GetNamedDSA / GetNamedDSHash |
| src/include/storage/latch.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/latch.h.md | Latch struct + canonical wait-loop pattern in header comment |
| src/include/storage/waiteventset.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/waiteventset.h.md | WL_* bitmask + WakeupMyProc/WakeupOtherProc declarations |
| src/include/storage/barrier.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/barrier.h.md | Process Barrier struct + API; NOT memory barriers (see port/atomics.h) |
| src/include/storage/sinval.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/sinval.h.md | SharedInvalidationMessage union + 7 message-type codes |
| src/include/storage/sinvaladt.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/sinvaladt.h.md | Shared-queue layer thin facade |
| src/include/storage/procsignal.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/procsignal.h.md | ProcSignalReason (10) + ProcSignalBarrierType (6) + 32B cancel key |
| src/include/storage/pmsignal.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/pmsignal.h.md | PMSignalReason (11) + QuitSignalReason + PostmasterIsAlive inline fast path |
| src/include/storage/standby.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/standby.h.md | RecoveryConflictReason (8) + RunningTransactionsData |
| src/include/storage/ipc.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | knowledge/files/src/include/storage/ipc.h.md | PG_ENSURE_ERROR_CLEANUP macro + exit API + ipci.c entrypoints |
| src/include/storage/subsystemlist.h | 2026-06-01 | ef6a95c7c64 | read | storage-ipc-file-by-file | (cited inline) | Ordered list of all builtin ShmemCallbacks driving startup init |
| src/backend/libpq/be-secure.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | TLS/GSS multiplex; retry-on-EAGAIN with latch |
| src/backend/libpq/be-secure-openssl.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | OpenSSL provider; SNI clienthello; ALPN |
| src/backend/libpq/be-secure-common.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | passphrase cmd; key perms; pg_hosts.conf loader |
| src/backend/libpq/be-secure-gssapi.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | 16 KB GSS packet size is part of the wire protocol |
| src/backend/libpq/auth.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | ClientAuthentication dispatch switch; auth_failed; set_authn_id |
| src/backend/libpq/auth-sasl.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | Generic SASL exchange loop used by SCRAM + OAuth |
| src/backend/libpq/auth-scram.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | SCRAM-SHA-256 mech impl; not fully read |
| src/backend/libpq/auth-oauth.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | OAUTHBEARER mech impl; not fully read |
| src/backend/libpq/be-fsstubs.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | lo_* SQL fns; LO descriptors live in per-xact memcxt |
| src/backend/libpq/crypt.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | get_role_password, encrypt_password, md5/plain verify |
| src/backend/libpq/hba.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | check_hba (linear first-match), load_hba, parse_hba_line, ident usermap |
| src/backend/libpq/ifaddr.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | pg_range_sockaddr netmask math used by hba.c |
| src/backend/libpq/pqcomm.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | Socket I/O; ListenServerPort/AcceptConnection/pq_getmessage |
| src/backend/libpq/pqformat.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | Message build/parse helpers; typsend/typreceive |
| src/backend/libpq/pqmq.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | shm_mq variant of PQcommMethods for parallel workers |
| src/backend/libpq/pqsignal.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | BlockSig/UnBlockSig/StartupBlockSig masks |
| src/backend/libpq/README.SSL | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md | Only README in libpq; SSL flow + EDH rationale |
| src/include/libpq/libpq.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md, knowledge/subsystems/headers-wave3.md | PQcommMethods vtable; secure_* API |
| src/include/libpq/libpq-be.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md, knowledge/subsystems/headers-wave3.md | Port struct; ClientConnectionInfo; be_tls_* API |
| src/include/libpq/libpq-fs.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | INV_READ/INV_WRITE only |
| src/include/libpq/auth.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | PG_MAX_AUTH_TOKEN_LENGTH; hook types |
| src/include/libpq/hba.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/libpq-backend.md, knowledge/subsystems/headers-wave3.md | UserAuth enum; HbaLine; TokenizedAuthLine |
| src/include/libpq/pqcomm.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | Protocol constants shared with frontend |
| src/include/libpq/pqformat.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | Header for pqformat.c protos |
| src/include/libpq/pqmq.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | pq_redirect_to_shm_mq protos |
| src/include/libpq/pqsignal.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | Backend sigset masks |
| src/include/libpq/sasl.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | pg_be_sasl_mech callbacks; PG_SASL_EXCHANGE_* |
| src/include/libpq/scram.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | pg_be_scram_mech extern; parse_scram_secret |
| src/include/libpq/crypt.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | PasswordType enum; MAX_ENCRYPTED_PASSWORD_LEN |
| src/include/libpq/be-fsstubs.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | lo_read/lo_write C entry; AtEOXact_LargeObject |
| src/backend/port/atomics.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/port.md | u64 atomic simulation via per-atomic spinlock |
| src/backend/port/posix_sema.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/port.md | POSIX PGSemaphore; cache-line-padded sem_t |
| src/backend/port/sysv_sema.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/port.md | SysV semget impl; SEMAS_PER_SET=16 < SEMMSL |
| src/backend/port/sysv_shmem.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/port.md | mmap-anon shmem + tiny SysV interlock since 9.3 |
| src/backend/port/win32_shmem.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/port.md | Win32 CreateFileMapping; protective-region reattach dance |
| src/include/port/atomics.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | Per-arch dispatch; frontend-forbidden |
| src/include/port/atomics/arch-arm.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | ARM atomics overrides |
| src/include/port/atomics/arch-x86.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | x86 inline-asm barriers + spinlock |
| src/include/port/atomics/arch-ppc.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | PPC atomics overrides |
| src/include/port/atomics/fallback.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | Spinlock-based last-resort impl |
| src/include/port/atomics/generic.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | Generic helpers built on primitives |
| src/include/port/atomics/generic-gcc.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | __atomic/__sync builtins |
| src/include/port/atomics/generic-msvc.h | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/headers-wave3.md | MSVC intrinsics |
| src/backend/main/main.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/main.md | Process startup; DispatchOption switch; root check |
| src/backend/foreign/foreign.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/foreign.md | FDW catalog accessors; GetFdwRoutine* dispatch |
| src/include/foreign/foreign.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/foreign.md, knowledge/subsystems/headers-wave3.md | ForeignServer/Table/UM/DataWrapper structs |
| src/include/foreign/fdwapi.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/foreign.md, knowledge/subsystems/headers-wave3.md | FdwRoutine vtable; all callback typedefs |
| src/backend/jit/jit.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | Provider-indep dispatch; sticky-failure load; resowner |
| src/backend/jit/README | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | Architectural rationale; FATAL-on-OOM; type sync; inlining |
| src/backend/jit/llvm/llvmjit.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | LLVM context pool; ORC LLJIT setup; type imports |
| src/backend/jit/llvm/llvmjit_deform.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | slot_compile_deform: per-TupleDesc deform fn |
| src/backend/jit/llvm/llvmjit_expr.c | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | llvm_compile_expr: ExprState->steps codegen |
| src/backend/jit/llvm/llvmjit_inline.cpp | 2026-06-01 | ef6a95c7c64 | skim | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | Cross-module inliner using bitcode indexes |
| src/backend/jit/llvm/llvmjit_wrap.cpp | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | LLVMGetFunctionType + safe SectionMemoryManager bridge |
| src/backend/jit/llvm/llvmjit_error.cpp | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/jit.md | enter/leave_fatal_on_oom; ereport(FATAL) handlers |
| src/include/jit/jit.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/jit.md, knowledge/subsystems/headers-wave3.md | PGJIT_* flags; JitContext; JitProviderCallbacks |
| src/include/jit/llvmjit.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/jit.md, knowledge/subsystems/headers-wave3.md | LLVMJitContext; type globals; codegen entry pts |
| src/backend/partitioning/partbounds.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/partitioning.md | Bound build + sort + three bsearches (list/range/hash) |
| src/backend/partitioning/partprune.c | 2026-06-01 | ef6a95c7c64 | deep-read | leaf-subsystems-wave3 | knowledge/subsystems/partitioning.md | Pruning step gen + interpreter; planner+exec entry |
| src/backend/partitioning/partdesc.c | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/partitioning.md | PartitionDesc two-descriptor cache; PartitionDirectory |
| src/include/partitioning/partbounds.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/partitioning.md, knowledge/subsystems/headers-wave3.md | PartitionBoundInfoData; bsearch protos |
| src/include/partitioning/partprune.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/partitioning.md, knowledge/subsystems/headers-wave3.md | PartitionPruneContext; PruneCxtStateIdx |
| src/include/partitioning/partdesc.h | 2026-06-01 | ef6a95c7c64 | read | leaf-subsystems-wave3 | knowledge/subsystems/partitioning.md, knowledge/subsystems/headers-wave3.md | PartitionDescData + streak-detect cache fields |
| src/backend/replication/README | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/README.md | Walreceiver-libpq split + walsender PM shutdown ordering |
| src/backend/replication/walsender.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/walsender.c.md | exec_replication_command dispatch + WalSndLoop + Start{Physical,Logical}Replication |
| src/backend/replication/walreceiver.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/walreceiver.c.md | Standby-side WAL receiver auxproc; libpq adapter loaded dynamically |
| src/backend/replication/walreceiverfuncs.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/walreceiverfuncs.c.md | Startup-process side of walreceiver IPC; WalRcvData shmem |
| src/backend/replication/slot.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/slot.c.md | ReplicationSlot create/acquire/invalidate; locking trio; on-disk format |
| src/backend/replication/slotfuncs.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/slotfuncs.c.md | SQL-callable slot wrappers; SlotSyncSkipReason map |
| src/backend/replication/syncrep.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/syncrep.c.md | SyncRepWaitForLSN + per-mode queues + FIRST/ANY semantics |
| src/backend/replication/repl_gram.y | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/replication/repl_gram.y.md | Replication-command grammar surface |
| src/backend/replication/repl_scanner.l | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/replication/repl_scanner.l.md | Flex lexer; fprintf→ereport hack |
| src/backend/replication/syncrep_gram.y | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/replication/syncrep_gram.y.md | synchronous_standby_names parser |
| src/backend/backup/basebackup.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/backup/basebackup.c.md | BASE_BACKUP entry from walsender; bbsink chain |
| src/backend/backup/backup_manifest.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/backup_manifest.c.md | JSON backup manifest emitter |
| src/backend/backup/basebackup_sink.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | bbsink vtable |
| src/backend/backup/basebackup_copy.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | TAR-over-COPY sink |
| src/backend/backup/basebackup_server.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | Server-side target sink |
| src/backend/backup/basebackup_gzip.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | gzip compressor sink |
| src/backend/backup/basebackup_lz4.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | lz4 compressor sink |
| src/backend/backup/basebackup_progress.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | pg_stat_progress_basebackup plumbing |
| src/backend/backup/basebackup_incremental.c | 2026-06-01 | ef6a95c7c64 | skim | replication-wave3 | knowledge/files/src/backend/backup/basebackup_supporting.md | UPLOAD_MANIFEST + block-tracking |
| src/backend/replication/logical/decode.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/decode.c.md | LogicalDecodingProcessRecord + rmgr dispatch + filter logic |
| src/backend/replication/logical/reorderbuffer.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/reorderbuffer.c.md | Txn reassembly + spill-to-disk + toast reassembly + max-heap eviction |
| src/backend/replication/logical/logical.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/logical.c.md | LogicalDecodingContext lifecycle + plugin callback wrappers |
| src/backend/replication/logical/logicalfuncs.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/logicalfuncs.c.md | SQL SRFs pg_logical_slot_*_changes |
| src/backend/replication/logical/snapbuild.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/snapbuild.c.md | Historic catalog snapshot building; START→BUILDING→FULL→CONSISTENT |
| src/backend/replication/logical/worker.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/worker.c.md | Apply worker; streamed xacts; 2PC tristate; RDT state machine |
| src/backend/replication/logical/tablesync.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/tablesync.c.md | Per-rel tablesync state machine INIT→...→READY |
| src/backend/replication/logical/launcher.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/launcher.c.md | Worker pool, conflict-detection slot xmin aggregation |
| src/backend/replication/logical/proto.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/proto.c.md | logicalrep_write_* / read_* wire format |
| src/backend/replication/logical/relation.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/relation.c.md | Subscriber relmap cache + attrmap + invalidation |
| src/backend/replication/logical/conflict.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/conflict.c.md | PG18 ConflictType + ReportApplyConflict |
| src/backend/replication/logical/origin.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/origin.c.md | Replication origins; 2-byte id; per-slot lwlock for remote/local LSN |
| src/backend/replication/logical/applyparallelworker.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/applyparallelworker.c.md | Parallel apply DSM + stream/xact session locks for deadlock detection |
| src/backend/replication/logical/slotsync.c | 2026-06-01 | ef6a95c7c64 | deep-read | replication-wave3 | knowledge/files/src/backend/replication/logical/slotsync.c.md | Primary→standby logical slot sync; RS_TEMPORARY→RS_PERSISTENT |
| src/backend/replication/logical/message.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/message.c.md | Generic logical messages (LogLogicalMessage) |
| src/backend/replication/pgoutput/pgoutput.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/pgoutput/pgoutput.c.md | Built-in pub/sub output plugin |
| src/backend/replication/logical/logicalctl.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/logicalctl.c.md | Dynamic logical-decoding activation (PG18 effective_wal_level) |
| src/backend/replication/logical/sequencesync.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/sequencesync.c.md | PG18 sequence sync state INIT→READY |
| src/backend/replication/logical/syncutils.c | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/backend/replication/logical/syncutils.c.md | Common helpers for table/sequence sync workers |
| src/include/replication/walsender.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | Walsender public surface; CRSSnapshotAction |
| src/include/replication/walsender_private.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | WalSnd + WalSndCtlData; grammar entry exports |
| src/include/replication/walreceiver.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | WalRcvData + libpqwalreceiver vtable |
| src/include/replication/slot.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | ReplicationSlot + persistency + invalidation cause bitmask |
| src/include/replication/slotsync.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | Slot-sync exports |
| src/include/replication/syncrep.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | Sync-rep wait modes + SyncRepConfigData |
| src/include/replication/output_plugin.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | OutputPluginCallbacks vtable |
| src/include/replication/logical.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | LogicalDecodingContext layout |
| src/include/replication/logicalproto.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | LogicalRepMsgType + protocol version constants |
| src/include/replication/logicalrelation.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | LogicalRepRelMapEntry |
| src/include/replication/logicalworker.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | Worker entrypoints |
| src/include/replication/logicallauncher.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | Launcher GUCs + APIs |
| src/include/replication/decode.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | XLogRecordBuffer + per-rmgr decode entries |
| src/include/replication/reorderbuffer.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | ReorderBufferChange/TXN + spill path constants |
| src/include/replication/snapbuild.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | SnapBuildState 4-stage enum |
| src/include/replication/origin.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | xl_replorigin_set/drop + DoNotReplicateId sentinel |
| src/include/replication/conflict.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | ConflictType + ConflictTupleInfo |
| src/include/replication/message.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | xl_logical_message |
| src/include/replication/pgoutput.h | 2026-06-01 | ef6a95c7c64 | read | replication-wave3 | knowledge/files/src/include/replication/headers.md | PGOutputData |

<!-- optimizer wave 3 (plan/path/prep/util/geqo + headers) file-by-file phase -->
| src/backend/optimizer/plan/analyzejoins.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/plan/analyzejoins.c.md | Join removal + reduce_unique_semijoins + remove_useless_self_joins |
| src/backend/optimizer/plan/initsplan.c | 2026-06-01 | ef6a95c7c64 | deep-read | optimizer-wave3 | knowledge/files/src/backend/optimizer/plan/initsplan.c.md | RelOptInfo/EC/SJI construction; PHI freeze invariant |
| src/backend/optimizer/plan/planagg.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/plan/planagg.c.md | MIN/MAX → indexscan ORDER BY LIMIT 1 |
| src/backend/optimizer/plan/planmain.c | 2026-06-01 | ef6a95c7c64 | deep-read | optimizer-wave3 | knowledge/files/src/backend/optimizer/plan/planmain.c.md | query_planner: ordering spec for planner phases |
| src/backend/optimizer/plan/setrefs.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/plan/setrefs.c.md | set_plan_references: 9-item planner-finalization contract |
| src/backend/optimizer/plan/subselect.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/plan/subselect.c.md | SubLink/CTE → SubPlan/InitPlan; outer_params discipline |
| src/backend/optimizer/path/clausesel.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/clausesel.c.md | Range-query pairing; extended stats first |
| src/backend/optimizer/path/equivclass.c | 2026-06-01 | ef6a95c7c64 | deep-read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/equivclass.c.md | EC machinery; opfamily-consistency rule; duplicate-derived intentional |
| src/backend/optimizer/path/indxpath.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/indxpath.c.md | Index path generation; partial-index predicate recheck |
| src/backend/optimizer/path/joinpath.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/joinpath.c.md | add_paths_to_joinrel; UNIQUE_OUTER/INNER local-only jointypes |
| src/backend/optimizer/path/joinrels.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/joinrels.c.md | DP level construction; mark_dummy_rel GEQO context discipline |
| src/backend/optimizer/path/pathkeys.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/pathkeys.c.md | Canonical pathkey machinery; mergeclause EC update |
| src/backend/optimizer/path/tidpath.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/path/tidpath.c.md | TidScan/TidRangeScan path generation; CurrentOfExpr preserved |
| src/backend/optimizer/prep/prepqual.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/prep/prepqual.c.md | negate_clause + canonicalize_qual; AND/OR flatness preservation |
| src/backend/optimizer/prep/prepjointree.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/prep/prepjointree.c.md | Required invocation order; pull_up_subqueries + reduce_outer_joins |
| src/backend/optimizer/prep/preptlist.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/prep/preptlist.c.md | preprocess_targetlist; update_colnos vs processed_tlist resnos |
| src/backend/optimizer/prep/prepunion.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/prep/prepunion.c.md | plan_set_operations; UNION ALL appendrel split-out |
| src/backend/optimizer/prep/prepagg.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/prep/prepagg.c.md | AggInfo/AggTransInfo CSE + shared transition state |
| src/backend/optimizer/util/appendinfo.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/appendinfo.c.md | Parent↔child Var translation; ROWID_VAR machinery |
| src/backend/optimizer/util/clauses.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/clauses.c.md | Expression probes + eval_const_expressions home |
| src/backend/optimizer/util/extendplan.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/extendplan.c.md | Planner extension state slots; used by GEQO |
| src/backend/optimizer/util/inherit.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/inherit.c.md | expand_inherited_rtentry; apply_child_basequals |
| src/backend/optimizer/util/joininfo.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/joininfo.c.md | Per-baserel joininfo maintenance |
| src/backend/optimizer/util/orclauses.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/orclauses.c.md | extract_restriction_or_clauses |
| src/backend/optimizer/util/paramassign.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/paramassign.c.md | paramExecTypes/plan_params/curOuterParams three-structure split |
| src/backend/optimizer/util/placeholder.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/placeholder.c.md | PlaceHolderVar/PHI lifecycle; deconstruct_jointree freeze |
| src/backend/optimizer/util/plancat.c | 2026-06-01 | ef6a95c7c64 | deep-read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/plancat.c.md | get_relation_info catalog gateway; no-lock invariant |
| src/backend/optimizer/util/predtest.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/predtest.c.md | predicate_implied_by / predicate_refuted_by; immutable-only |
| src/backend/optimizer/util/relnode.c | 2026-06-01 | ef6a95c7c64 | deep-read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/relnode.c.md | RelOptInfo build/lookup; find_base_rel ERRORs |
| src/backend/optimizer/util/restrictinfo.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/restrictinfo.c.md | make_restrictinfo + extract_actual_*; commute_restrictinfo shares structure |
| src/backend/optimizer/util/tlist.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/tlist.c.md | Targetlist utilities; tlist_same_* ignores labeling |
| src/backend/optimizer/util/var.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/util/var.c.md | pull_varnos/varattnos/var_clause; flatten_join_alias_vars |
| src/backend/optimizer/geqo/geqo_main.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_main.c.md | GA driver; registered as planner extension |
| src/backend/optimizer/geqo/geqo_eval.c | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_eval.c.md | Fitness fn; gimme_tree clump merging |
| src/backend/optimizer/geqo/geqo_pool.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_pool.c.md | Pool/Chromosome alloc + spread_chromo |
| src/backend/optimizer/geqo/geqo_selection.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_selection.c.md | linear_rand selection bias |
| src/backend/optimizer/geqo/geqo_recombination.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_recombination.c.md | init_tour + shared crossover utilities |
| src/backend/optimizer/geqo/geqo_erx.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_erx.c.md | Default ERX crossover |
| src/backend/optimizer/geqo/geqo_pmx.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_pmx.c.md | Optional PMX |
| src/backend/optimizer/geqo/geqo_cx.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_cx.c.md | Optional CX |
| src/backend/optimizer/geqo/geqo_ox1.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_ox1.c.md | Optional OX1 |
| src/backend/optimizer/geqo/geqo_ox2.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_ox2.c.md | Optional OX2 |
| src/backend/optimizer/geqo/geqo_px.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_px.c.md | Optional PX |
| src/backend/optimizer/geqo/geqo_mutation.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_mutation.c.md | CX-only mutation |
| src/backend/optimizer/geqo/geqo_random.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_random.c.md | per-PlannerInfo pg_prng_state wrapper |
| src/backend/optimizer/geqo/geqo_copy.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_copy.c.md | geqo_copy memcpy |
| src/backend/optimizer/geqo/geqo_misc.c | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/backend/optimizer/geqo/geqo_misc.c.md | GEQO_DEBUG printers |
| src/include/optimizer/optimizer.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/optimizer.h.md | Public planner API for non-planner code |
| src/include/optimizer/cost.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/cost.h.md | DEFAULT_*_COST + cost_* + enable_* GUCs |
| src/include/optimizer/paths.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/paths.h.md | Aggregated optimizer/path/ prototypes |
| src/include/optimizer/pathnode.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/pathnode.h.md | create_*_path API + relnode.c API + build_simple_rel_hook |
| src/include/optimizer/planmain.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/planmain.h.md | optimizer/plan/ prototypes + cursor_tuple_fraction GUC |
| src/include/optimizer/planner.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/planner.h.md | planner.c internals (subquery_planner, standard_planner) |
| src/include/optimizer/appendinfo.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/appendinfo.h.md | appendinfo.c prototypes |
| src/include/optimizer/clauses.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/clauses.h.md | clauses.c internal API |
| src/include/optimizer/extendplan.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/extendplan.h.md | Planner extension state API |
| src/include/optimizer/inherit.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/inherit.h.md | inherit.c prototypes |
| src/include/optimizer/joininfo.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/joininfo.h.md | joininfo.c prototypes |
| src/include/optimizer/orclauses.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/orclauses.h.md | extract_restriction_or_clauses |
| src/include/optimizer/paramassign.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/paramassign.h.md | paramassign.c prototypes |
| src/include/optimizer/placeholder.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/placeholder.h.md | PHV/PHI API |
| src/include/optimizer/plancat.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/plancat.h.md | get_relation_info + constraint_exclusion enum |
| src/include/optimizer/prep.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/prep.h.md | Aggregated optimizer/prep/ prototypes |
| src/include/optimizer/restrictinfo.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/restrictinfo.h.md | RestrictInfo API |
| src/include/optimizer/subselect.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/subselect.h.md | SS_* prototypes |
| src/include/optimizer/tlist.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/tlist.h.md | tlist.c prototypes |
| src/include/optimizer/geqo.h | 2026-06-01 | ef6a95c7c64 | read | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo.h.md | GEQO GUCs + recombination #defines + GeqoPrivateData |
| src/include/optimizer/geqo_gene.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_gene.h.md | Gene/Chromosome/Pool types |
| src/include/optimizer/geqo_misc.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_misc.h.md | Debug printers |
| src/include/optimizer/geqo_mutation.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_mutation.h.md | geqo_mutation |
| src/include/optimizer/geqo_pool.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_pool.h.md | Pool API |
| src/include/optimizer/geqo_random.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_random.h.md | per-PlannerInfo PRNG |
| src/include/optimizer/geqo_recombination.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_recombination.h.md | Per-operator prototypes + Edge/City types |
| src/include/optimizer/geqo_selection.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_selection.h.md | geqo_selection + linear_rand |
| src/include/optimizer/geqo_copy.h | 2026-06-01 | ef6a95c7c64 | skim | optimizer-wave3 | knowledge/files/src/include/optimizer/geqo_copy.h.md | geqo_copy |
| src/backend/commands/tablecmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/tablecmds.c.md | Three-phase ALTER TABLE driver; rewrite-vs-validate; lock-level computation |
| src/backend/commands/indexcmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/indexcmds.c.md | DefineIndex; CIC three-txn protocol; REINDEX CONCURRENTLY |
| src/backend/commands/copy.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/copy.c.md | COPY option parsing + dispatch |
| src/backend/commands/copyfrom.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/copyfrom.c.md | Multi-insert fast path; ON_ERROR/FREEZE |
| src/backend/commands/copyfromparse.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/copyfromparse.c.md | Four-stage buffer pipeline; SIMD line scan |
| src/backend/commands/copyto.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/copyto.c.md | COPY TO formats + CopyDestReceiver |
| src/backend/commands/vacuum.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/vacuum.c.md | VACUUM driver; cutoffs + failsafe; cost-delay |
| src/backend/commands/analyze.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/analyze.c.md | Two-stage sampling; 300*attstattarget; Vitter |
| src/backend/commands/repack.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/repack.c.md | Replaces cluster.c; concurrent mode via logical-decoding bgworker |
| src/backend/commands/define.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/define.c.md | DefElem extractors used by all *cmds.c |
| src/backend/commands/alter.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/alter.c.md | Generic ALTER OWNER/RENAME/SET SCHEMA |
| src/backend/commands/dbcommands.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/dbcommands.c.md | CREATE DATABASE WAL_LOG vs FILE_COPY; LockSharedObject |
| src/backend/commands/schemacmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/schemacmds.c.md | CREATE SCHEMA with embedded subcommands |
| src/backend/commands/tablespace.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/tablespace.c.md | Symlink layout; in_place_tablespaces |
| src/backend/commands/typecmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/typecmds.c.md | Types + domains + enums + ranges |
| src/backend/commands/operatorcmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/operatorcmds.c.md | DefineOperator; shell-then-fix self-references |
| src/backend/commands/aggregatecmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/aggregatecmds.c.md | DefineAggregate; moving aggregates |
| src/backend/commands/functioncmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/functioncmds.c.md | Functions/procedures/casts/transforms; CALL txn control |
| src/backend/commands/view.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/view.c.md | Views as ON SELECT rules |
| src/backend/commands/matview.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/matview.c.md | REFRESH MATERIALIZED VIEW; CONCURRENTLY delta |
| src/backend/commands/trigger.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/trigger.c.md | Trigger queue; transition tables; deferred firing |
| src/backend/commands/event_trigger.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/event_trigger.c.md | DDL/login event triggers; command stash |
| src/backend/commands/prepare.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/prepare.c.md | PREPARE/EXECUTE; generic-vs-custom plan choice |
| src/backend/commands/portalcmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/portalcmds.c.md | DECLARE CURSOR; WITH HOLD persistence |
| src/backend/commands/explain.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/explain.c.md | EXPLAIN walker; SERIALIZE option |
| src/backend/commands/extension.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/extension.c.md | Control-file parser shared with GUC; creating_extension flag |
| src/backend/commands/dropcmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/dropcmds.c.md | Generic-DROP dispatcher; IF EXISTS wording |
| src/backend/commands/discard.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/discard.c.md | DISCARD ALL session-state reset; pooler-critical |
| src/backend/commands/lockcmds.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/lockcmds.c.md | LOCK TABLE; view recursion |
| src/backend/commands/seclabel.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/seclabel.c.md | SECURITY LABEL; provider registry |
| src/backend/commands/comment.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/comment.c.md | COMMENT ON; comments are not dependencies |
| src/backend/commands/amcmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/amcmds.c.md | CREATE/DROP ACCESS METHOD |
| src/backend/commands/async.c | 2026-06-01 | ef6a95c7c64 | read | commands-wave3 | knowledge/files/src/backend/commands/async.c.md | NOTIFY/LISTEN; SLRU queue model |
| src/backend/commands/collationcmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/collationcmds.c.md | Collation version drift handling |
| src/backend/commands/conversioncmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/conversioncmds.c.md | CREATE CONVERSION (tiny) |
| src/backend/commands/foreigncmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/foreigncmds.c.md | FDW/SERVER/USER MAPPING + IMPORT FOREIGN SCHEMA |
| src/backend/commands/opclasscmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/opclasscmds.c.md | Opclass/opfamily DDL; strategy/support numbers |
| src/backend/commands/policy.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/policy.c.md | RLS policy DDL; PERMISSIVE/RESTRICTIVE combine |
| src/backend/commands/publicationcmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/publicationcmds.c.md | Publication DDL; row filters & col lists |
| src/backend/commands/sequence.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/sequence.c.md | nextval log-cnt trick; single-page hot spot |
| src/backend/commands/statscmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/statscmds.c.md | Extended-stats DDL |
| src/backend/commands/subscriptioncmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/subscriptioncmds.c.md | Subscription DDL; two_phase; run_as_owner |
| src/backend/commands/tsearchcmds.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/tsearchcmds.c.md | Parser/template/dict/config mapping model |
| src/backend/commands/user.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/user.c.md | Roles; SET/INHERIT/ADMIN separation |
| src/backend/commands/variable.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/variable.c.md | GUC check/assign/show triples for specialised vars |
| src/backend/commands/wait.c | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/backend/commands/wait.c.md | WAIT FOR LSN (PG 18+; replaces waitlsn) |
| src/include/commands/alter.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/alter.h.md | |
| src/include/commands/async.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/async.h.md | |
| src/include/commands/collationcmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/collationcmds.h.md | |
| src/include/commands/comment.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/comment.h.md | |
| src/include/commands/conversioncmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/conversioncmds.h.md | |
| src/include/commands/copy.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/copy.h.md | |
| src/include/commands/copyfrom_internal.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/copyfrom_internal.h.md | |
| src/include/commands/createas.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/createas.h.md | |
| src/include/commands/dbcommands.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/dbcommands.h.md | |
| src/include/commands/defrem.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/defrem.h.md | Cross-cutting catch-all header |
| src/include/commands/discard.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/discard.h.md | |
| src/include/commands/event_trigger.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/event_trigger.h.md | |
| src/include/commands/explain.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/explain.h.md | |
| src/include/commands/explain_dr.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/explain_dr.h.md | |
| src/include/commands/extension.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/extension.h.md | |
| src/include/commands/lockcmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/lockcmds.h.md | |
| src/include/commands/matview.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/matview.h.md | |
| src/include/commands/policy.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/policy.h.md | |
| src/include/commands/portalcmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/portalcmds.h.md | |
| src/include/commands/prepare.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/prepare.h.md | |
| src/include/commands/proclang.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/proclang.h.md | |
| src/include/commands/publicationcmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/publicationcmds.h.md | MAX_RELCACHE_INVAL_MSGS=4096 |
| src/include/commands/schemacmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/schemacmds.h.md | |
| src/include/commands/seclabel.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/seclabel.h.md | |
| src/include/commands/sequence.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/sequence.h.md | FormData_pg_sequence_data tuple layout |
| src/include/commands/subscriptioncmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/subscriptioncmds.h.md | |
| src/include/commands/tablecmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/tablecmds.h.md | |
| src/include/commands/tablespace.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/tablespace.h.md | xl_tblspc_create_rec |
| src/include/commands/trigger.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/trigger.h.md | TriggerData; ExecB[SR]/A[SR]/IR families |
| src/include/commands/typecmds.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/typecmds.h.md | |
| src/include/commands/user.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/user.h.md | check_password_hook |
| src/include/commands/vacuum.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/vacuum.h.md | VacuumParams, VacuumCutoffs, VacAttrStats |
| src/include/commands/view.h | 2026-06-01 | ef6a95c7c64 | skim | commands-wave3 | knowledge/files/src/include/commands/view.h.md | |

<!-- executor file-by-file phase, wave 3 -->
| src/backend/executor/execExpr.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execExpr.c.md | Expression compilation; ExecBuild*; ExprSetupInfo; FETCHSOME setup |
| src/backend/executor/execExprInterp.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execExprInterp.c.md | Interpreter; direct vs switch threading; ExecJust* fast paths |
| src/backend/executor/execScan.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execScan.c.md | Generic qual+project loop for scan nodes |
| src/backend/executor/execTuples.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execTuples.c.md | TupleTableSlot 4 kinds + slot_deform_heap_tuple |
| src/backend/executor/execUtils.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execUtils.c.md | EState/ExprContext lifecycle; range-table API |
| src/backend/executor/execGrouping.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execGrouping.c.md | TupleHashTable shared by HashAgg/Hashjoin/SetOp/Memoize |
| src/backend/executor/execAmi.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/execAmi.c.md | ReScan/MarkPos/RestrPos dispatcher |
| src/backend/executor/execAsync.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execAsync.c.md | Async exec protocol — Append + ForeignScan |
| src/backend/executor/execJunk.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/execJunk.c.md | JunkFilter — strip CTID/rowmark junk before client |
| src/backend/executor/execIndexing.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execIndexing.c.md | Speculative-insert protocol; unique/exclusion enforcement |
| src/backend/executor/execParallel.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execParallel.c.md | Leader-side parallel setup; worker entry ParallelQueryMain |
| src/backend/executor/execPartition.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/execPartition.c.md | Tuple routing + runtime partition pruning |
| src/backend/executor/execReplication.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/execReplication.c.md | Logical-rep apply: RelationFindReplTuple*, ExecSimple* |
| src/backend/executor/execCurrent.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/execCurrent.c.md | WHERE CURRENT OF — search_plan_tree |
| src/backend/executor/execSRF.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/execSRF.c.md | SRF protocol (ValuePerCall + Materialize) for funcs/ProjectSet |
| src/backend/executor/instrument.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/instrument.c.md | EXPLAIN ANALYZE instrumentation + pgBufferUsage diff |
| src/backend/executor/functions.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/functions.c.md | SQL-language function executor; fmgr_sql + lazy/eager |
| src/backend/executor/tqueue.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/tqueue.c.md | shm_mq tuple passing between leader and workers |
| src/backend/executor/tstoreReceiver.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/tstoreReceiver.c.md | DestReceiver -> Tuplestore (WITH HOLD detoast option) |
| src/backend/executor/nodeAgg.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeAgg.c.md | HashAgg + sorted Agg; aggsplit modes; spill protocol |
| src/backend/executor/nodeHash.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeHash.c.md | HashJoinTable build, batch growth, chunked allocator |
| src/backend/executor/nodeHashjoin.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeHashjoin.c.md | Hybrid hashjoin + PHJ barrier phase machine |
| src/backend/executor/nodeMergejoin.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeMergejoin.c.md | Sort-merge join state machine |
| src/backend/executor/nodeModifyTable.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeModifyTable.c.md | DML driver; Prologue/Act/Epilogue; MERGE; cross-partition UPDATE |
| src/backend/executor/nodeAppend.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeAppend.c.md | Append serial+parallel+async; runtime pruning |
| src/backend/executor/nodeMergeAppend.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeMergeAppend.c.md | k-way merge via binaryheap |
| src/backend/executor/nodeSort.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeSort.c.md | tuplesort wrapper + datum-sort fast path + bounded sort |
| src/backend/executor/nodeIncrementalSort.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeIncrementalSort.c.md | Dual-tuplesort per-prefix-group sort |
| src/backend/executor/nodeMaterial.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeMaterial.c.md | Tuplestore buffer for rescan/mark/restore/backward |
| src/backend/executor/nodeLimit.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeLimit.c.md | LIMIT/OFFSET + WITH TIES + PERCENT; tuples_needed |
| src/backend/executor/nodeWindowAgg.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeWindowAgg.c.md | Window functions + sliding-window agg via inverse trans |
| src/backend/executor/nodeGather.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeGather.c.md | Leader-side worker fan-in (unordered) |
| src/backend/executor/nodeGatherMerge.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeGatherMerge.c.md | Order-preserving k-way merge over worker queues |
| src/backend/executor/nodeIndexscan.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeIndexscan.c.md | Index-driven scan; kNN reorder; runtime keys |
| src/backend/executor/nodeIndexonlyscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeIndexonlyscan.c.md | VM check + heap fallback for index-only |
| src/backend/executor/nodeBitmapHeapscan.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeBitmapHeapscan.c.md | TIDBitmap-driven heap scan; lossy pages |
| src/backend/executor/nodeBitmapIndexscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeBitmapIndexscan.c.md | MultiExec returning TIDBitmap from amgetbitmap |
| src/backend/executor/nodeBitmapAnd.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeBitmapAnd.c.md | tbm_intersect of children |
| src/backend/executor/nodeBitmapOr.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeBitmapOr.c.md | tbm_union of children |
| src/backend/executor/nodeTidscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeTidscan.c.md | TID-set fetch with qsort+qunique |
| src/backend/executor/nodeTidrangescan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeTidrangescan.c.md | CTID range scan via table_relation_scan_tid_range |
| src/backend/executor/nodeSamplescan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeSamplescan.c.md | TABLESAMPLE driver via TsmRoutine |
| src/backend/executor/nodeGroup.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeGroup.c.md | Bare GROUP BY without aggregates |
| src/backend/executor/nodeSubqueryscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeSubqueryscan.c.md | FROM-clause subquery shim |
| src/backend/executor/nodeSubplan.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeSubplan.c.md | SubPlan expression; InitPlan; hashed ANY/ALL |
| src/backend/executor/nodeCtescan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeCtescan.c.md | Non-recursive WITH reader (shared tuplestore) |
| src/backend/executor/nodeWorktablescan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeWorktablescan.c.md | Working-table scan inside recursive CTE |
| src/backend/executor/nodeRecursiveunion.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeRecursiveunion.c.md | Recursive-CTE driver; semi-naive evaluation |
| src/backend/executor/nodeForeignscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeForeignscan.c.md | FdwRoutine shim + async-capable callbacks |
| src/backend/executor/nodeCustom.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeCustom.c.md | CustomScan extension dispatch |
| src/backend/executor/nodeLockRows.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeLockRows.c.md | SELECT FOR UPDATE/SHARE row locking + EPQ |
| src/backend/executor/nodeSetOp.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeSetOp.c.md | INTERSECT/EXCEPT (sorted + hashed) |
| src/backend/executor/nodeUnique.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeUnique.c.md | Consecutive-dup removal over sorted input |
| src/backend/executor/nodeResult.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeResult.c.md | No-input projection + One-Time Filter |
| src/backend/executor/nodeValuesscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeValuesscan.c.md | VALUES clause; per-row ExprState |
| src/backend/executor/nodeProjectSet.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeProjectSet.c.md | SRF-in-TLIST driver; LCM cardinality |
| src/backend/executor/nodeTableFuncscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeTableFuncscan.c.md | XMLTABLE/JSON_TABLE via TableFuncRoutine |
| src/backend/executor/nodeFunctionscan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeFunctionscan.c.md | FROM-clause function; ROWS FROM zip; ordinality |
| src/backend/executor/nodeNamedtuplestorescan.c | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/backend/executor/nodeNamedtuplestorescan.c.md | Transition-table named tuplestore scan |
| src/backend/executor/nodeMemoize.c | 2026-06-01 | ef6a95c7c64 | deep-read | executor-wave3 | knowledge/files/src/backend/executor/nodeMemoize.c.md | LRU cache over parameterized inner scan |
| src/include/executor/executor.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/executor.h.md | eflags + ExecutorStart/Run/Finish/End + ExecEvalExpr/ExecQual/ExecProject |
| src/include/executor/execdesc.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/execdesc.h.md | QueryDesc layout + CreateQueryDesc |
| src/include/executor/execExpr.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/execExpr.h.md | ExprEvalOp opcode enum; ExprEvalStep; JIT-shared helpers |
| src/include/executor/instrument.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/instrument.h.md | BufferUsage/WalUsage/Instrumentation + INSTRUMENT_* options |
| src/include/executor/nodeAgg.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeAgg.h.md | AggStatePerTrans/PerAgg/PerGroup/PerPhase/PerHash struct layouts |
| src/include/executor/nodeAppend.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeAppend.h.md | Append prototypes + ExecAsyncAppendResponse |
| src/include/executor/nodeHashjoin.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeHashjoin.h.md | HashJoin prototypes + ExecHashJoinSaveTuple |
| src/include/executor/nodeHash.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeHash.h.md | HashJoinTable lifecycle + ExecChooseHashTableSize |
| src/include/executor/nodeIndexscan.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeIndexscan.h.md | ExecIndexBuildScanKeys + runtime/array key helpers |
| src/include/executor/nodeMergejoin.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeMergejoin.h.md | MergeJoin prototypes (no parallel) |
| src/include/executor/nodeModifyTable.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeModifyTable.h.md | ModifyTable + Generated columns + MERGE slots |
| src/include/executor/nodeSort.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeSort.h.md | Sort prototypes (Mark/Restore + parallel) |
| src/include/executor/nodeSubplan.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeSubplan.h.md | SubPlan + InitPlan + ExecSetParamPlanMulti |
| src/include/executor/nodeWindowAgg.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/nodeWindowAgg.h.md | WindowAgg prototypes |
| src/include/executor/tablefunc.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/tablefunc.h.md | TableFuncRoutine callback bundle |
| src/include/executor/tuptable.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/tuptable.h.md | TupleTableSlot + ops vtable + 4 builtin slot kinds |
| src/include/executor/tstoreReceiver.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/tstoreReceiver.h.md | Create+SetParams two-step DestReceiver setup |
| src/include/executor/functions.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/functions.h.md | SQLFunctionParseInfo + fmgr_sql |
| src/include/executor/spi_priv.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/spi_priv.h.md | _SPI_PLAN_MAGIC + _SPI_connection layout |
| src/include/executor/execPartition.h | 2026-06-01 | ef6a95c7c64 | read | executor-wave3 | knowledge/files/src/include/executor/execPartition.h.md | PartitionDispatch + PartitionTupleRouting API |
| src/backend/access/brin/README | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/brin/README.md | Canonical narrative for the Block Range Index (BRIN) access method. |
| src/backend/access/brin/brin.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/brin/brin.c.md | The public-interface module of the BRIN access method. |
| src/backend/access/common/attmap.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/attmap.c.md | Build and manage AttrMap: a mapping from output-column attnum → input-column ... |
| src/backend/access/common/bufmask.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/bufmask.c.md | Page-masking helpers used ONLY during WAL consistency checking (wal_consisten... |
| src/backend/access/common/detoast.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/detoast.c.md | Read side of TOAST: given a possibly-EXTERNAL, possibly-COMPRESSED varlena po... |
| src/backend/access/common/heaptuple.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/common/heaptuple.c.md | Heap-tuple format helpers used by every table AM, not just heap/. |
| src/backend/access/common/indextuple.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/indextuple.c.md | Build, deform and trim IndexTuple values. |
| src/backend/access/common/printsimple.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/printsimple.c.md | A no-catalog-access DestReceiver. |
| src/backend/access/common/printtup.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/common/printtup.c.md | The DestReceiver implementation that converts query result tuples into the Po... |
| src/backend/access/common/relation.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/relation.c.md | The lowest-level "open any relation by OID" helpers, shared by tables, indexe... |
| src/backend/access/common/reloptions.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/reloptions.c.md | Core support for pg_class.reloptions and pg_tablespace.spcoptions: a typed-op... |
| src/backend/access/common/scankey.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/scankey.c.md | Three tiny initializers for ScanKeyData: filling out the struct with the righ... |
| src/backend/access/common/session.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/session.c.md | Encapsulates "user session" state that must be SHARED between the leader and ... |
| src/backend/access/common/syncscan.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/syncscan.c.md | Cross-backend synchronization of sequential scans on the same table. |
| src/backend/access/common/tidstore.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/tidstore.c.md | An in-memory set of ItemPointerData (block + offset), organised as a radix tr... |
| src/backend/access/common/toast_compression.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/toast_compression.c.md | The compression algorithms supported for TOAST: PGLZ (always built in) and LZ... |
| src/backend/access/common/toast_internals.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/common/toast_internals.c.md | The TOAST storage layer: compress, save and delete out-of-line values in a TO... |
| src/backend/access/common/tupconvert.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/common/tupconvert.c.md | Convert a tuple from one TupleDesc to a logically-equivalent but differently-... |
| src/backend/access/common/tupdesc.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/common/tupdesc.c.md | Build, copy, compare, ref-count and free TupleDesc objects. |
| src/backend/access/heap/README | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/heap/README.md | Two design documents that explain non-obvious heap-AM mechanisms: |
| src/backend/access/heap/heapam.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/heap/heapam.c.md | The heart of the heap access method. |
| src/backend/access/heap/heapam_handler.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/heap/heapam_handler.c.md | "Wires up the lower level heapam.c et al routines with the tableam abstractio... |
| src/backend/access/heap/heapam_visibility.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/heap/heapam_visibility.c.md | Implements every MVCC visibility test in PostgreSQL. |
| src/backend/access/heap/heapam_xlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/heap/heapam_xlog.c.md | WAL redo for the heap access method. |
| src/backend/access/heap/hio.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/heap/hio.c.md | Implements heap I/O placement: place a prepared tuple on a locked buffer (Rel... |
| src/backend/access/heap/pruneheap.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/heap/pruneheap.c.md | Implements heap page pruning and HOT-chain management: on-access pruning (hea... |
| src/backend/access/heap/rewriteheap.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/heap/rewriteheap.c.md | Support routines for completely rewriting a heap relation while preserving vi... |
| src/backend/access/heap/vacuumlazy.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/heap/vacuumlazy.c.md | The lazy ("concurrent", non-blocking) VACUUM driver for heap relations. |
| src/backend/access/heap/visibilitymap.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/heap/visibilitymap.c.md | Implements the visibility map fork: a 2-bits-per-heap-page bitmap (ALL_VISIBL... |
| src/backend/access/index/amapi.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/index/amapi.c.md | Index-AM-API plumbing: call an AM's handler function to fetch the IndexAmRout... |
| src/backend/access/index/amvalidate.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/index/amvalidate.c.md | Catalog-traversal helpers shared by all index AMs' amvalidate and amadjustmem... |
| src/backend/access/index/genam.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/index/genam.c.md | The "general index AM" facade with two distinct roles: |
| src/backend/access/index/indexam.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/index/indexam.c.md | The per-tuple dispatch layer of the index AM API. |
| src/backend/access/sequence/sequence.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/sequence/sequence.c.md | Two-function file: sequence_open and sequence_close. |
| src/backend/access/table/table.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/table/table.c.md | Thin wrappers over relation_open* that ALSO enforce "this must be something y... |
| src/backend/access/table/tableam.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/table/tableam.c.md | The bigger-than-inline parts of the table-AM dispatch layer. |
| src/backend/access/table/tableamapi.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/table/tableamapi.c.md | Two responsibilities: |
| src/backend/access/table/toast_helper.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/table/toast_helper.c.md | Reusable helpers for table-AM implementations that need to TOAST varlena attr... |
| src/backend/access/tablesample/bernoulli.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/tablesample/bernoulli.c.md | The BERNOULLI TABLESAMPLE method: per-tuple sampling. |
| src/backend/access/tablesample/system.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/tablesample/system.c.md | The SYSTEM TABLESAMPLE method: block-level sampling. |
| src/backend/access/tablesample/tablesample.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/tablesample/tablesample.c.md | One function: GetTsmRoutine(tsmhandler). |
| src/backend/access/transam/README | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/README.md | The README is the canonical narrative for the access/transam subsystem. |
| src/backend/access/transam/clog.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/clog.c.md | The pg_xact (formerly pg_clog) commit-log manager. |
| src/backend/access/transam/commit_ts.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/commit_ts.c.md | SLRU storing (commit timestamp, ReplOriginId) per committed transaction. |
| src/backend/access/transam/generic_xlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/generic_xlog.c.md | Generic WAL: lets extensions (and core) record arbitrary page changes without... |
| src/backend/access/transam/multixact.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/multixact.c.md | The pg_multixact SLRU manager. |
| src/backend/access/transam/parallel.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/parallel.c.md | Infrastructure for launching parallel workers. |
| src/backend/access/transam/rmgr.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/rmgr.c.md | Builds the global RmgrTable array of resource-manager records by #include-ing... |
| src/backend/access/transam/slru.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/slru.c.md | Generic "Simple LRU" page-buffer machinery for permanent SLRU files indexed b... |
| src/backend/access/transam/subtrans.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/subtrans.c.md | Stores the immediate parent TransactionId for each transaction; used to resol... |
| src/backend/access/transam/timeline.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/timeline.c.md | Read/write timeline history files (<tli>.history). |
| src/backend/access/transam/transam.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/transam.c.md | High-level "did this XID commit / abort" interface on top of pg_xact. |
| src/backend/access/transam/twophase.c | 2026-06-02 | 4b0bf0788b0 | deep-read | cloud:pg-file-backfiller | knowledge/files/src/backend/access/transam/twophase.c.md | Implements PREPARE TRANSACTION / COMMIT PREPARED / ROLLBACK PREPARED. Re-verified at anchor + deepened (DELAY_CHKPT mechanics, logical-rep conflict detection, redo dedup). |
| src/backend/access/transam/twophase_rmgr.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/transam/twophase_rmgr.c.md | Static dispatch tables mapping TwoPhaseRmgrId to the recover / postcommit / p... |
| src/backend/access/transam/varsup.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/varsup.c.md | Postgres OID and XID counter management. |
| src/backend/access/transam/xact.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xact.c.md | Top-level transaction system. |
| src/backend/access/transam/xlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlog.c.md | The WAL manager's runtime spine: it coordinates database startup (StartupXLOG... |
| src/backend/access/transam/xlogarchive.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogarchive.c.md | Backend-side helpers for the WAL archive. |
| src/backend/access/transam/xlogbackup.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogbackup.c.md | Builds the text contents for backup_label and <...>.backup history files emit... |
| src/backend/access/transam/xlogfuncs.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogfuncs.c.md | SQL-level user interface to WAL: pg_backup_start, pg_backup_stop, pg_switch_w... |
| src/backend/access/transam/xloginsert.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xloginsert.c.md | Producer-side WAL: collect registered buffers and data via the XLogBeginInser... |
| src/backend/access/transam/xlogprefetcher.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogprefetcher.c.md | Drop-in replacement for an XLogReader that looks ahead in the WAL and issues ... |
| src/backend/access/transam/xlogreader.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogreader.c.md | The portable WAL-record decoder. |
| src/backend/access/transam/xlogrecovery.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogrecovery.c.md | Owns the WAL recovery state machine. |
| src/backend/access/transam/xlogstats.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogstats.c.md | Tiny utility module: per-record byte counting for tools that compute WAL stat... |
| src/backend/access/transam/xlogutils.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogutils.c.md | Helpers shared by redo routines: buffer-fetch with "missing / truncated" haza... |
| src/backend/access/transam/xlogwait.c | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/backend/access/transam/xlogwait.c.md | Implements blocking waits for WAL operations to reach specific LSNs, on both ... |
| src/backend/backup/basebackup_supporting | 2026-06-01 | ef6a95c7c64 | skim | reconciliation-backfill | knowledge/files/src/backend/backup/basebackup_supporting.md | Group doc for the basebackup sink implementations and helpers, all reached |
| src/backend/utils/adt/array_typanalyze.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/array_typanalyze.c.md | The custom ANALYZE per-column statistics gatherer for array columns. |
| src/backend/utils/adt/array_userfuncs.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/array_userfuncs.c.md | User-visible array support functions — the SQL-callable layer over arrayfuncs... |
| src/backend/utils/adt/arrayfuncs.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/arrayfuncs.c.md | Core support for PostgreSQL's polymorphic array type: I/O, subscripting (get/... |
| src/backend/utils/adt/jsonb.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/jsonb.c.md | I/O routines for the jsonb data type: text → binary (jsonb_in), binary → text... |
| src/backend/utils/adt/jsonb_op.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/jsonb_op.c.md | > "Special operators for jsonb only, used by various index access methods" |
| src/backend/utils/adt/like.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/like.c.md | The LIKE / NOT LIKE / ILIKE / NOT ILIKE operators with %/_ wildcard semantics. |
| src/backend/utils/adt/numeric.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/numeric.c.md | The arbitrary-precision exact decimal NUMERIC data type. |
| src/backend/utils/adt/selfuncs.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/selfuncs.c.md | The standard library of selectivity estimators (oprrest and oprjoin functions... |
| src/backend/utils/adt/varchar.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/varchar.c.md | Implementation of the SQL types char(n) (= bpchar, blank-padded) and varchar(n). |
| src/backend/utils/adt/varlena.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/adt/varlena.c.md | Functions for variable-length built-in types — text, bytea, the varlena infra... |
| src/backend/utils/sort/logtape.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/sort/logtape.c.md | Provides the illusion of N independent "tape devices" multiplexed onto a sing... |
| src/backend/utils/sort/qsort_interruptible.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/sort/qsort_interruptible.c.md | A single line of useful content: provide a qsort_arg-shaped sort function tha... |
| src/backend/utils/sort/sortsupport.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/sort/sortsupport.c.md | Setup helpers for the SortSupport API — PostgreSQL's reduced-overhead alterna... |
| src/backend/utils/sort/tuplesort.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/sort/tuplesort.c.md | Generalized tuple-sort engine. |
| src/backend/utils/sort/tuplesortvariants.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/sort/tuplesortvariants.c.md | The per-variant glue layer over the generic engine in tuplesort.c. |
| src/backend/utils/sort/tuplestore.c | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/backend/utils/sort/tuplestore.c.md | Materialized intermediate result. |
| src/include/access/attmap.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/attmap.h.md | Defines AttrMap (output-attnum → input-attnum mapping) and declares the const... |
| src/include/access/clog.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/clog.h.md | Public interface to pg_xact. |
| src/include/access/commit_ts.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/commit_ts.h.md | Public interface for the commit-timestamp SLRU. |
| src/include/access/detoast.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/detoast.h.md | Declares the public TOAST read API plus the VARATT_EXTERNAL_GET_POINTER macro... |
| src/include/access/generic_xlog.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/generic_xlog.h.md | The four-function public API for generic xlog records (open / register buffer... |
| src/include/access/heapam.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/heapam.h.md | Public API of the heap table access method: scan descriptors, insert/update/d... |
| src/include/access/heapam_xlog.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/heapam_xlog.h.md | Defines every WAL record type emitted by the heap access method, the opcode n... |
| src/include/access/hio.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/hio.h.md | Tiny header exposing two functions and one state struct that together make up... |
| src/include/access/htup.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/htup.h.md | Lightweight public header that defines the in-memory HeapTupleData wrapper (l... |
| src/include/access/htup_details.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/htup_details.h.md | Defines the on-disk layout of a heap tuple's fixed header (HeapTupleHeaderDat... |
| src/include/access/multixact.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/multixact.h.md | Public interface to pg_multixact. |
| src/include/access/parallel.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/parallel.h.md | Public interface for the parallel-worker infrastructure. |
| src/include/access/printtup.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/printtup.h.md | Declares the wire-protocol DestReceiver factory printtup_create_DR, the SendR... |
| src/include/access/relation.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/relation.h.md | Declares the AM-agnostic relation-open primitives: relation_open, try_relatio... |
| src/include/access/reloptions.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/reloptions.h.md | Public typedefs and prototypes for the reloptions framework. |
| src/include/access/rmgr.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/rmgr.h.md | Defines RmgrId (uint8), the RmgrIds enum built from rmgrlist.h, the built-in ... |
| src/include/access/scankey.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/scankey.h.md | Defines ScanKeyData / ScanKey and the SK_* flag bits. |
| src/include/access/session.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/session.h.md | Defines the Session struct and declares the four lifecycle functions implemen... |
| src/include/access/slru.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/slru.h.md | Public interface to slru.c: the SlruDesc / SlruShared descriptors, the page-s... |
| src/include/access/subtrans.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/subtrans.h.md | Tiny header exposing the eight pg_subtrans entry points. |
| src/include/access/toast_compression.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/toast_compression.h.md | Defines the on-disk compression-method identifiers ('p', 'l', …) used in pg_a... |
| src/include/access/transam.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/transam.h.md | The lowest-level transaction-ID arithmetic and shared TransamVariables struct. |
| src/include/access/tupdesc.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/tupdesc.h.md | Defines TupleDesc (the backend's canonical rowtype descriptor) plus the auxil... |
| src/include/access/tupdesc_details.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/tupdesc_details.h.md | Internal header holding the AttrMissing struct definition (used to record "va... |
| src/include/access/twophase.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/twophase.h.md | Public interface to twophase.c. |
| src/include/access/twophase_rmgr.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/twophase_rmgr.h.md | Defines the dispatch tables and IDs for 2PC-aware subsystems. |
| src/include/access/visibilitymap.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/visibilitymap.h.md | Public API for the per-relation visibility map (VM) fork. |
| src/include/access/xact.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xact.h.md | Public interface for xact.c: isolation/read-only/deferrable GUCs, synchronous... |
| src/include/access/xlog.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlog.h.md | The public façade of the WAL manager. |
| src/include/access/xlog_internal.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlog_internal.h.md | WAL-file-level internals: page headers, segment math, filename encoding, the ... |
| src/include/access/xlogarchive.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlogarchive.h.md | Prototype-only header for the backend's WAL archive helpers. |
| src/include/access/xlogbackup.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/xlogbackup.h.md | The BackupState struct used to thread base-backup metadata through pg_backup_... |
| src/include/access/xlogdefs.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlogdefs.h.md | The smallest, most-includable WAL types: XLogRecPtr (uint64 LSN), XLogSegNo (... |
| src/include/access/xloginsert.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/xloginsert.h.md | Tiny public header for the WAL-record construction API. |
| src/include/access/xlogprefetcher.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlogprefetcher.h.md | Declarations for the recovery-side WAL prefetcher: a drop-in replacement for ... |
| src/include/access/xlogreader.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/xlogreader.h.md | Public interface to the generic WAL reading facility. |
| src/include/access/xlogrecord.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlogrecord.h.md | The on-disk WAL record format definitions. |
| src/include/access/xlogrecovery.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/xlogrecovery.h.md | Public interface to xlogrecovery.c: recovery-target enums, pause-state enum, ... |
| src/include/access/xlogstats.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/access/xlogstats.h.md | Per-rmgr, per-info counter struct for WAL statistics. |
| src/include/access/xlogutils.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlogutils.h.md | Public surface of xlogutils.c: the HotStandbyState enum, InRecovery / standby... |
| src/include/access/xlogwait.h | 2026-06-01 | ef6a95c7c64 | deep-read | reconciliation-backfill | knowledge/files/src/include/access/xlogwait.h.md | Public interface to xlogwait.c: the WaitLSNType / WaitLSNResult enums, the Wa... |
| src/include/replication/headers | 2026-06-01 | ef6a95c7c64 | skim | reconciliation-backfill | knowledge/files/src/include/replication/headers.md | Group doc for the replication subsystem's public/internal headers. Each |
| src/include/utils/logtape.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/utils/logtape.h.md | Public interface for logtape.c — the multi-tape-multiplexing-into-one- BufFil... |
| src/include/utils/sortsupport.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/utils/sortsupport.h.md | Defines the SortSupport framework: a reduced-overhead alternative to the trad... |
| src/include/utils/tuplesort.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/utils/tuplesort.h.md | Public interface for the generalized tuple-sort engine implemented across tup... |
| src/include/utils/tuplestore.h | 2026-06-01 | ef6a95c7c64 | read | reconciliation-backfill | knowledge/files/src/include/utils/tuplestore.h.md | Public interface for tuplestore.c — the "dumbed-down version of tuplesort.c" ... |
| src/backend/utils/adt/jsonb_util.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/jsonb_util.c.md | iterator + on-disk converter + deep-contains + hash; key sort by (len,memcmp) not collation |
| src/backend/utils/adt/jsonpath.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/jsonpath.c.md | binary tree flatten/unflatten + jspIsMutable planner hook |
| src/backend/utils/adt/jsonpath_exec.c | 2026-06-01 | ef6a95c7c64 | skim | utils-adt-rerun | knowledge/files/src/backend/utils/adt/jsonpath_exec.c.md | recursive sequence-of-values executor; lax mode auto-unwrap; tri-state predicate logic |
| src/backend/utils/adt/jsonpath_gram.y | 2026-06-01 | ef6a95c7c64 | skim | utils-adt-rerun | knowledge/files/src/backend/utils/adt/jsonpath_gram.y.md | bison pure-parser; palloc-backed; produces JsonPathParseItem tree |
| src/backend/utils/adt/jsonpath_scan.l | 2026-06-01 | ef6a95c7c64 | skim | utils-adt-rerun | knowledge/files/src/backend/utils/adt/jsonpath_scan.l.md | flex reentrant scanner; fatal-error rerouted through ereport |
| src/backend/utils/adt/date.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/date.c.md | DateADT=int32 days since 2000; TimeADT=int64 µs; cross-type comparators |
| src/backend/utils/adt/timestamp.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/timestamp.c.md | int64 µs since 2000-01-01 (was double seconds); Interval=month/day/time; interval_cmp normalizes via 30d/24h |
| src/backend/utils/adt/oid.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/oid.c.md | uint32 wire-format; oidvector has lower-bound 0 not 1 |
| src/backend/utils/adt/int.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/int.c.md | int2/int4 + cross-width comparators + in_range for window frames |
| src/backend/utils/adt/int8.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/int8.c.md | int64 ops; int128 intermediate for int8mul overflow check |
| src/backend/utils/adt/float.c | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/backend/utils/adt/float.c.md | -ffast-math is a compile error; shortest-decimal default; Welford float8_accum |
| src/include/utils/jsonb.h | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/include/utils/jsonb.h.md | on-disk JEntry encoding (len-or-offset every 32nd); JsonbValue union; iterator tokens |
| src/include/utils/jsonpath.h | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/include/utils/jsonpath.h.md | JsonPathItemType ordinals are on-disk; jpiNull..jpiBool aliased to jbvNull..jbvBool |
| src/include/utils/date.h | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/include/utils/date.h.md | DateADT/TimeADT/TimeTzADT typedefs; TIMETZ_TYPLEN=12 vs sizeof=16 gotcha |
| src/include/utils/timestamp.h | 2026-06-01 | ef6a95c7c64 | read | utils-adt-rerun | knowledge/files/src/include/utils/timestamp.h.md | Datum macros + INTERVAL_TYPMOD packing + PgStartTime/PgReloadTime globals |
| src/backend/catalog/heap.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/heap.c.md | heap_create_with_catalog 12-step recipe; AccessExclusiveLock on new relid before catalog rows |
| src/backend/catalog/index.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/index.c.md | index_create + REINDEX CONCURRENTLY swap dance; index_build SECURITY_RESTRICTED_OPERATION |
| src/backend/catalog/dependency.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/dependency.c.md | findDependentObjects recursion; DEPFLAG bitset; INTERNAL/EXTENSION owner-flip |
| src/backend/catalog/namespace.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/namespace.c.md | RangeVarGetRelidExtended lock-and-recheck loop; search_path cache; activePathGeneration |
| src/backend/catalog/storage.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/storage.c.md | PendingRelDelete list in TopMemoryContext; atCommit=true vs false; smgrDoPendingDeletes |
| src/backend/catalog/pg_inherits.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/pg_inherits.c.md | inhdetachpending + active-snapshot visibility for concurrent DETACH |
| src/backend/catalog/pg_constraint.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/pg_constraint.c.md | CreateConstraintEntry universal inserter; DeconstructFkConstraintRow |
| src/backend/catalog/aclchk.c | 2026-06-01 | ef6a95c7c64 | deep | catalog-rerun | knowledge/files/src/backend/catalog/aclchk.c.md | GRANT/REVOKE backend + xxx_aclmask family; pg_init_privs for extensions |
| src/backend/catalog/catalog.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/catalog.c.md | IsSharedRelation hardcoded list; IsPinnedObject; GetNewOidWithIndex; GetNewRelFileNumber |
| src/backend/catalog/indexing.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/indexing.c.md | CatalogTupleInsert universal wrapper; no EState → no partial/expression catalog indexes |
| src/backend/catalog/objectaddress.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/objectaddress.c.md | ObjectProperty data-driven table; get_object_address main entry |
| src/backend/catalog/objectaccess.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/objectaccess.c.md | object_access_hook dispatch (POST_CREATE, DROP, POST_ALTER, NAMESPACE_SEARCH, FUNCTION_EXECUTE, TRUNCATE) |
| src/backend/catalog/partition.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/partition.c.md | get_partition_parent via pg_inherits inhseqno=1; map_partition_varattnos |
| src/backend/catalog/toasting.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/toasting.c.md | create_toast_table + needs_toast_table predicate |
| src/backend/catalog/pg_depend.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_depend.c.md | recordDependencyOn + pinning via refclassid=0 |
| src/backend/catalog/pg_shdepend.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_shdepend.c.md | cross-DB deps with dbid; DROP OWNED BY; REASSIGN OWNED |
| src/backend/catalog/pg_proc.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_proc.c.md | ProcedureCreate + language validators + parse-error position transpose |
| src/backend/catalog/pg_type.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_type.c.md | TypeCreate universal entry; TypeShellMake forward decls; makeArrayTypeName |
| src/backend/catalog/pg_operator.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_operator.c.md | OperatorShellMake + Create + COMMUTATOR/NEGATOR back-fill |
| src/backend/catalog/pg_class.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_class.c.md | tiny stub; most pg_class writes are inplace from elsewhere |
| src/backend/catalog/pg_namespace.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_namespace.c.md | NamespaceCreate; rest of schema logic is in namespace.c |
| src/backend/catalog/pg_attrdef.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_attrdef.c.md | StoreAttrDefault flips atthasdef; recordDependencyOnExpr |
| src/backend/catalog/pg_aggregate.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_aggregate.c.md | AggregateCreate signature checks; MOVING AGGREGATE inverse |
| src/backend/catalog/pg_cast.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_cast.c.md | CastCreate; deps on castfunc + types |
| src/backend/catalog/pg_collation.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_collation.c.md | CollationCreate; libc/icu/builtin provider |
| src/backend/catalog/pg_conversion.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_conversion.c.md | ConversionCreate; FindDefaultConversion via search_path |
| src/backend/catalog/pg_db_role_setting.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_db_role_setting.c.md | AlterSetting per-(db,role) GUC overrides; ApplySetting at session start |
| src/backend/catalog/pg_enum.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_enum.c.md | EnumValuesCreate float-spaced sortorder; uncommitted-enum hash; RenumberEnumType |
| src/backend/catalog/pg_largeobject.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_largeobject.c.md | LO metadata + chunks; real lo_* APIs in storage/large_object |
| src/backend/catalog/pg_parameter_acl.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_parameter_acl.c.md | GUC parameter ACL shared catalog; lazy row creation |
| src/backend/catalog/pg_range.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_range.c.md | RangeCreate; subtype + canonical/subdiff func deps |
| src/backend/catalog/pg_publication.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_publication.c.md | publication_add_relation + column lists + row filters; publish_via_partition_root expansion |
| src/backend/catalog/pg_subscription.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_subscription.c.md | GetSubscription; per-(sub,rel) tablesync state machine |
| src/backend/catalog/pg_tablespace.c | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/pg_tablespace.c.md | tiny stub; directory_is_empty for CREATE TABLESPACE |
| src/backend/catalog/_generators.md | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/backend/catalog/_generators.md | genbki.pl + Catalog.pm + system_*.sql + information_schema.sql combined doc |
| src/include/catalog/README | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/_README.md | one-line README; pointer to bki.html docs |
| src/include/catalog/_catalog_headers_overview | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/_catalog_headers_overview.md | 70 pg_*.h headers grouped by domain; BKI markings + LOOKUP graph |
| src/include/catalog/catalog.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/catalog.h.md | catalog.c prototypes |
| src/include/catalog/dependency.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/dependency.h.md | DependencyType character literals are on-disk; PERFORM_DELETION_* flags |
| src/include/catalog/genbki.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/genbki.h.md | CATALOG()/BKI_* macros empty for C, recognised by genbki.pl; BEGIN/END_CATALOG_STRUCT pack for AIX |
| src/include/catalog/heap.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/heap.h.md | CookedConstraint + RawColumnDefault structs; CHKATYPE_* flags |
| src/include/catalog/index.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/index.h.md | INDEX_CREATE_* + INDEX_CONSTR_CREATE_* + IndexStateFlagsAction |
| src/include/catalog/indexing.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/indexing.h.md | CatalogIndexState typedef; DECLARE_UNIQUE_INDEX list |
| src/include/catalog/namespace.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/namespace.h.md | RVRFlags + RangeVarGetRelidCallback typedef + FuncCandidateList |
| src/include/catalog/objectaccess.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/objectaccess.h.md | ObjectAccessType enum + Invoke*Hook macros |
| src/include/catalog/objectaddress.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/objectaddress.h.md | ObjectAddress {classId, objectId, objectSubId} triple |
| src/include/catalog/partition.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/partition.h.md | partition.c prototypes |
| src/include/catalog/storage.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/storage.h.md | storage.c prototypes; wal_skip_threshold GUC |
| src/include/catalog/storage_xlog.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/storage_xlog.h.md | XLOG_SMGR_CREATE/TRUNCATE record formats |
| src/include/catalog/toasting.h | 2026-06-01 | ef6a95c7c64 | read | catalog-rerun | knowledge/files/src/include/catalog/toasting.h.md | toasting.c prototypes |
| src/backend/backup/basebackup_target.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_target.c.md | Extensible target registry; BaseBackupAddTarget API |
| src/backend/backup/basebackup_progress.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_progress.c.md | Mandatory sink; updates bbsink_state.bytes_done + tablespace_num |
| src/backend/backup/basebackup_gzip.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_gzip.c.md | zlib deflate sink |
| src/backend/backup/basebackup_lz4.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_lz4.c.md | lz4frame sink |
| src/backend/backup/basebackup_zstd.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_zstd.c.md | zstd streaming sink + workers |
| src/backend/backup/basebackup_server.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_server.c.md | Server-side target sink |
| src/backend/backup/basebackup_throttle.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/backup/basebackup_throttle.c.md | MAX_RATE token-bucket sleep via WaitLatch |
| src/backend/backup/walsummary.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/backup/walsummary.c.md | WAL summary file layout + completeness check |
| src/common/blkreftable.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/backup/blkreftable.c.md | BlockRefTable: chunked array-or-bitmap per-rel block modification tracking |
| src/backend/statistics/extended_stats.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/statistics/extended_stats.c.md | CREATE STATISTICS driver; statext_clauselist_selectivity (MCV then dependencies) |
| src/backend/statistics/dependencies.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/statistics/dependencies.c.md | Soft functional dependencies; P(a,b) = f*P(a) + (1-f)*P(a)*P(b) |
| src/backend/statistics/mvdistinct.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/statistics/mvdistinct.c.md | Multi-column ndistinct for GROUP BY estimation |
| src/backend/statistics/mcv.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/statistics/mcv.c.md | Multivariate MCV; frequency vs base_frequency combining via mcv_combine_selectivities |
| src/backend/regex/regcomp.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/regex/regcomp.c.md | NFA construction + colormap; #includes all regc_*.c |
| src/backend/regex/regexec.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/regex/regexec.c.md | Lazy DFA execution with NFA fallback for backref/lookaround |
| src/backend/regex/regc_color.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regc_color.c.md | Color partitioning of alphabet (#include into regcomp.c) |
| src/backend/regex/regc_cvec.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regc_cvec.c.md | Character vector for bracket parsing |
| src/backend/regex/regc_lex.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regc_lex.c.md | Lexer (advanced regex flavor) |
| src/backend/regex/regc_locale.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regc_locale.c.md | POSIX character class tables |
| src/backend/regex/regc_nfa.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regc_nfa.c.md | NFA optimization passes (pullback/pushfwd/fixempties/compact) |
| src/backend/regex/regc_pg_locale.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regc_pg_locale.c.md | pg_wchar ctype adapter + cache |
| src/backend/regex/rege_dfa.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/rege_dfa.c.md | Lazy DFA subset (state-set hash, color-indexed transitions) |
| src/backend/regex/regerror.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regerror.c.md | pg_regerror error-message lookup |
| src/backend/regex/regexport.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regexport.c.md | NFA introspection for pg_trgm |
| src/backend/regex/regfree.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regfree.c.md | pg_regfree teardown |
| src/backend/regex/regprefix.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/regprefix.c.md | Extract literal prefix for LIKE/~ indexing |
| src/backend/regex/README | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/regex/_README.md | Reverse-engineered Spencer regex library notes |
| src/backend/tsearch/dict.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/dict.c.md | Standard dictionary SQL interface |
| src/backend/tsearch/dict_ispell.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/dict_ispell.c.md | Ispell template wrapper |
| src/backend/tsearch/dict_simple.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/dict_simple.c.md | lowercase + stopword dict |
| src/backend/tsearch/dict_synonym.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/dict_synonym.c.md | One-word substitution dict |
| src/backend/tsearch/dict_thesaurus.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/dict_thesaurus.c.md | Phrase substitution dict with stem-matched trie |
| src/backend/tsearch/regis.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/regis.c.md | Fast regex subset for affix conditions |
| src/backend/tsearch/spell.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/spell.c.md | Ispell/Hunspell morphology engine |
| src/backend/tsearch/to_tsany.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/to_tsany.c.md | to_tsvector / to_tsquery SQL surface |
| src/backend/tsearch/ts_locale.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/ts_locale.c.md | Multibyte ctype helpers |
| src/backend/tsearch/ts_parse.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/ts_parse.c.md | parsetext driver wiring parser → dict chain |
| src/backend/tsearch/ts_selfuncs.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/ts_selfuncs.c.md | @@ operator selectivity via MCELEM lexeme stats |
| src/backend/tsearch/ts_typanalyze.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/ts_typanalyze.c.md | tsvector ANALYZE lossy-counting MCELEM |
| src/backend/tsearch/ts_utils.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/ts_utils.c.md | get_tsearch_config_filename path resolver |
| src/backend/tsearch/wparser.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/wparser.c.md | ts_parse SQL wrapper |
| src/backend/tsearch/wparser_def.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/tsearch/wparser_def.c.md | Default parser; 26 token types |
| src/backend/utils/activity/pgstat.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat.c.md | Cumulative stats infra: per-kind dispatch, pending → shmem flush |
| src/backend/utils/activity/pgstat_archiver.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_archiver.c.md | Fixed-amount archiver counters |
| src/backend/utils/activity/pgstat_bgwriter.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_bgwriter.c.md | Fixed-amount bgwriter counters |
| src/backend/utils/activity/pgstat_checkpointer.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_checkpointer.c.md | Fixed-amount checkpointer counters (split from bgwriter in PG17) |
| src/backend/utils/activity/pgstat_database.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_database.c.md | Per-db stats + recovery-conflict counters |
| src/backend/utils/activity/pgstat_function.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_function.c.md | Per-function call counts + self/total time |
| src/backend/utils/activity/pgstat_io.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_io.c.md | pg_stat_io 4-D matrix (backend × object × context × op) |
| src/backend/utils/activity/pgstat_relation.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_relation.c.md | Per-table counters + subxact tuple stack + 2PC integration |
| src/backend/utils/activity/pgstat_replslot.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_replslot.c.md | Slot index in memory, slot name on disk |
| src/backend/utils/activity/pgstat_slru.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_slru.c.md | Per-SLRU-pool block/flush/truncate counters |
| src/backend/utils/activity/pgstat_subscription.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_subscription.c.md | Logical-replication subscription error/conflict counters |
| src/backend/utils/activity/pgstat_wal.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_wal.c.md | WAL counters fed from pgWalUsage |
| src/backend/utils/activity/pgstat_xact.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_xact.c.md | Subxact tuple stack + pending drops + 2PC RMID |
| src/backend/utils/activity/pgstat_backend.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/pgstat_backend.c.md | Per-ProcNumber stats, PendingBackendStats fast path |
| src/backend/utils/activity/wait_event.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/wait_event.c.md | pgstat_report_wait_start/end (MyProc->wait_event_info) |
| src/backend/utils/activity/wait_event_funcs.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/wait_event_funcs.c.md | pg_wait_events view, auto-generated body |
| src/backend/utils/activity/backend_progress.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/backend_progress.c.md | pgstat_progress_* infra (20-slot param array) |
| src/backend/utils/activity/backend_status.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/activity/backend_status.c.md | pg_stat_activity slot array + changecount torn-read protocol |
| src/backend/utils/fmgr/dfmgr.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/utils/fmgr/dfmgr.c.md | Dynamic .so loader; PG_MODULE_MAGIC; never unloads; rendezvous vars |
| src/backend/utils/fmgr/funcapi.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/fmgr/funcapi.c.md | SRF + composite/polymorphic helpers |
| src/backend/utils/hash/dynahash.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/utils/hash/dynahash.c.md | Larson linear hashing; partitioned mode disables expand; 32 freelists with scavenging |
| src/backend/utils/hash/pg_crc.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/hash/pg_crc.c.md | CRC-32C and CRC-32 tables (hot loop in src/port) |
| src/backend/utils/mb/mbutils.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/mb/mbutils.c.md | Encoding conversion runtime + same-encoding return-as-is idiom |
| src/backend/utils/mb/conv.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/mb/conv.c.md | LocalToUtf/UtfToLocal generic conversion helpers |
| src/backend/utils/mb/conversion_procs/ | 2026-06-01 | ef6a95c7c64 | skim | final-leafs-rerun | knowledge/files/src/backend/utils/mb/_conversion_procs.md | Per-conversion .so libs loaded on demand |
| src/backend/utils/resowner/resowner.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/utils/resowner/resowner.c.md | Array+hash hybrid; 3-phase release; sort by reverse priority; lock fast-path cache |
| src/backend/utils/misc/guc.c | 2026-06-01 | ef6a95c7c64 | deep | final-leafs-rerun | knowledge/files/src/backend/utils/misc/guc.c.md | GUC engine: source/context precedence, nest-level stack, ALTER SYSTEM |
| src/backend/utils/misc/guc_funcs.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/guc_funcs.c.md | SET/SHOW/RESET SQL surface + pg_settings SRFs |
| src/backend/utils/misc/guc_tables.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/guc_tables.c.md | ConfigureNames* built-in registry |
| src/backend/utils/misc/pg_controldata.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/pg_controldata.c.md | pg_control_* SQL functions |
| src/backend/utils/misc/pg_rusage.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/pg_rusage.c.md | getrusage wrapper for VACUUM VERBOSE |
| src/backend/utils/misc/ps_status.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/ps_status.c.md | argv[0] overwrite for ps/top display |
| src/backend/utils/misc/rls.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/rls.c.md | check_enable_rls + row_security_active() |
| src/backend/utils/misc/sampling.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/sampling.c.md | Algorithm S + reservoir for ANALYZE/TABLESAMPLE |
| src/backend/utils/misc/superuser.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/superuser.c.md | superuser() / superuser_arg with cache + bootstrap escape |
| src/backend/utils/misc/timeout.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/timeout.c.md | Multiplex one SIGALRM across many TimeoutId reasons |
| src/backend/utils/misc/conffiles.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/conffiles.c.md | include/include_dir helpers for postgresql.conf/pg_hba.conf |
| src/backend/utils/misc/stack_depth.c | 2026-06-01 | ef6a95c7c64 | read | final-leafs-rerun | knowledge/files/src/backend/utils/misc/stack_depth.c.md | check_stack_depth() recursion guard |
| src/include/utils/_misc_headers | 2026-06-01 | ef6a95c7c64 | skim | final-leafs-rerun | knowledge/files/src/include/utils/_misc_headers.md | Combined header doc: guc.h, ps_status.h, hsearch.h, resowner.h, wait_event.h, ... |
| src/include/backup/_backup_headers | 2026-06-01 | ef6a95c7c64 | skim | final-leafs-rerun | knowledge/files/src/include/backup/_backup_headers.md | basebackup_sink.h, basebackup_target.h, walsummary.h, ... |
| src/include/statistics/_statistics_headers | 2026-06-01 | ef6a95c7c64 | skim | final-leafs-rerun | knowledge/files/src/include/statistics/_statistics_headers.md | statistics.h + extended_stats_internal.h |
| src/include/regex/_regex_headers | 2026-06-01 | ef6a95c7c64 | skim | final-leafs-rerun | knowledge/files/src/include/regex/_regex_headers.md | regex.h, regexport.h, regguts.h, regerrs.h |
| src/include/tsearch/_tsearch_headers | 2026-06-01 | ef6a95c7c64 | skim | final-leafs-rerun | knowledge/files/src/include/tsearch/_tsearch_headers.md | ts_type.h, ts_public.h, ts_cache.h, dicts/spell.h |
| src/backend/access/brin/brin_pageops.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_pageops.c.md | BRIN page-level update/insert + cross-page lock-order |
| src/backend/access/brin/brin_revmap.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_revmap.c.md | revmap lookup/extend; desummarize protocol |
| src/backend/access/brin/brin_xlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_xlog.c.md | BRIN redo + masking |
| src/backend/access/brin/brin_minmax.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_minmax.c.md | minmax opclass |
| src/backend/access/brin/brin_minmax_multi.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_minmax_multi.c.md | multi-minmax opclass |
| src/backend/access/brin/brin_bloom.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_bloom.c.md | bloom-filter opclass |
| src/backend/access/brin/brin_inclusion.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_inclusion.c.md | inclusion (R-tree-like) opclass |
| src/backend/access/brin/brin_validate.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_validate.c.md | amvalidate for BRIN |
| src/backend/access/brin/brin_tuple.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/brin/brin_tuple.c.md | BRIN on-disk tuple form |
| src/include/access/brin.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin.h.md | BRIN public AM-callable header |
| src/include/access/brin_internal.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin_internal.h.md | BrinOpcInfo + BrinDesc |
| src/include/access/brin_page.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin_page.h.md | BRIN page layout constants |
| src/include/access/brin_pageops.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin_pageops.h.md | brin_pageops prototypes |
| src/include/access/brin_revmap.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin_revmap.h.md | brin_revmap prototypes |
| src/include/access/brin_tuple.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin_tuple.h.md | BrinMemTuple/BrinValues |
| src/include/access/brin_xlog.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/brin_xlog.h.md | BRIN WAL record formats |
| src/backend/access/gin/README | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gin/README.md | GIN README summary |
| src/backend/access/gin/ginbtree.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginbtree.c.md | GIN abstract B-tree engine + split protocol |
| src/backend/access/gin/ginxlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginxlog.c.md | GIN redo + recompress action stream |
| src/backend/access/gin/gininsert.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/gininsert.c.md | GIN insert top-level + parallel build |
| src/backend/access/gin/gindatapage.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/gindatapage.c.md | posting-tree page mechanics |
| src/backend/access/gin/ginentrypage.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginentrypage.c.md | entry-tree leaf format |
| src/backend/access/gin/ginscan.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginscan.c.md | scan setup + extractQuery |
| src/backend/access/gin/ginfast.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginfast.c.md | fastupdate pending list |
| src/backend/access/gin/ginget.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginget.c.md | scan iteration / gingetbitmap |
| src/backend/access/gin/ginlogic.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginlogic.c.md | bool/ternary consistent bridge |
| src/backend/access/gin/ginpostinglist.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginpostinglist.c.md | varbyte posting-list codec |
| src/backend/access/gin/ginutil.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginutil.c.md | ginhandler + entry insert orchestration |
| src/backend/access/gin/ginvacuum.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginvacuum.c.md | GIN VACUUM 2-stage |
| src/backend/access/gin/ginvalidate.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gin/ginvalidate.c.md | amvalidate for GIN |
| src/include/access/gin.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/gin.h.md | GIN public API |
| src/include/access/gin_private.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/gin_private.h.md | GinState + scan/btree internals |
| src/include/access/ginblock.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/ginblock.h.md | GIN on-disk page layouts |
| src/include/access/ginxlog.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/ginxlog.h.md | GIN WAL record formats |
| src/backend/access/gist/README | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gist/README.md | GIST README summary |
| src/backend/access/gist/gist.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gist/gist.c.md | gisthandler + gistdoinsert + gistplacetopage |
| src/backend/access/gist/gistget.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistget.c.md | scan + NSN race + KNN queue |
| src/backend/access/gist/gistproc.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistproc.c.md | 2-D R-tree opclasses (Guttman split) |
| src/backend/access/gist/gistsplit.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistsplit.c.md | multi-column split orchestration |
| src/backend/access/gist/gistxlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistxlog.c.md | GIST redo (NSN stamping, FollowRight) |
| src/backend/access/gist/gistbuild.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistbuild.c.md | sorted-vs-buffering build |
| src/backend/access/gist/gistbuildbuffers.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistbuildbuffers.c.md | temp-file-backed node buffers |
| src/backend/access/gist/gistscan.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistscan.c.md | scan setup; pairing-heap cmp |
| src/backend/access/gist/gistutil.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistutil.c.md | gistfillbuffer + NSN/FollowRight macros + gistNewBuffer |
| src/backend/access/gist/gistvacuum.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistvacuum.c.md | 2-stage VACUUM + NSN-based jump-back |
| src/backend/access/gist/gistvalidate.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/gist/gistvalidate.c.md | amvalidate for GIST |
| src/include/access/gist.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/gist.h.md | GIST public API |
| src/include/access/gist_private.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/gist_private.h.md | GIST internal types |
| src/include/access/gistscan.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/gistscan.h.md | gistscan prototypes |
| src/include/access/gistxlog.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/gistxlog.h.md | GIST WAL record formats |
| src/backend/access/hash/README | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/hash/README.md | hash README summary |
| src/backend/access/hash/hash.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/hash/hash.c.md | hashhandler + build + VACUUM |
| src/backend/access/hash/hashinsert.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashinsert.c.md | _hash_doinsert + opportunistic vacuum_one_page |
| src/backend/access/hash/hashpage.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashpage.c.md | page mgmt + split + metapage cache validation |
| src/backend/access/hash/hashsearch.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashsearch.c.md | scan + split-mode dual-bucket reading |
| src/backend/access/hash/hash_xlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/hash/hash_xlog.c.md | hash redo (13 record types) |
| src/backend/access/hash/hashfunc.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashfunc.c.md | built-in hash opclass procs |
| src/backend/access/hash/hashovfl.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashovfl.c.md | overflow / bitmap free space |
| src/backend/access/hash/hashsort.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashsort.c.md | build-time tuplesort by bucket |
| src/backend/access/hash/hashutil.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashutil.c.md | hashkey/bucket math + _hash_finish_split |
| src/backend/access/hash/hashvalidate.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/hash/hashvalidate.c.md | amvalidate for hash |
| src/include/access/hash.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/hash.h.md | hash AM all-header |
| src/include/access/hash_xlog.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/hash_xlog.h.md | hash WAL record formats |
| src/backend/access/spgist/README | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/spgist/README.md | SP-GiST README summary |
| src/backend/access/spgist/spgist.c | 2026-06-01 | ef6a95c7c64 | skim | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgist.c.md | NOTE: file does not exist (handler in spgutils.c) |
| src/backend/access/spgist/spgdoinsert.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgdoinsert.c.md | the insert engine + AddNode/SplitTuple/PickSplit |
| src/backend/access/spgist/spgscan.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgscan.c.md | scan + redirect-following + KNN |
| src/backend/access/spgist/spgxlog.c | 2026-06-01 | ef6a95c7c64 | deep-read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgxlog.c.md | spg redo (8 records, REDIRECT conflict) |
| src/backend/access/spgist/spgkdtreeproc.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgkdtreeproc.c.md | k-d tree opclass over point |
| src/backend/access/spgist/spgquadtreeproc.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgquadtreeproc.c.md | quadtree opclass over point |
| src/backend/access/spgist/spgtextproc.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgtextproc.c.md | radix tree opclass over text |
| src/backend/access/spgist/spgutils.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgutils.c.md | spghandler + triple-parity allocator + last-used-page cache |
| src/backend/access/spgist/spgvalidate.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgvalidate.c.md | amvalidate for SP-GiST |
| src/backend/access/spgist/spgvacuum.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgvacuum.c.md | VACUUM + pending-list for concurrent moves |
| src/backend/access/spgist/spginsert.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spginsert.c.md | spgbuild + spginsert wrappers |
| src/backend/access/spgist/spgproc.c | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/backend/access/spgist/spgproc.c.md | common opclass helpers |
| src/include/access/spgist.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/spgist.h.md | SP-GiST public API |
| src/include/access/spgist_private.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/spgist_private.h.md | SP-GiST private types |
| src/include/access/spgxlog.h | 2026-06-01 | ef6a95c7c64 | read | index-ams-rerun | knowledge/files/src/include/access/spgxlog.h.md | SP-GiST WAL record formats |

<!-- utils/mmgr headers — per-file deep docs (file-by-file phase rerun) -->
| src/include/utils/memutils.h | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-headers-rerun | knowledge/files/src/include/utils/memutils.h.md | Size limits, top-level context pointers, ALLOCSET_*_SIZES, pg_memory_is_all_zeros |
| src/include/utils/palloc.h | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-headers-rerun | knowledge/files/src/include/utils/palloc.h.md | Universal palloc API + MemoryContextSwitchTo inline + reset callbacks |
| src/include/utils/memutils_internal.h | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-headers-rerun | knowledge/files/src/include/utils/memutils_internal.h.md | Per-impl callback prototypes + MemoryContextMethodID enum (16-slot dispatch table) |
| src/include/utils/memutils_memorychunk.h | 2026-06-01 | ef6a95c7c64 | deep-read | mmgr-headers-rerun | knowledge/files/src/include/utils/memutils_memorychunk.h.md | MemoryChunk hdrmask layout: 4+1+30+30 bits with shared bit; magic for external chunks |

<!-- executor per-file deep docs (file-by-file phase, exec lifecycle + SPI + canonical join) -->
| src/backend/executor/execMain.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-executor | knowledge/files/src/backend/executor/execMain.c.md | ExecutorStart/Run/Finish/End + InitPlan + ExecEndPlan + ExecutePlan + EvalPlanQual entry surface |
| src/backend/executor/execProcnode.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-executor | knowledge/files/src/backend/executor/execProcnode.c.md | ExecInitNode/MultiExecProcNode/ExecEndNode dispatch tables + ExecProcNodeFirst first-call trick + ExecShutdownNode + ExecSetTupleBound |
| src/backend/executor/spi.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-executor | knowledge/files/src/backend/executor/spi.c.md | SPI stack + connect/finish + four-way snapshot policy in _SPI_execute_plan + cursor wrappers + atomic vs non-atomic mem-context choice |
| src/backend/executor/nodeNestloop.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-executor | knowledge/files/src/backend/executor/nodeNestloop.c.md | Full 401-line state machine; nestParams push-down + REWIND eflags rule + inner-not-rescanned-in-ReScan invariant |

<!-- optimizer per-file deep docs (file-by-file phase, planner+createplan+allpaths+costsize+pathnode) -->
| src/backend/optimizer/plan/planner.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-optimizer | knowledge/files/src/backend/optimizer/plan/planner.c.md | standard_planner + subquery_planner + grouping_planner upper-rel chain; create_grouping/window/distinct/ordered paths; planner_hook + create_upper_paths_hook |
| src/backend/optimizer/plan/createplan.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-optimizer | knowledge/files/src/backend/optimizer/plan/createplan.c.md | Path→Plan recursion + CP_EXACT/SMALL/LABEL/IGNORE tlist flags + full create_*_plan dispatch + NestLoopParam handover via curOuterRels/curOuterParams |
| src/backend/optimizer/path/allpaths.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-optimizer | knowledge/files/src/backend/optimizer/path/allpaths.c.md | make_one_rel pipeline + per-RTE set_rel_size/pathlist dispatch + standard_join_search DP loop + partition-wise join + subquery pushdown safety |
| src/backend/optimizer/path/costsize.c | 2026-06-01 | ef6a95c7c64 | read | file-by-file-optimizer | knowledge/files/src/backend/optimizer/path/costsize.c.md | All cost_* + set_*_size_estimates; disabled_nodes lex-order replaces old disable_cost hack; FK-join selectivity shortcut; initial/final cost split for joins |
| src/backend/optimizer/util/pathnode.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-optimizer | knowledge/files/src/backend/optimizer/util/pathnode.c.md | add_path dominance pruning (STD_FUZZ_FACTOR=1.01) + IndexPath pfree exception + add_partial_path differences + every create_*_path constructor + reparameterize_path family |

<!-- storage/buffer per-file docs (backfilling earlier deep reads with companion .md) -->
| src/backend/storage/buffer/bufmgr.c | 2026-06-01 | ef6a95c7c64 | deep-read | file-by-file-bufmgr | knowledge/files/src/backend/storage/buffer/bufmgr.c.md | Per-file companion: public API + BufferAlloc/GetVictimBuffer/Pin/Unpin/Flush/Lock/Cleanup/IO/Checkpoint dispatch; 8 967 lines |
| src/include/storage/buf_internals.h | 2026-06-01 | ef6a95c7c64 | read | file-by-file-bufmgr | knowledge/files/src/include/storage/buf_internals.h.md | Per-file companion: 64-bit packed state layout, BufferDesc locking rules, BM_* flags, forward decls for the whole subsystem |

<!-- cloud:pg-file-backfiller 2026-06-02 — deep re-verify at new anchor -->
| src/backend/access/heap/heapam_visibility.c | 2026-06-02 | 4b0bf0788b0 | deep-read | cloud:pg-file-backfiller | knowledge/files/src/backend/access/heap/heapam_visibility.c.md | Deep re-verify at anchor 4b0bf07; corrected hint-bit drift (BufferBeginSetHintBits/BufferFinishSetHintBits/BufferSetHintBits16 + SetHintBitsState replacing single-shot MarkBufferDirtyHint); HeapTupleSatisfiesMVCCBatch amortized path |

<!-- a1-catalog-headers 2026-06-02 — foreground sweep #1 (Phase A); 72 docs in one batch via 6 parallel general-purpose agents -->
| src/include/catalog/pg_class.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_class.h.md | Relation catalog header — FormData_pg_class + relkind/relpersistence/replident on-disk chars |
| src/include/catalog/pg_attribute.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_attribute.h.md | Column catalog header — FormData_pg_attribute + FormExtraData sister struct, ATTRIBUTE_IDENTITY/GENERATED chars |
| src/include/catalog/pg_type.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_type.h.md | Type catalog header — FormData_pg_type + TYPTYPE/TYPCATEGORY/TYPALIGN/TYPSTORAGE chars + polymorphic-type macros |
| src/include/catalog/pg_proc.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_proc.h.md | Procedure catalog header — FormData_pg_proc + PROKIND/PROVOLATILE/PROPARALLEL/PROARGMODE chars |
| src/include/catalog/pg_namespace.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_namespace.h.md | Schema catalog header — minimal FormData_pg_namespace + NamespaceCreate prototype |
| src/include/catalog/pg_language.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_language.h.md | Procedural-language catalog header — FormData_pg_language with handler/inline/validator OIDs |
| src/include/catalog/pg_database.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_database.h.md | Database catalog header (SHARED) — FormData_pg_database + Template0/Postgres DB OID macros + DATCONNLIMIT sentinels |
| src/include/catalog/pg_tablespace.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_tablespace.h.md | Tablespace catalog header (SHARED) — minimal FormData_pg_tablespace + get_tablespace_location |
| src/include/catalog/pg_authid.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_authid.h.md | Role catalog header (SHARED) — FormData_pg_authid with rolpassword, no TOAST table |
| src/include/catalog/pg_index.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_index.h.md | Index catalog header — FormData_pg_index + indkey/indclass/indoption vectors + INDOPTION_DESC/NULLS_FIRST |
| src/include/catalog/pg_inherits.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_inherits.h.md | Inheritance/partition-parent edges catalog header — FormData_pg_inherits + find_all_inheritors etc. |
| src/include/catalog/pg_partitioned_table.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_partitioned_table.h.md | Partition-key catalog header — FormData_pg_partitioned_table + partattrs/partclass/partcollation vectors |
| src/include/catalog/pg_operator.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_operator.h.md | Operator catalog: name, kind ('l'/'b'), left/right/result types, code/rest/join regprocs, commutator/negator |
| src/include/catalog/pg_aggregate.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_aggregate.h.md | Aggregate metadata keyed on aggfnoid: transfn/finalfn/combinefn/serial/moving-agg, aggkind, finalmodify |
| src/include/catalog/pg_cast.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_cast.h.md | Type cast catalog: source/target/func, CoercionCodes ('i'/'a'/'e'), CoercionMethod ('f'/'b'/'i') |
| src/include/catalog/pg_collation.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_collation.h.md | Collation catalog: collprovider ('d'/'b'/'i'/'c'), deterministic, locale/icurules/version varlena tail |
| src/include/catalog/pg_conversion.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_conversion.h.md | Encoding conversion catalog: for/to encoding (pseudo lookup), conproc, condefault |
| src/include/catalog/pg_am.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_am.h.md | Access method catalog: amname, amhandler regproc, amtype ('i'/'t') |
| src/include/catalog/pg_amop.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_amop.h.md | Opfamily-member operators: (family,left,right,strategy) PK, amoppurpose ('s'/'o'), denormalized amopmethod |
| src/include/catalog/pg_amproc.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_amproc.h.md | Opfamily-member support procs: (family,left,right,procnum) PK; AM-specific procnum meaning |
| src/include/catalog/pg_opclass.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_opclass.h.md | Operator class: method/name/namespace PK, opcfamily, opcintype, opcdefault, optional opckeytype |
| src/include/catalog/pg_opfamily.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_opfamily.h.md | Operator family container: opfmethod/name/namespace, IsBuiltinBooleanOpfamily macro |
| src/include/catalog/pg_constraint.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_constraint.h.md | Constraint catalog: contype ('c'/'f'/'n'/'p'/'u'/'t'/'x'), FK fkey/pfeqop/ppeqop/ffeqop arrays, period support |
| src/include/catalog/pg_attrdef.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_attrdef.h.md | Column DEFAULT expressions: (adrelid, adnum) FK to pg_attribute, adbin pg_node_tree FORCE_NOT_NULL |
| src/include/catalog/pg_depend.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_depend.h.md | per-DB dependency edges; no oid, no PK; deptype char on-disk via DependencyType |
| src/include/catalog/pg_shdepend.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_shdepend.h.md | shared dependency edges; BKI_SHARED_RELATION; dbid=0 means shared referrer |
| src/include/catalog/pg_auth_members.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_auth_members.h.md | role membership; shared + ROWTYPE_OID + SCHEMA_MACRO; admin/inherit/set options |
| src/include/catalog/pg_default_acl.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_default_acl.h.md | ALTER DEFAULT PRIVILEGES rows; DEFACLOBJ_* on-disk chars; TOAST |
| src/include/catalog/pg_init_privs.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_init_privs.h.md | initdb/extension initial-priv snapshot; InitPrivsType on-disk chars |
| src/include/catalog/pg_largeobject.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_largeobject.h.md | LO chunk storage; bytea direct access via inv_api.c; LargeObject* prototypes |
| src/include/catalog/pg_largeobject_metadata.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_largeobject_metadata.h.md | LO owner + ACL; lomacl varlena but no DECLARE_TOAST |
| src/include/catalog/pg_seclabel.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_seclabel.h.md | per-DB SECURITY LABEL; provider+label opaque to PG; TOAST |
| src/include/catalog/pg_shseclabel.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_shseclabel.h.md | shared SECURITY LABEL; SHARED+ROWTYPE+SCHEMA_MACRO; TOAST_WITH_MACRO |
| src/include/catalog/pg_policy.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_policy.h.md | RLS policy rows; polcmd ACL_*_CHR on-disk; polroles[0]=PUBLIC; TOAST |
| src/include/catalog/pg_parameter_acl.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_parameter_acl.h.md | GUC ACLs; SHARED; lazy row creation; ParameterAclLookup/Create prototypes |
| src/include/catalog/pg_publication.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_publication.h.md | per-DB publications catalog; FormData + Publication/PublicationDesc/PublicationActions runtime structs; PUBLISH_GENCOLS_* on-disk chars |
| src/include/catalog/pg_publication_namespace.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_publication_namespace.h.md | per-DB pub-schema edges (FOR TABLES IN SCHEMA); 3 cols, no varlena |
| src/include/catalog/pg_publication_rel.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_publication_rel.h.md | per-DB pub-rel edges with prqual row filter + prattrs column list; TOASTed |
| src/include/catalog/pg_subscription.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_subscription.h.md | SHARED nailed catalog; FormData + Subscription runtime struct; LOGICALREP_STREAM_* / TWOPHASE_STATE_* / ORIGIN_* on-disk |
| src/include/catalog/pg_subscription_rel.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_subscription_rel.h.md | per-DB tablesync state; SUBREL_STATE_* on-disk + IPC-only chars; LogicalRepSequenceInfo |
| src/include/catalog/pg_replication_origin.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_replication_origin.h.md | SHARED; roident is hand-allocated uint16 embedded in WAL; no oid column |
| src/include/catalog/pg_foreign_data_wrapper.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_foreign_data_wrapper.h.md | FDWs with handler/validator/connection pg_proc refs; TOASTed |
| src/include/catalog/pg_foreign_server.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_foreign_server.h.md | servers binding to FDW + srvoptions; TOASTed |
| src/include/catalog/pg_foreign_table.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_foreign_table.h.md | per-FT sidecar (ftrelid PK, no oid); pairs with pg_class RELKIND='f' |
| src/include/catalog/pg_user_mapping.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_user_mapping.h.md | role-server mapping; umuser=0 means PUBLIC; credentials in umoptions |
| src/include/catalog/pg_extension.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_extension.h.md | installed extensions; extconfig/extcondition parallel arrays for dumpable config |
| src/include/catalog/pg_event_trigger.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_event_trigger.h.md | event triggers; evtenabled char reuses pg_trigger.h constants; evttags filter |
| src/include/catalog/pg_statistic.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_statistic.h.md | per-(rel,attr,inh) stats catalog; 5-slot kinds; info-leak surface for sample values |
| src/include/catalog/pg_statistic_ext.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_statistic_ext.h.md | CREATE STATISTICS definitions; stxkind 'd'/'f'/'m'/'e' chars on-disk |
| src/include/catalog/pg_statistic_ext_data.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_statistic_ext_data.h.md | serialized ndistinct/deps/MCV/per-expr stats; same info-leak as pg_statistic |
| src/include/catalog/pg_sequence.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_sequence.h.md | per-sequence params (start/min/max/inc/cache/cycle); current value lives in seqrel data page |
| src/include/catalog/pg_range.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_range.h.md | range type subtype/opclass/canonical/subdiff + range+multirange constructors |
| src/include/catalog/pg_transform.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_transform.h.md | CREATE TRANSFORM type-language with from/to-SQL regprocs |
| src/include/catalog/pg_enum.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_enum.h.md | enum labels + sort order; uncommitted-enum tracking API for in-xact ADD VALUE |
| src/include/catalog/pg_rewrite.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_rewrite.h.md | rewrite rules; ev_type/ev_enabled on-disk chars defined elsewhere |
| src/include/catalog/pg_trigger.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_trigger.h.md | triggers; tgtype bit layout + tgenabled 'O'/'D'/'R'/'A' chars are on-disk format |
| src/include/catalog/pg_description.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_description.h.md | COMMENT ON; identified by (objoid, classoid, objsubid); no .dat file |
| src/include/catalog/pg_shdescription.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_shdescription.h.md | SHARED COMMENT ON; (objoid, classoid) PK; toast uses named macros |
| src/include/catalog/pg_db_role_setting.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_db_role_setting.h.md | SHARED per-(db,role) GUC overrides applied at login; no syscache, direct scan |
| src/include/catalog/pg_ts_config.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_ts_config.h.md | pg_ts_config catalog: cfg-parser binding, indexed by name+nsp and oid |
| src/include/catalog/pg_ts_config_map.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_ts_config_map.h.md | pg_ts_config_map: (cfg, tokentype, seqno) → dict mapping rows, no oid column |
| src/include/catalog/pg_ts_dict.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_ts_dict.h.md | pg_ts_dict: TS dictionary rows binding a template + init option, TOASTed |
| src/include/catalog/pg_ts_parser.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_ts_parser.h.md | pg_ts_parser: parser name → five regproc callbacks (start/token/end/headline/lextype) |
| src/include/catalog/pg_ts_template.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_ts_template.h.md | pg_ts_template: template name → (tmplinit OPT, tmpllexize) regproc pair |
| src/include/catalog/pg_propgraph_element.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_propgraph_element.h.md | pg_propgraph_element: vertex/edge rows with src/dest refs and key arrays (PG18+) |
| src/include/catalog/pg_propgraph_element_label.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_propgraph_element_label.h.md | pg_propgraph_element_label: M2M edge between elements and labels (PG18+) |
| src/include/catalog/pg_propgraph_label.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_propgraph_label.h.md | pg_propgraph_label: (graph, label name) rows unique per graph (PG18+) |
| src/include/catalog/pg_propgraph_label_property.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_propgraph_label_property.h.md | pg_propgraph_label_property: per-(label, prop) expression as pg_node_tree, TOASTed (PG18+) |
| src/include/catalog/pg_propgraph_property.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_propgraph_property.h.md | pg_propgraph_property: (graph, prop name) with type/typmod/collation (PG18+) |
| src/include/catalog/pg_control.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/pg_control.h.md | pg_control on-disk format: ControlFileData, CheckPoint, DBState, XLOG info bytes, PG_CONTROL_VERSION=1902 |
| src/include/catalog/binary_upgrade.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/binary_upgrade.h.md | binary_upgrade_next_* globals consumed by heap_create / pg_type create paths during pg_upgrade reload |
| src/include/catalog/catversion.h | 2026-06-02 | 4b0bf0788b0 | read | catalog-headers-a1 | knowledge/files/src/include/catalog/catversion.h.md | CATALOG_VERSION_NO=202605131 (YYYYMMDDN); bump on any catalog or pg_node_tree format change |

<!-- a2-libpq-stack 2026-06-03 — foreground sweep #2 (Phase A); 69 docs in one batch via 6 parallel general-purpose agents -->
| src/include/libpq/auth.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/auth.h.md | network auth entry points and hooks |
| src/include/libpq/be-fsstubs.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/be-fsstubs.h.md | non-fmgr large-object read/write + xact cleanup |
| src/include/libpq/be-gssapi-common.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/be-gssapi-common.h.md | shared GSSAPI helpers (error format, delegated cred) |
| src/include/libpq/crypt.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/crypt.h.md | password hashing / verify API + PasswordType enum |
| src/include/libpq/hba.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/hba.h.md | UserAuth enum + HbaLine / IdentLine parser API |
| src/include/libpq/ifaddr.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/ifaddr.h.md | netmask / interface enumeration helpers for HBA |
| src/include/libpq/libpq-be-fe-helpers.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/libpq-be-fe-helpers.h.md | header-only libpq driver helpers for extensions |
| src/include/libpq/libpq-be-fe.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/libpq-be-fe.h.md | MemoryContext-safe PGresult wrappers for extensions |
| src/include/libpq/libpq-be.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/libpq-be.h.md | Port struct + SSL/GSS hook prototypes |
| src/include/libpq/libpq-fs.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/libpq-fs.h.md | INV_READ / INV_WRITE LO mode flag bits |
| src/include/libpq/libpq.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/libpq.h.md | PQcommMethods + pqcomm/be-secure entry points and SSL GUCs |
| src/include/libpq/oauth.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/oauth.h.md | OAuth validator module ABI + HBA option helpers |
| src/include/libpq/pg-gssapi.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/pg-gssapi.h.md | GSSAPI header include shim + Windows X509_NAME workaround |
| src/include/libpq/pqcomm.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/pqcomm.h.md | protocol version, ALPN, cancel/SSL/GSS negotiation codes |
| src/include/libpq/pqformat.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/pqformat.h.md | StringInfo wire-message serializer/deserializer API |
| src/include/libpq/pqmq.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/pqmq.h.md | redirect FE/BE protocol writes into a shm_mq |
| src/include/libpq/pqsignal.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/pqsignal.h.md | canonical signal masks + WIN32 sigaction emulation |
| src/include/libpq/protocol.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/protocol.h.md | PqMsg_* wire bytes + AUTH_REQ_* subcodes |
| src/include/libpq/sasl.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/sasl.h.md | backend SASL mechanism callback interface |
| src/include/libpq/scram.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/include/libpq/scram.h.md | SCRAM-SHA-256 mechanism instance + secret parse helpers |
| src/backend/libpq/auth.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/auth.c.md | Top-level ClientAuthentication driver + per-method dispatch |
| src/backend/libpq/auth-sasl.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/auth-sasl.c.md | SASL outer loop: AUTH_REQ_SASL/CONT/FIN wire protocol |
| src/backend/libpq/auth-scram.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/auth-scram.c.md | Server SCRAM-SHA-256(-PLUS) + parse_scram_secret + doomed pattern |
| src/backend/libpq/auth-oauth.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/auth-oauth.c.md | Server OAUTHBEARER + validator-library plugin API + HBA-option machinery |
| src/backend/libpq/crypt.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/crypt.c.md | pg_authid.rolpassword helpers: get_role_password, encrypt_password, md5/plain crypt_verify |
| src/backend/libpq/be-secure.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/be-secure.c.md | TLS/GSS dispatch shim: secure_read/write retry-loop, secure_open_server |
| src/backend/libpq/be-secure-common.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/be-secure-common.c.md | TLS impl-independent helpers: passphrase_command, key-file perms, pg_hosts.conf parser |
| src/backend/libpq/be-secure-gssapi.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/be-secure-gssapi.c.md | GSSAPI transport encryption: be_gssapi_read/write framing, secure_open_gssapi |
| src/backend/libpq/be-secure-openssl.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/be-secure-openssl.c.md | OpenSSL impl of be_tls_*: ctx build, SNI cb, verify cb, peer DN/CN, channel-binding hash |
| src/backend/libpq/hba.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/hba.c.md | pg_hba.conf lexer + parser + first-match engine; default-deny via uaImplicitReject |
| src/backend/libpq/pqcomm.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/pqcomm.c.md | wire-format socket layer; 8K send/recv rings; PqCommBusy reentrancy; non-blocking + latch model |
| src/backend/libpq/pqformat.c | 2026-06-03 | 4b0bf0788b0 | medium-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/pqformat.c.md | message build/parse helpers above pqcomm; StringInfo cursor-as-msgtype trick |
| src/backend/libpq/pqmq.c | 2026-06-03 | 4b0bf0788b0 | medium-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/pqmq.c.md | parallel-worker shm_mq protocol bridge; PqCommMethods vtable swap; reentrancy = detach |
| src/backend/libpq/pqsignal.c | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/pqsignal.c.md | BlockSig / UnBlockSig / StartupBlockSig mask init |
| src/backend/libpq/be-fsstubs.c | 2026-06-03 | 4b0bf0788b0 | medium-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/be-fsstubs.c.md | LO SQL wrappers + per-xact FD cookie table; lo_compat_privileges relic |
| src/backend/libpq/be-gssapi-common.c | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/be-gssapi-common.c.md | GSS error stringify (COMMERROR-only) + delegated cred store into MEMORY: ccache |
| src/backend/libpq/ifaddr.c | 2026-06-03 | 4b0bf0788b0 | medium-read | libpq-stack-a2 | knowledge/files/src/backend/libpq/ifaddr.c.md | CIDR mask arithmetic + 4-way #ifdef pg_foreach_ifaddr |
| src/interfaces/libpq/fe-connect.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-connect.c.md | PQconnectPoll state machine, conninfo/URI/service/pgpass parsing, multi-host iteration |
| src/interfaces/libpq/fe-cancel.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-cancel.c.md | Modern PGcancelConn (PG17+) plus legacy signal-safe PQcancel + PQrequestCancel |
| src/interfaces/libpq/fe-exec.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-exec.c.md | PGresult lifecycle, PQexec/async machinery, pipeline mode, COPY, escaping, fast-path PQfn |
| src/interfaces/libpq/fe-misc.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-misc.c.md | pqGet*/pqPut* primitives, in/out buffer geometry, pqReadData/pqSendSome, PQsocketPoll |
| src/interfaces/libpq/fe-print.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-print.c.md | Legacy PQprint/PQdisplayTuples/PQprintTuples result pretty-printer (HTML3 XSS surface) |
| src/interfaces/libpq/fe-protocol3.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-protocol3.c.md | pqParseInput3 message dispatcher, pqGetErrorNotice3, pqFunctionCall3 |
| src/interfaces/libpq/fe-trace.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-trace.c.md | PQtrace wire-protocol tracer with per-message helpers and regress-mode suppressions |
| src/interfaces/libpq/fe-lobj.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-lobj.c.md | lo_open/read/write/close/import/export wrappers via PQfn with lazy lobjfuncs OID cache |
| src/interfaces/libpq/fe-auth.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-auth.c.md | Client auth dispatcher; SASL mechanism negotiation; require_auth/channel_binding gates |
| src/interfaces/libpq/fe-auth.h | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-auth.h.md | Private header exposing pg_fe_sendauth, scram mech table, auth-data hook |
| src/interfaces/libpq/fe-auth-oauth.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-auth-oauth.c.md | OAUTHBEARER mechanism; RFC 9207 mix-up defense; v1/v2 hook poisoning |
| src/interfaces/libpq/fe-auth-oauth.h | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-auth-oauth.h.md | OAuth state machine enum + fe_oauth_state struct |
| src/interfaces/libpq/fe-auth-sasl.h | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-auth-sasl.h.md | Frontend SASL mechanism vtable; SASLStatus enum (incl. SASL_ASYNC) |
| src/interfaces/libpq/fe-auth-scram.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md | Client SCRAM-SHA-256(-PLUS); pg_strong_random nonces; timingsafe_bcmp |
| src/interfaces/libpq/fe-gssapi-common.c | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-gssapi-common.c.md | GSS error formatter, credential probe, SPN import helpers |
| src/interfaces/libpq/fe-gssapi-common.h | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-gssapi-common.h.md | ENABLE_GSS-gated GSS helper prototypes |
| src/interfaces/libpq/fe-secure.c | 2026-06-03 | 4b0bf0788b0 | medium-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-secure.c.md | TLS/GSS/raw dispatch; SIGPIPE masking; write-failed latch with delayed-error pattern |
| src/interfaces/libpq/fe-secure-common.c | 2026-06-03 | 4b0bf0788b0 | medium-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-secure-common.c.md | Cert name/IP matching; wildcard rules; CVE-2009-4034 embedded-NUL defense |
| src/interfaces/libpq/fe-secure-common.h | 2026-06-03 | 4b0bf0788b0 | shallow-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-secure-common.h.md | TLS-agnostic peer-name matching API |
| src/interfaces/libpq/fe-secure-gssapi.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-secure-gssapi.c.md | GSSAPI as TLS-replacement transport; wrap/unwrap with conf_state check |
| src/interfaces/libpq/fe-secure-openssl.c | 2026-06-03 | 4b0bf0788b0 | deep-read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/fe-secure-openssl.c.md | OpenSSL backend; SSL_CTX setup; cert+key loading; SAN-vs-CN; verify_cb passthrough |
| src/interfaces/libpq/libpq-fe.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/libpq-fe.h.md | THE public libpq API — every PQ* prototype, opaque typedef, feature-detect macro |
| src/interfaces/libpq/libpq-int.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/libpq-int.h.md | Internal libpq header: full PGconn + PGresult struct layout, async state machine |
| src/interfaces/libpq/pqexpbuffer.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/pqexpbuffer.h.md | Frontend StringInfo equivalent: PQExpBuffer API with broken-state OOM handling |
| src/interfaces/libpq/pqexpbuffer.c | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/pqexpbuffer.c.md | PQExpBuffer impl: shared oom_buffer for broken state, INT_MAX overflow guards |
| src/interfaces/libpq/libpq-events.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/libpq-events.h.md | Event hook API — PGEVT_* lifecycle events, instance data per proc |
| src/interfaces/libpq/libpq-events.c | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/libpq-events.c.md | Events impl — proc-address keyed registration, plugin trust boundary |
| src/interfaces/libpq/oauth-debug.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/oauth-debug.h.md | PGOAUTHDEBUG env parsing — UNSAFE: prefix gates HTTP/trace/dos-endpoint flags |
| src/interfaces/libpq/legacy-pqsignal.c | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/legacy-pqsignal.c.md | ABI shim — exports pqsignal symbol with 9.2 semantics for pre-9.3 client binaries |
| src/interfaces/libpq/pthread-win32.c | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/pthread-win32.c.md | Partial pthread on Win32 — CRITICAL_SECTION mutex, TLS stubs return NULL |
| src/interfaces/libpq/win32.c | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/win32.c.md | Winsock WSAE* error-to-string table + FormatMessage DLL fallback chain |
| src/interfaces/libpq/win32.h | 2026-06-03 | 4b0bf0788b0 | read | libpq-stack-a2 | knowledge/files/src/interfaces/libpq/win32.h.md | Three-line CRT redirect (close/read/write -> _close/_read/_write) |

<!-- a3-pg-dump 2026-06-03 — foreground sweep #3 (Phase A); 36 docs via 4 parallel general-purpose agents -->
| src/bin/pg_dump/pg_dump.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_dump.c.md | Main driver: catalog walkers, dependency sort, per-kind dumpers, security-restrict boundary |
| src/bin/pg_dump/pg_dump.h | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_dump.h.md | DumpableObject type system + 48-kind enum + DumpComponents bitmask |
| src/bin/pg_dump/pg_dump_sort.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md | Type-name baseline + topological sort + 8 cycle-repair fixers |
| src/bin/pg_dump/pg_dumpall.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_dumpall.c.md | Cluster-wide driver: roles, tablespaces, per-DB pg_dump fork+exec, map.dat/toc.glo |
| src/bin/pg_dump/pg_restore.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_restore.c.md | Restore driver: single-archive vs dumpall-archive mode, parallel jobs, filter file |
| src/bin/pg_dump/pg_backup.h | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup.h.md | Public archive API: ArchiveFormat/Mode/teSection enums, ConnParams/RestoreOptions/DumpOptions/Archive structs |
| src/bin/pg_dump/pg_backup_archiver.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md | Central archive driver: TOC management, RestoreArchive (serial + 3-phase parallel), restore_toc_entry, fix_dependencies, CloneArchive for workers |
| src/bin/pg_dump/pg_backup_archiver.h | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_archiver.h.md | Private types: ArchiveHandle/TocEntry, archive version macros K_VERS_1_0..K_VERS_1_16, 25+ format-callback typedefs |
| src/bin/pg_dump/pg_backup_custom.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md | Custom format (-Fc, default): PGDMP file with header+TOC+compressed data blocks, parallel restore via shared dataState |
| src/bin/pg_dump/pg_backup_db.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_db.c.md | Connection lifecycle + SQL exec wrappers: ConnectDatabaseAhx, ExecuteSqlCommandBuf multiplexer, IssueACLPerBlob |
| src/bin/pg_dump/pg_backup_db.h | 2026-06-03 | 4b0bf0788b0 | shallow-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_db.h.md | Tiny header: ExecuteSqlCommandBuf/Statement/Query, StartTransaction/CommitTransaction, EndDBCopyMode |
| src/bin/pg_dump/pg_backup_directory.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md | Directory format (-Fd): toc.dat + per-TE dumpId.dat + per-LO blob_OID.dat. Path-traversal surface via attacker filename in TOC |
| src/bin/pg_dump/pg_backup_null.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_null.c.md | Null format (-Fp plain text): write-only, no archive structure; emits LO data as SELECT pg_catalog.lowrite |
| src/bin/pg_dump/pg_backup_tar.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_tar.c.md | Tar format (-Ft): hand-rolled tar parser with checksum verify; 12-octal-digit size header → DoS via padding-skip |
| src/bin/pg_dump/compress_io.c | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_io.c.md | Backend dispatcher + suffix-discovery for the 4 compression libs |
| src/bin/pg_dump/compress_io.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_io.h.md | Vtable contract: CompressorState + CompressFileHandle |
| src/bin/pg_dump/compress_none.c | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_none.c.md | Pass-through backend (128KB write buffering, fopen-shim stream API) |
| src/bin/pg_dump/compress_none.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_none.h.md | Trivial header for none backend |
| src/bin/pg_dump/compress_gzip.c | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_gzip.c.md | zlib deflate/inflate + gzopen-wrapper backend |
| src/bin/pg_dump/compress_gzip.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_gzip.h.md | Trivial header for gzip backend |
| src/bin/pg_dump/compress_lz4.c | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_lz4.c.md | LZ4 frame-format backend (lazy init, shared LZ4State across APIs) |
| src/bin/pg_dump/compress_lz4.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_lz4.h.md | Trivial header for lz4 backend |
| src/bin/pg_dump/compress_zstd.c | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_zstd.c.md | Zstandard backend (newest) + long-distance-matching option |
| src/bin/pg_dump/compress_zstd.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/compress_zstd.h.md | Trivial header for zstd backend |
| src/bin/pg_dump/pg_backup_tar.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_tar.h.md | POSIX ustar header layout + LF_* type-flag constants |
| src/bin/pg_dump/pg_backup_utils.c | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_utils.c.md | progname, set_dump_section, on_exit_nicely callback list, exit_nicely |
| src/bin/pg_dump/common.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/common.c.md | DumpId/CatalogId registries + getSchemaData collector spine; silent-drop in flagInhTables/flagInhIndexes |
| src/bin/pg_dump/connectdb.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/connectdb.c.md | pg_dumpall connect-per-DB driver; expand_dbname=true with server-derived dbname flagged as likely Phase D |
| src/bin/pg_dump/connectdb.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/connectdb.h.md | 12-arg ConnectDatabase + executeQuery prototypes |
| src/bin/pg_dump/dumputils.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/dumputils.c.md | ACL/SECURITY LABEL/ALTER CONFIG emitters; all 16 fmtId callsites audited correct |
| src/bin/pg_dump/dumputils.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/dumputils.h.md | Externs + PGDUMP_STRFTIME_FMT |
| src/bin/pg_dump/filter.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/filter.c.md | --filter=file parser; pattern returned unquoted, silent backslash-escape swallow |
| src/bin/pg_dump/filter.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/filter.h.md | FilterStateData + command/object enums + exit_function callback |
| src/bin/pg_dump/parallel.c | 2026-06-03 | 4b0bf0788b0 | deep-read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/parallel.c.md | -j N worker pool: fork on Unix, threads on Windows; signal-safety + pgpipe TCP loopback |
| src/bin/pg_dump/parallel.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/parallel.h.md | ParallelState, ParallelCompletionPtr, WFW enum, PG_MAX_JOBS |
| src/bin/pg_dump/pg_backup_utils.h | 2026-06-03 | 4b0bf0788b0 | read | pg-dump-a3 | knowledge/files/src/bin/pg_dump/pg_backup_utils.h.md | pg_fatal override → exit_nicely; section flags; on_exit_nicely callback type |

<!-- a4-bin-tools 2026-06-03 — foreground sweep #4 (Phase A); 43 docs via 5 parallel general-purpose agents covering src/bin/{psql,pg_basebackup,initdb} -->
| src/bin/psql/command.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/command.c.md | All `\` meta-commands dispatcher; restrict_key static gate; \password/\copy/\edit/\!/\connect |
| src/bin/psql/command.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/command.h.md | Meta-command status + handler prototypes |
| src/bin/psql/common.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/common.c.md | SendQuery, ExecQueryAndProcessResults, PrintNotifications, -L logfile capture, \gexec, SIGINT longjmp |
| src/bin/psql/common.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/common.h.md | SIGINT longjmp protocol declarations; query-side externs |
| src/bin/psql/copy.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/copy.c.md | \copy implementation; PROGRAM 'cmd' → popen; protocol-v2 fallback path |
| src/bin/psql/copy.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/copy.h.md | do_copy/handleCopyIn/handleCopyOut prototypes |
| src/bin/psql/crosstabview.c | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/crosstabview.c.md | \crosstabview AVL-tree pivot with CROSSTABVIEW_MAX_COLUMNS=1600 cap |
| src/bin/psql/crosstabview.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/crosstabview.h.md | PrintResultsInCrosstab prototype |
| src/bin/psql/describe.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/describe.c.md | Every `\d*` catalog query builder; processSQLNamePattern audit; printTable usage |
| src/bin/psql/describe.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/describe.h.md | listX/describeX prototypes |
| src/bin/psql/help.c | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/help.c.md | --help text, \? topic dispatch, helpVariables/helpSQL |
| src/bin/psql/help.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/help.h.md | Help dispatch prototypes |
| src/bin/psql/input.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/input.c.md | readline/libedit wrapper; ~/.psql_history at 0600 but no O_NOFOLLOW; no password-pattern filter |
| src/bin/psql/input.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/input.h.md | gets_interactive/gets_fromFile/pg_append_history prototypes |
| src/bin/psql/large_obj.c | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/large_obj.c.md | \lo_import/export with arbitrary client-side paths under psql UID |
| src/bin/psql/large_obj.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/large_obj.h.md | do_lo_* prototypes |
| src/bin/psql/mainloop.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/mainloop.c.md | REPL loop, transaction-state echo, pg_append_history every input line (no scrub) |
| src/bin/psql/mainloop.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/mainloop.h.md | MainLoop prototype |
| src/bin/psql/prompt.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/prompt.c.md | PROMPT %-substitution; %`cmd` popen on every render; %:var: forwards server error text raw |
| src/bin/psql/prompt.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/prompt.h.md | get_prompt + promptStatus_t |
| src/bin/psql/psqlscanslash.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/psqlscanslash.h.md | Slash-arg flex scanner externs (impl in .l) |
| src/bin/psql/settings.h | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/settings.h.md | Master PsqlSettings/pset struct; pset.db holds libpq PGconn with cached credentials |
| src/bin/psql/startup.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/startup.c.md | main(); option parsing; .psqlrc lookup; simple_prompt password (no explicit_bzero) |
| src/bin/psql/stringutils.c | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/stringutils.c.md | strtokx token splitting; e_strings+del_quotes combo documented unsupported |
| src/bin/psql/stringutils.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/stringutils.h.md | strtokx prototype |
| src/bin/psql/tab-complete.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/tab-complete.h.md | initialize_readline prototype |
| src/bin/psql/tab-complete.in.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/psql/tab-complete.in.c.md | Tab queries on user's open transaction; processSQLNamePattern via psqlscan callback; auto-firing PQexec |
| src/bin/psql/variables.c | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/variables.c.md | psql variable store; bare :var unsanitized; \gset path from server |
| src/bin/psql/variables.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/psql/variables.h.md | VariableSpace + hooks prototypes |
| src/bin/pg_basebackup/astreamer_inject.c | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/astreamer_inject.c.md | Tablespace-map / signal-file injection into the backup tar stream |
| src/bin/pg_basebackup/astreamer_inject.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/astreamer_inject.h.md | bbstreamer_inject_file / bbstreamer_recovery_injector prototypes |
| src/bin/pg_basebackup/pg_basebackup.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md | Main; CopyStream / tar / plain output; spclocation trust; --waldir symlink |
| src/bin/pg_basebackup/pg_createsubscriber.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md | Convert standby → logical-replication subscriber; .conf→.disabled credential retention |
| src/bin/pg_basebackup/pg_receivewal.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md | Receive + archive WAL; FindStreamingStart hex-filename scan; sync_method |
| src/bin/pg_basebackup/pg_recvlogical.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md | Receive logical decoding output; newline-as-separator not enforced; outfile no O_NOFOLLOW |
| src/bin/pg_basebackup/receivelog.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/receivelog.c.md | WAL receive loop; timeline jumps; static globals encode single-stream invariant |
| src/bin/pg_basebackup/receivelog.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/receivelog.h.md | StreamCtl + ReceiveXlogStream prototype |
| src/bin/pg_basebackup/streamutil.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/streamutil.c.md | Shared connection helpers; password static; wal_segment_size + data_directory_mode trusted from server |
| src/bin/pg_basebackup/streamutil.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/streamutil.h.md | GetConnection/CreateReplicationSlot/etc prototypes |
| src/bin/pg_basebackup/walmethods.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/walmethods.c.md | Pluggable WAL writer (tar + directory); 8 GiB ustar cap inherited |
| src/bin/pg_basebackup/walmethods.h | 2026-06-03 | 4b0bf0788b0 | read | bin-tools-a4 | knowledge/files/src/bin/pg_basebackup/walmethods.h.md | WalWriteMethod vtable contract |
| src/bin/initdb/findtimezone.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/initdb/findtimezone.c.md | System timezone autodetection; bare strcat under install-trusted tzdir |
| src/bin/initdb/initdb.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-tools-a4 | knowledge/files/src/bin/initdb/initdb.c.md | Cluster bootstrap; superuser_password never zeroed; --pwfile stale-TODO "paranoia for now" |

<!-- a5-common 2026-06-03 — foreground sweep #5 (Phase A); 109 docs via 5 parallel general-purpose agents covering src/common/ + src/include/common/ -->
| src/common/archive.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/archive.c.md | A5 sweep per-file doc |
| src/common/base64.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/base64.c.md | A5 sweep per-file doc |
| src/common/binaryheap.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/binaryheap.c.md | A5 sweep per-file doc |
| src/common/blkreftable.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/blkreftable.c.md | A5 sweep per-file doc |
| src/common/checksum_helper.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/checksum_helper.c.md | A5 sweep per-file doc |
| src/common/compression.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/compression.c.md | A5 sweep per-file doc |
| src/common/config_info.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/config_info.c.md | A5 sweep per-file doc |
| src/common/controldata_utils.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/controldata_utils.c.md | A5 sweep per-file doc |
| src/common/cryptohash.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/cryptohash.c.md | A5 sweep per-file doc |
| src/common/cryptohash_openssl.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/cryptohash_openssl.c.md | A5 sweep per-file doc |
| src/common/d2s.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/d2s.c.md | A5 sweep per-file doc |
| src/common/d2s_full_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/common/d2s_full_table.h.md | Generated Ryu d2s lookup table — stub doc |
| src/common/d2s_intrinsics.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/d2s_intrinsics.h.md | A5 sweep per-file doc |
| src/common/digit_table.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/digit_table.h.md | A5 sweep per-file doc |
| src/common/encnames.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/encnames.c.md | A5 sweep per-file doc |
| src/common/exec.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/exec.c.md | A5 sweep per-file doc |
| src/common/f2s.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/f2s.c.md | A5 sweep per-file doc |
| src/common/fe_memutils.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/fe_memutils.c.md | A5 sweep per-file doc |
| src/common/file_perm.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/file_perm.c.md | A5 sweep per-file doc |
| src/common/file_utils.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/file_utils.c.md | A5 sweep per-file doc |
| src/common/hashfn.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/hashfn.c.md | A5 sweep per-file doc |
| src/common/hmac.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/hmac.c.md | A5 sweep per-file doc |
| src/common/hmac_openssl.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/hmac_openssl.c.md | A5 sweep per-file doc |
| src/common/instr_time.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/instr_time.c.md | A5 sweep per-file doc |
| src/common/ip.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/ip.c.md | A5 sweep per-file doc |
| src/common/jsonapi.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/jsonapi.c.md | A5 sweep per-file doc |
| src/common/keywords.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/keywords.c.md | A5 sweep per-file doc |
| src/common/kwlookup.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/kwlookup.c.md | A5 sweep per-file doc |
| src/common/link-canary.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/link-canary.c.md | A5 sweep per-file doc |
| src/common/logging.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/logging.c.md | A5 sweep per-file doc |
| src/common/md5.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/md5.c.md | A5 sweep per-file doc |
| src/common/md5_common.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/md5_common.c.md | A5 sweep per-file doc |
| src/common/md5_int.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/md5_int.h.md | A5 sweep per-file doc |
| src/common/parse_manifest.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/parse_manifest.c.md | A5 sweep per-file doc |
| src/common/percentrepl.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/percentrepl.c.md | A5 sweep per-file doc |
| src/common/pg_get_line.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/pg_get_line.c.md | A5 sweep per-file doc |
| src/common/pg_lzcompress.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/pg_lzcompress.c.md | A5 sweep per-file doc |
| src/common/pg_prng.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/pg_prng.c.md | A5 sweep per-file doc |
| src/common/pgfnames.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/pgfnames.c.md | A5 sweep per-file doc |
| src/common/psprintf.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/psprintf.c.md | A5 sweep per-file doc |
| src/common/relpath.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/relpath.c.md | A5 sweep per-file doc |
| src/common/restricted_token.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/restricted_token.c.md | A5 sweep per-file doc |
| src/common/rmtree.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/rmtree.c.md | A5 sweep per-file doc |
| src/common/ryu_common.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/ryu_common.h.md | A5 sweep per-file doc |
| src/common/saslprep.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/saslprep.c.md | A5 sweep per-file doc |
| src/common/scram-common.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/scram-common.c.md | A5 sweep per-file doc |
| src/common/sha1.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/sha1.c.md | A5 sweep per-file doc |
| src/common/sha1_int.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/sha1_int.h.md | A5 sweep per-file doc |
| src/common/sha2.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/sha2.c.md | A5 sweep per-file doc |
| src/common/sha2_int.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/sha2_int.h.md | A5 sweep per-file doc |
| src/common/sprompt.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/sprompt.c.md | A5 sweep per-file doc |
| src/common/string.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/string.c.md | A5 sweep per-file doc |
| src/common/stringinfo.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/stringinfo.c.md | A5 sweep per-file doc |
| src/common/unicode_case.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/unicode_case.c.md | A5 sweep per-file doc |
| src/common/unicode_category.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/unicode_category.c.md | A5 sweep per-file doc |
| src/common/unicode_norm.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/unicode_norm.c.md | A5 sweep per-file doc |
| src/common/username.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/username.c.md | A5 sweep per-file doc |
| src/common/wait_error.c | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/common/wait_error.c.md | A5 sweep per-file doc |
| src/common/wchar.c | 2026-06-03 | 4b0bf0788b0 | deep-read | common-a5 | knowledge/files/src/common/wchar.c.md | A5 sweep per-file doc |
| src/include/common/archive.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/archive.h.md | A5 sweep per-file doc |
| src/include/common/base64.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/base64.h.md | A5 sweep per-file doc |
| src/include/common/blkreftable.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/blkreftable.h.md | A5 sweep per-file doc |
| src/include/common/checksum_helper.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/checksum_helper.h.md | A5 sweep per-file doc |
| src/include/common/compression.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/compression.h.md | A5 sweep per-file doc |
| src/include/common/config_info.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/config_info.h.md | A5 sweep per-file doc |
| src/include/common/connect.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/connect.h.md | A5 sweep per-file doc |
| src/include/common/controldata_utils.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/controldata_utils.h.md | A5 sweep per-file doc |
| src/include/common/cryptohash.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/cryptohash.h.md | A5 sweep per-file doc |
| src/include/common/fe_memutils.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/fe_memutils.h.md | A5 sweep per-file doc |
| src/include/common/file_perm.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/file_perm.h.md | A5 sweep per-file doc |
| src/include/common/file_utils.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/file_utils.h.md | A5 sweep per-file doc |
| src/include/common/hashfn.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/hashfn.h.md | A5 sweep per-file doc |
| src/include/common/hashfn_unstable.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/hashfn_unstable.h.md | A5 sweep per-file doc |
| src/include/common/hmac.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/hmac.h.md | A5 sweep per-file doc |
| src/include/common/int.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/int.h.md | A5 sweep per-file doc |
| src/include/common/int128.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/int128.h.md | A5 sweep per-file doc |
| src/include/common/ip.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/ip.h.md | A5 sweep per-file doc |
| src/include/common/jsonapi.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/jsonapi.h.md | A5 sweep per-file doc |
| src/include/common/keywords.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/keywords.h.md | A5 sweep per-file doc |
| src/include/common/kwlookup.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/kwlookup.h.md | A5 sweep per-file doc |
| src/include/common/link-canary.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/link-canary.h.md | A5 sweep per-file doc |
| src/include/common/logging.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/logging.h.md | A5 sweep per-file doc |
| src/include/common/md5.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/md5.h.md | A5 sweep per-file doc |
| src/include/common/oauth-common.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/oauth-common.h.md | A5 sweep per-file doc |
| src/include/common/openssl.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/openssl.h.md | A5 sweep per-file doc |
| src/include/common/parse_manifest.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/parse_manifest.h.md | A5 sweep per-file doc |
| src/include/common/percentrepl.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/percentrepl.h.md | A5 sweep per-file doc |
| src/include/common/pg_lzcompress.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/pg_lzcompress.h.md | A5 sweep per-file doc |
| src/include/common/pg_prng.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/pg_prng.h.md | A5 sweep per-file doc |
| src/include/common/relpath.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/relpath.h.md | A5 sweep per-file doc |
| src/include/common/restricted_token.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/restricted_token.h.md | A5 sweep per-file doc |
| src/include/common/saslprep.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/saslprep.h.md | A5 sweep per-file doc |
| src/include/common/scram-common.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/scram-common.h.md | A5 sweep per-file doc |
| src/include/common/sha1.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/sha1.h.md | A5 sweep per-file doc |
| src/include/common/sha2.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/sha2.h.md | A5 sweep per-file doc |
| src/include/common/shortest_dec.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/shortest_dec.h.md | A5 sweep per-file doc |
| src/include/common/string.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/string.h.md | A5 sweep per-file doc |
| src/include/common/unicode_case.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/unicode_case.h.md | A5 sweep per-file doc |
| src/include/common/unicode_case_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_case_table.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_category.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/unicode_category.h.md | A5 sweep per-file doc |
| src/include/common/unicode_category_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_category_table.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_east_asian_fw_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_east_asian_fw_table.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_nonspacing_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_nonspacing_table.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_norm.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/unicode_norm.h.md | A5 sweep per-file doc |
| src/include/common/unicode_norm_hashfunc.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_norm_hashfunc.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_norm_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_norm_table.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_normprops_table.h | 2026-06-03 | 4b0bf0788b0 | skim | common-a5 | knowledge/files/src/include/common/unicode_normprops_table.h.md | Generated Unicode table — stub doc |
| src/include/common/unicode_version.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/unicode_version.h.md | A5 sweep per-file doc |
| src/include/common/username.h | 2026-06-03 | 4b0bf0788b0 | read | common-a5 | knowledge/files/src/include/common/username.h.md | A5 sweep per-file doc |

<!-- a6-bin-upgrade 2026-06-03 — foreground sweep #6 (Phase A); 36 docs via 5 parallel general-purpose agents covering src/bin/{pg_upgrade,pg_rewind,pg_amcheck} -->
| src/bin/pg_upgrade/check.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/check.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/controldata.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/controldata.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/dump.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/dump.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/exec.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/exec.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/file.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/file.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/function.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/function.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/info.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/info.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/multixact_read_v18.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/multixact_read_v18.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/multixact_read_v18.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/multixact_read_v18.h.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/multixact_rewrite.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/multixact_rewrite.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/option.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/option.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/parallel.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/parallel.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/pg_upgrade.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/pg_upgrade.h | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/relfilenumber.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/server.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/server.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/slru_io.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/slru_io.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/slru_io.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/slru_io.h.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/tablespace.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/tablespace.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/task.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/task.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/util.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/util.c.md | A6 sweep per-file doc |
| src/bin/pg_upgrade/version.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_upgrade/version.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/datapagemap.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/datapagemap.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/datapagemap.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/datapagemap.h.md | A6 sweep per-file doc |
| src/bin/pg_rewind/file_ops.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/file_ops.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/file_ops.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/file_ops.h.md | A6 sweep per-file doc |
| src/bin/pg_rewind/filemap.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/filemap.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/filemap.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/filemap.h.md | A6 sweep per-file doc |
| src/bin/pg_rewind/libpq_source.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/libpq_source.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/local_source.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/local_source.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/parsexlog.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/parsexlog.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/pg_rewind.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/pg_rewind.c.md | A6 sweep per-file doc |
| src/bin/pg_rewind/pg_rewind.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/pg_rewind.h.md | A6 sweep per-file doc |
| src/bin/pg_rewind/rewind_source.h | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/rewind_source.h.md | A6 sweep per-file doc |
| src/bin/pg_rewind/timeline.c | 2026-06-03 | 4b0bf0788b0 | read | bin-upgrade-a6 | knowledge/files/src/bin/pg_rewind/timeline.c.md | A6 sweep per-file doc |
| src/bin/pg_amcheck/pg_amcheck.c | 2026-06-03 | 4b0bf0788b0 | deep-read | bin-upgrade-a6 | knowledge/files/src/bin/pg_amcheck/pg_amcheck.c.md | A6 sweep — heap/btree verifier frontend |
| src/backend/utils/adt/bool.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/bool.c.md | boolean type I/O; parse_bool_with_len keyword table; trailing-char invariant |
| src/backend/utils/adt/char.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/char.c.md | single-byte "char" type I/O + int/text coercions |
| src/backend/utils/adt/name.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/name.c.md | NameData type (NAMEDATALEN blank-padded); nameconcatoid suffix sizing |
| src/backend/utils/adt/xid.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/xid.c.md | xid/xid8 types; wraparound vs plain-u32 comparator split (triangle ineq) |
| src/backend/utils/adt/tid.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/tid.c.md | TID/ItemPointer I/O; NoCheck accessors; padding-aware hashtid |
| src/backend/utils/adt/oid8.c | 2026-06-03 | 4b0bf0788b0 | read | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/oid8.c.md | scalar 8-byte Oid8 type (NOT oidvector — that is oid.c); hashes as int8 |
| src/backend/utils/adt/arrayutils.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/arrayutils.c.md | array subscript/dim arithmetic; two-tier Safe vs unchecked overflow contract |
| src/backend/utils/adt/pg_lsn.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/pg_lsn.c.md | pg_lsn (XLogRecPtr) I/O; add/sub overflow delegated to numeric_pg_lsn |
| src/backend/utils/adt/uuid.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/uuid.c.md | uuid I/O/cmp/hash; v4+v7 generators via pg_strong_random; v7 backend-local monotonicity |
| src/backend/utils/adt/mac.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/mac.c.md | macaddr (6-byte) I/O/cmp; padding-free struct so sizeof-hash is safe |
| src/backend/utils/adt/mac8.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/mac8.c.md | macaddr8 (EUI-64) I/O; macaddr8_set7bit; hexlookup range-guard pitfall |
| src/backend/utils/adt/enum.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/enum.c.md | enum I/O via pg_enum; uncommitted-value check_safe_enum_use; soft-error gap |
| src/backend/utils/adt/cash.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/cash.c.md | money (int64 cents); lc_monetary-driven I/O; not locale-stable round-trip |
| src/backend/utils/adt/numutils.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/numutils.c.md | int<->string core (pg_strtoint*/pg_*toa); overflow detection reference impl |
| src/backend/utils/adt/encode.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/encode.c.md | encode()/decode() dispatch (hex/base64/escape); output-length overflow contract |
| src/backend/utils/adt/quote.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/quote.c.md | quote_ident/literal/nullable; SQL_STR_DOUBLE + E-prefix injection safety |
| src/backend/utils/adt/ascii.c | 2026-06-03 | 4b0bf0788b0 | deep | pg-file-backfiller(cloud) | knowledge/files/src/backend/utils/adt/ascii.c.md | to_ascii + ascii_safe_strlcpy; inline translation-table length invariant |

<!-- a7-utils-cache-adt 2026-06-03 — foreground sweep #7 (Phase A); 104 docs via 6 parallel general-purpose agents covering src/backend/utils/{cache,adt}/ -->
| src/backend/utils/adt/acl.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/acl.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/amutils.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/amutils.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/array_expanded.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/array_expanded.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/array_selfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/array_selfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/arraysubs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/arraysubs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/arrayutils.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/arrayutils.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/ascii.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/ascii.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/bool.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/bool.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/bytea.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/bytea.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/cash.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/cash.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/char.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/char.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/cryptohashfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/cryptohashfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/datetime.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/datetime.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/datum.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/datum.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/dbsize.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/dbsize.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/ddlutils.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/ddlutils.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/domains.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/domains.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/encode.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/encode.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/enum.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/enum.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/expandeddatum.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/expandeddatum.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/expandedrecord.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/expandedrecord.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/format_type.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/format_type.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/formatting.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/formatting.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/genfile.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/genfile.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/geo_ops.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/geo_ops.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/geo_selfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/geo_selfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/geo_spgist.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/geo_spgist.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/hbafuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/hbafuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/inet_cidr_ntop.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/inet_cidr_ntop.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/inet_net_pton.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/inet_net_pton.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/json.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/json.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/jsonb_gin.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/jsonb_gin.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/jsonbsubs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/jsonbsubs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/jsonfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/jsonfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/jsonpath_internal.h | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/jsonpath_internal.h.md | A7 sweep per-file doc |
| src/backend/utils/adt/levenshtein.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/levenshtein.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/like_match.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/like_match.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/like_support.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/like_support.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/lockfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/lockfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/mac.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/mac.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/mac8.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/mac8.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/mcxtfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/mcxtfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/misc.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/misc.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/multirangetypes.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/multirangetypes.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/multirangetypes_selfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/multirangetypes_selfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/multixactfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/multixactfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/name.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/name.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/network.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/network.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/network_gist.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/network_gist.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/network_selfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/network_selfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/network_spgist.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/network_spgist.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/numutils.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/numutils.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/oid8.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/oid8.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/oracle_compat.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/oracle_compat.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/orderedsetaggs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/orderedsetaggs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/partitionfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/partitionfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_dependencies.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_dependencies.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_locale.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_locale.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_locale_builtin.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_locale_builtin.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_locale_icu.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_locale_icu.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_locale_libc.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_locale_libc.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_lsn.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_lsn.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_ndistinct.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_ndistinct.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pg_upgrade_support.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/pg_upgrade_support.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pgstatfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/pgstatfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pseudorandomfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/pseudorandomfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/pseudotypes.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/pseudotypes.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/quote.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/quote.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/rangetypes.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/rangetypes.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/rangetypes_gist.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/rangetypes_gist.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/rangetypes_selfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/rangetypes_selfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/rangetypes_spgist.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/rangetypes_spgist.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/rangetypes_typanalyze.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/rangetypes_typanalyze.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/regexp.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/regexp.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/regproc.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/regproc.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/ri_triggers.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/ri_triggers.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/rowtypes.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/rowtypes.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/ruleutils.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/ruleutils.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/skipsupport.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/skipsupport.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tid.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tid.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/trigfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/trigfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsginidx.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsginidx.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsgistidx.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/tsgistidx.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsquery.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/tsquery.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsquery_cleanup.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsquery_cleanup.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsquery_gist.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsquery_gist.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsquery_op.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsquery_op.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsquery_rewrite.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsquery_rewrite.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsquery_util.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsquery_util.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsrank.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/tsrank.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsvector.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsvector.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsvector_op.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/tsvector_op.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/tsvector_parser.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/tsvector_parser.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/uuid.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/uuid.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/varbit.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/varbit.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/version.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/version.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/waitfuncs.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/waitfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/windowfuncs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/windowfuncs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/xid.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/adt/xid.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/xid8funcs.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/xid8funcs.c.md | A7 sweep per-file doc |
| src/backend/utils/adt/xml.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/adt/xml.c.md | A7 sweep per-file doc |
| src/backend/utils/cache/funccache.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/cache/funccache.c.md | A7 sweep per-file doc |
| src/backend/utils/cache/relfilenumbermap.c | 2026-06-03 | 4b0bf0788b0 | read | utils-a7 | knowledge/files/src/backend/utils/cache/relfilenumbermap.c.md | A7 sweep per-file doc |
| src/backend/utils/cache/relmapper.c | 2026-06-03 | 4b0bf0788b0 | deep-read | utils-a7 | knowledge/files/src/backend/utils/cache/relmapper.c.md | A7 sweep per-file doc |

<!-- a8-include-replication 2026-06-04 — foreground sweep #8 (Phase A); 22 docs via 3 parallel general-purpose agents -->
| src/include/replication/conflict.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/conflict.h.md | A8 sweep per-file doc |
| src/include/replication/decode.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/decode.h.md | A8 sweep per-file doc |
| src/include/replication/logical.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/logical.h.md | A8 sweep per-file doc |
| src/include/replication/logicalctl.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/logicalctl.h.md | A8 sweep per-file doc |
| src/include/replication/logicallauncher.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/logicallauncher.h.md | A8 sweep per-file doc |
| src/include/replication/logicalproto.h | 2026-06-04 | 4b0bf0788b0 | deep-read | include-replication-a8 | knowledge/files/src/include/replication/logicalproto.h.md | A8 sweep per-file doc |
| src/include/replication/logicalrelation.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/logicalrelation.h.md | A8 sweep per-file doc |
| src/include/replication/logicalworker.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/logicalworker.h.md | A8 sweep per-file doc |
| src/include/replication/message.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/message.h.md | A8 sweep per-file doc |
| src/include/replication/origin.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/origin.h.md | A8 sweep per-file doc |
| src/include/replication/output_plugin.h | 2026-06-04 | 4b0bf0788b0 | deep-read | include-replication-a8 | knowledge/files/src/include/replication/output_plugin.h.md | A8 sweep per-file doc |
| src/include/replication/pgoutput.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/pgoutput.h.md | A8 sweep per-file doc |
| src/include/replication/reorderbuffer.h | 2026-06-04 | 4b0bf0788b0 | deep-read | include-replication-a8 | knowledge/files/src/include/replication/reorderbuffer.h.md | A8 sweep per-file doc |
| src/include/replication/slot.h | 2026-06-04 | 4b0bf0788b0 | deep-read | include-replication-a8 | knowledge/files/src/include/replication/slot.h.md | A8 sweep per-file doc |
| src/include/replication/slotsync.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/slotsync.h.md | A8 sweep per-file doc |
| src/include/replication/snapbuild.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/snapbuild.h.md | A8 sweep per-file doc |
| src/include/replication/snapbuild_internal.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/snapbuild_internal.h.md | A8 sweep per-file doc |
| src/include/replication/syncrep.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/syncrep.h.md | A8 sweep per-file doc |
| src/include/replication/walreceiver.h | 2026-06-04 | 4b0bf0788b0 | deep-read | include-replication-a8 | knowledge/files/src/include/replication/walreceiver.h.md | A8 sweep per-file doc |
| src/include/replication/walsender.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/walsender.h.md | A8 sweep per-file doc |
| src/include/replication/walsender_private.h | 2026-06-04 | 4b0bf0788b0 | read | include-replication-a8 | knowledge/files/src/include/replication/walsender_private.h.md | A8 sweep per-file doc |
| src/include/replication/worker_internal.h | 2026-06-04 | 4b0bf0788b0 | deep-read | include-replication-a8 | knowledge/files/src/include/replication/worker_internal.h.md | A8 sweep per-file doc |

<!-- a9-plpgsql 2026-06-04 — foreground sweep #9 (Phase A); 9 source files via 4 parallel general-purpose agents; pl_kwlists.md combines the two kwlist headers -->
| src/pl/plpgsql/src/pl_comp.c | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_comp.md | A9 sweep per-file doc |
| src/pl/plpgsql/src/pl_exec.c | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_exec.md | A9 sweep per-file doc; 9218 LOC giant |
| src/pl/plpgsql/src/pl_funcs.c | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_funcs.md | A9 sweep per-file doc |
| src/pl/plpgsql/src/pl_gram.y | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_gram.md | A9 sweep per-file doc; Bison grammar |
| src/pl/plpgsql/src/pl_handler.c | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_handler.md | A9 sweep per-file doc; privileged entrypoint |
| src/pl/plpgsql/src/pl_reserved_kwlist.h | 2026-06-04 | 4b0bf0788b0 | read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_kwlists.md | A9 sweep; combined kwlist doc |
| src/pl/plpgsql/src/pl_scanner.c | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_scanner.md | A9 sweep per-file doc |
| src/pl/plpgsql/src/pl_unreserved_kwlist.h | 2026-06-04 | 4b0bf0788b0 | read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/pl_kwlists.md | A9 sweep; combined kwlist doc |
| src/pl/plpgsql/src/plpgsql.h | 2026-06-04 | 4b0bf0788b0 | deep-read | plpgsql-a9 | knowledge/files/src/pl/plpgsql/src/plpgsql.md | A9 sweep per-file doc; 1333 LOC landmark header |

<!-- a10-pl-other 2026-06-04 — foreground sweep #10 (Phase A); 30 source files via 4 parallel general-purpose agents; ppport.h SKIPPED as vendored Devel::PPPort boilerplate; plpython .c/.h modules combined into one doc per module per A9 pl_kwlists.md precedent -->
| src/pl/plperl/plperl.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plperl/plperl.c.md | A10 sweep per-file doc; dual-posture trusted+untrusted |
| src/pl/plperl/plperl.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plperl/plperl.h.md | A10 sweep per-file doc |
| src/pl/plperl/plperl_system.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plperl/plperl_system.h.md | A10 sweep per-file doc |
| src/pl/plpython/plpython.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpython.h.md | A10 sweep per-file doc |
| src/pl/plpython/plpython_system.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpython_system.h.md | A10 sweep per-file doc |
| src/pl/plpython/plpy_main.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_main.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_main.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_main.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_elog.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_elog.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_elog.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_elog.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_exec.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_exec.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_exec.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_exec.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_procedure.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_procedure.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_procedure.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_procedure.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_typeio.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_typeio.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_typeio.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_typeio.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_plpymodule.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_plpymodule.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_plpymodule.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_plpymodule.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_resultobject.c | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_resultobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_resultobject.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_resultobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_planobject.c | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_planobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_planobject.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_planobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_cursorobject.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_cursorobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_cursorobject.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_cursorobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_spi.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_spi.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_spi.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_spi.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_util.c | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_util.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_util.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_util.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_subxactobject.c | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_subxactobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/plpython/plpy_subxactobject.h | 2026-06-04 | 4b0bf0788b0 | read | pl-other-a10 | knowledge/files/src/pl/plpython/plpy_subxactobject.md | A10 sweep; combined .c+.h module doc |
| src/pl/tcl/pltcl.c | 2026-06-04 | 4b0bf0788b0 | deep-read | pl-other-a10 | knowledge/files/src/pl/tcl/pltcl.c.md | A10 sweep per-file doc; dual-posture trusted+untrusted; Tcl Safe slave interp |

<!-- a11-contrib-top 2026-06-04 — foreground sweep #11 (Phase A); 36 source files via 4 parallel general-purpose agents; FIRST contrib/ sweep -->
| contrib/pg_stat_statements/pg_stat_statements.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md | A11; query telemetry |
| contrib/dblink/dblink.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/dblink/dblink.c.md | A11; cross-cluster query bridge |
| contrib/postgres_fdw/postgres_fdw.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md | A11; 8837 LOC FDW core |
| contrib/postgres_fdw/connection.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/postgres_fdw/connection.c.md | A11; cross-cluster trust boundary |
| contrib/postgres_fdw/deparse.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/postgres_fdw/deparse.c.md | A11; SQL emission |
| contrib/postgres_fdw/option.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/postgres_fdw/option.c.md | A11; option allowlist |
| contrib/postgres_fdw/shippable.c | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/postgres_fdw/shippable.c.md | A11; pushdown decisions |
| contrib/postgres_fdw/postgres_fdw.h | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/postgres_fdw/postgres_fdw.h.md | A11; internal header |
| contrib/pgcrypto/pgcrypto.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgcrypto.md | A11; SQL surface (combined .c+.h) |
| contrib/pgcrypto/pgcrypto.h | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgcrypto.md | A11; combined .c+.h |
| contrib/pgcrypto/px.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/px.md | A11; PX abstract API (combined .c+.h) |
| contrib/pgcrypto/px.h | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/px.md | A11; combined .c+.h |
| contrib/pgcrypto/px-crypt.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/px-crypt.md | A11; crypt(3) dispatch |
| contrib/pgcrypto/px-crypt.h | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/px-crypt.md | A11; combined .c+.h |
| contrib/pgcrypto/px-hmac.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/px-hmac.md | A11; HMAC over PX hash |
| contrib/pgcrypto/openssl.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/openssl.md | A11; OpenSSL backend |
| contrib/pgcrypto/mbuf.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/mbuf.md | A11; byte-buffer (combined .c+.h) |
| contrib/pgcrypto/mbuf.h | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/mbuf.md | A11; combined .c+.h |
| contrib/pgcrypto/crypt-blowfish.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/crypt-blowfish.md | A11; bcrypt |
| contrib/pgcrypto/crypt-des.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/crypt-des.md | A11; traditional DES crypt(3) |
| contrib/pgcrypto/crypt-md5.c | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/crypt-md5.md | A11; $1$ MD5-crypt |
| contrib/pgcrypto/crypt-sha.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/crypt-sha.md | A11; $5$/$6$ SHA-crypt |
| contrib/pgcrypto/crypt-gensalt.c | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/crypt-gensalt.md | A11; salt generators |
| contrib/pgcrypto/pgp.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp.md | A11; PGP framework (combined .c+.h) |
| contrib/pgcrypto/pgp.h | 2026-06-04 | 4b0bf0788b0 | read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp.md | A11; combined .c+.h |
| contrib/pgcrypto/pgp-pgsql.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-pgsql.md | A11; PGP SQL bindings |
| contrib/pgcrypto/pgp-armor.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-armor.md | A11; ASCII-armor |
| contrib/pgcrypto/pgp-cfb.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-cfb.md | A11; CFB mode |
| contrib/pgcrypto/pgp-compress.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-compress.md | A11; zlib decompression — CRITICAL bomb |
| contrib/pgcrypto/pgp-decrypt.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-decrypt.md | A11; PGP packet parser + decrypt |
| contrib/pgcrypto/pgp-encrypt.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-encrypt.md | A11; PGP encryption |
| contrib/pgcrypto/pgp-info.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-info.md | A11; key-info functions |
| contrib/pgcrypto/pgp-mpi-openssl.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-mpi-openssl.md | A11; MPI via OpenSSL |
| contrib/pgcrypto/pgp-mpi.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-mpi.md | A11; MPI shared |
| contrib/pgcrypto/pgp-pubdec.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-pubdec.md | A11; PKCS#1 v1.5 decrypt |
| contrib/pgcrypto/pgp-pubenc.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-pubenc.md | A11; PKCS#1 v1.5 encrypt |
| contrib/pgcrypto/pgp-pubkey.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-pubkey.md | A11; public-key parsing |
| contrib/pgcrypto/pgp-s2k.c | 2026-06-04 | 4b0bf0788b0 | deep-read | contrib-top-a11 | knowledge/files/contrib/pgcrypto/pgp-s2k.md | A11; String-to-Key |

<!-- a11-fe_utils 2026-06-04 — cloud pg-file-backfiller sweep (overnight); 18 .c files in src/fe_utils/ via 4 parallel general-purpose agents -->
| src/fe_utils/string_utils.c | 2026-06-04 | 4b0bf0788b0 | deep-read | a11-fe_utils | knowledge/files/src/fe_utils/string_utils.c.md | A11 sweep; fmtId/processSQLNamePattern/appendShellString chokepoint (A4 gap closed) |
| src/fe_utils/option_utils.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/option_utils.c.md | A11 sweep; option_parse_int/str, handle_help_version_opts |
| src/fe_utils/query_utils.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/query_utils.c.md | A11 sweep; executeQuery/executeMaintenanceCommand |
| src/fe_utils/simple_list.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/simple_list.c.md | A11 sweep; simple_{string,oid,ptr}_list helpers |
| src/fe_utils/conditional.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/conditional.c.md | A11 sweep; psql \if/\elif/\else/\endif conditional stack |
| src/fe_utils/cancel.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/cancel.c.md | A11 sweep; async-signal-safe query cancel; cancelConn global |
| src/fe_utils/connect_utils.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/connect_utils.c.md | A11 sweep; connectDatabase + password retry; secret-scrub site |
| src/fe_utils/recovery_gen.c | 2026-06-04 | 4b0bf0788b0 | deep-read | a11-fe_utils | knowledge/files/src/fe_utils/recovery_gen.c.md | A11 sweep; writes primary_conninfo cleartext password to postgresql.auto.conf |
| src/fe_utils/version.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/version.c.md | A11 sweep; PG_VERSION parse; memcpy uninit-tail correctness flag |
| src/fe_utils/archive.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/archive.c.md | A11 sweep; thin wrapper; escaping lives in src/common/archive.c |
| src/fe_utils/astreamer_file.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/astreamer_file.c.md | A11 sweep; plain_writer/extractor; absolute-symlink path-check bypass |
| src/fe_utils/astreamer_tar.c | 2026-06-04 | 4b0bf0788b0 | deep-read | a11-fe_utils | knowledge/files/src/fe_utils/astreamer_tar.c.md | A11 sweep; tar parser/archiver; A4 trust-the-stream boundary; PAX rejected |
| src/fe_utils/astreamer_gzip.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/astreamer_gzip.c.md | A11 sweep; gzip streamer; streaming output buffer (no RAM bomb) |
| src/fe_utils/astreamer_lz4.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/astreamer_lz4.c.md | A11 sweep; lz4 streamer; streaming output buffer |
| src/fe_utils/astreamer_zstd.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/astreamer_zstd.c.md | A11 sweep; zstd streamer; ZSTD_DStreamOutSize bound |
| src/fe_utils/mbprint.c | 2026-06-04 | 4b0bf0788b0 | read | a11-fe_utils | knowledge/files/src/fe_utils/mbprint.c.md | A11 sweep; pg_wcswidth/pg_wcsformat; mbvalidate UTF-8-only no-op |
| src/fe_utils/parallel_slot.c | 2026-06-04 | 4b0bf0788b0 | deep-read | a11-fe_utils | knowledge/files/src/fe_utils/parallel_slot.c.md | A11 sweep; async connection-slot pool for reindexdb/vacuumdb |
| src/fe_utils/print.c | 2026-06-04 | 4b0bf0788b0 | deep-read | a11-fe_utils | knowledge/files/src/fe_utils/print.c.md | A11 sweep; psql result formatter; 8-format dispatch; width_total overflow flag |
| src/include/fe_utils/print.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/print.h.md | headers sweep; printTableOpt/printTableContent model; mutable pg_utf8format global |
| src/include/fe_utils/astreamer.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/astreamer.h.md | headers sweep; astreamer vtable/ops + chunk-sequence contract; base-must-be-first convention |
| src/include/fe_utils/string_utils.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/string_utils.h.md | headers sweep; fmtId/processSQLNamePattern/appendShellString API; identifier-quoting chokepoint |
| src/include/fe_utils/conditional.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/conditional.h.md | headers sweep; \if/\elif/\endif 6-state stack (psql+pgbench) |
| src/include/fe_utils/psqlscan_int.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/psqlscan_int.h.md | headers sweep; PsqlScanStateData + 0xFF-substitution trick; BEGIN/END 4-id heuristic |
| src/include/fe_utils/psqlscan.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/psqlscan.h.md | headers sweep; public lexer API; PsqlScanQuoteType delegation to host callback |
| src/include/fe_utils/parallel_slot.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/parallel_slot.h.md | headers sweep; ParallelSlot pool for reindexdb/vacuumdb; handler result-ownership |
| src/include/fe_utils/simple_list.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/simple_list.h.md | headers sweep; SimpleOid/String/Ptr lists; touched-flag semantics |
| src/include/fe_utils/connect_utils.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/connect_utils.h.md | headers sweep; ConnParams + trivalue; connectDatabase password-reuse |
| src/include/fe_utils/option_utils.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/option_utils.h.md | headers sweep; option_parse_int + check_mut_excl_opts variadic macro |
| src/include/fe_utils/mbprint.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/mbprint.h.md | headers sweep; pg_wcssize/pg_wcsformat measure-then-layout contract |
| src/include/fe_utils/recovery_gen.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/recovery_gen.h.md | headers sweep; GenerateRecoveryConfig API; MINIMUM_VERSION_FOR_RECOVERY_GUC; secret-to-disk |
| src/include/fe_utils/cancel.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/cancel.h.md | headers sweep; CancelRequested sig_atomic_t + SetCancelConn; distinct from print.h cancel_pressed |
| src/include/fe_utils/query_utils.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/query_utils.h.md | headers sweep; executeQuery/Command/MaintenanceCommand exit-vs-bool split |
| src/include/fe_utils/version.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/version.h.md | headers sweep; get_pg_version + GET_PG_MAJORVERSION_NUM; PG_VERSION_H guard-name reuse |
| src/include/fe_utils/archive.h | 2026-06-05 | 4b0bf0788b0 | read | fe_utils-headers | knowledge/files/src/include/fe_utils/archive.h.md | headers sweep; RestoreArchivedFile restore_command runner |
| src/port/explicit_bzero.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/explicit_bzero.c.md | port sweep; 5-arm dead-store-resistant scrub; SecretBuf primitive |
| src/port/pg_strong_random.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/pg_strong_random.c.md | port sweep; CSPRNG OpenSSL/Win32/urandom; return-value load-bearing; O_CLOEXEC nit |
| src/port/timingsafe_bcmp.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/timingsafe_bcmp.c.md | port sweep; constant-time compare; CRYPTO_memcmp / XOR-OR fold |
| src/port/snprintf.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/snprintf.c.md | port sweep; PG own printf; %m=errno-at-entry; %n$ positional; C99 subset |
| src/port/path.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/path.c.md | port sweep; canonicalize + path_is_safe_for_extraction gate; canonicalization precondition |
| src/port/quotes.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/quotes.c.md | port sweep; config-file quote-doubling; NOT for SQL; int-len trunc nit |
| src/port/tar.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/tar.c.md | port sweep; ustar header octal/base-256; 99-byte name cap; checksum-last |
| src/port/strlcpy.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/strlcpy.c.md | port sweep; OpenBSD bounded copy; always NUL-terminates |
| src/port/strlcat.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/strlcat.c.md | port sweep; OpenBSD bounded concat; siz=whole-buffer |
| src/port/pgmkdirp.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/pgmkdirp.c.md | port sweep; mkdir -p; umask dance; mutates path on failure |
| src/port/pgcheckdir.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/pgcheckdir.c.md | port sweep; dir empty/dotfile/mount classification; errno=0 readdir idiom |
| src/port/pg_bitutils.c | 2026-06-06 | 4b0bf0788b0 | read | port-shims | knowledge/files/src/port/pg_bitutils.c.md | port sweep; clz/ctz/popcount tables + portable popcount; mask-splat |
| src/port/chklocale.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/chklocale.c.md | port sweep; locale codeset -> PG encoding map; save/restore LC_CTYPE |
| src/port/getpeereid.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/port/getpeereid.c.md | port sweep; UDS peer uid/gid; kernel-attested; peer auth anchor |
| src/timezone/pgtz.c | 2026-06-06 | 4b0bf0788b0 | deep | port-shims | knowledge/files/src/timezone/pgtz.c.md | timezone glue; case-insensitive tzfile open; GMT no-fs special-case; hidden-file traversal guard |
| src/timezone/pgtz.h | 2026-06-06 | 4b0bf0788b0 | read | port-shims | knowledge/files/src/timezone/pgtz.h.md | tz private header; struct state/ttinfo/lsinfo/pg_tz; fixed-size zone footprint |
| src/timezone/tzfile.h | 2026-06-06 | 4b0bf0788b0 | read | port-shims | knowledge/files/src/timezone/tzfile.h.md | TZif on-disk format; TZ_MAX_* DoS bounds; v2/v3 dual layout |
| src/timezone/private.h | 2026-06-07 | 4b0bf0788b0 | read | timezone | knowledge/files/src/timezone/private.h.md | timezone sweep; vendored IANA private header; calendar/limit/leap macros; TIME_T_MIN/MAX over pg_time_t |
| src/timezone/strftime.c | 2026-06-07 | 4b0bf0788b0 | read | timezone | knowledge/files/src/timezone/strftime.c.md | timezone sweep; bundled C-locale strftime; pg_strftime overrun-returns-empty; %Z is the untrusted-input path |
| src/timezone/localtime.c | 2026-06-07 | 4b0bf0788b0 | deep | timezone | knowledge/files/src/timezone/localtime.c.md | timezone sweep; runtime TZif loader+converter; tzloadbody hard-validates; pg_tz_acceptable rejects leap-sec; static result buffer; malloc-not-palloc |
| src/timezone/zic.c | 2026-06-07 | 4b0bf0788b0 | read | timezone | knowledge/files/src/timezone/zic.c.md | timezone sweep; build-time zone compiler (frontend tool); namecheck path-traversal gate; writezone inverse of tzloadbody; conservative umask |
| src/include/storage/aio_types.h | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/include/storage/aio_types.h.md | AIO sweep; low-include-burden types; PgAioResult bitpacked to 8 bytes (StaticAssert); split-uint32 generation in wait ref |
| src/include/storage/aio.h | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/include/storage/aio.h.md | AIO sweep; main public interface; worker is DEFAULT_IO_METHOD; callbacks by ID not pointer (EXEC_BACKEND); complete_shared vs complete_local |
| src/include/storage/aio_internal.h | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/include/storage/aio_internal.h.md | AIO sweep; private data model; 8-state PgAioHandleState machine; PgAioHandle/PgAioBackend/PgAioCtl/IoMethodOps; PGAIO_VERBOSE XXX |
| src/include/storage/aio_subsys.h | 2026-06-08 | 4b0bf0788b0 | read | storage-aio | knowledge/files/src/include/storage/aio_subsys.h.md | AIO sweep; subsystem-not-issuer entry points; pgaio_init_backend/error_cleanup/AtEOXact_Aio/workers_enabled |
| src/backend/storage/aio/aio.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/aio.c.md | AIO sweep; core engine; one-handed-out-handle deadlock rule; generation-gated wait refs; completion-in-critsec; batchmode deadlock footgun |
| src/backend/storage/aio/aio_callback.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/aio_callback.c.md | AIO sweep; ID->callbacks table; innermost-first; stage/complete_shared/complete_local drivers; result distillation |
| src/backend/storage/aio/aio_io.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/aio_io.c.md | AIO sweep; readv/writev start routines; pgaio_io_perform_synchronously (shared fallback); -errno convention |
| src/backend/storage/aio/aio_target.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/aio_target.c.md | AIO sweep; target registry (smgr only); reopen for worker mode; set_target exactly once |
| src/backend/storage/aio/aio_init.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/aio_init.c.md | AIO sweep; shmem sizing/init; io_max_concurrency auto-tune (cap 64); generation starts at 1; method shmem chaining |
| src/backend/storage/aio/aio_funcs.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/aio_funcs.c.md | AIO sweep; pg_get_aios SRF (pg_aios view); lock-free generation/state recheck snapshot; cross-backend info exposure |
| src/backend/storage/aio/method_sync.c | 2026-06-08 | 4b0bf0788b0 | read | storage-aio | knowledge/files/src/backend/storage/aio/method_sync.c.md | AIO sweep; io_method=sync; always-synchronous; submit is unreachable elog(ERROR); shared fallback baseline |
| src/backend/storage/aio/method_worker.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/method_worker.c.md | AIO sweep; default method; shared submission ring + worker bitmap; elastic pool; wakeup-propagation chain; single-queue scaling ceiling |
| src/backend/storage/aio/method_io_uring.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/method_io_uring.c.md | AIO sweep; Linux io_uring; one ring per backend in postmaster; any-backend drain under completion_lock; EAGAIN->PANIC; IOSQE_ASYNC heuristic |
| src/backend/storage/aio/read_stream.c | 2026-06-08 | 4b0bf0788b0 | deep | storage-aio | knowledge/files/src/backend/storage/aio/read_stream.c.md | AIO sweep; THE read-stream helper; adaptive combine/readahead distances; fast path; forwarded buffers; int16 ~32k cap |
| src/backend/access/rmgrdesc/rmgrdesc_utils.c | 2026-06-08 | 4b0bf0788b0 | read | rmgrdesc | knowledge/files/src/backend/access/rmgrdesc/rmgrdesc_utils.c.md | rmgrdesc sweep; shared array_desc + element printers; canonical waldump array format |
| src/backend/access/rmgrdesc/xlogdesc.c | 2026-06-08 | 4b0bf0788b0 | deep | rmgrdesc | knowledge/files/src/backend/access/rmgrdesc/xlogdesc.c.md | rmgrdesc sweep; checkpoint decoder; wal_level_options table; XLogRecGetBlockRefInfo (waldump FPI accounting) |
| src/backend/access/rmgrdesc/xactdesc.c | 2026-06-08 | 4b0bf0788b0 | deep | rmgrdesc | knowledge/files/src/backend/access/rmgrdesc/xactdesc.c.md | rmgrdesc sweep; canonical ParseCommit/Abort/PrepareRecord (shared redo+waldump); xinfo-gated commit wire format; alignment gotcha |
| src/backend/access/rmgrdesc/heapdesc.c | 2026-06-08 | 4b0bf0788b0 | deep | rmgrdesc | knowledge/files/src/backend/access/rmgrdesc/heapdesc.c.md | rmgrdesc sweep; heap/heap2 record set; heap_xlog_deserialize_prune_and_freeze (shared); infobits/VM-bit decoding |
| src/backend/access/rmgrdesc/clogdesc.c | 2026-06-08 | 4b0bf0788b0 | read | rmgrdesc | knowledge/files/src/backend/access/rmgrdesc/clogdesc.c.md | rmgrdesc sweep; CLOG zeropage/truncate only; int64 pageno; status bits not individually WAL-logged |
| src/backend/access/rmgrdesc/standbydesc.c | 2026-06-08 | 4b0bf0788b0 | deep | rmgrdesc | knowledge/files/src/backend/access/rmgrdesc/standbydesc.c.md | rmgrdesc sweep; hot-standby LOCK/RUNNING_XACTS/INVALIDATIONS; standby_desc_invalidations shared inval renderer |

<!-- a12-contrib-security 2026-06-09 — foreground sweep #12 (Phase A); 30 source files via 4 parallel general-purpose agents; SECURITY-themed contrib bundle -->
| contrib/amcheck/verify_common.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/amcheck/verify_common.md | A12; combined .c+.h |
| contrib/amcheck/verify_common.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-security-a12 | knowledge/files/contrib/amcheck/verify_common.md | A12; combined .c+.h |
| contrib/amcheck/verify_gin.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/amcheck/verify_gin.md | A12; GIN verification |
| contrib/amcheck/verify_heapam.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/amcheck/verify_heapam.md | A12; heap verification; honest crash disclosure |
| contrib/amcheck/verify_nbtree.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/amcheck/verify_nbtree.md | A12; B-tree verification |
| contrib/pageinspect/pageinspect.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-security-a12 | knowledge/files/contrib/pageinspect/pageinspect.md | A12; combined .h+rawpage.c |
| contrib/pageinspect/rawpage.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/pageinspect.md | A12; central RLS-bypass primitive |
| contrib/pageinspect/heapfuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/heapfuncs.c.md | A12; tuple_data_split = type-input bypass canary |
| contrib/pageinspect/btreefuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/btreefuncs.c.md | A12; B-tree page introspection |
| contrib/pageinspect/brinfuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/brinfuncs.c.md | A12; BRIN page introspection |
| contrib/pageinspect/ginfuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/ginfuncs.c.md | A12; GIN page introspection |
| contrib/pageinspect/gistfuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/gistfuncs.c.md | A12; GiST page introspection |
| contrib/pageinspect/hashfuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pageinspect/hashfuncs.c.md | A12; most-hardened decoder |
| contrib/pageinspect/fsmfuncs.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-security-a12 | knowledge/files/contrib/pageinspect/fsmfuncs.c.md | A12; FSM page introspection |
| contrib/pgstattuple/pgstattuple.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pgstattuple/pgstattuple.c.md | A12; table stats; SnapshotDirty |
| contrib/pgstattuple/pgstatindex.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pgstattuple/pgstatindex.c.md | A12; index stats |
| contrib/pgstattuple/pgstatapprox.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/pgstattuple/pgstatapprox.c.md | A12; VM-trust fail-open |
| contrib/sepgsql/sepgsql.h | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/sepgsql.h.md | A12; SELinux class IDs + bit positions |
| contrib/sepgsql/hooks.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/hooks.c.md | A12; object_access_hook dispatch |
| contrib/sepgsql/selinux.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/selinux.c.md | A12; libselinux wrapper |
| contrib/sepgsql/uavc.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/uavc.c.md | A12; userspace AVC cache; permissive-widening bug |
| contrib/sepgsql/label.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/label.c.md | A12; security-label storage |
| contrib/sepgsql/database.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/database.c.md | A12; db_database class |
| contrib/sepgsql/schema.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/schema.c.md | A12; db_schema class |
| contrib/sepgsql/relation.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/relation.c.md | A12; db_table/sequence/view classes |
| contrib/sepgsql/proc.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/proc.c.md | A12; db_procedure class; line-279 typo finding |
| contrib/sepgsql/dml.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sepgsql/dml.c.md | A12; DML row-level filter; foreign-table gap |
| contrib/file_fdw/file_fdw.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/file_fdw/file_fdw.c.md | A12; in-tree path-traversal class |
| contrib/auth_delay/auth_delay.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/auth_delay/auth_delay.c.md | A12; failure-only delay = timing oracle |
| contrib/sslinfo/sslinfo.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-security-a12 | knowledge/files/contrib/sslinfo/sslinfo.c.md | A12; TLS connection introspection |

<!-- a13-contrib-datatypes 2026-06-09 — foreground sweep #13 (Phase A); 56 source files via 4 parallel general-purpose agents; contrib datatypes + index-AM opclasses -->
| contrib/hstore/hstore.h | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore.h.md | A13; hstore varlena format |
| contrib/hstore/hstore_compat.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore_compat.c.md | A13; pre-PG-8.4 compat — forged HS_FLAG_NEWVERSION bypass |
| contrib/hstore/hstore_gin.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore_gin.c.md | A13; GIN opclass |
| contrib/hstore/hstore_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore_gist.c.md | A13; GiST CRC32 signature collisions |
| contrib/hstore/hstore_io.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore_io.c.md | A13; I/O — hstore_recv DoS surface |
| contrib/hstore/hstore_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore_op.c.md | A13; operators + modifiers |
| contrib/hstore/hstore_subs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/hstore/hstore_subs.c.md | A13; subscripting |
| contrib/ltree/ltree.h | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/ltree.h.md | A13; ltree/lquery/ltxtquery varlena |
| contrib/ltree/ltree_io.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/ltree_io.c.md | A13; parse_lquery 400000x memory amplification |
| contrib/ltree/lquery_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/lquery_op.c.md | A13; checkCond catastrophic backtracking |
| contrib/ltree/ltree_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/ltree_op.c.md | A13; ltree operators |
| contrib/ltree/ltxtquery_io.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/ltxtquery_io.c.md | A13; ltxtquery parser + deparser |
| contrib/ltree/ltxtquery_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/ltxtquery_op.c.md | A13; ltxtquery evaluation |
| contrib/ltree/ltree_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/ltree_gist.c.md | A13; GiST opclass; siglen=64 default too small |
| contrib/ltree/_ltree_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/_ltree_gist.c.md | A13; ltree[] GiST; per-INSERT CPU DoS |
| contrib/ltree/_ltree_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/_ltree_op.c.md | A13; ltree[] operators |
| contrib/ltree/crc32.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/crc32.c.md | A13; locale-change breaks GiST signatures |
| contrib/ltree/crc32.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/ltree/crc32.h.md | A13 |
| contrib/btree_gist/btree_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_gist.md | A13; combined .c+.h |
| contrib/btree_gist/btree_gist.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_gist.md | A13; combined .c+.h |
| contrib/btree_gist/btree_utils_num.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_utils_num.md | A13; combined .c+.h |
| contrib/btree_gist/btree_utils_num.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_utils_num.md | A13; combined .c+.h |
| contrib/btree_gist/btree_utils_var.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_utils_var.md | A13; latent collation footgun |
| contrib/btree_gist/btree_utils_var.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_utils_var.md | A13; combined .c+.h |
| contrib/btree_gist/btree_bit.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_bit.c.md | A13 |
| contrib/btree_gist/btree_bool.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_bool.c.md | A13 |
| contrib/btree_gist/btree_bytea.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_bytea.c.md | A13 |
| contrib/btree_gist/btree_cash.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_cash.c.md | A13 |
| contrib/btree_gist/btree_date.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_date.c.md | A13 |
| contrib/btree_gist/btree_enum.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_enum.c.md | A13; OID stability footgun |
| contrib/btree_gist/btree_float4.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_float4.c.md | A13; NaN divergence vs nbtree |
| contrib/btree_gist/btree_float8.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_float8.c.md | A13; NaN divergence vs nbtree |
| contrib/btree_gist/btree_inet.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_inet.c.md | A13; lossy double scalar; *recheck=true |
| contrib/btree_gist/btree_int2.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_int2.c.md | A13 |
| contrib/btree_gist/btree_int4.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_int4.c.md | A13 |
| contrib/btree_gist/btree_int8.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_int8.c.md | A13 |
| contrib/btree_gist/btree_interval.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_interval.c.md | A13 |
| contrib/btree_gist/btree_macaddr.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_macaddr.c.md | A13 |
| contrib/btree_gist/btree_macaddr8.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_macaddr8.c.md | A13 |
| contrib/btree_gist/btree_numeric.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_numeric.c.md | A13; trnc=false load-bearing |
| contrib/btree_gist/btree_oid.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_oid.c.md | A13 |
| contrib/btree_gist/btree_text.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_text.c.md | A13; trnc=false saves text indexes |
| contrib/btree_gist/btree_time.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_time.c.md | A13 |
| contrib/btree_gist/btree_ts.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_ts.c.md | A13 |
| contrib/btree_gist/btree_uuid.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gist/btree_uuid.c.md | A13; WORDS_BIGENDIAN assumption |
| contrib/intarray/_int.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int.md | A13; combined .h+_int_tool.c |
| contrib/intarray/_int_tool.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int.md | A13; combined .h+_int_tool.c |
| contrib/intarray/_int_bool.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int_bool.md | A13; bool query parser; ~3GB DoS |
| contrib/intarray/_int_gin.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int_gin.md | A13; GIN opclass |
| contrib/intarray/_int_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int_gist.md | A13; GiST opclass |
| contrib/intarray/_int_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int_op.md | A13; array operators |
| contrib/intarray/_int_selfuncs.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_int_selfuncs.md | A13; selectivity functions |
| contrib/intarray/_intbig_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/intarray/_intbig_gist.md | A13; intbig GiST; trivial bit-collisions |
| contrib/tablefunc/tablefunc.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/tablefunc/tablefunc.md | A13; CRITICAL — connectby_text SQL injection |
| contrib/citext/citext.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/citext/citext.md | A13; collation asymmetry |
| contrib/btree_gin/btree_gin.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-datatypes-a13 | knowledge/files/contrib/btree_gin/btree_gin.md | A13; GIN opclass framework |

<!-- a14-contrib-remainder 2026-06-09 — foreground sweep #14 (Phase A); 44 source files via 4 parallel general-purpose agents; contrib remainder cleanup (23 modules) -->
| contrib/pg_visibility/pg_visibility.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_visibility/pg_visibility.c.md | A14; VM/FSM introspection; no C-side privilege checks |
| contrib/pg_buffercache/pg_buffercache_pages.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_buffercache/pg_buffercache_pages.c.md | A14; shared-buffers introspection; REVOKE-only gate |
| contrib/pg_freespacemap/pg_freespacemap.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/pg_freespacemap/pg_freespacemap.c.md | A14; tiny FSM wrapper |
| contrib/pg_prewarm/pg_prewarm.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_prewarm/pg_prewarm.c.md | A14; page-prewarming SRF |
| contrib/pg_prewarm/autoprewarm.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_prewarm/autoprewarm.c.md | A14; PUBLIC autoprewarm controls (no REVOKE) |
| contrib/pgrowlocks/pgrowlocks.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md | A14; row-lock introspection; buffer→SLRU lock ordering |
| contrib/pg_walinspect/pg_walinspect.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md | A14; 🚨 show_data=true RLS bypass via FPI |
| contrib/pg_surgery/heap_surgery.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_surgery/heap_surgery.c.md | A14; force-freeze resurrects aborted tuples |
| contrib/pg_overexplain/pg_overexplain.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_overexplain/pg_overexplain.c.md | A14; EXPLAIN extension; thin |
| contrib/basebackup_to_shell/basebackup_to_shell.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/basebackup_to_shell/basebackup_to_shell.c.md | A14; %-escape substitution model fragile |
| contrib/basic_archive/basic_archive.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/basic_archive/basic_archive.c.md | A14; sample WAL archive; stat-rename TOCTOU |
| contrib/tsm_system_rows/tsm_system_rows.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/tsm_system_rows/tsm_system_rows.c.md | A14; TABLESAMPLE with row target |
| contrib/tsm_system_time/tsm_system_time.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/tsm_system_time/tsm_system_time.c.md | A14; time budget enforced at block boundary |
| contrib/lo/lo.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/lo/lo.c.md | A14; legacy orphan-LO trigger |
| contrib/bloom/blcost.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/bloom/blcost.c.md | A14; bloom cost estimator |
| contrib/bloom/blinsert.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/bloom/blinsert.c.md | A14; metapage-lock serializes inserters |
| contrib/bloom/bloom.h | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/bloom/bloom.h.md | A14; bloom signature header |
| contrib/bloom/blscan.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/bloom/blscan.c.md | A14; sequential index scan |
| contrib/bloom/blutils.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/bloom/blutils.c.md | A14; deterministic signValue LCG |
| contrib/bloom/blvacuum.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/bloom/blvacuum.c.md | A14; bulk-delete |
| contrib/bloom/blvalidate.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/bloom/blvalidate.c.md | A14; opclass validator |
| contrib/isn/isn.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn.c.md | A14; ISBN/ISSN/ISMN/EAN/UPC parser; weak-input GUC |
| contrib/isn/isn.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn.h.md | A14; orphan `initialize` decl |
| contrib/isn/EAN13.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn_data_headers.md | A14; combined w/ ISBN/ISMN/ISSN/UPC; 2004/2006 tables |
| contrib/isn/ISBN.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn_data_headers.md | A14; combined w/ EAN/ISMN/ISSN/UPC |
| contrib/isn/ISMN.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn_data_headers.md | A14; combined w/ EAN/ISBN/ISSN/UPC |
| contrib/isn/ISSN.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn_data_headers.md | A14; combined w/ EAN/ISBN/ISMN/UPC |
| contrib/isn/UPC.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/isn/isn_data_headers.md | A14; combined w/ EAN/ISBN/ISMN/ISSN |
| contrib/seg/seg.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/seg/seg.c.md | A14; float seg; NaN-poison GiST |
| contrib/seg/segdata.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/seg/segdata.h.md | A14; SEG struct + sentinels |
| contrib/cube/cube.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/cube/cube.c.md | A14; N-d cube; 16 MB palloc upstream of dim cap |
| contrib/cube/cubedata.h | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/cube/cubedata.h.md | A14; NDBOX header |
| contrib/earthdistance/earthdistance.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/earthdistance/earthdistance.c.md | A14; spherical earth (cube wrapper) |
| contrib/unaccent/unaccent.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/unaccent/unaccent.c.md | A14; accent-removal dictionary; trie |
| contrib/dict_xsyn/dict_xsyn.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/dict_xsyn/dict_xsyn.c.md | A14; synonym dictionary |
| contrib/dict_int/dict_int.c | 2026-06-09 | 4b0bf0788b0 | read | contrib-remainder-a14 | knowledge/files/contrib/dict_int/dict_int.c.md | A14; integer-truncation dict |
| contrib/pg_trgm/trgm.h | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_trgm/trgm.h.md | A14; HASHVAL=trgm%95 sig-bit map |
| contrib/pg_trgm/trgm_gin.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_trgm/trgm_gin.c.md | A14; GIN opclass; full-scan on empty trigrams |
| contrib/pg_trgm/trgm_gist.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_trgm/trgm_gist.c.md | A14; GiST signature opclass |
| contrib/pg_trgm/trgm_op.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_trgm/trgm_op.c.md | A14; trigram extraction + similarity; show_trgm oracle |
| contrib/pg_trgm/trgm_regexp.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/pg_trgm/trgm_regexp.c.md | A14; zero CFI in regex→NFA pipeline |
| contrib/fuzzystrmatch/fuzzystrmatch.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/fuzzystrmatch/fuzzystrmatch.c.md | A14; soundex / metaphone / levenshtein |
| contrib/fuzzystrmatch/dmetaphone.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/fuzzystrmatch/dmetaphone.c.md | A14; no length cap, no CFI in main loop |
| contrib/fuzzystrmatch/daitch_mokotoff.c | 2026-06-09 | 4b0bf0788b0 | deep-read | contrib-remainder-a14 | knowledge/files/contrib/fuzzystrmatch/daitch_mokotoff.c.md | A14; D-M soundex variant |

<!-- a15-include-finishing 2026-06-09 — foreground sweep #15 (Phase A); 115 header files via 4 parallel general-purpose agents; src/include/utils + storage + lib + executor finishing pass -->
| src/include/utils/acl.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/acl.h.md | A15; utils header |
| src/include/utils/aclchk_internal.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/aclchk_internal.h.md | A15; utils header |
| src/include/utils/array.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/array.md | A15; utils header |
| src/include/utils/arrayaccess.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/arrayaccess.md | A15; utils header |
| src/include/utils/ascii.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/ascii.h.md | A15; utils header |
| src/include/utils/backend_progress.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/backend_progress.md | A15; utils header |
| src/include/utils/backend_status.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/backend_status.md | A15; utils header |
| src/include/utils/builtins.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/builtins.md | A15; utils header |
| src/include/utils/bytea.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/bytea.md | A15; utils header |
| src/include/utils/cash.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/cash.md | A15; utils header |
| src/include/utils/conffiles.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/conffiles.h.md | A15; utils header |
| src/include/utils/datetime.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/datetime.md | A15; utils header |
| src/include/utils/datum.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/datum.md | A15; utils header |
| src/include/utils/dsa.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/dsa.md | A15; utils header |
| src/include/utils/expandeddatum.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/expandeddatum.md | A15; utils header |
| src/include/utils/expandedrecord.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/expandedrecord.md | A15; utils header |
| src/include/utils/float.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/float.md | A15; utils header |
| src/include/utils/fmgrtab.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/fmgrtab.md | A15; utils header |
| src/include/utils/formatting.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/formatting.h.md | A15; utils header |
| src/include/utils/freepage.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/freepage.md | A15; utils header |
| src/include/utils/funccache.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/funccache.md | A15; utils header |
| src/include/utils/geo_decls.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/geo_decls.md | A15; utils header |
| src/include/utils/guc.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/guc.h.md | A15; utils header |
| src/include/utils/guc_hooks.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/guc_hooks.h.md | A15; utils header |
| src/include/utils/guc_tables.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/guc_tables.h.md | A15; utils header |
| src/include/utils/help_config.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/help_config.h.md | A15; utils header |
| src/include/utils/hsearch.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/hsearch.md | A15; utils header |
| src/include/utils/index_selfuncs.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/index_selfuncs.md | A15; utils header |
| src/include/utils/inet.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/inet.md | A15; utils header |
| src/include/utils/injection_point.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/injection_point.h.md | A15; utils header |
| src/include/utils/json.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/json.md | A15; utils header |
| src/include/utils/jsonfuncs.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/jsonfuncs.md | A15; utils header |
| src/include/utils/memdebug.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/memdebug.md | A15; utils header |
| src/include/utils/multirangetypes.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/multirangetypes.md | A15; utils header |
| src/include/utils/numeric.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/numeric.md | A15; utils header |
| src/include/utils/pg_crc.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pg_crc.md | A15; utils header |
| src/include/utils/pg_locale.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pg_locale.h.md | A15; utils header |
| src/include/utils/pg_locale_c.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pg_locale_c.h.md | A15; utils header |
| src/include/utils/pg_lsn.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pg_lsn.md | A15; utils header |
| src/include/utils/pg_rusage.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pg_rusage.md | A15; utils header |
| src/include/utils/pgstat_internal.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pgstat_internal.md | A15; utils header |
| src/include/utils/pgstat_kind.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pgstat_kind.md | A15; utils header |
| src/include/utils/pidfile.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/pidfile.h.md | A15; utils header |
| src/include/utils/portal.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/portal.md | A15; utils header |
| src/include/utils/ps_status.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/ps_status.h.md | A15; utils header |
| src/include/utils/queryenvironment.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/queryenvironment.md | A15; utils header |
| src/include/utils/rangetypes.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/rangetypes.md | A15; utils header |
| src/include/utils/regproc.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/regproc.h.md | A15; utils header |
| src/include/utils/rel.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/rel.md | A15; utils header |
| src/include/utils/relfilenumbermap.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/relfilenumbermap.md | A15; utils header |
| src/include/utils/relmapper.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/relmapper.md | A15; utils header |
| src/include/utils/relptr.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/relptr.md | A15; utils header |
| src/include/utils/reltrigger.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/reltrigger.md | A15; utils header |
| src/include/utils/resowner.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/resowner.md | A15; utils header |
| src/include/utils/rls.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/rls.h.md | A15; utils header |
| src/include/utils/ruleutils.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/ruleutils.md | A15; utils header |
| src/include/utils/sampling.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/sampling.md | A15; utils header |
| src/include/utils/selfuncs.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/selfuncs.md | A15; utils header |
| src/include/utils/sharedtuplestore.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/sharedtuplestore.md | A15; utils header |
| src/include/utils/skipsupport.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/skipsupport.md | A15; utils header |
| src/include/utils/timeout.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/timeout.md | A15; utils header |
| src/include/utils/tzparser.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/tzparser.h.md | A15; utils header |
| src/include/utils/usercontext.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/usercontext.h.md | A15; utils header |
| src/include/utils/uuid.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/uuid.md | A15; utils header |
| src/include/utils/varbit.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/varbit.md | A15; utils header |
| src/include/utils/varlena.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/varlena.md | A15; utils header |
| src/include/utils/wait_classes.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/wait_classes.md | A15; utils header |
| src/include/utils/wait_event.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/wait_event.md | A15; utils header |
| src/include/utils/xid8.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/xid8.md | A15; utils header |
| src/include/utils/xml.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-1 | knowledge/files/src/include/utils/xml.md | A15; utils header |
| src/include/storage/block.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/block.h.md | A15; storage core header |
| src/include/storage/buf.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/buf.h.md | A15; storage core header |
| src/include/storage/bufmgr.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/bufmgr.h.md | A15; storage core header |
| src/include/storage/condition_variable.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/condition_variable.h.md | A15; storage core header |
| src/include/storage/indexfsm.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/indexfsm.h.md | A15; storage core header |
| src/include/storage/io_worker.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/io_worker.h.md | A15; storage core header |
| src/include/storage/itemid.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/itemid.h.md | A15; storage core header |
| src/include/storage/large_object.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/large_object.h.md | A15; storage core header |
| src/include/storage/lmgr.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/lmgr.h.md | A15; storage core header |
| src/include/storage/lockdefs.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/lockdefs.h.md | A15; storage core header |
| src/include/storage/locktag.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/locktag.h.md | A15; storage core header |
| src/include/storage/lwlocklist.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/lwlocklist.h.md | A15; storage core header |
| src/include/storage/off.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/off.h.md | A15; storage core header |
| src/include/storage/pg_sema.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/pg_sema.h.md | A15; storage core header |
| src/include/storage/pg_shmem.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/pg_shmem.h.md | A15; storage core header |
| src/include/storage/predicate.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/predicate.h.md | A15; storage core header |
| src/include/storage/predicate_internals.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/predicate_internals.h.md | A15; storage core header |
| src/include/storage/procnumber.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/procnumber.h.md | A15; storage core header |
| src/include/storage/read_stream.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/read_stream.h.md | A15; storage core header |
| src/include/storage/relfilelocator.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/relfilelocator.h.md | A15; storage core header |
| src/include/storage/s_lock.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/s_lock.h.md | A15; storage core header |
| src/include/storage/spin.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/storage/spin.h.md | A15; storage core header |
| src/include/lib/binaryheap.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/binaryheap.h.md | A15; lib data structure header |
| src/include/lib/bipartite_match.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/bipartite_match.h.md | A15; lib data structure header |
| src/include/lib/bloomfilter.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/bloomfilter.h.md | A15; lib data structure header |
| src/include/lib/dshash.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/dshash.h.md | A15; lib data structure header |
| src/include/lib/hyperloglog.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/hyperloglog.h.md | A15; lib data structure header |
| src/include/lib/ilist.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/ilist.h.md | A15; lib data structure header |
| src/include/lib/integerset.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/integerset.h.md | A15; lib data structure header |
| src/include/lib/knapsack.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/knapsack.h.md | A15; lib data structure header |
| src/include/lib/pairingheap.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/pairingheap.h.md | A15; lib data structure header |
| src/include/lib/qunique.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/qunique.h.md | A15; lib data structure header |
| src/include/lib/radixtree.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/radixtree.h.md | A15; lib data structure header |
| src/include/lib/rbtree.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/rbtree.h.md | A15; lib data structure header |
| src/include/lib/simplehash.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/simplehash.h.md | A15; lib data structure header |
| src/include/lib/sort_template.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/sort_template.h.md | A15; lib data structure header |
| src/include/lib/stringinfo.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-4 | knowledge/files/src/include/lib/stringinfo.h.md | A15; lib data structure header |
| src/include/executor/execAsync.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/execAsync.md | A15; executor support header |
| src/include/executor/execParallel.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/execParallel.md | A15; executor support header |
| src/include/executor/execScan.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/execScan.md | A15; executor support header |
| src/include/executor/execdebug.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/execdebug.md | A15; executor support header |
| src/include/executor/hashjoin.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/hashjoin.md | A15; executor support header |
| src/include/executor/instrument_node.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/instrument_node.md | A15; executor support header |
| src/include/executor/spi.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/spi.md | A15; executor support header |
| src/include/executor/tqueue.h | 2026-06-09 | 4b0bf0788b0 | deep-read | include-finishing-a15-3 | knowledge/files/src/include/executor/tqueue.md | A15; executor support header |
| src/backend/access/rmgrdesc/nbtdesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/nbtdesc.c.md | rmgrdesc cloud sweep; 15 btree opcodes; delvacuum_desc packed offset+update array decode |
| src/backend/access/rmgrdesc/gindesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/gindesc.c.md | rmgrdesc cloud sweep; recompress segment stream; inverted !HasBlockImage FPI guard |
| src/backend/access/rmgrdesc/gistdesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/gistdesc.c.md | rmgrdesc cloud sweep; 5 opcodes; empty out_gistxlogPageUpdate (ISSUE) |
| src/backend/access/rmgrdesc/hashdesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/hashdesc.c.md | rmgrdesc cloud sweep; SPLIT_PAGE/SPLIT_CLEANUP no desc case (ISSUE); double tuple counts |
| src/backend/access/rmgrdesc/spgdesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/spgdesc.c.md | rmgrdesc cloud sweep; 8 SP-GiST opcodes; parenthetical flag suffixes |
| src/backend/access/rmgrdesc/brindesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/brindesc.c.md | rmgrdesc cloud sweep; XLOG_BRIN_OPMASK strips init-bit in desc, kept in identify |
| src/backend/access/rmgrdesc/mxactdesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/mxactdesc.c.md | rmgrdesc cloud sweep; out_member status decode; 64-bit pageno/offset |
| src/backend/access/rmgrdesc/committsdesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/committsdesc.c.md | rmgrdesc cloud sweep; zeropage/truncate; identify on unmasked info (ISSUE) |
| src/backend/access/rmgrdesc/dbasedesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/dbasedesc.c.md | rmgrdesc cloud sweep; CREATE file-copy vs wal-log strategies; multi-tablespace drop |
| src/backend/access/rmgrdesc/genericdesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/genericdesc.c.md | rmgrdesc cloud sweep; self-delimiting (offset,length,payload) delta stream; constant identify |
| src/backend/access/rmgrdesc/logicalmsgdesc.c | 2026-06-09 | 4b0bf0788b0 | deep | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/logicalmsgdesc.c.md | rmgrdesc cloud sweep; user-controlled prefix raw %s (ISSUE); hex payload dump |
| src/backend/access/rmgrdesc/relmapdesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/relmapdesc.c.md | rmgrdesc cloud sweep; single RELMAP_UPDATE opcode; dbid 0 = shared map |
| src/backend/access/rmgrdesc/replorigindesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/replorigindesc.c.md | rmgrdesc cloud sweep; SET/DROP; LSN_FORMAT_ARGS; identify on unmasked info |
| src/backend/access/rmgrdesc/seqdesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/seqdesc.c.md | rmgrdesc cloud sweep; single SEQ_LOG opcode; relation locator render |
| src/backend/access/rmgrdesc/smgrdesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/smgrdesc.c.md | rmgrdesc cloud sweep; CREATE/TRUNCATE; relpathperm().str by-value idiom |
| src/backend/access/rmgrdesc/tblspcdesc.c | 2026-06-09 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/backend/access/rmgrdesc/tblspcdesc.c.md | rmgrdesc cloud sweep; CREATE (symlink path) / DROP |
| src/include/executor/nodeBitmapAnd.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeBitmapAnd.h.md | exec-headers cloud sweep; MultiExec-returning (TIDBitmap), AND combinator |
| src/include/executor/nodeBitmapOr.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeBitmapOr.h.md | exec-headers cloud sweep; MultiExec OR combinator |
| src/include/executor/nodeBitmapIndexscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeBitmapIndexscan.h.md | exec-headers cloud sweep; leaf TIDBitmap producer; shares ExecIndexBuildScanKeys |
| src/include/executor/nodeBitmapHeapscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeBitmapHeapscan.h.md | exec-headers cloud sweep; bitmap consumer; full parallel-aware + instrument quartets |
| src/include/executor/nodeSeqscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeSeqscan.h.md | exec-headers cloud sweep; canonical scan template; two parallel quartets |
| src/include/executor/nodeSamplescan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeSamplescan.h.md | exec-headers cloud sweep; TABLESAMPLE; no parallel |
| src/include/executor/nodeIndexonlyscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeIndexonlyscan.h.md | exec-headers cloud sweep; VM-gated; mark/restore + full parallel |
| src/include/executor/nodeTidscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeTidscan.h.md | exec-headers cloud sweep; ctid= / CURRENT OF; no parallel |
| src/include/executor/nodeTidrangescan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeTidrangescan.h.md | exec-headers cloud sweep; ctid range; parallel-aware (vs point tidscan) |
| src/include/executor/nodeForeignscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeForeignscan.h.md | exec-headers cloud sweep; FDW shell; async trio + Shutdown |
| src/include/executor/nodeCustom.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeCustom.h.md | exec-headers cloud sweep; CustomScan extension ABI; mark/restore + parallel |
| src/include/executor/nodeFunctionscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeFunctionscan.h.md | exec-headers cloud sweep; SRF in FROM; tuplestore-owning ExecEnd |
| src/include/executor/nodeValuesscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeValuesscan.h.md | exec-headers cloud sweep; VALUES; NO ExecEnd (execProcnode.c:734) |
| src/include/executor/nodeCtescan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeCtescan.h.md | exec-headers cloud sweep; non-recursive WITH reader; shared tuplestore |
| src/include/executor/nodeWorktablescan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeWorktablescan.h.md | exec-headers cloud sweep; recursive working table; NO ExecEnd |
| src/include/executor/nodeNamedtuplestorescan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeNamedtuplestorescan.h.md | exec-headers cloud sweep; trigger transition tables; NO ExecEnd |
| src/include/executor/nodeSubqueryscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeSubqueryscan.h.md | exec-headers cloud sweep; un-pulled-up FROM subquery shell |
| src/include/executor/nodeTableFuncscan.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeTableFuncscan.h.md | exec-headers cloud sweep; XMLTABLE/JSON_TABLE via TableFuncRoutine |
| src/include/executor/nodeNestloop.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeNestloop.h.md | exec-headers cloud sweep; reference join template; nestParams |
| src/include/executor/nodeMaterial.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeMaterial.h.md | exec-headers cloud sweep; canonical mark/restore; tuplestore buffer |
| src/include/executor/nodeIncrementalSort.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeIncrementalSort.h.md | exec-headers cloud sweep; prefix-group sort; instrumentation-only DSM; no mark/restore |
| src/include/executor/nodeMemoize.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeMemoize.h.md | exec-headers cloud sweep; param-cache; public planner helper ExecEstimateCacheEntryOverheadBytes |
| src/include/executor/nodeGroup.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeGroup.h.md | exec-headers cloud sweep; sorted GROUP BY (no aggregates) |
| src/include/executor/nodeUnique.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeUnique.h.md | exec-headers cloud sweep; sorted DISTINCT; adjacent dedup |
| src/include/executor/nodeSetOp.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeSetOp.h.md | exec-headers cloud sweep; INTERSECT/EXCEPT; public EstimateSetOpHashTableSpace |
| src/include/executor/nodeRecursiveunion.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeRecursiveunion.h.md | exec-headers cloud sweep; WITH RECURSIVE engine; owns working table |
| src/include/executor/nodeMergeAppend.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeMergeAppend.h.md | exec-headers cloud sweep; order-preserving heap merge; partitioned ordered scans |
| src/include/executor/nodeGather.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeGather.h.md | exec-headers cloud sweep; parallel leader (unordered); ExecShutdownGather |
| src/include/executor/nodeGatherMerge.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeGatherMerge.h.md | exec-headers cloud sweep; order-preserving parallel leader |
| src/include/executor/nodeResult.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeResult.h.md | exec-headers cloud sweep; projection/one-time-qual gate; pass-through mark/restore |
| src/include/executor/nodeProjectSet.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeProjectSet.h.md | exec-headers cloud sweep; SRF in target list (post-PG10) |
| src/include/executor/nodeLimit.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeLimit.h.md | exec-headers cloud sweep; LIMIT/OFFSET/WITH TIES; drives child shutdown |
| src/include/executor/nodeLockRows.h | 2026-06-10 | 4b0bf0788b0 | read | pg-file-backfiller | knowledge/files/src/include/executor/nodeLockRows.h.md | exec-headers cloud sweep; SELECT FOR UPDATE/SHARE; EvalPlanQual site |
