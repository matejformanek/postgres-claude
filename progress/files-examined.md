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
