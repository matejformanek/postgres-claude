# PostgreSQL internals glossary

Distilled terms for the pg-claude corpus. Grown mechanically by the
`pg-corpus-maintainer` cloud routine (recipe:
`.claude/cloud/pg-corpus-maintainer.md`, Pass 2).

**Provenance.** Each entry is distilled from an existing per-file or long-form
corpus doc (named after "— via"), which carries the underlying `file:line`
verification against `source/` at the corpus's last-verified commit
(`ef6a95c7c64`, 2026-06-01). `file:line` refs are into `source/...` and stay
stable across upstream pulls. Confidence tags follow CLAUDE.md.

Entries are alphabetical (case-insensitive). One `### <term>` heading per term
so future runs can detect what's already defined and append idempotently.

<!-- glossary:auto -->


### _bt_check_unique
The nbtree routine (`nbtinsert.c`) that enforces a unique constraint at insert time by scanning for a live duplicate; it can wait on an in-progress inserter (`UNIQUE_CHECK_INSERT_INPROGRESS`) and is the sole implementation behind `amcanunique`. [verified-by-code] (via `knowledge/subsystems/access-nbtree.md`).



### _bt_compare
The nbtree key-comparison primitive comparing a scan/insertion key against an index tuple on a page; binary search within a page and downlink choice both call it. [verified-by-code] (`nbtsearch.c` — via `knowledge/files/src/backend/access/nbtree/nbtsearch.c.md`).



### _bt_findsplitloc
The nbtree page-split-point chooser (`nbtsplitloc.c`): a multi-objective heuristic balancing byte distribution across the two halves, suffix-truncation depth, duplicate-run avoidance, the single-value split strategy, and applying fillfactor only on the rightmost page. [verified-by-code] (via `knowledge/subsystems/access-nbtree.md`).



### _bt_finish_split
The nbtree routine (`nbtinsert.c`) that completes an incomplete page split (marked `BTP_INCOMPLETE_SPLIT`) by inserting the missing downlink into the parent; a second inserter encountering the flag must finish the split before proceeding. [verified-by-code] (via `knowledge/subsystems/access-nbtree.md`).



### _bt_first
The nbtree routine that positions a scan at the first matching tuple: it descends the tree using the preprocessed scan keys and returns the first qualifying item, after which `_bt_next` walks the leaf level. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtree.c.md`).



### _bt_getstackbuf
The nbtree helper that, when a cached parent buffer on the insertion stack turns out to have itself split, walks right along the parent level until it finds the page now holding the relevant downlink. [verified-by-code] (via `knowledge/subsystems/access-nbtree.md`).



### _bt_killitems
The nbtree optimisation that marks index tuples LP_DEAD when a scan has proven the referenced heap tuples are dead, letting later scans and `_bt_vacuum_one_page` skip or reclaim them without a full VACUUM. [verified-by-code] (`nbtutils.c` — via `knowledge/files/src/backend/access/nbtree/nbtutils.c.md`).



### _bt_moveright
The Lehman-&-Yao right-walk in nbtree (`nbtsearch.c`) — when a descent lands on a page that a concurrent split has narrowed, it follows the right-link until the target key is in range, the mechanism that lets nbtree search without holding locks down the tree. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtsearch.c.md`).



### _bt_pagedel
The nbtree page-deletion routine that removes an empty leaf (and unlinks its parent downlink) during VACUUM, leaving the page recyclable once no scan could still need it. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtree.c.md`).



### _bt_search
The nbtree routine that descends from the root to the leaf page where a given key belongs and returns that buffer; amcheck's `bt_rootdescend` drives it from the root to verify every leaf tuple is still re-findable through the tree. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### _bt_split
The nbtree leaf/internal page-split routine: when an insert won't fit, it chooses a split point (`_bt_findsplitloc`), moves the right half to a new page, and rewires sibling links; SSI's `PredicateLockPageSplit` fires right after it so the split is visible atomically. [verified-by-code] (`nbtinsert.c:1234` — via `knowledge/files/src/backend/access/nbtree/nbtinsert.c.md`).



### _dosmaperr
The Windows port helper that translates a Win32 `GetLastError()` code into the nearest POSIX `errno`, letting the `src/port` shims present a Unix-like error interface to the rest of the backend. [verified-by-code] (`win32pread.c:42` — via `knowledge/files/src/port/win32pread.c.md`).



### _fsm
The filename suffix of a relation's free-space-map fork (e.g. `<relfilenode>_fsm`); the FSM is a separate per-relation fork tracking approximate free space per page, updated after heap redo via `RecordPageWithFreeSpace` when a page's free space changes materially. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_xlog.c.md`).



### _hash_doinsert
The hash-index per-row insert path (`hashinsert.c`) — hashes the key to a bucket, takes the bucket's lock, and adds the index tuple, opportunistically clearing LP_DEAD items via `_hash_vacuum_one_page` and triggering a split when the fill factor is exceeded. [from-comment] (via `knowledge/files/src/backend/access/hash/hashinsert.c.md`).



### _hash_expandtable
The hash-index split engine (`hashpage.c`) — decides whether to grow the table, picks which bucket to split, and performs the cleanup-lock dance before `_hash_splitbucket` redistributes tuples. Hash grows one bucket at a time, not by doubling. [from-comment] (via `knowledge/files/src/backend/access/hash/hashpage.c.md`).



### _hash_finish_split
The hash-AM routine (`hashpage.c`) that completes a bucket split left incomplete by a crash or concurrent aborter, moving any still-old-bucket tuples into the new bucket before the index is used further. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### _hash_splitbucket
The hash-AM routine (`hashpage.c`) that performs a bucket split: it scans the old bucket, re-hashes each tuple against the new mask, and relocates those that now belong to the new bucket. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### _PG_init
The conventional entry-point symbol a loadable backend module exports; the backend calls it exactly once per backend that loads the library — at `shared_preload_libraries` time for preloaded modules, or at first `LOAD` / `CREATE EXTENSION` use otherwise — to define GUCs, install hooks, and request shared memory. [from-comment] (`pgcrypto.c:67-83` — via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### _PG_jit_provider_init
The symbol a JIT provider shared library must export; after `dlopen` the core calls `load_external_function(path, "_PG_jit_provider_init", …)` and invokes it to populate a `JitProviderCallbacks` struct. Signature `void _PG_jit_provider_init(JitProviderCallbacks *cb)`. [verified-by-code] (`jit.c:112`, `jit.h:67` — via `knowledge/docs-distilled/jit-extensibility.md`).



### _PG_output_plugin_init
The required entry-point symbol every logical-decoding output plugin exports; `logical.c` locates it by name after loading the plugin's shared library and calls it with an `OutputPluginCallbacks *` so the plugin can fill in its `startup` / `begin` / `change` / `commit` / ... callback vtable. [verified-by-code] (`logical.c:52` — via `knowledge/files/src/backend/replication/logical/logical.c.md`).



### _vm
The filename suffix of a relation's visibility-map fork (e.g. `12345_vm`): a bitmap with two bits per heap page (`VISIBILITYMAP_ALL_VISIBLE`, `VISIBILITYMAP_ALL_FROZEN`) that enables index-only scans and lets VACUUM skip all-frozen pages. [from-docs] (via `knowledge/docs-distilled/storage-vm.md`).



### AbortCurrentTransaction
The transaction-manager entry point (`xact.c:3501`) that aborts the current transaction; it is reached either through `PG_CATCH` after an `ereport(ERROR)` longjmp, or by an explicit call from high-level loops such as the postmaster/main loop after catching an error. [verified-by-code] (`xact.c` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### AbortSubTransaction
The subtransaction counterpart of `AbortTransaction`: it rolls back the current subtransaction's effects — releasing its locks, buffers, and queued invalidations — during `RollbackToSavepoint` or error propagation caught inside a savepoint. [verified-by-code] (via `knowledge/idioms/abort-transaction-cleanup.md`).



### AbortTransaction
The transaction-manager routine that rolls back the current top-level
transaction — releasing locks and buffer pins via resource owners, running
abort callbacks, and discarding the transaction's memory — reached on any
`ERROR` longjmp. [verified-by-code] (via
`knowledge/subsystems/access-transam.md`).



### AcceptInvalidationMessages
The routine that drains and applies pending shared-invalidation (sinval)
messages, flushing stale relcache/catcache entries; it runs at every lock
acquisition so a backend always sees catalog changes committed before it took
the lock. [from-comment] (`inval.c:30` — via
`knowledge/files/src/backend/utils/cache/inval.c.md`).



### AccessExclusiveLock
The strongest table-level lock mode; it conflicts with every other mode,
including itself, so only one holder exists at a time and no concurrent reader
or writer proceeds. DDL such as `DROP TABLE`, `TRUNCATE`, and most `ALTER TABLE`
forms take it, and `heap_create_with_catalog` grabs it on a new relid the
instant the OID is assigned — before any catalog row is inserted — so other
backends never observe a half-built relation. [verified-by-code]
(`heap.c:1293` — via `knowledge/files/src/backend/catalog/heap.c.md`).



### AccessShareLock
The weakest table-level lock mode, acquired by a plain `SELECT` for the
duration it reads a relation. It conflicts only with `AccessExclusiveLock`, so
ordinary reads and writes coexist freely; the conflict table lives in the lock
manager's method table. [verified-by-code]
(via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### ACL
PostgreSQL's privilege representation: an `Acl` is a variable-length array of `AclItem` entries (grantee, grantor, privilege bitmask) attached to a catalog object's `aclitem[]` column. `aclchk.c` evaluates `GRANT`/`REVOKE`, merges and checks these items, and is the choke point for `pg_*_aclcheck` permission tests. [verified-by-code] (via `knowledge/files/src/backend/catalog/aclchk.c.md`).



### ACL_ALL_RIGHTS_RELATION
The bitmask enumerating every privilege applicable to a table/relation — SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER plus MAINTAIN — used when expanding a NULL `relacl` to the owner's default full set. [verified-by-code] (`acl.h:160` — via `knowledge/docs-distilled/ddl-priv.md`).



### ACL_MAINTAIN_CHR
The single-character abbreviation `'m'` for the MAINTAIN privilege (VACUUM/ANALYZE/CLUSTER/REINDEX/REFRESH/LOCK) in the compact `aclitem` text form; MAINTAIN is the newest privilege bit. [verified-by-code] (`acl.h:151` — via `knowledge/docs-distilled/ddl-priv.md`).



### ACL_SELECT
The privilege bit for `SELECT` within an `AclItem` privilege mask; the `ACL_*` family enumerates the grantable privileges that `pg_class_aclcheck` and friends test. [verified-by-code] (via `knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md`).



### AclItem
The fixed struct `{ ai_grantee, ai_privs, ai_grantor }` that is one element of an `aclitem[]` array — one grantee's privilege bitmask plus the grantor who conferred it. [verified-by-code] (`acl.h:54` — via `knowledge/docs-distilled/ddl-priv.md`).



### acquire_sample_rows
The ANALYZE callback (`analyze.c`) that reads a random sample of up to `targrows` rows from a relation using Vitter reservoir sampling over randomly chosen blocks; its output feeds the per-column `compute_stats` routines. [verified-by-code] (via `knowledge/idioms/analyze-block-and-reservoir-sampling.md`).



### AcquireRewriteLocks
The rewriter routine that re-takes the same locks the parser took on every
relation in a query's range table, before rules are applied — needed because a
cached/stored query tree is re-used across invocations and the locks must be
freshly held each time. [from-comment] (`rewriteHandler.c:148` — via
`knowledge/files/src/backend/parser/parse_relation.c.md`).



### active_count
Snapshot refcount field counting how many `ActiveSnapshotElt` stack entries reference the snapshot; `PushActiveSnapshot` bumps it (copying static/unregistered snapshots first), and when it and `regd_count` both hit zero the snapshot is freed. [verified-by-code] (`snapmgr.c` — via `knowledge/idioms/snapshot-active-stack-and-registered.md`).



### ActivePortal
Backend global naming the innermost currently-executing portal; it is saved and restored around every nested portal execution so re-entrant SPI/utility execution restores the correct portal context on return. [verified-by-code] (`pquery.c:36` — via `knowledge/subsystems/tcop.md`).



### ActiveSnapshot
The top of the backend's active-snapshot stack — the snapshot that "the current
command" sees, managed by `PushActiveSnapshot` / `PopActiveSnapshot` /
`GetActiveSnapshot`. The snapshot manager tracks this stack (plus the
registered-snapshot heap) and uses the oldest of them to advance or hold back
`MyProc->xmin`. [from-comment] (`snapmgr.c:1-104` — via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### ActiveSnapshotElt
A node in the backend's active-snapshot stack; each element pins one snapshot
that bounds visibility for the currently executing portion of a query, pushed by
`PushActiveSnapshot` and popped in LIFO order. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### add_path
The optimizer routine that submits a candidate `Path` to a `RelOptInfo`'s
pathlist, immediately pruning it by cost/pathkey/parameterization dominance: a
new path is kept only if nothing already there dominates it, and it evicts any
existing path it dominates. This add-and-prune discipline is what keeps the
path space from exploding during join enumeration. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/util/pathnode.c.md`).



### add_paths_to_joinrel
Adds join paths (`joinpath.c`) to a join `RelOptInfo` for one pair of input rels — enumerates nestloop, mergejoin, and hashjoin variants in both join orders, subject to outer-join and semi/anti-join legality. Called from `make_join_rel`. [from-comment] (via `knowledge/files/src/backend/optimizer/path/joinrels.c.md`).



### addforeignupdatetargets
The FDW callback that adds the row-identity junk columns (e.g. a remote `ctid` or key) an `UPDATE` / `DELETE` needs to locate the target row on the remote side. [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### admin_option
The per-membership boolean in `pg_auth_members` (default false) granting the right to further grant that role membership to others — the ADMIN axis, independent of the INHERIT and SET axes. [verified-by-code] (`pg_auth_members.h:47` — via `knowledge/docs-distilled/role-membership.md`).



### AdvanceXLInsertBuffer
WAL routine that makes a fresh in-memory xlog insertion buffer available for a new page: it initialises the page header and, if the slot must be reused, writes out (or waits for) the oldest buffered page first. [verified-by-code] (via `knowledge/idioms/wal-buffer-state.md`).



### AfterTriggerEndSubXact
Fires at subtransaction end (both commit and abort branches) to release or roll back the after-trigger event queue state captured at the matching AfterTriggerBeginSubXact. [verified-by-code] (via `knowledge/idioms/trigger-during-error.md`).



### AfterTriggerEndXact
The routine that fires (or discards) all remaining deferred AFTER-trigger events
at transaction end and frees the after-trigger event queue; it runs as part of
commit/abort cleanup. [verified-by-code] (via
`knowledge/idioms/prepare-transaction-2pc.md`).



### AfterTriggerFireDeferred
Fires the queued deferred (CONSTRAINT) AFTER-trigger events at the end of the
transaction (or at `SET CONSTRAINTS ... IMMEDIATE`), draining the after-trigger
event list in order. [verified-by-code] (via
`knowledge/idioms/prepare-transaction-2pc.md`).



### afterTriggers
The backend-global state holding the deferred (AFTER) trigger event queue, structured as a stack of per-(sub)transaction frames (`trans_stack[]`) so each subtransaction's pending events can be committed or rolled back independently. RI foreign-key checks ride this same queue as AFTER triggers. [verified-by-code] (via `knowledge/idioms/trigger-during-error.md`).



### AfterTriggersTableData
The per-table transition-capture record that hangs off the after-trigger
event state; its `tcs_insert_private` / `tcs_update_private` tuplestores
accumulate OLD/NEW rows for `REFERENCING ... TABLE` transition tables so a
statement-level trigger can scan them after the statement completes.
[verified-by-code] (via `knowledge/idioms/trigger-transition-tables.md`).



### AGG_HASHED
One of `nodeAgg.c`'s four aggregation strategies: build a hash table keyed by the GROUP BY columns where each entry stores the running trans-state, then emit results by iterating the table after input is exhausted. Used for unsorted input; since PG 13 it can spill to disk when the hash table outgrows `hash_mem` (writing new groups to partitioned LogicalTapes) rather than erroring as pre-13 did. [from-comment] (`aggregate-hash-vs-sort.md` — via `knowledge/idioms/aggregate-hash-vs-sort.md`).



### AGG_MIXED
One of `nodeAgg.c`'s four aggregation strategies, used for `GROUPING SETS` where some sets are best handled by hashing and others by sorting. The "real" Agg node is marked AGG_MIXED, with additional sorted phases described by chained nodes; the chain must be ordered so hashed entries come before sorted/plain entries. [from-comment] (`aggregate-hash-vs-sort.md` — via `knowledge/idioms/aggregate-hash-vs-sort.md`).



### AGG_PLAIN
The AggStrategy for a plain aggregate — a single group computed over all input rows, with no GROUP BY hashing or sorting (as opposed to AGG_SORTED / AGG_HASHED / AGG_MIXED). [verified-by-code] (via `knowledge/files/src/backend/executor/nodeAgg.c.md`).



### AGG_SORTED
One of `nodeAgg.c`'s four aggregation strategies, used when the input is already sorted on the GROUP BY columns (planner placed a Sort below, or the input is naturally ordered). It streams one group at a time in O(1) memory: read a tuple, compare GROUP BY columns to the previous; if the same group advance the trans-state, else emit the result and reset. `AGG_PLAIN` is essentially AGG_SORTED with a single group. [from-comment] (`aggregate-hash-vs-sort.md` — via `knowledge/idioms/aggregate-hash-vs-sort.md`).



### AggCheckCallContext
An fmgr helper a function calls to discover whether it is being invoked as an aggregate transition/final function; it returns 0 (not in aggregate context), 1 (aggregate), or 2 (window), and optionally outputs the long-lived aggregate-state memory context. A transition function may safely mutate its state argument in place only when this returns nonzero; expanded-object states should be allocated in a child of the returned context. [verified-by-code] (`fmgr.h` — via `knowledge/docs-distilled/xaggr.md`).



### Aggref
The parse/plan node representing one aggregate-function call (e.g. `sum(x)`); the parser emits it when a `FuncCall` name resolves to an aggregate rather than an ordinary function, and the planner/executor route it through the Agg node's transition/final machinery. [verified-by-code] (via `knowledge/docs-distilled/parser-stage.md`).



### AggSplit
A bitmask describing how an aggregate is split across partial and final stages (`AGGSPLIT_SIMPLE`, `AGGSPLIT_INITIAL_SERIAL`, `AGGSPLIT_FINAL_DESERIAL`) for partial and parallel aggregation. [verified-by-code] (via `knowledge/files/src/include/nodes/nodes.h.md`).



### AGGSPLIT_FINAL_DESERIAL
The AggSplit mode (AGGSPLITOP_COMBINE | AGGSPLITOP_DESERIALIZE) for the final stage of a split aggregate: it deserializes worker-produced transition values and then combines them, so the combine function receives trans-values rather than raw inputs. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeAgg.c.md`).



### AGGSPLIT_INITIAL_SERIAL
The aggregate-split mode for the first (partial) stage that additionally serializes the transition values, so they can be transmitted to a later finalizing/combining stage. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeAgg.c.md`).



### AGGSPLIT_SIMPLE
The `aggsplit` mode denoting a normal, non-split aggregation: the transition function runs and the final function is applied in the same node, with no partial/serialize handling. It contrasts with split modes such as `AGGSPLIT_INITIAL_SERIAL` (the lower, partial half that runs transfunc, skips finalfunc, and serializes). [verified-by-code] (`nodeAgg.c` — via `knowledge/files/src/backend/executor/nodeAgg.c.md`).



### AggState
The executor run-state node for an Aggregate plan node, holding the per-group
transition values, the `ExprContext`s used for transition/final evaluation, and
(for hashed aggregation) the in-memory hash tables. `ExecAgg` drives it,
switching between sorted and hashed grouping strategies. [verified-by-code] (via
`knowledge/data-structures/exprcontext.md`).



### ai_grantee
The `AclItem` field naming the role that receives the privileges (a role OID; zero denotes PUBLIC). [verified-by-code] (`acl.h:56-57` — via `knowledge/docs-distilled/ddl-priv.md`).



### ai_grantor
The `AclItem` field naming the role that granted the privileges, retained so that revoking a grant option can cascade down that grantor's grant chain. [verified-by-code] (`acl.h:56-57` — via `knowledge/docs-distilled/ddl-priv.md`).



### ai_privs
The `AclItem` field holding the privilege bitmask — low bits are the granted privileges, high bits the matching WITH GRANT OPTION flags. [verified-by-code] (`acl.h:56-57` — via `knowledge/docs-distilled/ddl-priv.md`).



### AIO
Asynchronous I/O subsystem (PG 18) that lets a backend submit read requests and continue work while the kernel (or a dedicated io_worker) services them. Buffer reads route through the AIO machinery via `StartReadBuffer`/`WaitReadBuffers`, with `io_method` selecting the worker, io_uring, or synchronous fallback path. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### aio_internal
The private header (`src/include/storage/aio_internal.h`) behind PostgreSQL's async-I/O subsystem: it declares the `PgAioHandle` struct, the per-handle state fields, and the I/O state machine that `aio.c` drives. Callers outside the AIO core see only the public `aio.h` surface; the internal header is where the submitted / in-flight / completed transitions and handle-slot bookkeeping live. [inferred] (`aio_internal.h` — via `knowledge/files/src/include/storage/aio_internal.h.md`).



### ALL_FROZEN
The second visibility-map bit: set when every tuple on a heap page is also
frozen, so anti-wraparound VACUUM can skip the page entirely; it implies
`ALL_VISIBLE`. [from-comment] (`visibilitymap.c:1-95` — via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### ALL_VISIBLE
One of the two visibility-map bits (2 bits per heap page): set when every
tuple on the page is visible to all transactions, letting scans skip
visibility checks and index-only scans avoid heap fetches. [from-comment]
(`visibilitymap.c:1-95` — via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### allequalimage
The opclass property (verified by `_bt_allequalimage`) asserting that, for every type in the index, equal values have byte-identical representations — the precondition that lets nbtree apply deduplication safely. [verified-by-code] (`nbtutils.c` — via `knowledge/files/src/backend/access/nbtree/nbtutils.c.md`).



### ALLOC_CHUNK_LIMIT
The AllocSet threshold above which an allocation request is treated as a "large" chunk given its own dedicated block, instead of being served from a power-of-two size-class free list. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### ALLOC_MINBITS
In the AllocSet allocator, the base-2 log of the smallest chunk size (8 bytes); chunk size classes are powers of two from `1 << ALLOC_MINBITS` up to `ALLOC_CHUNK_LIMIT`. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocateDir
The fd-manager-tracked `opendir` wrapper: it returns a DIR* whose descriptor counts against the backend's fd budget and is closed automatically at transaction abort, the directory analogue of `AllocateFile`. [verified-by-code] (`fd.c` — via `knowledge/files/src/backend/storage/file/fd.c.md`).



### AllocateFile
The fd.c stdio wrapper (fopen-style) that registers an open file with the virtual-file-descriptor machinery so the kernel fd can be transiently evicted under pressure; backend code that calls `fopen(3)` directly is buggy because it bypasses VFD eviction. [from-comment] (via `knowledge/files/src/backend/storage/file/fd.c.md`).



### allocChunkLimit
The `AllocSet` threshold above which a requested chunk is given its own dedicated block (a "large" allocation) instead of being carved from a shared block and bucketed by free-list size class. [verified-by-code] (`aset.c:516-519` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocSet
The default `MemoryContext` implementation (`AllocSetContext`). It amortizes
many small `palloc`s by carving them out of a few larger `malloc`'d blocks,
keeps a per-size free list for reuse, and frees every block at once on
`AllocSetReset`/`MemoryContextDelete`. It is the right choice unless a
specialized type (Slab, Generation, Bump) fits the allocation pattern better.
[from-comment] (`aset.c:16-43` — via
`knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### ALLOCSET_DEFAULT_SIZES
The standard `(minContextSize, initBlockSize, maxBlockSize)` triple passed to `AllocSetContextCreate` for general-purpose contexts; it starts blocks at 8 KB and doubles up to 8 MB, the AllocSet default growth profile. [verified-by-code] (`aset.c:432` — via `knowledge/subsystems/utils-mmgr.md`).



### ALLOCSET_SMALL_SIZES
A compact size triple for `AllocSetContextCreate` used by contexts expected to stay tiny (e.g. short-lived per-call state); it starts with smaller blocks than `ALLOCSET_DEFAULT_SIZES` to avoid wasting a full 8 KB on contexts that rarely grow. [inferred] (via `knowledge/idioms/memory-context-allocset-internals.md`).



### AllocSetAlloc
The core allocator of the AllocSet memory-context type: small requests are carved from power-of-two freelists within a block, while requests above the chunk limit become dedicated blocks; it is the function behind most `palloc` calls. [verified-by-code] (`aset.c` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocSetAllocLarge
The AllocSet oversized-allocation path: a request larger than `allocChunkLimit` gets its own dedicated block rather than a free-list chunk, so it can be `pfree`d back to the OS individually instead of being retained in the context. [verified-by-code] (`aset.c` — via `knowledge/idioms/memory-context-allocset-internals.md`).



### AllocSetContext
The default general-purpose memory-context allocator (the "aset") that manages
power-of-two free lists and grows by malloc'd blocks; it extends
`MemoryContextData` with block and freelist bookkeeping. [verified-by-code]
(`aset.c:158-171` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocSetContextCreate
The constructor for the default `AllocSet` memory-context type, returning a new
child `MemoryContext` under a named parent with min/init/max block-size
parameters (commonly the `ALLOCSET_DEFAULT_SIZES` triple). It is the
overwhelmingly common context to create for per-query and per-tuple scratch
space. [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### AllocSetContextCreateInternal
The real constructor behind the `AllocSetContextCreate` macro: it allocates and initializes an AllocSet (the default general-purpose) memory context under a parent, taking minContextSize / initBlockSize / maxBlockSize to size its block growth. [verified-by-code] (`aset.c` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocSetFree
The AllocSet reclaim path that returns a chunk to its size-class freelist (or frees the whole block for oversized/dedicated chunks); it is what `pfree` dispatches to for AllocSet-backed contexts. [verified-by-code] (`aset.c` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### AllocSizeIsValid
Predicate testing whether a requested size is within the ordinary 1 GB `MaxAllocSize` limit; callers use it to `ereport` on an over-large or overflowed size. Companion `AllocHugeSizeIsValid` tests the huge limit instead. [verified-by-code] (`memutils.h` — via `knowledge/files/src/include/utils/memutils.h.md`).



### allowed_auth_methods
The libpq per-connection bitmask (`conn->allowed_auth_methods`) that backs the `require_auth` option; each server auth request is checked against it, and `AUTH_REQ_OK` is additionally gated on `client_finished_auth` unless the user explicitly permitted unauthenticated connections. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-auth.c.md`).



### allowincritsection
A `MemoryContextData` flag; when false, allocating in that context inside a critical section trips an assertion, enforcing the rule that critical sections must not palloc. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### allTheSame
An SP-GiST inner-tuple flag marking a tuple whose `picksplit` could not actually separate the input set, so all children hold identical prefixes; it is the recovery mechanism for a degenerate split and forces `inner_consistent`/`choose` to treat every child uniformly. [verified-by-code] (via `knowledge/docs-distilled/spgist.md`).



### ALWAYS_SECURE_SEARCH_PATH_SQL
The canonical SQL string `SELECT pg_catalog.set_config('search_path', '',
false)` that frontend tools (and `SECURITY DEFINER` code) run right after
connecting to empty the `search_path`, so later unqualified names cannot be
hijacked by attacker-controlled schemas. Defined in `common/connect.h`.
[verified-by-code] (via
`knowledge/files/src/fe_utils/connect_utils.c.md`).



### AM (access method)
The pluggable interface that lets PostgreSQL support multiple index and table
storage engines behind a uniform API. An index AM advertises its callbacks
through an `IndexAmRoutine` struct returned by its `*handler` function (e.g.
`bthandler`); core code calls `amvalidate` to check an opclass and dispatches
scans/inserts through the struct rather than hard-coding btree behavior.
[from-comment] (`amapi.c:1` — via
`knowledge/files/src/backend/access/index/amapi.c.md`).



### ambeginscan
The `IndexAmRoutine` callback that allocates and initialises an `IndexScanDesc` for a new scan; AMs lean on the AM-agnostic `RelationGetIndexScan`/`IndexScanEnd` boilerplate to do it. [verified-by-code] (`amapi.c:32-59` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### ambuild
The mandatory `IndexAmRoutine` callback that builds a complete new index from scratch over the contents of an existing table (the CREATE INDEX hot path). [verified-by-code] (`amapi.c:32-59` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### ambuildempty
The `IndexAmRoutine` callback that writes an empty index into the relation's init fork, used so unlogged-table indexes can be reset to empty after a crash. [verified-by-code] (`amapi.c:32-59` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### ambulkdelete
The `IndexAmRoutine` callback driving VACUUM's first index pass: it scans the index and removes entries that point at dead heap TIDs, returning stats consumed by `amvacuumcleanup`. [verified-by-code] (`index_bulk_delete` dispatches into `ambulkdelete` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### amcanmulticol
The `IndexAmRoutine` boolean declaring the AM supports multiple key columns; it is independent of `amcaninclude`, so an AM may allow one key plus INCLUDE payload columns while forbidding multiple keys. [from-docs] (via `knowledge/docs-distilled/index-api.md`).



### amcanunique
The `IndexAmRoutine` boolean declaring the AM can enforce a UNIQUE constraint via `aminsert` unique checks; in core only nbtree sets it. [from-docs] (via `knowledge/docs-distilled/index-unique-checks.md`).



### amcostestimate
The `IndexAmRoutine` callback that hands the planner an AM-specific cost, selectivity, and correlation estimate for a candidate index path; it is invoked from the planner's `cost_index`. [verified-by-code] (`cost_index` calls index am-specific `amcostestimate` — via `knowledge/subsystems/optimizer.md`).



### amendscan
The `IndexAmRoutine` callback that releases the resources an index scan acquired, closing out what `ambeginscan` opened. [verified-by-code] (`amapi.c:32-59` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### amgetbitmap
The `IndexAmRoutine` callback that returns all matching TIDs at once into a `TIDBitmap` for a bitmap index scan. AMs such as BRIN provide only this (no `amgettuple`) and return a lossy bitmap that the bitmap-heap-scan recheck filters. [from-README] (via `knowledge/files/src/backend/access/brin` docs and `knowledge/architecture/access-methods.md`).



### amgettuple
The `IndexAmRoutine` callback that returns the next matching heap TID one at a time, used by a plain (and index-only) index scan; AMs that cannot enumerate TIDs individually omit it and provide only `amgetbitmap`. [verified-by-code] (`amapi.c:32-59` lists it among the mandatory-or-optional callbacks GetIndexAmRoutine checks — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### aminsert
The mandatory `IndexAmRoutine` callback that inserts one new index entry for a freshly stored or updated heap tuple; like `ambuild` it typically calls `index_form_tuple` to build the on-disk index tuple. [verified-by-code] (`amapi.c:32-59` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### ammarkpos
The index-AM callback that remembers the current scan position (one saved mark per scan) so a later `amrestrpos` can return to it — used by mergejoin to rescan the inner side. A new `ammarkpos` overwrites the previous mark. [from-docs] (via `knowledge/data-structures/indexamroutine.md`).



### amopfamily
The `pg_amop` column linking an operator-family membership row back to its `pg_opfamily`. A family groups related operator classes across types so cross-type operators become indexable. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### amopopr
The `pg_amop` column identifying an operator that is a member of an operator family. Cross-data-type operators (e.g. comparing `int4` to `int8`) are members of the *family* via `pg_amop` rather than of any single operator class, which is what makes them index-usable. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### amoptionalkey
The `IndexAmRoutine` boolean declaring that the index's first key column may be absent from the query's WHERE clause, letting the planner do a full-index scan; false (as in hash) forces at least one equality key. [from-docs] (via `knowledge/data-structures/indexamroutine.md`).



### amrescan
The `IndexAmRoutine` callback that (re)starts an index scan with a new array of scan keys, reusing the `IndexScanDesc` opened by `ambeginscan`; the unkeyed case builds a zero-length key array. [verified-by-code] (`amapi.c:32-59` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### amrestrpos
The index-AM callback that restores the scan to the position previously saved by `ammarkpos`; the save/restore pair supports mergejoin's re-read of the inner relation. [from-docs] (via `knowledge/data-structures/indexamroutine.md`).



### amsearchnulls
The `IndexAmRoutine` boolean declaring the AM can satisfy `IS NULL` / `IS NOT NULL` searches and index NULL entries; bloom, for instance, sets it false. [from-docs] (via `knowledge/data-structures/indexamroutine.md`).



### amtranslatecmptype
The `IndexAmRoutine` callback that maps a generic `CompareType` (LT/LE/EQ/GE/GT) to this AM's strategy number, the inverse-direction partner of `amtranslatestrategy`; it lets AM-agnostic code request an operator by comparison semantics. [from-docs] (via `knowledge/docs-distilled/index-functions.md`).



### amvacuumcleanup
The `IndexAmRoutine` callback for VACUUM's second index pass: final cleanup, free-space recording, and statistics after `ambulkdelete`. The two-phase `ambulkdelete`/`amvacuumcleanup` contract is documented in `amapi.h`. [verified-by-code] (via `knowledge/files/src/backend/access/index/amapi.c.md`).



### amvalidate
The `IndexAmRoutine` callback (also exposed as a SQL-callable function) that sanity-checks an opclass: it cross-checks the `pg_amop` and `pg_amproc` rows against the AM's required-operator/required-proc rules. It runs during ALTER OPERATOR FAMILY and is exercised by `amcheck` and `--enable-cassert` builds. [from-comment] (`amapi.c:1-31`, `brin_validate.c:1-12` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### analyze_mcv_list
The ANALYZE cutoff routine that decides how many most-common values to keep: it retains a value in the MCV list only while doing so is statistically justified (the value is significantly more common than average and estimable), trimming the tail. [verified-by-code] (via `knowledge/idioms/analyze-mcv-histogram-correlation.md`).



### Append
Executor/plan node that concatenates the outputs of several child subplans in sequence, returning all of the first child's tuples, then the next, and so on; it is the workhorse behind `UNION ALL` and behind scanning a partitioned table (one child subplan per surviving partition). [inferred] (via `knowledge/subsystems/executor.md`).



### appendConnStrVal
Escapes and appends a value into a libpq connection string (wrapping in single
quotes and backslash-escaping as needed); used when generating
`primary_conninfo` and similar conninfo strings. [verified-by-code]
(`recovery_gen.c:68-99` — via
`knowledge/files/src/fe_utils/recovery_gen.c.md`).



### appendShellString
The fe_utils helper that single-quotes a string for safe inclusion in a shell
command line; its hard-coded "safe set" of characters is the security boundary
against shell injection in tools that shell out. [verified-by-code]
(`string_utils.c:600-605` — via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### appendStringInfo
The `printf`-style append to a `StringInfo`: formats its arguments and appends them, growing the buffer as needed; the most common way to build SQL text, deparsed queries, or log lines incrementally. [verified-by-code] (via `knowledge/files/src/common/stringinfo.c.md`).



### appendStringInfoChar
Appends a single character to a `StringInfo`, growing the buffer if full; the cheap per-character primitive used by quoting and escaping loops. [verified-by-code] (via `knowledge/files/src/common/stringinfo.c.md`).



### appendStringInfoString
Appends a NUL-terminated C string to a `StringInfo`, growing the buffer via `enlargeStringInfo` as needed; the workhorse for assembling query text, EXPLAIN output, and format strings without the caller pre-sizing anything. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### appendStringLiteralConn
Appends a properly escaped SQL string literal to a buffer, choosing the
escaping from a live `PGconn`'s server settings (standard_conforming_strings,
server encoding) so the literal is safe for that exact server. [from-comment]
(`string_utils.c:451-463` — via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### application_name
A session GUC carrying a free-text label identifying the connecting application; it surfaces in `pg_stat_activity`, the `%a` log-line-prefix escape, and CSV logs. Because it is client-settable it can carry user-controlled text into monitoring views — postgres_fdw additionally exposes `postgres_fdw.application_name` with `%a/%u/%d`-style expansion for remote connections. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/option.c.md`).



### apply_dispatch
The logical-replication apply worker's message router: it reads the leading type byte of a streamed change message and dispatches to the matching `apply_handle_*` routine. [verified-by-code] (`worker.c:3797` — via `knowledge/subsystems/replication.md`).



### ApplyContext
The logical-replication apply worker's long-lived memory context, reset
per-transaction as the worker streams and applies remote changes; distinct
from the per-message scratch context so cross-message state survives while
per-change allocations are reclaimed. [inferred] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### ApplyMessageContext
A per-message memory context used by the logical-replication apply worker; it is
reset after each streamed change so that decoding a transaction's row events
cannot leak memory across the apply loop. [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### ApplyRetrieveRule
The rewriter routine that expands a view reference by substituting the view's
stored `SELECT` rule into the query's range table, replacing the RTE_RELATION
entry with an RTE_SUBQUERY. [verified-by-code] (`rewriteHandler.c:2200-2204` —
via `knowledge/subsystems/parser-and-rewrite.md`).



### ApplyWalRecord
The xlogrecovery.c routine that, inside the `ReadRecord → ApplyWalRecord` redo loop, dispatches one WAL record to its rmgr's `rm_redo` callback during crash/archive/standby recovery. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### ApplyWorkerMain
The entry point of a logical-replication apply worker, launched by the
bgworker harness; it performs the streaming-replication handshake, then enters
the main loop receiving and applying the publisher's change stream. [from-code]
(`worker.c` — via `knowledge/subsystems/replication.md`).



### archive_command
The GUC holding a shell command the archiver runs to copy each completed WAL
segment to long-term storage; it must return zero only on durable success, and
PostgreSQL retries the same segment until it does. It is the classic (pre-archive-library)
mechanism behind continuous archiving / PITR. [verified-by-code] (via
`knowledge/files/contrib/basic_archive/basic_archive.c.md`).



### archive_library
The GUC (added in PG 15) naming a loadable archive module `.so` that implements the `_PG_archive_module_init` callback interface, used instead of an `archive_command` shell string to ship completed WAL segments. Exactly one of the two may be set. [inferred] (via `knowledge/idioms/archive-command-fallback.md`).



### archive_timeout
GUC forcing a WAL segment switch after the interval so a low-traffic cluster's unarchived data can't sit indefinitely; it only fires when there is unarchived WAL to flush out. [from-README] (via `knowledge/docs-distilled/runtime-config-wal.md`).



### ArchiveHandle
The central pg_dump/pg_restore state object representing an open archive plus
its connection and format-specific method pointers (custom, directory, tar,
plain). Restore-time helpers like `ReconnectToServer(AH, dbname)` thread it
through every step. [verified-by-code] (via
`knowledge/files/src/bin/pg_dump/pg_backup_db.c.md`).



### ArchiveModuleCallbacks
The callback vtable an archive-library module fills in (check-configured /
archive-file / shutdown) and returns from its `_PG_archive_module_init`, letting
the archiver invoke a loadable module instead of shelling out to
`archive_command`. [verified-by-code] (via
`knowledge/idioms/archive-command-fallback.md`).



### ArchiveRecoveryRequested
The startup-process flag set when a `recovery.signal` or `standby.signal` file is present, meaning the cluster must perform archive recovery (consulting `restore_command` for missing WAL); `ArchiveRecoveryRequested && !InArchiveRecovery` marks the late transition into archive recovery. [verified-by-code] (via `knowledge/idioms/crash-recovery-startup.md`).



### array_iterator
The ltree helper that walks each element of a PostgreSQL array, invoking a per-element callback via `DirectFunctionCall2(callback, PointerGetDatum(item), PointerGetDatum(param))`; its `*found` short-circuit works only because the inner function returns its bool answer without consuming or freeing the element datum. [verified-by-code] (via `knowledge/files/contrib/ltree/_ltree_op.c.md`).



### ArrayType
The varlena header struct for a PostgreSQL array value, recording the number of dimensions, a null-bitmap-present flag, the element type OID, and the per-dimension bounds, followed by the packed element data. Array code must round element offsets to the element type's alignment, and in-place mutation (e.g. `intarray`'s element delete) compacts within the existing allocation. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_op.md`).



### as_snap
Field of an `ActiveSnapshotElt` holding the snapshot itself; the element also carries `as_level` and `as_next`, forming the active-snapshot stack whose invariant is `as_level` non-increasing toward the bottom and a NULL-terminated list. [from-comment] (`snapmgr.c:173` — via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### assign_hook
The GUC callback invoked after a proposed value passes its `check_hook`, to install the parsed value into the backend's C-level state; the `check_hook`/`assign_hook`/`show_hook` trio backs GUCs with non-trivial semantics (DateStyle, TimeZone, client_encoding, role, transaction_isolation), implemented in `variable.c`. [verified-by-code] (via `knowledge/files/src/backend/commands/variable.c.md`).



### assign_record_type_typmod
Assigns a session-local typmod to an anonymous `RECORD` row type and caches its `TupleDesc` in the typcache, so transient composite types can be referenced by a compact (typid, typmod) pair. [verified-by-code] (`typcache.c:2067` — via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### AssignTransactionId
The routine that lazily allocates a real `TransactionId` the first time a transaction (or subtransaction) needs one — typically at its first write — recursively assigning XIDs to unassigned parents and entering them into the proc array / subxid cache. [verified-by-code] (`xact.c:637` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### astreamer_tar
A link in `pg_basebackup`'s astreamer streaming chain (`src/fe_utils/astreamer_tar.c`) that parses a tar byte stream into typed archive members and hands each member to a successor astreamer (typically `astreamer_tar_parser`). The astreamer abstraction lets base-backup post-processing (decompress, extract, re-tar) be composed as a pipeline of small typed stages. [inferred] (`astreamer_tar.c` — via `knowledge/files/src/fe_utils/astreamer_tar.c.md`).



### AsyncRequest
The per-subplan request/response struct the executor's asynchronous-execution
machinery passes between a parent (e.g. Append) and an async-capable child such
as a foreign scan: it carries the requestor, requestee, a callback slot, and a
`request_complete` flag. `ExecAsyncRequest`/`ExecAsyncNotify`/`ExecAsyncResponse`
drive it so multiple foreign scans can have I/O in flight at once.
[verified-by-code] (via `knowledge/files/src/include/executor/execAsync.md`).



### asyncxactlsn
`asyncXactLSN` records the latest LSN an asynchronously-committed transaction depends on, so the WAL writer knows how far it must eventually flush to make those commits durable. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### AtEOXact_GUC
The end-of-transaction GUC-stack unwinder: given a nest level returned by `NewGUCNestLevel`, it pops every GUC setting pushed since that level, restoring prior values. It runs on the normal commit/abort path and is also called explicitly (e.g. postgres_fdw's `reset_transmission_modes`) so an error inside a temporarily-forced GUC scope still unwinds correctly. [verified-by-code] (`postgres_fdw.c:4147` — via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### AtEOXact_Inval
End-of-transaction cache-invalidation flush: at commit it broadcasts the accumulated shared-invalidation messages (bracketing the relcache init-file rewrite when `RelcacheInitFileInval` is set); at abort it discards the queued messages locally. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### attribute_buf
The `CopyFromStateData` parse buffer holding one field's bytes after a line has been split into columns; the innermost of COPY FROM's four buffers (`raw_buf` -> `input_buf` -> `line_buf` -> `attribute_buf`). [verified-by-code] (via `knowledge/files/src/include/commands/copyfrom_internal.h.md`).



### AttrMap
A compact attribute-number remapping table produced by tupconvert.c to convert a tuple between two logically-equivalent but differently-ordered `TupleDesc`s — the workhorse behind partition tuple-routing, inheritance parent↔child, and logical-replication column matching. [verified-by-code] (via `knowledge/files/src/backend/access/common/tupconvert.c.md`).



### AttrNumber
The 16-bit signed integer type naming a column position within a relation
(1-based for user columns; system columns like `ctid` use negative numbers, and
0/`InvalidAttrNumber` means "no column"). It appears throughout the parser and
executor, e.g. `get_rte_attribute_name(RangeTblEntry *, AttrNumber)`.
[verified-by-code] (via `knowledge/files/src/include/parser/parsetree.h.md`).



### AUTH_REQ_OK
The frontend/backend authentication-request code meaning "authentication succeeded, no further exchange is required"; libpq stops the auth handshake when it receives it. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-auth.c.md`).



### authn_id
The post-authentication identity string stored in `ClientConnectionInfo` (`libpq-be.h`) — the name the auth method actually verified (certificate CN, Kerberos principal, RADIUS user, …) — and the value surfaced by the `system_user` function. [from-comment] (`libpq-be.h:86-106` — via `knowledge/subsystems/libpq-backend.md`).



### AuthRequest
The uint32 authentication-request code the server sends during startup (`pqcomm.h`); libpq's `pg_fe_sendauth` branches on it to run the matching client-side auth method (password, MD5, SCRAM/SASL, GSS, …). [verified-by-code] (`fe-auth.c:1065` — via `knowledge/files/src/interfaces/libpq/fe-auth.c.md`).



### autovacuum
The background facility that automatically issues `VACUUM` and `ANALYZE` on
tables whose dead-tuple or modification counters cross per-table thresholds. An
`autovacuum launcher` schedules work per database and forks short-lived
`autovacuum worker` backends to do it; it is also the safety net against
transaction-id wraparound. [from-comment] (via
`knowledge/files/src/backend/postmaster/autovacuum.c.md`).



### autovacuum_naptime
GUC (default 1 min) setting how often the autovacuum launcher wakes; it tries to visit each database once per naptime, so with N databases a given database is considered roughly every `autovacuum_naptime / N`. [from-README] (via `knowledge/docs-distilled/routine-vacuuming.md`).



### backend
A per-connection PostgreSQL server process. The postmaster forks one backend
per accepted connection; that backend runs `PostgresMain`, the "traffic cop"
read-parse-plan-execute loop, for the life of the session. Because each
session is a fresh fork, backend PIDs are not stable across connects.
[verified-by-code] (`postgres.c:4274` — via
`knowledge/files/src/backend/tcop/postgres.c.md`).



### backend_startup
The early connection-establishment phase in a freshly forked backend that reads
the startup packet, negotiates protocol version and SSL/GSS encryption, applies
startup GUCs, and authenticates before `InitPostgres` runs. The `ProcessStartupPacket`
path here is exposed to unauthenticated input, so it is a hardened trust
boundary. [verified-by-code] (via
`knowledge/files/src/include/tcop/backend_startup.h.md`).



### BackendInitialize
The early phase of a forked backend's startup (within `BackendMain`) that
reads the client's startup packet and performs authentication before the
backend enters its command loop. [verified-by-code] (`backend_startup.c:76` —
via `knowledge/files/src/backend/postmaster/postmaster.c.md`).



### BackendKeyData
A startup-phase backend message (type byte `'K'`) carrying secret-key data the frontend must save in order to later issue query-cancel requests. It is sent on successful authentication, before `ParameterStatus` and `ReadyForQuery`; as of protocol v3.2 its secret is variable length (4–256 bytes) rather than a fixed 4 bytes. [from-README] (`protocol-flow.md` — via `knowledge/docs-distilled/protocol-flow.md`).



### BackendMain
The entry point of a freshly forked client backend; it runs
`BackendInitialize` (read the startup packet, set up signals) and then enters
the `PostgresMain` command loop. [verified-by-code] (`backend_startup.c:76` —
via `knowledge/files/src/backend/tcop/postgres.c.md`).



### BackendPidGetProc
Looks up the `PGPROC` of a live backend by its process id, scanning the ProcArray; it returns NULL when no such backend exists. [verified-by-code] (via `knowledge/files/src/include/storage/procarray.h.md`).



### BackendStartup
The postmaster routine that handles a newly arrived connection by forking a
child process to become the client backend. [verified-by-code]
(`postmaster.c:3576` — via `knowledge/architecture/query-lifecycle.md`).



### BackendType
The enum classifying each PostgreSQL process (client backend, autovacuum
worker, walwriter, checkpointer, background worker, …); it drives
process-title and statistics reporting. [verified-by-code]
(`miscadmin.h:340-381` — via `knowledge/architecture/process-model.md`).



### BackgroundWorker
The registration struct an extension fills in (name, library/function entry
point, restart policy, flags for shmem/DB access) and hands to
`RegisterBackgroundWorker` (static, at load) or `RegisterDynamicBackgroundWorker`
(runtime) so the postmaster forks and manages a long-lived helper process.
[verified-by-code] (`bgworker.c:658` — via
`knowledge/files/src/backend/postmaster/bgworker.c.md`).



### BackgroundWorkerHandle
The opaque handle returned by `RegisterDynamicBackgroundWorker` identifying a launched worker; it is used with `GetBackgroundWorkerPid` / `WaitForBackgroundWorkerStartup` / `…Shutdown` and is freed by the launcher once the worker is done. [verified-by-code] (via `knowledge/idioms/apply-worker-loop-and-dispatch.md`).



### BackgroundWorkerInitializeConnection
The bgworker.c entry that attaches a registered background worker to a specific database and role, running the same `InitPostgres` path a normal backend uses (so `MyProc` must already exist). [verified-by-code] (via `knowledge/files/src/backend/utils/init/postinit.c.md`).



### BackgroundWorkerUnblockSignals
The call a background-worker main function must make first, before any other setup, because the worker starts with all signals blocked; it unblocks them so the worker can receive SIGTERM/SIGHUP. It is typically followed by `BackgroundWorkerInitializeConnection`. [verified-by-code] (`worker_spi.c` — via `knowledge/idioms/background-worker-startup.md`).



### backup_label
A small text file written into the data directory at the start of a non-exclusive base backup; it records the start WAL location, the checkpoint redo point, and the backup method so recovery knows where to begin replaying WAL. Its contents are produced by `build_backup_content`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlogfuncs.c.md`).



### backup_manifest
A JSON file emitted alongside a base backup listing every file with its size, modification time, and checksum, plus the WAL range needed to restore; `pg_verifybackup` later replays it to detect corruption, truncation, or missing files. [from-comment] (via `knowledge/files/contrib/basebackup_to_shell/basebackup_to_shell.c.md`).



### BAS_BULKREAD
The BufferAccessStrategy ring type used for large sequential reads
(seqscans, ANALYZE, `COPY ... TO`): a small fixed ring of shared buffers is
reused so one big scan can't evict the entire buffer pool.
[verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### BASE_BACKUP
The replication-protocol command (used by `pg_basebackup`) that asks a walsender
to stream a full copy of the data directory as a tar/plain archive, with options
for WAL inclusion, checkpoint mode, tablespace mapping, and progress reporting.
[verified-by-code] (via
`knowledge/files/src/backend/replication/repl_gram.y.md`).



### base_yylex
The raw flex scanner entry point (exposed by `pgc.l`/`scan.l`) that the higher-level lexer wrapper calls; the wrapper saves and post-processes `base_yylval`/`base_yylloc`/`base_yytext` because `base_yylex` overwrites them on each token. ECPG's `parser.c` wraps it to fill location info. [verified-by-code] (`parser.c:238-278` — via `knowledge/files/src/interfaces/ecpg/preproc/parser.c.md`).



### base_yyparse
The bison-generated parser entry point of the ECPG preprocessor (`ecpg`), driven once per input `.pgc`/`.pgh` file after all per-file global state (cursors, typedefs, defines, `when_*` handlers) is reset. [verified-by-code] (via `knowledge/files/src/interfaces/ecpg/preproc/ecpg.c.md`).



### basebackup_to_shell
A contrib server module that adds a `shell` target to the replication `BASE_BACKUP ... TARGET` command, piping each base-backup tarball to an operator-configured shell command (`basebackup_to_shell.command`) instead of streaming it back to the client. It is the reference consumer of the `BaseBackupAddTarget` extensibility hook, showing how a `bbsink` can redirect backup output. [verified-by-code] (via `knowledge/files/contrib/basebackup_to_shell/basebackup_to_shell.c.md`).



### BaseInit
The early per-backend initialization that sets up the buffer pool access, relcache, and file access before a database is selected, shared by regular backends and auxiliary processes during `InitPostgres`. [verified-by-code] (via `knowledge/files/src/backend/postmaster/auxprocess.c.md`).



### baserestrictinfo
The list of single-relation `RestrictInfo` quals attached to a base `RelOptInfo` — the `WHERE` clauses that reference only that one relation and can be applied as a scan filter or index qual. Distinct from `joininfo`, which holds clauses spanning more than one relation. [verified-by-code] (via `knowledge/data-structures/reloptinfo.md`).



### basic_archive
The reference contrib archive module demonstrating the `archive_library` callback API: `_PG_archive_module_init` returns an `ArchiveModuleCallbacks` struct wiring `check_configured_cb` and `archive_file_cb`. It copies each completed WAL segment to a target directory durably via a temp file plus `durable_rename`, the template real archive libraries follow. [verified-by-code] (via `knowledge/files/contrib/basic_archive/basic_archive.c.md`).



### BasicOpenFile
Opens a kernel file descriptor while registering it with the fd manager's count so PostgreSQL stays under `max_safe_fds`, but without the virtual-FD (`File`) layer's automatic reopen-on-eviction behaviour. [verified-by-code] (via `knowledge/files/src/backend/storage/file/fd.c.md`).



### bbs_buffer
The shared scratch-buffer field on a base-backup streamer (`astreamer`); in the file-extraction path neither writer uses it because the tar extractor keeps its own buffer, so `bbs_buffer` ownership is a per-streamer concern worth checking when chaining streamers. [verified-by-code] (`astreamer_file.c:67` — via `knowledge/files/src/fe_utils/astreamer_file.c.md`).



### be_fsstubs
The backend SQL-callable wrappers (`lo_import`, `lo_export`, `lo_open`,
`loread`, `lowrite`, …) implementing the large-object interface over the
inversion-FS routines; `lo_import`/`lo_export` read and write server-side files
and are therefore restricted to superusers / `pg_read_server_files` roles.
[verified-by-code] (via
`knowledge/files/src/backend/libpq/be-fsstubs.c.md`).



### be_gssapi_write
The backend GSSAPI transport send routine that wraps outbound bytes in per-message GSS security tokens, staging them through `PqGSSSendBuffer`. [verified-by-code] (`be-secure-gssapi.c:105` — via `knowledge/docs-distilled/gssapi-enc.md`).



### be_tls_init
Builds the process-wide OpenSSL server `SSL_CTX` at server start/reload — loading the cert chain and private key — from which each connection's TLS session is derived. [verified-by-code] (`be-secure-openssl.c` — via `knowledge/docs-distilled/ssl-tcp.md`).



### be_tls_open_server
Performs the per-connection server-side TLS handshake on top of the shared context built by `be_tls_init`; reached via `secure_open_server`'s SSL branch. [verified-by-code] (`be-secure-openssl.c` — via `knowledge/docs-distilled/ssl-tcp.md`).



### BecomeLockGroupMember
The call a parallel worker makes during startup to join its leader's lock
group, so the deadlock detector treats leader and workers as a single unit and
never reports a false deadlock on locks they pass between themselves.
[verified-by-code] (via
`knowledge/idioms/parallel-worker-launch-wait-and-errors.md`).



### before_shmem_exit
Registers a callback to run during normal backend shutdown before shared memory is detached, so cleanup that touches shmem state (releasing slots, decrementing counters) happens while that state is still mapped. It is distinct from `on_shmem_exit`, which runs slightly later in the same teardown. [inferred] (via `knowledge/files/src/backend/storage/ipc/ipc.c.md`).



### BeginCopyFrom
The COPY ... FROM entry routine (`copyfrom.c:1535`) that opens the data source (file, program, or frontend), initializes a `CopyFromState`, sets up per-column input-function lookups, and initializes the target `ResultRelInfo` (including BEFORE/INSTEAD OF triggers); it returns the opaque `CopyFromState` later driven by `CopyFrom` and torn down by `EndCopyFrom`. `WITH (FREEZE)` preconditions are enforced here, and file_fdw reuses it as a thin shim to read server-side files/programs. [verified-by-code] (`copyfrom.c:1535` — via `knowledge/files/src/backend/commands/copyfrom.c.md`).



### begindirectmodify
The FDW callback that begins a *direct-modify* plan — an `UPDATE` / `DELETE` executed entirely on the remote server rather than row-by-row (with `PlanDirectModify` / `IterateDirectModify` / `EndDirectModify`). [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### beginforeignmodify
The FDW callback that initializes per-modify state for a row-at-a-time `INSERT` / `UPDATE` / `DELETE` on a foreign table, the DML counterpart to `BeginForeignScan`. [from-docs] (via `knowledge/docs-distilled/fdw-callbacks.md`).



### BeginForeignScan
The FDW callback that initializes a foreign scan at executor startup —
establishing the connection/cursor and stashing per-scan state — before the
first `IterateForeignScan`. [verified-by-code] (via
`knowledge/idioms/fdw-iterate-scan.md`).



### BeginInternalSubTransaction
Starts a subtransaction from C code (not from a SQL `SAVEPOINT`), giving a
PG_TRY/PG_CATCH frame that can be rolled back independently. plpgsql wraps a
block that has an `EXCEPTION` clause in one, taking care to create the
statement memory context *before* the subxact so caught error data outlives the
rollback. [verified-by-code] (`pl_exec.c:1818` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### BeginSampleScan
A required `TsmRoutine` callback for a table-sampling method (the plug-in behind `TABLESAMPLE`), invoked to start a scan with the evaluated parameter Datums and the `REPEATABLE` seed. It is the executor-time entry into the block-then-tuple sampling loop, paired with the required `NextSampleTuple` and the optional `NextSampleBlock`. [verified-by-code] (`tablesample-method.md` — via `knowledge/docs-distilled/tablesample-method.md`).



### BgBufferSync
The background writer's per-cycle scan that cleans a bounded number of dirty shared buffers ahead of the clock sweep, using a moving average of recent allocation demand to pace how far ahead of the strategy point it writes. [verified-by-code] (`bgwriter.c` — via `knowledge/files/src/backend/postmaster/bgwriter.c.md`).



### bgw_extra
A fixed `BGW_EXTRALEN`-byte opaque scratch buffer in the `BackgroundWorker` struct that the registrant fills before registration and the worker reads back via `MyBgworkerEntry->bgw_extra`; worker_spi packs `Oid + Oid + uint32` into it. Because it is raw memory, `sizeof(payload) <= BGW_EXTRALEN` must hold or the next worker slot is corrupted. [verified-by-code] (via `knowledge/scenarios/add-new-bgworker.md`).



### bgw_flags
The capability bitmask field of the `BackgroundWorker` struct declaring what the worker needs — e.g. `BGWORKER_SHMEM_ACCESS` and `BGWORKER_BACKEND_DATABASE_CONNECTION`; the postmaster consults it when deciding connection setup and start eligibility. [verified-by-code] (via `knowledge/files/src/include/postmaster/bgworker.h.md`).



### bgw_function_name
The name of the worker's entry-point function (resolved inside `bgw_library_name`) that the postmaster calls to launch a background worker; each logical-replication `*Main` is the `bgw_function_name` for its flavor, and worker_spi uses `"worker_main"`. [verified-by-code] (via `knowledge/files/src/include/postmaster/bgworker.h.md`).



### bgw_library_name
The shared library the postmaster loads to find `bgw_function_name` (a `$libdir`-relative name with no `.so` suffix); worker_spi sets it via `sprintf(worker.bgw_library_name, "worker_spi")`. [verified-by-code] (via `knowledge/scenarios/add-new-bgworker.md`).



### bgw_main_arg
The single `Datum` argument passed to the worker's main function at start; e.g. test_shm_mq sets `bgw_main_arg = dsm_segment_handle(seg)` so the worker can attach the shared DSM segment. [verified-by-code] (via `knowledge/files/src/test/modules/test_shm_mq/setup.c.md`).



### BGW_NEVER_RESTART
The `bgw_restart_time` sentinel value telling the postmaster never to restart a background worker once it exits or crashes (as opposed to a restart interval in seconds). [verified-by-code] (via `knowledge/idioms/bgworker-and-parallel.md`).



### bgw_notify_pid
The PID the postmaster signals (SIGUSR1) on the worker's start/stop state changes; a registrant sets `bgw_notify_pid = MyProcPid` so `WaitForBackgroundWorkerStartup` can wake it, and the worker can look the registrant up via `MyBgworkerEntry->bgw_notify_pid`. [verified-by-code] (via `knowledge/files/src/test/modules/worker_spi/worker_spi.c.md`).



### bgw_restart_time
The `BackgroundWorker` field giving the seconds the postmaster waits before restarting the worker after a crash, or `BGW_NEVER_RESTART` to leave it dead. One-shot or on-demand workers set the never-restart sentinel to avoid a crash loop. [inferred] (`bgworker.h:84` — via `knowledge/scenarios/add-new-bgworker.md`).



### bgw_start_time
The `BgWorkerStart_*` enum controlling how far into startup the postmaster waits before launching the worker — e.g. `BgWorkerStart_RecoveryFinished` starts it only after recovery reaches consistency. [verified-by-code] (via `knowledge/files/src/include/postmaster/bgworker.h.md`).



### BGWH_STARTED
The `BgwHandleStatus` value from `GetBackgroundWorkerPid`/`WaitForBackgroundWorkerStartup` meaning the worker has started and registered its pid; contrast `BGWH_NOT_YET_STARTED` and `BGWH_STOPPED`. [from-docs] (via `knowledge/docs-distilled/bgworker.md`).



### BGWORKER_BACKEND_DATABASE_CONNECTION
A `bgw_flags` bit on the `BackgroundWorker` struct declaring that the worker intends to attach to a database (via `BackgroundWorkerInitializeConnection`); it sits alongside `BGWORKER_SHMEM_ACCESS` and `BGWORKER_CLASS_PARALLEL`. [verified-by-code] (`bgworker.h` — via `knowledge/files/src/include/postmaster/bgworker.h.md`).



### BGWORKER_SHMEM_ACCESS
A `bgw_flags` bit a background worker sets to request access to the server's main shared-memory segment and lightweight locks; required by almost any worker that touches shared state, and a prerequisite for `BGWORKER_BACKEND_DATABASE_CONNECTION`. [from-README] (via `knowledge/docs-distilled/bgworker.md`).



### BgWorkerStart_ConsistentState
The `bgw_start_time` value delaying a background worker's launch until a standby has reached a consistent recovery state (so it may query); on a primary it is equivalent to starting in normal running. [from-docs] (via `knowledge/docs-distilled/bgworker.md`).



### bgwriter (background writer)
The auxiliary process that trickles dirty shared buffers out to the storage
manager ahead of checkpoints, smoothing write spikes so backends and the
checkpointer find clean victims more often. It runs `BackgroundWriterMain`,
sleeping on a latch between rounds, and never writes WAL itself. [from-comment]
(via `knowledge/files/src/backend/postmaster/bgwriter.c.md`).



### bgwriter_delay
GUC (default 200 ms, the `BgWriterDelay` global) setting how long the background writer sleeps between rounds of flushing dirty shared buffers ahead of backend demand. [verified-by-code] (via `knowledge/files/src/backend/postmaster/bgwriter.c.md`).



### BgWriterStats
The accumulator of background-writer activity counters (buffers cleaned, maxwritten-clean halts) that a backend flushes into the shared pgstat bgwriter entry, surfaced by `pg_stat_bgwriter`. [verified-by-code] (via `knowledge/data-structures/pgstat-counter.md`).



### bitcode inlining
The JIT mechanism that inlines the bodies of `C`/`internal` functions (and operators over them) into JIT'd expressions by loading their pre-built LLVM bitcode from `$pkglibdir/bitcode/$extension/` (with a summary index `$extension.index.bc`); PGXS builds and installs this bitcode automatically, and core PG's own bitcode lives at `$pkglibdir/bitcode/postgres`. [verified-by-code] (`llvmjit_inline.cpp:492,811-812` — via `knowledge/docs-distilled/jit-extensibility.md`).



### BitmapAnd
The executor node (`nodeBitmapAnd.c`) that intersects the TID bitmaps produced by several BitmapIndexScan children before a single BitmapHeapScan fetches the surviving heap tuples. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeBitmapAnd.c.md`).



### BitmapHeapNext
The access routine of a Bitmap Heap Scan executor node: it consumes the TID bitmap built by the child bitmap-index scan and fetches the matching heap tuples page at a time, honouring lossy (whole-page) bitmap entries. [verified-by-code] (via `knowledge/idioms/parallel-bitmap-heap.md`).



### BitmapHeapScan
The plan/executor node that consumes a TID bitmap built by one or more
BitmapIndexScan children and fetches the matching heap tuples in physical block
order, which turns scattered index hits into mostly-sequential heap I/O.
`ExecInitBitmapHeapScan` wires it up; it supports lossy bitmap pages by
rechecking the qual on every tuple of a lossy block.
[verified-by-code] (via `knowledge/files/src/include/executor/nodeBitmapHeapscan.md`).



### BitmapHeapScanState
The executor run-state node for a Bitmap Heap Scan; `BitmapHeapNext` drives it,
consuming the TID bitmap produced by the underlying bitmap index scan(s) and
fetching the matching heap tuples in physical block order. [verified-by-code]
(via `knowledge/idioms/bitmap-heap-scan-flow.md`).



### BitmapIndexScan
The executor node by which an index AM returns a bitmap of matching TIDs
rather than tuples one at a time; a `BitmapHeapScan` above it then fetches
the heap pages in physical order, and several such bitmaps can be AND/ORed.
[verified-by-code] (via `knowledge/subsystems/executor.md`).



### BitmapIndexScanState
The executor state node (`execnodes.h`) for a Bitmap Index Scan: it runs an index scan purely to produce a TID bitmap (no heap fetch), which a Bitmap Heap Scan above it consumes; `ExecInitBitmapIndexScan` / `ExecEndBitmapIndexScan` manage its lifecycle. [verified-by-code] (via `knowledge/files/src/include/executor/nodeBitmapIndexscan.md`).



### BitmapOr
The executor node that unions the bitmaps produced by several
`BitmapIndexScan` children into one combined TID bitmap, feeding a single
`BitmapHeapScan`. It is how `OR`-of-indexable-quals turns into one heap pass.
[verified-by-code] (via `knowledge/subsystems/executor.md`).



### bitmapqualorig
The original index qual expressions kept on a Bitmap Heap Scan node so the executor can recheck them per tuple; a recheck is forced when the bitmap went lossy (page-level rather than tuple-level) so false-positive rows are filtered out. [verified-by-code] (via `knowledge/idioms/bitmap-heap-scan-flow.md`).



### Bitmapset
A compact variable-length set of small non-negative integers (a `Bitmapset`),
used throughout the planner and parser for things like sets of relids,
attribute numbers, and required-outer relations. Operations
(`bms_add_member`, `bms_is_member`, `bms_union`, …) treat it as an immutable-ish
value and may reallocate. [from-comment] (via
`knowledge/files/src/backend/nodes/bitmapset.c.md`).



### BitmapShouldInitializeSharedState
The predicate that elects a single leader among parallel Bitmap Heap Scan participants to build the shared TID bitmap, while the others wait; it enforces single-leader initialisation of the shared state. [verified-by-code] (via `knowledge/idioms/parallel-bitmap-heap.md`).



### BITS_PER_BITMAPWORD
The width (32 or 64) of one word in a `Bitmapset` or tidbitmap, i.e. the granularity at which membership bits are packed into `bitmapword` array elements. [verified-by-code] (via `knowledge/files/src/backend/nodes/bitmapset.c.md`).



### BKI
The Backend Interface bootstrap format — the `postgres.bki` script that `initdb` feeds to a bootstrap-mode backend to lay down the initial system catalogs. It is generated by `genbki.pl` from the `pg_*.h` catalog headers and `.dat` files; `bootstrap.c` is the parser/executor that creates the catalog relations from it. [verified-by-code] (via `knowledge/files/src/backend/bootstrap/bootstrap.c.md`).



### BKI_ARRAY_DEFAULT
A `genbki` annotation in a catalog header that supplies the default value
for an array-typed column in bootstrap (`.bki`) data, so hand-written `.dat`
rows can omit it. [from-comment] (via
`knowledge/files/src/include/catalog/pg_type.h.md`).



### BKI_BOOTSTRAP
A catalog header marker (empty to the C compiler, recognized by genbki.pl on the same source line as `CATALOG()`) declaring that the catalog is created during the bootstrap phase, before any other catalog exists. Only the lowest-level catalogs such as pg_class, pg_attribute, pg_proc, and pg_type carry it. [verified-by-code] (`_catalog_headers_overview.md` — via `knowledge/files/src/include/catalog/_catalog_headers_overview.md`).



### BKI_DEFAULT
One of the catalog header macros (alongside `BKI_BOOTSTRAP`,
`BKI_SHARED_RELATION`, `BKI_ROWTYPE_OID`, `BKI_LOOKUP`) that annotate a
`CATALOG()` column. It supplies the default value used to fill a `.dat` row that
omits the field. The macros are empty to the C compiler (defined in `genbki.h`)
and meaningful only to `genbki.pl` at build time. [verified-by-code] (via
`knowledge/files/src/backend/catalog/_generators.md`).



### BKI_FORCE_NOT_NULL
A catalog-definition macro forcing a column to be NOT NULL in the generated BKI
even though its C type or position would otherwise let bootstrap treat it as
nullable (e.g. the first variable-length or array column). [verified-by-code]
(via `knowledge/files/src/include/catalog/pg_propgraph_element.h.md`).



### BKI_LOOKUP
A catalog-column annotation declaring that an `Oid` column's `.dat` values are
written as names and resolved to OIDs against another catalog (e.g.
`BKI_LOOKUP(pg_proc)`) during bootstrap. Missing it on a column that is
semantically an OID reference is a recurring corpus issue. [from-comment] (via
`knowledge/idioms/catalog-conventions.md`).



### BKI_LOOKUP_OPT
A BKI annotation macro on a catalog column declaring that the column holds an OID referencing another catalog, so genbki.pl resolves symbolic names to OIDs at bootstrap-emit time; the `_OPT` variant additionally allows the column to be zero (no reference). [from-comment] (via `knowledge/files/src/backend/catalog/_generators.md`).



### BKI_ROWTYPE_OID
A `CATALOG()` annotation that pins the OID of the composite (row) type
implicitly created for a system catalog, so that type OID is stable and can be
referenced from other bootstrap data. Processed by `genbki.pl`; invisible to the
C compiler. [verified-by-code] (via
`knowledge/files/src/backend/catalog/_generators.md`).



### BKI_SCHEMA_MACRO
A catalog header marker (empty to the C compiler, recognized by genbki.pl alongside `CATALOG()`) that directs generation of a `Schema_pg_X[]` macro for use by relcache bootstrap. It appears on catalogs whose hardwired schema the relcache must build before pg_class is readable, such as pg_class, pg_attribute, pg_proc, and pg_type. [verified-by-code] (`_catalog_headers_overview.md` — via `knowledge/files/src/include/catalog/_catalog_headers_overview.md`).



### BKI_SHARED_RELATION
A `CATALOG()` annotation marking a system catalog as cluster-wide (shared
across all databases, stored in the `global/` tablespace) rather than
per-database — e.g. `pg_database`, `pg_authid`. `genbki.pl` recognises it at
build time; it is empty to the C compiler. [verified-by-code] (via
`knowledge/files/src/backend/catalog/_generators.md`).



### BLCKSZ
The compile-time database block (page) size, 8192 bytes by default; nearly every on-disk structure — heap and index pages, free-space sizing, TOAST chunking, WAL page alignment — is expressed in multiples or fractions of it. [verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### BlessTupleDesc
Registers a transient (non-catalog) `TupleDesc` with the typcache so its row type gains a valid composite-type identity; required before returning composite/record Datums or building tuples in a set-returning function. [verified-by-code] (via `knowledge/files/contrib/sslinfo/sslinfo.c.md`).



### BLK_NEEDS_REDO
One of the four `XLogRedoAction` verdicts returned by `XLogReadBufferForRedo` during WAL replay (`xlogutils.h:72-77`); it means the buffer page's LSN is less than the record's LSN, so the redo handler MUST apply the per-buffer-data payload to bring the page up to date. The other verdicts — `BLK_DONE`, `BLK_RESTORED`, `BLK_NOTFOUND` — signal that the change is already applied, was restored from a full-page image, or the block is gone; redo applies changes ONLY on `BLK_NEEDS_REDO`, which keeps replay idempotent. [verified-by-code] (`xlog-region-replay.md` — via `knowledge/idioms/xlog-region-replay.md`).



### BLK_NOTFOUND
One of the XLogReadBufferForRedo result codes ({BLK_NEEDS_REDO, BLK_DONE, BLK_RESTORED, BLK_NOTFOUND}); it signals that the referenced block no longer exists (e.g. the relation was truncated), so redo of that block is skipped. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlogutils.c.md`).



### blkreftable
The block-reference table used by incremental backup: it records, per relation
fork, which blocks changed since a prior backup (derived from WAL summaries) so
`pg_basebackup --incremental` and `pg_combinebackup` can copy only modified
blocks. Serialized into the backup manifest. [verified-by-code] (via
`knowledge/files/src/include/common/blkreftable.h.md`).



### BlockIdSet
Inline helper that packs a 32-bit `BlockNumber` into the split hi/lo 16-bit `BlockIdData` representation stored inside an `ItemPointer`; paired with `BlockIdGetBlockNumber` for the reverse. [verified-by-code] (via `knowledge/files/src/include/storage/block.h.md`).



### BlockNumber
A `uint32` identifying a page within a single relation fork; block 0 is the
first 8 KB page. `InvalidBlockNumber` (0xFFFFFFFF) is the sentinel "no block",
which caps a fork at just under 2^32 pages. Combined with an `OffsetNumber`
it forms an `ItemPointer`/TID. [verified-by-code] (`block.h:31` — via
`knowledge/files/src/bin/pg_rewind/datapagemap.h.md`).



### BlockRefTable
The incremental-backup data structure: a simplehash from relation-fork to the set of blocks modified since a reference LSN (chunked bitmaps), written into WAL summary files and merged into one in-memory table when an incremental base backup is taken. [verified-by-code] (`blkreftable.c:144-150` — via `knowledge/files/src/include/common/blkreftable.h.md`).



### BlocktableEntry
The per-heap-block value stored in vacuum's `TidStore` radix tree; it uses a
two-mode encoding (a small sorted offset array, or a bitmap) so a block's dead
item offsets are recorded compactly regardless of density. [verified-by-code]
(via `knowledge/idioms/vacuum-tid-store.md`).



### BM_DIRTY
The buffer state flag marking that the page has been modified since it was
read in and must be written back before the buffer can be reused.
[verified-by-code] (`buf_internals.h:106-127` — via
`knowledge/subsystems/storage-buffer.md`).



### BM_IO_ERROR
The buffer state flag set when an in-progress I/O failed; it is cleared
together with `BM_IO_IN_PROGRESS` when the I/O completes
(`TerminateBufferIO`), signalling waiters that the operation did not succeed.
[verified-by-code] (`bufmgr.c:7366-7413` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BM_IO_IN_PROGRESS
The buffer state flag indicating a read or write I/O is underway on the
buffer; other backends wanting the page wait on the buffer's I/O condition
variable until the flag clears. [verified-by-code] (`bufmgr.c:7366-7413` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BM_LOCKED
The buffer-descriptor state-word flag bit that spinlock-protects the rest of
the packed atomic state; `LockBufHdr`/`UnlockBufHdr` set and clear it around
any non-atomic update of the refcount/usagecount/flags word.
[verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### BM_PERMANENT
Buffer-descriptor flag marking a buffer that belongs to a logged (permanent) relation; permanent buffers must be written at every checkpoint and gate XLogFlush in FlushBuffer, whereas unlogged buffers are written only at shutdown. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BM_PIN_COUNT_WAITER
The buffer state flag recording that a backend is waiting for the buffer's pin
count to drop to one (a "superexclusive" lock used e.g. by VACUUM); only one
such waiter is allowed at a time. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### BM_TAG_VALID
Buffer flag set once a victim buffer's tag has been assigned to a new page; it is set together with BUF_USAGECOUNT_ONE (plus BM_PERMANENT when applicable) under the buffer-header spinlock during buffer allocation. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### bms_add_member
Adds an integer to a `Bitmapset`, reallocating the word array if the bit index exceeds the current allocation and returning the (possibly moved) set; the canonical way to accumulate a set of attnums, relids, or param ids. [verified-by-code] (via `knowledge/files/src/backend/nodes/multibitmapset.c.md`).



### bms_is_member
Tests whether an integer is present in a `Bitmapset` — the "is this attribute/relid in the set?" primitive. Attribute callers offset by `FirstLowInvalidHeapAttributeNumber` so system columns map to non-negative bit positions. [verified-by-code] (via `knowledge/files/contrib/lo/lo.c.md`).



### boot_val
The compiled-in default of a GUC variable — the value in force before any config file, `ALTER SYSTEM`, or session `SET` is applied; every `DefineCustom*Variable` call must supply one. [inferred] (via `knowledge/scenarios/add-new-cost-model-knob.md`).



### BOOTSTRAP_SUPERUSERID
The fixed OID (10) of the bootstrap superuser role created by `initdb`; it is used as the default object owner and in permission fast-paths that recognise the cluster's original superuser. [verified-by-code] (via `knowledge/files/src/include/utils/guc_tables.h.md`).



### bootstrap_template1
The initdb phase that replays the bootstrap BKI stream to build the initial catalog of `template1`, at which point the cluster's frozen checksum/locale/encoding invariants are written. [verified-by-code] (`initdb.c:1571` — via `knowledge/docs-distilled/creating-cluster.md`).



### BootstrapModeMain
The entry point for bootstrap/check mode (`bootstrap.c`, `pg_noreturn`): `--boot` runs `BootstrapModeMain(argc, argv, false)` to build the initial catalogs during initdb, and `--check` runs it with `check_only=true`. [verified-by-code] (via `knowledge/subsystems/main.md`).



### bpchar_pattern_ops
The blank-padded-`char` counterpart of `text_pattern_ops`: byte-by-byte comparison enabling `LIKE`/anchored-regex index support on `bpchar` columns outside the C locale. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### BRIN
Block Range INdex — an index access method that stores a compact summary (typically min/max) per range of consecutive heap blocks instead of one entry per tuple, trading precision for tiny size on naturally-clustered columns. A scan consults each range's summary and re-checks only the blocks whose range cannot be ruled out. [from-README] (`brin.c:300` — via `knowledge/files/src/backend/access/brin/README.md`).



### brin_deform_tuple
The BRIN routine (in `brin_tuple.c`) that unpacks an on-disk BRIN index tuple into an in-memory `BrinMemTuple` of per-column summary values, the inverse of `brin_form_tuple`; called throughout `brin.c`'s scan and union paths. [verified-by-code] (via `knowledge/files/src/backend/access/brin/brin.c.md`).



### brin_doupdate
The BRIN page-ops routine that replaces a summary index tuple in place when it still fits, or marks the old one dead and inserts the larger one elsewhere, updating the revmap pointer either way. It is how a range's min/max gets widened as new heap tuples arrive. [inferred] (`brin_pageops.c:115` — via `knowledge/files/src/backend/access/brin/brin.c.md`).



### brin_form_tuple
The BRIN serializer (`brin_tuple.c`) that packs a `BrinMemTuple`'s per-column summary values into an on-disk index tuple, walking each opclass's `oi_nstored` stored columns. [verified-by-code] (via `knowledge/idioms/brin-tuple-format.md`).



### brin_revmap
The BRIN range map: the logical structure (backed by special revmap pages) that maps each block range number to the TID of its summary index tuple, letting a scan jump from a heap range directly to its summary. `brinRevmapAccess`/`brinGetTupleForHeapBlock` are its read path. [inferred] (`brin_revmap.c:1` — via `knowledge/idioms/brin-revmap.md`).



### brin_xlog
The BRIN WAL-replay module (`src/backend/access/brin/brin_xlog.c`): `brin_redo` dispatches one handler per `XLOG_BRIN_*` op code to reconstruct BRIN regular and revmap pages during recovery, and `brin_mask` masks non-deterministic bytes for consistency checking. A subtle invariant is that the regular page's block number is recovered from `BufferGetBlockNumber` after locking rather than carried in the record. [verified-by-code] (`brin_xlog.c:71-115` — via `knowledge/files/src/backend/access/brin/brin_xlog.c.md`).



### BrinDesc
The in-memory descriptor for a BRIN index that caches the opclass support
procedures and per-column metadata needed to build, union, and consult range
summaries without re-reading the metapage each time. [verified-by-code] (via
`knowledge/idioms/brin-tuple-format.md`).



### bringetbitmap
The BRIN `amgetbitmap` implementation: it scans the revmap + range tuples, runs each opclass `consistent` function against the query, and `tbm_add_page`s every heap range that might match, producing a lossy TID bitmap that the heap scan then rechecks. [verified-by-code] (via `knowledge/idioms/brin-summarize-and-scan.md`).



### brinGetTupleForHeapBlock
The BRIN revmap reader (`brin_revmap.c`) — the scan hot path — that, given a heap block number, follows the reverse map to the index tuple summarizing the range containing that block. [verified-by-code] (via `knowledge/idioms/brin-revmap.md`).



### brininsert
BRIN's `aminsert` implementation: it updates the summarising range tuple covering the heap block that received the new row, and can trigger autosummarization when a row first lands on a fresh page range. [verified-by-code] (`brin.c:398-422` — via `knowledge/files/src/backend/access/brin` docs).



### BrinMemTuple
The in-memory, deconstructed form of a BRIN range summary (parallel to the
packed on-disk `BrinTuple`), holding per-column `BrinValues` that union/add-value
support procedures mutate during summarization. [verified-by-code] (via
`knowledge/idioms/brin-tuple-format.md`).



### BrinTuple
The on-disk index tuple of a BRIN index — one per summarized block range —
carrying the per-column summary values (e.g. min/max for `minmax`) plus
null/allnulls flags. [verified-by-code] (via
`knowledge/idioms/brin-tuple-format.md`).



### bt_index_check
The lighter of amcheck's two B-tree verifiers: it checks page-level and parent-child invariants of an index while holding only an `AccessShareLock`, as opposed to `bt_index_parent_check`'s stronger, more thorough (and more locking) pass. [from-comment] (via `knowledge/issues/amcheck.md`).



### bt_multi_page_stats
A pageinspect function (`btreefuncs.c`) reporting `bt_page_stats`-style metadata for a range of B-tree pages in one call. [from-docs] (via `knowledge/subsystems/contrib-pageinspect.md`).



### bt_rootdescend
amcheck's nbtree verification routine that, for each non-pivot leaf tuple, drives `_bt_search` from the root back down to confirm the tuple is reachable through the tree's downlinks; a discrepancy means index corruption and the backend dies. [verified-by-code] (`verify_nbtree.c:3008-3058` — via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### btdeletedpagedata
`BTDeletedPageData` is the nbtree on-page structure recording when a page was half/fully deleted (its safe-xid), so a recycled page is not reused until no scan can still land on it. [verified-by-code] (via `knowledge/files/src/include/access/nbtree.h.md`).



### BTORDER_PROC
The B-tree opclass support-function slot number 1 — the 3-way comparison function (returning <0/0/>0) every btree opclass must supply. It is the first of the btree support slots (`BTSORTSUPPORT_PROC`, `BTINRANGE_PROC`, `BTEQUALIMAGE_PROC`, `BTOPTIONS_PROC`, `BTSKIPSUPPORT_PROC` being 2..6). [verified-by-code] (`nbtree.h` — via `knowledge/files/src/include/access/nbtree.h.md`).



### BTP_HALF_DEAD
The nbtree page flag marking a leaf partway through deletion (unlinked from its parent but not yet from the leaf level) — the intermediate state of the two-stage page-deletion protocol. [verified-by-code] (`nbtree.h` — via `knowledge/subsystems/access-nbtree.md`).



### BTP_HAS_FULLXID
The nbtree page flag (a recent addition) indicating a deleted page's special area stores a full 64-bit XID (`BTDeletedPageData`) instead of a 32-bit one, so page recycling survives XID wraparound. [verified-by-code] (`nbtree.h:76-85` — via `knowledge/subsystems/access-nbtree.md`).



### BTP_INCOMPLETE_SPLIT
The nbtree page flag marking a page whose split completed on the child but whose parent downlink insertion has not yet finished; a later inserter (or `_bt_finish_split`) must complete it, and it can persist across crashes. [verified-by-code] (`nbtree.h:76-85` — via `knowledge/subsystems/access-nbtree.md`).



### BTPageIsRecyclable
The nbtree predicate testing whether a previously deleted index page is now safe to reuse — i.e. its deletion is old enough that no concurrent scan could still be following a stale pointer to it. [verified-by-code] (`nbtpage.c:874-1007` — via `knowledge/files/src/backend/access/nbtree/nbtpage.c.md`).



### BTPageOpaqueData
The nbtree per-page special-space struct (`nbtree.h`) holding sibling links (`btpo_prev`/`btpo_next`), level, and flag bits (leaf/root/deleted/incomplete-split); it is the header every btree page carries after its line pointers. [verified-by-code] (via `knowledge/subsystems/access-nbtree.md`).



### btpo_flags
The `BTP_*` flag-bits field in an nbtree page's special-space opaque data, recording page state (leaf/root/deleted/half-dead/incomplete-split). [verified-by-code] (`nbtree.h:76-85` — via `knowledge/subsystems/access-nbtree.md`).



### btpo_level
The nbtree page's tree-level field in its special-space opaque data — 0 marks a leaf, higher values are internal levels up toward the root. [verified-by-code] (`nbtree.h` — via `knowledge/subsystems/access-nbtree.md`).



### btree_gist
The contrib module providing GiST opclasses for the data types that normally only have B-tree support (ints, floats, dates, text, etc.). This lets those types participate in GiST-only features such as exclusion constraints and KNN distance ordering within a single multi-column GiST index. [verified-by-code] (via `knowledge/files/contrib/btree_gist/btree_gist.c.md`).



### BTSORTSUPPORT_PROC
The B-tree opclass support-function slot number (2) for an optional sort-support function, sitting between `BTORDER_PROC` (1) and `BTINRANGE_PROC` (3) in the 1..6 nbtree support-proc slot range. It lets an opclass provide an optimized comparator for sorting. [verified-by-code] (`nbtree.h` — via `knowledge/files/src/include/access/nbtree.h.md`).



### btvacuumscan
The nbtree index-vacuum scan (`nbtree.c`) — `btbulkdelete` wraps it in `PG_ENSURE_ERROR_CLEANUP` and it walks every block calling `btvacuumpage` to delete index tuples pointing at dead heap TIDs and reclaim empty pages. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtree.c.md`).



### BUCKET_TO_BLKNO
The hash-AM macro (`hash.h`) translating a logical bucket number into the physical block number of the bucket's primary page, accounting for the split-point/`spares[]` allocation layout. [verified-by-code] (via `knowledge/idioms/hash-page-layout.md`).



### buf_id
The zero-based slot index of a buffer in the buffer pool array. For local (temp-table) buffers the user-facing `Buffer` handle is derived as `-buf_id - 1`, mirroring the negative encoding that distinguishes local from shared buffers. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/localbuf.c.md`).



### buf_internals
`src/include/storage/buf_internals.h` — the private buffer-manager header defining `BufferDesc`, the atomic packed `state` field (reference count + usage count + flag bits in one `pg_atomic_uint32`), `BufferTag`, and the buffer-mapping hash-table interface. Included only by buffer-manager internals (`bufmgr.c`, `freelist.c`, `localbuf.c`), not by general backend code. [verified-by-code] (via `knowledge/files/src/include/storage/buf_internals.h.md`).



### buf_state
The packed 64-bit atomic word of a `BufferDesc` (`bufHdr->state`), read via `pg_atomic_read_u64`, that co-locates the buffer's refcount, usagecount, and status flags (dirty, valid, IO-in-progress, pin-waiter) so they can be CAS-updated together. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### buffer (shared buffer)
A `BLCKSZ`-sized page slot in the shared buffer pool, the cache between
backends and the storage manager. Each buffer has a fixed-size `BufferDesc`
header carrying its page identity (`tag`) and an atomic 64-bit `state` packing
refcount, usagecount, flags, and content-lock bits; pool and headers are
allocated in shared memory at startup. [verified-by-code]
(`buf_internals.h:326-359`, `buf_init.c:24-145` — via
`knowledge/subsystems/storage-buffer.md`).



### BUFFER_LOCK_EXCLUSIVE
The mode argument to `LockBuffer` taking a buffer's content lock for writing
(vs `BUFFER_LOCK_SHARE` for reading, `BUFFER_LOCK_UNLOCK` to release). It is the
short-lived LWLock guarding a page's bytes, distinct from the buffer pin that
keeps the page resident. [verified-by-code] (`brin_pageops.c:115` — via
`knowledge/files/src/backend/access/brin/brin.c.md`).



### BUFFER_LOCK_SHARE
The mode argument to `LockBuffer` for taking a shared content lock on a
buffer — multiple readers may hold it concurrently but no writer can — as
opposed to `BUFFER_LOCK_EXCLUSIVE`. [from-comment] (via
`knowledge/subsystems/contrib-pgrowlocks.md`).



### BUFFER_LOCK_UNLOCK
The `LockBuffer` mode that releases a buffer's content lock — the counterpart to `BUFFER_LOCK_SHARE` and `BUFFER_LOCK_EXCLUSIVE`; `UnlockReleaseBuffer` combines it with dropping the pin. [verified-by-code] (via `knowledge/files/src/include/storage/bufmgr.h.md`).



### buffer_strategy_lock
The spinlock in `BufferStrategyControl` guarding the clock-sweep bookkeeping (`completePasses`, the freelist head, bgwriter procno); per the buffer-manager README, nothing else may be acquired while it is held. [from-README] (via `knowledge/subsystems/storage-buffer.md`).



### BufferAccessStrategy
A ring-buffer eviction policy object passed into the buffer manager so bulk
operations (sequential scans, VACUUM, COPY) reuse a small set of buffers
instead of flooding shared_buffers; built via `GetAccessStrategy` with a
`BufferAccessStrategyType` such as `BAS_BULKREAD`. [verified-by-code] (via
`knowledge/idioms/tableam-vtable-lifecycle.md`).



### BufferAlloc
The buffer-manager core that, given a page identity, either returns the
already-resident buffer or selects a victim via the clock-sweep, evicting and
remapping it; the heart of `ReadBuffer`'s lookup path. [verified-by-code]
(`bufmgr.c:2197-2351` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BufferBeginSetHintBits
The routine that acquires (or upgrades to) the share-exclusive content lock
required before writing hint bits, serializing hint-setters on a page so
concurrent visibility checks don't corrupt the line-pointer/infomask state.
[verified-by-code] (via `knowledge/idioms/hint-bits-setbufferdirty.md`).



### BufferDesc
The shared-memory descriptor for one buffer-pool slot: it holds the buffer
tag, a packed atomic `state` word (refcount + usagecount + flag bits), and the
content/IO lock machinery. `LockBufHdr` spins on the state word to get a
consistent view; the actual page bytes live in a separate buffer-blocks array.
[verified-by-code] (`bufmgr.c:7527` — via
`knowledge/files/src/include/storage/buf_internals.h.md`).



### BufferFinishSetHintBits
The bufmgr routine ending a hint-bit-setting batch on a shared buffer: after `BufferBeginSetHintBits` acquires the right to set hints (via a share-exclusive content-lock dance) and the caller ORs visibility bits like `HEAP_XMIN_COMMITTED` into tuple infomasks, a single `BufferFinishSetHintBits(buffer, true, true)` dirties the buffer once for the whole batch. `HeapTupleSatisfiesMVCCBatch` is the lone amortizing caller, threading an `SHB_*` state through the per-tuple checks and calling it only when state is `SHB_ENABLED`. [verified-by-code] (`bufmgr.c:7078-7087` — via `knowledge/idioms/hint-bits-setbufferdirty.md`).



### BufferGetBlockNumber
Returns the block number of the page currently held in a pinned buffer; used pervasively to recover the physical block when only the buffer handle is in hand (e.g. WAL redo recording an `INIT_PAGE`'d block). [verified-by-code] (`bufmgr.c` — via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BufferGetLSNAtomic
Reads a buffer page's LSN atomically (taking the buffer header spinlock on platforms without atomic 64-bit reads); visibility and hint-bit logic compare it against a commit LSN to decide whether WAL covering a change is already durable. [verified-by-code] (`bufmgr.c` — via `knowledge/idioms/hint-bits-setbufferdirty.md`).



### BufferGetPage
Inline accessor returning the `Page` (8 KB block image) backing a pinned buffer; the bridge from the buffer-manager handle to the page-layout API (`PageGetItem`, `PageGetMaxOffsetNumber`, …). [verified-by-code] (via `knowledge/files/src/include/storage/bufmgr.h.md`).



### BufferIsLocal
The macro that tests whether a `Buffer` handle refers to a backend-local
buffer (temp-table buffer, negative buffer number) rather than a shared-buffer-
pool buffer. Shared-pool routines such as `MarkBufferDirty` assert
`!BufferIsLocal(buffer)` so local buffers take the separate `localbuf.c` path.
[verified-by-code] (`bufmgr.c:7533-7565` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### BufferSetHintBits16
Atomically sets a 16-bit hint-bit mask on a shared buffer's page under the deferred-hint-bit rule, the helper that lets visibility checking record xmin/xmax commit status without a full exclusive content lock. [verified-by-code] (`heapam_visibility.c` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### BufferSync
The buffer manager's flush primitive that writes out all dirty shared buffers during a checkpoint; it is the long pole of a checkpoint and its work is spread over `checkpoint_completion_target` of the inter-checkpoint interval. It runs as one of the `CheckPointGuts` phases after the `XLOG_CHECKPOINT` record records the redo-start LSN. [verified-by-code] (`bufmgr.c` — via `knowledge/idioms/checkpoint-coordination.md`).



### BufferTag
The `(relfilelocator, forknum, blocknum)` key identifying which on-disk
block a shared buffer currently holds; it is hashed through the partitioned
buffer-mapping table to locate the owning buffer. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### BufferUsage
The instrumentation counter struct (`instrument.c`) accumulating shared/local buffer hits, reads, dirtied and written during execution (and optionally planning); surfaced by `EXPLAIN (BUFFERS)` and accumulated per-statement by pg_stat_statements. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### BufFile
A buffered, segmented temporary-file abstraction that transparently spans the
1 GB per-segment limit and is tracked for cleanup at transaction or query end.
The executor uses `BufFile`s to spill data that exceeds `work_mem` — e.g. the
per-batch outer/inner files of a multi-batch hash join. [from-comment] (via
`knowledge/files/src/backend/executor/nodeHashjoin.c.md`).



### BufMapping
The buffer manager's own family of partition LWLocks guarding the shared
buffer-lookup hash table; it is a separate partition family from the
heavyweight lock-manager partitions, and the lock-ordering relationship between
the two is unverified (issue U2). [from-README] (via
`knowledge/subsystems/storage-lmgr.md`).



### BufMappingLock
The partitioned LWLock tranche guarding the shared buffer-lookup hash table (buffer tag → buffer id); partitioning by hash reduces contention on concurrent lookups and inserts. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/buf_table.c.md`).



### BuildAccumulator
The GIN build-time key accumulator (`ginbulk.c`): during index build (and pending-list cleanup) it accumulates per-key posting lists in memory up to `maintenance_work_mem`, then flushes each merged group via `ginEntryInsert`. [verified-by-code] (via `knowledge/files/src/backend/access/gin/gininsert.c.md`).



### buildACLCommands
The pg_dump/dumputils helper that, given an object's current and baseline
ACLs, emits the GRANT/REVOKE statement sequence needed to recreate its
privileges. [verified-by-code] (via
`knowledge/files/src/bin/pg_dump/dumputils.h.md`).



### BuildIndexValueDescription
Formats the indexed column values of a tuple into a parenthesized "(col)=(val)" string for error messages such as unique-violation detail, respecting column privileges so unauthorized values are omitted. [verified-by-code] (`genam.c` — via `knowledge/files/src/backend/access/index/genam.c.md`).



### BuildTupleFromCStrings
Constructs a `HeapTuple` from an array of C strings by running each column's type input function against an `AttInMetadata`; the convenient (if allocation-heavy) row builder for set-returning functions returning text-shaped data. [verified-by-code] (via `knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md`).



### bulk_write
The smgr-level facility for populating a brand-new relation fork in bulk (CREATE INDEX, REINDEX, CLUSTER, table rewrites) while bypassing the shared buffer manager, avoiding buffer-lock and partition-lock contention. It buffers pages and writes them out in batches, WAL-logging as needed, then fsyncs the fork at the end. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



### BulkInsertState
The heap bulk-insert state returned by `GetBulkInsertState` and freed by `FreeBulkInsertState`; it caches a target buffer across `heap_insert` / `heap_multi_insert` / `heap_update` so repeated free-space lookups are avoided during a bulk load. [verified-by-code] (`heapam.c:1937` — via `knowledge/files/src/include/access/hio.h.md`).



### BulkWriteState
The `bulk_write.c` state (SMgrRelation + fork + use_wal flag) driving buffered bulk relation writes that bypass shared buffers — used by index build (`nbtsort.c`) and similar — batching page fills, WAL-logging, and flush. [verified-by-code] (`bulk_write.c:61-79` — via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



### BumpContext
The densest-packing MemoryContext type (PG 17+): it carries no per-chunk header
in production builds (`Bump_CHUNKHDRSZ = 0`) and stubs out `BumpFree` /
`BumpRealloc` with `elog(ERROR)`, so the only way to release its memory is
`MemoryContextReset` or `MemoryContextDelete`. [verified-by-code]
(`bump.c:645-682` — via `knowledge/subsystems/utils-mmgr.md`).



### BumpContextCreate
The constructor for a Bump memory context — an allocation-only arena that hands
out chunks by bumping a pointer and frees nothing until reset/delete, used where
all allocations share one short lifetime (e.g. tuplesort). [verified-by-code]
(via `knowledge/idioms/memory-context-api-and-dispatch.md`).



### CachedExpression
A stand-alone cached, planned expression (the single-expression analogue of a `CachedPlan`) that is invalidated by relevant catalog changes; used, for example, for partition constraint expressions. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### CachedFunction
The generic funccache base struct (`funccache.h:106-118`) that PL handlers embed as their first member so the shared function cache can manage them. It carries an `fn_hashkey` backpointer, `fn_xmin`/`fn_tid` invalidation-watch fields, a delete callback, and a `use_count`; it is keyed by a `CachedFunctionHashKey` (funcOid + trigger/event-trigger flags + trigOid + input collation + argtypes + call result type). [verified-by-code] (`funccache.md` — via `knowledge/files/src/include/utils/funccache.md`).



### CachedPlan
The executable plan produced from a `CachedPlanSource`, either generic
(parameter-independent, reused) or custom (re-planned for specific parameter
values). Its refcount is tracked through a `ResourceOwner` and released after
locks at end of the owning scope. [verified-by-code] (`plancache.c:117` — via
`knowledge/files/src/backend/utils/cache/plancache.c.md`).



### CachedPlanSource
The plancache structure representing one parsed-but-reusable query source: it
caches the raw/analyzed parse tree and produces a `CachedPlan` (generic or
custom) that survives across executions. PL/pgSQL's "simple expression"
fast-path keys off a statement compiling to exactly one `CachedPlanSource`.
[from-comment] (`pl_exec.c:8233` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### CacheInvalidateHeapTuple
The catalog-DML entry point that registers the invalidation messages implied
by inserting/updating/deleting a catalog tuple, so that dependent relcache and
syscache entries get flushed at commit. [verified-by-code] (`inval.c:1568` —
via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### CacheMemoryContext
The long-lived `MemoryContext` (a child of `TopMemoryContext`) that holds
relcache, catcache, and plan-cache entries for the life of the backend.
Allocations placed here are deliberately never freed per-query, so leaking into
it is a true backend-lifetime leak. [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### CacheRegisterRelcacheCallback
The registration call that installs a callback fired whenever any relcache entry is invalidated; the callback receives the OID of the invalidated relation (or `InvalidOid` for a full reset). It is the relcache-wide counterpart to `CacheRegisterSyscacheCallback`, which fires per specific syscache entry. [verified-by-code] (`inval.c` — via `knowledge/idioms/cache-invalidation-registration.md`).



### CacheRegisterSyscacheCallback
The registration call by which a backend module asks the shared-invalidation machinery to fire a callback whenever a specific syscache entry (identified by cache id, e.g. `PROCOID`, `TYPEOID`, `AUTHOID`) is invalidated; the callback receives the hash value of the invalidated tuple (or 0 for a full reset). The plan cache, typcache, and superuser cache all use it so their derived state is flushed when the underlying catalog row changes. [verified-by-code] (`inval.h:24` — via `knowledge/files/src/include/utils/inval.h.md`).



### CALLED_AS_TRIGGER
The macro a SQL-callable C function uses to detect whether it was invoked as a trigger (by inspecting `fcinfo->context`); a language-handler or polymorphic function tests it to branch between trigger and normal call conventions. Its partner is `CALLED_AS_EVENT_TRIGGER`. [verified-by-code] (`source/src/include/commands/trigger.h` — via `knowledge/docs-distilled/plhandler.md`).



### CallSyscacheCallbacks
The inval dispatcher that invokes every callback registered with `RegisterSyscacheCallback` for a given syscache when a relevant tuple is invalidated, letting subsystems (planner, typcache, ...) drop derived state. [verified-by-code] (`inval.c:1895` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### cancel_pressed
The psql global flag set true by `psql_cancel_callback` on SIGINT when `sigint_interrupt_enabled` is off (otherwise the handler `siglongjmp`s out); downstream loops poll it to abort. The longjmp arm is `#ifndef`-stripped on WIN32, which handles Ctrl-C differently. [from-comment] (via `knowledge/files/src/bin/psql/common.c.md`).



### canonicalize_path
Normalises a filesystem path in place, collapsing `.`/`..` segments and redundant separators; used by frontend tools and by server functions such as `genfile.c` before path-safety checks. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/genfile.c.md`).



### CaseTestExpr
The placeholder Expr node standing in for "the value being tested" inside a CASE (or the source datum of an assignment/coercion), evaluated by reading the caseValue slot the surrounding node set rather than by recomputing the subexpression. [verified-by-code] (`primnodes.h` — via `knowledge/files/src/include/nodes/primnodes.h.md`).



### catalog (system catalog)
The set of on-disk tables (`pg_class`, `pg_proc`, `pg_type`, …) that hold all
database metadata — every relation, type, function, and operator is a row in a
catalog. The initial contents are bootstrapped from `.dat`/`.h` files via the
BKI mechanism; editing catalogs has strict OID and `catversion` rules.
[from-README] (via `knowledge/idioms/catalog-conventions.md`).



### CATALOG_VARLEN
The C macro that brackets the variable-length and nullable trailing columns of
a system-catalog struct in its `pg_*.h` definition. The compiled C struct omits
everything inside `#ifdef CATALOG_VARLEN`, since those fields cannot be accessed
as fixed-offset members and must go through `heap_getattr`/deform.
[verified-by-code] (`pg_largeobject.h:38` — via
`knowledge/files/src/include/catalog/pg_largeobject.h.md`).



### CATALOG_VERSION_NO
The catalog version number in `catversion.h`; a mismatch between a server and
its data directory's value makes the server refuse to start. Any change to the
on-disk catalog layout — new catalog column, changed BKI data, or a changed
`pg_node_tree` out/read format serialized into a catalog — requires bumping it.
[from-comment] (`pg_propgraph_label_property.h:42` — via
`knowledge/files/src/include/catalog/pg_propgraph_label_property.h.md`).



### catalog_xmin
The oldest transaction id whose catalog rows a logical replication slot still
needs; the `ProcArray`/`GetOldestSafeDecodingTransactionId` machinery holds the
global catalog horizon back to it so vacuum does not remove catalog tuples a
slot might still decode. Distinct from a slot's data `xmin`. [verified-by-code]
(via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).



### CatalogCacheCreateEntry
Builds and inserts a new `CatCTup` into a catcache bucket on a lookup miss,
caching a catalog row keyed by its lookup arguments so subsequent
`SearchSysCache` calls hit in memory. [verified-by-code] (via
`knowledge/idioms/syscache-catcache-internals.md`).



### CatalogId
In `pg_dump`, a `(tableoid, oid)` pair that uniquely identifies a dumped catalog object; it keys the archive's object lookup and dependency graph. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/common.c.md`).



### CatalogSnapshot
A cached MVCC snapshot used specifically for catalog scans, pseudo-registered by snapmgr.c and refreshed when invalidation messages arrive, so catalog reads see the latest committed catalog state without taking a fresh snapshot on every lookup. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### CatalogTupleDelete
Deletes one catalog row by TID via `simple_heap_delete`; no index maintenance is needed because the dead heap line pointer makes the matching index entries unreachable. The delete counterpart of `CatalogTupleInsert`. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### CatalogTupleInsert
The universal "write one new row into a system catalog" helper: opens the relation's indexes, does `simple_heap_insert`, runs `CatalogIndexInsert` to add matching index entries, then closes the indexes. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### CatalogTupleUpdate
Updates a catalog row via `simple_heap_update` and inserts fresh index entries through `CatalogIndexInsert`; the old index entry is reclaimed with the dead tuple, since at the heap level an update is a delete+insert. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### CatCache
A single catalog cache: it indexes one system catalog by one specific N-tuple of key columns (1 ≤ N ≤ `CATCACHE_MAXKEYS = 4`), holding `HeapTuple` copies in hash buckets and supporting negative entries that mark "no row matches this key". It is the substrate beneath syscache and lsyscache. [verified-by-code] (`catcache.h:35` — via `knowledge/subsystems/utils-cache.md`).



### catcache (catalog cache)
The per-backend cache of individual system-catalog rows keyed by lookup key
(e.g. a `pg_proc` row by OID), backing the `SearchSysCache` API. Entries are
negative-cacheable and invalidated by shared-invalidation messages when another
backend changes the underlying catalog. [from-comment] (via
`knowledge/files/src/backend/utils/cache/catcache.c.md`).



### CATCACHE_MAXKEYS
The compile-time maximum (4) number of key columns on which a system-catalog cache (catcache) may be indexed; it bounds the `SearchSysCacheN` family. [verified-by-code] (via `knowledge/files/src/include/utils/catcache.h.md`).



### CatCacheInvalidate
The catcache.c routine (callable only from inval.c) that flushes the cached entries matching an invalidated tuple's keys; part of the catalog-cache coherence machinery driven by shared-invalidation messages. [verified-by-code] (`catcache.c:643` — via `knowledge/files/src/backend/utils/cache/catcache.c.md`).



### CatCList
A cached *list* of `CatCTup`s answering a non-unique-key catcache query (e.g. all pg_amop rows for an opfamily); it transitively pins its member tuples for the list's lifetime. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### CatCTup
One cached catalog row inside a `CatCache`: a positive entry wrapping a `HeapTuple` copy, or a key-only negative entry marking "row absent". Allocated as a single chunk so the tuple body is contiguous with its header. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/catcache.c.md`).



### cheapest_startup_path
The `pathlist` member with the lowest startup cost, selected by `set_cheapest`; used when a plan needs the first row quickly (e.g. `LIMIT`, cursors) rather than the cheapest total. [verified-by-code] (via `knowledge/data-structures/reloptinfo.md`).



### cheapest_total_path
The member of a `RelOptInfo.pathlist` with the lowest total cost, chosen by `set_cheapest`; upper planning stages chain off each rel's `cheapest_total_path` when total runtime (not fast-start) is what matters. [verified-by-code] (via `knowledge/data-structures/reloptinfo.md`).



### check_default_partition_contents
The routine (with `check_new_partition_bound`) that scans an existing DEFAULT partition when a new sibling is attached, erroring if any row would now belong to the new partition. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### CHECK_ENCODING_CONVERSION_ARGS
The boilerplate macro every encoding-conversion procedure invokes first to assert it was called with the source/destination encoding ids it was registered for and a non-negative length. It turns a mis-registered conversion proc into a clean elog rather than a corruption. [inferred] (via `knowledge/files/src/backend/utils/mb/conversion_procs/README.md`).



### CHECK_FOR_INTERRUPTS
The macro every long-running loop must call so a backend can act on a pending
cancel, terminate, or recovery-conflict signal at a safe point rather than
mid-critical-section. It expands to a cheap flag test that, when set, longjmps
out via `ProcessInterrupts`. Omitting it from a tight loop makes that loop
un-cancellable. [verified-by-code] (`pl_exec.c:2026` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### check_function_bodies
GUC that, when on (default), makes a language validator test-compile a new function's body at `CREATE FUNCTION` time; `plpgsql_validator` sets up a fake fcinfo and calls `plpgsql_compile(..., true)` only when it is on. pg_dump emits `SET check_function_bodies = false` so restores don't fail on forward references. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



### check_hba
The `pg_hba.conf` matcher: `check_hba()` walks the parsed `parsed_hba_lines` list with `foreach`, testing each connection's role / database / address against the rules to select the authentication method. [verified-by-code] (via `knowledge/docs-distilled/auth-pg-hba-conf.md`).



### check_hook
The optional validation callback in the GUC check/assign/show trio: it runs on a proposed new value, can reject it (returning false) or normalize/cook it into an `extra` blob, before `assign_hook` installs it. Custom GUCs supply one to enforce cross-setting constraints. [inferred] (`guc.c:5049` — via `knowledge/scenarios/add-new-guc.md`).



### check_loadable_libraries
The pg_upgrade preflight check that, for every loadable library referenced by the old cluster, verifies the corresponding `.so` actually loads in the new cluster before the upgrade proceeds; community proposals have pitched extending it into a plugin-name whitelist. [inferred] (via `knowledge/issues/include-replication.md`).



### check_password_hook
A pluggable global hook (`check_password_hook_type`) invoked from `CreateRole`/`AlterRole` to vet a new password's strength; the `passwordcheck` contrib module chains it. Exported alongside the `Password_encryption` GUC in `user.h`. [verified-by-code] (via `knowledge/files/src/backend/commands/user.c.md`).



### check_stack_depth
The recursion guard called at the top of every deeply-recursive backend routine; it compares the current stack pointer against `max_stack_depth` and `ereport(ERROR)`s before a runaway recursion can overflow the C stack and crash the backend. Recursive expression/parse-tree walkers and user-facing recursive functions (e.g. ltree, intarray bool-expression parsers) must call it on each level. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_bool.md`).



### checkCond
The recursive backtracking matcher at the heart of ltree's lquery engine: it walks an lquery's levels against an ltree's levels with per-level repetition counts (`{N,M}`), label variants (`a|b|c`), and match modifiers. Its unbounded backtracking is the basis for an A13 ReDoS-style concern echoed by pg_trgm's `pg_regcomp`. [verified-by-code] (`lquery_op.c:183` — via `knowledge/files/contrib/ltree/lquery_op.c.md`).



### CheckDeadLock
The deadlock detector entry point, invoked from `ProcSleep` after the
deadlock-timeout fires. It walks the lock wait-for graph looking for a cycle and,
if found, either rearranges wait queues to resolve a soft edge or signals the
current process to abort. [verified-by-code] (`proc.c:1856` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### CheckForSerializableConflictIn
The SSI hook a writer calls before modifying a page/tuple to detect a read-write dependency *into* its write (someone else read what it is about to change), recording the rw-antidependency that may later force a serialization-failure rollback. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/predicate.c.md`).



### CheckFunctionValidatorAccess
The permission gate a PL validator (`plpgsql_validator`, `plperl_validator`,
…) calls before inspecting a function body: it confirms the current user may
validate the target function/language, and the validator returns `VOID`
silently if access is denied. This keeps `CREATE FUNCTION`-time body checks from
leaking information to unprivileged callers. [verified-by-code]
(`pl_handler.c:441` — via `knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



### checkpoint
A point at which all dirty shared buffers are flushed and a WAL record is
written so crash recovery can start replaying from there rather than the start
of the log. `CreateCheckPoint` performs the work; the redo pointer it records
bounds how much WAL recovery must scan. [from-comment] (via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### checkpoint_completion_target
GUC (default 0.9) spreading a checkpoint's buffer writes across that fraction of the `checkpoint_timeout` interval to smooth I/O; the buffer manager throttles the checkpoint write loop against it. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### checkpoint_timeout
GUC setting the maximum time between automatic (time-driven) checkpoints; the checkpointer starts a checkpoint when this elapses, distinct from WAL-volume-driven and backend-requested checkpoints. [verified-by-code] (via `knowledge/files/src/backend/postmaster/checkpointer.c.md`).



### checkpointer
The dedicated auxiliary process that performs checkpoints (and restartpoints on
standbys), spreading the buffer flush over time per
`checkpoint_completion_target`. Backends request checkpoints by signalling it
rather than running `CreateCheckPoint` themselves. [from-comment] (via
`knowledge/files/src/backend/postmaster/checkpointer.c.md`).



### checksum_payload
The backup-manifest entry field holding a file's raw checksum bytes (paired with `checksum_length`), consumed by `pg_combinebackup`/`pg_verifybackup` when validating a reconstructed data directory. [verified-by-code] (via `knowledge/files/src/bin/pg_combinebackup/load_manifest.h.md`).



### chgParam
The bitmapset on a `PlanState` listing parameter ids whose values changed since the node last ran; a non-empty set on rescan forces the subtree to recompute rather than reuse buffered output. It is how correlated subplans and nestloop inner sides know to re-execute. [inferred] (via `knowledge/idioms/epq-recheck-flow.md`).



### choose_custom_plan
The plancache heuristic deciding generic vs custom plan for a parameterized statement: one-shot ⇒ custom, no params ⇒ generic, the first five executions are always custom and then averaged cost is compared, with the `plan_cache_mode` GUC and cursor options able to override. [verified-by-code] (`plancache.c:1175` — via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### chunk_id
The first component of the `(chunk_id, chunk_seq)` key that indexes a TOAST value's out-of-line chunk chain; every out-of-lined varlena is stored as fixed-size chunks in the table's TOAST relation under one shared `chunk_id`. [from-comment] (via `knowledge/files/src/backend/access/common/toast_internals.c.md`).



### chunk_seq
The ordinal (second) component of the TOAST `(chunk_id, chunk_seq)` key, numbering the fixed-size chunks of one out-of-line value in sequence so the detoast path can reassemble them in order. [from-comment] (via `knowledge/files/src/backend/access/common/toast_internals.c.md`).



### clauselist_selectivity
The optimizer routine that estimates the combined selectivity of a list of restriction clauses, applying per-clause estimates plus any applicable extended (multivariate) statistics, with an independence assumption for the remainder. [inferred] (via `knowledge/idioms/extended-statistics-statext.md`).



### cleanuplock
`CleanUpLock` (`lock.c:1746`) garbage-collects a heavyweight `LOCK` shared-hash entry once its `nRequested` count reaches zero. [from-README] (via `knowledge/subsystems/storage-lmgr.md`).



### client_encoding
The session GUC naming the character-set encoding of data exchanged with the client; the backend transcodes between it and the database (server) encoding on input and output. Functions that synthesize text (e.g. pgcrypto decrypt) must produce bytes valid in the client encoding or risk encoding-violation errors at send time. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### client_finished_auth
The libpq latch that records the client actually completed an authentication handshake (SCRAM verifier checked, OAuth bearer sent, etc.); `require_auth` insists it is set even for `AUTH_REQ_OK` so a server can't skip auth by simply answering "ok". [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-auth.c.md`).



### client_min_messages
GUC setting the minimum elevel sent to the client; during authentication `ClientAuthInProgress` overrides it so only `>= ERROR` reaches the client (many clients can't handle NOTICE mid-auth, and it is a security consideration). [from-comment] (via `knowledge/files/src/backend/utils/error/elog.c.md`).



### ClientAuthentication
The backend routine that runs the configured authentication method (matched
from `pg_hba.conf` via the parsed `HbaLine` rules) against a newly connected
client, before the session is allowed to proceed. It is the chokepoint every
connection passes through during backend startup. [verified-by-code]
(via `knowledge/files/src/backend/tcop/backend_startup.c.md`).



### ClientAuthentication_hook
The hook fired from `auth.c`'s `ClientAuthentication` after the authentication method runs but before the backend proceeds, letting a module (e.g. sepgsql, auth_delay) inspect or veto the connection; modules install it from `_PG_init`. [verified-by-code] (`label.c:421-422` — via `knowledge/files/contrib/sepgsql/label.c.md`).



### ClientConnectionInfo
The shared-memory-propagated struct (`libpq-be.h`) carrying the authenticated identity (`authn_id`), authentication method, and SSL/GSS details of a connection, so parallel workers inherit the leader's client-auth context. [verified-by-code] (via `knowledge/subsystems/libpq-backend.md`).



### ClientKey
In SCRAM authentication, the HMAC-derived key the client proves possession of;
the server stores only its hash (`StoredKey`) so a stolen verifier cannot
directly impersonate the client. [verified-by-code] (via
`knowledge/subsystems/libpq-backend.md`).



### ClientSignature
In SCRAM authentication, the HMAC of the stored key over the auth message
(`HMAC(StoredKey, AuthMessage)`); XOR-ing it with the `ClientProof` the client
sent recovers a candidate `ClientKey`, whose hash the server compares to the
stored key. This is how the server verifies the client knew the password without
ever storing it. [verified-by-code] (`auth-scram.c:1147` — via
`knowledge/files/src/backend/libpq/auth-scram.c.md`).



### ClockSweepTick
Advances the buffer-pool clock hand by one slot (`freelist.c`), decrementing the victim candidate's `usage_count`; `StrategyGetBuffer` sweeps with it until it can CAS-pin an unpinned, zero-usage-count buffer to evict. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/freelist.c.md`).



### CLOG
The *commit log* (on disk as `pg_xact`) — a dense SLRU-backed array of two status bits per transaction id recording in-progress / committed / aborted / sub-committed. Visibility checks consult it through `TransactionIdDidCommit` / `TransactionIdDidAbort`; new pages are extended under `XidGenLock` via `ExtendCLOG`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/clog.c.md`).



### clog (CLOG / pg_xact)
The commit-log SLRU that stores two status bits per transaction (in-progress /
committed / aborted / sub-committed), consulted by visibility checks to resolve
whether a tuple's xmin/xmax committed. It lives under `pg_xact/` and is driven
through `TransactionIdSetTreeStatus` / `TransactionIdGetStatus`. [from-comment]
(via `knowledge/files/src/backend/access/transam/clog.c.md`).



### clog_redo
The CLOG resource manager's WAL redo routine (`clog.c::clog_redo`) — replays `CLOG_ZEROPAGE` and `CLOG_TRUNCATE` records so a recovering standby keeps its `pg_xact` SLRU in step with the primary. Per-record commit-status bit changes are *not* WAL-logged here; they ride the transaction's own commit record. [verified-by-code] (via `knowledge/files/src/backend/access/rmgrdesc/clogdesc.c.md`).



### cmax
The command id of the statement that deleted a tuple within its deleting transaction, held in `t_cid`; paired with `cmin` for self-modification visibility. If both `cmin` and `cmax` are needed for the same tuple in one transaction, PostgreSQL substitutes a synthetic combo CID resolved through `combocid.c`. [verified-by-code] (via `knowledge/idioms/combocid-handling.md`).



### CMD_SELECT
The `CmdType` enum value tagging a `Query` or `PlannedStmt` as a `SELECT`, as opposed to `CMD_INSERT` / `CMD_UPDATE` / `CMD_DELETE` / `CMD_UTILITY`. [verified-by-code] (via `knowledge/files/src/backend/parser/analyze.c.md`).



### CMD_UTILITY
The `CmdType` enum value tagging a `Query` that wraps a utility (DDL) statement rather than an optimizable DML/SELECT query; such a Query carries the untransformed raw statement in `utilityStmt` (non-NULL iff `commandType == CMD_UTILITY`). DDL is not analyzed at parse-analyze time — the default branch of `transformStmt` wraps it as `Query{CMD_UTILITY, utilityStmt=raw}` and real analysis is deferred to `ProcessUtility` via `parse_utilcmd.c`; `pg_plan_query` refuses (returns NULL for) CMD_UTILITY Querys. [verified-by-code] (`parser-and-rewrite.md` — via `knowledge/subsystems/parser-and-rewrite.md`).



### CmdType
The enum tagging a query/plan's operation — `CMD_SELECT`, `CMD_INSERT`,
`CMD_UPDATE`, `CMD_DELETE`, `CMD_MERGE`, `CMD_UTILITY`, `CMD_NOTHING` — that
drives executor and rewriter dispatch. [verified-by-code] (via
`knowledge/idioms/trigger-transition-tables.md`).



### cmin
The command id of the statement that inserted a tuple within its inserting transaction; used so a transaction does not see rows created by later commands in the same statement's snapshot. When a tuple is both inserted and deleted in one transaction, `cmin` and `cmax` share `t_cid` and are disambiguated by a combo CID. [verified-by-code] (via `knowledge/idioms/combocid-handling.md`).



### coerce_type
The parse-analysis routine (`parse_coerce.c`) that returns an expression converted to a requested target type — inserting a cast, a `CoerceViaIO`, or a relabel as the cast catalog dictates; `can_coerce_type` is the predicate-only counterpart. [verified-by-code] (via `knowledge/files/src/backend/parser/parse_coerce.c.md`).



### CoerceToDomain
An expression node that applies a domain's constraints (`NOT NULL`, `CHECK`) when a value is cast to a domain type; the checks run at expression-evaluation time. [verified-by-code] (via `knowledge/files/src/backend/parser/parse_coerce.c.md`).



### CollectedCommand
The captured DDL parse tree plus the OIDs of objects it created, accumulated
during command execution so an event trigger can later deparse it back to
reconstructable SQL via `deparse_utility_command`. [verified-by-code] (via
`knowledge/idioms/ddl-deparse-via-event-triggers.md`).



### ColumnRef
The raw parse-tree node representing an unresolved column reference (a name or dotted name path) in a SQL expression, before namespace resolution. During parse analysis `transformColumnRef` resolves it against the range table (via `parse_relation.c`) into a `Var` — or, where a parse hook applies, a `Param` — and `transformExprRecurse` dispatches to it on `T_ColumnRef`. [verified-by-code] (`parse_expr.c:47` — via `knowledge/files/src/backend/parser/parse_expr.c.md`).



### ComboCID
An in-memory mapping that packs a `(cmin, cmax)` pair into a single "combo" command id when one transaction both inserts and later deletes the same tuple; it keeps the on-disk `t_cid` field a single 32-bit slot while preserving both command ids for visibility checks. Its state is serialized to parallel workers. [verified-by-code] (via `knowledge/files/src/backend/utils/time/combocid.c.md`).



### CommandComplete
The wire-protocol message the backend sends after a SQL command finishes,
carrying the command tag (e.g. `INSERT 0 5`, `SELECT 12`). The tag and its
optional row count come from `cmdtaglist.h`; the row-count flag is wire-
significant, so flipping it for an existing tag breaks libpq clients that parse
the tag. [verified-by-code] (via
`knowledge/files/src/include/tcop/cmdtaglist.h.md`).



### CommandCounterIncrement
Advances the backend's command counter within a transaction so rows written by an earlier command become visible to later commands in the same transaction; it also flushes pending invalidation messages. Routinely called between the catalog-modifying steps of DDL. [verified-by-code] (`inval.c:1` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### CommandCounterIncrement (CCI)
Bumps the command counter within the current transaction so that changes made
by earlier commands become visible to later commands in the same transaction,
while still being invisible to other transactions. Catalog-mutating code calls
it between steps (e.g. after inserting a pg_class row, before inserting
dependent rows) so the next lookup sees the new tuple. [verified-by-code]
(`xact.c:1130` — via
`knowledge/files/src/backend/access/transam/xact.c.md`).



### CommandDest
The enum of possible result destinations (Remote, RemoteExecute, SPI, Tuplestore, Copy, None, …) defined in `dest.h`; `CreateDestReceiver` switches on it to build the matching `DestReceiver`. [verified-by-code] (`dest.h:85-100` — via `knowledge/files/src/include/tcop/dest.h.md`).



### CommandEndInvalidationMessages
The hook fired at the end of each command that flushes the locally-queued
catalog invalidation messages — both applying them to this backend's caches and
adding them to the list broadcast at commit. [verified-by-code] (via
`knowledge/idioms/syscache-invalidation-flow.md`).



### CommandId
A 32-bit counter (`cid`) distinguishing commands within a single transaction so
a statement does not see rows its own later commands produced (the
`cmin`/`cmax` of a tuple). It is reset each transaction; only commands that
write advance it. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/xid.c.md`).



### CommandTag
The enum identifying each SQL command kind (SELECT, INSERT, CREATE TABLE, …);
`cmdtag.c` holds its static metadata table and `GetCommandTagName` maps it to
the user-visible command-completion string. [verified-by-code] (`cmdtag.c:9` —
via `knowledge/files/src/backend/tcop/cmdtag.c.md`).



### commit timestamp (commit_ts)
An optional SLRU (`pg_commit_ts/`) that records the wall-clock commit time and
origin of each transaction when `track_commit_timestamp` is on, queryable via
`pg_xact_commit_timestamp`. It is primarily used by conflict detection in
logical replication. [from-comment] (via
`knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### commit_cb
The logical-decoding output-plugin callback `commit_cb(ctx, txn, commit_lsn)` invoked at end of a decoded transaction; it (and its siblings `begin_cb`/`change_cb`) only fire once snapshot building reaches CONSISTENT, and it can read `txn->origin_id`. [verified-by-code] (via `knowledge/idioms/output-plugin-callbacks.md`).



### commit_delay
A microsecond sleep taken by the group-commit leader inside `XLogFlush` before flushing WAL, batching concurrent commits into a single fsync; default 0. Paired with `commit_siblings`. [verified-by-code] (via `knowledge/docs-distilled/wal-configuration.md`).



### commit_siblings
The minimum number of concurrently-active transactions required before `commit_delay`'s group-commit sleep engages (default 5); together they form PostgreSQL's group-commit tuning pair. [from-README] (via `knowledge/docs-distilled/runtime-config-wal.md`).



### commit_ts
The SLRU-backed subsystem that stores, per committed transaction, its commit timestamp and originating `ReplOriginId`; active only when `track_commit_timestamp` is on. It is the backing store for `pg_xact_commit_timestamp()` and feeds last-update-wins conflict resolution in logical replication. [verified-by-code] (`commit_ts.c` — via `knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### CommitTransaction
The xact.c routine that performs a top-level transaction commit: it fires
pre-commit callbacks, processes pending relation-file deletes via
`smgrDoPendingDeletes`, writes and flushes the commit WAL record
(`RecordTransactionCommit`), releases locks, and advances the proc's state. The
abort counterpart is `AbortTransaction`. [verified-by-code]
(`storage.c:673-735` — via
`knowledge/files/src/backend/catalog/storage.c.md`).



### CommitTransactionCommand
The top-level transaction-control routine called after each statement to advance
or finalize transaction state (commit an implicit xact, end a command within an
explicit block); paired with `StartTransactionCommand`. [verified-by-code] (via
`knowledge/idioms/commit-transaction-sequence.md`).



### CommonTableExpr
The parse node for one WITH-clause CTE: it carries the CTE name, column aliases, the subquery, and the `MATERIALIZED` / `NOT MATERIALIZED` flag; a Query collects them in its `cteList`. [verified-by-code] (via `knowledge/files/src/backend/parser/parse_cte.c.md`).



### CompactAttribute
The slimmed-down, cache-hot per-column descriptor cached in parallel with each `Form_pg_attribute` inside a `TupleDesc`; it is repopulated by `TupleDescFinalize` after manual descriptor edits so the deform hot path avoids touching the full catalog form. [verified-by-code] (via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### CompareType
A small backend-wide enum of named comparison semantics
(`COMPARE_LT`/`LE`/`EQ`/`GE`/`GT`/`NE`) decoupled from any one access method's
strategy numbers. It lets generic code request "the less-than operator" without
hardcoding btree strategy 1, and AMs translate `CompareType` to and from their
own strategy numbers. [verified-by-code] (via
`knowledge/files/src/include/access/cmptype.h.md`).



### compile_expr
One of the three callbacks in the JIT provider vtable (with `reset_after_error` and `release_context`); `compile_expr` JIT-compiles an expression-evaluation step into native code. [verified-by-code] (via `knowledge/subsystems/jit.md`).



### CompleteCachedPlan
The plancache routine (`plancache.c:393`) that "completes" a `CachedPlanSource` after analyze + rewrite: it attaches the query tree along with its dependency lists (`relationOids` for relcache deps, `invalItems` for syscache deps) and optionally reparents the source into long-lived memory. It is step two of the two-step create (`CreateCachedPlan` then `CompleteCachedPlan`); only after the later `SaveCachedPlan` does the source begin receiving sinval events. [verified-by-code] (`plancache.c:393` — via `knowledge/subsystems/utils-cache.md`).



### completePasses
The `BufferStrategyControl` counter recording how many full revolutions the clock sweep has made around the buffer pool; bumped under `buffer_strategy_lock` whenever `nextVictimBuffer` wraps, and read by the bgwriter pacing logic. [verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### compress_io
`src/bin/pg_dump/compress_io.c` — pg_dump's compression abstraction layer, exposing the `CompressFileHandle` and `CompressorState` interfaces so archive readers and writers stay compression-agnostic. Concrete backends (none, gzip, lz4, zstd) plug in behind a function-pointer table selected from the `--compress` method. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/compress_io.c.md`).



### compress_zstd
`src/bin/pg_dump/compress_zstd.c` — the zstd backend of pg_dump's `compress_io` abstraction, implementing streaming and file-handle compression on top of libzstd. It is one of the pluggable `CompressFileHandle` implementations, chosen when the dump is created with `--compress=zstd`. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/compress_zstd.c.md`).



### CompressFileHandle
pg_dump's abstraction over a possibly-compressed output file — a vtable of read/write/getc/gets/close ops so the archiver code is agnostic to whether the underlying stream is plain, gzip, lz4, or zstd. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md`).



### CompressorState
The pg_dump compression vtable allocated by `AllocateCompressor` and specialized by `InitCompressor{None,Gzip,LZ4,Zstd}`; it carries the read / write / end callbacks so the archiver stays compression-method agnostic (a build lacking a method leaves the callbacks NULL). [verified-by-code] (`compress_io.c:122-142` — via `knowledge/files/src/bin/pg_dump/compress_io.c.md`).



### compute_distinct_stats
The ANALYZE per-column routine for types that are hashable/equality-comparable but not ordered: it computes null fraction, average width, ndistinct, and an MCV list, but no histogram or correlation. [verified-by-code] (via `knowledge/idioms/analyze-mcv-histogram-correlation.md`).



### compute_query_id
GUC (`off`/`auto`/`on`/`regress`) controlling whether the core query-id (jumble hash) is computed; pg_stat_statements calls `EnableQueryId()` so `compute_query_id = auto` lights up, and it records nothing when the id is off and no other module requested one. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### compute_scalar_stats
The ANALYZE compute callback for scalar (ordered) types: it builds the most-common-values list, histogram, and physical-vs-logical correlation, dropping below-noise items. [verified-by-code] (`analyze.c:1999` — via `knowledge/files/src/backend/commands/analyze.c.md`).



### compute_trivial_stats
The last-resort ANALYZE per-column routine used when a type supports neither ordering nor equality: it can only record null fraction and average width, leaving distinctness and MCV empty. [verified-by-code] (via `knowledge/idioms/analyze-mcv-histogram-correlation.md`).



### ComputeXidHorizons
The procarray routine that scans live backends to compute the cluster's xid horizons (oldest xmin etc.) used to decide which dead tuples are removable; corrupting the xid order would break it. [from-README] (`transam/README:272-285` — via `knowledge/files/src/backend/access/transam/README.md`).



### CONCURRENTLY
The option on `CREATE INDEX`/`REINDEX`/`DROP INDEX` (and `REFRESH MATERIALIZED VIEW`) that avoids an `AccessExclusiveLock` blocking writes, at the cost of multiple transaction-spanning heap scans and waits for concurrent snapshots to finish. In `index.c` the concurrent build splits into the `BUILDING`/`READY`/`VALIDATE` catalog-state phases bracketed by `WaitForLockers`. [verified-by-code] (via `knowledge/files/src/backend/catalog/index.c.md`).



### condition_variable
A PostgreSQL synchronization primitive letting one process sleep until another signals a condition, without busy-waiting; built on the process latch with a wait-queue of `proclist` entries. The idiom is `ConditionVariablePrepareToSleep` / loop-checking the condition / `ConditionVariableSleep` / `ConditionVariableCancelSleep`, woken by `ConditionVariableSignal` or `Broadcast`. [from-comment] (via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionalLockBuffer
The non-blocking variant of `LockBuffer`: it tries to take the buffer content
lock and returns false immediately if it can't, instead of waiting. Used where a
backend must not block on a busy page — e.g. opportunistic pruning or a scan
that prefers to skip a contended page. [verified-by-code]
(`bufmgr.c:6567-6910` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ConditionalLockBufferForCleanup
A non-blocking attempt to acquire a cleanup lock (exclusive content lock plus a
guarantee of sole pin) on a buffer; VACUUM uses it to skip pages currently
pinned by other backends rather than wait. [verified-by-code] (via
`knowledge/idioms/vacuum-two-pass-heap.md`).



### ConditionalStack
psql's stack tracking nested `\if` / `\elif` / `\else` state, so it knows whether the current branch is active, being skipped, or already taken. [verified-by-code] (via `knowledge/files/src/bin/psql/prompt.h.md`).



### ConditionVariable
A sleep/wake primitive: a spinlock-protected `proclist` of waiting PGPROCs where one backend sleeps until another `Signal`s or `Broadcast`s it, each waiter being woken via `SetLatch(MyLatch)`. `ConditionVariablePrepareToSleep` enqueues before the condition re-test to avoid a lost wakeup. [verified-by-code] (`condition_variable.c:37` — via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionVariableBroadcast
Wakes every backend sleeping on a condition variable; the broadcast counterpart of `ConditionVariableSignal`, used after a state change that all waiters need to re-check (e.g. a slot becoming available). [verified-by-code] (`condition_variable.c:284` — via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionVariableCancelSleep
Must be called after a condition-variable wait loop exits; it dequeues the backend from the CV's wait list if it is still queued. Part of the mandatory CV sleep protocol (`ConditionVariablePrepareToSleep` / `Sleep` / `CancelSleep`). [verified-by-code] (`condition_variable.c:232` — via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionVariableSignal
Wakes exactly one backend sleeping in `ConditionVariableSleep` on a given condition variable (`condition_variable.c:261`); `ConditionVariableBroadcast` wakes all. CVs let backends wait on an arbitrary predicate without holding an LWLock across the wait. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConditionVariableSleep
The blocking primitive of the condition-variable API: after
`ConditionVariablePrepareToSleep`, a backend calls `ConditionVariableSleep(cv,
wait_event)` to sleep until another backend `ConditionVariableSignal`/`Broadcast`s
the variable. It is the latch-backed, interruptible way to wait on a shared-state
predicate without a busy spin. [verified-by-code] (`condition_variable.c:98` —
via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### ConfigData
The tiny `{name, setting}` pair struct behind the `pg_config` CLI; given `my_exec_path`, `get_configdata` builds a 23-entry `ConfigData[]` mixing runtime-resolved paths (`BINDIR`, `PGXS`, …) with build-time constants (`CONFIGURE`, `CC`, `CFLAGS`, `VERSION`). [verified-by-code] (via `knowledge/files/src/common/config_info.c.md`).



### ConfigureNames
The set of arrays in `guc_tables.c` (`ConfigureNamesBool` / `Int` / `Real` / `String` / `Enum`) defining every in-tree GUC's name, context, flags, and hooks; the table is `PGDLLIMPORT` and deliberately non-const so extensions and assign-hooks can mutate entries. [verified-by-code] (via `knowledge/idioms/guc-variables.md`).



### confirmed_flush
The LSN on a logical replication slot up to which the downstream has confirmed receipt and persistence; the slot will not return changes before it again, and it (with `restart_lsn`) governs how much WAL and how many catalog rows must be retained. It advances as the subscriber reports feedback. [inferred] (via `knowledge/idioms/replication-slot-advance.md`).



### confirmed_flush_lsn
A logical replication slot's persisted "the downstream has confirmed receipt up to here" LSN; WAL older than it may be reclaimed, and it is the restart floor a standby must have flushed past. [verified-by-code] (via `knowledge/subsystems/replication.md`).



### ConflictType
The enum tagging a logical-replication apply conflict; PG defines eight kinds
(`insert_exists`, `update_differ`, `update_exists`, `update_missing`,
`delete_differ`, `delete_missing`, and so on) so conflict logging and
resolution can dispatch on the exact failure. [verified-by-code]
(`conflict.h:31-62` — via `knowledge/subsystems/replication.md`).



### ConnectDatabase
The shared frontend connect helper (`connectdb.c:39`, used by pg_dumpall and pg_restore in -d mode) wrapping `PQconnectdbParams` with connection-string parsing, optional password prompting/retry, a server-version check, and a forced secure `search_path` via `ALWAYS_SECURE_SEARCH_PATH_SQL`. It is distinct from the heavier `pg_backup_db.c` connection family inside pg_dump proper, which would drag in the full Archive machinery. [verified-by-code] (`connectdb.c:39` — via `knowledge/files/src/bin/pg_dump/connectdb.c.md`).



### ConnParams
The frontend-tools struct of command-line connection parameters — dbname (which may itself be a full connstring), host, port, user, password-prompt tri-value, and `override_dbname` — shared by libpq-based utilities to open connections consistently. `override_dbname` replaces only the bare database name within a connstring, leaving the rest intact (how `vacuumdb -d "connstr" mydb` works); a parallel-slot pool shares one `ConnParams` so all its connections open identically. [verified-by-code] (`connect_utils.h:25` — via `knowledge/files/src/include/fe_utils/connect_utils.h.md`).



### consistentFn
The GIN/GiST opclass support function the scan calls to decide, from the set of matched index keys, whether a heap tuple actually satisfies the indexable qualifier (true), cannot (false), or might-need-recheck. It is what turns partial-match index entries into a correct answer. [inferred] (`ginget.c:1005` — via `knowledge/idioms/gin-scan-and-consistent.md`).



### construct_array
Builds a one-dimensional PostgreSQL array Datum from a C array of element Datums plus the element type's length/byval/alignment; the standard array constructor, with `construct_md_array` for multi-dim. [verified-by-code] (`arrayfuncs.c:3367` — via `knowledge/files/src/backend/utils/adt/arrayfuncs.c.md`).



### ControlFile
The on-disk `pg_control` file, declared as `ControlFileData` in `pg_control.h` even though it is not a heap relation, so its format is documented; it embeds the `CheckPoint` record body (`checkPointCopy`) and the `DBState` enum. Changing these structs requires bumping `PG_CONTROL_VERSION`, and the integer `DBState` values are on-disk. [verified-by-code] (`pg_control.h` — via `knowledge/files/src/include/catalog/pg_control.h.md`).



### ControlFileData
The fixed-layout struct serialised into `pg_control` describing cluster-wide
state (system identifier, latest checkpoint location, catalog/control
versions); it is read and written as a single ~8 KiB block guarded by a CRC.
[verified-by-code] (`controldata_utils.c:68-178` — via
`knowledge/files/src/common/controldata_utils.c.md`).



### conversion_procs
The `src/backend/utils/mb/conversion_procs/` tree of per-encoding-pair character-set conversion functions; each is a thin glue function that calls the shared `LocalToUtf` / `UtfToLocal` radix-tree drivers in `conv.c` and is registered in `pg_conversion`. [from-README] (via `knowledge/files/src/backend/utils/mb/_conversion_procs.md`).



### copy_file_range
The Linux syscall pg_combinebackup can use to copy file extents without pulling data through userspace; `copy_file.c` loops `copy_file_range(2)` with `SSIZE_MAX` until it returns 0, one of several copy methods (clone, hardlink, plain copy) it selects between. [verified-by-code] (via `knowledge/files/src/bin/pg_combinebackup/copy_file.c.md`).



### CopyData
The protocol message that carries a chunk of COPY payload in either direction
during COPY IN/OUT. It is one of the few message types libpq lets exceed the
30 KB "huge message" guard (`VALID_LONG_MESSAGE_TYPE`), because bulk data
legitimately runs large. [verified-by-code] (via
`knowledge/files/src/interfaces/libpq/fe-protocol3.c.md`).



### copydone
The extended wire-protocol message the frontend sends to end a COPY data stream (paired with `CopyData`; `CopyFail` aborts instead); the backend then replies with `CommandComplete`. [from-docs] (via `knowledge/docs-distilled/protocol-flow.md`).



### CopyFromRoutine
The function-pointer vtable an extension supplies to register a custom COPY *input* format (its TO counterpart is `CopyToRoutine`); `copy.c`'s option parser dispatches on `format` to install it, alongside the built-in text/csv/binary routines. [verified-by-code] (via `knowledge/files/src/backend/commands/copy.c.md`).



### copyObject
Deep-copies an arbitrary `Node` tree by dispatching on `nodeTag`; the generated `copyfuncs.c` supplies a per-node-type copier so parser/planner trees can be cloned without manual field walking. [verified-by-code] (via `knowledge/files/src/backend/nodes/copyfuncs.c.md`).



### copyObjectImpl
The implementation behind the `copyObject` macro (`copyfuncs.c`) — a giant node-type switch (mostly generated by `gen_node_support.pl`) that deep-copies any parse/plan tree node, recursing through its sub-nodes and Lists. [verified-by-code] (via `knowledge/files/src/backend/nodes/copyfuncs.c.md`).



### CopySnapshot
Makes a palloc'd copy of a snapshot in the current memory context so it can
outlive the source (e.g. when registering it), since snapshots are otherwise
backed by transient `xip` arrays. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### cost_seqscan
The planner's sequential-scan cost estimator: disk cost = `seq_page_cost * baserel->pages`, plus per-output-row CPU (tlist) cost. It is the simplest of the `cost_*` functions in `costsize.c` and a good template for reading the cost model. [verified-by-code] (`costsize.c:270` — via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### covering index
An index that stores extra payload columns via `INCLUDE` so it can satisfy an index-only scan for queries needing those columns, without making them part of the key. On a unique covering index the uniqueness constraint applies to the key columns only, not the payload. [from-docs §11.9] (via `knowledge/docs-distilled/indexes-index-only-scans.md`).



### cpu_tuple_cost
The planner cost-model unit (cost.h / costsize.c) charged per tuple processed by the executor; it feeds the cpu_run_cost term of nearly every path's cost estimate. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### CRC
Cyclic Redundancy Check — PostgreSQL uses a 32-bit CRC (`pg_crc32c`, hardware-accelerated where available) to detect corruption in WAL records, the control file, and other on-disk structures. Each WAL record's CRC covers its body and header so recovery can reject a torn or garbled record at the tail of the log. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xloginsert.c.md`).



### create_gather_path
Builds a `GatherPath` (`pathnode.c`) that collects tuples from parallel workers running a partial subpath into the leader; the boundary where a parallel plan becomes serial again. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/pathnode.c.md`).



### create_index_paths
Generates `IndexPath`s for a base relation (`indxpath.c`, reached from `allpaths.c`) — matches restriction and join clauses to index columns, builds bitmap-OR combinations, and costs each candidate index scan. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/allpaths.c.md`).



### create_plan
The public entry into createplan.c that turns the chosen best `Path` tree into an executable `Plan` tree: it resets per-plan state, recurses via `create_plan_recurse`, applies target-list labeling, and attaches initplans. [verified-by-code] (`createplan.c:339` — via `knowledge/subsystems/optimizer.md`).



### CREATE_REPLICATION_SLOT
A replication-protocol command (parsed in the walsender replication grammar) that creates a named physical or logical replication slot, optionally naming an output plugin for logical slots. It sits alongside the other slot commands `DROP_REPLICATION_SLOT`, `ALTER_REPLICATION_SLOT`, and `READ_REPLICATION_SLOT`. [verified-by-code] (`repl_gram.y` — via `knowledge/files/src/backend/replication/repl_gram.y.md`).



### create_sort_path
Wraps a subpath in an explicit `SortPath` (`pathnode.c`), pricing the sort with `cost_sort` and recording the resulting pathkeys so an upper node can rely on the ordering. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/pathnode.c.md`).



### CreateCachedPlan
The plancache entry point called after `raw_parser` but before `parse_analyze*`; it creates a `CachedPlanSource` from the raw parse tree (cheap, no analysis yet), sets `magic = CACHEDPLANSOURCE_MAGIC`, and copies the raw tree into a fresh child of `CurrentMemoryContext`. The source is later finished by `CompleteCachedPlan`, which sets `query_list` and computes `relationOids`/`invalItems`. [verified-by-code] (`utils-cache.md` — via `knowledge/subsystems/utils-cache.md`).



### CreateCheckPoint
The function (driven by the checkpointer) that performs a checkpoint —
flushing dirty buffers, writing a checkpoint WAL record, and updating
`pg_control`'s redo pointer so recovery can restart from there.
[verified-by-code] (via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### CreateDataDirLockFile
Writes `postmaster.pid` (the `DIRECTORY_LOCK_FILE`) in `$PGDATA` with the postmaster PID and a shmem key so a second postmaster on the same data dir refuses to start; written in multiple steps, so a torn file is a known transient rather than corruption. [verified-by-code] (`miscinit.c:1465` — via `knowledge/docs-distilled/server-start.md`).



### CreateDestReceiver
The factory that maps a `CommandDest` value to the matching `DestReceiver` implementation (client, tuplestore, SPI, COPY, …), producing the sink that query result rows are routed through. [verified-by-code] (`dest.c` — via `knowledge/subsystems/tcop.md`).



### CreateExecutorState
Allocates a fresh `EState` and its dedicated per-query memory context, the first
step of `ExecutorStart`; everything the executor allocates for the query hangs
off this context. [verified-by-code] (via
`knowledge/idioms/epq-state-init.md`).



### CreateParallelContext
The entry point that allocates a `ParallelContext`, names the worker entrypoint
function, and begins sizing the DSM segment; the first step of the
parallel-worker launch sequence before `InitializeParallelDSM`. [verified-by-code]
(via `knowledge/idioms/bgworker-and-parallel.md`).



### CreatePredicateLock
Creates an SSI predicate lock, acquiring the predicate-locking LWLocks in the prescribed rank order (a subset of the seven-level chain, e.g. SerializablePredicateListLock → partition → SerializableXactHashLock) and releasing them in reverse. [verified-by-code] (`predicate.c:2392` — via `knowledge/subsystems/storage-lmgr.md`).



### CreateRestartPoint
The recovery-side counterpart to `CreateCheckPoint`, defined in `xlog.c`, that establishes a restartpoint on a standby — the mechanism by which a hot-standby trims WAL and bounds crash-recovery work without performing a full checkpoint of its own. [inferred] (`xlog.c` — via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### CreateSharedMemoryAndSemaphores
The ipci.c routine run at postmaster startup that sizes and lays out the main shared-memory segment by calling each subsystem's `XxxShmemInit`, then creates the semaphores. [verified-by-code] (via `knowledge/subsystems/storage-ipc.md`).



### CreateTemplateTupleDesc
Allocates an uninitialized `TupleDesc` for N attributes in a single allocation (descriptor header + N `Form_pg_attribute` + N `CompactAttribute` slots) with `tdrefcount = -1`; attributes are then filled in via `TupleDescInitEntry`. [verified-by-code] (`tupdesc.c:165` — via `knowledge/data-structures/tupledesc.md`).



### CreateTupleDescCopy
Makes a flat copy of a `TupleDesc`, duplicating the attribute entries but NOT the constraints or defaults; `CreateTupleDescCopyConstr` is the variant that copies those too. [verified-by-code] (via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### CritSectionCount
The per-backend critical-section nesting depth; while it is `> 0`, `errstart` promotes any ERROR to PANIC, because failing partway through a WAL-logged shared-memory mutation must take down the server rather than leave it inconsistent. [verified-by-code] (`elog.c:372` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### crosstab
A set-returning function in the `contrib/tablefunc` module that pivots rows into columns: given SQL returning `(row_id, category, value)` it produces one output row per `row_id` with N value columns. The output column count must be known at parse time, which is why callers must supply an explicit `AS ct(...)` column definition list; variants include `crosstab(sql, sql_categories)` for explicit column ordering and the fixed-width `crosstab2/3/4`. [from-README] (`contrib-tablefunc.md` — via `knowledge/subsystems/contrib-tablefunc.md`).



### cryptohash
The unified cryptographic-hash abstraction (`pg_cryptohash_create`/`_update`/
`_final`) that dispatches to OpenSSL when built `--with-ssl`, or to in-tree
fallback implementations otherwise, giving the same MD5/SHA-1/SHA-2 API to both
backend and frontend code. [verified-by-code] (via
`knowledge/files/src/include/common/cryptohash.h.md`).



### cryptohash_openssl
The OpenSSL-backed digest implementation (`src/common/cryptohash_openssl.c`) that provides `pg_cryptohash_create` / `_update` / `_final` when PostgreSQL is built with OpenSSL, replacing the in-tree software fallback in `cryptohash.c`. Its `pg_cryptohash_create` is careful to allocate the wrapper before the OpenSSL context so an OOM cannot leak the about-to-be-allocated context. [verified-by-code] (`cryptohash_openssl.c:121-133` — via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### cstring_to_text
The fmgr helper that copies a NUL-terminated C string into a freshly palloc'd `text` Datum (the length-taking variant is `cstring_to_text_with_len`). Note it performs no server-encoding validation — callers handling untrusted bytes must sanitize separately. [verified-by-code] (via `knowledge/files/contrib/sslinfo/sslinfo.c.md`).



### CStringGetTextDatum
Macro that turns a NUL-terminated C string into a `text` Datum (palloc'ing a varlena copy); the usual way to hand a C string back to SQL as `text`. Its inverse is `text_to_cstring`. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### CT_UPDATE_MISSING
A logical-replication conflict type reported when an incoming UPDATE cannot find any matching row in the target relation (as opposed to CT_UPDATE_DELETED, where the row was concurrently deleted). [verified-by-code] (via `knowledge/files/src/include/replication/conflict.h.md`).



### CT_UPDATE_ORIGIN_DIFFERS
A logical-replication conflict type (conflict.h) reported when an incoming UPDATE targets a row that was last modified by a different replication origin. [verified-by-code] (via `knowledge/files/src/include/replication/conflict.h.md`).



### CTE
Common Table Expression — a `WITH` query whose named subqueries can be referenced by the main query (and, for `WITH RECURSIVE`, by themselves). `parse_cte.c` analyzes the `WITH` list, resolves forward/recursive references, and records whether each CTE must be materialized as an optimization fence. [verified-by-code] (via `knowledge/files/src/backend/parser/parse_cte.c.md`).



### CteScan
The executor plan node that reads from a tuplestore materialized by a non-recursive `WITH` CTE's producer (a `RecursiveUnion` or plain producer); all `CteScan` nodes referencing the same CTE share one tuplestore. Entry points are `ExecInitCteScan` / `ExecEndCteScan` / `ExecReScanCteScan`, with `CteScan` declared in `plannodes.h` and `CteScanState` in `execnodes.h`. [verified-by-code] (`nodeCtescan.md` — via `knowledge/files/src/include/executor/nodeCtescan.md`).



### CUBE_MAX_DIM
The compile-time cap (`#define CUBE_MAX_DIM (100)`) on the number of dimensions allowed in a `cube`-type value, enforced at every cube constructor and in the cube parser. The bound keeps per-cube storage and GiST split costs bounded; the source comment calls 100 "pretty arbitrary, but don't make it so large that you risk overflow in sizing calculations." [verified-by-code] (`cubedata.h` — via `knowledge/files/contrib/cube/cubedata.h.md`).



### curcid
The current command id carried in a snapshot, set from `GetCurrentCommandId()`; it bounds which same-transaction command effects are visible. In parallel mode the value is fixed at worker launch, so a worker asserting a changed `curcid` indicates an illegal command-counter bump. [verified-by-code] (via `knowledge/idioms/snapshot-active-stack-and-registered.md`).



### CurrBytePos
The global "next byte to insert" cursor in the WAL insertion machinery (`XLogCtlInsert`); reserving space for a record atomically advances CurrBytePos while `PrevBytePos` records the start of the previous record so back-links can be filled in. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### CurrentMemoryContext
The global that names the context where a bare `palloc` allocates. Code sets
it with the inline `MemoryContextSwitchTo(new)`, which returns the previous
context so callers can restore it; forgetting to restore is a classic source of
allocations landing in the wrong context. [verified-by-code] (via
`knowledge/idioms/memory-contexts.md`).



### CurrentResourceOwner
The global pointing at the resource owner that newly-acquired resources
(buffer pins, locks, tuplestore handles, catcache refs) are charged to, so
they can be released en masse when the owner ends. [verified-by-code] (via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### CurrentSession
The backend-global pointer to the active `Session` struct under parallel/shared
execution, anchoring session-scoped shared state such as the shared record
typmod registry. [verified-by-code] (via
`knowledge/idioms/typcache-record-typmod-and-shared.md`).



### CurrentSnapshot
The most recently taken MVCC snapshot in the current transaction, returned by
`GetTransactionSnapshot`; under `READ COMMITTED` it is refreshed each command,
under `REPEATABLE READ` it is taken once and held. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### CurrentSnapshotData
One of snapmgr's statically-allocated `SnapshotData` slots (declared `static SnapshotData CurrentSnapshotData = {SNAPSHOT_MVCC}`), into which `GetSnapshotData` writes the backend's current MVCC snapshot. Because the static slot is clobbered by the next snapshot-taking call, callers that need the snapshot to outlive subsequent calls must `PushActiveSnapshot` or `RegisterSnapshot` (both `CopySnapshot` it first); under Read Committed a fresh snapshot overwrites it per statement. [verified-by-code] (`snapmgr.c` — via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### CurTransactionContext
The per-transaction memory context whose lifetime matches the current
(sub)transaction; allocations there live until that transaction commits or
aborts, distinct from the per-query and per-tuple contexts. [from-comment]
(via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### custom_private
The extension-owned list on a `CustomPath` / `CustomScan` where a custom-scan provider stashes private state — e.g. when a path is parameterized by a parent relation. [from-docs] (via `knowledge/docs-distilled/custom-scan-path.md`).



### CustomExecMethods
The callback vtable a custom-scan provider supplies (BeginCustomScan /
ExecCustomScan / EndCustomScan / ReScan / Explain, plus optional parallel hooks)
to plug a `CustomScanState` into the executor. [verified-by-code] (via
`knowledge/docs-distilled/custom-scan.md`).



### CustomPath
A planner Path subtype injected by a custom-scan provider (via `set_rel_pathlist_hook` or `set_join_pathlist_hook` in `_PG_init`, chaining any prior hook) so it competes with seqscan/indexscan and can still be parallelized above. Beyond the embedded `Path` it carries `flags` (capability bits like `CUSTOMPATH_SUPPORT_BACKWARD_SCAN`/`MARK_RESTORE`/`PROJECTION`), `custom_paths` (child Paths), `custom_restrictinfo`, `nodeToString`-compatible `custom_private`, and a `CustomPathMethods` table whose `PlanCustomPath` callback converts it (typically to a `CustomScan`). [from-README] (`custom-scan-path.md` — via `knowledge/docs-distilled/custom-scan-path.md`).



### custompathmethods
The callback struct attached to a `CustomPath`; its `PlanCustomPath` callback converts the path into a `CustomScan` plan node during createplan. [from-docs] (via `knowledge/docs-distilled/custom-scan-path.md`).



### CustomScan
A plan-node type that lets an extension inject its own executor node into a plan tree via registered callback method tables (CustomScanMethods / CustomExecMethods), enabling custom scan or join strategies without patching the core executor. [verified-by-code] (`nodes/plannodes.h:932` — via `knowledge/files/src/backend/nodes/extensible.c.md`).



### CustomScanMethods
The custom-scan method table whose key callback is `CreateCustomScanState`; it is looked up by name (registered via `RegisterCustomScanMethods` / `GetCustomScanMethods`) because CustomScan nodes serialize through nodeToString to parallel workers. It is one of the three custom-scan method tables alongside `CustomPathMethods` and `CustomExecMethods`. [verified-by-code] (`extensible.h` — via `knowledge/files/src/include/nodes/extensible.h.md`).



### CustomScanState
The execution-side node state for a custom-scan provider, embedded as the first member of a larger provider-defined struct (the provider allocates something larger than `CustomScanState`); it is the runtime counterpart to the planner-side `CustomPath`/`CustomScan`. [from-README] (via `knowledge/docs-distilled/custom-scan-plan.md`).



### cvt_text_name
The btree_gin coercion that truncates an oversize `text` to `NAMEDATALEN-1` via `pg_mbcliplen` when indexing as `name`, assuming the shortened result still sorts below the original — correct only under byte-comparison (C) collation, not ICU/libc orderings. [from-comment] (via `knowledge/files/contrib/btree_gin/btree_gin.md`).



### data_checksums
The initdb static bool, `true` by default since PG 18, that turns on cluster-wide page checksums at bootstrap; the state is permanent at initdb time and can only be toggled offline afterward via `pg_checksums`. [verified-by-code] (`initdb.c:167` — via `knowledge/docs-distilled/creating-cluster.md`).



### data_directory_mode
The permission mask (`PG_DIR_MODE_OWNER`, 0700) the server applies to the data directory, relaxed to group-read when group access is enabled at initdb; part of the cluster's single file-permission boundary. [verified-by-code] (via `knowledge/files/src/backend/utils/init/globals.c.md`).



### DatabaseRelationId
The compile-time OID (1262) of the shared `pg_database` system catalog, assigned via the `CATALOG(pg_database,1262,DatabaseRelationId)` BKI macro. It is the relation identifier passed to `LockSharedObject(DatabaseRelationId, dboid, ...)` to serialize CREATE/DROP/RENAME DATABASE and new-connection setup against the same DB OID, and to `object_aclcheck(DatabaseRelationId, dboid, ...)` for per-database ACL checks. [verified-by-code] (`pg_database.h:12` — via `knowledge/files/src/include/catalog/pg_database.h.md`).



### datachecksum_state
`src/backend/postmaster/datachecksum_state.c` — the PG18 online data-checksum enable/disable engine. It holds both the four-state (`off` / `inprogress-on` / `inprogress-off` / `on`) transition logic driven by ProcSignalBarriers that every backend absorbs, and the launcher/worker background processes that rewrite every page in the cluster while the database stays online (so `pg_checksums` no longer needs a shutdown). [verified-by-code] (via `knowledge/files/src/backend/postmaster/datachecksum_state.c.md`).



### DataChecksumsNeedWrite
The predicate that data-page checksums are enabled for writes; one of the two disjuncts of `XLogHintBitIsNeeded()`, so enabling checksums forces hint-bit updates to be WAL-logged even when `wal_log_hints` is off. [verified-by-code] (via `knowledge/files/src/include/access/xlog.h.md`).



### DataDir
The global C string holding the absolute path of the running cluster's data
directory (`PGDATA`), set during postmaster startup. Security-sensitive
SQL-callable file functions like `pg_read_file` confine their argument to paths
under `DataDir`, `Log_directory`, and a few allowed roots.
[verified-by-code] (via `knowledge/files/src/backend/utils/adt/genfile.c.md`).



### datadir_target
In pg_rewind, the root path of the target cluster's data directory; every file operation resolves `<datadir_target>/<path>`, which is also the surface for the tool's symlink-race concerns. [from-comment] (via `knowledge/files/src/bin/pg_rewind/file_ops.c.md`).



### DataRow
The wire-protocol message carrying one result row's column values, emitted by
the `printtup` DestReceiver after a `RowDescription`. Both the networked backend
and the `--single` standalone backend funnel result tuples through `printtup`,
which formats each as a `DataRow`. [verified-by-code] (via
`knowledge/files/src/backend/access/common/printtup.c.md`).



### date_mi
The builtin implementing `date - date` (returning an integer day count). In GiST penalty math it can overflow when one operand is `+/-infinity`, which btree_gist's date opclass must guard against. [from-comment] (via `knowledge/files/contrib/btree_gist/btree_date.c.md`).



### DateStyle
The backend global (in `miscadmin.h`) holding the active date/time output style — `USE_ISO_DATES`, `USE_SQL_DATES`, `USE_POSTGRES_DATES`, `USE_GERMAN_DATES`, or `USE_XSD_DATES` — paired with `DateOrder` (`DATEORDER_YMD`/`DMY`/`MDY`) for ambiguous-input interpretation; it is set by `check_datestyle`/`assign_datestyle` parsing a combined string like `"ISO, DMY"` and defaults to `USE_ISO_DATES`. It controls two unrelated things at once: output formatting and ambiguous-input (MDY vs DMY) parsing, a well-known footgun. [verified-by-code] (`miscadmin.h:216-251`, `globals.c:25` — via `knowledge/files/src/include/miscadmin.h.md`).



### Datum
The generic pointer-width value type that carries any SQL datum through the
executor and fmgr layer: pass-by-value types are stored inline, pass-by-
reference types as pointers into memory. Conversion macros (`Int32GetDatum`,
`DatumGetPointer`, …) move concrete C values in and out. [inferred] (via
`knowledge/idioms/fmgr.md`).



### DatumBigEndianToNative
A Datum-level byte-order helper (`pg_bswap.h`) that converts a big-endian-encoded `Datum` to native order — `pg_bswap64` on little-endian machines, a no-op on big-endian; it assumes an 8-byte Datum. [verified-by-code] (via `knowledge/files/src/include/port/pg_bswap.md`).



### DatumGetInt32
Macro extracting a 32-bit signed integer from a `Datum`; one of the `DatumGet*`/`*GetDatum` conversion family in `postgres.h` that mediates between the generic Datum representation and concrete C types. [verified-by-code] (via `knowledge/files/src/include/postgres.h.md`).



### DatumGetPointer
The inverse of `PointerGetDatum`: it reinterprets a `Datum` that carries a
by-reference value as a `char *` so the callee can dereference it. By-reference
types (text, arrays, composites) are always passed as a pointer disguised in a
`Datum`, so fmgr-level code unwraps them with `DatumGetPointer` (or a
type-specific `DatumGet*` wrapper). [verified-by-code] (via
`knowledge/files/src/include/postgres.h.md`).



### DBA
Database Administrator — the operator role that runs and tunes a cluster (configuring `postgresql.conf`, scheduling VACUUM, managing backups). Used in the corpus to mark behavior or diagnostics aimed at operators rather than backend hackers. [verified-by-code] (via `knowledge/files/contrib/pageinspect/pageinspect.md`).



### dbId
The database OID component carried in shared-invalidation messages and standby WAL descriptions; a catcache invalidation is keyed on `(cacheId, hashValue, dbId)` so receivers in other databases can ignore it (`InvalidOid` means database-wide). [verified-by-code] (`inval.c:64` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### dbOid
The database-OID field in WAL descriptions and relfilenode locators (`spcOid` / `dbOid` / `relNumber`), identifying which database a logged change belongs to; `InvalidOid` here denotes a shared (cluster-wide) relation. [verified-by-code] (`seqdesc.c:31` — via `knowledge/files/src/backend/access/rmgrdesc/seqdesc.c.md`).



### ddl_command_end
The event-trigger firing point that runs just after a DDL command completes (after the matching `sql_drop` triggers); if the command errors, its `ddl_command_end` triggers do not run. It is the companion to `ddl_command_start`. [from-README] (via `knowledge/docs-distilled/event-trigger-definition.md`).



### ddl_command_start
One of the `EventTriggerEvent` values (with `ddl_command_end`, `sql_drop`, `table_rewrite`, `login`) that `evtcache.c` maps to the ordered list of enabled event-trigger functions, rebuilt by a name-order scan of `pg_event_trigger`. Fires before a DDL command executes. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### DeadFakeAttributeNumber
A synthetic negative attribute number (`#define`d to `FirstLowInvalidHeapAttributeNumber`, one slot *below* the lowest real system attribute so it cannot collide) that pg_dirtyread uses for its invented `dead boolean` column; when requested, tuple-conversion computes it from the visibility horizon via `HeapTupleIsSurelyDead(tuple, oldest_xmin)`. Illustrates the pattern of squatting below `FirstLowInvalidHeapAttributeNumber` to add a virtual system column. [verified-by-code] (via `knowledge/ideologies/pg_dirtyread.md`).



### deadlock detector
The lock-manager component that, on `deadlock_timeout` expiring while a backend
waits for a heavyweight lock, builds the wait-for graph and looks for a cycle.
A hard cycle aborts the youngest waiter with a deadlock error; soft edges let
it re-order the wait queue instead. [from-comment] (via
`knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



### deadlock_timeout
The wait duration (default 1 s) after which a lock waiter triggers PostgreSQL's optimistic deadlock detector; `ProcSleep` arms `DEADLOCK_TIMEOUT` and, when `got_deadlock_timeout` fires, calls `CheckDeadLock`, which walks the waits-for graph in `deadlock.c`. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



### DeadLockCheck
The deadlock-detector entry (`deadlock.c:220`, called from `CheckDeadLock` in proc.c with all lock-partition LWLocks held) that walks the wait-for graph and returns a `DeadLockState`, optionally rearranging wait queues to break a soft deadlock. [verified-by-code] (`deadlock.c:220` — via `knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



### debug_discard_caches
The int GUC (modern successor to compile-time CLOBBER_CACHE_ALWAYS) that forces full cache flushes on every `AcceptInvalidationMessages`, recursively up to the configured depth, to shake out stale relcache/syscache pointer bugs. It defaults to and caps at 0 unless `DISCARD_CACHES_ENABLED` was compiled in. [verified-by-code] (`inval.h:22` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### DECLARE_TOAST
A catalog-header macro that declares the TOAST table (and its index) for a
system catalog, fixing both their OIDs — e.g. `DECLARE_TOAST(pg_description,
2834, 2835)`. `genbki.pl` emits the corresponding bootstrap entries.
[verified-by-code] (via
`knowledge/files/src/include/catalog/pg_description.h.md`).



### DECLARE_UNIQUE_INDEX
The catalog-header macro declaring a unique index on a system catalog (its
name, fixed OID, and indexed columns), consumed by `genbki.pl` to emit the BKI
that bootstrap uses to build the index. `_PKEY` marks the primary key.
[verified-by-code] (`pg_auth_members.h:66` — via
`knowledge/files/src/include/catalog/pg_auth_members.h.md`).



### DECLARE_UNIQUE_INDEX_PKEY
The catalog-header macro that declares a system catalog's primary-key index
(name, OID, and the indexed columns) so `genbki.pl` can emit the bootstrap index
definition — e.g. `pg_description`'s `(objoid, classoid, objsubid)` PK. The
sibling `DECLARE_UNIQUE_INDEX` declares non-PK unique indexes. [verified-by-code]
(via `knowledge/files/src/include/catalog/pg_description.h.md`).



### DecodeDateTime
The datetime-input core: it tokenises a date/time string and fills a broken-down `struct pg_tm` (plus fractional seconds and timezone), dispatching on each field's decoded type. [verified-by-code] (`dt_common.c:1426-1432` — via `knowledge/files/src/backend/utils/adt/datetime.c.md`).



### DecodedXLogRecord
The fully parsed form of a WAL record produced by the xlogreader: the record header plus each registered block's data and full-page image, ready to be consumed by redo or logical decoding. [verified-by-code] (via `knowledge/files/src/include/access/xlogreader.h.md`).



### DecodeInterval
The datetime-parsing routine (`datetime.c:3511`) that decodes a Postgres-style interval literal from a pre-tokenized field array into a `struct tm` + fractional seconds; a flat state machine (not recursive) that walks the fields backwards so unit suffixes are seen before bare values. It is part of the shared `ParseDateTime`/`DecodeDateTime`/`DecodeInterval`/`DecodeISO8601Interval` API and has historically been hardened against parser-DoS and overflow CVEs. [verified-by-code] (`datetime.c:3511` — via `knowledge/files/src/backend/utils/adt/datetime.c.md`).



### deconstruct_array
Explodes an array Datum into a C array of element Datums and null flags given the element type's properties; the read-side counterpart of `construct_array`. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/array_userfuncs.c.md`).



### deconstruct_jointree
The planner pass that walks the parsed jointree to build the flat range-table/`RelOptInfo` representation, distributing qualifiers to the right join levels; after it runs no new PlaceHolderVars may be created. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### DEFAULT_COLLATION_OID
The OID of the database's default collation, passed to collation-aware routines (`str_tolower`, comparisons) when no explicit collation applies. Several corpus findings flag asymmetry hazards when one operator uses `DEFAULT_COLLATION_OID` while a sibling uses the input collation (e.g. citext `=` vs `<`, pg_trgm). [verified-by-code] (via `knowledge/files/contrib/dict_xsyn/dict_xsyn.c.md`).



### default_index
In `PartitionBoundInfo`, the array index of the DEFAULT partition (or `-1` if none), paired with `null_index` for the NULL-accepting partition. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### DEFAULT_INEQ_SEL
The planner's default selectivity constant for an inequality comparison, defined as `1/3`, used when no usable statistics are available. Range estimation combines two such halves but falls back to `DEFAULT_RANGE_INEQ_SEL` if either side is `DEFAULT_INEQ_SEL` or the combined result goes negative. [verified-by-code] (`selfuncs.md` — via `knowledge/files/src/include/utils/selfuncs.md`).



### DEFAULT_IO_BUFFER_SIZE
The shared unit of I/O (128 KB) defined in `compress_io.h` and used by every pg_dump compression backend as the block size for both compressed and uncompressed data; the LZ4 backend sizes its buffer at `LZ4F_compressBound(DEFAULT_IO_BUFFER_SIZE) * 1.5`. A code comment warns that changing the value requires re-checking that the test cases still exercise all branches, since enlarging it can silently disable some code paths on small inputs. [verified-by-code] (`compress_io.h.md` — via `knowledge/files/src/bin/pg_dump/compress_io.h.md`).



### DEFAULT_RANGE_INEQ_SEL
The planner's fallback selectivity constant (`0.005`) used when estimating a range/inequality clause with no usable statistics. Range estimation normally combines two inequality halves, but falls back to this constant if either half is `DEFAULT_INEQ_SEL` or the combined result goes negative, because the two halves are not independent. [verified-by-code] (`selfuncs.md` — via `knowledge/files/src/include/utils/selfuncs.md`).



### default_statistics_target
The GUC setting the default ANALYZE sampling depth: it scales both the maximum number of MCVs and the number of histogram buckets `compute_scalar_stats` builds per column (a per-column `ALTER TABLE … SET STATISTICS` overrides it). [verified-by-code] (via `knowledge/files/src/backend/commands/analyze.c.md`).



### DefElem
The generic "defined element" parse node — a `defname`/`arg` name-value pair
the grammar produces for open-ended option lists (`WITH (...)`, `CREATE
EXTENSION` options, utility-statement knobs). Utility code walks a `List` of
`DefElem`s and interprets each by name, which keeps the grammar from needing a
dedicated production per option. [verified-by-code] (via
`knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md`).



### DefineCustomBoolVariable
The GUC-registration entry point an extension calls (typically from `_PG_init`) to add a custom boolean parameter, supplying name, help text, storage pointer, default, context, flags, and optional check/assign/show hooks. [from-comment] (via `knowledge/files/contrib/sepgsql/hooks.c.md`).



### DefineQueryRewrite
The implementation of CREATE RULE: it validates and installs a rewrite rule
into `pg_rewrite`, including the special handling that converts a relation
into a view when an `ON SELECT DO INSTEAD` rule is added. [verified-by-code]
(`rewriteDefine.c:224` — via `knowledge/subsystems/parser-and-rewrite.md`).



### DELAY_CHKPT_IN_COMMIT
A `delayChkpt` flag a backend sets on its `PGPROC` across the window where it
has written its commit WAL but not yet made the effects visible, forcing a
concurrent checkpoint to wait so it cannot capture a torn commit state. Logical
replication's conflict detection reads the oldest such xid via
`TwoPhaseGetOldestXidInCommit`. [verified-by-code] (`twophase.c:2835` — via
`knowledge/files/src/backend/access/transam/twophase.c.md`).



### DELAY_CHKPT_START
A PGPROC `delayChkpt` flag a backend sets to bar a checkpoint from starting between a critical WAL insert and the corresponding buffer changes, preventing a checkpoint from capturing a torn state. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



### deleteDependencyRecordsFor
Removes every `pg_depend` row whose dependent object is the given (classid, objid); called during DROP and ALTER to tear down an object's outgoing dependency edges before the object itself is removed. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_depend.c.md`).



### deleteXid
The XID published as the `snapshotConflictHorizon` in a page-reuse WAL record (nbtree `XLOG_BTREE_REUSE_PAGE`, the GiST/BRIN analogues): standbys use it to cancel queries that could still see the page about to be recycled — the conflict is raised at recycle time, not delete time. [from-comment] (`gistxlog.c:378` — via `knowledge/files/src/backend/access/gist/gistxlog.c.md`).



### DestReceiver
The abstract sink for query result tuples: a struct of `receiveSlot`/`rStartup`/
`rShutdown`/`rDestroy` callbacks chosen by command context (client wire
protocol, `SELECT INTO`/tuplestore, SPI, COPY, printtup). The executor calls
`receiveSlot` per output tuple without knowing the concrete destination.
[from-comment] (`pl_exec.c:3576` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### DestroyParallelContext
The final stage of the parallel-execution lifecycle (`CreateParallelContext` → `InitializeParallelDSM` → `LaunchParallelWorkers` → `WaitForParallelWorkersToFinish` → `DestroyParallelContext`); it tears down a `ParallelContext`, ensuring workers have exited (under `HOLD_INTERRUPTS` + `WaitForParallelWorkersToExit`) before freeing the DSM segment and per-context state. It runs unconditionally on cleanup and is followed by `ExitParallelMode`. [verified-by-code] (`parallel.c:959` — via `knowledge/files/src/backend/access/transam/parallel.c.md`).



### detoast_attr
The function that turns a possibly-toasted varlena datum into a fully in-line, decompressed one — fetching out-of-line chunks from the toast table and/or running the compression decompressor as needed. Most type code calls the `PG_DETOAST_DATUM` macros which funnel here. [inferred] (`detoast.c:116` — via `knowledge/idioms/detoast-stream-consumption.md`).



### detoast_external_attr
The read side of TOAST: given an EXTERNAL (and possibly COMPRESSED) varlena pointer, it reassembles the full out-of-line value from its chunks in the TOAST table; `detoast_attr` and `detoast_attr_slice` are the broader and partial variants. [verified-by-code] (via `knowledge/files/src/backend/access/common/detoast.c.md`).



### dict_snowball
The built-in text-search stemming dictionary backed by the Snowball stemmer library. Its C source is generated from per-language Snowball algorithm files plus a small PostgreSQL wrapper (`dict_snowball.c`) that adapts the stemmer to the `ispell`/dictionary template API used by `tsvector` processing. [verified-by-code] (via `knowledge/files/src/backend/snowball/README.md`).



### DirectFunctionCall
The fmgr family (`DirectFunctionCall1` … `DirectFunctionCall9`) that invokes a C function by direct pointer using the version-1 calling convention, bypassing any catalog lookup; it is limited to nine arguments. [verified-by-code] (`fmgr.h` — via `knowledge/files/src/include/fmgr.h.md`).



### DirectFunctionCall1
Calls a built-in function by its C symbol with one argument, bypassing the fmgr catalog lookup; the fast path for invoking a known function like `nextval` or a type input function from C. `DirectFunctionCall2`/`3`/… take more args. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### DirectFunctionCall2
An fmgr convenience macro that calls a built-in C function by its C symbol
with two `Datum` arguments, skipping catalog lookup; it errors if the callee
returns NULL (use `FunctionCall2` when NULL is possible). [verified-by-code]
(via `knowledge/files/contrib/intarray/_int_op.md`).



### DIRECTORY_LOCK_FILE
The macro naming the postmaster interlock file `postmaster.pid`; its presence and contents implement the single-postmaster-per-data-dir guard. [verified-by-code] (`miscinit.c:61` — via `knowledge/docs-distilled/server-start.md`).



### disabled_nodes
A count field on `Path`/`Plan` (PG17+) recording how many plan nodes were built
from a disabled operation (e.g. under `enable_seqscan = off`); the planner now
prefers the path with the fewest disabled nodes before comparing cost, instead
of the old "add a huge `disable_cost` penalty" hack. [verified-by-code] (via
`knowledge/subsystems/optimizer.md`).



### DispatchJobForTocEntry
The pg_dump parallel dispatcher: it blocks until a worker is idle, then sends that worker a `DUMP <id>` or `RESTORE <id>` command for a TOC entry, registering a completion callback. [verified-by-code] (`parallel.c:1207` — via `knowledge/files/src/bin/pg_dump/parallel.c.md`).



### dlist_head
The anchor of an intrusive doubly-linked list (`ilist.h`): a single sentinel `dlist_node` whose `next`/`prev` point at the first and last elements, giving O(1) push/pop at both ends and O(1) delete of any known node. Paired with `dlist_node` members on the elements. [inferred] (via `knowledge/data-structures/dlist-node.md`).



### dlist_node
The two-pointer (`prev`,`next`) struct embedded inside a larger struct to make it a member of an intrusive doubly-linked list. Because the node lives inside the element, list membership needs no extra allocation; `dlist_container` recovers the enclosing struct from the node pointer. [inferred] (via `knowledge/data-structures/dlist-node.md`).



### do_analyze_rel
The core ANALYZE driver (`analyze.c`) for one relation: it acquires the sample via `acquire_sample_rows`, runs each column's `compute_stats`, and writes the results into `pg_statistic`. [verified-by-code] (via `knowledge/idioms/analyze-block-and-reservoir-sampling.md`).



### DomainConstraintCache
The refcounted cache of a domain type's CHECK/NOT NULL constraints, hung off
its `TypeCacheEntry`; expression states that coerce to the domain hold a
reference so the compiled constraint list survives concurrent invalidation
until every user has released it. [verified-by-code] (via
`knowledge/idioms/typcache-entry-and-lookup.md`).



### DomainConstraintRef
A reference object that lets a cached domain type track its CHECK/NOT NULL
constraints and be notified through the typcache when those constraints change,
so coercions revalidate against the current definition. [verified-by-code] (via
`knowledge/idioms/typcache-entry-and-lookup.md`).



### DomainHasConstraints
A typcache predicate reporting whether a domain type carries CHECK / NOT NULL constraints; it drives optimizer volatility analysis, since a coercion to a constrained domain is not a no-op and may not be freely removed. [verified-by-code] (`typcache.c:1497` — via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### DropRelationBuffers
The bufmgr bulk routine that discards all shared-buffer pages belonging to a relation's forks (e.g. on truncate/drop) so stale data is not flushed back to a relfile that is going away. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### DSA
Dynamic Shared Area — an allocator (`dsa.c`) that hands out `palloc`-like allocations from dynamic shared memory segments, so multiple cooperating backends (e.g. parallel workers) can share data structures. Pointers are passed between processes as `dsa_pointer` offsets rather than raw addresses, since the segment may map at different addresses per backend. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/dsa.c.md`).



### dsa_area
The per-backend handle to a dynamic shared-memory area — an allocator that
hands out `dsa_pointer`s usable across cooperating backends (parallel workers),
backed by one or more DSM segments that grow on demand. Code attaches to a shared
area, `dsa_allocate`s from it, and translates pointers with `dsa_get_address`.
[verified-by-code] (`dsa.c:347-373` — via
`knowledge/files/src/backend/utils/mmgr/dsa.c.md`).



### dsa_create_in_place
The dynamic-shared-area constructor that initializes a DSA inside a caller-provided shmem region (rather than allocating a fresh DSM segment), letting an extension back a variable-length arena — e.g. pg_stat_monitor's query-text store — out of space it reserved at `shmem_request` time. [verified-by-code `hash_query.c:103`] (via `knowledge/ideologies/pg_stat_monitor.md`).



### dsa_get_address
Translates a `dsa_pointer` into a backend-local address within a `dsa_area`; it has side effects (may map newly-created and unmap freed segments) so it must run in backend-local code, and it silently returns a wrong pointer if handed a `dsa_pointer` from a different area. [verified-by-code] (`dsa.c:956` — via `knowledge/files/src/include/utils/dsa.md`).



### dsa_pointer
A relative offset into a dynamic shared memory area (DSA), used instead of a raw
pointer because the same DSA segment can be mapped at different addresses in
different backends. `dsa_get_address` converts it to a usable local pointer;
`InvalidDsaPointer` is the null sentinel. [verified-by-code] (via
`knowledge/files/src/backend/utils/mmgr/dsa.c.md`).



### dshash
The dynamic shared-memory hash table built on `dsa` — a concurrent,
partition-locked hash map whose entries live in a `dsa_area` so multiple
backends (e.g. parallel workers, the shared typmod registry, stats collector
tables) can read and write it. [verified-by-code] (`dshash.c:1-30` — via
`knowledge/files/src/backend/lib/dshash.c.md`).



### DSM (dynamic shared memory)
The facility for creating shared-memory segments after postmaster startup, used
mainly to pass tuples and state to parallel workers. One backend creates a
`dsm_segment` and shares its handle; others `dsm_attach`/`dsm_detach`, and
detach callbacks run cleanup. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/dsm.c.md`).



### dsm_create
Creates a new dynamic shared-memory segment of a given size and returns a `dsm_segment *`; the segment is reference-counted and pinned to the creating resource owner, the low-level primitive beneath parallel query and the DSM registry. [from-comment] (via `knowledge/files/src/backend/storage/ipc/dsm_registry.c.md`).



### dsm_segment
A per-backend descriptor for an attached dynamic-shared-memory segment; it is owned by a `ResourceOwner` and is the substrate under `dsa_area`, `shm_mq`, and parallel-query shared state. [verified-by-code] (`dsm.c:73-83` — via `knowledge/subsystems/storage-ipc.md`).



### dump_line
The pg_bsd_indent routine that emits the pending label, code, and comment at their computed output columns and then resets the line buffers — the point where the reindenter actually writes a formatted source line. [verified-by-code] (via `knowledge/files/src/tools/pg_bsd_indent/io.c.md`).



### DumpableObject
pg_dump's in-memory base "class" for every catalog object it might emit
(tables, types, functions, ACLs, …); the `getXxx()` collectors populate
subclasses, dependency edges are computed between them, and a topological sort
plus per-type `dumpXxx` routines turn them into ordered archive entries.
[verified-by-code] (via
`knowledge/files/src/bin/pg_dump/pg_dump.c.md`).



### durable_rename
The fsync-aware wrapper around `rename(2)` that renames a file and then fsyncs
both the file and the containing directory so the new name survives a crash.
Used wherever a rename must be crash-safe, such as installing an archived WAL
segment or finalizing a control file. [verified-by-code] (via
`knowledge/files/contrib/basic_archive/basic_archive.c.md`).



### dynamic_library_path
The search path `expand_dynamic_library_name()` walks to resolve a loadable module's name to a `.so`; output-plugin loading also searches it, and any library on the path exporting the required symbol is loaded (no whitelist). [verified-by-code] (via `knowledge/files/src/backend/utils/fmgr/dfmgr.c.md`).



### ECPG
Embedded SQL in C — PostgreSQL's preprocessor (`ecpg`) that turns `EXEC SQL ...` directives in a `.pgc` source file into libpq calls plus a C file the normal compiler can build. The preproc grammar mirrors the backend grammar, which is why grammar changes often need a matching ECPG update. [verified-by-code] (via `knowledge/files/src/interfaces/ecpg/preproc/ecpg_keywords.c.md`).



### ECPGdump_a_type
The ECPG preprocessor's top-level host-variable type dumper: it performs hidden-variable shadowing checks, then dispatches on the type kind (array/struct/union/char_variable/descriptor/default) to emit the C declaration. It is the only `ECPGdump_a_*` symbol with external linkage. [verified-by-code] (`type.c:218` — via `knowledge/files/src/interfaces/ecpg/preproc/type.c.md`).



### ECPGttype
The ECPG preprocessor enum naming a simple/host C type (as opposed to `ECPGdtype`, the descriptor-item enum); `ECPGmake_simple_type` builds a type node from an `ECPGttype` plus a size string, and `ecpg_type_name` maps the enum back to its name. The enum itself is defined outside `type.h` and referenced throughout the preprocessor. [verified-by-code] (via `knowledge/files/src/interfaces/ecpg/preproc/type.h.md`).



### EEOP_
The prefix of the expression-evaluation opcode enum (`ExprEvalOp`); each compiled expression step built by `execExpr.c` carries an `EEOP_*` op that `execExprInterp.c`'s dispatch loop (or the JIT) switches on — e.g. `EEOP_PARAM_CALLBACK`, `EEOP_HASHED_SCALARARRAYOP`. [verified-by-code] (via `knowledge/files/src/backend/executor/execExprInterp.c.md`).



### EEOP_FUNCEXPR_STRICT
An expression-evaluation interpreter opcode that evaluates a strict function call, short-circuiting to a NULL result if any argument is NULL rather than invoking the function. It is one of the `EEOP_*` steps dispatched by the per-row expression evaluator. [verified-by-code] (`execExprInterp.c` — via `knowledge/files/src/backend/executor/execExprInterp.c.md`).



### effective_io_concurrency
A planner/executor GUC (also a per-tablespace option cached in `spccache.c`) hinting how many concurrent I/O requests the storage can service, used to size prefetch depth; a tablespace field `< 0` falls back to the GUC default. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/spccache.c.md`).



### elog
The terse error/log macro for internal "can't happen" conditions: `elog(ERROR, "…")` takes only a level and a format string (no SQLSTATE or detail), longjmp'ing on ERROR like `ereport`. Reserved for programming errors, not user-facing messages. [verified-by-code] (via `knowledge/files/contrib/spi/moddatetime.c.md`).



### EmitErrorReport
The elog/ereport output-routing function that dispatches a completed error frame to its sinks: `send_message_to_server_log` (log_line_prefix formatting plus optional CSV/JSON/syslog/eventlog/console writers) and `send_message_to_frontend` (libpq protocol), with routing decided by `Log_destination` and `whereToSendOutput`. [verified-by-code] (`elog.c` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### EmitProcSignalBarrier
The procsignal mechanism (`procsignal.c`) for global state changes that must be confirmed by every backend (e.g. dropping a logical slot, changing checksum mode). It OR's the barrier type into each slot's `pss_barrierCheckMask`, atomically mints a new `psh_barrierGeneration`, and signals every backend with SIGUSR1; backends absorb the change in `ProcessProcSignalBarrier`, letting the emitter wait until the new generation is acknowledged. [verified-by-code] (`procsignal.c` — via `knowledge/files/src/backend/storage/ipc/procsignal.c.md`).



### EmitWarningsOnPlaceholders
The former name of `MarkGUCPrefixReserved` — the call an extension makes after defining its GUCs to claim its `prefix.*` namespace, so unknown `prefix.foo` settings warn instead of silently persisting. [verified-by-code] (`guc.h:418-421` — via `knowledge/files/src/include/utils/guc.h.md`).



### EnableQueryId
The call that turns on core query jumbling so a query-id is computed; pg_stat_statements (and pg_stash_advice) invoke it because the module is useless without a query-id, which makes `compute_query_id = auto` effectively active. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### EncodeDateOnly
The datetime.c encoder that formats a broken-down `struct tm` date into a caller-supplied buffer in one of four styles (ISO / SQL / German / Postgres), honoring the `DateStyle`/`EuroDates` selection. It is the date-only counterpart to `EncodeDateTime`; both expect a buffer sized for the maximal output (≥ `MAXDATELEN`/128 bytes) since they emit via chained `sprintf` with no length argument. [verified-by-code] (`datetime.c:4379` — via `knowledge/files/src/backend/utils/adt/datetime.c.md`).



### EncodeDateTime
The datetime.c full date+time formatter that renders a `struct tm` plus fractional seconds and optional timezone into a caller buffer in one of four styles (ISO / SQL / German / Postgres). It is the output-side counterpart of `DecodeDateTime` and is consumed by timestamp/timestamptz output functions; like `EncodeDateOnly` it writes via chained `sprintf` and requires the caller to pre-size the buffer for the worst case (BC marker + full fsec + `MAXTZLEN` tz name). [verified-by-code] (`datetime.c:4496` — via `knowledge/files/src/backend/utils/adt/datetime.c.md`).



### encrypt_password
`encrypt_password()` (`crypt.c:180`) hashes a plaintext password into the stored verifier form (SCRAM or MD5) selected by `password_encryption`. [verified-by-code] (via `knowledge/docs-distilled/auth-password.md`).



### END_CRIT_SECTION
The macro closing a critical section opened by `START_CRIT_SECTION()`; inside the section any `ereport(ERROR)` is promoted to `ereport(PANIC)`, and it decrements the `CritSectionCount` counter. WAL/XLOG insertion is the principal in-tree user; a mis-paired `END_CRIT_SECTION` without a matching `START` underflows the counter. [verified-by-code] (`miscadmin.h` — via `knowledge/files/src/include/miscadmin.h.md`).



### end_lsn
The upper bound of a WAL byte range; paired with `start_lsn` it bounds the records a WAL reader such as `pg_walinspect` returns, and a decoded record's own `end_lsn` marks where the next record begins. [verified-by-code] (`pg_walinspect.c:7` — via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`).



### EndCommand
The tcop routine that sends the `CommandComplete` message (carrying the statement's `CommandTag` and any row count) to the client after a command finishes; the bookend to `BeginCommand`. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### endforeignmodify
The FDW callback that tears down per-modify state at end of a foreign-table DML operation, releasing remote resources opened by `BeginForeignModify`. [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### EndForeignScan
The FDW callback invoked at scan shutdown to release connection and per-scan
resources; the counterpart to `BeginForeignScan` in the foreign-scan executor
lifecycle. [verified-by-code] (via `knowledge/idioms/fdw-iterate-scan.md`).



### EndPrepare
The two-phase-commit routine (`twophase.c:1151`) that makes a PREPARE durable: after `MarkAsPreparing` reserves a `GlobalTransaction` shmem slot and per-rmgr `RegisterTwoPhaseRecord` chunks accumulate the state blob, `EndPrepare` emits the `XLOG_XACT_PREPARE` WAL record and flushes both it and the 2PC state file. It sets `DELAY_CHKPT_START` across the insert/flush to close a prepare/checkpoint race, rejects blobs larger than `MaxAllocSize` up front, and on return the prepared state survives backend exit. [verified-by-code] (`twophase.c:1151` — via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### EndRecPtr
The `XLogReaderState` field giving the WAL LSN just *past* the end of the record just read; redo, rewind, and streaming logic advance using it, as opposed to `ReadRecPtr`, which is the record's start. [verified-by-code] (`xlogreader.c` — via `knowledge/idioms/xlog-region-replay.md`).



### enlargeStringInfo
The StringInfo routine that grows a buffer to guarantee at least N more bytes of capacity (repalloc'ing as needed), the explicit-capacity sibling of `appendStringInfo`; frontend astreamer code uses it to pre-size fixed output buffers before a bulk write. [verified-by-code] (via `knowledge/files/src/fe_utils/astreamer_lz4.c.md`).



### EnsurePortalSnapshotExists
Makes sure an active snapshot is pushed for the current portal before running
a query that needs one — notably after a `COMMIT` inside a procedure has torn
down the previous snapshot. [verified-by-code] (`pl_exec.c:6119` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### EnterParallelMode
Marks the start of a parallel region, after which the backend may not assign new
XIDs or perform other operations unsafe to replicate to workers; balanced by
`ExitParallelMode`. [verified-by-code] (via
`knowledge/idioms/bgworker-and-parallel.md`).



### eqsel
The built-in selectivity estimator for the `=` operator — looks up the constant in the column's most-common-values list (and otherwise falls back to `1/ndistinct`) to estimate the fraction of rows an equality qual passes. One of the per-operator estimators dispatched from `clausesel.c`. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/clausesel.c.md`).



### EquivalenceClass
The planner structure grouping expressions known to be mutually equal (via
equality clauses and constants), enabling transitive predicate derivation,
pathkey canonicalization, and join-order flexibility. [verified-by-code] (via
`knowledge/data-structures/restrictinfo.md`).



### ereport
The macro family for reporting errors and log messages, taking an elevel
(DEBUG…NOTICE…ERROR…PANIC), a SQLSTATE, and `errmsg`/`errdetail`/`errhint`
fields. `ERROR` and above do a `longjmp` to the nearest handler. Every C file
that reports errors includes `elog.h`. [verified-by-code] (via
`knowledge/files/src/include/utils/elog.h.md`).



### ereturn
The soft-error counterpart of `ereport`: when an `escontext` is supplied it records the error into that context and *returns* (rather than `longjmp`-ing), letting the caller treat a bad input as a recoverable failure. [verified-by-code] (`miscnodes.h`; `ltxtquery_io.c:250-252` — via `knowledge/idioms/error-handling.md`).



### errcode
The `ereport` auxiliary that sets the five-character SQLSTATE for an error, e.g. `errcode(ERRCODE_UNDEFINED_COLUMN)`; codes come from `errcodes.txt`. Omitting it defaults to `ERRCODE_INTERNAL_ERROR`. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### ERRCODE_DATA_CORRUPTED
The SQLSTATE error code raised when backend code detects on-disk/structural corruption — e.g. TOAST detoasting on a chunk-size or end-of-chunk mismatch (`heaptoast.c`) and amcheck index/heap verification on an out-of-sequence or missing entry. Such corruption-path messages are typically emitted via `errmsg_internal` (untranslated), which is considered acceptable for a corruption diagnostic. [verified-by-code] (`heaptoast.c` — via `knowledge/files/src/backend/access/heap/heaptoast.c.md`).



### ERRCODE_FEATURE_NOT_SUPPORTED
The SQLSTATE (class 0A) raised when a code path is deliberately unimplemented or an internal-only type/operation is invoked from SQL; e.g. internal GiST key types raise it from their in/out functions. [verified-by-code] (via `knowledge/files/contrib/intarray/_intbig_gist.md`).



### errcode_for_file_access
The ereport helper that translates the current `errno` from a failed filesystem call into the matching PostgreSQL `SQLSTATE` (e.g. ENOENT → undefined_file, ENOSPC → disk_full), so file-I/O error sites need not hard-code SQLSTATEs. [verified-by-code] (`elog.c:929` — via `knowledge/scenarios/add-new-error-code.md`).



### ERRCODE_INTERNAL_ERROR
The default SQLSTATE applied to an `ereport`/`elog` call at `elevel >= ERROR` when `errcode(...)` is omitted (WARNING defaults to `ERRCODE_WARNING`, lower levels to `ERRCODE_SUCCESSFUL_COMPLETION`). Because it is the silent fallback, leaving it in place for an error a client might reasonably want to catch is a code smell — it signals "this should not happen" rather than a classified condition. [from-comment] (`error-handling.md` — via `knowledge/idioms/error-handling.md`).



### ERRCODE_INVALID_PARAMETER_VALUE
The SQLSTATE `22023` reported when a function argument or option is given a
value that is out of range or otherwise unacceptable for the operation.
[from-comment] (via `knowledge/files/contrib/pgcrypto/crypt-sha.md`).



### ERRCODE_PROGRAM_LIMIT_EXCEEDED
The SQLSTATE `54000` class error raised when an operation exceeds a hard implementation limit rather than running out of a resource — e.g. intarray's `g_int_compress` throwing when an array has too many elements to compress into the GiST key. [verified-by-code] (`_int_gist.c:184` — via `knowledge/files/contrib/intarray/_int_gist.md`).



### errcontext
The `ereport` auxiliary that appends a CONTEXT line to the current error, used by error-context callbacks (e.g. PL line numbers, COPY row numbers) to add a call-stack-like trail to a message. [verified-by-code] (`elog.h:177-234` — via `knowledge/idioms/error-handling.md`).



### errdetail
The `ereport` auxiliary supplying a secondary detail line (a full sentence, capitalised) elaborating the primary `errmsg`; `errdetail_internal` skips translation for fixed text. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### errdetail_internal
The non-translated sibling of `errdetail`: it attaches a DETAIL line to an in-flight `ereport` without marking the string for message translation, used for developer-facing or already-formatted detail text. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### errhint
The `ereport` auxiliary supplying a hint line suggesting how to fix the error; phrased as advice, may be a sentence fragment, and is the lowest-priority of the message components. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### errmsg
The `ereport` auxiliary carrying the primary, translatable error message; convention is lower-case start, no trailing period, no embedded newlines. The one component every error must have. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### errmsg_internal
The `ereport` message helper for messages that should NOT be translated or
shown to ordinary users — internal "can't happen" conditions and developer
diagnostics. It behaves like `errmsg` but skips gettext, signalling that the
text is for hackers, not for end users. [verified-by-code] (via
`knowledge/idioms/error-handling.md`).



### error_context_stack
The backend-global linked list of `ErrorContextCallback`s; each pushed entry contributes an errcontext line (the "while ... " annotations) when an error is reported, and is popped on normal exit or unwound by the `PG_TRY`/setjmp machinery on longjmp. Callbacks must restore the previous head, and care is needed so a mid-operation longjmp doesn't skip a pop. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### error_mqh
The per-parallel-worker `shm_mq` handle the leader reads for the worker's propagated `ereport` messages; the leader treats `error_mqh == NULL` (worker sent `PqMsg_Terminate`) as "this worker has finished cleanly." [verified-by-code] (via `knowledge/idioms/parallel-worker-launch-wait-and-errors.md`).



### ErrorContext
A small `MemoryContext` reserved at backend startup so that error reporting can
allocate even when the failing operation has exhausted memory; it is reset
after each error is handled. Along with `TopMemoryContext` it is one of only two
contexts initialized directly by `MemoryContextInit`. [from-comment]
(`mcxt.c:362-398` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### ErrorContextCallback
A node on a per-backend linked stack of "add context to the next error" callbacks; ereport() walks the stack so each layer (e.g. plpgsql line, COPY row) can append an errcontext() line describing where the error arose. [verified-by-code] (via `knowledge/files/src/include/utils/elog.h.md`).



### ErrorData
The struct that accumulates one in-flight error/log report — SQLSTATE, severity, message/detail/hint, source file/line/function, and context — built up by ereport()/errmsg() and consumed by the error-context callbacks and the log/client emitters. [verified-by-code] (`elog.c:12` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### ErrorResponse
The protocol message the backend sends to report an error to the client,
composed of typed fields (severity, SQLSTATE, message, detail, hint, position…)
mirroring an `ereport`. libpq parses it into a `PGresult`; it is one of the
message types allowed to exceed the normal length cap. [verified-by-code] (via
`knowledge/files/src/interfaces/libpq/fe-trace.c.md`).



### ErrorSaveContext
A node passed into "soft" input functions so a conversion failure is reported by setting a flag in the context instead of throwing via ereport; callers that supply it (COPY ... ON_ERROR, the SQL/JSON functions) can skip or default a bad value rather than abort the statement. [verified-by-code] (via `knowledge/idioms/fmgr.md`).



### errstart
Opens a new error frame on the backend's `errordata[]` stack at the start of an `ereport`/`elog`; the `errmsg`/`errcode`/`errdetail`/... helpers then populate that frame and `errfinish` either logs it or `longjmp`s out. [verified-by-code] (`elog.c:362-405` — via `knowledge/idioms/error-handling.md`).



### es_query_cxt
The `EState` field holding the per-query memory context created by `CreateExecutorState`. Everything the executor allocates for the query lives here and is reclaimed wholesale by `FreeExecutorState`, so it is the executor's primary leak boundary. [verified-by-code] (via `knowledge/data-structures/estate.md`).



### escape_json
The backend/`src/common` routine that emits an RFC 8259 JSON string literal, `\uXXXX`-escaping control characters; it is why the JSON constructors (`array_to_json`, `row_to_json`, `to_json`) always produce syntactically valid output for string content. The lower-level family lives in `src/common/jsonapi.c`. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/json.c.md`).



### escontext
A soft-error context (an `ErrorSaveContext *`) threaded through input/parse functions so that a conversion failure can be *captured* into the context instead of thrown via `ereport`; it is the mechanism behind COPY's `ON_ERROR ignore` and `pg_input_is_valid`. [verified-by-code] (carried in `CopyFromState` — via `knowledge/files/src/backend/commands` copyfrom docs).



### EState
The top-level executor run-state for one query execution: it holds the range
table, result relations, the per-query memory context, the snapshot, parameter
values, and the tuple destination, and is shared by every `PlanState` in the
tree. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### estimate_rel_size
Reads `pg_class.relpages`/`reltuples` and scales them to the relation's actual current file size (`plancat.c`) to estimate row count, page count, and all-visible fraction for planning. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/plancat.c.md`).



### EstimateSnapshotSpace
Computes the byte size needed to serialize a snapshot (xmin/xmax, the xip and subxip arrays) so a parallel leader can size the DSM segment before `SerializeSnapshot` copies the snapshot for its workers. [verified-by-code] (`snapmgr.c` — via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### EUC_CN
The Simplified Chinese Extended Unix Code encoding, supported via the `utf8_and_euc_cn.c` conversion proc that backs the `euc_cn_to_utf8` and `utf8_to_euc_cn` rows in `pg_conversion`, using radix-tree maps generated by `UCS_to_EUC_CN.pl`. EUC_CN ↔ Unicode is one-to-one (NULL combined-character map), so conversion routes through `LocalToUtf` / `UtfToLocal` with no per-encoding helper callback. [verified-by-code] (`utf8_and_euc_cn.c.md` — via `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc_cn/utf8_and_euc_cn.c.md`).



### EUC_JP
A multi-byte Japanese encoding (extended Unix code) handled by PostgreSQL's encoding-conversion procs; PG ships direct transcoders such as `euc_jp_and_sjis.c` (EUC_JP ↔ SJIS, no UTF-8 round trip) and `utf8_and_euc2004.c`, with `PGEUCALTCODE` (`0xa2ae`) as the EUC_JP replacement character and `PG_EUC_JP` as its `pg_enc` enum value. It is classified as an "other multibyte" encoding (distinct from single-byte and UTF-8) for locale/case-mapping purposes. [verified-by-code] (`euc_jp_and_sjis.c` — via `knowledge/files/src/backend/utils/mb/conversion_procs/euc_jp_and_sjis/euc_jp_and_sjis.c.md`).



### EUC_KR
The Korean Extended Unix Code encoding (the KS X 1001 / Wansung subset, not the larger UHC superset), supported via the `utf8_and_euc_kr.c` conversion proc that backs the `euc_kr_to_utf8` and `utf8_to_euc_kr` rows in `pg_conversion`. The EUC_KR ↔ Unicode mapping is one-to-one (NULL combined-character map), and the proc dispatches through `LocalToUtf` / `UtfToLocal` with a generated radix tree. [verified-by-code] (`utf8_and_euc_kr.c.md` — via `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc_kr/utf8_and_euc_kr.c.md`).



### ev_action
The `pg_rewrite` catalog column that stores a rule's action as a serialized node tree (read back through the nodes read-funcs machinery); one of the columns whose contents are node trees rather than scalars. [from-comment] (via `knowledge/files/src/include/nodes/readfuncs.h.md`).



### eval_const_expressions
The optimizer pass (`clauses.c`) that constant-folds and simplifies an expression tree — inlining strict functions, collapsing constant sub-expressions, simplifying CASE — run during `preprocess_qual_conditions` in the planner. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/clauses.c.md`).



### EvalPlanQual
The mechanism that lets a `READ COMMITTED` UPDATE/DELETE/SELECT-FOR-UPDATE cope
with a row another transaction concurrently modified: instead of aborting, it
re-fetches the latest committed version and re-runs the qual and projection
against it (an "EPQ recheck"). The executor diverts to `EvalPlanQualNext` on a
`TM_Updated`/`TM_Deleted` result. [verified-by-code] (via
`knowledge/subsystems/executor.md`).



### EvalPlanQualBegin
The routine that initializes an EPQ (EvalPlanQual) recheck sub-execution after a
concurrent update is detected, re-evaluating the plan against the updated row
version under `READ COMMITTED`. [verified-by-code] (via
`knowledge/idioms/epq-recheck-flow.md`).



### EvalPlanQualEnd
Tears down the EvalPlanQual (EPQ) recheck state after a concurrent-update recheck, freeing the mini-executor built to re-evaluate a locked/updated row against the latest tuple version. [verified-by-code] (`execMain.c:3208` — via `knowledge/idioms/epq-state-init.md`).



### EvalPlanQualFetchRowMark
EvalPlanQual helper that re-fetches the current version of a non-locked row identified by an ExecRowMark (e.g. a ROW_MARK_REFERENCE row or an FDW row) during an EPQ recheck. [verified-by-code] (via `knowledge/idioms/epq-multi-table.md`).



### EvalPlanQualInit
Sets up the `EPQState` (the mini-executor used to recheck and re-project an
updated row version) attached to a ModifyTable/LockRows node before any EPQ
recheck is needed. [verified-by-code] (via
`knowledge/idioms/epq-recheck-flow.md`).



### EvalPlanQualNext
The EvalPlanQual re-check driver: when a concurrent update is detected on a
locked row, the executor diverts here to re-run the qual, projection, and
join under the updated tuple, deciding whether the row still satisfies the
query. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### EvalPlanQualStart
Sets up the EvalPlanQual mini-executor that re-evaluates a plan against the freshly-updated version of a concurrently-modified row during `READ COMMITTED` updates and row locking. [verified-by-code] (via `knowledge/files/src/backend/executor/execMain.c.md`).



### EventTriggerData
The context struct passed to an event-trigger function, carrying the event name
(`ddl_command_start`, etc.), the command tag, and the parse tree of the
triggering statement. [verified-by-code] (via
`knowledge/idioms/event-trigger-firing.md`).



### examine_variable
The selectivity-estimation helper (`selfuncs.c`) that, given one side of an operator clause, locates the underlying column and fetches its `pg_statistic` row (via `get_attstatsslot`) — the entry point every estimator uses to reach MCV lists and histograms. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/rangetypes_selfuncs.c.md`).



### ExceptionalCondition
The crash handler invoked by a failed `Assert()`: it writes a one-line `TRAP: failed Assert(...)` to stderr, optionally dumps a backtrace and sleeps for debugger attach, then `abort()`s — deliberately bypassing the elog machinery so reporting an assertion failure needs minimal working infrastructure. The `Assert` macro family in `c.h` expands to call it when `USE_ASSERT_CHECKING` is on, and it is always compiled into the backend (gated `!FRONTEND`) so cassert-built extensions can link against a non-cassert backend. [verified-by-code] (`assert.c:29` — via `knowledge/files/src/backend/utils/error/assert.c.md`).



### ExclusiveLock
A heavyweight table-level lock mode that conflicts with every mode except
`AccessShareLock` (so plain `SELECT` still proceeds, but any writer or
weaker lock blocks); taken e.g. by `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
[from-comment] (via `knowledge/subsystems/contrib-pgrowlocks.md`).



### EXEC_BACKEND
The build symbol selecting the "re-exec" backend-startup model (mandatory on
Windows, optional elsewhere for debugging) in which a new backend is started by
exec-ing a fresh postgres image and re-attaching shared memory, instead of
relying on `fork()` to inherit the postmaster's address space. [inferred] (via
`knowledge/architecture/process-model.md`).



### exec_bind_message
The `postgres.c` handler for the extended-protocol `'B'` (Bind) message: it binds parameter values to a prepared statement, (re)plans if needed via the plan cache, and produces a ready-to-execute portal. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### exec_execute_message
The `postgres.c` handler for the extended-protocol `'E'` (Execute) message: it runs a bound portal for up to `max_rows` rows, dispatching to the executor or, for a utility portal, to `ProcessUtility`. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### exec_parse_message
The `postgres.c` handler for the extended-protocol `'P'` (Parse) message: it parses the query text, runs parse analysis, and stores the result as a named or unnamed prepared statement. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### exec_prog
The pg_upgrade routine that runs an external command (with `parallel_exec_prog` as the concurrent variant); the audit invariant is that every external program pg_upgrade launches goes through one of these two choke points. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/exec.c.md`).



### exec_simple_query
The tcop routine that handles a simple-query (`'Q'`) protocol message, running the entire parse → analyze → rewrite → plan → execute pipeline for a query string; it is the canonical "tour of the whole query path" entry point in `postgres.c`. [verified-by-code] (`postgres.c:1029-1320` — via `knowledge/architecture/query-lifecycle.md`).



### exec_stmt_dynexecute
The PL/pgSQL executor routine behind `EXECUTE` of a dynamically built command string: it evaluates the string expression, runs the SQL via SPI, and optionally captures the result into a target — the primary dynamic-SQL path in `pl_exec.c`. [from-comment] (`pl_exec.c:4541` — via `knowledge/issues/plpgsql.md`).



### ExecAgg
The executor entry (`ExecProcNode`) for an Agg plan node (`nodeAgg.c:2247`). It dispatches to `agg_retrieve_direct` for sorted/plain aggregation or `agg_fill_hash_table` + `agg_retrieve_hash_table` for hashed grouping, walking each active `Aggref`'s transition function over the input rows. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeAgg.c.md`).



### ExecAppend
The Append node executor (`nodeAppend.c`) — concatenates the output of several child subplans (e.g. partitions of a UNION ALL or an inheritance tree), draining each in turn, with parallel-append and run-time partition-pruning support layered on top. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeAppend.c.md`).



### ExecAuxRowMark
Executor state that ties a plan's `ExecRowMark` (row-locking / EvalPlanQual bookkeeping) to the junk attributes (`ctid`, `tableoid`, `wholerow`) that carry each locked row's identity through the plan. [verified-by-code] (via `knowledge/files/src/include/nodes/execnodes.h.md`).



### ExecBitmapHeapScan
The bitmap-heap-scan executor — consumes a TID bitmap built by a lower BitmapIndexScan/BitmapAnd/BitmapOr node and fetches the heap pages it names in physical order, rechecking lossy pages. Driven by `BitmapHeapNext`. [verified-by-code] (via `knowledge/idioms/bitmap-heap-scan-flow.md`).



### ExecBuildAggTrans
The routine that compiles an aggregate's per-row transition work into an
`ExprState` program (a chain of `ExprEvalStep`s), which the JIT path can then
lower to native code. [verified-by-code] (via
`knowledge/idioms/jit-expression-codegen.md`).



### ExecCheckPermissions
The executor's ACL pass (`execMain.c:862`), run once at `ExecutorStart` over all range-table entries and their `RTEPermissionInfo`s before any tuples flow. It also fires the `ExecutorCheckPerms_hook` (used by sepgsql as a veto-only MAC layer after PG's own DAC check). Parallel workers inherit executor state via DSM and do not re-invoke it — the leader's single check covers the access. [verified-by-code] (`execMain.c:862` — via `knowledge/files/src/backend/executor/execMain.c.md`).



### ExecClearTuple
Resets a `TupleTableSlot` to empty — releasing any buffer pin or palloc'd tuple it held and marking it `TTS_EMPTY`; called between tuples in an executor node's per-tuple loop to avoid leaking pins. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### execendfoo
Naming convention for a plan node's per-node teardown function, dispatched from `ExecEndNode`; state palloc'd in `ExecInitFoo` must NOT be manually `pfree`d here — the per-query memory context reclaims it. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ExecEndNode
The teardown half of the executor node API: `ExecEndPlan` walks the `PlanState`
tree calling each node's `ExecEndNode` to close relations, free tuple slots, and
release per-node resources after execution finishes. [verified-by-code]
(`execMain.c:1565` — via `knowledge/subsystems/executor.md`).



### ExecEndPlan
The executor shutdown step that recursively ends every plan node, closes result and range-table relations and indexes, and releases the executor's per-query resources at the close of a query's execution. [verified-by-code] (via `knowledge/files/src/backend/executor/execProcnode.c.md`).



### ExecEvalExpr
Runs a compiled `ExprState` against the current tuple/econtext, returning the result Datum and null flag; the per-tuple expression evaluator that `ExecInitExpr` prepares. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### execExpr
`src/backend/executor/execExpr.c` — the expression *compiler*: `ExecInitExpr` and friends flatten an expression tree into a linear `ExprState` step program (an array of `ExprEvalStep`, each an `ExprEvalOp` opcode plus operands) that the interpreter or JIT then runs. This compile-once / run-many design is what replaced the old recursive `ExecEvalExpr` tree-walk. [verified-by-code] (via `knowledge/files/src/backend/executor/execExpr.c.md`).



### execExprInterp
`src/backend/executor/execExprInterp.c` — the expression *interpreter* that executes the `ExprState` step program built by `execExpr.c`. `ExecInterpExpr` is a computed-goto dispatch loop over the `ExprEvalOp` opcodes; when JIT is enabled `llvmjit_expr.c` emits native code for the same opcode set instead. [verified-by-code] (via `knowledge/files/src/backend/executor/execExprInterp.c.md`).



### ExecFindPartition
Maps a tuple to its target leaf partition during tuple routing, walking the
`PartitionDispatch` tree and applying the partition key, used by INSERT/COPY/UPDATE
into partitioned tables. [verified-by-code] (via
`knowledge/idioms/partition-tuple-routing.md`).



### execforeignbatchinsert
The FDW callback that inserts a batch of buffered rows in one remote round-trip; the batch size is set by `GetForeignModifyBatchSize`. [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### execforeigninsert
The FDW callback invoked once per inserted row on a foreign table; COPY's multi-insert fast path is bypassed for foreign tables so each row routes through `BeginForeignInsert` / `ExecForeignInsert`. [verified-by-code] (via `knowledge/files/src/backend/commands/copyfrom.c.md`).



### execforeignupdate
The FDW DML callback invoked once per row for `UPDATE`; its `planSlot` holds only the changed columns plus the row-identity junk columns. [from-docs] (via `knowledge/docs-distilled/fdw-callbacks.md`).



### execGrouping
`src/backend/executor/execGrouping.c` — the shared hash-table machinery for grouping/duplicate-elimination executor nodes. It builds `TupleHashTable`s keyed on grouping columns (used by HashAgg, hashed `SubPlan`, `RecursiveUnion`, `SetOp`), wiring per-column equality and hash `FmgrInfo`s into a `simplehash`-backed table. [verified-by-code] (via `knowledge/files/src/backend/executor/execGrouping.c.md`).



### ExecHashJoin
The hash-join node executor (`nodeHashjoin.c:802`) — builds the inner hash table once, then probes it with each outer tuple, handling batching to disk when the table exceeds `work_mem`. A parallel variant shares one hash table across workers. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeHashjoin.c.md`).



### ExecIndexScan
The index-scan node executor (`nodeIndexscan.c`) — repeatedly calls `index_getnext_slot`, applying any non-indexable recheck quals before emitting. Its `ExecIndexScanInitializeDSM` wires up `index_parallelscan_initialize` for a shared parallel scan. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeIndexscan.c.md`).



### ExecInitExpr
Compiles an expression tree (`Expr`) into an executable `ExprState` for a given plan node, resolving function lookups and building the step program once so per-tuple evaluation is cheap. plpgsql hooks here to install its param-eval callbacks. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### ExecInitExprRec
The recursive workhorse of expression compilation in `execExpr.c`: it switches on each source Expr node's `NodeTag` to emit the corresponding `EEOP_*` step(s) into the `ExprState`'s steps array (using a stack-resident scratch `ExprEvalStep` pushed via `ExprEvalPushStep`, which may repalloc). Every Expr node type needs an arm here; the default arm throws `unrecognized node type`, which is how unprocessed parse-tree nodes (e.g. a `SubLink` that bypassed the planner) surface as runtime errors. [verified-by-code] (`execExpr.c:2657-2660` — via `knowledge/files/src/backend/executor/execExpr.c.md`).



### execinitfoo
Naming convention for a plan node's per-node init function, dispatched by node tag from `ExecInitNode`; it allocates the node's `PlanState` and child state in the per-query context. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ExecInitNode
The recursive constructor of the executor's run-time tree: called from
`InitPlan`, it turns each `Plan` node into a `PlanState` (allocating slots,
expression states, and child states) and installs the node's per-tuple
`ExecProcNode` callback. [verified-by-code] (`execMain.c:847` — via
`knowledge/subsystems/executor.md`).



### ExecInitParallelPlan
The parallel-executor entry point that prepares a plan subtree (the body under `Gather`/`Gather Merge`) for execution by worker backends: it builds the `ParallelContext`, allocates the DSM segment, serializes the plan tree, and sets up the tuple queues, returning a `ParallelExecutorInfo` handle stored in the leader's `EState`. The worker count is fixed at init time, and `sendParams` selects which PARAM_EXEC values are serialized into the DSM; `MyClientPort` is deliberately not sent, so workers cannot send results directly to a client. [verified-by-code] (`execParallel.md` — via `knowledge/files/src/include/executor/execParallel.md`).



### execinitpartitionpruning
`ExecInitPartitionPruning` (`execPartition.c`) builds run-time pruning state from a `PartitionPruneInfo` at executor startup, letting Append / MergeAppend skip subplans whose partitions cannot match. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### ExecInitSeqScan
Builds the `SeqScanState` for a sequential-scan plan node: it opens the target relation with the right lock, initializes the scan's qual and projection, and defers the actual `table_beginscan` to first execution. [verified-by-code] (`nodeSeqscan.c` — via `knowledge/files/src/backend/executor/nodeSeqscan.c.md`).



### execinsert
The executor routine that inserts one tuple into a result relation — performing partition routing, constraint checks, and index maintenance; shared by `INSERT` and the insert side of `MERGE` / cross-partition `UPDATE`. [verified-by-code] (via `knowledge/files/src/backend/executor/execPartition.c.md`).



### ExecInsertIndexTuples
The executor routine that, after a heap insert/update, adds index entries for the new tuple to every index on the table (handling partial, expression, and exclusion indexes via an EState); catalog DDL bypasses it for the lighter `CatalogIndexInsert`. [from-comment] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### ExecInterpExpr
The executor's principal expression-evaluation worker (`execExprInterp.c:470`): a single function with every opcode body inlined that walks an `ExprState`'s flat `steps[]` array using direct-threaded computed gotos (or a switch fallback). It is the fast-path of expression execution — every expression in the system runs through it or its JIT mirror, which is why `ExprEvalStep` is hard-capped at 64 bytes. A first-call wrapper `ExecInterpExprStillValid` revalidates `VAR` steps against the slot's TupleDesc before installing `ExecInterpExpr` for subsequent calls. [verified-by-code] (`execExprInterp.c:470` — via `knowledge/files/src/backend/executor/execExprInterp.c.md`).



### execMain
`src/backend/executor/execMain.c` — the executor's top-level driver: `ExecutorStart` (build the `EState`/`PlanState` tree), `ExecutorRun` (pull tuples via `ExecutePlan`), `ExecutorFinish`, and `ExecutorEnd`, plus permission checking (`ExecCheckRTPerms`) and result-relation setup. These four entry points are the hook-points wrapped by extensions like `pg_stat_statements` and `auto_explain`. [verified-by-code] (via `knowledge/files/src/backend/executor/execMain.c.md`).



### ExecMergeJoin
The merge-join executor (`nodeMergejoin.c:596`), a state machine that advances two sorted inputs in lockstep, emitting matches where the merge keys are equal and using mark/restore to replay the inner side across duplicate outer keys. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeMergejoin.c.md`).



### ExecModifyTable
The driver (`nodeModifyTable.c:4606`) for INSERT/UPDATE/DELETE/MERGE — pulls tuples from its subplan, applies the per-row operation through the table AM, and fires BEFORE/AFTER triggers, RETURNING projection, and ON CONFLICT handling. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeModifyTable.c.md`).



### ExecNestLoop
The nested-loop join executor (`nodeNestloop.c:60`) — a `for(;;)` loop that pulls one outer tuple, rescans the entire inner plan against it, and emits matches (plus unmatched outers for left joins). The inner side is re-executed once per outer row. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeNestloop.c.md`).



### ExecParallelFinish
The leader-side wind-down of a parallel plan: it waits for all workers to stop, accumulates their instrumentation and buffer/WAL usage into the leader's counters, and shuts down the parallel context. [verified-by-code] (`execParallel.c` — via `knowledge/files/src/backend/executor/execParallel.c.md`).



### ExecProcNode
The volcano-style "pull one tuple" entry point of a plan node. Rather than a
central switch, each `PlanState` stores its own `ExecProcNode` function pointer
(installed by `ExecInitNode`), so the executor advances any node uniformly by
calling `node->ExecProcNode(node)`. [verified-by-code] (via
`knowledge/files/src/backend/executor/execProcnode.c.md`).



### ExecProcNodeFirst
The wrapper installed as a plan node's `ExecProcNode` on first execution; it performs the one-time `check_stack_depth` and then swaps itself out for the node's real per-tuple routine to avoid the check on every subsequent call. [verified-by-code] (via `knowledge/files/src/backend/executor/execProcnode.c.md`).



### ExecProject
Evaluates a node's target list against the current tuple and stores the result into the node's projection slot, returning that slot. Nodes call it (or skip it when projection is unnecessary) on every row before returning. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeResult.c.md`).



### ExecQual
Evaluates a boolean qualifier ExprState against the current tuple slot, returning true only if the expression is true (SQL NULL counts as false), the standard filter test applied to WHERE/JOIN/HAVING quals during execution. [verified-by-code] (`executor.h` — via `knowledge/files/src/include/executor/executor.h.md`).



### execreadyinterpretedexpr
`ExecReadyInterpretedExpr` inspects the first few opcodes of a freshly-compiled expression and installs a specialized evaluator for common short shapes, falling back to the generic interpreter otherwise. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ExecReScan
Resets a plan node's execution state so it can be scanned again from the start —
used for the inner side of a nested loop, correlated subplans, and rewound
cursors. `execAmi.c` dispatches on `nodeTag` to the per-node `ExecReScan<Node>`
routine, which clears tuple state and rescans children. [verified-by-code] (via
`knowledge/files/src/backend/executor/execAmi.c.md`).



### ExecRowMark
The per-relation executor record describing a row-level lock (`FOR UPDATE` /
`FOR SHARE` or a foreign/auxiliary mark) that EvalPlanQual must re-fetch; it is
paired with an `ExecAuxRowMark` and set up during plan initialization.
[verified-by-code] (via `knowledge/idioms/epq-multi-table.md`).



### ExecScan
The shared executor helper that drives a scan node's main loop — fetch the next tuple via an access-method callback, apply the node's qual, project, and return the slot — reused by SeqScan, IndexScan, ForeignScan and friends. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ExecScanFetch
The inline core of `ExecScan` that fetches the next tuple from an access method (or, under EvalPlanQual, substitutes the recheck tuple) before qual and projection are applied; sharing it keeps every scan node's hot loop consistent. [verified-by-code] (`execScan.h` — via `knowledge/files/src/include/executor/execScan.md`).



### ExecSeqScan
The sequential-scan node executor (`nodeSeqscan.c`). PG18 splits the old single `ExecSeqScan` into specialized variants (no-qual/no-projection, etc.) chosen at init so the hot path skips dead branches; each drives the table AM's `scan_getnextslot`. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeSeqscan.c.md`).



### execseqscanepq
A dedicated sequential-scan variant used when EvalPlanQual is active; `ExecSeqScanEPQ` handles the EPQ re-check path that plain `ExecSeqScan` omits. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ExecShutdownNode
An executor pass run *before* `ExecEndNode` that shuts a plan subtree down early — most importantly to release parallel workers and gather their instrumentation while the node's state is still live. [verified-by-code] (`execProcnode.c:753` — via `knowledge/files/src/backend/executor/execAmi.c.md`).



### ExecSort
The Sort node executor (`nodeSort.c`) — feeds every input tuple into a `tuplesort` on first call, then returns them in order; parallel sorts share state set up by `ExecSortEstimate`/`InitializeDSM`/`InitializeWorker` to do a final merge. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeSort.c.md`).



### ExecStoreHeapTuple
Places a physical `HeapTuple` into a `TupleTableSlot`, optionally taking ownership for pfree; one of the `ExecStore*` family that populates a slot from a particular tuple representation before the executor reads it. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### ExecStoreVirtualTuple
Marks a slot's already-filled `tts_values`/`tts_isnull` arrays as the slot's valid contents (a "virtual" tuple with no physical backing); used after a node computes column values directly. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### ExecSubPlan
Evaluates a SubPlan expression node — a subquery embedded in an expression — handling the ALL/ANY/EXISTS and scalar forms and reusing the hashed subplan when the planner marked it hashable. [verified-by-code] (`nodeSubplan.c` — via `knowledge/files/src/backend/executor/nodeSubplan.c.md`).



### ExecSupportsMarkRestore
Planner-time predicate answering whether a given `Path` yields a plan node that supports the mark/restore protocol (needed on the inner side of a merge join). When it returns false, the planner interposes a Material node. [verified-by-code] (`execAmi.c:419` — via `knowledge/subsystems/executor.md`).



### executeCommand
The `src/fe_utils` query helper that runs a SQL command for its side effects (no result set expected) with uniform echo and error handling, exiting on failure; it is the sibling of `executeQuery` (expects rows) and `executeMaintenanceCommand` (returns instead of exiting). [verified-by-code] (`query_utils.h:19` — via `knowledge/files/src/include/fe_utils/query_utils.h.md`).



### executor
The engine that runs a finished plan tree. Each query passes through the
`ExecutorStart` / `ExecutorRun` / `ExecutorFinish` / `ExecutorEnd` lifecycle;
`ExecutorRun` (hookable, dispatching to `standard_ExecutorRun`) pulls tuples
through the plan node tree one node at a time. [verified-by-code]
(`execMain.c:308,318` — via
`knowledge/files/src/backend/executor/execMain.c.md`).



### ExecutorCheckPerms_hook
The executor hook fired during DML permission checking, giving an extension (e.g. sepgsql) a chance to apply row-/column-level access decisions before execution proceeds; it also fires in parallel workers, so a hook must be parallel-safe. [verified-by-code] (`hooks.c:478` — via `knowledge/files/contrib/sepgsql/dml.c.md`).



### ExecutorEnd
The final phase of executor lifecycle: it shuts down the plan tree
(`ExecEndNode` recursing through every node), releasing per-node resources
after `ExecutorStart`/`ExecutorRun`/`ExecutorFinish`. `standard_ExecutorEnd`
is the default, hookable implementation. [verified-by-code] (`execMain.c:486`
— via `knowledge/architecture/executor.md`).



### ExecutorFinish
The executor phase between `ExecutorRun` and `ExecutorEnd` that fires any
deferred after-triggers and runs `AfterTriggerEndQuery`, so all row processing
is complete before teardown; `standard_ExecutorFinish` is the hookable
default. [verified-by-code] (`execMain.c:417` — via
`knowledge/files/src/backend/executor/execMain.c.md`).



### ExecutorRun
The middle phase of executor lifecycle (after `ExecutorStart`, before
`ExecutorEnd`) that pulls tuples through the plan tree for a given row count
and direction; `standard_ExecutorRun` is the default, hookable implementation.
[verified-by-code] (`execMain.c:318` — via
`knowledge/architecture/executor.md`).



### ExecutorStart
The first of the four-phase executor API
(`ExecutorStart`/`ExecutorRun`/`ExecutorFinish`/`ExecutorEnd`). It builds the
`PlanState` tree from the `PlannedStmt` via `ExecInitNode`, allocates the
`EState`, and wires up result relations and the tuple destination — but runs no
tuples yet. [verified-by-code] (via
`knowledge/files/src/backend/executor/execParallel.c.md`).



### exit_nicely
The frontend convention (each tool defines its own) of a single exit wrapper that runs registered cleanup — disconnecting, removing temp files, restoring terminal state — before calling `exit`. pg_dump's version also closes the archive and any parallel workers. [inferred] (`pg_dump.c:2403` — via `knowledge/files/src/bin/pg_dump/pg_dump.c.md`).



### ExitParallelMode
The transaction-machinery call that leaves parallel mode, paired with `EnterParallelMode`/`IsInParallelMode`; it forms the parallel-mode bridge in xact.c used by parallel.c around worker setup/teardown. [verified-by-code] (`xact.c` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### ExpandedObjectHeader
The in-memory header for the "expanded" representation of complex TOASTable types (arrays, records, jsonb): a phony varlena header equal to `EOH_HEADER_MAGIC` (-1), a pointer to the type's `ExpandedObjectMethods`, the owning MemoryContext, and two stored TOAST pointers (read-write and read-only). It backs the deconstructed in-memory form that re-flattens to the on-disk contiguous varlena on demand. [verified-by-code] (`expandeddatum.h` — via `knowledge/files/src/include/utils/expandeddatum.md`).



### explainforeignscan
The FDW callback that adds wrapper-specific detail (e.g. the generated remote SQL) to a foreign scan's EXPLAIN output; the FDW analogue of a custom node's `ExplainCustomScan`. [verified-by-code] (via `knowledge/files/src/backend/commands/explain.c.md`).



### ExplainPropertyText
One of the format-neutral EXPLAIN output helpers (`ExplainPropertyText`,
`ExplainPropertyInteger`, `ExplainPropertyFloat`, …) that emit a labelled value
into the current `ExplainState`, letting the same node code render correctly as
TEXT, JSON, XML, or YAML. Node-specific EXPLAIN code calls these rather than
printf-ing, so all output formats stay in sync. [verified-by-code] (via
`knowledge/files/src/include/commands/explain_format.h.md`).



### ExplainState
The mutable accumulator threaded through EXPLAIN: it holds the output
`StringInfo`, the chosen format, indentation/grouping stack, and the option
flags (ANALYZE, BUFFERS, VERBOSE…). It is an opaque forward-declared struct
(INV-EXPLAIN-FORMAT) so extensions add output through the property API rather
than poking its fields. [verified-by-code] (via
`knowledge/files/src/include/commands/explain_format.h.md`).



### explicit_bzero
A memory-zeroing call the compiler is forbidden to elide as a dead store, used to scrub secrets (passwords, keys, SCRAM material) from stack/heap buffers before they go out of scope. Plain `memset(p,0,n)` right before a free is a classic dead-store-elimination target, so security-sensitive paths must use this instead. [verified-by-code] (via `knowledge/files/src/port/explicit_bzero.c.md`).



### EXPOSE_TO_CLIENT_CODE
A guard macro used in catalog headers to mark a block of constant definitions
(enum-like character/OID constants) that should also be visible to client code,
so `genbki.pl` copies them into the generated client-facing header. Constants
inside such a block are frequently on-disk values, making them hard to change.
[verified-by-code] (via
`knowledge/files/src/include/catalog/pg_propgraph_element.h.md`).



### Expr
The node supertype for scalar expression trees (`Var`, `Const`, `OpExpr`,
`FuncExpr`, …) evaluated to produce a value during execution. Expression nodes
are compiled into a flat `ExprState` program by `ExecInitExpr` rather than
walked node-by-node at run time. [inferred] (via
`knowledge/files/src/include/nodes/primnodes.h.md`).



### ExprContext
The per-node evaluation scratchpad attached to a `PlanState`: it holds the
inner/outer/scan tuple slots an expression reads and the short-lived
`ecxt_per_tuple_memory` context that `ExecEvalExpr` allocates into and that is
reset once per tuple. [verified-by-code] (`pl_exec.c:8771` — via
`knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### expression index
(a.k.a. functional index) An index whose column is a computed expression such as `lower(col1)`, serving queries like `WHERE lower(col1) = 'value'`. The expression is stored so search never recomputes it, but each insert and non-HOT update must recompute it (the maintenance cost). The query must use the *same* expression form — the planner matches syntactically and will not rewrite equivalents — and the expression must be `IMMUTABLE`. [from-docs §11.7] (via `knowledge/docs-distilled/indexes-expressional.md`).



### expression_planner
Plans a standalone `Expr` that is not part of a `Query`: it runs `fix_opfuncids` + `eval_const_expressions`, producing an executable expression tree for cases like DDL default evaluation. It is the cheapest of the expression-preparation entry points and assumes the input is SubLink-free. [verified-by-code] (`planner.c:7081` — via `knowledge/files/src/backend/optimizer/plan/planner.c.md`).



### expression_tree_walker
The generic recursion driver that visits every sub-node of an expression tree, invoking a caller-supplied `walker` callback with an opaque `context`; returning true from the walker short-circuits. Its transforming counterpart is `expression_tree_mutator`. [verified-by-code] (via `knowledge/idioms/query-tree-walkers.md`).



### ExprEvalStep
One instruction in the flattened `ExprState` evaluation program; the expression
interpreter dispatches on the step opcode, and the JIT provider emits LLVM IR
per step. [verified-by-code] (via
`knowledge/idioms/jit-expression-codegen.md`).



### ExprState
The compiled, flattened form of an expression tree: `ExecInitExpr` walks an
`Expr` once and emits a linear program of `ExprEvalStep`s that
`ExecInterpExpr` (or JIT-compiled code) runs per tuple, avoiding a recursive
tree walk on the hot path. [from-comment] (via
`knowledge/files/src/backend/executor/execExpr.c.md`).



### exprType
Returns the OID of the data type a given expression `Node` evaluates to, by switching on the node tag (`Var`, `Const`, `FuncExpr`, …). It is the universal way analysis, rewrite, and deparse code asks "what type is this?" without caring how the value is produced. [inferred] (via `knowledge/files/src/backend/nodes/nodeFuncs.c.md`).



### exprTypmod
The companion of `exprType` that returns an expression's type modifier (e.g. the `N` in `varchar(N)`), or −1 when unknown. Together they let the planner build a `TupleDesc` for an arbitrary projection. [inferred] (via `knowledge/files/src/backend/nodes/nodeFuncs.c.md`).



### ExtendBufferedRel
The modern bufmgr API for growing a relation by one or more new blocks in the buffer pool (with `ExtendBufferedRelBy`/`ExtendBufferedRelTo`), replacing the old read-a-block-past-EOF idiom and able to extend in bulk under the relation-extension lock. [verified-by-code] (`bufmgr.c:818` — via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ExtendCLOG
Allocates and zeroes the next CLOG page when a freshly assigned xid crosses a page boundary. It runs under `XidGenLock` (held across `ExtendCommitTs` and `ExtendSUBTRANS` too) so the SLRUs grow in lockstep with xid assignment. [from-comment] (via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### ExtendSUBTRANS
Grows the `pg_subtrans` SLRU so it covers a newly assigned XID; it is called under `XidGenLock` during XID allocation in `varsup.c`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### extra_float_digits
GUC governing how many significant digits float output emits; postgres_fdw's `set_transmission_modes()` forces `extra_float_digits=3` (plus `datestyle=ISO`, `intervalstyle=postgres`) under a GUC nestlevel while deparsing Consts so the remote round-trips floats losslessly. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### extractQuery
The GIN opclass support procedure that decomposes a query datum into the set of individual key entries GIN must look up, returning per-entry search modes; `ginscan.c` calls it during scan setup. [from-comment] (`ginscan.c:1-13` — via `knowledge/files/src/backend/access/gin/ginscan.c.md`).



### extractQueryFn
The GIN opclass support function that decomposes a query datum into the set of index keys to search for, plus a per-key search mode; the scan then fetches each key's posting list and combines them via the `consistent`/`triConsistent` function. [verified-by-code] (via `knowledge/idioms/gin-scan-and-consistent.md`).



### FastPathStrongRelationLocks
The shared-memory array of per-hashcode counters that lets the lock manager's fast path work: a weak (relation) locker may take the fast path only while the matching strong-lock counter is zero, and a strong locker bumps it under a spinlock before forcing weak holders to the main table. [verified-by-code] (`lock.c:1832` — via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### FastPathTransferRelationLocks
Moves a relation's weak locks out of backends' per-backend fast-path arrays
into the shared heavyweight lock table when a conflicting strong lock is
requested; it must take each backend's `fpInfoLock`. [from-comment]
(`lock.c:2885-2954` — via
`knowledge/files/src/backend/storage/lmgr/README.md`).



### fastupdate
The GIN index option that batches new entries into an unsorted pending list instead of merging them into the entry tree on every insert; it speeds inserts but adds scan-time work and a periodic merge, and is bounded by `gin_pending_list_limit`. [from-docs] (via `knowledge/idioms/gin-tree-structure.md`).



### FDW
Foreign Data Wrapper — the extension API (`FdwRoutine` in `fdwapi.h`) by which a foreign table is scanned, modified, and planned as if it were local. Callbacks like `GetForeignPaths`, `GetForeignPlan`, `IterateForeignScan`, and the `ExecForeign*` modify hooks let the planner and executor delegate to a remote or external data source. [verified-by-code] (via `knowledge/files/src/include/foreign/fdwapi.h.md`).



### fdw_handler
The pseudo-type of an FDW's handler function; the function `palloc`s and returns an `FdwRoutine` struct of callback pointers that the planner and executor dispatch through. [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### fdw_private
The opaque channel by which an FDW threads its own planning/execution state between callbacks; it exists at three levels — `RelOptInfo.fdw_private` (a bare `void *`), `ForeignPath.fdw_private` and `ForeignScan.fdw_private` (both `List *` so they can be copied/serialized). [verified-by-code] (via `knowledge/docs-distilled/fdw-planning.md`).



### FdwRoutine
The struct of callback pointers (`GetForeignRelSize`, `GetForeignPaths`,
`GetForeignPlan`, `BeginForeignScan`, `IterateForeignScan`, the modify and
analyze hooks, …) that a foreign-data wrapper's `*_handler` function populates
and returns; core code dispatches every FDW operation through it rather than
hard-coding any wrapper. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.h.md`).



### fe_utils
The shared frontend-utility library (`src/fe_utils`) holding code common to the client programs — connection helpers, the table/`printTable` query-output formatter, string and cancel handling — so `psql`, `pg_dump`, and friends don't each reimplement it. [verified-by-code] (via `knowledge/files/src/include/fe_utils/print.h.md`).



### FeBeWaitSet
The long-lived `WaitEventSet` a backend keeps for its main client loop, multiplexing the client socket, the process latch, and postmaster-death detection so it need not rebuild an epoll set on every wait. [verified-by-code] (via `knowledge/files/src/include/libpq/libpq.h.md`).



### FetchPreparedStatementResultDesc
Returns the `TupleDesc` describing a prepared statement's result columns, used to answer a protocol Describe on a named statement without executing it. [verified-by-code] (via `knowledge/files/src/include/commands/prepare.h.md`).



### file_utils
`src/common/file_utils.c` — durability and directory helpers shared by backend and frontend: `fsync_pgdata` / `fsync_dir_recurse` (the crash-safety sync sweep run by initdb, pg_rewind, pg_basebackup), `durable_rename`, and `pg_pwrite_*` wrappers. [verified-by-code] (via `knowledge/files/src/common/file_utils.c.md`).



### FileSet
A named set of temporary files shared among cooperating backends (e.g. parallel hash join), built on the SharedFileSet machinery so any participant can open files created by another and the whole set is cleaned up together. [verified-by-code] (via `knowledge/files/src/backend/storage/file/fileset.c.md`).



### FileTag
A compact fork+segment identifier (`handler` + `forknum` + `rlocator` + `segno`, defined in `sync.h`) used to queue fsync requests from a backend to the checkpointer through the md.c / sync.c machinery. [verified-by-code] (`sync.h:50-56` — via `knowledge/files/src/backend/storage/sync/sync.c.md`).



### filter_by_origin_cb
The optional logical-decoding output-plugin callback that lets a plugin skip changes originating from a given replication origin, the mechanism that breaks infinite loops in bi-directional replication. Returning true drops the change before the row callbacks see it. [inferred] (via `knowledge/idioms/output-plugin-callbacks.md`).



### final_cost_hashjoin
The second-phase hash-join cost estimate (`costsize.c`) — refines the `initial_cost_hashjoin` lower bound with batch count, bucket fill, and parallel-hash sharing once the specific inner/outer paths are known. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### find_other_exec
A `src/common` helper that locates a sibling PostgreSQL executable in the same install directory as the running program and verifies its `--version` matches, so tools like pg_ctl and pg_upgrade invoke the right postgres/initdb binary. It guards against version-mismatched binaries on `PATH`. [inferred] (via `knowledge/files/src/common/exec.c.md`).



### find_rendezvous_variable
The fmgr shared-state lookup (`dfmgr.c`) that returns a stable, process-global pointer slot keyed by a string name, letting two independently-loaded modules find each other without link-time coupling; PL/pgSQL exposes its `PLpgSQL_plugin **` hook table through the `"PLpgSQL_plugin"` rendezvous name this way. [verified-by-code] (via `knowledge/files/src/backend/utils/fmgr/dfmgr.c.md`).



### find_variable
The ECPG preprocessor's top-level resolver for a host-variable reference string: it dispatches to `find_simple`/`find_struct` to resolve field/struct access and `mmfatal`s if the variable was never declared. [verified-by-code] (`variable.c:234` — via `knowledge/files/src/interfaces/ecpg/preproc/variable.c.md`).



### findoprnd
intarray's `query_int` parser helper that wires up operands of a parsed query-int expression; it enforces `delta >= PG_INT16_MIN` and otherwise raises `ERRCODE_PROGRAM_LIMIT_EXCEEDED` ("query_int expression is too complex"). [verified-by-code] (`_int_bool.c:494-501` — via `knowledge/files/contrib/intarray` docs).



### fireRIRrules
The rewriter routine that recursively applies relation-level instead/also
rules — most importantly expanding views into their underlying queries and
applying row-level-security qualifications. [from-comment]
(`rewriteHandler.c:2049-2063` — via
`knowledge/files/src/backend/parser/parse_cte.c.md`).



### FirstGenbkiObjectId
The OID boundary (currently 10000) separating hand-assigned catalog OIDs from those auto-assigned by genbki.pl to bootstrap objects that lack an explicit `oid` in the .dat files, so the build can fill OIDs unattended without colliding with manual ones. [from-README] (via `knowledge/files/src/include/catalog/_README.md`).



### FirstLowInvalidHeapAttributeNumber
A negative sentinel, one below the lowest system attribute number, used as an offset to map (mostly negative) system attnums into a non-negative index range for bitmapsets and similar per-attribute bit arrays. [from-comment] (`sysattr.h` — via `knowledge/files/src/include/access/sysattr.h.md`).



### FirstNormalObjectId
The OID (16384) at which normal runtime object creation begins; everything below is reserved for catalog and bootstrap objects, so an OID ≥ this value identifies a user-created object. [from-README] (via `knowledge/files/src/include/catalog/_README.md`).



### FirstNormalTransactionId
The first ordinary TransactionId (3) that participates in visibility comparison; the three values below it — Invalid(0), Bootstrap(1), Frozen(2) — are special and always sort as older than any normal xid. [verified-by-code] (`transam.h` — via `knowledge/files/src/include/access/transam.h.md`).



### FirstOffsetNumber
The constant `1`: the first valid item-pointer offset within a heap or index page. Line-pointer offsets on a page run `FirstOffsetNumber` .. `MaxOffsetNumber`. [verified-by-code] (`off.h:16` — via `knowledge/files/src/include/storage/off.h.md`).



### FirstSnapshotSet
The backend-global flag recording that the transaction's first snapshot has been taken; snapmgr asserts on it to enforce that a transaction snapshot is established exactly once. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### FirstXactSnapshot
The first snapshot registered in a `REPEATABLE READ`/`SERIALIZABLE`
transaction; it is retained for the transaction's lifetime so all statements see
a stable view and it pins the transaction's xmin horizon. [verified-by-code]
(via `knowledge/idioms/snapshot-active-stack-and-registered.md`).



### FixedParallelState
The fixed-size leader-published control block in a parallel query's DSM
segment, stored under a reserved TOC key; workers read it on attach to recover
the leader's PID, transaction/snapshot context, and other invariant launch
parameters. [from-code] (`parallel.c:1-120` — via
`knowledge/idioms/bgworker-and-parallel.md`).



### FLEXIBLE_ARRAY_MEMBER
The portable spelling of a trailing C99 flexible array member used pervasively
for variable-length structs (a trailing `char name[FLEXIBLE_ARRAY_MEMBER]` or
similar). It lets a struct be over-allocated so the array runs off the end
without tripping bounds checkers. [verified-by-code] (`plpgsql.h:460` — via
`knowledge/files/src/pl/plpgsql/src/plpgsql.md`).



### FlushBuffer
The bufmgr routine that writes a dirty shared buffer's page out to its
relation via `smgrwrite`, after ensuring WAL up to the page's LSN is flushed
(the WAL-before-data rule). Called by the checkpointer, the bgwriter's
`BgBufferSync`, and by any backend that has to evict a dirty victim buffer.
[verified-by-code] (`bufmgr.c:4512-4628` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### FlushErrorState
The elog.c routine that resets the error-data stack depth to -1 after an error has been handled; a `PG_CATCH` block must call it (or `PG_RE_THROW()`), or leftover stack depth makes future `errstart` calls misbehave. [verified-by-code] (`elog.c:2063` — via `knowledge/files/src/backend/utils/error/elog.c.md`).



### fmgr (function manager)
The uniform calling convention for invoking any SQL-callable C function:
arguments and result travel as `Datum`s inside a `FunctionCallInfo`, and
`PG_FUNCTION_INFO_V1` plus the `PG_GETARG_*`/`PG_RETURN_*` macros wrap the
boilerplate. The `FmgrInfo` carries the resolved function, collation, and
argument count. [from-comment] (via `knowledge/idioms/fmgr.md`).



### fmgr_hook
A global hook fired immediately before and after every fmgr-dispatched function call (with a `needs_fmgr_hook` predicate to limit overhead), used by sepgsql to perform per-call permission checks. It is the most invasive of the function-call hooks. [inferred] (`label.c:425` — via `knowledge/files/contrib/sepgsql/label.c.md`).



### fmgr_info
Fills an `FmgrInfo` lookup cache for a function OID — resolving the C entry point, argument count, and strictness — so subsequent `FunctionCall*` invocations skip the catalog lookup; the setup step before repeatedly calling a dynamically-chosen function. [verified-by-code] (via `knowledge/files/src/backend/access/common/scankey.c.md`).



### FmgrInfo
The cached lookup result for a callable function: it bundles the resolved
function pointer, expected argument count, strictness, and a memory context, so
repeated `FunctionCall*` invocations skip the catalog lookup. Built once by
`fmgr_info` and reused for the life of the operation. [from-comment]
(`fastpath.c:37` — via `knowledge/subsystems/tcop.md`).



### fmtId
The fe_utils helper that double-quotes a SQL identifier only when necessary —
the single identifier-quoting chokepoint shared by psql, pg_dump and friends.
It writes into a small set of rotating static buffers, so callers must consume
the result before the next `fmtId` call. [verified-by-code]
(`string_utils.c:44` — via `knowledge/files/src/fe_utils/string_utils.c.md`).



### fmtIdEnc
The encoding-aware variant of `fmtId` that quotes an identifier while
validating it against a specified client encoding; like `fmtId` it shares the
rotating static buffer that callers must consume before the next call.
[verified-by-code] (`string_utils.c:44` — via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### fmtQualifiedId
The `src/fe_utils/string_utils.c` helper that double-quotes a schema-qualified identifier as needed for safe interpolation into generated SQL (the qualified-name counterpart of `fmtId`); both depend on a process-global encoding set via `setFmtEncoding`, which is why their doc comments warn the result is reused per call. [verified-by-code] (`string_utils.c:296` — via `knowledge/files/src/fe_utils/string_utils.c.md`).



### fn_extra
The per-call scratch pointer in `FmgrInfo`/`FunctionCallInfo` that a C function
uses to cache state (compiled regexps, lookup tables, SRF context) across
invocations within one query. It must point into a memory context that lives
long enough — typically `fn_mcxt` — and starts NULL on first call. [verified-by-code]
(via `knowledge/idioms/fmgr.md`).



### fn_mcxt
The memory context recorded in a `FmgrInfo`, guaranteed to live as long as the `FmgrInfo` itself; set-returning and caching functions stash cross-call state there instead of in the (shorter-lived) per-call context. It is the safe home for `fn_extra` allocations. [inferred] (via `knowledge/data-structures/fmgrinfo.md`).



### fn_oid
The OID of the function being called, stored in the `FmgrInfo` set up by `fmgr_info`. SQL-callable C functions read it (via `fcinfo->flinfo->fn_oid`) when one C entry point backs several catalog functions and must discriminate. [inferred] (via `knowledge/data-structures/fmgrinfo.md`).



### foreignasyncrequest
The FDW async-execution callback that produces the next tuple (or registers that it is waiting) for an async-capable foreign scan under Append. [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### foreigndatawrapper
The catalog-cache struct describing an installed FDW — its handler and validator functions plus wrapper-level options; sibling to `ForeignServer` / `ForeignTable` / `UserMapping`. [from-docs] (via `knowledge/docs-distilled/fdw-helpers.md`).



### ForeignPath
The Path node an FDW adds for scanning a foreign table (built via `create_foreignscan_path`); its `fdw_private` carries planner-chosen detail that `GetForeignPlan` later folds into the `ForeignScan` plan node. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### ForeignScan
The executor plan node that scans a foreign table through an FDW. For
postgres_fdw `postgresGetForeignPlan` builds it, `postgresBeginForeignScan`
opens the remote connection and declares a cursor, and `postgresIterateForeignScan`
fetches rows in batches. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### ForeignServer
The in-memory form of a `pg_foreign_server` catalog row (`foreign.h`): server name, owning FDW OID, type/version, and generic options; FDWs look it up via `GetForeignServer`. [verified-by-code] (via `knowledge/subsystems/foreign.md`).



### foreigntable
The catalog-cache struct (from `foreign.c` `GetForeignTable`) describing a foreign table's server and per-table options; sibling to `ForeignServer` / `ForeignDataWrapper` / `UserMapping`. [from-docs] (via `knowledge/docs-distilled/fdw-helpers.md`).



### ForkNumber
The enum selecting which physical fork of a relation (main, fsm, vm, init) an smgr/buffer operation targets; passed to `smgr_bulk_start_rel` and the smgr read/write APIs. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



### FormData
The C struct mirroring a system catalog's fixed columns, named
`FormData_pg_<catalog>` with a pointer typedef `Form_pg_<catalog>`. After
`GETSTRUCT` on a `HeapTuple`, code reads the row's fixed part by casting to this
struct; variable-length/nullable columns past it need `heap_getattr`.
[verified-by-code] (`pg_subscription.h:131` — via
`knowledge/files/src/include/catalog/pg_subscription.h.md`).



### FormData_pg_attribute
The C struct mirroring one row of `pg_attribute` — a column's on-disk definition (`attname`, `atttypid`, `attlen`, `attalign`, `attnotnull`, …). `TupleDesc` attribute arrays are built from these, with a cut-down `CompactAttribute` cached alongside for the hot deform path. [verified-by-code] (via `knowledge/files/src/include/access/tupdesc.h.md`).



### FPI (full-page image)
A complete copy of a disk page written into the WAL the first time the page is
modified after a checkpoint, protecting against torn-page writes during
recovery. `XLogInsert` adds an FPI automatically when needed (tunable per
buffer via `REGBUF_FORCE_IMAGE` / `REGBUF_NO_IMAGE`). [from-comment] (via
`knowledge/files/src/backend/access/transam/xloginsert.c.md`).



### fpInfoLock
The per-backend LWLock in `PGPROC` that guards that backend's fast-path lock
array; `FastPathTransferRelationLocks` must take it, and its ordering against
the heavyweight partition LWLock is a documented subtlety. [from-comment]
(`lock.c:2885-2954` — via
`knowledge/files/src/backend/storage/lmgr/README.md`).



### FreeExecutorState
Tears down an `EState` and everything allocated in its per-query memory context,
called at executor end (and in EPQ teardown) to release tuple slots, expr
contexts, and child run-state. [verified-by-code] (via
`knowledge/idioms/epq-state-init.md`).



### FreePageManager
The buddy-style allocator that tracks runs of free pages inside a DSA/DSM segment, backing dsa.c's sub-allocation; it keeps free ranges in a balanced btree plus size-class freelists so it can satisfy and coalesce variable-length page requests. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/freepage.c.md`).



### freeze_required
The `HeapPageFreeze` flag `heap_prepare_freeze_tuple` sets when a page contains an xid old enough that freezing is mandatory (not merely opportunistic); it forces the page to be frozen even outside an aggressive vacuum. [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### FreezeLimit
The XID cutoff VACUUM computes (from `vacuum_freeze_min_age` against
`OldestXmin`) below which tuple xmins are frozen; tuples older than it get their
xmin marked `FrozenTransactionId`/frozen-bit. [verified-by-code] (via
`knowledge/idioms/vacuum-two-pass-heap.md`).



### FreezeMultiXactId
The vacuum/freeze routine that decides how to rewrite a tuple's xmax MultiXact when freezing: it strips lock-only members and may replace the MultiXact with a plain xid or InvalidTransactionId. [verified-by-code] (via `knowledge/idioms/multixact-slru.md`).



### FreezePageConflictXid
The field in a HeapPageFreeze that accumulates the newest xid whose freezing would generate a recovery-conflict, so the emitted freeze WAL record carries a correct conflict horizon for hot-standby. [verified-by-code] (via `knowledge/files/src/include/access/heapam.h.md`).



### from_collapse_limit
The planner GUC bounding how large a sub-`FROM`/subquery flattening may grow the join search before the planner stops merging; the sibling of `join_collapse_limit` (which defaults to it) for explicit `JOIN` syntax. Lowering it curbs planning time on many-way joins at the cost of join-order freedom. [from-docs] (via `knowledge/docs-distilled/explicit-joins.md`).



### FrontendProtocol
The global recording which version of the PostgreSQL wire protocol the current connection negotiated, set during startup-packet processing. Backend code consults it (via `PG_PROTOCOL_MAJOR`/`MINOR`) to decide message framing and which protocol features — for example negotiated protocol extensions — are available to the client. [verified-by-code] (via `knowledge/files/src/include/libpq/libpq-be.h.md`).



### FrozenTransactionId
The special transaction id 2 that marks a tuple as unconditionally visible to
everyone ("frozen"), removing it from any wraparound danger. Modern code keeps
the real xmin on the tuple and sets `HEAP_XMIN_FROZEN`, so
`HeapTupleHeaderGetXmin` returns `FrozenTransactionId` for frozen tuples; pre-9.4
heaps may still physically store xmin=2 on disk. [from-comment] (via
`knowledge/files/src/include/access/htup_details.h.md`).



### FSM (free space map)
The per-relation map tracking approximate free space in each page so inserts
can find room without scanning. It is itself stored as a relation fork
(`FSM_FORKNUM`) organized as a tree of `BLCKSZ` pages. [from-comment] (via
`knowledge/files/src/backend/storage/freespace/freespace.c.md`).



### fsync_fname
The `src/common/file_utils.c` durability helper that fsyncs a single file or directory by name (opening RDWR for files, RDONLY for dirs); fsync failure is fatal except for directories on OSes that reject directory fsync with EBADF/EINVAL. It opens without `O_NOFOLLOW`, a noted symlink consideration. [verified-by-code] (`file_utils.c:399-447` — via `knowledge/files/src/common/file_utils.c.md`).



### full_page_writes
GUC that makes the first modification of a page after a checkpoint log a full-page image in WAL, guarding against torn pages; pg_rewind and pg_upgrade assume/require it, and disabling it is only safe on hardware with atomic page writes. [verified-by-code] (via `knowledge/files/src/bin/pg_rewind/pg_rewind.c.md`).



### FullTransactionId
A 64-bit transaction id that carries the wraparound epoch in its high 32 bits
alongside the ordinary 32-bit `TransactionId`, so it never wraps and can be
compared with plain integer ordering. Used where wraparound ambiguity would be
fatal, e.g. nextXid bookkeeping. [verified-by-code] (`transam.h:65-68` — via
`knowledge/files/src/include/access/transam.h.md`).



### FUNC_MAX_ARGS
The hard cap on the number of arguments a function may take, defined as 100 in `pg_config_manual.h`. Note that despite this cap, the fmgr `DirectFunctionCallN` family tops out at 9 arguments. [verified-by-code] (`pg_config_manual.h` — via `knowledge/files/src/include/fmgr.h.md`).



### FuncExpr
The `primnodes.h` runtime node for an ordinary function call after parse analysis; `transformFuncCall` produces a `FuncExpr` (or `Aggref`/`WindowFunc`) from a raw `FuncCall`. [from-comment] (via `knowledge/files/src/backend/parser/parse_expr.c.md`).



### FunctionCall2Coll
Invokes a function (via its prepared `FmgrInfo`) with two arguments and an explicit collation OID; the collation-aware member of the `FunctionCallNColl` family used by comparison and pattern operators. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/sortsupport.c.md`).



### FunctionCallInfo
The per-call argument bundle passed to every fmgr-callable C function — flinfo, collation, context/resultinfo, nargs, and the args[] array of (Datum, isnull) pairs; the PG_GETARG_* / PG_RETURN_* macros read and write through it. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### FunctionCallInfoBaseData
The fmgr per-call argument block (`fmgr.h:85-96`): it carries the
`FmgrInfo *flinfo`, the call context node, collation, argument count, a result
NULL flag, and a trailing flexible array of `NullableDatum` args. Every
`PG_FUNCTION_ARGS` function receives a pointer to one, and `PG_GETARG_*` macros
read out of its `args[]`. [verified-by-code] (`fmgr.h:85-96` — via
`knowledge/files/src/include/fmgr.h.md`).



### FunctionCallInvoke
The core fmgr dispatch macro that calls a function through its
`FmgrInfo`/`FunctionCallInfo`, passing already-set-up arguments and returning the
`Datum`; the engine beneath `DirectFunctionCall`/`OidFunctionCall`. [verified-by-code]
(via `knowledge/idioms/fmgr.md`).



### FunctionScan
The executor node that materializes the result of a set-returning function in
the FROM clause, supporting both value-per-call and materialize SRF protocols
and multiple functions via ROWS FROM. [verified-by-code] (via
`knowledge/subsystems/executor.md`).



### Gather
The executor node that collects tuples from parallel workers (and, for
`GatherMerge`, preserves sort order) back into the leader's single stream,
marking the boundary between the parallel and serial portions of a plan. Below
it the plan runs in multiple worker backends; above it execution is serial.
[inferred] (via `knowledge/files/src/backend/executor/nodeGather.c.md`).



### GatherMerge
The parallel-query executor node that collects tuples from multiple worker backends while preserving their common sort order via a binary heap — the order-preserving counterpart to the plain Gather node. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### gbt_num_compress
The btree_gist compress function for scalar (numeric-family) types: given a leaf datum it stores the value twice, as the `[lower, upper]` bounds of a degenerate one-point interval, so internal and leaf entries share the `GBT_NUMKEY` layout. [verified-by-code] (via `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`).



### GBT_NUMKEY
`typedef char GBT_NUMKEY` — btree_gist's opaque byte-storage type for scalar (numeric-family) index keys; each supported type lays out its `[lower, upper]` bounds inside this buffer, which is why `gbt_num_compress` writes the leaf value twice. [verified-by-code] (via `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`).



### gen_keywordlist
The `gen_keywordlist.pl` build-time code generator that turns a `kwlist.h` keyword table into a perfect-hash lookup; it asserts the keyword list is ASCII-sorted at generation time, but nothing re-checks the ordering in the C build, so a hand-edit can silently break it. [from-comment] (via `knowledge/files/src/include/parser/kwlist.h.md`).



### gen_node_support
The Perl generator (`gen_node_support.pl`) that reads the node struct
definitions and emits the `copy`/`equal`/`out`/`read` support functions for
every `Node` type, driven by `pg_node_attr` annotations in the headers. Adding a
node field without re-running it leaves copy/equal silently incomplete.
[verified-by-code] (via `knowledge/files/src/backend/nodes/copyfuncs.c.md`).



### gen_random_bytes
The pgcrypto function returning cryptographically-strong random bytes (alongside `gen_random_uuid`), gated by `pgcrypto.builtin_crypto_enabled`. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### gen_random_uuid
The built-in SQL function (moved into core in PG 13) that returns a freshly generated version-4 random UUID using the backend's strong RNG. It superseded pgcrypto's same-named function for the common case. [inferred] (`uuid.c:524` — via `knowledge/files/src/backend/utils/adt/uuid.c.md`).



### gen_salt
The pgcrypto SQL function that produces a random salt string for `crypt()`, encoding the algorithm (`des`, `md5`, `xdes`, `bf`) and, for adaptive hashes, a work-factor. The corpus flags weak defaults — e.g. `gen_salt('bf')` defaulting to cost 5, below modern guidance. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### generate_join_implied_equalities
Derives the join-level equality clauses implied by an equivalence class (`equivclass.c`) — e.g. from `a=b` and `b=c` it can supply `a=c` across a join, with the OJ-introduced relids folded into `join_relids` so outer-join semantics stay correct. [from-comment] (via `knowledge/files/src/backend/optimizer/path/equivclass.c.md`).



### generate_series
The canonical set-returning function; in the `FROM` clause it is executed by the `FunctionScan` node, which materializes the function's output into a tuplestore (or uses value-per-call for a single-function scan). [from-comment] (via `knowledge/files/src/include/executor/nodeFunctionscan.md`).



### GenerationContext
The MemoryContext type tuned for FIFO/queue allocation lifetimes: each block
tracks `nchunks`/`nfree`, and an emptied block either parks in the single-slot
`set->freeblock` or is returned to malloc, with no per-context freelist.
[verified-by-code] (`generation.c` — via `knowledge/subsystems/utils-mmgr.md`).



### GenerationContextCreate
Constructor for a Generation memory context — a FIFO-ish allocator tuned for objects freed in roughly the order allocated (e.g. tuple streams), which lets whole blocks be reclaimed at once and avoids AllocSet-style fragmentation. [verified-by-code] (`generation.c` — via `knowledge/idioms/memory-contexts.md`).



### generic_xlog
The Generic WAL facility that lets extensions (and some core AMs) WAL-log arbitrary page modifications without writing a custom resource manager; the producer registers buffers, edits page images, and `GenericXLogFinish` computes per-page deltas and emits the record. Redo is generic byte-delta replay, so no extension-specific redo routine is needed. [verified-by-code] (`generic_xlog.c` — via `knowledge/files/src/backend/access/transam/generic_xlog.c.md`).



### GEQO
The Genetic Query Optimizer — the fallback join-order search used when a query's FROM-list size reaches `geqo_threshold`, replacing the exhaustive dynamic-programming search with a randomized genetic algorithm to keep planning time bounded. It registers its own RelOptInfo-building path under the name `"geqo"`. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/extendplan.c.md`; see `knowledge/subsystems/optimizer.md`).



### geqo_threshold
The join count (default 12) at or above which the planner switches from exhaustive dynamic-programming join search to the genetic query optimizer (GEQO); one of the `geqo_*` GUC family driven from `geqo_main.c`. [verified-by-code] (via `knowledge/files/src/backend/optimizer/geqo/geqo_main.c.md`).



### get_actual_variable_range
The selectivity-estimation routine (`selfuncs.c`) that, instead of trusting the histogram, opens the index to read a column's actual current min/max; long runs of dead index entries can slow it, a known planner hotspot. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/selfuncs.c.md`).



### get_attname
An `lsyscache.c` helper returning the name of a column given its relation OID and attribute number; one of the `get_att*` family wrapping `SearchSysCache` over `pg_attribute`. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/lsyscache.c.md`).



### get_attstatsslot
The `lsyscache.c` accessor that fetches one slot of `pg_statistic`'s polymorphic `stavalues`/`stanumbers` arrays for a column; its mate `free_attstatsslot` releases the array memory, which is required because the array contents may be palloc'd separately from the cache tuple. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/lsyscache.c.md`).



### get_call_result_type
Determines a function's result tuple descriptor at run time from the call context (handling polymorphic and RECORD return types), returning a `TypeFuncClass`; the SRF setup helper that resolves what columns to return. [verified-by-code] (via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`).



### get_configdata
The single accessor behind the `pg_config` CLI: given `my_exec_path` it returns an array of `ConfigData{name,setting}` pairs built from build-time `VAL_*` constants plus runtime path resolution, which `pg_config` prints as `name = value` lines. [from-comment] (via `knowledge/files/src/include/common/config_info.h.md`).



### get_matching_partitions
The run-time / plan-time pruning routine (`partprune.c`) returning a Bitmapset of partition indexes whose bounds can satisfy the pruning clauses. [verified-by-code] (via `knowledge/files/src/backend/partitioning/partprune.c.md`).



### get_page_from_raw
The pageinspect helper that reinterprets a raw `bytea` as a `Page`; it deliberately does no header validation itself, so callers that need a sane page must validate before calling. [from-comment] (via `knowledge/files/contrib/pageinspect/pageinspect.md`).



### get_parallel_divisor
The `costsize.c` helper computing the divisor applied to a partial path's per-worker row and cost estimates; it encodes the effective worker count including a fractional term for the leader's own partial participation in the scan. [from-comment] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### get_password_type
`get_password_type()` (`crypt.c:153`) inspects a stored password string and returns whether it is plaintext, MD5, or SCRAM-SHA-256. [verified-by-code] (via `knowledge/docs-distilled/auth-password.md`).



### get_raw_page
The pageinspect SQL function that returns one 8 kB relation block as a raw
`bytea`, the entry point for the rest of the module's page-decoding functions
(`heap_page_items`, `page_header`, `bt_page_stats`). It reads through the buffer
manager, so it sees the in-memory copy of the page. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/pageinspect.md`).



### get_rel_name
Returns the relation name for an OID via the relcache/syscache, or NULL if the OID no longer resolves; callers that print it must guard against the NULL, which signals a stale-OID race. [from-comment] (via `knowledge/files/contrib/pg_plan_advice/pgpa_output.c.md`).



### get_toast_snapshot
The accessor that returns the snapshot used to fetch TOAST chunks; TOAST reads no longer use the statically allocated `SnapshotToast` directly but obtain the snapshot through this function so out-of-line fetches see a consistent view. [verified-by-code] (via `knowledge/files/src/include/utils/snapmgr.h.md`).



### GetAccessStrategy
The buffer-manager entry point (`freelist.c`) that allocates a `BufferAccessStrategy` ring sized by bulk-IO type: `BAS_BULKREAD` scales with the pin limit and io_combine/effective_io_concurrency, `BAS_BULKWRITE` = 16 MB, `BAS_VACUUM` = 2 MB, while `BAS_NORMAL` returns NULL so callers use the global clock sweep. It delegates to `GetAccessStrategyWithSize`, which caps any ring to `NBuffers/8` so a strategy can never starve the shared pool. [verified-by-code] (`freelist.c` — via `knowledge/files/src/backend/storage/buffer/freelist.c.md`).



### GetActiveSnapshot
Returns the snapshot at the top of the active-snapshot stack — the one the
currently executing query should use for visibility. Operations that run "as of
now within this command" (e.g. large-object reads) call it rather than acquiring
a fresh transaction snapshot. [verified-by-code] (via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### GetBufferDescriptor
Returns the `BufferDesc` for a given buffer id from the shared descriptor array;
the descriptor carries the buffer tag, state (refcount/usagecount/flags packed in
an atomic), and content-lock. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### GetCachedPlan
Returns a ready-to-execute `CachedPlan` from a `CachedPlanSource`, replanning if
a dependent object changed or if the generic-vs-custom plan choice flips based
on accumulated cost estimates. [verified-by-code] (via
`knowledge/idioms/cached-plan-invalidation.md`).



### GetCatalogSnapshot
Returns a snapshot specialized for catalog scans — refreshed whenever catalog
invalidations may have occurred — so system-table reads see the latest committed
catalog state without taking a new MVCC snapshot per lookup. [verified-by-code]
(via `knowledge/idioms/snapshot-static-and-current.md`).



### GetChunkSizeFromFreeListIdx
The AllocSet helper mapping a free-list index back to the power-of-two-ish chunk size it holds (`aset.c:146`); the inverse of the size→free-list-index bucketing that AllocSet uses to recycle freed chunks. [verified-by-code] (via `knowledge/idioms/memory-context-allocset-internals.md`).



### GetCommandTagEnum
Maps a command-tag string (e.g. "SELECT") to its `CommandTag` enum via the generated `cmdtaglist.h` table, letting code compare tags by integer instead of by strcmp. [verified-by-code] (`cmdtag.c` — via `knowledge/files/src/backend/tcop/cmdtag.c.md`).



### GetConnection
In `postgres_fdw`, the per-(user-mapping) connection-cache lookup that returns an
existing libpq connection to a foreign server or opens a new one, tracking it
for transaction-scoped cleanup. [verified-by-code] (via
`knowledge/files/contrib/postgres_fdw/connection.c.md`).



### GetCurrentCommandId
Returns the current *command id* (`CommandId`) for the active transaction, optionally marking it `used` so the next `CommandCounterIncrement` allocates a fresh one. Tuples stamp `cmin`/`cmax` with it so a statement cannot see rows its own later commands insert. [verified-by-code] (via `knowledge/data-structures/estate.md`).



### GetCurrentSubTransactionId
The transaction-manager call returning the `SubTransactionId` of the currently active subtransaction. It is part of the subtransaction API used alongside `BeginInternalSubTransaction`, `ReleaseCurrentSubTransaction`, and `RollbackAndReleaseCurrentSubTransaction`. [verified-by-code] (`xact.h` — via `knowledge/idioms/subtransaction-stack.md`).



### GetCurrentTransactionId
Returns the current subtransaction's XID, assigning one on first call (which makes the transaction "real" and visible in the proc array); read-only transactions never call it and so never burn an XID. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



### GetDatabaseEncoding
Returns the current database's server encoding id; the mb-conversion routines' "return the input pointer unchanged when no conversion is needed" contract is built on it, which is what makes conditional `pfree` of converted strings safe. [verified-by-code] (`mbutils.c` — via `knowledge/files/src/backend/utils/mb/mbutils.c.md`).



### GetFdwRoutine
The `foreign.c` function that loads a foreign-data-wrapper's handler and calls it to obtain the `FdwRoutine` callback struct; called lazily and typically cached, it is the entry point through which core code reaches an FDW's methods. [verified-by-code] (via `knowledge/idioms/fdw-routine-callbacks.md`).



### getforeignjoinpaths
The FDW planner callback letting a wrapper offer a path that pushes a join down to the remote side; it differs from base-rel path generation in operating on an already-joined relation. [from-docs] (via `knowledge/docs-distilled/fdw-callbacks.md`).



### getforeignmodifybatchsize
The FDW callback reporting how many rows `ExecForeignBatchInsert` may buffer per remote round-trip, enabling batched inserts (e.g. postgres_fdw's `batch_size`). [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### GetForeignPaths
The FDW callback that generates candidate `ForeignPath` access paths for a foreign table during planning, the foreign-scan analogue of an AM contributing index paths. [from-comment] (via `knowledge/files/contrib/postgres_fdw` and `knowledge/files/src/backend/foreign` docs).



### GetForeignPlan
The FDW planner callback that turns the chosen `ForeignPath` into a `ForeignScan` plan node, packaging whatever the scan callbacks will need into `fdw_private` (typically a `List *`). [inferred] (via `knowledge/docs-distilled/fdw-planning.md`).



### GetForeignRelSize
The first FDW planner callback: it estimates the row count and width of a
foreign relation and stashes FDW-private planning state on the `RelOptInfo`.
[verified-by-code] (via `knowledge/idioms/fdw-routine-callbacks.md`).



### GetForeignRowMarkType
The `FdwRoutine` callback that tells the planner how a foreign table participates in row locking (`SELECT ... FOR UPDATE`/EvalPlanQual) — e.g. whether rows must be re-fetched (`ROW_MARK_COPY`) rather than locked in place. [verified-by-code] (via `knowledge/docs-distilled/fdwhandler.md`).



### getforeignupperpaths
The FDW planner callback that inserts wrapper-provided paths into an upper relation (grouping / aggregation / ordering / final), enabling aggregate and sort pushdown. [from-docs] (via `knowledge/docs-distilled/fdw-planning.md`).



### GetIndexAmRoutine
Calls an index access method's handler function and returns its `IndexAmRoutine` callback struct, asserting that every mandatory callback (`ambuild`, `aminsert`, `amrescan`, `amgettuple`/`amgetbitmap`, `ambulkdelete`, `amvacuumcleanup`, …) is non-NULL. [verified-by-code] (`amapi.c:33` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### GetLatestSnapshot
Takes a fresh MVCC snapshot reflecting the most recently committed transactions,
used (e.g. by `RETURNING` and some DDL) where the command must see rows newer
than the statement's original snapshot. [verified-by-code] (via
`knowledge/idioms/snapshot-static-and-current.md`).



### GetLockConflicts
Returns the list of VXIDs holding heavyweight locks that conflict with a given `LOCKTAG`/mode (`lock.c:3077`). It is how `CREATE INDEX CONCURRENTLY`, DDL, and recovery conflict handling find exactly which transactions they must wait out. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### GetMemoryChunkContext
Returns the MemoryContext that owns a given palloc'd chunk by reading the owning-context reference stored in the chunk's header; underpins pfree/repalloc and context-aware utilities. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### GetMemoryChunkSpace
Returns the total bytes (including header and padding) a given palloc'd chunk
occupies, by dispatching on the chunk's `MemoryContextMethodID`; used by
memory accounting in tuplesort/tuplestore and similar. [verified-by-code]
(`mcxt.c:773` — via
`knowledge/files/src/include/utils/memutils_memorychunk.h.md`).



### GetMultiXactIdMembers
Returns the array of `MultiXactMember` (each an xid plus its lock/update
status) packed into a given MultiXactId, used to resolve exactly who holds
row locks on a tuple whose `xmax` is a multixact. [verified-by-code] (via
`knowledge/subsystems/contrib-pgrowlocks.md`).



### GetNamedDSMSegment
The API that creates-or-attaches a named, fixed-size dynamic-shared-memory segment shared across backends by string name; extensions pair it with `dshash_create`/`dshash_attach` to build process-shared hash tables for their state. [verified-by-code] (`pg_stash_advice.c:567-598` — via `knowledge/files/contrib/pg_stash_advice/pg_stash_advice.c.md`).



### GetNewTransactionId
The allocator for a fresh XID: it advances the shared `nextXid` counter under
`XidGenLock`, extends CLOG/SUBTRANS as needed, fires the wraparound
warning/limit logic, and records the xid in the backend's `PGPROC`. Called
lazily on first write, so read-only transactions never consume an xid.
[verified-by-code] (`varsup.c:68` — via
`knowledge/files/src/backend/access/transam/varsup.c.md`).



### GetOldestNonRemovableTransactionId
Computes the oldest XID whose row versions must still be retained — the vacuum
horizon — by taking the minimum over all backends' xmins, replication slots, and
prepared transactions. [verified-by-code] (via
`knowledge/idioms/xmin-horizon-management.md`).



### GetOldestXmin
The core function returning the oldest transaction id that any current or future snapshot in the cluster could still consider running — the removal horizon below which dead tuples are safe to reclaim. It is **not available during recovery**, so code needing it (e.g. pg_dirtyread's synthetic `dead` column) must hard-error on a standby. On modern PG it is increasingly replaced by the `GlobalVisState *` machinery (`GlobalVisTestFor`). [verified-by-code] (via `knowledge/ideologies/pg_dirtyread.md`; see also `knowledge/idioms/xmin-horizon-management.md`).



### GetPortalByName
Looks up a named portal (cursor) in the per-backend portal hash table, returning the `Portal` used by FETCH/MOVE/CLOSE and by the extended-query protocol's named-portal execution. [verified-by-code] (`portalmem.c` — via `knowledge/files/src/backend/utils/mmgr/portalmem.c.md`).



### GetRecordedFreeSpace
The Free Space Map query that returns the amount of free space recorded for a given heap block (`GetRecordedFreeSpace(rel, heapBlk) → Size`), reading the FSM's per-slot byte category without searching for a page. It is part of the freespace.h public surface alongside `GetPageWithFreeSpace` and `RecordPageWithFreeSpace`. [verified-by-code] (`freespace.c` — via `knowledge/files/src/backend/storage/freespace/freespace.c.md`).



### GetRelationPath
The function (declared in relpath.h, implemented in relpath.c) that composes the filesystem path under PGDATA for a relation from its `(dbOid, spcOid, RelFileNumber)` and fork number. It returns a `RelPathStr` by value (a fixed `char str[REL_PATH_STR_MAXLEN+1]` buffer) to stay allocation-free in critical sections and avoid array-to-pointer decay; it ends with an Assert rather than a runtime check. [verified-by-code] (`relpath.h` — via `knowledge/files/src/include/common/relpath.h.md`).



### GetSnapshotData
The routine that builds an MVCC snapshot by scanning the `ProcArray` under
`ProcArrayLock` (SHARED) to record `xmin`, `xmax`, and the set of in-progress
xids. Its cost scales with the number of active backends, which is why the
snapshot-scalability work cached parts of it. [verified-by-code]
(`procarray.c:2349` — via `knowledge/subsystems/storage-ipc.md`).



### GetTableAmRoutine
The function that calls a table access method's handler and validates that all 30+ mandatory `TableAmRoutine` callbacks are non-NULL; it is the table-AM analogue of `GetIndexAmRoutine`. It is invoked from `relcache.c::RelationInitTableAccessMethod` when a relcache entry is built. [verified-by-code] (`tableamapi.c` — via `knowledge/files/src/backend/access/table/tableamapi.c.md`).



### GetTransactionSnapshot
Returns the transaction's MVCC snapshot — a new one in READ COMMITTED (per
statement), or the single serializable snapshot taken once under
REPEATABLE READ/SERIALIZABLE. It hands back a reference to a statically allocated
snapshot that callers must `RegisterSnapshot` if they need it to outlive the
command. [from-comment] (via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### getTypeOutputInfo
Looks up a type's output function OID and its typisvarlena flag from `pg_type`; the prelude to `OidOutputFunctionCall` when converting an arbitrary Datum to its text representation. [verified-by-code] (via `knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### GetUserId
Returns the current *effective* user OID (the one permission checks run
against), which can differ from the session user under `SECURITY DEFINER` or
`SET ROLE`. Permission-sensitive code such as postgres_fdw picks
`OidIsValid(checkAsUser) ? checkAsUser : GetUserId()` so it acts as the
row-security-defining role, matching `ExecCheckPermissions`. [verified-by-code]
(`postgres_fdw.c:1743` — via
`knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### GetUserMapping
The catalog lookup (`foreign.c`) returning the `UserMapping` for a (role, server) pair; postgres_fdw calls it during scan/modify setup to find the credentials keying its connection cache. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### GetVictimBuffer
The buffer-manager routine that selects a replacement buffer via the clock-sweep (or the free list), writing it out first if it is dirty, so that a page miss can be read into the reclaimed frame. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### getvisibilitymappins
`GetVisibilityMapPins` (`hio.c:138`) pins the visibility-map pages for the two heap buffers an `UPDATE` may touch, acquiring them lower-block-first to avoid deadlock with a concurrent UPDATE choosing the opposite pair. [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### GIN (Generalized Inverted Index)
An index access method optimized for composite values where many keys map to
one row — full-text `tsvector`, arrays, `jsonb` — built around a posting-list
structure plus a pending-list fast path for cheap inserts. Scans union/intersect
posting lists for the matched keys. [from-comment] (via
`knowledge/files/src/backend/access/gin/ginget.c.md`).



### GIN_DATA
A GIN page-opaque flag marking a "data" (posting-tree) page, as distinct from entry-tree, leaf, pending-list, or meta pages. [verified-by-code] (via `knowledge/files/src/include/access/ginblock.h.md`).



### GIN_LIST_FULLROW
A GIN pending-list page flag (in `ginblock.h`) marking that a page contains complete heap rows' worth of entries rather than a partial row. When all entries for one heap tuple fit on a single page the page is flagged `GIN_LIST_FULLROW`; when a single row's entries span multiple pages those pages have the flag clear, and GIN's pending-list cleanup checks the flag to decide row boundaries. [verified-by-code] (`gin-fastupdate-pending.md` — via `knowledge/idioms/gin-fastupdate-pending.md`).



### GIN_MAYBE
A GIN ternary consistent-function result meaning "the indexed keys alone cannot decide the match; recheck against the heap tuple", as opposed to `GIN_TRUE` / `GIN_FALSE`. [inferred] (via `knowledge/files/src/backend/access/gin/ginarrayproc.c.md`).



### GIN_METAPAGE_BLKNO
The fixed block number (0) of a GIN index's metapage; fastupdate pending-list insertion takes a page lock on it to serialise concurrent writers appending to the pending list. [verified-by-code] (via `knowledge/idioms/gin-fastupdate-pending.md`).



### GIN_SEARCH_MODE_ALL
The GIN scan mode that forces a full scan of the entire index entry space rather than a targeted posting-list probe; a `BooleanSearchStrategy` query with no required value (e.g. intarray's `! 42`) selects it, turning an apparently O(log N) index lookup into O(N) work. [verified-by-code] (`_int_gin.c:32-40` — via `knowledge/files/contrib/intarray/_int_gin.md`).



### ginEntryInsert
Inserts one key into GIN's entry tree, creating or extending the posting list / posting tree of heap TIDs for that key. It is the merge target both for direct inserts and for `ginInsertCleanup` draining the pending list. [verified-by-code] (via `knowledge/files/src/backend/access/gin/gininsert.c.md`).



### gingetbitmap
The GIN `amgetbitmap` entry point (`ginget.c`): GIN supports only bitmap scans, so this drives the whole scan — advancing each key stream via `keyGetItem`, merging them in `scanGetItem`, and emitting matching heap TIDs into a TID bitmap. [verified-by-code] (via `knowledge/idioms/gin-scan-and-consistent.md`).



### gininsert
The GIN per-row insert AM slot: with `fastupdate=on` it appends the row's keys to the metapage pending list (`ginHeapTupleFastInsert`); otherwise it extracts keys via the opclass `extractValue` and calls `ginEntryInsert` once per key. [from-comment] (via `knowledge/files/src/backend/access/gin/gininsert.c.md`).



### ginInsertCleanup
Drains GIN's fastupdate pending list into the main entry tree: it scans the list pages head-to-tail, accumulates entries in a `BuildAccumulator`, calls `ginEntryInsert` per merged group, then `shiftList`-deletes the consumed head pages. [from-comment] (via `knowledge/files/src/backend/access/gin/ginfast.c.md`).



### GinMetaPageData
The contents of a GIN index's metapage: the pending-list head/tail block numbers, the pending-list tuple/page counts, entry- and data-page totals, and a version stamp. [verified-by-code] (via `knowledge/files/src/include/access/ginblock.h.md`).



### GinPostingList
GIN's compressed, varbyte-encoded representation of a sorted list of heap TIDs for one index key, stored SHORTALIGN'd in the posting tree/lists; decoding it yields the TIDs a key matches. [verified-by-code] (via `knowledge/files/src/include/access/gin_tuple.h.md`).



### GinScanEntry
A single primitive scan stream inside a GIN index scan: the opclass
`extractQuery` function turns each query into one or more `GinScanEntry`s, each
streaming matching ItemPointers, which the `GinScanKey` consistent function then
combines. [verified-by-code] (via `knowledge/idioms/gin-scan-and-consistent.md`).



### GinScanKey
GIN scan-time structure holding one query key's per-entry scan state (a GinScanEntry array plus consistent-function bookkeeping), built from a qualifying indexable clause. [verified-by-code] (via `knowledge/files/src/include/access/gin_private.h.md`).



### GinState
The per-scan/per-build working struct that caches a GIN index's opclass support
functions and tuple-descriptor details, threaded through routines like
`GinFormTuple` so they need not re-resolve the opclass on every key.
[verified-by-code] (via `knowledge/idioms/gin-tree-structure.md`).



### GiST
Generalized Search Tree — an extensible *template* index AM for tree-structured indexes (R-tree, RD-tree, B-tree-like, …). The opclass author supplies the consistent/union/penalty/picksplit support functions while the core handles page layout, WAL, and concurrency. [from-docs] (via `knowledge/docs-distilled/gist.md`).



### GiST (Generalized Search Tree)
A balanced-tree index access-method *framework* parameterized by an operator
class that supplies `consistent`, `union`, `penalty`, `picksplit`, and friends,
letting one structure serve R-tree, range, nearest-neighbour, and many other
indexing schemes. Search descends subtrees whose predicate the `consistent`
function cannot rule out. [from-comment] (via
`knowledge/files/src/backend/access/gist/gistget.c.md`).



### gistdoinsert
The top-level GiST insertion path (`gist.c`) — descends from the root choosing the subtree whose key needs least enlargement (`gistchoose`), then calls `gistplacetopage`, "the workhorse that performs one step of the insertion", splitting via the opclass `picksplit` when the leaf overflows. [from-readme] (via `knowledge/files/src/backend/access/gist/gist.c.md`).



### GISTMaxIndexKeySize
The hard upper bound on the size of a single GiST index key (derived from what fits on an index page with required overhead); signature-based opclasses like ltree's expose a `siglen` reloption tunable up to this limit. [verified-by-code] (`ltree_gist.c:735` — via `knowledge/files/contrib/ltree/ltree.h.md`).



### GlobalVisCheckRemovableFullXid
Tests whether a given 64-bit FullTransactionId is old enough that no snapshot in the cluster could still see it, i.e. whether a tuple that dead at that xid is safely removable; the FullXid form avoids 32-bit wraparound ambiguity. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtxlog.c.md`).



### GlobalVisCheckRemovableXid
The 32-bit TransactionId convenience wrapper over `GlobalVisCheckRemovableFullXid`, used on hot paths where the caller already holds a plain xid and wraparound is not a concern. [verified-by-code] (via `knowledge/files/src/include/utils/snapmgr.h.md`).



### GlobalVisState
The cached *visibility horizon* a backend carries (field `vistest` on the vacuum/prune state) describing which xids are definitely dead to all sessions. Pruning and HOT-cleanup test tuples against it instead of recomputing `RecentXmin`, so a single snapshot of the global horizon drives a whole page scan. [verified-by-code] (via `knowledge/idioms/vacuum-hot-prune.md`).



### GlobalVisTestFor
The modern visibility-horizon accessor (PG 14+) returning a `GlobalVisState *` for a relation — the lazily-updated, class-specific removal boundary used to test whether a tuple is surely dead — superseding the older scalar `GetOldestXmin` result for pruning/vacuum decisions. [verified-by-code] (via `knowledge/ideologies/pg_dirtyread.md`; see also `knowledge/idioms/xmin-horizon-management.md`).



### GRAPH_TABLE
The SQL/PGQ property-graph query construct that produces a rowset from a graph
pattern match. In the parser it appears as its own range-table-entry kind
(`RTE_GRAPH_TABLE`) with a matching `ParseNamespaceItem`, alongside the other
FROM-item forms. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_relation.c.md`).



### group_lsn
The per-SLRU-page array of WAL LSNs recording, for each group of a page, the latest WAL position that must be flushed before that group may be written back — the mechanism enforcing WAL-before-data for clog status-bit updates. It is monotonic per slot/group. [verified-by-code] (`slru.h:43` — via `knowledge/idioms/clog-slru.md`).



### grouping_planner
The planner stage that takes a single (sub)query's flattened join tree and adds the upper-rel processing — grouping/aggregation, window functions, DISTINCT, ORDER BY, and LIMIT — on top of the cheapest scan/join path, producing the final Path for that query level. It is invoked per subquery_planner level. [from-comment] (via `knowledge/files/src/backend/optimizer/prep/prepunion.c.md`; see `knowledge/subsystems/optimizer.md`).



### GSS
GSSAPI (Generic Security Services API) — the standard interface PostgreSQL uses for Kerberos-based authentication and, optionally, GSS transport encryption of the connection. Both the backend (`be-secure-gssapi.c`) and libpq frontend negotiate and wrap traffic through it when `gss` auth or encryption is requested. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-auth.c.md`).



### GSSENCRequest
The pre-startup negotiation packet a client sends to request GSSAPI transport encryption on the ordinary port — the GSS twin of `SSLRequest`, identified by `NEGOTIATE_GSS_CODE`. [verified-by-code] (`pqcomm.h:129` — via `knowledge/docs-distilled/gssapi-enc.md`).



### GUC (Grand Unified Configuration)
PostgreSQL's runtime configuration-variable system. Every setting (`work_mem`,
`wal_level`, …) is a `config_generic` record with a bool/int/real/string/enum
subclass; all built-in GUCs are registered into one table by
`build_guc_variables` at startup, and extensions add their own via
`DefineCustom*Variable`. [verified-by-code] (`guc.c:871` — via
`knowledge/files/src/backend/utils/misc/guc.c.md`).



### guc_malloc
The GUC subsystem's own allocator wrapper used for string-valued GUCs: it allocates in a long-lived context (not the transient query context) and reports failure at a caller-chosen elevel, which is why string `assign` hooks must `guc_strdup`/`guc_malloc` rather than `palloc`. [inferred] (via `knowledge/scenarios/add-new-guc.md`).



### guc_tables
`src/backend/utils/misc/guc_tables.c` — the static arrays (`ConfigureNamesBool`, `...Int`, `...Real`, `...String`, `...Enum`) that declare every built-in GUC: its name, context, group, default, bounds, and check/assign/show hooks. The GUC machinery in `guc.c` walks these tables at startup to build the runtime hash; adding a built-in setting means adding a row here. [verified-by-code] (via `knowledge/files/src/backend/utils/misc/guc_tables.c.md`).



### GucSource
The enum ranking where a GUC setting came from (default, config file, environment, client, SET, override, …). A pending change is honored only if its `GucSource` is `>=` the source that set the current value, which is how session SET can't be overridden by a lower-priority source. [verified-by-code] (`guc.h:97` — via `knowledge/idioms/guc-variables.md`).



### HandleCopyResult
The psql result-dispatcher (`common.c:938`) that, on a `PGRES_COPY_IN` / `PGRES_COPY_OUT` result, routes to `handleCopyIn` / `handleCopyOut` using `pset.copyStream` so a `\copy` uses the client-side file rather than the server FS. [verified-by-code] (via `knowledge/files/src/bin/psql/copy.c.md`).



### HandleFunctionRequest
The fastpath.c server-side handler for the legacy `PQfn()` fast-path protocol message, which invokes a function by OID directly without going through the parser/planner. [from-comment] (via `knowledge/subsystems/tcop.md`).



### HandleSlashCmds
The top-level psql backslash-command dispatcher (`command.c:230`): it reads the command name via `psql_scan_slash_command` then routes to the matching `exec_command_*` handler. Called by `MainLoop` on every `PSCAN_BACKSLASH` token, and by `startup.c` for `-c \foo` actions (where `query_buf`/`previous_buf` may be NULL). [verified-by-code] (`command.c:230` — via `knowledge/files/src/bin/psql/command.c.md`).



### has_privs_of_role
The ACL routine that tests whether one role has the privileges of another,
following role membership transitively but honoring the `INHERIT` attribute (as
opposed to `is_member_of_role`, which ignores inheritance). It backs most
permission checks on SQL objects. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/acl.c.md`).



### hash_agg_set_limits
`hash_agg_set_limits` (`nodeAgg.c:1807`) computes the hash-table memory ceiling and expected bucket / group counts for hashed aggregation; `hash_agg_check_limits` then triggers spill-to-disk when the ceiling is exceeded. [verified-by-code] (via `knowledge/idioms/aggregate-hash-vs-sort.md`).



### hash_any
The general-purpose Jenkins hash over an arbitrary byte range used throughout the backend (hash indexes, hashed plan nodes, partition routing); it is a non-cryptographic hash, so it carries no collision-attack guarantees. [verified-by-code] (`ltree_op.c:137,184` — via `knowledge/files/contrib/ltree` docs).



### HASH_BLOBS
The `HASHCTL` flag passed to `hash_create` declaring that keys are
fixed-length binary blobs hashed with `tag_hash`, rather than
null-terminated C strings (the default `string_hash`). [verified-by-code]
(via `knowledge/data-structures/dynahash-hashctl.md`).



### hash_bytes
PostgreSQL's general-purpose byte-string hash (a Jenkins-derived mix) returning a 32-bit value; `hash_bytes_extended` gives a 64-bit seedable variant, and these underlie the default hash opclasses and dynahash. [verified-by-code] (via `knowledge/files/src/common/hashfn.c.md`).



### HASH_ELEM
The `HASHCTL` flag telling `hash_create` that `keysize` and `entrysize` are
provided in the control struct; it is set for essentially every dynahash
table. [verified-by-code] (via
`knowledge/data-structures/dynahash-hashctl.md`).



### HASH_ENTER
The dynahash action code passed to `hash_search` (or `hash_search_with_hash_value`) that inserts a key if absent, pulling a fresh entry from the freelist via `get_hash_entry`; contrast `HASH_FIND` and `HASH_REMOVE`. On a shared hash table this op requires the EXCLUSIVE-mode partition (or table) LWLock, whereas `HASH_FIND` needs only SHARED. [verified-by-code] (`dynahash.c` — via `knowledge/files/src/backend/utils/hash/dynahash.c.md`).



### HASH_FIND
The dynahash `HASHACTION` requesting a lookup only (no insert); together with `HASH_ENTER`, `HASH_ENTER_NULL`, and `HASH_REMOVE` it parameterizes `hash_search`. [verified-by-code] (via `knowledge/files/src/backend/utils/hash/dynahash.c.md`).



### HASH_FIXED_SIZE
A dynahash flag declaring that a shared hash table may not grow past its initial size, so all of its space is pre-allocated in shared memory up front. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/shmem_hash.c.md`).



### HASH_MAX_BITMAPS
The cap on how many bitmap pages a hash-index metapage can track via hashm_mapp[]; overflow-page free-space bookkeeping fails once hashm_nmaps reaches it. [verified-by-code] (via `knowledge/files/src/include/access/hash.h.md`).



### HASH_PARTITION
A `dynahash` `HASHCTL` flag that splits a hashtable into N independent partitions, each protected by its own LWLock, for high-concurrency shared-memory use such as the buffer-mapping table and the lock-manager table (16 partitions each by default). The `num_partitions` count must be a power of 2 because that constraint is required for the partition-lock indexing. [verified-by-code] (`dynahash-hashctl.md` — via `knowledge/data-structures/dynahash-hashctl.md`).



### hash_search
The dynahash lookup/insert/remove entry point; the `action` argument is `HASH_FIND` / `HASH_ENTER` / `HASH_ENTER_NULL` / `HASH_REMOVE`, and the `_with_hash_value` variant lets the caller pass a precomputed hash to avoid recomputation. [verified-by-code] (`dynahash.c:889` — via `knowledge/files/src/backend/utils/hash/dynahash.c.md`).



### hash_seq_search
The dynahash iterator: given a `HASH_SEQ_STATUS` initialized by `hash_seq_init`, it returns each entry of a hash table in turn; used to sweep caches (e.g. invalidate every `TypeCacheEntry`) where no key is known. [from-comment] (via `knowledge/idioms/typcache-domain-and-invalidation.md`).



### hash_xlog
The hash-index WAL-replay module (`src/backend/access/hash/hash_xlog.c`) that redoes bucket splits, page inserts, and overflow-page allocation during recovery; the online hash-AM code in `hashovfl.c` / `hashutil.c` emits the records this module replays. [from-comment] (`hash_xlog.c` — via `knowledge/files/src/backend/access/hash/README.md`).



### HashAgg
The hash-based grouping executor strategy (`nodeAgg.c`): it builds an in-memory
`TupleHashTable` keyed by the grouping columns, accumulating transition values
per group, and spills batches to disk when the hash table exceeds `work_mem`
(hash-agg spill). [verified-by-code] (via
`knowledge/files/src/backend/executor/execGrouping.c.md`).



### hashbucketcleanup
The hash-AM deferred-cleanup pass (`hash.c`) that removes dead tuples and, in split-cleanup mode, purges tuples that were copied to a new bucket during a split, running under a cleanup lock. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### HashJoin
The executor node that joins two inputs by building an in-memory (or batched, spill-to-disk) hash table on the inner relation's join key and probing it with each outer row; chosen by the planner for equijoins on large unsorted inputs. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeHash.c.md`).



### HashJoinTable
The in-memory (and optionally batched-to-disk) hash table built by the Hash node for a hash join, holding the inner tuples bucketed by hash value plus the batch bookkeeping that spills excess tuples to temp files when they exceed work_mem. [verified-by-code] (`nodeHash.c` — via `knowledge/files/src/backend/executor/nodeHash.c.md`).



### hashm_firstfree
Hash-index metapage field tracking the first potentially-free overflow-page bitmap bit; the overflow allocator scans from here. Invariant: it may legitimately *underestimate* (cheaper next scan) but must never *overestimate*, or a free page would become unreachable. [from-README] (via `knowledge/files/src/backend/access/hash/hashovfl.c.md`).



### hashm_highmask
The hash-index metapage bit-mask applied to a hash value when the target bucket may lie in the not-yet-fully-populated upper half of the current split point; if the masked bucket exceeds `hashm_maxbucket` the code falls back to `hashm_lowmask`. [verified-by-code] (via `knowledge/files/src/include/access/hash.h.md`).



### hashm_lowmask
The hash-index metapage bit-mask for the lower (already-split) portion of the bucket space, used as the fallback modulus when a hash value masked by `hashm_highmask` would address a bucket above `hashm_maxbucket`. [verified-by-code] (via `knowledge/files/src/include/access/hash.h.md`).



### hashm_maxbucket
The hash-index metapage (`HashMetaPageData`) field recording the highest in-use bucket number; together with `hashm_highmask`/`hashm_lowmask` it defines the current bucket address space during linear (incremental) bucket splitting. [verified-by-code] (via `knowledge/files/src/include/access/hash.h.md`).



### hashm_spares
The hash-index metapage array recording the cumulative count of overflow-page "spares" allocated before each splitpoint group; bucket-number-to-block-number address arithmetic reads it, and because buckets never move once created the array only grows. [from-README] (`README:45-99` — via `knowledge/files/src/backend/access/hash/README.md`).



### hasho_prevblkno
Hash-index page-special field holding the previous block number; on a *primary bucket* page it is overloaded to instead cache the bucket count as of that bucket's last split (a primary bucket's real prev-block is always Invalid), enabling stale-safe metapage caching. [from-README] (via `knowledge/idioms/hash-page-layout.md`).



### hashValue
A 32-bit hash of a catalog tuple's cache key computed by `PrepareToInvalidateCacheTuple`; syscache invalidation matches receivers by `hashValue` rather than by tuple TID so VACUUM FULL (which moves tuples) stays correct. It is also the dependency key in `PlanInvalItem`. [verified-by-code] (`inval.c:64` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### HbaLine
The in-memory parsed form of one `pg_hba.conf` record — connection type,
address range, database/role matchers, auth method, and method options. The
authentication code matches an incoming connection to an `HbaLine` and then runs
the named method (including pluggable validators such as OAuth).
[verified-by-code] (via
`knowledge/files/src/backend/libpq/auth-oauth.c.md`).



### heap
PostgreSQL's default table access method: tuples are stored as
`HeapTupleHeader`-prefixed rows inside `BLCKSZ` pages, with old/new row
versions coexisting for MVCC. HOT (heap-only-tuple) chains and the
tuple-locking protocol — the trickier invariants — are documented in the heap
READMEs. [from-README] (`README.HOT`, `README.tuplock` — via
`knowledge/files/src/backend/access/heap/README.md`).



### HEAP_COMBOCID
The `t_infomask` bit marking that a tuple's `cmin`/`cmax` field actually
stores a "combo command id" — needed because the same transaction both
inserted and later deleted the tuple in different commands, so both a real
cmin and cmax must be recoverable. [verified-by-code] (via
`knowledge/subsystems/access-heap.md`).



### heap_deform_tuple
The heap-AM routine that explodes a `HeapTuple` into parallel `values[]`/`isnull[]` arrays per a `TupleDesc`, walking attributes with alignment/null handling; the eager bulk counterpart to the lazy, per-attribute `heap_getattr`/`nocachegetattr`. [verified-by-code] (`heaptuple.c:1254` — via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### heap_delete
The table-AM-level heap delete: marks a tuple deleted by stamping xmax and the command id, WAL-logs it, and returns a `TM_Result` (TM_Ok / TM_Updated / TM_BeingModified …) so the caller can handle concurrent update races. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### heap_execute_freeze_tuple
Applies a freeze plan produced by `heap_prepare_freeze_tuple` — it mutates the tuple header (clearing xmax, marking xmin frozen) inside the page-prune critical section; the prepare step only *plans* the freeze. [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### heap_form_tuple
Builds a `HeapTuple` from an array of Datums and null flags against a `TupleDesc`: it computes the null-bitmap and data sizes, MAXALIGNs the data offset, palloc's the tuple, and fills the header. The standard constructor for a new heap row. [verified-by-code] (`heaptuple.c:1025` — via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### heap_freetuple
`pfree`s a `HeapTuple` produced by `heap_form_tuple`/`heap_copytuple` in a single free, since the header and data live in one palloc chunk. [verified-by-code] (`heaptuple.c:1372` — via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### heap_freeze_prepared_tuples
The heap routine that applies previously computed `HeapTupleFreeze` plans to a page's tuples inside the prune/freeze critical section (`pruneheap.c`), calling the inline `heap_execute_freeze_tuple`. It is deliberately split from `heap_prepare_freeze_tuple` (which only builds the plan) so VACUUM can validate all tuples before mutating any. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### heap_getattr
Extracts one attribute as a Datum from a `HeapTuple` given its attnum and `TupleDesc`, handling nulls and the cached-offset fast path; hot enough that tuplesort caches the sort key out-of-tuple to avoid calling it per comparison. [verified-by-code] (via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### heap_getnext
The heap-AM sequential-scan accessor that returns the next `HeapTuple` from a scan descriptor, advancing page-at-a-time and applying the scan's snapshot; the table-AM-agnostic callers use `table_scan_getnextslot` instead. [from-comment] (via `knowledge/files/contrib/pgstattuple/pgstattuple.c.md`).



### heap_getsysattr
Returns a *system* attribute of a heap tuple (`ctid`, `xmin`, `xmax`, `cmin`, `tableoid`, …) by negative attribute number, packaging the header field as a `Datum`. Used when a query references a system column. [verified-by-code] (via `knowledge/files/src/backend/access/common/heaptuple.c.md`).



### HEAP_HASNULL
A heap-tuple `t_infomask` data-shape bit (`0x0001`, low byte) set when the tuple contains at least one SQL NULL, signalling that the t_bits null bitmap following the HeapTupleHeader is present and must be consulted when deforming attributes. [verified-by-code] (`htup_details.h` — via `knowledge/files/src/include/access/htup_details.h.md`).



### heap_hot_search_buffer
Follows a HOT chain on an already-pinned buffer starting from a root TID, returning the one chain member visible to the snapshot (or none). Shared by the index-fetch path and other callers that must resolve a HOT chain to a live tuple. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_indexscan.c.md`).



### HEAP_HOT_UPDATED
The `t_infomask2` bit set on the OLD tuple of a HOT update, signalling that
its `t_ctid` points to a same-page successor that continues the HOT chain
(so index entries need not be added for the new version). [verified-by-code]
(via `knowledge/subsystems/access-heap.md`).



### heap_inplace_update_and_unlock
Part of the catalog inplace-update trio (`heap_inplace_lock` / `heap_inplace_update_and_unlock` / `heap_inplace_unlock`): it overwrites a catalog tuple in place — no new tuple version — for fields like `relhasindex`, then releases the buffer/tuple locks. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### heap_insert
The heap access-method routine that inserts one tuple into a relation: it finds a page with free space (RelationGetBufferForTuple), writes the tuple, sets its xmin, marks the buffer dirty, and emits a WAL record. The catalog wrapper `simple_heap_insert`/`CatalogTupleInsert` is the universal "write one system-catalog row" path built on it. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### HEAP_KEYS_UPDATED
An `infomask2` bit indicating that an `UPDATE`/`DELETE` modified key columns (or locked the row `FOR UPDATE`), which affects how the tuple's `xmax` lock conflicts with other lockers. [verified-by-code] (via `knowledge/files/src/include/access/htup_details.h.md`).



### heap_lock_tuple
The heap-AM routine implementing row-level locking (`SELECT FOR UPDATE/SHARE` and EvalPlanQual): it sets the appropriate `HEAP_XMAX_*` lock bits, possibly forming a MultiXact when several lockers coexist, and reports whether it had to wait or the tuple moved. It does not delete the tuple. [inferred] (`heapam.c:1` — via `knowledge/subsystems/access-heap.md`).



### heap_modify_tuple
Builds a new `HeapTuple` from an existing one plus a sparse set of replacement values/nulls, copying unmodified columns through unchanged so they avoid recomputation; the basis for trigger "modify the NEW row" idioms. [verified-by-code] (via `knowledge/files/contrib/spi/autoinc.c.md`).



### HEAP_MOVED_OFF
A heap-tuple `t_infomask` bit (`0x4000`) left over from the pre-9.0 VACUUM FULL implementation that physically relocated tuples; paired with `HEAP_MOVED_IN` (`0x8000`). It is no longer set by modern code but is retained so pg_upgrade'd clusters carrying the bit still interpret old tuples correctly. [verified-by-code] (`htup_details.h` — via `knowledge/files/src/include/access/htup_details.h.md`).



### heap_multi_insert
The heap-AM bulk-insert routine that writes many tuples into a page (or pages) under fewer WAL records than repeated `heap_insert`; COPY uses it for throughput. [verified-by-code] (`heapam.c:1-58` — via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### HEAP_ONLY_TUPLE
An infomask2 bit (`0x8000`) marking a heap tuple that no index points at
directly because it was produced by a HOT update and is reachable only by
following a `t_ctid` chain from an indexed ancestor. It is what lets HOT updates
skip index maintenance. [verified-by-code] (`htup_details.h:293-296` — via
`knowledge/files/src/include/access/htup_details.h.md`).



### heap_page_items
The pageinspect SRF `heap_page_items()` that decodes every line pointer and tuple header (infomask, xmin / xmax, `t_ctid`) on a raw heap page — the primary way to inspect HOT chains and visibility bits. [from-docs] (via `knowledge/docs-distilled/pageinspect.md`).



### heap_page_prune_and_freeze
The combined single-pass routine (PG 17 merged pruning and freezing) that, under a buffer cleanup lock, removes dead/redirected line pointers and freezes eligible tuples on one heap page, emitting one WAL record for both. VACUUM's first phase drives it per page. [inferred] (`heapam.h:260` — via `knowledge/subsystems/access-heap.md`).



### heap_page_prune_execute
Applies a previously computed prune/freeze plan to a heap page (redirect, dead, and unused line-pointer changes); the same routine runs on the primary and during `heap_xlog_prune_freeze` redo so the page ends identical. [verified-by-code] (`heapam.h:444-465` — via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### heap_page_prune_opt
The opportunistic, best-effort HOT-pruning entry point called during ordinary scans (e.g. from `heap_page_prune_opt`-aware `heapgetpage`) when a page looks prunable and a cleanup lock is cheaply obtainable. Unlike VACUUM's pruning it silently gives up rather than wait. [inferred] (`pruneheap.c:269` — via `knowledge/idioms/vacuum-hot-prune.md`).



### heap_pre_freeze_checks
The heap routine (`heapam.c`) that validates a batch of planned freezes before the critical section applies them — asserting each tuple's xmin is committed and xmax aborted/invalid, so freezing cannot lose a still-relevant xid. [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### heap_prepare_freeze_tuple
Examines a single heap tuple during VACUUM and computes (without yet applying) the freeze actions it needs, feeding the batch that `heap_freeze_prepared_tuples` later executes under one WAL record. [verified-by-code] (`heapam.h:406` — via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### heap_prune_chain
The pruning core (`pruneheap.c`, line 1483) that walks one HOT chain from its root line pointer and decides each member's fate — redirect, mark dead, or keep. It enforces the HOT-chain rules (root is non-HOT-only; members carry `HEAP_ONLY_TUPLE`; the chain ends at a self-`t_ctid`, aborted xmin, or off-page pointer). [verified-by-code] (via `knowledge/files/src/backend/access/heap/pruneheap.c.md`).



### heap_toast_insert_or_update
The heap-AM entry point that, on insert/update of a tuple too wide for a page, compresses and/or pushes out-of-line the largest TOAST-able attributes until the tuple fits, writing chunks to the relation's TOAST table. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heaptoast.c.md`).



### heap_update
The heap access-method routine that replaces a tuple with a new version: it sets the old tuple's xmax and `t_ctid` to point at the new tuple (forming the update chain), inserts the new version (HOT-updating on the same page when no indexed column changed), and WAL-logs the change. System-catalog updates go through `simple_heap_update`/`CatalogTupleUpdate`. [verified-by-code] (via `knowledge/files/contrib/sepgsql/relation.c.md`).



### heap_vacuum_rel
The top-level entry point of lazy VACUUM for one heap relation: it runs the two-pass scan (prune+freeze, collect dead TIDs, vacuum indexes, reap line pointers), updates the visibility map and free-space map, and writes new `pg_class` stats. [verified-by-code] (`vacuumlazy.c:623` — via `knowledge/idioms/vacuum-two-pass-heap.md`).



### HEAP_XMAX_COMMITTED
A heap-tuple infomask hint bit (`0x0400`) recording that the transaction stored in `t_xmax` has been observed committed, so later visibility checks can skip the CLOG lookup. It is one of the visibility hint-bit family alongside `HEAP_XMIN_COMMITTED`, `HEAP_XMIN_INVALID`, and `HEAP_XMAX_INVALID`. [verified-by-code] (`htup_details.h` — via `knowledge/files/src/include/access/htup_details.h.md`).



### HEAP_XMAX_INVALID
A heap-tuple `t_infomask` visibility hint bit (`0x0800`) recording that the tuple's xmax is known invalid — the deleting/locking transaction aborted or xmax was never validly set — so a visibility check can treat the tuple as not-deleted without a CLOG probe. It also participates in the three-part `HeapTupleHeaderIsHotUpdated` check (HOT chains are auto-broken when the updating xact aborts and this bit is set). [verified-by-code] (`htup_details.h` — via `knowledge/files/src/include/access/htup_details.h.md`).



### HEAP_XMAX_IS_MULTI
The heap tuple infomask bit signalling that `t_xmax` holds a MultiXactId rather than a plain transaction XID; visibility and locking code must bounds-check the multixact before interpreting the field. [verified-by-code] (via `knowledge/idioms/locking-overview.md` and `knowledge/files/src/backend/access/heap` docs).



### HEAP_XMAX_LOCK_ONLY
A heap-tuple infomask bit indicating that xmax is a locker, not an updater — i.e. the xmax transaction merely locked the row rather than modifying it. It discriminates lockers from updaters during MVCC visibility checks and update-chain walks; without checking it, a locker tuple is mistaken for an updater. [verified-by-code] (`htup_details.h` — via `knowledge/idioms/tuple-locking-modes.md`).



### HEAP_XMIN_COMMITTED
A heap-tuple hint bit caching "this tuple's inserting xact is known committed"
(its `HEAP_XMAX_COMMITTED` sibling does the same for the deleter). A set hint
may only be written after that xact's commit WAL is flushed, so a hint never
lies even though it is not itself WAL-logged. [verified-by-code]
(`heapam_visibility.c:142` — via `knowledge/subsystems/access-heap.md`).



### HEAP_XMIN_FROZEN
The infomask bit-combination (`HEAP_XMIN_COMMITTED | HEAP_XMIN_INVALID`) that marks a tuple's inserting xid as frozen, so the tuple is unconditionally visible regardless of the current xid horizon. Modern freezing sets these bits in place instead of overwriting xmin with `FrozenTransactionId`. [inferred] (`htup_details.h:204` — via `knowledge/idioms/heap-tuple-freeze.md`).



### HEAP_XMIN_INVALID
A heap-tuple `t_infomask` visibility hint bit (`0x0200`) indicating the tuple's inserting transaction (xmin) is known aborted/invalid. The bits are hints, not authoritative, and `HEAP_XMIN_COMMITTED|HEAP_XMIN_INVALID` set together (`0x0300`) is reused to encode the frozen state (`HEAP_XMIN_FROZEN`). [verified-by-code] (`htup_details.h` — via `knowledge/files/src/include/access/htup_details.h.md`).



### heapam_handler
The table-AM shim (`src/backend/access/heap/heapam_handler.c`) that registers the heap access method's `TableAmRoutine` and forwards nearly every callback to the real implementations in `heapam.c` / `heapam_visibility.c` / `pruneheap.c`. It is the concrete example every custom table-AM is written against. [verified-by-code] (`heapam_handler.c` — via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### heapam_visibility
`src/backend/access/heap/heapam_visibility.c` — the home of the `HeapTupleSatisfies*` visibility routines (`...MVCC`, `...Self`, `...Dirty`, `...Vacuum`, `...HistoricMVCC`, etc.) that decide, against a given snapshot, whether a heap tuple version is visible. It also sets hint bits (`HEAP_XMIN_COMMITTED` / `HEAP_XMAX_COMMITTED`) as a side effect of resolving xmin/xmax commit status via CLOG. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### heapam_xlog
`src/backend/access/heap/heapam_xlog.c` — the WAL redo half of the heap access method: `heap_redo` / `heap2_redo` dispatch on the xl_info opcode and replay `XLOG_HEAP_INSERT`, `_UPDATE`, `_DELETE`, `_HOT_UPDATE`, `_LOCK`, vacuum/prune, and freeze records, mirroring the write-side WAL generated in `heapam.c`. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_xlog.c.md`).



### heapBlk
The heap block number a BRIN summary tuple summarizes, stored both in the index tuple (`bt_blkno`) and in the WAL record; BRIN redo asserts the two agree (`tuple->bt_blkno == xlrec->heapBlk`) to catch WAL corruption. [verified-by-code] (`brin_xlog.c:83` — via `knowledge/files/src/backend/access/brin/brin_xlog.c.md`).



### heapgettup_pagemode
The page-at-a-time heap scan iterator (`heapam.c:1073`): for each new block it locks the buffer once, calls `heap_prepare_pagescan` to populate `rs_vistuples[]` via `HeapTupleSatisfiesMVCCBatch`, then unlocks and walks the visible-tuple array without re-locking. This is the modern MVCC path; the older `heapgettup` holds the lock across the whole page. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### HeapKeyTest
The inline function (in `access/valid.h`) that applies an array of
`ScanKey`s to a heap tuple, returning whether it satisfies all of them — the
qual-check heap scans use after fetching a candidate tuple. `systable_beginscan`
falls back to it when it does a sequential scan instead of an index scan.
[verified-by-code] (via `knowledge/files/src/include/access/valid.h.md`).



### HeapTuple
The lightweight in-memory wrapper for a heap row:
`struct HeapTupleData { uint32 t_len; ItemPointerData t_self; Oid t_tableOid;
HeapTupleHeader t_data; }` — a length, the row's self-TID, its table OID, and a
pointer to the on-page header. The bit-level layout lives in `htup_details.h`.
[verified-by-code] (`htup.h:62-69` — via
`knowledge/files/src/include/access/htup.h.md`).



### HeapTupleData
The in-memory heap-tuple wrapper struct: `t_len`, `t_self` (the self-TID), `t_tableOid`, and `t_data` pointing at the on-disk `HeapTupleHeader`; `HEAPTUPLESIZE` is `MAXALIGN(sizeof(HeapTupleData))`. [verified-by-code] (`htup.h:62-69` — via `knowledge/files/src/include/access/htup.h.md`).



### HeapTupleFreeze
The plan record produced by `heap_prepare_freeze_tuple` describing how one
tuple is to be frozen; computed outside any critical section and only later
applied by `heap_freeze_prepared_tuples` inside the prune/freeze crit section,
so all per-page checks batch before the section is entered. [from-comment]
(`heapam.h:153` — via `knowledge/subsystems/access-heap.md`).



### HeapTupleGetDatum
Static inline that wraps a `HeapTuple` as a composite (row) `Datum` by exposing its `t_data` header; the return idiom for a function producing a composite/record result. [verified-by-code] (`funcapi.h:229-233` — via `knowledge/files/src/include/funcapi.h.md`).



### HeapTupleGetUpdateXid
For a tuple whose `xmax` is a multixact, returns the actual updating or deleting XID among the multixact members (or the plain `xmax` when it is not a multixact). [verified-by-code] (via `knowledge/files/src/include/access/htup_details.h.md`).



### HeapTupleHeader
The on-page prefix of every heap tuple (`HeapTupleHeaderData`): it carries the
`xmin`/`xmax` transaction stamps, the `t_ctid` forward link, an infomask of
status bits, and the null bitmap, ahead of the user data. Its bit-level layout
and accessor macros live in `htup_details.h`. [from-comment] (via
`knowledge/files/src/include/access/htup_details.h.md`).



### HeapTupleHeaderData
The on-disk header prefixed to every heap tuple, holding the xmin/xmax
transaction stamps, infomask flags, the tuple's TID (`t_ctid`), and the null
bitmap; since 8.3 cmin and cmax share one field, disambiguated via the
combo-CID machinery. [from-comment] (via
`knowledge/files/src/backend/utils/time/combocid.c.md`).



### HeapTupleHeaderGetCmin
The accessor returning a tuple's real insert command id (cmin); it asserts the tuple's xmin is the current transaction and, when `HEAP_COMBOCID` is set, indirects through the combo-CID map rather than reading `t_cid` directly. MVCC visibility uses it (e.g. comparing against `snapshot->curcid`) so a command does not see rows inserted by a later command in the same transaction; callers must never read `t_cid` directly. [verified-by-code] (`combocid.c:104` — via `knowledge/files/src/backend/utils/time/combocid.c.md`).



### HeapTupleHeaderGetRawXmin
Accessor returning a tuple header's raw xmin *without* the frozen-xid substitution; syscache validity checks use it, e.g. comparing a cached `fn_xmin` against the live `pg_proc` tuple's raw xmin to detect that the row was replaced. [verified-by-code] (`fmgr.c:178` — via `knowledge/files/src/pl/plpython/plpy_procedure.md`).



### HeapTupleHeaderGetUpdateXid
Returns the updating xid of a heap tuple, transparently resolving the `HEAP_XMAX_IS_MULTI` case by reading the MultiXact members. Because that lookup can `palloc`, callers inside critical sections must avoid it (the `GetCmax` assert is deliberately weakened for this reason). [verified-by-code] (via `knowledge/files/src/backend/utils/time/combocid.c.md`).



### HeapTupleHeaderGetXmin
The accessor returning a tuple's inserting transaction id, honouring the
frozen bit: it yields `FrozenTransactionId` when `HEAP_XMIN_FROZEN` is set,
otherwise the raw stored xmin (`htup_details.h:328`). MVCC visibility and freeze
logic read xmin exclusively through it so frozen tuples are handled uniformly.
[from-comment] (`htup_details.h:314-321` — via
`knowledge/files/src/include/access/htup_details.h.md`).



### HeapTupleIsSurelyDead
The heap-visibility helper that reports whether a tuple is dead relative to a supplied oldest-xmin horizon (i.e. dead to *every* possible snapshot, hence reclaimable), as opposed to dead only to a particular snapshot. VACUUM-adjacent code and forensic tools (pg_dirtyread's `dead` column) use it to classify already-removed rows. [verified-by-code] (via `knowledge/ideologies/pg_dirtyread.md`).



### HeapTupleSatisfies
The prefix of the MVCC visibility-oracle family in `heapam_visibility.c` (`HeapTupleSatisfiesMVCC`, `…Vacuum`, `…Dirty`, `…SelfUpdated`, `…HistoricMVCC`, …); every routine may also set hint bits and `MarkBufferDirtyHint` when it observes a transaction has committed or aborted. [from-comment] (via `knowledge/subsystems/access-heap.md`).



### HeapTupleSatisfiesMVCC
The visibility test for an ordinary snapshot-based `SELECT`: it decides whether one heap tuple is visible under a given MVCC snapshot by consulting `xmin`/`xmax`, CLOG, and hint bits, and may set hint bits as a side effect. [verified-by-code] (`heapam_visibility.c:938` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### HeapTupleSatisfiesMVCCBatch
The batched, page-at-a-time MVCC visibility routine that amortizes hint-bit setting across a whole heap page's line pointers; it is the only visibility caller that uses the amortized hint-bit path. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### HeapTupleSatisfiesUpdate
The visibility routine that decides whether a tuple can be updated/deleted now,
returning an `HTSU_Result` (e.g. `MayBeUpdated`, `Updated`, `BeingModified`)
that drives EPQ rechecks and tuple-lock waits. [verified-by-code] (via
`knowledge/idioms/tuple-locking-modes.md`).



### HeapTupleSatisfiesVacuum
The visibility routine that classifies a tuple for VACUUM relative to the
`OldestXmin` horizon — `DEAD`, `LIVE`, `RECENTLY_DEAD`, `INSERT_IN_PROGRESS`,
`DELETE_IN_PROGRESS` — deciding what can be reclaimed. [verified-by-code] (via
`knowledge/idioms/vacuum-two-pass-heap.md`).



### HeapTupleSatisfiesVisibility
The dispatch wrapper that applies a snapshot's `satisfies` method to a heap
tuple, returning whether the tuple is visible under that snapshot; the entry
point heap scans call per tuple. [verified-by-code] (via
`knowledge/idioms/snapshot-static-and-current.md`).



### hemdist
The ltree GiST Hamming-distance function over signature bitmaps, used for penalty and picksplit decisions; it calls `pg_popcount` per comparison, so a picksplit's O(n^2) pairing over ~120 entries of a 224-bit signature runs ~14 400 popcounts. [from-comment] (via `knowledge/files/contrib/ltree/_ltree_gist.c.md`).



### HENTRY_POSMASK
The hstore on-disk mask `0x3FFFFFFF` that reserves the top 2 bits of an `HEntry` for flags (e.g. `HENTRY_ISNULL`) and uses the low 30 bits for the end-position offset of a key/value within the string area. As invariant INV-1 it caps the hstore string area at ~1 GB; the compat re-encode loop applies `& HENTRY_POSMASK` with no overflow guard, so a `pos + keylen` overflow is silently truncated rather than rejected. [verified-by-code] (`hstore.h` — via `knowledge/files/contrib/hstore/hstore.h.md`).



### highmask
The hash-index metapage bitmask applied to a hash code when the candidate bucket exceeds `maxbucket`; the high/low mask pair implements linear hashing so only one bucket splits at a time as the index grows. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### hint bit
A cached commit/abort status bit (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_COMMITTED`,
…) stamped into a tuple's infomask the first time a backend resolves its
transaction's fate via clog, so later visibility checks skip the clog lookup.
Setting one only dirties the page as a *hint* (`MarkBufferDirtyHint`) and is not
WAL-logged unless checksums/`wal_log_hints` are on. [from-comment] (via
`knowledge/subsystems/access-heap.md`).



### HistoricSnapshot
A special snapshot installed by `SetupHistoricSnapshot` for logical decoding:
rather than ProcArray-based visibility it consults the reorder buffer's
catalog-tuple view, letting decoding see catalog rows as they stood at a past
point in WAL. [verified-by-code] (via
`knowledge/idioms/snapshot-export-historic-parallel.md`).



### HistoricSnapshotActive
A snapshot-manager predicate (one of the `SetupHistoricSnapshot` / `TeardownHistoricSnapshot` logical-decoding hooks) reporting whether a fixed "historic" catalog snapshot is currently installed. When active, `GetCatalogSnapshot` returns that historic snapshot, and `GetTransactionSnapshot` branches on it. [verified-by-code] (`snapmgr.c` — via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### HMAC
Hash-based Message Authentication Code — a keyed hash (RFC 2104) PostgreSQL uses for SCRAM and in pgcrypto; the backend wraps OpenSSL's implementation (or an in-tree fallback) behind a px_hmac / pg_hmac vtable. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/px-hmac.md`).



### HOLD_INTERRUPTS
The macro that increments `InterruptHoldoffCount` to defer processing of
cancel/die interrupts inside a sensitive region; it is paired with a
matching `RESUME_INTERRUPTS` and is weaker than a full critical section.
[verified-by-code] (via `knowledge/subsystems/storage-lmgr.md`).



### holdcontext
A holdable cursor's `holdContext` is a memory context created as a *sibling* of the portal context under `TopPortalContext`, so the materialized tuplestore can outlive the portal after the transaction commits. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### HOT (heap-only tuple)
An UPDATE optimization: when no indexed column changes and the new row version
fits on the same page, PostgreSQL chains the new tuple to the old via `t_ctid`
without inserting new index entries. The update is logged as
`XLOG_HEAP_HOT_UPDATE`, and index scans reach the live version by following the
HOT chain from the indexed root tuple. [verified-by-code] (`heapam.c:62` — via
`knowledge/files/src/backend/access/heap/heapam.c.md`).



### hot_standby_feedback
GUC that makes a hot standby report its oldest xmin back to the primary so the primary's VACUUM won't remove rows the standby's queries still need — at the cost of delaying cleanup on the primary. [from-README] (via `knowledge/docs-distilled/hot-standby.md`).



### hstore_concat
The hstore `||` operator implementation, merging two hstores with right-hand keys overriding left-hand duplicates — the canonical key-merge pattern reused by hstore's subscripting-assignment path. [from-comment] (via `knowledge/files/contrib/hstore/hstore_subs.c.md`).



### hstore_recv
The binary-input (receive) function for the `hstore` type; because it reconstructs the on-disk representation directly from wire bytes rather than from text, it can produce internal shapes the text input syntax cannot, so downstream code must not assume text-only invariants. [verified-by-code] (via `knowledge/files/contrib/hstore/hstore_subs.c.md`).



### hstoreCheckKeyLen
The hstore length guard that ereports if a key exceeds `HSTORE_MAX_KEY_LEN` (with `hstoreCheckValLen` for values); both the text input (`hstore_in`) and binary receive (`hstore_recv`) paths route through it so over-long keys can't be constructed. [verified-by-code] (via `knowledge/files/contrib/hstore/hstore_io.c.md`).



### hstoreUpgrade
The hstore compatibility routine that promotes a pre-9.0 on-disk hstore value to the current format on read; its compat path can in principle produce a value that passes validation yet encodes an unusual shape, so consumers must not over-trust hstore bytes. [verified-by-code] (`hstore_op.c:172` — via `knowledge/files/contrib/hstore/hstore_op.c.md`).



### HTAB
The handle type for PostgreSQL's built-in dynamic hash table (`dynahash`), created by `hash_create` and used pervasively for in-memory and shared-memory hash tables (lock tables, catcache, plan caches, FDW shippability caches). Shared-memory HTABs are fixed-size and partitioned; backend-local ones can grow. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/shippable.c.md`).



### htup_details
`src/include/access/htup_details.h` — the header defining the on-disk heap-tuple layout: `HeapTupleHeaderData` (xmin/xmax/cid/ctid, the `t_infomask` / `t_infomask2` flag words, the null bitmap), plus the macros that read and set those fields (`HeapTupleHeaderGetXmin`, `...GetUpdateXid`, the `HEAP_*` infomask bits). The single most-cited header for MVCC and tuple-visibility code. [verified-by-code] (via `knowledge/files/src/include/access/htup_details.h.md`).



### ICU
International Components for Unicode — the optional collation provider PostgreSQL can use instead of the libc locale for sorting and case handling. `pg_locale_icu.c` wraps ICU collators and version strings so a database or per-column collation can pin deterministic, version-tracked Unicode ordering. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/pg_locale_icu.c.md`).



### IDENTIFY_SYSTEM
The first replication-protocol command a client issues: the walsender replies
with the system identifier, current timeline, current WAL flush position, and
default database, which the client uses to set up streaming. [verified-by-code]
(via `knowledge/files/src/backend/replication/repl_gram.y.md`).



### idle_in_transaction_session_timeout
GUC terminating a session that sits idle inside an open transaction longer than the limit, releasing the locks and xmin such a session pins; measured in ms and declared with the other timeout GUCs in `proc.h`. [verified-by-code] (via `knowledge/files/src/include/storage/proc.h.md`).



### importforeignschema
`ImportForeignSchema` (IMPORT FOREIGN SCHEMA) calls the FDW's `ImportForeignSchema` callback, which returns a list of `CREATE FOREIGN TABLE` statements that the command then executes through `ProcessUtility`. [verified-by-code] (via `knowledge/files/src/backend/commands/foreigncmds.c.md`).



### in_progress_list
The typcache guard list tracking type-cache entries currently being (re)built, so that an invalidation arriving mid-build is not lost; it is allocated as the last step of `lookup_type_cache`'s OOM-resilient lazy init and finalized at end of (sub)transaction. [verified-by-code] (via `knowledge/idioms/typcache-entry-and-lookup.md`).



### INCLUDE (covering-index payload)
The `CREATE INDEX … INCLUDE (cols)` clause that adds non-key payload columns to an index: stored but never interpreted by the index machinery (they need not be of an indexable type), they enable index-only scans and, thanks to B-tree suffix truncation, keep internal pages small. A key+payload tuple exceeding the index type's maximum tuple size makes the *insertion fail*, so wide INCLUDE columns are a footgun. [from-docs §11.9] (via `knowledge/docs-distilled/indexes-index-only-scans.md`).



### INCOMPLETE_SPLIT
A btree page flag recording that a page was split but its parent downlink has
not yet been inserted (the downlink is a separate WAL record). A later
insert/scan that encounters the flag must finish the split first; this two-step
design is what makes nbtree split crash-safe without holding parent locks during
the split. [verified-by-code] (via
`knowledge/files/src/backend/access/nbtree/nbtinsert.c.md`).



### IncrementalBackupInfo
An opaque object built from the prior backup manifest plus WAL summaries; it answers, per relation block, whether that block changed since the prior backup, letting an incremental base backup send only changed blocks. [verified-by-code] (via `knowledge/files/src/include/backup/basebackup_incremental.h.md`).



### IncrementalSort
The executor node that sorts rows already partially ordered by a prefix of the
sort key, sorting only within prefix-equal groups to reduce memory and start-up
cost versus a full Sort. [verified-by-code] (via
`knowledge/subsystems/executor.md`).



### index-only scan (IOS)
A scan that answers a query entirely from an index, skipping the heap, when every referenced column is stored in the index AND the per-page `VM_ALL_VISIBLE` bit is set. Because visibility (xmin/xmax) lives only in heap tuples, the visibility map is the side channel that makes skipping the heap safe; heavily-updated tables keep VM bits cleared and degrade IOS to ordinary index scans (VACUUM resets the bits). B-tree always supports it; GiST/SP-GiST only for some opclasses; GIN never. [from-docs §11.9] (via `knowledge/docs-distilled/indexes-index-only-scans.md`).



### INDEX_ALT_TID_MASK
An nbtree index-tuple header bit marking a tuple as "alternative TID" format — either a deduplicated posting-list tuple or a pivot/high-key — in which case `t_tid`'s block and offset fields carry packed metadata rather than a heap pointer (combined with `BT_IS_POSTING` for posting lists). [verified-by-code] (via `knowledge/files/src/include/access/nbtree.h.md`).



### index_beginscan
The genam-level entry point that opens an index scan: it allocates the
`IndexScanDesc`, binds the index and heap relations and snapshot, and calls the
AM's `ambeginscan`. It is one of the "INTERFACE ROUTINES" in `indexam.c`
(`index_open`/`index_beginscan`/`index_getnext_tid`/…) that wrap the AM
callbacks. [from-comment] (`indexam.c:13-40` — via
`knowledge/files/src/backend/access/index/indexam.c.md`).



### index_build
The phase of index creation that scans the heap and populates a freshly-created empty index by calling the AM's `ambuild`; invoked by `index_create` (and reindex) after the catalog rows exist. [inferred] (via `knowledge/files/src/backend/catalog/index.c.md`).



### index_close
Releases an index relation opened with `index_open`, optionally dropping the lock; one of the `indexam.c` INTERFACE ROUTINES. [verified-by-code] (`indexam.c:178` — via `knowledge/files/src/backend/access/index/indexam.c.md`).



### index_create
The catalog backend for `CREATE INDEX`: inserts the index's `pg_class` row, `pg_attribute` rows, and `pg_index` row (via `UpdateIndexRelation`), recording opclass/collation/options, and triggers the initial `index_build`. [verified-by-code] (`index.c:730` — via `knowledge/files/src/backend/catalog/index.c.md`).



### index_fetch_heap
The indexam wrapper that, given a TID returned by `index_getnext_tid`, fetches the heap tuple through the table AM and follows the HOT chain (`xs_heap_continue` tells it to keep walking the same chain). `index_getnext_slot` loops `index_getnext_tid` + `index_fetch_heap`. [verified-by-code] (via `knowledge/files/src/backend/access/index/indexam.c.md`).



### index_form_tuple
The convenience constructor that builds an `IndexTuple` from a `TupleDesc` plus values/nulls arrays, allocating the result in `CurrentMemoryContext` and handling null bitmap and TOAST-compression of index attributes. [verified-by-code] (`indextuple.c:44` — via `knowledge/files/src/backend/access/common/indextuple.c.md`).



### index_getnext_slot
The generic-index scan driver that returns the next matching heap tuple into a slot: it loops calling `index_getnext_tid` then `index_fetch_heap`, honoring `xs_heap_continue` to keep walking a single HOT chain before advancing the index. [verified-by-code] (`indexam.c:698` — via `knowledge/files/src/backend/access/index/indexam.c.md`).



### index_getnext_tid
The indexam per-tuple primitive (`indexam.c:599`) that asks the index AM for the next matching TID via its `amgettuple` callback, returning just the pointer; the caller then uses `index_fetch_heap` to materialize the heap row. [verified-by-code] (via `knowledge/files/src/backend/access/index/indexam.c.md`).



### index_insert
The genam wrapper that inserts one index entry for a heap tuple by dispatching to the AM's `aminsert`; called from `ExecInsertIndexTuples` and from catalog-index maintenance after a heap insert/update. [verified-by-code] (`indexam.c:214` — via `knowledge/files/src/backend/access/index/indexam.c.md`).



### INDEX_MAX_KEYS
A compile-time constant (default 32, set in `pg_config_manual.h`) capping the number of key columns an index may have; changing it requires a fresh initdb. It sits alongside the related `PARTITION_MAX_KEYS = 32` in the same tunables header. [verified-by-code] (`pg_config_manual.h` — via `knowledge/files/src/include/pg_config_manual.h.md`).



### index_open
Opens an index relation by OID, taking the requested lock and validating that the relation really is an index; the index-specific sibling of `relation_open`/`table_open`. [verified-by-code] (`indexam.c:134` — via `knowledge/files/src/backend/access/index/indexam.c.md`).



### IndexAmRoutine
The callback table an index access method returns from its `*handler`
function, advertising build/insert/scan/vacuum entry points
(`ambuild`, `aminsert`, `amgettuple`, `amgetbitmap`, `ambulkdelete`,
`amvacuumcleanup`, …) plus capability flags. Core code dispatches through this
struct rather than hard-coding any one AM. [from-comment] (`amapi.c:1` — via
`knowledge/files/src/backend/access/index/amapi.c.md`).



### IndexBulkDeleteResult
The accumulator an index AM's `ambulkdelete`/`amvacuumcleanup` returns to VACUUM,
reporting pages deleted/freed and tuples removed so VACUUM can update statistics
and free-space state. [verified-by-code] (via
`knowledge/idioms/gin-fastupdate-pending.md`).



### IndexFetchTableData
The table-AM scan state an index scan uses to fetch heap tuples by TID (heapam specializes it as `IndexFetchHeapData`); it is created by `index_fetch_begin` and released by `index_fetch_end`. [verified-by-code] (via `knowledge/files/src/include/access/relscan.md`).



### IndexGetRelation
The catalog/index.c reverse lookup mapping an index OID to its parent heap relation OID, with a `missing_ok` flag. It is used both during REINDEX/statistics resolution and as a race guard: amcheck and pg_prewarm call it once before locking and re-check after taking the parent lock to detect a drop-and-reuse of the index OID under them. [verified-by-code] (`index.c:3604` — via `knowledge/files/src/backend/catalog/index.c.md`).



### IndexInfo
The executor/catalog descriptor of an index — key columns, expressions, partial
predicate, opclass info — built from `pg_index` and used for index builds,
inserts, and predicate checks. [verified-by-code] (via
`knowledge/idioms/gin-tree-structure.md`).



### IndexOptInfo
A planner per-index scratch structure (declared in `pathnodes.h`) describing a usable index on a relation, used during access-path generation and index cost estimation. Like `RelOptInfo` and `Path`, it is per-planning-cycle scratch state and does NOT support `copyObject`. [from-comment] (`pathnodes.h.md` — via `knowledge/files/src/include/nodes/pathnodes.h.md`).



### IndexPath
The planner `Path` representing a scan via a specific index, carrying the chosen
index clauses, scan direction, and estimated costs that `add_path` compares
against other access paths. [verified-by-code] (via
`knowledge/subsystems/optimizer.md`).



### IndexScan
The plan/executor node that walks an index to find matching TIDs and fetches the corresponding heap tuples, applying any remaining qual; the ordered, selective alternative to a SeqScan. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### IndexScanDesc
The runtime descriptor for an in-progress index scan, created by
`index_beginscan` and handed to every index-AM scan callback
(`amgettuple`/`amgetbitmap`). It holds the scan keys, the current/marked
positions, the heap and index `Relation`s, and the AM's private `opaque` state;
e.g. nbtree's `_bt_readpage(IndexScanDesc scan, ScanDirection dir, …)` advances
it. [verified-by-code] (via
`knowledge/files/src/backend/access/nbtree/nbtreadpage.c.md`).



### IndexTuple
The on-disk index entry layout — a header (TID pointing at the heap tuple, info bits, size) followed by the indexed key values; index AMs build and interpret it via the index_form_tuple / index_getattr helpers. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/tuplesortvariants.c.md`).



### IndexTupleData
The on-disk index-tuple header (`itup.h:35`): an 8-byte struct of `t_tid` (a 6-byte ItemPointer to the heap row) plus `t_info`, a 16-bit bit-packed word holding a hasNulls bit, a hasVarwidths bit, an AM-reserved bit, and a 13-bit size. The attribute payload begins at `MAXALIGN(sizeof(IndexTupleData) + optional bitmap)`; nbtree reuses the layout for pivot tuples (e.g. overwriting a leaf high key with a dummy `IndexTupleData`), and spgist aliases it as `SpGistNodeTupleData`. [verified-by-code] (`itup.md` — via `knowledge/files/src/include/access/itup.md`).



### IndexTupleSize
The `itup.h` macro extracting an index tuple's byte length from the size bits of its `t_info` field. AM code uses it to advance tuple-by-tuple over a page (e.g. SpGist node walks, GIN/btree page scans) and amcheck cross-checks `IndexTupleSize(itup) == ItemIdGetLength(itemid)`; because the value comes from on-page bytes, a corrupted size of 0 can trip infinite scan loops, so page-level sanity checks and amcheck are the defenders. [verified-by-code] (`itup.h:71` — via `knowledge/files/src/include/access/itup.md`).



### indexuniquecheck
The `IndexUniqueCheck` flag passed to `index_insert` telling the AM whether (and how eagerly) to enforce a unique constraint — `NO`, `YES`, or `PARTIAL` for deferred checks. [verified-by-code] (via `knowledge/files/src/backend/access/index/indexam.c.md`).



### indisvalid
The `pg_index` flag marking whether an index may be used to answer queries; a failed CREATE INDEX CONCURRENTLY can leave a built-but-invalid index with this set false. [verified-by-code] (via `knowledge/files/src/backend/catalog` index docs).



### inherit_option
The per-membership boolean in `pg_auth_members` (default true) controlling whether the member passively holds the granted role's privileges — the INHERIT axis, evaluated by `has_privs_of_role`. [verified-by-code] (`pg_auth_members.h:50` — via `knowledge/docs-distilled/role-membership.md`).



### init_fn
The shared-memory initialization callback in a registered shmem-startup slot; the shmem bootstrap walks the list of `{size_fn, init_fn}` entries (e.g. `TwoPhaseShmemInit`) after allocating the segment so each subsystem can lay out its region. [verified-by-code] (`twophase.c:196-199` — via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### initBlockSize
The `AllocSet`/`GenerationContext` field giving the size of the first malloc'd block; subsequent blocks grow geometrically (`nextBlockSize`) toward `maxBlockSize`. [verified-by-code] (`aset.c:432-454` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### InitBufferTag
The macro that fills a `BufferTag` from a relation locator, fork, and block number, carefully zeroing the whole struct first because uninitialized pad bytes would corrupt its use as a hash key. [from-comment] (via `knowledge/subsystems/storage-buffer.md`).



### initial_cost_nestloop
The cheap first-phase nestloop cost estimate (`costsize.c`) computed before the inner path is fixed, giving `add_path` a lower bound to prune dominated joins; `final_cost_nestloop` then prices the chosen inner, using `has_indexed_join_quals` for inner-rescan cost. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### InitializeDSM
The parallel-executor node callback phase (`ExecXxxInitializeDSM`) in which a parallel-aware plan node places its shared coordination state into the query's dynamic-shared-memory segment during parallel setup. It follows the `Estimate` phase (which sizes the space) and is paired with `InitializeWorker` (worker-side attach) and `ReInitializeDSM` (rescan reset). [verified-by-code] (via `knowledge/files/src/backend/executor/nodeSort.c.md`).



### InitializeParallelDSM
The parallel-infrastructure step (after `CreateParallelContext`, before `LaunchParallelWorkers`) that sizes and creates the dynamic-shared-memory segment, lays out its table-of-contents, and serializes the leader's state (GUCs, snapshot, libraries) for workers to restore. [from-comment] (via `knowledge/files/src/include/access/parallel.h.md`).



### InitializeWorker
Shorthand for a plan node's `ExecXxxInitializeWorker` callback in the parallel-executor protocol: it attaches a parallel worker to the node's DSM state produced by `ExecXxxInitializeDSM`. Some nodes (e.g. Memoize) keep no shared per-worker state and use it only to wire up instrumentation. [from-comment] (via `knowledge/files/src/include/executor/nodeMemoize.md`).



### InitMaterializedSRF
Sets up a set-returning function in materialize mode: it builds the result `Tuplestore` and tuple descriptor and wires them into the `ReturnSetInfo`, so the function can emit all rows up front rather than value-per-call. [verified-by-code] (`verify_heapam.c:325` — via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### InitPlan
A sub-SELECT the planner can prove is uncorrelated, so it is executed exactly
once and its result stashed for reuse rather than re-run per outer row.
`SS_process_ctes` may also turn a CTE into an initplan; `root->cte_plan_ids`
records which (-1 = none). [from-comment] (`subselect.c:883` — via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).



### InitPlans
SubPlan nodes attached to a plan node's `initPlan` list that are evaluated once at the parent node's startup rather than per-row; their results are cached into PARAM_EXEC (`$N`) slots that later expression evaluations read. `SS_attach_initplans` puts them on the topmost node of a query level, the leader runs them (via `ExecSetParamPlan`) before launching parallel workers so workers see the cached value, and EXPLAIN shows them as separate `InitPlan N (returns $0)` boxes. [verified-by-code] (`createplan.c:162` — via `knowledge/idioms/subplan-and-initplan.md`).



### InitPostgres
The per-backend initialization routine run early in a new backend: it joins
shared memory, sets up the relcache/catcache, binds to the target database, and
performs authorization checks before the backend enters its command loop.
[verified-by-code] (`utils/init/postinit.c:716` — via
`knowledge/architecture/query-lifecycle.md`).



### InitPostgresCompat
A version-shim wrapper (used by preload-time background workers such as pg_wait_sampling's collector) around `InitPostgres` that lets a worker become a full backend participating in `ProcSignal` — so `procsignal_sigusr1_handler` fires — *without* connecting to any database (`InitPostgresCompat(NULL, InvalidOid, …)`), i.e. with `BGWORKER_SHMEM_ACCESS` only and no `BGWORKER_BACKEND_DATABASE_CONNECTION`. [verified-by-code] (via `knowledge/ideologies/pg_wait_sampling.md`).



### InitProcess
The startup routine that claims a PGPROC slot from the shared ProcArray for the current backend and initializes its latch, lock-wait, and semaphore state; it runs early in backend startup, before the process can take heavyweight locks. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### initStringInfo
Initialises a `StringInfo`, allocating a small starting buffer in the current memory context so subsequent `appendStringInfo*` calls can grow it; the start of every dynamic-string build. [verified-by-code] (via `knowledge/files/src/fe_utils/astreamer_zstd.c.md`).



### injection_point
A named hook compiled in only when `--enable-injection-points` is set, letting
tests attach a callback at a precise spot in backend C code to force a race,
error, or wait. The header defers `dlopen` until first hit; the build-time gate
is the sole defense against this being an arbitrary-code surface in production.
[verified-by-code] (via
`knowledge/files/src/include/utils/injection_point.h.md`).



### injection_points
PostgreSQL's test-only fault-injection framework (compiled in under `--enable-injection-points`): named points placed in backend code that a test can attach to in order to pause, error out, or run a callback at that spot. [verified-by-code] (via `knowledge/files/src/test/modules/injection_points` docs).



### InjectionPointAttach
The test-infrastructure call that registers a callback at a named injection point: `InjectionPointAttach(name, library, function, private_data, size)`; when a backend reaches the matching `INJECTION_POINT(name)` the callback fires, used to deterministically exercise race windows in TAP tests. [verified-by-code] (`injection_point.c:17` — via `knowledge/files/src/backend/utils/misc/injection_point.c.md`).



### inner_consistent
The SP-GiST opclass support function (`spgInnerConsistentIn` -> `spgInnerConsistentOut`) called at each inner tuple during a scan to decide which child nodes could contain matching leaves; for `allTheSame` inner tuples it must return an all-or-nothing answer or the scan errors. [verified-by-code] (via `knowledge/idioms/spgist-scan-and-consistent.md`).



### INNER_VAR
The special `varno` value meaning "a column of the inner input of this join/plan node" in an executor-level target list; it sits alongside `OUTER_VAR` and `INDEX_VAR`. [verified-by-code] (via `knowledge/files/src/include/nodes/primnodes.h.md`).



### input_buf
The `CopyFromStateData` buffer holding decoded/encoding-converted input between the raw read buffer (`raw_buf`) and per-line splitting (`line_buf`); one of COPY FROM's four staged parse buffers. [verified-by-code] (via `knowledge/files/src/include/commands/copyfrom_internal.h.md`).



### InputFunctionCall
The fmgr wrapper that invokes a type's text-input function (cstring → Datum), handling the three-argument convention (value, typioparam, typmod) and NULL semantics; the entry point for parsing literals and COPY-in fields. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### INSERT_IN_PROGRESS
One of the `HEAPTUPLE_*` results returned by the vacuum-oriented visibility routine `HeapTupleSatisfiesVacuumHorizon` (in `heapam_visibility.c`), indicating a tuple whose inserting transaction is still running and uncommitted. Vacuum/pruning uses it to decide a tuple is neither removable nor yet stably live. [verified-by-code] (`heapam_visibility.c` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### insertingAt
The per-`WALInsertLock` atomic recording the LSN up to which that lock's current holder has finished copying its record into the WAL buffers; `WaitXLogInsertionsToFinish` reads it (via `LWLockWaitForVar`) so a flusher can wait only for in-flight inserts below a target LSN. [verified-by-code] (via `knowledge/idioms/xloginsertlock-partitioning.md`).



### instr_time
PostgreSQL's portable high-precision interval-timing type and `INSTR_TIME_*` macro family, used for EXPLAIN ANALYZE timings, pg_stat_statements, and other instrumentation. The non-inline part sets a global ticks-per-nanosecond factor; the clock source is `clock_gettime(CLOCK_MONOTONIC)` (or a platform equivalent). [verified-by-code] (via `knowledge/files/src/common/instr_time.c.md`).



### InstrStartNode
Starts the per-node instrumentation timer wrapped around a plan node's `ExecProcNode` when `EXPLAIN ANALYZE` (or auto_explain) is active; the matching `InstrStopNode` accumulates rows and elapsed time. The wrapping is installed at `ExecProcNodeFirst` so the hot path stays untouched when instrumentation is off. [verified-by-code] (via `knowledge/files/src/backend/executor/execProcnode.c.md`).



### Int32GetDatum
Macro packing a 32-bit signed integer into a `Datum`; the `*GetDatum` counterpart of `DatumGetInt32`, used when handing an int to fmgr or a `PG_RETURN_INT32`. [verified-by-code] (via `knowledge/files/contrib/spi/moddatetime.c.md`).



### int4_ops
The default B-tree operator class for `int4`, bundling the comparison operators and support function an index uses for four-byte integers. An operator class is a per-(access-method, type) object; the default is chosen automatically from the column's type unless a non-default opclass is named at `CREATE INDEX`. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### interleaved_parts
A `PartitionBoundInfo` bitmapset (set only for a baserel, `partbounds.h:75-77`) marking list partitions whose bound values interleave, which disables certain pruning fast-paths. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### IntervalStyle
A global GUC controlling interval output formatting, defaulting to `INTSTYLE_POSTGRES` (set in `globals.c`) and selected from the `INTSTYLE_*` values. It is one of the I/O-affecting GUCs that `dblink`'s `applyRemoteGucs` propagates (alongside `DateStyle`) by opening a GUC nestlevel and `SET LOCAL`-ing it; ECPG's pgtypeslib lacks the real global and hardcodes it locally in `DecodeInterval`. [verified-by-code] (`globals.c` — via `knowledge/files/src/backend/utils/init/globals.c.md`).



### INV_READ
The large-object open-mode flag (`0x00040000`, defined in `libpq/libpq-fs.h`) requesting that an LO be opened for reading; it pairs with `INV_WRITE` and the two can be ORed (`lo_creat(INV_READ | INV_WRITE)` is the canonical create-and-open pattern). `inv_open`/`lo_open` translate `INV_READ`/`INV_WRITE` to internal `IFS_RDLOCK`/`IFS_WRLOCK`, and the flags are part of the LO ABI. [verified-by-code] (`libpq-fs.h` — via `knowledge/files/src/include/libpq/libpq-fs.h.md`).



### INV_WRITE
The large-object open-mode flag (paired with `INV_READ`) passed to `lo_open`/`inv_open` to request a writable LO descriptor. Writing requires the snapshot semantics that make the LO visible for update within the transaction. [inferred] (`be-fsstubs.c:98` — via `knowledge/files/src/backend/libpq/be-fsstubs.c.md`).



### INVALID_PROC_NUMBER
The sentinel `ProcNumber` (-1) meaning "no backend", used wherever a PGPROC
slot index may be absent — e.g. a relation with no associated temp-table
backend. [from-comment] (via `knowledge/data-structures/relfilelocator.md`).



### InvalidateCatalogSnapshot
Discards the backend's cached catalog snapshot so the next catalog read takes
a fresh one — invoked when invalidation messages indicate catalog state changed.
It is part of the `LocalExecuteInvalidationMessage` machinery that keeps relcache
and catcache coherent with committed DDL. [verified-by-code] (via
`knowledge/files/src/backend/utils/cache/inval.c.md`).



### InvalidateCompositeTypeCacheEntry
The type-cache callback that fires on relcache invalidation of a composite
type's defining relation, marking the cached `TypeCacheEntry`'s tuple
descriptor stale so the next lookup rebuilds it. [verified-by-code] (via
`knowledge/idioms/typcache-entry-and-lookup.md`).



### InvalidateSystemCaches
Flushes every entry in this backend's catcache and relcache, used after events
(like a large sinval overflow / reset) where targeted invalidation isn't
possible and the safe response is to rebuild caches lazily. [verified-by-code]
(via `knowledge/idioms/syscache-invalidation-flow.md`).



### InvalidBlockNumber
The all-ones `BlockNumber` (0xFFFFFFFF) sentinel meaning "no such block",
returned for an empty relation or an uninitialized scan position.
[verified-by-code] (via `knowledge/subsystems/storage-lmgr.md`).



### InvalidBuffer
The sentinel buffer identifier (value 0) returned when no valid shared or local buffer is held; callers test against it before releasing a pin or reading buffer contents. [verified-by-code] (`buf.h` — via `knowledge/files/src/include/storage/buf.h.md`).



### InvalidOffsetNumber
The sentinel `OffsetNumber` value 0, meaning "no line pointer"; valid item
offsets on a page start at `FirstOffsetNumber` (1). [verified-by-code] (via
`knowledge/docs-distilled/tablesample-method.md`).



### InvalidOid
The sentinel OID value 0, meaning "no object" — never a valid catalog row OID.
It is used pervasively as a null/absent marker in fixed `Oid` columns and
keys, e.g. PL/Tcl uses `InvalidOid` as the hash key for the untrusted shared
interpreter. [from-comment] (`pltcl.c:112` — via
`knowledge/files/src/pl/tcl/pltcl.c.md`).



### InvalidTransactionId
The reserved `TransactionId` 0, meaning "no transaction"; real XIDs begin at
`FirstNormalTransactionId` (3) after the three special low values. [verified-by-code]
(via `knowledge/docs-distilled/transactions.md`).



### InvalidXLogRecPtr
The sentinel `XLogRecPtr` value 0, meaning "no valid WAL position". Because a
real record never starts at LSN 0, code uses it as a not-set marker — e.g. a
buffer's "WAL position that must be flushed before write-out" may be
`InvalidXLogRecPtr` when the page has no pending WAL dependency.
[verified-by-code] (`xlog.c:273-278` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### invalItems
The list of catalog cache-invalidation items a cached plan accumulates so it can be invalidated when a non-relation dependency (function, operator, etc.) changes; `RevalidateCachedQuery` refreshes both `relationOids` and `invalItems` on replan. [from-comment] (`plancache.c:22-28` — via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### io_method
The GUC selecting how the AIO subsystem issues disk I/O — `sync` (no async),
`worker` (dedicated I/O worker processes), or `io_uring` (Linux kernel
submission rings). It is the user-facing switch over the pluggable
`IoMethodOps` callback tables. [verified-by-code] (via
`knowledge/files/src/backend/storage/aio/aio.c.md`).



### io_uring
A Linux kernel asynchronous-I/O interface that PostgreSQL's AIO subsystem can use as an I/O method (alongside worker-based and synchronous methods) to submit and reap disk reads without blocking the backend. The io_uring method keeps the ring FD open across operations, which constrains FD-close ordering. [verified-by-code] (via `knowledge/files/src/backend/storage/aio/aio.c.md`).



### io_wref
The `BufferDesc` field of type `PgAioWaitRef` that references an in-flight asynchronous I/O for that buffer; it is valid only while an AIO on the buffer is in progress, letting waiters find and await the read/write. [verified-by-code] (via `knowledge/files/src/include/storage/buf_internals.h.md`).



### IoMethodOps
The AIO method-abstraction vtable (`aio_internal.h`): each I/O method (`worker`, `io_uring`, `sync`) supplies an `IoMethodOps` instance, letting the AIO subsystem submit and reap I/Os without knowing the backend implementation. [verified-by-code] (via `knowledge/files/src/include/storage/aio_internal.h.md`).



### IOOP_EXTEND
The pgstat I/O-operation enum value for relation extension; it is the first bytes-tracked `IOOp` entry (the enum splits into not-bytes-tracked and bytes-tracked ranges, and code relies on `IOOP_EXTEND` marking that boundary). [verified-by-code] (via `knowledge/files/src/include/pgstat.h.md`).



### IPC
Inter-Process Communication — the shared-memory-plus-signals mechanisms tying together PostgreSQL's per-connection backend processes: the shared-memory segment, latches, signals, and the `on_shmem_exit`/`before_shmem_exit` cleanup callback stacks that run at backend exit. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/ipc.c.md`).



### is_member_of_role
The `acl.c` predicate answering "may this role SET ROLE to that role?" — the SET-identity axis, distinct from `has_privs_of_role`'s passive-privilege (INHERIT) axis. [verified-by-code] (`acl.c:5048` — via `knowledge/docs-distilled/role-membership.md`).



### IsA
The node-tag test macro that checks a `Node *` carries a given `NodeTag`; it
is the standard idiom for runtime dispatch over PostgreSQL's tagged node
hierarchy. [verified-by-code] (via `knowledge/subsystems/foreign.md`).



### IsAJsonbScalar
The macro distinguishing a scalar `JsonbValue` (type tag < 0x10) from a composite one — the branch point for ops that behave differently per category. [verified-by-code] (`jsonb.h:299-301` — via `knowledge/data-structures/jsonbvalue.md`).



### IsBinaryUpgrade
A process-identity global flag indicating the backend is running in binary-upgrade mode (pg_upgrade), listed among miscadmin.h process-identity globals like `IsPostmasterEnvironment`, `IsUnderPostmaster`, and `ExitOnAnyError`. [verified-by-code] (`miscadmin.h` — via `knowledge/files/src/include/miscadmin.h.md`).



### IsBootstrapProcessingMode
Tests whether the backend is in bootstrap mode (initdb building the initial
catalogs), a state in which many cache/lookup paths are bypassed or specialized.
[verified-by-code] (via `knowledge/idioms/syscache-invalidation-flow.md`).



### isCommit
The boolean parameter threaded through transaction-cleanup routines (`smgrDoPendingDeletes`, `smgrDoPendingSyncs`, xact callbacks) telling them whether the current (sub)transaction is committing or aborting, so one routine can drive both the commit and abort code paths over the same pending list. [verified-by-code] (`storage.c:673` — via `knowledge/files/src/backend/catalog/storage.c.md`).



### isforeignpathasynccapable
The FDW callback declaring that a foreign scan path can run asynchronously under Append, enabling concurrent remote scans (`ForeignAsyncRequest` / `ForeignAsyncConfigureWait` / `ForeignAsyncNotify`). [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### IsInParallelMode
Returns whether the backend is currently inside a parallel region, where
certain operations (assigning XIDs, writing data, taking new snapshots) are
restricted to preserve worker/leader consistency. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### IsParallelWorker
Tests whether the current process is a parallel worker (as opposed to the
leader), gating worker-only setup such as joining the leader's lock group and
importing transaction state. [verified-by-code] (via
`knowledge/idioms/subtransaction-stack.md`).



### IsQueryIdEnabled
The canonical predicate gating query-jumble computation: end-of-parse-analysis calls `JumbleQuery` only when `IsQueryIdEnabled()` is true, combining the `compute_query_id` GUC setting with whether a consumer such as `pg_stat_statements` registered interest. [verified-by-code] (`queryjumblefuncs.c` — via `knowledge/files/src/backend/nodes/queryjumblefuncs.c.md`).



### IsRelationExtensionLockHeld
Reports whether the current backend holds a relation-extension lock; it is asserted at points that must not acquire another heavyweight lock while extending, since that could deadlock. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### issue_xlog_fsync
The low-level `xlog.c` routine that fsyncs a WAL segment file according to the configured `wal_sync_method` (fdatasync, fsync, open_datasync, etc.); `XLogWrite` calls it and its timing is fed into `pg_stat_io`. [verified-by-code] (via `knowledge/docs-distilled/wal.md`).



### IsUnderPostmaster
The global boolean (initialized false in `globals.c`) set true by `InitPostmasterChild` in every postmaster-forked child, distinguishing a normal backend from standalone single-user / bootstrap mode. Startup code branches on it — e.g. `!IsUnderPostmaster` triggers `StartupXLOG` and the single-user superuser/standalone authentication path — and it must be set early or error handling goes wrong. [verified-by-code] (`miscinit.c:96`, `globals.c:24` — via `knowledge/files/src/backend/utils/init/miscinit.c.md`).



### ItemIdData
The 4-byte line pointer (`ItemId`) in a page's line-pointer array; its
`lp_off`/`lp_len`/`lp_flags` bitfields locate a tuple and encode whether the
slot is `LP_NORMAL`, `LP_REDIRECT`, `LP_DEAD`, or `LP_UNUSED`. [verified-by-code]
(via `knowledge/idioms/gin-fastupdate-pending.md`).



### ItemIdIsValid
The line-pointer validity macro: given an `ItemId` from `PageGetItemId`, it
checks the entry isn't out of range before the bytes are dereferenced. Page
inspectors reading possibly-corrupt pages must call it (and `ItemIdIsNormal`)
before `PageGetItem` to avoid reading off the page. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### ItemPointer
A `(BlockNumber, OffsetNumber)` pair — the TID — locating a line-pointer slot on
a page. A tuple's `t_self` is its own TID; `t_ctid` points to its successor
version (or to itself when there is none). [verified-by-code]
(`htup_details.h:86` — via `knowledge/subsystems/access-heap.md`).



### ItemPointerData
The 6-byte on-disk tuple identifier (TID): a BlockIdData (block number) plus an OffsetNumber (1-based line-pointer slot). ItemPointer is a pointer to it, and the system CTID column exposes it at SQL level. [verified-by-code] (via `knowledge/files/src/include/storage/itemptr.h.md`).



### ItemPointerGetBlockNumber
Inline accessor extracting the `BlockNumber` from a TID's split `BlockIdData`; paired with `ItemPointerGetOffsetNumber` to decode a tuple pointer into (block, offset). A `NoCheck` variant skips the validity assert. [verified-by-code] (via `knowledge/files/src/include/storage/itemptr.h.md`).



### ItemPointerGetOffsetNumber
Inline accessor returning the line-pointer offset within a page from a TID; the second half of decoding an `ItemPointer`, complementing `ItemPointerGetBlockNumber`. [verified-by-code] (via `knowledge/files/src/backend/storage/page/itemptr.c.md`).



### ItemPointerSet
Inline macro that sets an `ItemPointerData` (TID) from a block number and item offset; the canonical way to construct a tuple pointer, paired with `ItemPointerSetInvalid` for the empty case. [verified-by-code] (via `knowledge/files/src/include/storage/itemptr.h.md`).



### iteratedirectmodify
The FDW callback that drives a direct-modify (remote-executed `UPDATE` / `DELETE`), returning result rows when `RETURNING` is present. [from-docs] (via `knowledge/docs-distilled/fdwhandler.md`).



### IterateForeignScan
The `FdwRoutine` callback that returns the next tuple of a foreign scan into
the supplied slot, or an empty slot at end-of-scan; called once per row by
the executor. [verified-by-code] (via
`knowledge/subsystems/contrib-file_fdw.md`).



### jbvArray
The `JsonbValue` composite type tag (0x10) for a fully-deserialized JSON array, whose `val.array.elems[]` holds child `JsonbValue`s; the `rawScalar` flag marks a top-level bare scalar wrapped as a one-element array. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvBinary
The `JsonbValue` type tag for a composite still in its on-disk packed `JsonbContainer` form — the lazy-deserialization handle that lets operators walk on-disk JSONB without fully expanding it. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvBool
The `JsonbValue` scalar type tag for a JSON boolean. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvDatetime
The virtual `JsonbValue` type tag (0x20) used by `jsonpath`/SQL-JSON date-time operations; it has no on-disk JSONB representation and is serialized to a string on output. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvNull
The `JsonbValue` scalar type tag (value 0x0) for a JSON null. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvNumeric
The `JsonbValue` scalar type tag for a JSON number, carrying a PG `Numeric` in `val.numeric`. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvObject
The `JsonbValue` composite type tag for a fully-deserialized JSON object, whose `val.object.pairs[]` holds `JsonbPair` key/value entries. [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvString
The `JsonbValue` scalar type tag for a JSON string; its `val.string` is a `{ int len; char *val; }` (length-counted, not NUL-terminated). [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jbvType
The `jbvType` enum tag classifying a `JsonbValue` into scalar (0x0–0xF: `jbvNull`/`jbvString`/`jbvNumeric`/`jbvBool`), composite (0x10+: `jbvArray`/`jbvObject`/`jbvBinary`), or virtual (0x20+: `jbvDatetime`). [verified-by-code] (`jsonb.h:227-247` — via `knowledge/data-structures/jsonbvalue.md`).



### jit_above_cost
The estimated plan-cost threshold above which JIT compilation of a query's expressions is triggered; one of the `jit_*` GUCs in `jit.h`, checked at node init (e.g. hot VALUES scans) alongside `jit_inline_above_cost` / `jit_optimize_above_cost`. [verified-by-code] (via `knowledge/files/src/include/jit/jit.h.md`).



### jit_compile_expr
The provider-agnostic entry in `jit.c` that requests JIT compilation of an expression: it consults only `PGJIT_PERFORM | PGJIT_EXPR` (the optimization/inline flags matter only to the provider) before dispatching to the loaded JIT provider. [verified-by-code] (via `knowledge/files/src/backend/jit/jit.c.md`).



### jit_debugging_support
A developer JIT GUC (§20.17) that registers JIT-generated functions with a debugger (gdb/lldb) so they appear in backtraces; one of the debug-only knobs §32.3 defers to runtime-config-developer. [from-docs] (via `knowledge/docs-distilled/jit-configuration.md`).



### jit_dump_bitcode
A developer JIT GUC (§20.17) that writes the LLVM bitcode (`.bc`) of generated functions into the data directory for inspection. [from-docs] (via `knowledge/docs-distilled/jit-configuration.md`).



### jit_enabled
The C variable (`jit.c:33`, default `false`) that gates whether the JIT provider library is loaded at all; `provider_init()` early-outs when it is false, so a `--with-llvm` build running with `jit=off` never pays the LLVM `dlopen` cost. Distinct from the shipped `jit` GUC boot value (`on`), which is what actually lets a plan clearing `jit_above_cost` be JIT-compiled. [verified-by-code] (via `knowledge/docs-distilled/jit-decision.md`).



### jit_expressions
The developer GUC (§20.17) that independently toggles JIT expression compilation by clearing/setting the `PGJIT_EXPR` bit; the expression counterpart of `jit_tuple_deforming`. [verified-by-code] (`jit.h:23-24` — via `knowledge/docs-distilled/jit-configuration.md`).



### jit_inline_above_cost
The plan-cost threshold above which the JIT provider inlines small functions into the generated code; one of the `jit_*` cost gates (`jit_above_cost`, `jit_inline_above_cost`, `jit_optimize_above_cost`) the executor compares against per query. [verified-by-code] (via `knowledge/files/src/include/jit/jit.h.md`).



### jit_optimize_above_cost
The plan-cost threshold above which the JIT provider runs the optimizer over generated code; passed as part of the OR-bitmask of JIT flags the provider receives, alongside `jit_above_cost` and `jit_inline_above_cost`. [verified-by-code] (via `knowledge/files/src/include/jit/jit.h.md`).



### jit_profiling_support
A developer JIT GUC (§20.17) that emits profiling data (e.g. for `perf`) for JIT-generated functions. [from-docs] (via `knowledge/docs-distilled/jit-configuration.md`).



### jit_provider
The `PGC_POSTMASTER` GUC (default `"llvmjit"`) naming the shared library the server `dlopen`s as its JIT backend; because the choice is fixed at server start, swapping providers "without recompiling" still needs a restart. `jit.c` builds the path `<pkglibdir>/<jit_provider><DLSUFFIX>` and loads it lazily on the first query that needs JIT. [verified-by-code] (`jit.c:91` — via `knowledge/docs-distilled/jit-extensibility.md`).



### jit_release_context
The generic JIT teardown entry (`jit_release_context` → provider `llvm_release_context` → `ResourceOwnerForgetJIT`); the resource-owner callback nulls the owner first so it isn't removed from an owner already dropping the context. [verified-by-code] (via `knowledge/files/src/backend/jit/llvm/llvmjit.c.md`).



### jit_tuple_deforming
The developer GUC (runtime-config-developer §20.17) that independently toggles JIT tuple deforming by clearing/setting the `PGJIT_DEFORM` bit; paired with `jit_expressions` so each half of JIT's contribution can be A/B-measured. [verified-by-code] (`jit.h:23-24` — via `knowledge/docs-distilled/jit-configuration.md`).



### JitContext
The per-query JIT state object that accumulates generated modules and
instrumentation counters; it is created lazily when a query's estimated cost
crosses `jit_above_cost` and freed at executor shutdown. [verified-by-code] (via
`knowledge/idioms/jit-expression-codegen.md`).



### JitInstrumentation
The counters (generation, inlining, optimization, emission times and module
counts) accumulated on a `JitContext` and surfaced by `EXPLAIN (ANALYZE)` to
attribute time spent in the JIT pipeline. [verified-by-code] (via
`knowledge/idioms/jit-provider-and-context.md`).



### JitProviderCallbacks
The function table a JIT provider library fills in (reset-after-error / compile-expr
/ release-context) and returns from `_PG_jit_provider_init`, decoupling the core
from the LLVM implementation. [verified-by-code] (via
`knowledge/idioms/jit-provider-and-context.md`).



### JitProviderCompileExprCB
The typedef for the JIT provider's `compile_expr` callback: takes an `ExprState *` and returns `bool`; the core operation of the provider vtable, dispatched from `jit_compile_expr` → `provider.compile_expr(state)`. [verified-by-code] (`jit.h:72`, `jit.c:152` — via `knowledge/docs-distilled/jit-extensibility.md`).



### JitProviderReleaseContextCB
The typedef for the JIT provider's `release_context` callback, which frees a `JitContext`; one of the three function pointers in `JitProviderCallbacks` (with `reset_after_error` and `compile_expr`). [verified-by-code] (`jit.h:70` — via `knowledge/docs-distilled/jit-extensibility.md`).



### JitProviderResetAfterErrorCB
The typedef for the JIT provider's `reset_after_error` callback, which recovers provider state after a `longjmp`; the first of the three `JitProviderCallbacks` pointers. [verified-by-code] (`jit.h:69` — via `knowledge/docs-distilled/jit-extensibility.md`).



### Join Filter
The `EXPLAIN` line for a join condition (from an outer join's `ON`) evaluated at a join node. Unlike a plain `Filter`, a row that fails a `Join Filter` under an outer join can still be emitted null-extended, rather than being removed unconditionally. [from-docs §14.1.2] (via `knowledge/docs-distilled/using-explain.md`).



### join_search_one_level
The inner driver of the standard dynamic-programming join search: given all best paths for relation sets of size k, it builds and costs the joins that produce size-(k+1) sets, calling `make_join_rel` / `add_path` for each legal pair. [inferred] (via `knowledge/ideologies/pg_hint_plan.md`).



### JoinCostWorkspace
A scratch struct the planner fills with a cheap initial cost estimate for a candidate join path (the initial_cost_* pass), used as an early-cut threshold before the expensive final_cost_* pass runs. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### joininfo
The list of `RestrictInfo` clauses on a base `RelOptInfo` that mention this relation and at least one other — the join-qual bookkeeping maintained in `optimizer/util/joininfo.c` and consulted when enumerating join paths. [verified-by-code] (via `knowledge/data-structures/reloptinfo.md`).



### JoinWaitQueue
The proc.c primitive (`proc.c:1179`) that inserts the current backend into a heavyweight lock's wait queue before it sleeps in `ProcSleep`; part of the lock-wait protocol invoked from lock.c. [verified-by-code] (`proc.c:1179` — via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### JSON_TABLE
The SQL/JSON construct `JSON_TABLE(context_item, path COLUMNS (...))` that
turns a JSON document into a relational rowset. Parse analysis in
`parse_jsontable.c` expands the COLUMNS clause into a `TableFunc` node of type
`JSTYPE_JSON_TABLE`. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_jsontable.c.md`).



### JsonbContainer
The on-disk packed representation of a composite JSONB array/object; a `jbvBinary` `JsonbValue` points at one via `val.binary.data` for lazy traversal. [verified-by-code] (`jsonb.h:255-297` — via `knowledge/data-structures/jsonbvalue.md`).



### JsonbIterator
The stateful cursor used to walk a binary jsonb value one token at a time (object keys, array elements, scalars) without fully expanding it, driving comparison, containment, and text output. [verified-by-code] (`jsonb_util.c` — via `knowledge/files/src/backend/utils/adt/jsonb_util.c.md`).



### JsonbIteratorNext
Advances a `JsonbIterator` to the next token, returning a `JsonbIteratorToken` (BEGIN/END of object or array, a key, or a value) and populating the caller's `JsonbValue`; recursion into nested containers is requested via its skipNested flag. [verified-by-code] (`jsonb_util.c` — via `knowledge/files/src/backend/utils/adt/jsonb_util.c.md`).



### JsonbPair
One key/value entry inside a deserialized `jbvObject` `JsonbValue` (`{ int nPairs; JsonbPair *pairs; }`), where both key and value are themselves `JsonbValue`s. [verified-by-code] (`jsonb.h:255-297` — via `knowledge/data-structures/jsonbvalue.md`).



### JsonbValue
The in-memory, expanded representation of a jsonb value — a tagged union
over scalars, arrays, and objects — used while building or iterating jsonb
before it is serialized to the compact on-disk `JEntry` form. [from-comment]
(via `knowledge/subsystems/contrib-jsonb_plperl.md`).



### JsonbValueToJsonb
The top-level flattener that walks an in-memory `JsonbValue` tree and constructs the packed on-disk `Jsonb` varlena (sorted keys, canonical storage form). A raw scalar input is wrapped in the `JB_FSCALAR | JB_FARRAY` pseudo-array; otherwise it dispatches to `convertToJsonb`. It copies key/value bytes during conversion (so temporary source buffers can be freed) and collapses duplicate object keys last-wins. [verified-by-code] (`jsonb_util.c:96` — via `knowledge/files/src/backend/utils/adt/jsonb_util.c.md`).



### JsonLexContext
The jsonapi.c lexer state (input pointer, current token, optional incremental-parse buffer) threaded through the SAX-style JSON parser shared by backend and frontend; a static `failed_oom` instance handles allocation failure in the frontend. [verified-by-code] (via `knowledge/files/src/common/jsonapi.c.md`).



### JumbleQuery
The routine that walks a parsed Query and computes its jumble — a normalized fingerprint that collapses constant values — so pg_stat_statements can group executions of the same statement shape under one queryid. [verified-by-code] (via `knowledge/files/src/backend/parser/analyze.c.md`).



### JunkFilter
The executor helper (`execJunk.c`) that strips junk attributes (ctid, tableoid, resjunk sort/group columns) from a tuple before it is returned to the client, and extracts the system columns row-modifying nodes need. [verified-by-code] (via `knowledge/files/src/backend/executor/execJunk.c.md`).



### keyGetItem
The GIN scan routine (`ginget.c`) that advances a single scan key's entry streams to the next candidate heap TID and calls the opclass `consistent` function to decide whether that key is satisfied there. [verified-by-code] (via `knowledge/idioms/gin-scan-and-consistent.md`).



### KNN
K-Nearest-Neighbor search — the ordered, distance-ranked index scan supported by GiST (and SP-GiST) opclasses that implement the `ORDER BY column <-> constant` distance operator. The index returns tuples in increasing distance order without a separate sort, used by `btree_gist` and the geometric/`cube` opclasses. [verified-by-code] (via `knowledge/files/contrib/btree_gist/btree_gist.c.md`).



### KnownAssignedXids
The standby-side array that tracks transactions seen as in-progress in the WAL
stream during hot-standby recovery, so a standby can build MVCC snapshots
without the primary's live PGPROC array. Recovery records and prunes entries as
it replays commit/abort and running-xacts records. [verified-by-code]
(`xlogrecovery.c:161` — via
`knowledge/files/src/backend/access/transam/xlogrecovery.c.md`).



### last_found_count
Part of the partition-pruning "last found" cache (`last_found_*_index` / `last_found_count`) that skips the bsearch when successive tuples route to the same partition. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### lastOverflowedXid
The ProcArray field recording the highest xid that was live when some backend's subxid cache overflowed; any xid at or below it during that window is treated as potentially having invisible subxacts, so snapshots mark `suboverflowed` for the affected range. [verified-by-code] (via `knowledge/idioms/subxact-visibility-and-overflow.md`).



### lastRevmapPage
The BRIN metapage field recording the highest block currently used by the reverse map; blocks up to it are revmap pages and any regular tuples landing there must be evacuated before the revmap can extend. [verified-by-code] (via `knowledge/idioms/brin-revmap.md`).



### latch
The inter-process wait/wake primitive: a backend `WaitLatch`es on its own
`Latch` (often together with socket readiness and a timeout) and another process
calls `SetLatch` to wake it, replacing busy-polling for event-driven sleeps.
Latches are signal- and crash-safe and underlie almost every auxiliary process's
main loop. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/latch.c.md`).



### latest_page_number
In an SLRU's shared control, `latest_page_number` is read / written atomically rather than under the control lock, because its only writer is the single process extending the log. [verified-by-code] (via `knowledge/idioms/slru-page-replacement.md`).



### latestCompletedXid
The shared `ProcArray` field naming the highest XID known to have completed; snapshot building uses it to compute `xmax` and it is logged in `xl_running_xacts` for hot-standby snapshot bootstrap. [verified-by-code] (`procarray.c:1465-1475` — via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).



### launch_backend
The postmaster path (`postmaster_child_launch`) that forks/execs every child process — backends, autovacuum workers, background workers — passing the inherited state each needs to re-attach to shared memory. [from-comment] (via `knowledge/files/src/backend/postmaster/postmaster.c.md`).



### LaunchParallelWorkers
The step that asks the postmaster to start the background workers registered in
a `ParallelContext`; fewer than requested may start, and the plan must cope with
zero workers. [verified-by-code] (via
`knowledge/idioms/bgworker-and-parallel.md`).



### lazy_scan_heap
The phase-I driver of heap vacuum (`vacuumlazy.c`, line 1279) — scans every block, prunes HOT chains, records dead-item TIDs into the dead-items TID store, and updates the visibility map, deferring index cleanup to later phases. Driven by `heap_vacuum_rel`, which sets up the `LVRelState` and cutoffs first. [verified-by-code] (via `knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).



### lazy_scan_noprune
The VACUUM fallback (`vacuumlazy.c`) taken when a cleanup lock on a heap page cannot be acquired: it processes the page under a share lock only — recording dead-tuple and freeze information without pruning or defragmenting. [verified-by-code] (via `knowledge/idioms/vacuum-two-pass-heap.md`).



### lazy_scan_prune
VACUUM's per-page workhorse: under a cleanup lock it builds `PruneFreezeParams` and calls `heap_page_prune_and_freeze` for one heap page, then folds the returned prune/freeze result and LP_DEAD offsets into the vacuum's running counters. [verified-by-code] (`vacuumlazy.c:2021` — via `knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).



### lazy_vacuum_heap_page
VACUUM's second-pass routine that converts `LP_DEAD` line pointers to `LP_UNUSED` for the offsets recorded in the dead-items TID store; no data moves, so an exclusive (not super-exclusive) lock suffices. [from-comment] (via `knowledge/subsystems/access-heap.md`).



### lcons
Prepends an element to the head of a `List` (the counterpart of `lappend`); used where newest-first ordering matters, such as inserting at the head of a cache bucket. [verified-by-code] (via `knowledge/files/contrib/sepgsql/uavc.c.md`).



### leaf_consistent
The SP-GiST opclass support function (`spgLeafConsistentIn` -> `spgLeafConsistentOut`) that applies the scan qual to an individual leaf datum, returning match/no-match and, for ordered (KNN) scans, filling the `distances[]` array. [verified-by-code] (via `knowledge/docs-distilled/spgist.md`).



### LH_BUCKET_BEING_POPULATED
A hash-index page flag set on the target (new) bucket page of an in-progress bucket split, marking it as still being populated from the source bucket; it is cleared when the split finishes. [verified-by-code] (via `knowledge/idioms/hash-page-layout.md`).



### LH_BUCKET_BEING_SPLIT
A hash-index page flag set on a primary bucket page to mark it as the source bucket of an in-progress bucket split; it is cleared once the split completes. [verified-by-code] (via `knowledge/idioms/hash-page-layout.md`).



### line_buf
The `CopyFromStateData` buffer holding one full logical input row (after newline handling and any embedded-newline quoting) before it is split into per-column `attribute_buf` fields. [verified-by-code] (via `knowledge/files/src/include/commands/copyfrom_internal.h.md`).



### List
PostgreSQL's ubiquitous list type — an array-backed `List` of pointers
(`T_List`), integers, or OIDs — manipulated with `lappend`, `lfirst`,
`foreach`, and friends. Almost every multi-element structure in the parser,
planner, and executor is a `List`. [from-comment] (via
`knowledge/idioms/node-types-and-lists.md`).



### list_length
The O(1) length accessor for PostgreSQL's `List` (`nodes/pg_list.h`), returning the element count of a `List *` (or 0 for `NIL`). Because the modern List is a flat array, callers use it freely in hot paths and assertions — e.g. `list_length(explicit_subtransactions)` to snapshot subtransaction nesting depth. [verified-by-code] (via `knowledge/files/src/include/nodes/pg_list.h.md`).



### list_make1
Macro family (`list_make1` … `list_make5`) that builds a fixed-size `List` literal from its arguments in one call; the idiomatic way to construct short lists inline. [verified-by-code] (via `knowledge/files/src/include/nodes/pg_list.h.md`).



### ListCell
One element of PostgreSQL's List. Since the v13 rewrite a List is a flat array of ListCells, so foreach() indexes the array; a cell holds a pointer, int, or oid payload depending on the list's NodeTag. [verified-by-code] (via `knowledge/files/src/include/nodes/pg_list.h.md`).



### llvm_compile_expr
The `compile_expr` slot of the JIT provider: it JIT-compiles a fully-built `ExprState` step program into native code, emitting one LLVM IR function per expression by walking `state->steps[]` opcode-by-opcode. It returns true if a function was generated; otherwise execution falls back to the interpreter. [verified-by-code] (`llvmjit_expr.c:79-2977` — via `knowledge/files/src/backend/jit/llvm/llvmjit_expr.c.md`).



### llvm_create_context
The LLVM JIT routine that returns a usable LLVM context, calling `llvm_recreate_llvm_context` on every entry; the actual recreation only fires once the reuse counter reaches `LLVMJIT_LLVM_CONTEXT_REUSE_MAX=100` and no contexts are in use, so it is rare in a busy backend but frequent under low-concurrency JIT churn. [verified-by-code] (via `knowledge/files/src/backend/jit/llvm/llvmjit.c.md`).



### llvm_get_function
The JIT late-binding trampoline: on an expression's first call (not first emit) it triggers LLVM emission and overwrites `state->evalfunc` with the native function pointer, so subsequent calls run native code directly. Its `emission_counter` is what EXPLAIN attributes to the "JIT > Emission" line. [verified-by-code] (`llvmjit_expr.c:2987-3005` — via `knowledge/files/src/backend/jit/llvm/llvmjit_expr.c.md`).



### llvm_mutable_module
An LLVM-JIT helper returning the module a function is being emitted into; like `llvm_create_context` / `llvm_get_function` it asserts it runs inside a `fatal_on_oom` section so an LLVM OOM cannot longjmp out. [verified-by-code] (`llvmjit.c:228,319,367` — via `knowledge/files/src/backend/jit/llvm/llvmjit.c.md`).



### llvm_pg_func
The LLVM JIT type-module mechanism (`llvmjit_types.c`) that makes PG C helper functions callable from generated IR; the *set* of pointers in `referenced_functions[]` is contractual, so adding a new ExecEval helper to `execExpr.c` without registering it here is a common JIT contributor mistake. [from-comment] (via `knowledge/files/src/backend/jit/llvm/llvmjit_types.c.md`).



### llvm_recreate_llvm_context
The LLVM JIT routine that disposes and rebuilds the shared `LLVMContext` to reclaim type memory that the inliner "leaks"; it fires every `LLVMJIT_LLVM_CONTEXT_REUSE_MAX = 100` contexts, but only when `llvm_jit_context_in_use_count == 0`. [verified-by-code] (via `knowledge/files/src/backend/jit/llvm/llvmjit.c.md`).



### llvmjit_expr
`src/backend/jit/llvm/llvmjit_expr.c` — the LLVM JIT expression compiler. `llvm_compile_expr` walks an already-built `ExprState` step program and emits one LLVM IR function, handling 121 cases of `ExprEvalOp`; the result becomes the `ExprState`'s native `evalfunc`, replacing the `execExprInterp.c` dispatch loop for hot expressions. [verified-by-code] (`llvmjit_expr.c:1009-2949` — via `knowledge/files/src/backend/jit/llvm/llvmjit_expr.c.md`).



### LLVMJitContext
The per-backend JIT session object owned by the LLVM provider; it ties the lifetime of emitted machine code to a resource owner (subxact / xact) and holds the ORC `LLJIT` instances, so compiled expression functions are freed when their transaction ends. [verified-by-code] (`llvmjit.c:152-157` — via `knowledge/files/src/backend/jit/llvm/llvmjit.c.md`).



### lo_create
The large-object API call that creates a new LO with a caller-chosen OID (versus `lo_creat`, which assigns one); `lo_import_internal` uses it while streaming a local file into a large object in `LO_BUFSIZE` (8192-byte) chunks. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-lobj.c.md`).



### lo_export
The counterpart to `lo_import`: writes the contents of a large object out to a file on the server's filesystem. Like the import, it touches server files and so is privilege-restricted. [inferred] (via `knowledge/files/src/bin/psql/large_obj.c.md`).



### lo_import
The server-side SQL/psql function that reads a file on the server's filesystem and stores it as a new large object, returning its OID. Because it reads server files it is restricted to superusers (or `pg_read_server_files`). [inferred] (via `knowledge/files/src/bin/psql/large_obj.c.md`).



### lo_import_internal
The libpq client routine that streams a local file into a new large object: it `open(O_RDONLY|PG_BINARY)`s the file, calls `lo_creat`/`lo_create`, then loops `read -> lo_write` in `LO_BUFSIZE` (8192-byte) chunks, with careful cleanup since a failed `lo_write` has already aborted the server-side transaction. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-lobj.c.md`).



### lo_open
The server-side large-object API call that opens an existing LO by OID for reading and/or writing (`INV_READ` / `INV_WRITE`), returning a descriptor used by `lo_read` / `lo_write`; it lives alongside `lo_create` / `lo_unlink` in `inv_api.c`. [verified-by-code] (`inv_api.c:8` — via `knowledge/files/src/backend/storage/large_object/inv_api.c.md`).



### lo_read
The C-only server-side large-object read primitive (`be-fsstubs.c:153`) operating on an open LO descriptor; note the historical naming split — the SQL-callable forms are `loread`/`lowrite`, while the libpq client wrappers are `lo_read`/`lo_write`. [verified-by-code] (via `knowledge/files/src/backend/libpq/be-fsstubs.c.md`).



### lo_unlink
The large-object API call that deletes an LO and all its `pg_largeobject` chunks; the `vacuumlo` utility finds orphaned LOs (no remaining reference) and `lo_unlink`s them. [verified-by-code] (via `knowledge/files/contrib/vacuumlo/vacuumlo.c.md`).



### lo_write
The C-only server-side large-object write primitive (`be-fsstubs.c:181`) writing into an open LO descriptor; pg_dump and the libpq client buffer data (`LO_BUFSIZE` = 8192) before calling it. Client wrapper name is `lo_write`; the SQL function is `lowrite`. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-lobj.c.md`).



### load_domaintype_info
The typcache routine (`typcache.c`) that walks a domain's ancestor chain and compiles its CHECK/NOT NULL constraints into an executable list cached on the `TypeCacheEntry`, rebuilt on relevant cache invalidation. [verified-by-code] (via `knowledge/idioms/typcache-domain-and-invalidation.md`).



### load_external_function
Loads a shared library (if not already loaded) and resolves a named symbol from it, returning the function pointer; the mechanism behind C-language function lookup and `$libdir`-qualified references. [verified-by-code] (via `knowledge/files/src/backend/utils/fmgr/dfmgr.c.md`).



### load_file
Loads a shared library and runs its `_PG_init` without resolving any particular symbol; used by `LOAD` and `shared_preload_libraries` to pull in a module for its hook side-effects. [verified-by-code] (via `knowledge/files/src/backend/utils/fmgr/dfmgr.c.md`).



### load_relcache_init_file
The boot-time routine that deserializes the nailed and critical-index relcache entries from the `pg_internal.init` cache file (per-DB and shared `global/` copies), keyed by the magic word `RELCACHE_INIT_FILEMAGIC`; `write_relcache_init_file` produces the file. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### LOCAL_FCINFO
A macro (`fmgr.h:110-118`) that stack-allocates a `FunctionCallInfo` for a fixed number of arguments using a union trick that reserves enough aligned `char[]` storage under a `FunctionCallInfoBaseData`-aligned member. It is the canonical on-stack way to build an fcinfo by hand (paired with `FunctionCallInvoke`) and requires `nargs` to be a compile-time constant; the heap alternative is `palloc(SizeForFunctionCallInfo(nargs))`. [verified-by-code] (`fmgr.md` — via `knowledge/idioms/fmgr.md`).



### localbufferalloc
The temp-table analogue of `BufferAlloc`: `LocalBufferAlloc` resolves a backend-private (local) buffer for a block without shared-buffer-manager locking; reached via `PinBufferForBlock` for temp relations. [verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### LocalExecuteInvalidationMessage
Applies a single shared-invalidation message to this backend's caches —
evicting the named relcache/catcache entry — the per-message worker behind
`AcceptInvalidationMessages`. [verified-by-code] (`inval.c:823` — via
`knowledge/files/src/backend/utils/cache/inval.c.md`).



### locallock
The per-backend `LOCALLOCK` re-entry counter in the heavyweight-lock triple (`LOCK` / `PROCLOCK` / `LOCALLOCK`), so double-locking the same object only allocates one shared `PROCLOCK`. [from-README] (via `knowledge/subsystems/storage-lmgr.md`).



### LocalToUtf
The generic conversion driver that maps a server-encoding byte string to UTF-8
via a per-encoding radix/lookup table; the inverse of `UtfToLocal`. Encoding
conversion procedures call it from their `conv_proc` entry points. [verified-by-code]
(via `knowledge/files/src/backend/utils/mb/_conversion_procs.md`).



### lock_timeout
GUC aborting a statement that waits longer than the limit to acquire any lock; `ProcSleep` arms it as `LOCK_TIMEOUT` alongside `STATEMENT_TIMEOUT` and `DEADLOCK_TIMEOUT` in its main sleep loop. pg_dump sets it to 0 for restores. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### LockAcquire
The heavyweight (regular) lock-manager entry point: it finds or creates the
shared `LOCK`/`PROCLOCK` for a lock tag, checks conflicts via
`LockCheckConflicts`, and either grants immediately, takes the fast path for a
weak relation lock, or queues the backend to wait. `LockRelease` /
`LockReleaseAll` undo it. [verified-by-code] (`lock.c:806` — via
`knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### LockAcquireExtended
The heavyweight-lock acquisition core that handles fast-path eligibility, the
shared lock table, and wait-queue insertion; it calls `JoinWaitQueue` while
holding the lock-partition LWLock exclusively. [verified-by-code]
(`proc.c:1193` — via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### LockBuffer
The macro (wrapping `LockBufferInternal`) that takes or releases a buffer's
content lock in `BUFFER_LOCK_SHARE`/`BUFFER_LOCK_EXCLUSIVE`/`BUFFER_LOCK_UNLOCK`
mode — distinct from the pin that keeps the buffer resident. Readers take SHARE,
page-modifiers take EXCLUSIVE, and `LockBufferForCleanup` waits for the pin
count to drop to one for destructive operations like VACUUM pruning.
[verified-by-code] (`bufmgr.c:6567-6910` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### LockBufferForCleanup
Acquires a "cleanup" (superexclusive) lock on a buffer — an exclusive content
lock plus the guarantee of being the only pinner — required by operations like
VACUUM that must rearrange a page's line pointers. [verified-by-code] (via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### LockBufHdr
Acquires the per-buffer header spinlock encoded in the high bit of the
`BufferDesc` atomic state word, giving exclusive access to the buffer's tag and
flags for the brief critical section of pinning, tag reassignment, or flag
updates. `WaitBufHdrUnlocked` spins for a concurrent holder to release.
[verified-by-code] (`bufmgr.c:7527-7593` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### lockdatabaseobject
One of `lmgr.c`'s LOCKTAG-building façade functions; `LockDatabaseObject` takes a heavyweight lock on an arbitrary catalog object identified by (classId, objId, objsubId). [verified-by-code] (via `knowledge/subsystems/storage-lmgr.md`).



### lockGroupMembers
The PGPROC list (with `lockGroupLeader`/`lockGroupLink`) recording the members of a parallel lock group; all three fields are protected by the single partition LWLock chosen by `LockHashPartitionLockByProc(leader)`, so the deadlock detector (already holding every partition lock) can read them without extra locking. [from-README] (via `knowledge/subsystems/storage-lmgr.md`).



### LockHashPartitionLockByProc
Chooses the lock-manager partition LWLock that guards a process group's group-locking fields (`lockGroupLeader` / `lockGroupMembers` / `lockGroupLink`) by hashing the leader's pgprocno, so all parallel lock-group bookkeeping for one group falls under a single deterministic partition lock. [from-README] (`lock.h` — via `knowledge/subsystems/storage-lmgr.md`).



### LOCKMODE
The integer type naming a heavyweight lock strength (e.g. `AccessShareLock` .. `AccessExclusiveLock`), used as the argument to `LockRelation`/`table_open` and checked against the per-method conflict table to decide whether a request must wait. amcheck and many AMs take a relation under a specific LOCKMODE before reading. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_common.md`).



### LockRelationForExtension
The relation-extension lock taken before adding a new block to a heap or
index, serialising concurrent extenders so two backends don't both think they
created the same block number. It is a short-duration lock released as soon as
the page is added; read-only inspectors like `pgstatindex` deliberately do NOT
take it. [verified-by-code] (via
`knowledge/files/contrib/pgstattuple/pgstatindex.c.md`).



### LockRelationOid
Acquires a heavyweight relation lock by OID in a given mode, registering it with the lock manager so it is released at transaction end; the low-level lock under `table_open`/`relation_open`, also called directly when locking a relation without opening it. [verified-by-code] (via `knowledge/files/contrib/pg_prewarm/pg_prewarm.c.md`).



### LockRelease
The heavyweight lock-manager routine that releases one held lock on a `LOCKTAG` for a given mode, decrementing the `LOCK`/`PROCLOCK` and waking waiters if the lock becomes grantable. [verified-by-code] (`lock.c:806` — via `knowledge/files/src/backend/storage/lmgr/lock.c.md`).



### LockReleaseAll
Releases all heavyweight locks of a given lock method held by the backend at
transaction end (or on a specified lockmethod), walking the local lock table and
the shared `PROCLOCK`s. [verified-by-code] (via
`knowledge/data-structures/proclock.md`).



### LockRows
The executor node implementing row-level locking (`SELECT ... FOR UPDATE/SHARE`)
above its child scan; it locks each returned row and triggers EPQ rechecks when
a row was concurrently updated. [verified-by-code] (via
`knowledge/idioms/epq-multi-table.md`).



### LOCKTAG
The struct uniquely identifying the object a heavyweight lock protects — a tag of (locktag fields + lock method) covering relations, tuples, transactions, pages, advisory locks, etc. `LOCKTAG_TUPLE` is used, for example, by `systable_inplace_update_begin` to serialize inplace catalog updates against concurrent readers. [verified-by-code] (via `knowledge/files/src/backend/access/index/genam.c.md`).



### LOCKTAG_RELATION_EXTEND
The heavyweight `LOCKTAG` type taken briefly while extending a relation by a new page; the deadlock detector special-cases it (`FindLockCycleRecurseMember` bails immediately on it) because it is always held only momentarily. [verified-by-code] (`deadlock.c:556-557` — via `knowledge/subsystems/storage-lmgr.md`).



### LOCKTAG_TUPLE
A heavyweight-lock tag identifying a specific tuple (relation + block +
offset), used where buffer content locks are too short-lived — e.g.
`systable_inplace_update` takes one so a concurrent reader of a
`pg_class.relfrozenxid` in-place update sees a torn write only if it explicitly
re-reads. [verified-by-code] (via
`knowledge/files/src/backend/access/index/genam.c.md`).



### LockTagType
The one-byte discriminator inside a `LOCKTAG` naming what kind of object a
heavyweight lock protects; PG defines twelve (RELATION, RELATION_EXTEND, PAGE,
TUPLE, TRANSACTION, VIRTUALTRANSACTION, OBJECT, ADVISORY, and so on).
[verified-by-code] (`locktag.h:35-72` — via
`knowledge/subsystems/storage-lmgr.md`).



### LockTuple
The heavyweight tuple-lock API (`LockTuple`/`ConditionalLockTuple`/`UnlockTuple`) used as the *arbiter* that serializes concurrent row-lockers; the actual row-lock state still lives in the tuple's xmax/infomask, not in this lock. [verified-by-code] (`lmgr.c:562` — via `knowledge/files/src/backend/storage/lmgr/lmgr.c.md`).



### LockTupleMode
The enum naming the strength of a row-level lock
(`LockTupleKeyShare`/`Share`/`NoKeyExclusive`/`Exclusive`), as requested by
`SELECT ... FOR [KEY] SHARE/UPDATE` and by the executor's
`table_tuple_lock`. Logical-replication apply and EvalPlanQual re-find the live
tuple and re-lock it in the requested `LockTupleMode`. [verified-by-code] (via
`knowledge/files/src/backend/executor/execReplication.c.md`).



### log_lock_waits
GUC that logs a message when a backend has waited longer than `deadlock_timeout` for a lock (the deadlock check runs, and if no deadlock is found the long wait is logged); one of the ms-valued lock GUCs referenced from `proc.h`. [verified-by-code] (via `knowledge/files/src/include/storage/proc.h.md`).



### log_min_messages
GUC setting the minimum elevel written to the server log; `is_log_level_output()` implements its comparison with special ordering for LOG (sorted between ERROR and FATAL for the server-log test) and never sends `*_CLIENT_ONLY` messages to the log regardless of the setting. [verified-by-code] (via `knowledge/files/src/backend/utils/error/elog.c.md`).



### log_opts
The pg_upgrade `LogOpts` global holding logging configuration (verbose/internal log files, retention); one of the four process-wide globals (`log_opts`, `user_opts`, `old_cluster`, `new_cluster`) that thread state through the upgrade driver. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/util.c.md`).



### log_parameter_max_length
GUC bounding how many bytes of each bound parameter value are rendered when a statement's parameters are logged; `-1` means unlimited and it gates a data-leak surface in auto_explain's parameter logging. [verified-by-code] (via `knowledge/files/contrib/auto_explain/auto_explain.c.md`).



### logical decoding
The mechanism that turns the physical WAL stream back into a logical sequence
of row-level INSERT/UPDATE/DELETE changes, driven by a replication slot and an
output plugin. It underpins logical replication and CDC tooling without those
consumers parsing WAL themselves. [from-README] (via
`knowledge/subsystems/replication.md`).



### LogicalConfirmReceivedLocation
One of the slot-side advancement APIs in `logical.c` (alongside `LogicalIncreaseXminForSlot` and `LogicalIncreaseRestartDecodingForSlot`) by which a logical replication slot records that the consumer has confirmed receipt up to a given LSN. This lets the slot advance its catalog xmin and restart_lsn so WAL and old catalog rows below the confirmed point can be reclaimed. [verified-by-code] (`logical.c` — via `knowledge/files/src/backend/replication/logical/logical.c.md`).



### LogicalDecodingContext
The per-slot heap-allocated state of a logical decoding session, wiring
together the reorder buffer, the snapshot builder, and the output plugin's
callbacks; it lives in its own memory context. [verified-by-code]
(`logical.h:33-115` — via
`knowledge/files/src/include/replication/logical.h.md`).



### LogicalDecodingProcessRecord
The logical-decoding dispatch entry point: for each WAL record read via an `XLogReaderState` it switches on `XLogRecGetRmid` and routes to the per-rmgr decode handler (xlog, heap, heap2, xact, standby, logicalmsg). [verified-by-code] (via `knowledge/files/src/include/replication/decode.h.md`).



### LogicalRepApplyLoop
The main loop of a logical-replication apply worker: it waits on the
walreceiver stream, dispatches each decoded change to the apply handlers, and
periodically sends feedback. [verified-by-code] (via
`knowledge/idioms/apply-worker-loop-and-dispatch.md`).



### LogicalRepMsgType
The single-byte tag of a logical-replication protocol message ('B' begin, 'C' commit, 'I'/'U'/'D' insert/update/delete, plus stream variants); the apply worker's apply_dispatch switches on it. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/worker.c.md`).



### LogicalRepRelMapEntry
A subscriber-side cache entry mapping a publisher relation to the corresponding local relation plus the column and type mapping and the relation's sync/ready state; it is keyed by the remote relation id. [verified-by-code] (via `knowledge/files/src/include/replication/logicalrelation.h.md`).



### LogicalTape
One logical tape in the logtape abstraction: an append/read stream multiplexed with others onto a single temp file so external merge sort can maintain many "tapes" without one file per run. [verified-by-code] (`logtape.c` — via `knowledge/files/src/backend/utils/sort/logtape.c.md`).



### LogOpts
The pg_upgrade logging-options struct (`log_opts` global) carrying the internal/verbose log-file handles and related flags used across the upgrade driver. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/util.c.md`).



### LogwrtResult
The shared cached pair of WAL positions (Write and Flush) recording how far the
WAL has been written to the OS and fsynced to disk; backends consult it to avoid
redundant `XLogFlush` work. [verified-by-code] (via
`knowledge/idioms/wal-buffer-state.md`).



### lookup_type_cache
The typcache entry point: a cheap hashtable lookup keyed by type OID that then
lazily computes only the fields the caller's `TYPECACHE_*` flags request
(equality operator, btree opfamily, hash proc, …) and caches "tried and none
exists" negatives. It is how the executor and others get a type's comparison and
I/O support without repeated catalog scans. [verified-by-code] (via
`knowledge/files/src/backend/utils/cache/typcache.c.md`).



### loread
The server-side large-object read entry point invoked through the fastpath / SQL LO interface; given an LO descriptor from `lo_open(..., INV_READ)` (or `INV_WRITE`) it returns the next chunk of object data. [verified-by-code] (`inv_api.c:162` — via `knowledge/files/src/backend/storage/large_object/inv_api.c.md`).



### lossy bitmap
The degraded form a Bitmap Heap Scan's TID bitmap takes when it would exceed `work_mem`: it stores whole-page bits rather than individual tuple TIDs, so every tuple on a lossy page must be re-tested against the original qual (surfaced as `Recheck Cond` in `EXPLAIN`). [from-docs §11.5 / §14.1] (via `knowledge/docs-distilled/indexes-bitmap-scans.md`).



### LOWER_NODE
The compile-time `ltree.h` macro selecting whether ltree label CRCs are computed case-folded (default) or byte-literal (MSVC); it is deliberately frozen because it determines on-disk GiST signature CRCs, so changing it is a pg_upgrade-breaking event. [verified-by-code] (`ltree.h:29` — via `knowledge/files/contrib/ltree/ltree_gist.c.md`).



### lowmask
The hash-index metapage bitmask applied to a hash code first in `_hash_hashkey2bucket`; if the result overflows `maxbucket` the code is remasked with `highmask`. Together `lowmask`/`highmask` bound the current bucket-number range during linear-hash growth. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### LP_DEAD
The line-pointer flag marking an item as dead — its heap/index tuple is known gone — so scans can skip it and page-level cleanup can reclaim its space. In indexes the bit is a dirty *hint* set by scans; actual cleanup happens later (e.g. at insert time via `_hash_vacuum_one_page` / nbtree page-pruning). [verified-by-code] (via `knowledge/files/src/backend/access/hash/hashsearch.c.md`).



### lp_flags
`lp_flags` is the 2-bit line-pointer status field (`LP_UNUSED` / `LP_NORMAL` / `LP_REDIRECT` / `LP_DEAD`) in an `ItemIdData`, encoding a slot's state within a heap or index page. [from-docs] (via `knowledge/docs-distilled/storage.md`).



### lp_len
The length field of a heap/index line pointer (ItemId) giving the on-page byte length of the pointed-to item; together with `lp_off` it locates the tuple within the page. amcheck validates the geometry invariants `lp_len >= MAXALIGN(SizeofHeapTupleHeader)` and `lp_off + lp_len <= BLCKSZ`. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### LP_NORMAL
The `ItemId` line-pointer state for a slot that points at a normal, stored
heap tuple (both offset and length are valid), as opposed to `LP_UNUSED`,
`LP_REDIRECT`, or `LP_DEAD`. [verified-by-code] (via
`knowledge/files/contrib/amcheck/verify_heapam.md`).



### lp_off
The 15-bit byte offset within an 8 kB page where a line pointer's (`ItemIdData`)
tuple begins; together with `lp_len` and `lp_flags` it forms the item
identifier in the page's line-pointer array. The offset is to the start of the
tuple, measured from the page beginning. [verified-by-code] (via
`knowledge/files/src/include/storage/itemid.h.md`).



### LP_REDIRECT
An `ItemId` line-pointer state used by HOT: a redirecting pointer whose
offset names the live root of a HOT chain after the original root tuple was
pruned, keeping index entries valid without rewriting them.
[verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### LP_UNUSED
An `ItemId` line-pointer state marking a slot that holds no storage and is
free for reuse; produced by page pruning and vacuum reclaiming dead tuples.
[verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### LSN (log sequence number)
A byte position in the continuous WAL stream, represented by the 64-bit
`XLogRecPtr` type. Every WAL record and every modified page records an LSN;
comparing LSNs orders changes in time, and `InvalidXLogRecPtr` (0) marks "no
position". [verified-by-code] (`xlogdefs.h:28` — via
`knowledge/files/src/include/access/xlogdefs.h.md`).



### ltq_regex
The ltree `~` (ltree-matches-lquery) operator function; it always `PG_FREE_IF_COPY`s its detoasted args, which is why the wrapper `lt_q_regex` must be careful invoking it via `DirectFunctionCall2` to avoid double-freeing shared pointers. [from-comment] (via `knowledge/files/contrib/ltree/lquery_op.c.md`).



### ltree_compare
The C three-way comparator backing the `ltree` ordering operators (`<`/`<=`/`=`/`>=`/`>`, `<>`) and the `ltree_cmp` SQL function; it walks two ltree paths level-by-level. The `ltree_op.c` doc notes a commit restructured this comparator. [verified-by-code] (`ltree_op.c:49` — via `knowledge/files/contrib/ltree/ltree_op.c.md`).



### ltree_crc32_sz
ltree's label-hashing CRC32 routine; it is not cryptographic and carries no collision-resistance requirement — it only spreads labels across GiST signature bits — and its case-fold behavior is governed by `LOWER_NODE`. [verified-by-code] (`crc32.h:6-7` — via `knowledge/files/contrib/ltree/ltree_gist.c.md`).



### ltree_execute
The polish-notation evaluator (`ltxtquery_op.c:20`) that walks an `ltxtquery` tree against a value using a caller-supplied match callback; it is reused by both plain ltree matching and the GiST signature-bit consistent check. [verified-by-code] (via `knowledge/files/contrib/ltree/ltree.h.md`).



### LTREE_MAX_LEVELS
The ltree limit `LTREE_MAX_LEVELS = PG_UINT16_MAX = 65535`, deriving from `ltree.numlevel` being a `uint16`. It is enforced at parse time (`ltree_io.c`), at concatenation (`ltree_concat` rejects `a.numlevel + b.numlevel > LTREE_MAX_LEVELS`), and on lquery low/high bounds; combined with `LTREE_LABEL_MAX_CHARS = 1000` it bounds a single legitimate input at roughly 65 MB. [verified-by-code] (`ltree.h` — via `knowledge/files/contrib/ltree/ltree.h.md`).



### LW_EXCLUSIVE
The `LWLockAcquire` mode requesting exclusive ownership of a lightweight
lock, blocking all other shared and exclusive waiters until released;
contrast `LW_SHARED`. [verified-by-code] (via
`knowledge/subsystems/storage-lmgr.md`).



### LW_FLAG_HAS_WAITERS
The LWLock state bit (bit 31) indicating the lock has queued waiters that must be woken when it is released. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).



### LW_FLAG_LOCKED
The LWLock state bit (bit 29) that acts as a spinlock substitute, protecting manipulation of the lock's wait-list proclist. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).



### LW_SHARED
The shared (reader) acquisition mode of a lightweight lock, passed to `LWLockAcquire`; any number of backends may hold an LWLock in `LW_SHARED` simultaneously, versus the single holder of `LW_EXCLUSIVE`. A third internal mode, `LW_WAIT_UNTIL_FREE`, exists only for `LWLockAcquireOrWait` and the WAL-insert locks. [verified-by-code] (`lwlock.h:102-109` — via `knowledge/subsystems/storage-lmgr.md`).



### LWLock
A *lightweight lock* — the mid-weight shared-memory lock between a spinlock and the heavyweight lock manager, used to serialize access to shared structures (buffer headers, SLRU pools, the proc array). Acquired in `LW_SHARED` or `LW_EXCLUSIVE` mode via `LWLockAcquire`; backends queue on a waitlist and are woken by the releaser rather than spinning. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/s_lock.c.md`).



### LWLock (lightweight lock)
The in-memory lock used to guard shared-memory data structures, offering
exclusive and shared modes but no deadlock detection. LWLocks are cheap
relative to the heavyweight lock manager and are automatically released on
`elog(ERROR)` via `LWLockReleaseAll`. [from-comment] (`lwlock.c:6` — via
`knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).



### LWLockAcquire
Acquires a lightweight lock in `LW_SHARED` or `LW_EXCLUSIVE` mode, sleeping
on the lock's wait queue if it can't be granted immediately; it is the
primary primitive guarding shared-memory data structures. [verified-by-code]
(via `knowledge/subsystems/storage-lmgr.md`).



### LWLockAcquireOrWait
The LWLock entry point that acquires the lock if free, otherwise waits until it becomes free and then returns *without* holding it — the semantics the WAL-insert locks rely on. It is the sole user of the internal `LW_WAIT_UNTIL_FREE` mode, letting a backend block until an in-progress WAL insert finishes without itself taking the insert lock. [verified-by-code] (`lwlock.h:102-109` — via `knowledge/subsystems/storage-lmgr.md`).



### LWLockInitialize
Initialises an `LWLock` in place (clearing state and assigning a tranche id); called once for each lightweight lock at shared-memory setup. [verified-by-code] (`lwlock.c:562` — via `knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).



### LWLockNewTrancheId
Allocates a fresh, process-global tranche id at runtime so dynamically created LWLocks (e.g. those living in a DSM segment) can be grouped and named via `LWLockRegisterTranche`. It is the dynamic counterpart to the named-tranche request path. [inferred] (`lwlock.c:519` — via `knowledge/scenarios/add-new-lwlock-tranche.md`).



### LWLockRelease
Releases an LWLock held by the current backend and wakes the next compatible
waiter(s) on its queue; every `LWLockAcquire` must be balanced by exactly
one of these (resource owners catch leaks on error). [verified-by-code] (via
`knowledge/subsystems/storage-lmgr.md`).



### LWLockReleaseAll
Releases every LWLock the backend currently holds; called early in transaction abort / error cleanup (`ipc.c`) so cleanup callbacks may re-acquire. It is deliberately interrupt-balance-neutral, doing one `HOLD_INTERRUPTS()` per held lock to match the coming `RESUME_INTERRUPTS()`. [from-comment] (`lwlock.c` — via `knowledge/files/src/backend/storage/lmgr/lwlock.c.md`).



### main_fn
The entry-function pointer in an auxiliary / background-process registration (e.g. `BackgroundWriterMain`); the postmaster spawns the singleton process and dispatches into its `main_fn`. [verified-by-code] (`bgwriter.c:16` — via `knowledge/files/src/backend/postmaster/bgwriter.c.md`).



### MAIN_FORKNUM
The `ForkNumber` (0) of a relation's main data fork, as distinct from the
free-space-map (`FSM_FORKNUM`), visibility-map (`VISIBILITYMAP_FORKNUM`),
and unlogged-table init forks. [verified-by-code] (via
`knowledge/subsystems/contrib-pageinspect.md`).



### MainLoop
psql's REPL: the function `MainLoop(FILE *source)` reads lines, feeds them to the psqlscan flex lexer to separate SQL from backslash commands, accumulates SQL into a `query_buf`, and on each semicolon (or EOF) calls `SendQuery`, otherwise calls `HandleSlashCmds`. It is re-entrant — `process_file` calls it recursively for `\i`, and `startup.c`'s `main` calls it with stdin for interactive sessions. [verified-by-code] (`mainloop.c:32` — via `knowledge/files/src/bin/psql/mainloop.c.md`).



### MainLWLockArray
The shared-memory array holding all individually-named LWLocks plus the slices handed out by `RequestNamedLWLockTranche`; the named locks are declared via `PG_LWLOCK` macros in `lwlocklist.h`. [verified-by-code] (`lwlocklist.h:34-91` — via `knowledge/idioms/locking-overview.md`).



### maintenance_work_mem
The memory budget (default 65536 kB) for maintenance operations such as VACUUM and index build; VACUUM's TID store grows until it hits this cap, then pauses phase I to drain dead items before resuming. [from-comment] (via `knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).



### make_join_rel
The optimizer routine that builds (or finds) the `RelOptInfo` joining two relation sets and adds candidate join paths to it; the core join-search levels and GEQO's tour evaluation both call it repeatedly. [verified-by-code] (via `knowledge/files/src/include/optimizer/paths.h.md`).



### make_one_rel
The join-search entry point (`planmain.c` → `allpaths.c`): given the list of base relations it first sizes and paths each baserel, then drives the dynamic-programming join enumeration up to the single `RelOptInfo` for the whole FROM clause. [verified-by-code] (via `knowledge/files/src/backend/optimizer/plan/planmain.c.md`).



### make_pathkeys_for_sortclauses
Builds the list of `PathKey`s describing the ordering required by an ORDER BY / GROUP BY clause list (`pathkeys.c`), the canonical form the planner compares against a path's existing sort order to decide whether an explicit Sort is needed. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/pathkeys.c.md`).



### make_postgres
The initdb phase that clones the freshly bootstrapped `template1` into the default `postgres` database. [verified-by-code] (`initdb.c:2094` — via `knowledge/docs-distilled/creating-cluster.md`).



### make_rel_from_joinlist
The entry point (`allpaths.c`) into the join-order search: it takes the deconstructed join list and drives either the exhaustive dynamic-programming join search or, past `geqo_threshold`, the genetic optimizer. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### MAKE_SYSCACHE
The macro that declares one syscache: it ties a `SysCacheIdentifier` enum value
to the backing catalog and the unique index used as the lookup key, feeding the
generated `cacheinfo[]` table that `InitCatalogCache` builds from.
[verified-by-code] (`syscache.c:13` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### make_template0
The initdb phase that clones `template1` into the pristine `template0` — the untouched source for `CREATE DATABASE ... TEMPLATE template0`. [verified-by-code] (`initdb.c:2040` — via `knowledge/docs-distilled/creating-cluster.md`).



### makeNode
Allocates a zeroed node of the given type and stamps its `nodeTag`; every parse/plan node creation goes through it so `nodeTag()` dispatch in the copy/equal/out/read funcs works. [verified-by-code] (via `knowledge/files/src/backend/parser/gram.y.md`).



### makeObjectName
Constructs a candidate catalog object name from up to three component strings, truncating on NAMEDATALEN with a separator; the basis for `ChooseRelationName`/`ChooseIndexName` auto-naming of constraints and indexes. [verified-by-code] (`indexcmds.c:2546` — via `knowledge/files/src/backend/commands/indexcmds.c.md`).



### makeStringInfo
Allocates and initialises a `StringInfo` in one call (palloc + `initStringInfo`), returning the pointer; used where the buffer outlives the current stack frame, e.g. as aggregate transition state. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/bytea.c.md`).



### MarkAsPreparing
The two-phase-commit step that allocates a dummy PGPROC/GlobalTransaction for a `PREPARE TRANSACTION`, reserving the GID and transferring the backend's locks and xid to the prepared-transaction slot so the state survives the originating session. [verified-by-code] (`twophase.c` — via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### MarkBufferDirty
The call that flags a pinned, exclusively-locked buffer as modified so the
background writer/checkpointer will eventually write it; it must run inside the
WAL critical section so the dirty mark and the WAL record are atomic with
respect to crashes. Contrast `MarkBufferDirtyHint`, which is for
non-WAL-critical hint-bit changes. [verified-by-code] (`bufmgr.c:3156` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### MarkBufferDirtyHint
Marks a buffer dirty for a non-critical "hint" change (e.g. setting a tuple
hint bit or a VM bit), optionally emitting a WAL full-page image when
checksums or `wal_log_hints` are on; unlike `MarkBufferDirty` it tolerates
being skipped. [from-comment] (via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MarkGUCPrefixReserved
The call an extension makes (typically in `_PG_init`) to claim a custom-GUC
prefix such as `postgres_fdw.`, so the GUC machinery rejects unknown
`prefix.something` settings instead of silently keeping them as placeholders.
It is how a module turns its namespace into validated configuration.
[verified-by-code] (`option.c:572` — via
`knowledge/files/contrib/postgres_fdw/option.c.md`).



### MAX_BACKENDS
The maximum number of backend processes, defined in `procnumber.h` as `(1U << 18) - 1 = 262143` from `MAX_BACKENDS_BITS = 18`. The value is load-bearing across shared-memory bit-packing: `StaticAssertDecl`s constrain `MAX_BACKENDS_BITS` to fit the buffer-descriptor refcount field, the LWLock state encodes shared counts `1..MAX_BACKENDS` with the exclusive sentinel `LW_VAL_EXCLUSIVE = MAX_BACKENDS + 1`, and snapshot xip arrays are sized to `MAX_BACKENDS * 2`. [verified-by-code] (`procnumber.h.md` — via `knowledge/files/src/include/storage/procnumber.h.md`).



### max_connections
GUC capping concurrent backends (default 100); it sizes many shared-memory structures via `CalculateShmemSize`, interacts with the OS per-process FD limit (e.g. io_uring's `RLIMIT_NOFILE` needs), and is recorded in `pg_control` for hot-standby compatibility. [verified-by-code] (via `knowledge/files/src/include/catalog/pg_control.h.md`).



### MAX_LOCKMODES
The maximum number of heavyweight lock modes (10) in a lock method's conflict table; it bounds the `LOCKMODE` range and the per-mode arrays in a `LOCK`. [verified-by-code] (via `knowledge/files/src/include/storage/lock.h.md`).



### max_locks_per_transaction
GUC (default 64, restart-only) that sizes the shared lock table as `max_locks_per_transaction × (max_connections + prepared xacts)`; it bounds the whole table, NOT the locks any single transaction may take. [from-README] (via `knowledge/docs-distilled/runtime-config-locks.md`).



### max_prepared_transactions
GUC capping concurrently-prepared two-phase transactions; it also enlarges the shared lock table sizing (`max_connections + max_prepared_transactions`) and is one of the settings recorded for hot-standby compatibility. [from-README] (via `knowledge/docs-distilled/hot-standby.md`).



### max_slot_wal_keep_size
GUC capping how much WAL a replication slot may pin before the slot is invalidated (`max_slot_wal_keep_size_mb`, default `-1` = unbounded); at the default, one abandoned slot can fill the WAL volume — a documented DoS surface. [verified-by-code] (via `knowledge/files/src/include/replication/slot.h.md`).



### max_stack_depth
GUC (default ~2 MB) that `check_stack_depth()` enforces to abort runaway C recursion before a true stack overflow; recursive parsers/evaluators (ltree, intarray, jsonpath) rely on it, and a query parsed under a large `max_stack_depth` can fail to evaluate on a backend with a smaller one. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_bool.md`).



### max_wal_senders
GUC sizing the shared array of `WalSnd` slots for replication connections; `SyncRepRequested()` is `max_wal_senders > 0 && synchronous_standby_names` set, and the value is recorded in `pg_control` for standby compatibility. [verified-by-code] (via `knowledge/files/src/include/replication/walsender_private.h.md`).



### max_worker_processes
GUC (default 8) capping the total background-worker slots the postmaster reserves at startup (shared by parallel workers, logical apply, and extension workers); recorded in `pg_control` for standby compatibility. [verified-by-code] (via `knowledge/files/src/backend/utils/init/globals.c.md`).



### MAXALIGN
The macro rounding a size or pointer up to `MAXIMUM_ALIGNOF`, the strictest alignment any SQL datum requires; tuple headers, datums on a page, and palloc chunks are all MAXALIGN'd so typed access never faults. Width estimates and on-page layout math (e.g. `MAXALIGN(width) + MAXALIGN(SizeofHeapTupleHeader)`) use it constantly. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### MaxAllocHugeSize
The upper bound (`SIZE_MAX/2`) on a "huge" allocation requested via `MCXT_ALLOC_HUGE` / `palloc_huge`, distinct from the ordinary 1 GB `MaxAllocSize` cap that guards normal palloc calls. [verified-by-code] (via `knowledge/idioms/memory-contexts.md`).



### MaxAllocSize
The 1 GB − 1 (`0x3fffffff`) soft ceiling that ordinary `palloc` enforces;
requests above it raise an error. Chosen so allocation sizes always fit safely
in arithmetic; allocations that genuinely need more must use the `*Huge`
variants (`MemoryContextAllocHuge`, `palloc_extended` with `MCXT_ALLOC_HUGE`),
which raise the bound to `SIZE_MAX/2`. [from-comment] (`memutils.h:40` — via
`knowledge/idioms/memory-contexts.md`).



### MaxBackends
The computed ceiling on concurrent backends (max_connections + autovacuum workers + background workers + auxiliary procs); shared-memory structures such as the deadlock detector's worst-case workspace are pre-sized from it at startup. [verified-by-code] (`deadlock.c:143` — via `knowledge/files/src/backend/storage/lmgr/deadlock.c.md`).



### MaxBlockNumber
The largest valid `BlockNumber`, one below `InvalidBlockNumber`
(0xFFFFFFFE), bounding a relation at ~4 billion blocks. Code that allocates
per-block arrays sized off the relation length is implicitly bounded by it —
and doing so without the huge-allocation flag is a flagged resource concern in
`pg_visibility`. [verified-by-code] (via
`knowledge/files/contrib/pg_visibility/pg_visibility.c.md`).



### maxBlockSize
The `AllocSet` field capping how large the context's geometrically growing malloc'd blocks may get; `nextBlockSize` doubles toward this ceiling as more blocks are needed. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### maxbucket
The hash-index metapage field holding the highest live bucket number; combined with `highmask`/`lowmask` in `_hash_hashkey2bucket` it maps a hash code to a bucket during the incremental (one-bucket-at-a-time) table growth. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### MaxHeapTuplesPerPage
The upper bound on line pointers a heap page can hold, derived from the smallest possible tuple and the page size; it sizes per-page work arrays (e.g. prune/redirect) and bounds the OffsetNumbers on a heap page. [verified-by-code] (via `knowledge/files/src/backend/access/heap/pruneheap.c.md`).



### MAXIMUM_ALIGNOF
The widest fundamental alignment the platform requires (typically 8), used throughout the backend for MAXALIGN'd layout; defined in `c.h`. It intentionally excludes wider-than-8 types such as `int128`, which is why `int128` needs an explicit `pg_attribute_aligned(MAXIMUM_ALIGNOF)`, and it backs MAXALIGN'd helpers like `PGAlignedBlock`. [verified-by-code] (`c.h` — via `knowledge/files/src/include/c.h.md`).



### maxMsgNum
The monotonically increasing index of the next slot to fill in the shared sinval message ring (`SISeg`); each backend tracks how far it has read (`nextMsgNum`) so it knows which invalidation messages it still owes itself. When readers fall too far behind the queue, a reset is forced. [inferred] (via `knowledge/files/src/backend/storage/ipc/sinvaladt.c.md`).



### maxnummessages
`MAXNUMMESSAGES` is the fixed size of the shared sinval message ring; a backend that falls more than this many messages behind is force-reset (its reset flag set) rather than fed individual invalidations. [verified-by-code] (via `knowledge/idioms/sinvaladt-broadcast.md`).



### MaxOffsetNumber
The largest possible line-pointer offset on a page (`BLCKSZ / sizeof(ItemIdData)`),
the upper bound for `OffsetNumber` loops over a page's item array. [verified-by-code]
(via `knowledge/idioms/vacuum-tid-store.md`).



### MAXPGPATH
The compile-time maximum length (1024) for a filesystem-path buffer in PostgreSQL C code; path helpers snprintf into char[MAXPGPATH] arrays and treat truncation past it as an error. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md`).



### maybe_sleeping
One of the two memory-barriered flag states of a `Latch` (`is_set` + `maybe_sleeping`); the setter checks `maybe_sleeping` to decide whether it must actually wake the waiter, the handshake that keeps latch set/wait race-free. [from-comment] (via `knowledge/subsystems/storage-ipc.md`).



### MCTX_ALIGNED_REDIRECT_ID
The memory-context method ID (slot 6 in `mcxt_methods[]`, defined in `memutils_internal.h`) for the `palloc_aligned` indirection-chunk mechanism. A chunk of this type, created by `palloc_aligned` (`mcxt.c:1485+`), stores the requested `alignto` in its value field and redirects `pfree`/`repalloc` back to the real allocation; most method slots for this ID are NULL because only the alignment-redirection operations are wired in (`alignedalloc.c`). [verified-by-code] (`memory-context-api-and-dispatch.md` — via `knowledge/idioms/memory-context-api-and-dispatch.md`).



### MCV
Most-Common-Values list — the per-column (and, for extended statistics, multi-column) array of frequent values and their frequencies that ANALYZE stores in `pg_statistic`. The planner's selectivity estimators read the MCV list to estimate equality and range selectivity before falling back to histogram or default assumptions. [verified-by-code] (via `knowledge/files/src/backend/statistics/extended_stats.c.md`).



### MCXT_ALLOC_HUGE
The `MemoryContextAllocExtended` flag that lifts the normal 1 GB allocation
cap, allowing a single chunk up to `MaxAllocHugeSize`; used for genuinely
large buffers like big sorts. [verified-by-code] (via
`knowledge/subsystems/utils-mmgr.md`).



### MCXT_ALLOC_NO_OOM
A flag to `palloc_extended`/`MemoryContextAllocExtended` that makes an
allocation return `NULL` on failure instead of the usual
`ereport(ERROR)`-on-OOM behavior, for the rare caller that wants to handle
out-of-memory itself. [verified-by-code] (`mcxt.c:1200-1214` — via
`knowledge/subsystems/utils-mmgr.md`).



### mcxt_methods
The 16-entry vtable in `mcxt.c`, indexed by the `MemoryContextMethodID` packed into the low bits of each chunk header, that dispatches `alloc` / `free_p` / `realloc` / `reset` / `delete_context` / etc. to the per-context-type implementation. [verified-by-code] (`mcxt.c:67` — via `knowledge/subsystems/utils-mmgr.md`).



### MD5
The legacy message-digest hash PostgreSQL still supports for password authentication (`md5` verifiers) and as a SQL `md5()` function. `crypt.c` computes and verifies the salted MD5 password format; SCRAM-SHA-256 is the modern replacement for authentication. [verified-by-code] (via `knowledge/files/src/backend/libpq/crypt.c.md`).



### mdextend
The magnetic-disk (md) smgr single-block extend (`md.c:487`) — writes one new block at the end of a relation fork, growing the segment file (and rolling to a new 1GB segment at `RELSEG_SIZE`). The bulk path is `mdzeroextend`. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/md.c.md`).



### mdreadv
The md smgr vectored synchronous read (`md.c:858`) — reads one or more consecutive blocks of a relation fork into caller buffers in a single `preadv`, the modern replacement for the old per-block `mdread`. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/md.c.md`).



### mdwritev
The md smgr vectored synchronous write (`md.c:1070`), the mirror of `mdreadv` — writes consecutive blocks of a relation fork with a single `pwritev` and registers an fsync request with the checkpointer. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/md.c.md`).



### MEMORY_CONTEXT_CHECKING
A cassert-only build option (implied by `USE_ASSERT_CHECKING`) that makes the
allocators write sentinel bytes (`0x7E`) just past each chunk's requested size
and check them on free, catching small buffer overruns. It also enables
`randomize` fills of freed memory. [from-comment] (via
`knowledge/files/src/backend/utils/mmgr/memdebug.c.md`).



### MemoryChunk
The per-allocation header an allocator prepends to each `palloc`'d block,
encoding the owning context (or an offset to it) and the chunk size in a packed
word so that `pfree`/`repalloc` can recover the context from just the user
pointer. [verified-by-code] (`aset.c:128` — via
`knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### MemoryChunkGetBlock
Given a `MemoryChunk` pointer, recovers the owning block/header — used, for example, by the aligned-allocation redirect to find the real unaligned chunk to `pfree`. It asserts the chunk is not an external (huge) chunk. [verified-by-code] (`memutils_memorychunk.h:39` — via `knowledge/subsystems/utils-mmgr.md`).



### MemoryChunkSetHdrMask
Packs a chunk's owning-block offset, size class, and context-method id into the 64-bit `MemoryChunk` header word so that `pfree`/`repalloc` can recover the context and block from the chunk pointer alone. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### MemoryContext
A node in the hierarchical allocator: every `palloc` charges the
`CurrentMemoryContext`, and resetting or deleting a context frees all its
chunks at once — how PostgreSQL avoids per-allocation leak tracking. Contexts
nest (TopMemoryContext → per-query → per-tuple) so cleanup scopes to the right
lifetime. [from-comment] (via `knowledge/idioms/memory-contexts.md`).



### MemoryContextAlloc
The base allocator that requests a chunk from a specific MemoryContext rather than CurrentMemoryContext; palloc is the common wrapper that targets CurrentMemoryContext, and variants add zeroing, huge-size, or no-OOM-error behavior. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemoryContextAllocAligned
Allocates a chunk guaranteed to start on a requested power-of-two alignment by
over-allocating and embedding a redirection header, so the returned pointer
still frees correctly via the normal chunk machinery. [verified-by-code]
(`mcxt.c:1485-1591` — via
`knowledge/files/src/backend/utils/mmgr/alignedalloc.c.md`).



### MemoryContextAllocationFailure
The shared helper every memory-context allocator calls when its underlying `malloc()` returns NULL. Its behavior depends on the allocation flags: with `MCXT_ALLOC_NO_OOM` it returns NULL, otherwise it raises the out-of-memory `ereport(ERROR)`. This is the mechanism behind the "palloc never returns NULL" contract — the allocators tail-call it so the success path stays a cheap inline. [verified-by-code] (`mcxt.c:1200-1214` — via `knowledge/files/src/include/utils/memutils_internal.h.md`).



### memorycontextallochuge
The allocation entry that bypasses the regular `MaxAllocSize` (1 GB − 1) cap, allowing very large single allocations (e.g. big sort / hash arrays). [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### MemoryContextCallback
A function+arg cell registered on a `MemoryContext` to run when that context is
reset or deleted, the idiom for tying resource cleanup (e.g. closing a file or
tuplestore) to a context's lifetime. [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### memorycontextcounters
The struct (`nblocks` / `freechunks` / `totalspace` / `freespace`) that `MemoryContextMemConsumed` (`mcxt.c:838`) fills by walking a context subtree; the basis of `MemoryContextStats` output. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### MemoryContextCreate
The low-level constructor that initialises a new memory-context node of a
given method type and links it under a parent; allocator-specific creators
such as `AllocSetContextCreate` call it. [verified-by-code]
(`memutils_internal.h:148-158` — via
`knowledge/files/src/include/utils/memutils_internal.h.md`).



### MemoryContextData
The common header every memory context node begins with — method id,
parent/child/sibling links, name, and reset/delete callback — that the
concrete allocators (`AllocSetContext` etc.) extend. [verified-by-code]
(`aset.c:158-171` — via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### MemoryContextDelete
Frees a memory context and all its children in one shot, releasing every
allocation made in them without per-chunk `pfree`s — the workhorse of PG's
region-based memory discipline. Tearing down a per-function or per-query context
(e.g. plpgsql's `func->fn_cxt`) reclaims all its palloc'd state at once.
[verified-by-code] (via
`knowledge/files/src/pl/plpgsql/src/pl_funcs.md`).



### MemoryContextInit
The startup routine that creates the bootstrap memory contexts; per its own comment only `TopMemoryContext` and `ErrorContext` are initialized here, while every other context is created later by its owning subsystem. [from-comment] (`memutils.h:53-57` — via `knowledge/files/src/include/utils/memutils.h.md`).



### MemoryContextMemAllocated
Walks a memory context (optionally including its children) and returns the total bytes the allocator has obtained from `malloc`; the executor uses it for memory accounting and `work_mem` spill decisions. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemoryContextMethodID
The small enum tag stored in a memory chunk's header identifying which
allocator (AllocSet/Slab/Generation/Bump) owns it, so `pfree`/`repalloc` can
dispatch to the right method without a context pointer. [verified-by-code]
(`memutils_internal.h:107-147` — via
`knowledge/files/src/include/utils/memutils_memorychunk.h.md`).



### MemoryContextMethods
The per-allocator-type method vtable (declared in `memnodes.h`) that every `MemoryContextData` points at via its `methods` field; `mcxt.c`'s public API dispatches through it to the concrete allocator (AllocSet, Slab, Generation, Bump). It is a 10-entry function table: `alloc`, `free_p`, `realloc`, `reset`, `delete_context`, `get_chunk_context`, `get_chunk_space`, `is_empty`, `stats`, and (assert-only) `check`, wired into the `mcxt_methods[]` array indexed by `MemoryContextMethodID`. [verified-by-code] (`memnodes.h:58` — via `knowledge/files/src/include/nodes/memnodes.h.md`).



### MemoryContextRegisterResetCallback
Registers a `MemoryContextCallback` to run when a context is reset or deleted —
the canonical way to attach resource cleanup (closing handles, freeing external
state) to a context's lifetime. [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### MemoryContextReset
Frees all allocations made in a memory context (and resets it for reuse)
without destroying the context object itself — the cheap bulk-free that makes
per-tuple and per-call scratch contexts practical. Caches that rebuild from
scratch, like sepgsql's userspace AVC, reset their context rather than
`pfree`-ing entries one by one. [verified-by-code] (`uavc.c:78-86` — via
`knowledge/files/contrib/sepgsql/uavc.c.md`).



### memorycontextresetchildren
Resets every child of a context without deleting the context itself; part of the hierarchical reset/delete API where resetting a parent by default also frees the children's memory. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### MemoryContextResetOnly
Resets a single memory context — freeing its allocations and returning blocks to the malloc layer or keeping one keeper block — without recursing into child contexts, the primitive that `MemoryContextReset` builds on. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/tuplesort.c.md`).



### MemoryContextSetIdentifier
A memory-context API (`mcxt.c:664`) that attaches a dynamic, human-readable identifier string to an already-created context. Because the static context name passed to `*ContextCreate` must be a compile-time constant, this is the idiomatic way to add the variable part (e.g. a relation or plan name) that shows up in memory-context dumps. [verified-by-code] (`mcxt.c` — via `knowledge/idioms/memory-contexts.md`).



### MemoryContextSetParent
Re-parents a memory context, unlinking it from its old parent's child list and splicing it under a new one, the reparenting primitive used to hand a subtree's lifetime to a longer-lived context (e.g. caching a just-built expression). [verified-by-code] (`mcxt.c` — via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemoryContextStats
The mcxt.c routine (`mcxt.c:866`) that walks a context subtree and logs per-context allocation totals; the engine behind backend memory-context dumps and `pg_log_backend_memory_contexts`. [verified-by-code] (`mcxt.c:866` — via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemoryContextStrdup
The palloc-family helper that copies a NUL-terminated string into a *specified* memory context (rather than `CurrentMemoryContext`, which is what `pstrdup` uses). [verified-by-code] (via `knowledge/files/src/include/utils/palloc.h.md`).



### MemoryContextSwitchTo
The inline that sets `CurrentMemoryContext` to a given context and returns the
previous one. The idiom is "switch, allocate, switch back" using the saved
return value; it is the single discipline that keeps allocations in the right
lifetime bucket. [verified-by-code] (via
`knowledge/idioms/memory-contexts.md`).



### MemoryContextTraverseNext
The non-recursive pre-order descendant walker (mcxt.c) that MemoryContextReset/Stats/Check use to traverse a context subtree without stack recursion; it returns NULL when it climbs back up through the top context. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### MemSet
PostgreSQL's optimized `memset` macro that special-cases zeroing aligned,
word-multiple regions into a long-word store loop; the basis of `palloc0` and
struct zeroing in hot paths. [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### memutils_internal
The private memory-manager header (`src/include/utils/memutils_internal.h`) that declares the per-allocator `MemoryContextMethods` callback vectors — the `AllocSet*` / `Generation*` / `Slab*` alloc/free/realloc/reset functions — shared between `mcxt.c`'s dispatch layer and the concrete allocators. It is the seam that makes MemoryContext a pluggable interface. [verified-by-code] (`memutils_internal.h:38-53` — via `knowledge/files/src/backend/utils/mmgr/generation.c.md`).



### MERGE
The SQL `MERGE` command (SQL:2003) that applies `INSERT`/`UPDATE`/`DELETE`/`DO NOTHING` actions to a target table based on per-row `WHEN MATCHED`/`WHEN NOT MATCHED` conditions against a source. It is executed by `nodeModifyTable.c`, which evaluates the match conditions and dispatches the chosen merge action per tuple. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeModifyTable.c.md`).



### MergeAppend
The order-preserving sibling of `Append`: it merges the already-sorted outputs
of its child subplans (e.g. partitions each with a matching index order) into
one sorted stream, avoiding a top-level Sort. [verified-by-code] (via
`knowledge/files/src/backend/executor/execProcnode.c.md`).



### MergeJoin
The executor node that joins two inputs already sorted on the join key by advancing through both in lockstep; efficient when the inputs are pre-sorted (or cheaply sortable) and the join is an equality or range condition. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### MessageContext
The per-client-message memory context: it is reset at the top of each
protocol message in `PostgresMain`, so parse/analyze/plan allocations for one
command are reclaimed before the next, without per-allocation `pfree`.
[verified-by-code] (`mcxt.c:161` — via `knowledge/subsystems/utils-mmgr.md`).



### MinimalTuple
A stripped heap-tuple form used for executor-internal tuples (sorts, hashes,
tuplestores) that drops the system columns a stored row needs. Its layout
deliberately overlaps `HeapTupleHeaderData` below `t_infomask2` so the two can
be cast to share accessor code. [from-comment] (`htup_details.h:3-13` — via
`knowledge/files/src/include/access/htup_details.h.md`).



### minmsgnum
`minMsgNum` is the minimum `maxMsgNum` across all backends' `ProcState` entries, computed to decide which already-consumed sinval messages can be discarded from the ring. [verified-by-code] (`sinvaladt.c:148-154` — via `knowledge/architecture/process-model.md`).



### missing_ok
A widespread boolean-parameter convention: when true, a lookup that fails to find its object returns a sentinel (NULL/`InvalidOid`) instead of raising an error — e.g. `IndexGetRelation(indrelid, true)`. Lets callers probe for existence without `PG_TRY`. [inferred] (via `knowledge/files/contrib/amcheck/verify_common.md`).



### mm_strdup
The ECPG preprocessor's checked `strdup` (paired with `mm_alloc`), an arena-style allocator with an OOM-fatal contract: it never returns NULL — on allocation failure it calls `mmfatal` and aborts the preprocessor run. [verified-by-code] (`util.c:96` — via `knowledge/files/src/interfaces/ecpg/preproc/util.c.md`).



### ModifyTable
The executor plan node that performs `INSERT` / `UPDATE` / `DELETE` / `MERGE`,
driving the per-row table-AM and trigger machinery via
`ExecForeignInsert/Update/Delete` for foreign targets. postgres_fdw can bypass
it entirely with "direct modify", emitting the remote UPDATE/DELETE straight
from a single ForeignScan when all SET clauses are shippable and there are no
local quals. [verified-by-code]
(via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### module_pathname
The placeholder token in an extension's `.control` file that the SQL install script's `MODULE_PATHNAME` macro expands to the extension's loadable-library path, so `CREATE FUNCTION ... AS 'MODULE_PATHNAME'` need not hard-code the `.so` name. The build substitutes it. [inferred] (via `knowledge/scenarios/add-new-extension.md`).



### msgnum
`MsgNum` is the monotonically increasing sequence number of a shared-invalidation message; values are translated modulo the ring size (a power of two) to locate the slot. [verified-by-code] (via `knowledge/idioms/sinvaladt-broadcast.md`).



### msgnumlock
`msgnumLock` is the sinval spinlock used in a spinlock-as-memory-barrier idiom to publish `maxMsgNum` updates to shared-mode readers without a full LWLock. [verified-by-code] (via `knowledge/subsystems/storage-ipc.md`).



### MSGNUMWRAPAROUND
The sinval message-number wraparound period: when `maxMsgNum` exceeds it, the writer subtracts `MSGNUMWRAPAROUND` from every backend's `MsgNum` counter at once; it is a multiple of `MAXNUMMESSAGES` so ring indexing stays consistent. [verified-by-code] (via `knowledge/idioms/sinvaladt-broadcast.md`).



### MSVC
Microsoft Visual C — the Windows compiler toolchain PostgreSQL supports alongside GCC/Clang. Portability headers under `src/include/port` provide MSVC-specific intrinsics (e.g. atomic operations in `generic-msvc.h`) where the compiler lacks the GCC builtins used elsewhere. [verified-by-code] (via `knowledge/files/src/include/port/atomics/generic-msvc.h.md`).



### mul_size
Overflow-checked size multiplication that `ereport(ERROR)`s on overflow; paired with `add_size`. Used when computing an allocation size from counts that could conceivably overflow `Size`. [verified-by-code] (`palloc.h` — via `knowledge/files/src/include/utils/palloc.h.md`).



### multi_call_memory_ctx
The longer-lived memory context a set-returning function uses across its value-per-call invocations (set up via `SRF_FIRSTCALL_INIT` / `funcctx`); state allocated here survives between calls and is reset when the SRF finishes, triggering any registered cleanup callback. [from-comment] (via `knowledge/files/src/pl/plpython/plpy_exec.md`).



### MultiExec
The executor path for nodes that return a whole materialized result at once instead of tuple-at-a-time; `MultiExecProcNode` dispatches to e.g. `MultiExecBitmapIndexScan`/`MultiExecHash`, which hand back a bitmap or hash table. [from-comment] (via `knowledge/files/src/backend/executor/nodeBitmapIndexscan.c.md`).



### MultiExecProcNode
The bulk-result executor dispatch (parallel to `ExecProcNode`) used by nodes
that hand up an entire materialized result at once — e.g. a bitmap or a hash
table — rather than one tuple per call. [verified-by-code] (via
`knowledge/subsystems/executor.md`).



### MultiXact
A "multiple transaction" id used as a tuple's `xmax` when several transactions
hold a shared lock (or a mix of share/update locks) on the same row at once. The
visibility code resolves the real updater lazily via `HeapTupleGetUpdateXid`,
which may force MultiXact SLRU I/O, so it only does so after the cheaper
infomask-only checks fail. [verified-by-code]
(`heapam_visibility.c:1173-1176` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MULTIXACT_OFFSETS_PER_PAGE
The number of multixact-offset entries stored per SLRU page of `pg_multixact/offsets`; it fixes the page/segment layout the multixact SLRU addresses. [inferred] (via `knowledge/files/src/bin/pg_upgrade/multixact_read_v18.c.md`).



### MultiXactGenLock
The LWLock that serialises advancement of the shared MultiXact id / offset counters; it is taken (often in SHARED mode) when allocating a new MultiXactId or reading the generator state. [verified-by-code] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactId
An identifier for a set of transactions that simultaneously hold a lock on one row; when more than one transaction locks a tuple (e.g. FOR SHARE) the tuple's xmax stores a MultiXactId resolving to the member list, tracked by the multixact SLRUs. [verified-by-code] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactId (multixact)
An identifier standing in for a *set* of transactions that simultaneously hold
a row lock (e.g. several `SELECT ... FOR SHARE`), stored in a tuple's xmax when
more than one locker is involved. Members and offsets live in dedicated SLRUs
under `pg_multixact/`. [from-comment] (via
`knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactMember
One entry in a multixact's member array: a `TransactionId` plus status flag bits encoding the lock/update strength that transaction holds on a shared-locked row. The member arrays live in the pg_multixact "members" SLRU. [from-comment] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactOffset
The 32-bit index type into the pg_multixact "members" SLRU; each `MultiXactId` maps to an offset marking where its `MultiXactMember` array begins. [verified-by-code] (via `knowledge/files/src/backend/access/transam/multixact.c.md`).



### MultiXactStatus
The per-member lock-strength code stored in a MultiXact (e.g.
`ForKeyShare`, `ForShare`, `ForUpdate`, `NoKeyUpdate`, `Update`), letting a
single `xmax` represent several lockers with different modes. [verified-by-code]
(via `knowledge/idioms/multixact-slru.md`).



### MVCC
Multi-Version Concurrency Control — PostgreSQL keeps multiple row versions and uses per-tuple xmin/xmax plus a snapshot to decide which version each transaction sees, so readers never block writers or vice versa; the decision lives in the heapam visibility routines. [verified-by-code] (`heapam_visibility.c:6` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MVCC (multiversion concurrency control)
PostgreSQL's concurrency model: each row version (tuple) carries `xmin`/`xmax`
transaction stamps, and a snapshot decides which versions a query may see, so
readers never block writers. The visibility logic lives in routines like
`HeapTupleSatisfiesMVCC`, which test a tuple's xmin/xmax against the snapshot.
[verified-by-code] (`heapam_visibility.c:938` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### MXID
A MultiXactId — an identifier standing in for a *set* of transactions, used when several transactions hold a shared row lock (or a mix of share/update locks) on the same tuple simultaneously. Like XIDs, MXIDs are 32-bit and subject to wraparound, so they have their own freeze/vacuum horizon; the membership lives in the `pg_multixact` SLRU. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### my_exec_path
The absolute path of the currently running executable, resolved by `find_my_exec` at startup; front-end tools like `pg_config` pass it to `get_configdata` to locate the installation's build-relative directories. [verified-by-code] (via `knowledge/files/src/common/config_info.c.md`).



### my_level
The current subtransaction nesting level stamped onto stacked state such as `TransInvalidationInfo` and the AFTER-trigger frame, so that on subxact abort the right frame's invalidation messages / trigger events can be discarded. [verified-by-code] (`inval.c:48` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### MyBackendType
The global recording the current process's backend type (e.g. `B_STANDALONE_BACKEND`), whose storage lives in `miscinit.c`; `GetBackendTypeDesc` translates the enum to a description string via the proctype x-macro list. It is set during process startup, for instance by `InitStandaloneProcess`. [verified-by-code] (`miscinit.c` — via `knowledge/files/src/backend/utils/init/miscinit.c.md`).



### MyBgworkerEntry
The current background worker's own `BackgroundWorker` entry, from which a worker reads the arguments the registrant packed — e.g. `MyBgworkerEntry->bgw_extra` for the payload and `->bgw_notify_pid` to signal the registrant back. [verified-by-code] (via `knowledge/files/src/test/modules/worker_spi/worker_spi.c.md`).



### MyClientConnectionInfo
The backend global holding this session's `ClientConnectionInfo` (authenticated identity `authn_id` + auth method); `miscinit.c` serializes it into parallel workers via `SerializeClientConnectionInfo` / `RestoreClientConnectionInfo`. [verified-by-code] (via `knowledge/files/src/backend/utils/init/miscinit.c.md`).



### MyDatabaseId
The global holding the OID of the database the current backend is connected to, set during InitPostgres once the backend latches onto a database; most catalog lookups are implicitly scoped by it. [verified-by-code] (`postinit.c:707` — via `knowledge/files/src/backend/utils/init/postinit.c.md`).



### MyLatch
The current process's own latch — the one it sleeps on in
`WaitLatch(MyLatch, ...)`. Condition variables wake a waiter via
`SetLatch(waiter->procLatch)` rather than a semaphore, which is exactly what
makes CV waits interruptible (they honour `WL_TIMEOUT` and integrate with
`CHECK_FOR_INTERRUPTS()`), unlike LWLock waits. [verified-by-code] (via
`knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### MyProc
The global pointer to the current backend's own `PGPROC` slot in shared
memory, valid for the life of the process. Through it a backend exposes its
`xid`/`xmin`, wait state, and latch to the rest of the system (snapshots, lock
manager, `pg_stat_activity`). [verified-by-code] (via
`knowledge/data-structures/pgproc-fields.md`).



### MyProcNumber
The current backend's index into the shared PGPROC array (its ProcNumber) — a small dense integer used to address per-backend shared-state slots (fast-path locks, the sinval queue, ProcSignal) without a pointer. [verified-by-code] (via `knowledge/files/src/backend/utils/init/globals.c.md`).



### MyProcPid
The cached process id (getpid()) of the current backend, set at startup and reused in log lines, cancel-key checks, and lock/lwlock owner bookkeeping instead of calling getpid() repeatedly. [verified-by-code] (`csvlog.c:69` — via `knowledge/files/src/backend/utils/error/csvlog.c.md`).



### MyProcPort
The Port struct for the current backend's client connection — socket, remote/local addresses, negotiated protocol/auth state, GSS/SSL info, and startup-packet parameters; the backend reads client identity from it. [verified-by-code] (`backend_startup.c:177` — via `knowledge/subsystems/tcop.md`).



### NameData
The fixed-width catalog name type: a struct wrapping `char data[NAMEDATALEN]`
(64 bytes), used for identifier columns like `relname`/`proname` so they sit at
fixed offsets in a catalog row rather than as variable-length text.
[inferred] (via `knowledge/idioms/catalog-conventions.md`).



### NAMEDATALEN
The compile-time limit (default 64, so 63 usable bytes) on the length of any
SQL identifier stored in `name`-typed catalog columns; identifiers longer than
this are truncated. [verified-by-code] (via
`knowledge/files/contrib/postgres_fdw/option.c.md`).



### NameStr
Macro yielding a `char *` view of a fixed-width `Name` (NAMEDATALEN) field; the read accessor for catalog `name`-typed columns, the counterpart of `namestrcpy` on the write side. [from-comment] (via `knowledge/files/src/pl/plpython/plpy_procedure.md`).



### namestrcpy
Copies a C string into a fixed-width `Name` (NAMEDATALEN) field, zero-padding the remainder; the safe way to set a catalog `name`-typed column. [verified-by-code] (`name.c:233` — via `knowledge/files/src/backend/utils/adt/name.c.md`).



### NBuffers
The global giving the number of pages in the shared buffer pool — i.e. `shared_buffers` measured in 8 KB blocks. It bounds the `BufferDescriptors`/`BufferBlocks` arrays and many bulk-operation ring sizes. [inferred] (`buf_init.c:24` — via `knowledge/subsystems/storage-buffer.md`).



### NEGOTIATE_GSS_CODE
The magic protocol code `PG_PROTOCOL(1234,5680)` carried by a `GSSENCRequest`, telling the backend to negotiate GSSAPI encryption before the StartupMessage. [verified-by-code] (`pqcomm.h:129` — via `knowledge/docs-distilled/gssapi-enc.md`).



### NEGOTIATE_SSL_CODE
The magic protocol code `PG_PROTOCOL(1234,5679)` carried by an `SSLRequest`; the backend answers a single `'S'` (start TLS) or `'N'` (plaintext) byte before any StartupMessage. [verified-by-code] (`pqcomm.h:128` — via `knowledge/docs-distilled/ssl-tcp.md`).



### NegotiateProtocolVersion
The startup-path mechanism by which the server, on receiving a StartupMessage requesting a newer wire protocol minor version or unknown `_pq_.` protocol extension parameters, replies with a NegotiateProtocolVersion message stating the highest version it supports and listing unrecognized parameters. In the backend it is sent via `SendNegotiateProtocolVersion` from `backend_startup.c`. [verified-by-code] (`backend_startup.c` — via `knowledge/files/src/backend/tcop/backend_startup.c.md`).



### NestLoop
The nested-loop join plan node: for each outer-side row it scans (or re-scans)
the inner side, optionally passing the outer row's values down as
`NestLoopParam`s to drive a parameterized inner index scan. [verified-by-code]
(`plannodes.h:1006` — via
`knowledge/files/src/include/nodes/plannodes.h.md`).



### new_bucket
The hash-index bucket-split field (WAL record `xl_hash_split_allocate_page`) naming the newly-allocated higher-numbered bucket; a split moves tuples from `old_bucket` to `new_bucket`, with buffer 0 = old primary, 1 = new primary, 2 = metapage. [verified-by-code] (via `knowledge/idioms/hash-bucket-split.md`).



### new_cluster
pg_upgrade's `ClusterInfo` for the destination installation; the tool freezes its catalogs, transfers or links relation files keyed by the old/new relfilenode maps, and verifies its version and settings are upgrade-compatible with `old_cluster`. The pair is the core of the upgrade state. [inferred] (via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md`).



### NewGUCNestLevel
The call that opens a fresh GUC nesting level and returns its handle; code that must temporarily force settings pushes a level, applies overrides, and later passes the handle to `AtEOXact_GUC` to unwind exactly those overrides (used by postgres_fdw's deparse to force `datestyle=ISO` etc.). [verified-by-code] (`postgres_fdw.c:4108` — via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### NewRelfrozenXid
VACUUM's running candidate for the relation's new `relfrozenxid`, initialized
to `OldestXmin` and ratcheted up as the heap scan observes the oldest unfrozen
xid actually left on each page; the final value is written to `pg_class` at
cleanup. [verified-by-code] (via `knowledge/idioms/vacuum-two-pass-heap.md`).



### nextBlockSize
The `AllocSet` field holding the size of the next block the context will malloc; it grows geometrically from `initBlockSize` toward `maxBlockSize`, amortising allocation overhead for long-lived contexts. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/aset.c.md`).



### nextMsgNum
The per-backend `ProcState` cursor into the shared sinval message ring recording the next invalidation message this backend must still read; the gap to the writer's `maxMsgNum` is that backend's unconsumed backlog. [verified-by-code] (via `knowledge/idioms/sinvaladt-broadcast.md`).



### NextRecordTypmod
The backend-local counter that assigns the next typmod to a newly-seen anonymous
record (`RECORD`) row type, indexing it into the `RecordCacheArray`.
[verified-by-code] (via
`knowledge/idioms/typcache-record-typmod-and-shared.md`).



### NextSampleBlock
The TABLESAMPLE method callback that returns the next heap block number to
sample for a scan (or `InvalidBlockNumber` when done); the system methods cache
state across calls so the choice is stable within one scan. `tsm_system_time`
computes it from elapsed time rather than a row target.
[verified-by-code] (via
`knowledge/files/contrib/tsm_system_time/tsm_system_time.c.md`).



### NextSampleTuple
A mandatory `TsmRoutine` (TABLESAMPLE method) callback (in `tsmapi.h`) that picks the next tuple offset within the current block for the sampling executor node. Together with the also-mandatory `BeginSampleScan`, it returns block/offset numbers that the executor uses to directly fetch heap pages, so a buggy TSM extension can mis-direct those fetches. [verified-by-code] (`tsmapi.h` — via `knowledge/files/src/include/access/tsmapi.h.md`).



### nextVictimBuffer
The atomic clock hand in `BufferStrategyControl` that `ClockSweepTick` advances (fetch-add modulo NBuffers) to pick the next candidate for eviction; there is no real freelist, buffers are chosen by sweeping. [verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### nextXid
The next transaction id to be assigned, held as a `FullTransactionId` in shared memory (`TransamVariables`/`ShmemVariableCache`) and advanced under `XidGenLock`. Recovery restores it from the checkpoint and replayed records so post-crash xid assignment continues correctly. [inferred] (`xlogrecovery.c:1897` — via `knowledge/subsystems/access-transam.md`).



### Node
The tagged-union base of nearly every PostgreSQL tree structure: each node
begins with a `NodeTag` so generic code can dispatch on type via `IsA()` and
the auto-generated copy/equal/out/read functions. Parse trees, plan trees, and
most internal structures are Node trees. [from-comment] (via
`knowledge/files/src/include/nodes/nodes.h.md`).



### nodeAgg
`src/backend/executor/nodeAgg.c` — the Agg executor node implementing both plain/sorted aggregation and HashAgg, including grouping sets, `DISTINCT`/`ORDER BY` inside aggregates, partial/finalize aggregation for parallel query, and the spill-to-disk path when a hash table exceeds `work_mem` (`hash_agg_enter_spill_mode`). [verified-by-code] (via `knowledge/files/src/backend/executor/nodeAgg.c.md`).



### nodeFuncs
`src/backend/nodes/nodeFuncs.c` — generic helpers over expression `Node`s: `expression_tree_walker` / `expression_tree_mutator` (the recursion engines most planner passes build on), `exprType` / `exprTypmod` / `exprCollation`, and `exprLocation`. Distinct from the auto-generated copy/equal/out/read functions; these are the hand-written tree-traversal utilities. [verified-by-code] (via `knowledge/files/src/backend/nodes/nodeFuncs.c.md`).



### nodeRead
The node-tree deserializer (`readfuncs.c`) that reconstructs a Node from its `outfuncs.c` text form — used to ship plan trees to parallel workers and to read stored rules/views back from the catalog. [verified-by-code] (via `knowledge/files/src/backend/nodes/readfuncs.c.md`).



### NodeTag
The integer enum stamped as the first field of every `Node` so the copy/equal/
out/read machinery and `IsA()` can recognize a node's concrete type at runtime.
Tags are generated for core nodes; extensions reuse `T_ExtensibleNode` plus a
registered name. [verified-by-code] (`extensible.h:32` — via
`knowledge/files/src/backend/nodes/extensible.c.md`).



### nodeToString
Serializes any Node tree into the parenthesized textual representation used to store rules/views in the catalog and to ship plans to parallel workers; `stringToNode` is the inverse. Both are generated by `gen_node_support.pl`. [inferred] (via `knowledge/files/src/backend/nodes/outfuncs.c.md`).



### noError
The soft-error flag passed to lookup helpers (e.g. composite-type resolution in hstore); when true the callee returns a failure indication instead of `ereport`-ing, letting the caller handle a dropped/renamed dependency gracefully. [verified-by-code] (`hstore_op.c:351` — via `knowledge/files/contrib/hstore/hstore_op.c.md`).



### NoLock
The lock-mode sentinel (value 0) meaning "take no heavyweight lock"; passed to relation_open / table_open when the caller already holds a suitable lock, so the open just builds the relcache entry without re-locking. [verified-by-code] (`relation.c:65` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### NoticeResponse
A backend-to-frontend wire-protocol message (type byte `'N'`) carrying a non-error notice. It shares its on-the-wire format with `ErrorResponse` — a sequence of single-byte-coded fields terminated by a zero byte — differing only in severity. [from-README] (`protocol-message-formats.md` — via `knowledge/docs-distilled/protocol-message-formats.md`).



### null_index
In `PartitionBoundInfo`, the array index of the list partition that accepts NULL (or `-1` if none); the NULL-handling counterpart to `default_index`. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### NullableDatum
A compact `{ Datum value; bool isnull; }` struct used to carry a
possibly-NULL value as one unit — notably the per-argument storage inside
`FunctionCallInfo`. [verified-by-code] (via `knowledge/idioms/fmgr.md`).



### NUM_BUFFER_PARTITIONS
The fixed number (128) of partitions the shared buffer-mapping hash table is
divided into, each guarded by its own `BufMappingLock`, so lookups in
different partitions don't contend. [verified-by-code] (via
`knowledge/subsystems/storage-lmgr.md`).



### NUM_FULL_OFFSETS
The inline-offset capacity of a vacuum `BlocktableEntry` in the TID store, defined as `(sizeof(uintptr_t) - sizeof(uint8) - sizeof(int8)) / sizeof(OffsetNumber)` (4 on 64-bit, 2 on 32-bit). When a page has at most `NUM_FULL_OFFSETS` dead offsets they are stored directly in the entry's `full_offsets[]` array (inline mode, `nwords == 0`); exceeding it flips the entry to an allocated per-block bitmap, avoiding bitmap-allocation overhead for the common sparsely-dead page. [verified-by-code] (`tidstore.c.md` — via `knowledge/files/src/backend/access/common/tidstore.c.md`).



### NUM_INDIVIDUAL_LWLOCKS
The count of named, individually-declared LWLocks (enumerated in `lwlocklist.h`) that occupy the first fixed slots of the main LWLock array before the dynamically-assigned tranches. [verified-by-code] (via `knowledge/files/src/include/storage/lwlock.h.md`).



### NUM_LOCK_PARTITIONS
The fixed number (16) of partitions the heavyweight-lock shared hash table is
split into, each with its own LWLock, to spread contention. A backend needing
more than one partition lock must take them in partition-number order — a
deadlock-avoidance rule enforced in `CheckDeadLock`. [from-README] (via
`knowledge/files/src/backend/storage/lmgr/README.md`).



### NUM_XLOGINSERT_LOCKS
The number (8) of WAL insertion locks that let backends reserve WAL space concurrently; a record holds one insertion lock while copying its bytes into the WAL buffers. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### NUMA
Non-Uniform Memory Access — a multi-socket memory architecture where a core's access latency depends on which node owns the page. PG18 surfaces NUMA awareness through `pg_buffercache_numa` and `pg_shmem_allocations_numa`, which report the NUMA node backing each shared-buffer / shmem allocation so DBAs can diagnose cross-node traffic. [verified-by-code] (via `knowledge/files/contrib/pg_buffercache/pg_buffercache_pages.c.md`).



### numeric_in
The input function for the `numeric` type: it parses a decimal string into the packed variable-precision `Numeric` representation and rejects non-finite spellings such as NaN/inf where the caller forbids them. [verified-by-code] (via `knowledge/files/contrib/jsonb_plpython/jsonb_plpython.c.md`).



### NumericDigit
A base-10000 limb (`int16`) of the arbitrary-precision `numeric` type; the
digit array plus a weight and dscale form the variable-length on-disk
representation. [verified-by-code] (via
`knowledge/data-structures/numeric-type.md`).



### NumericVar
The unpacked, working representation of a `numeric` value (sign, weight, dscale,
and a `NumericDigit` array) that arithmetic routines operate on before packing
back to the varlena form. [verified-by-code] (via
`knowledge/data-structures/numeric-type.md`).



### numOR
In ltree's `parse_lquery`, the total count of `|` alternation operators in the whole query; each level's variant scratch array is over-allocated to `numOR + 1` items — wasteful but bounded by `PG_UINT16_MAX`. [verified-by-code] (`ltree_io.c:322` — via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### nworkers_launched
The field of `ParallelContext` reporting how many parallel workers actually started, which can be fewer than requested when `max_worker_processes` is exhausted. The leader must cope with the shortfall and may run the plan itself. [inferred] (via `knowledge/idioms/parallel-worker-launch-wait-and-errors.md`).



### O_NOFOLLOW
The open(2) flag that makes the call fail if the final path component is a symbolic link, used as a TOCTOU/symlink-attack defense when a privileged process opens a path an unprivileged user could influence. Several server-side file paths (file_fdw, the COPY path it shims, pg_rewind targets) have been flagged in corpus issues for *not* setting it. [inferred] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### OAT_FUNCTION_EXECUTE
An object-access-hook event fired just before a function is executed, giving an extension (such as `sepgsql`) a point at which to enforce an access-control policy. [verified-by-code] (via `knowledge/files/contrib/sepgsql/proc.c.md`).



### OAT_POST_CREATE
One member of the `ObjectAccessType` enum in objectaccess.h (alongside `OAT_DROP`, `OAT_POST_ALTER`, `OAT_NAMESPACE_SEARCH`, `OAT_FUNCTION_EXECUTE`, `OAT_TRUNCATE`) identifying the post-creation object-access event. It is fired through `InvokeObjectPostCreateHook[Arg]` (guarded by `object_access_hook != NULL`) and consumed by extensions such as sepgsql, which dispatch on the `classId` (e.g. `RelationRelationId` with subId 0 vs. >0 for table vs. column creation). [verified-by-code] (`objectaccess.h.md` — via `knowledge/files/src/include/catalog/objectaccess.h.md`).



### object_access_hook
The centralized callback in `objectaccess.h` that security / audit modules (e.g. sepgsql) install to be notified of catalog-object events — post-create, drop, truncate, post-alter, namespace-search, function-execute — dispatched from `objectaccess.c`. [verified-by-code] (via `knowledge/files/src/backend/catalog/objectaccess.c.md`).



### ObjectAddress
The canonical triple `(classId, objectId, objectSubId)` that uniquely names
any database object — the currency of dependency tracking, `ALTER`/`COMMENT`/
`SECURITY LABEL` routing, and DDL event collection. `objectSubId` distinguishes
a column from its table; functions returning the object they just created hand
back an `ObjectAddress`. [verified-by-code] (via
`knowledge/files/src/include/tcop/deparse_utility.h.md`).



### ObjectIdGetDatum
Macro packing an OID into a `Datum`; the `*GetDatum` member for `Oid`, used when passing a relation/type/proc OID to fmgr or syscache lookups. [verified-by-code] (via `knowledge/files/contrib/spi/moddatetime.c.md`).



### OffsetNumber
The 1-based index of a line pointer within a page (the second half of an
`ItemPointer`/TID). `FirstOffsetNumber` is 1; `InvalidOffsetNumber` is 0.
[verified-by-code] (`htup_details.h:86` — via
`knowledge/subsystems/access-heap.md`).



### Oid (object identifier)
The unsigned 32-bit type that names every catalog object (relations, types,
functions, operators, …); a value of `InvalidOid` (0) means "none". OIDs are
assigned from a global counter, with a reserved low range hand-assigned to
built-in objects. [inferred] (via `knowledge/idioms/catalog-conventions.md`).



### OidFunctionCall1
Looks up a function by OID and calls it with one argument in a single step (an fmgr_info + FunctionCall1 combination); used for handler functions like a tablesample method's, where the OID is known but not the symbol. [verified-by-code] (via `knowledge/files/src/backend/access/tablesample/tablesample.c.md`).



### OidIsValid
The trivial macro testing that an `Oid` is not `InvalidOid` (0); the ubiquitous
guard before using a catalog OID returned from a lookup. [verified-by-code] (via
`knowledge/idioms/catalog-conventions.md`).



### OidOutputFunctionCall
Calls a type's output function (looked up by the output-proc OID) to render a Datum as a `char *`; the generic "Datum to text" step after `getTypeOutputInfo`. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### old_cluster
The global `ClusterInfo` struct in pg_upgrade describing the source installation — its bindir, data directory, port, controldata, and per-database relation maps. Nearly every upgrade check compares fields of `old_cluster` against `new_cluster`. [inferred] (via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md`).



### OldestXmin
The computed horizon xid below which no running transaction can still see a given table's dead tuples; vacuum and HOT pruning use it to decide what is removable. [from-comment] (via `knowledge/community/user-questions/2026-06-02.md`).



### OldestXminType
A compatibility macro (used by forks such as pg_dirtyread) that straddles the PG 14 visibility-API change, resolving to either a plain `TransactionId` (older API) or a `GlobalVisState *` (newer), so one code path can hold whichever horizon representation `GetOldestXmin` / `GlobalVisTestFor` yields on the build's major version. [verified-by-code `dirtyread_tupconvert.h:20-24`] (via `knowledge/ideologies/pg_dirtyread.md`).



### on_dsm_detach
The API that registers a callback to run when a dynamic shared memory segment detaches (or the backend exits while attached); e.g. `pqmq.c` registers `pq_cleanup_redirect_to_shm_mq` so a parallel worker's protocol redirection is torn down when its DSM goes away. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqmq.c.md`).



### on_proc_exit
One of ipc.c's three callback registries (with `on_shmem_exit` and `before_shmem_exit`): functions registered here run, in LIFO order, during a normal backend exit, used for cleanup that must happen on the way down. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/ipc.c.md`).



### on_shmem_exit
Registers a callback to run during normal backend shutdown after the shared-memory teardown phase begins; the lifecycle complement of `before_shmem_exit`, used to release shared resources. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc` ipc docs).



### OOM
Out Of Memory — the condition where an allocation cannot be satisfied. In the backend, `palloc` failure raises an `ERROR` (longjmp) rather than returning NULL, so callers need not null-check; the OS OOM killer terminating the postmaster or a backend is a separate, harsher failure mode that crash recovery must handle. [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### opcdefault
The `pg_opclass` boolean column marking an operator class as the default for its data type, so `CREATE INDEX` selects it automatically unless a non-default opclass is named explicitly. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### opcintype
The `pg_opclass` column giving the data type an operator class is for; together with `opcmethod` (the access method) it keys each class to a (AM, type) pair. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### opclass (operator class)
A catalog object (`pg_opclass`) binding a data type to an index access method
by naming the operators and support functions an index needs (e.g. btree's
`<`,`<=`,`=`,`>=`,`>` plus the comparison support function). It is how
`CREATE INDEX` knows how to compare a column's values. [inferred] (via
`knowledge/files/src/backend/access/index/amapi.c.md`).



### opcmethod
The `pg_opclass` column naming the index access method (btree, hash, gist, …) an operator class belongs to; an opclass is meaningful only for one AM. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### OpenPipeStream
The backend `popen`-equivalent (`OpenPipeStream(cmd, PG_BINARY_R/W)`) that launches a shell command as a readable or writable pipe stream. It is the mechanism behind `COPY ... FROM/TO PROGRAM` and behind `file_fdw`'s program data source, which delegates through `BeginCopyFrom` with `is_program=true`. [verified-by-code] (`copyfrom.c` — via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### OpenTransientFile
The fd.c helper for opening an OS file outside the virtual-FD pool: the descriptor is automatically closed at transaction end (or on error), making it the right choice for short-lived reads/writes such as COPY and file_fdw, but it does not count against `max_files_per_process`. [from-comment] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### OpExpr
The expression node for a binary (or unary) operator invocation, carrying the
operator OID, result type, input collation, and argument list. The executor
evaluates it through the operator's underlying function; deparsers like
postgres_fdw only ship it remotely when `is_shippable(opno, OperatorRelationId)`
holds. [verified-by-code] (via
`knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### opfamily (operator family)
A grouping of related operator classes (`pg_opfamily`) that lets cross-type
operators participate in the same index strategy — e.g. int2/int4/int8 share
one btree family so a mixed-type predicate can still use an index. [inferred]
(via `knowledge/files/src/backend/access/index/amapi.c.md`).



### oprcanhash
The `pg_operator` flag declaring that an equality operator supports hashing, a prerequisite for hash joins and hash aggregation on the type; opclass setup must keep it consistent with the registered hash support function. [verified-by-code] (`pg_operator.dat:2775-2778` — via `knowledge/scenarios/add-new-data-type.md`).



### origin_id
The replication-origin identifier carried on a decoded commit record and in `ReorderBufferChange` (`reorderbuffer.h`); logical apply uses it to skip changes that originated from the local node, the mechanism behind origin-filtered / loop-avoiding logical replication. [from-comment] (via `knowledge/idioms/replication-origin-tracking.md`).



### os_info
A pg_upgrade global aggregating operating-system / cluster discovery state (binary and data directories, found executables, per-database file lists) alongside the `user_opts` options global; the migration driver threads both through its phases. [verified-by-code] (`option.c:14` — via `knowledge/files/src/bin/pg_upgrade/option.c.md`).



### OUTER_VAR
A special negative `Var.varno` sentinel (`-2`) used in post-planner executor plans, meaning the Var references the outer child plan node's output tuple slot (paired with `INNER_VAR` `-1` for the inner child, plus `INDEX_VAR` and `ROWID_VAR`). [verified-by-code] (`primnodes.h` — via `knowledge/data-structures/var-const-nodes.md`).



### output_plugin
The logical-decoding extension interface: a shared library that registers callbacks (`startup`, `begin`, `change`, `commit`, …) through `OutputPluginCallbacks`, invoked by the decoder to turn WAL changes into a consumer-defined format. `test_decoding` is the in-tree example. [from-comment] (via `knowledge/files/contrib/test_decoding/test_decoding.c.md`).



### OutputPluginCallbacks
The struct of callbacks (startup / begin / change / truncate / commit / ...)
that a logical-decoding output plugin fills in from `_PG_output_plugin_init`
to receive the reordered transaction stream. [verified-by-code] (via
`knowledge/idioms/output-plugin-callbacks.md`).



### OutputPluginPrepareWrite
The call a logical-decoding output plugin makes before writing to the stream to
obtain/prepare the output buffer; paired with `OutputPluginWrite` to emit a
decoded change. [verified-by-code] (via
`knowledge/idioms/output-plugin-callbacks.md`).



### OutputPluginWrite
The logical-decoding helper a plugin calls to flush the message it assembled (after `OutputPluginPrepareWrite`) to the replication stream; the pair brackets every emitted change. [verified-by-code] (`pgoutput.c:278-285` — via `knowledge/files/src/backend/replication/pgoutput/pgoutput.c.md`).



### PageAddItem
The bufpage macro (a wrapper over `PageAddItemExtended`) that inserts a new item — heap tuple or index entry — into a page's line-pointer array; the heap, btree, gist, and brin AMs all build pages through it. [from-comment] (`bufpage.h:24-78` — via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### PageGetHeapFreeSpace
Returns the usable free space on a heap page for a *new* tuple, accounting for the line-pointer that would have to be allocated and the `MaxHeapTuplesPerPage` cap — stricter than the raw `PageGetFreeSpace`. The FSM is fed from this. [verified-by-code] (via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### PageGetItem
The page-access macro returning a pointer to the tuple/item referenced by a given line pointer on a buffer page, the standard way AM code reads an item after `PageGetItemId`. Hardened wrappers (e.g. amcheck's `PageGetItemIdCareful`) bounds- and flag-check the line pointer first to avoid following corruption. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### PageGetItemId
The macro returning the `ItemId` (line pointer) for a given 1-based
`OffsetNumber` on a page — the indirection layer that lets the heap move tuples
within a page (during pruning/compaction) without changing their TIDs. Callers
pair it with `ItemIdIsValid`/`ItemIdIsNormal` before dereferencing.
[verified-by-code] (via
`knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### PageGetMaxOffsetNumber
Returns the highest valid line-pointer offset on a page (0 if empty), derived from `pd_lower`; the loop bound for scanning every item on a page. Off-by-one or unchecked use is a classic page-corruption read bug. [verified-by-code] (via `knowledge/files/contrib/pageinspect/brinfuncs.c.md`).



### PageHeader
The fixed header struct at the start of every standard 8KB disk page, holding `pd_lower`/`pd_upper` (the free-space boundaries), `pd_special`, `pd_checksum`, and `pd_pagesize_version`. All heap and index AMs lay out their content after it (item pointers grow up from `pd_lower`, tuples down from `pd_upper`, an opaque special area below `pd_special`); WAL's `REGBUF_STANDARD` flag marks a buffer as PageHeader-aware so full-page-image compression can elide the free-space hole. [verified-by-code] (via `knowledge/idioms/wal-record-construction.md`).



### PageHeaderData
The fixed header at the start of every 8 KB page: page LSN, checksum, flag
bits, the `pd_lower`/`pd_upper`/`pd_special` offsets that bound the line-pointer
array and the tuple area, and the page-size/version word. pageinspect's
`page_header()` decodes exactly these fields. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/pageinspect.md`).



### PageInit
Stamps a freshly-allocated 8 KB buffer as an empty PostgreSQL page: it zeroes the body, writes the `PageHeaderData` (pd_lower/pd_upper/pd_special, version), and is the first call when extending a relation by a new block. [verified-by-code] (via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### PageIsNew
The predicate that reports whether a page has never been initialised
(`pd_upper == 0`), i.e. freshly extended zero-filled space. AMs detect it on
read and run their page-init routine before use; bloom does
`PageIsNew || BloomPageIsDeleted` to decide a page needs reinitialising.
[verified-by-code] (via `knowledge/files/contrib/bloom/blinsert.c.md`).



### PageRepairFragmentation
Compacts a heap page during pruning/vacuum: it slides live tuples together to coalesce free space into one contiguous hole between the line-pointer array and the tuples, and `ERROR`s if it detects a corrupt item layout. [verified-by-code] (via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### PAGES_PER_CHUNK
The number of consecutive heap pages covered by one "chunk" entry in a `TIDBitmap`'s lossy representation, equal to `BLCKSZ / 32` (256 at the default 8K block size). When a bitmap becomes lossy, an entire chunk is collapsed into a single chunk header (located at `(blockno / PAGES_PER_CHUNK) * PAGES_PER_CHUNK`) with one bit per page rather than per tuple; it is kept a power of 2 to make the bit arithmetic cheap. [verified-by-code] (`tidbitmap.c.md` — via `knowledge/files/src/backend/nodes/tidbitmap.c.md`).



### PageSetLSN
The macro that stamps a page's LSN with the position returned by `XLogInsert`, recording that the page's latest change is durable once WAL up to that LSN is flushed; it must be set *after* `XLogInsert` returns. [from-README] (`transam/README:457-466` — via `knowledge/architecture/wal.md`).



### pagesPerRange
The BRIN parameter fixing how many consecutive heap pages summarize into one index range (default 128). It sets the granularity/size tradeoff: smaller ranges give tighter min/max summaries but a larger index and revmap. [inferred] (via `knowledge/idioms/brin-revmap.md`).



### PagetableEntry
The per-page record in a TIDBitmap: it holds either an exact bitmap of matching
offsets within one heap block or a "lossy" mark meaning the whole page must be
rechecked, and it moves through a three-state lifecycle as the bitmap is built
and then iterated. [verified-by-code] (via
`knowledge/idioms/tidbitmap-build-and-iterate.md`).



### palloc
Context-aware memory allocation. Memory returned by `palloc` belongs to the
`CurrentMemoryContext` rather than to the caller; it can be freed individually
with `pfree` but is more usually reclaimed in bulk when its context is reset or
deleted. OOM is reported via `ereport`, never a NULL return. [from-comment]
(`palloc.h:1-9,31-52` — via
`knowledge/files/src/include/utils/palloc.h.md`).



### palloc0
Like `palloc` but the returned block is zero-filled; the canonical way to obtain zeroed memory in the current `MemoryContext`. Like all palloc-family calls it throws on OOM rather than returning NULL. [verified-by-code] (via `knowledge/idioms/memory-contexts.md`).



### palloc0_array
A type-safe, zero-filling array-allocation macro shaped as `(type *) palloc0(count * sizeof(type))`; it uses `palloc_mul` internally so the size multiplication cannot silently overflow. It is one of the typed-allocation macros in `palloc.h:100-123` alongside `palloc_array`, `palloc_object`, and the `repalloc*` resize variants. [verified-by-code] (`palloc.h.md` — via `knowledge/files/src/include/utils/palloc.h.md`).



### palloc0_object
A typed allocation macro that palloc-zeroes `sizeof(type)` bytes and returns a correctly-typed pointer (e.g. `palloc0_object(Subscription)`), the zeroing typed sibling of `palloc_object`; it reduces `sizeof` mistakes versus a raw `palloc0`. [verified-by-code] (via `knowledge/upstream-deltas/2026-06-18.md`).



### palloc_aligned
A `palloc` variant that returns memory aligned to a caller-requested boundary (e.g. for direct I/O or SIMD), storing extra bookkeeping so that ordinary `pfree` still works on the pointer. [verified-by-code] (`mcxt.c:1485` — via `knowledge/files/src/backend/utils/mmgr/mcxt.c.md`).



### palloc_array
Type-safe allocation macro: `palloc_array(Type, n)` palloc's room for `n` elements of `Type`, computing the size and casting the result; the array sibling of `palloc_object`. An unbounded `n` is the allocation-DoS surface to cap at the input boundary. [verified-by-code] (via `knowledge/files/contrib/intarray/_int_gin.md`).



### palloc_extended
The flags-taking allocation entry point: `MCXT_ALLOC_HUGE` allows sizes up to `MaxAllocHugeSize`, `MCXT_ALLOC_NO_OOM` returns NULL instead of ereporting on OOM, and `MCXT_ALLOC_ZERO` zero-fills. Used where the standard palloc contract (ereport-on-OOM, ≤1 GB) does not fit. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### palloc_object
A typed allocation macro that `palloc`s `sizeof(T)` and returns a `T*` — e.g. `palloc_object(ControlFileData)`; it does NOT zero the memory, so relying on uninitialized fields (as `pgpa_trove.c` was noted to) is a bug. [verified-by-code] (via `knowledge/files/src/common/controldata_utils.c.md`).



### PANIC
The highest ereport severity: it logs the message and then aborts the whole postmaster, forcing a crash-recovery cycle on restart; reserved for corruption that makes continuing unsafe (e.g. a failed WAL redo). [verified-by-code] (via `knowledge/files/src/backend/utils/error/elog.c.md`).



### parallel query
The execution mode in which the leader backend launches parallel worker
backends (via `dsm` + a `ParallelContext`) to run a parallel-aware portion of a
plan beneath a `Gather`. Functions are labelled parallel-safe / -restricted /
-unsafe to decide what may run in a worker. [from-comment] (via
`knowledge/files/src/backend/access/transam/parallel.c.md`).



### parallel_divisor
The planner factor (computed by `get_parallel_divisor`) that a partial path's per-worker row and cost estimates are divided by; it approximates the effective number of workers, accounting for the leader's partial participation. [from-comment] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### PARALLEL_MAGIC
The magic number passed to shm_toc_create / shm_toc_attach for a parallel query's DSM table of contents, guarding against attaching to a mismatched or corrupt segment. [verified-by-code] (via `knowledge/idioms/parallel-context-and-dsm.md`).



### parallel_setup_cost
The planner cost-model unit charging the one-time overhead of launching parallel workers and setting up their DSM; it is added once to a parallel path to model the fixed cost of going parallel. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### parallel_tuple_cost
The planner cost-model unit charged per tuple passed from a parallel worker to the leader through the Gather shm_mq; it models the per-row cost of the parallel tuple queue. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### ParallelBitmapHeapState
The small DSM-resident control block coordinating a parallel bitmap heap scan:
one elected worker builds the shared TID bitmap while the others wait, then all
workers cooperatively consume pages from it. [verified-by-code] (via
`knowledge/idioms/parallel-bitmap-heap.md`).



### ParallelContext
The handle a leader backend uses to set up parallel query: it describes the
entry point, the DSM segment, and the shared state to copy to workers, and is
the object `RegisterDynamicBackgroundWorker` workers attach to.
[verified-by-code] (`parallel.h:33-50` — via
`knowledge/files/src/include/access/parallel.h.md`).



### ParallelWorkerMain
The fixed entrypoint a generic parallel worker runs after fork: it attaches to
the DSM segment, restores the leader's GUC/snapshot/xact state from the TOC, and
dispatches to the registered per-node worker function. [verified-by-code] (via
`knowledge/idioms/bgworker-and-parallel.md`).



### ParallelWorkerNumber
The zero-based index a parallel worker uses to locate its own slice of shared state (for example its `Instrumentation` slot); it is `-1` in the leader process. [verified-by-code] (via `knowledge/files/src/include/access/parallel.h.md`).



### ParallelWorkerReportLastRecEnd
A parallel worker → leader handoff that reports the worker's last-written WAL LSN (`XactLastRecEnd`) so the leader's commit correctly waits for the worker's WAL to be flushed and, if configured, replicated. [verified-by-code] (`parallel.c:1594` — via `knowledge/files/src/backend/access/transam/parallel.c.md`).



### PARAM_EXEC
The parameter kind for values passed internally within a plan at run time —
correlated-subquery references, recursive-CTE working state, and similar — as
opposed to `PARAM_EXTERN` client bind parameters. The planner assigns each a
slot id held in `PlannerInfo`. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).



### PARAM_EXTERN
One of the two `Param` parameter modes: an externally-supplied value statically known up front and carried via `ParamExternData` (contrast with `PARAM_EXEC`, which is computed during execution via `ParamExecData`). [from-comment] (`params.h` — via `knowledge/files/src/include/nodes/params.h.md`).



### PARAM_MULTIEXPR
A `Param` kind used for the columns of a multi-assignment `UPDATE ... SET (a, b) = (SELECT ...)`, referencing the individual output columns of the shared sub-select. [inferred] (via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### parameterdescription
The extended-query protocol message returned by Describe-on-a-prepared-statement, listing the parameter type OIDs the backend inferred for the statement. [from-docs] (via `knowledge/docs-distilled/protocol-flow.md`).



### ParameterStatus
The protocol message (tag 'S') by which the backend reports a GUC's value to the client — sent at startup for the reportable parameters (e.g. server_version, client_encoding, TimeZone) and again whenever one changes. [verified-by-code] (`fe-protocol3.c:183` — via `knowledge/files/src/interfaces/libpq/fe-protocol3.c.md`).



### ParamExecData
The executor-internal parameter slot (an entry in es_param_exec_vals[]) holding one PARAM_EXEC Datum plus its isnull flag, used to pass values into correlated subplans and initplans. [verified-by-code] (via `knowledge/files/src/include/nodes/params.h.md`).



### paramExecTypes
The `PlannerGlobal`/`PlannedStmt` list mapping each PARAM_EXEC slot number to its result type OID; it is the executor-internal parameter registry for correlated subplans and is never compacted for the plan's lifetime. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### ParamListInfo
The runtime parameter list (`params.h`) that carries external query-parameter values and types into the executor; e.g. PL/pgSQL's execstate threads one through to bind `$n` placeholders. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/plpgsql.md`).



### ParamRef
The raw parse-tree node (NodeTag-direct, `parsenodes.h:321`) representing a `$n` parameter placeholder, carrying just the parameter number and source location with no type info yet. During parse analysis `transformExprRecurse` lowers it via `transformParamRef`, which consults `pstate->p_paramref_hook` and emits a fully-typed `Param` Expr node; the original `ParamRef` is discarded. [verified-by-code] (via `knowledge/idioms/node-types.md`).



### parse_analyze_fixedparams
The parse-analysis entry point used when all parameter types are known up front, transforming a raw parse tree into a `Query`; the plan cache calls it during revalidation. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### parse_clause
The parser module (`src/backend/parser/parse_clause.c`) that transforms a query's FROM / WHERE / GROUP BY / HAVING / ORDER BY clauses and builds the join tree; e.g. `transformRangeTableFunc` handles a table-function FROM item. It runs after the target list is understood and populates the query's jointree and sort/group clauses. [verified-by-code] (`parse_clause.c` — via `knowledge/subsystems/parser-and-rewrite.md`).



### parse_coerce
The parser module (`src/backend/parser/parse_coerce.c`) implementing type coercion of expression operands to a target type — `coerce_to_target_type` plus the assignment / implicit / explicit coercion contexts, including special modes like `COERCION_PLPGSQL`. It is what decides whether a value can be silently converted and inserts the `CoerceViaIO` / cast nodes when it can. [verified-by-code] (`parse_coerce.c` — via `knowledge/subsystems/parser-and-rewrite.md`).



### parse_expr
The parser module (`src/backend/parser/parse_expr.c`) whose `transformExpr` turns raw grammar expression nodes into fully analyzed `Expr` trees, resolving column references, function calls (via `parse_func.c`), operators, and sublinks. `transformParamRef` here is where the `$n` / param-hook dispatch lives. [verified-by-code] (`parse_expr.c` — via `knowledge/subsystems/parser-and-rewrite.md`).



### parse_func
The parser module (`src/backend/parser/parse_func.c`) that resolves a function-call syntax node to a concrete `pg_proc` entry: candidate gathering, best-match selection over the overload set, polymorphic-type resolution, and `table.column` field-selection dispatch. `parse_oper.c` reuses the same candidate-matching shape for operators. [verified-by-code] (`parse_func.c` — via `knowledge/subsystems/parser-and-rewrite.md`).



### parse_lquery
ltree's hand-rolled recursive-descent parser for the `lquery` pattern type — a 9-state character-by-character machine (no flex/bison), paired with `parse_ltree` for the `ltree` type. It enforces `LQUERY_MAX_LEVELS = 65535` (INV-LQUERY-LEVEL-COUNT). [verified-by-code] (`ltree_io.c:268` — via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### parse_ltree
The ltree text-input parser (sibling `parse_lquery`); both classify label characters through the encoding-aware `ISLABEL`, so the same literal can parse differently under different `lc_ctype` — e.g. `é.bar` is a syntax error under C but a valid label under a UTF-8 locale. [from-comment] (via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### parse_manifest
The frontend/common parser for the backup manifest JSON emitted by
`pg_basebackup` — it validates the file list, checksums, and WAL range, and is
consumed by `pg_verifybackup` and `pg_combinebackup`. Built on the incremental
JSON parser so a huge manifest need not be held in memory at once.
[verified-by-code] (via
`knowledge/files/src/include/common/parse_manifest.h.md`).



### parse_oper
The parser module (`src/backend/parser/parse_oper.c`) that resolves an operator token to its `pg_operator` row — `oper()` / `right_oper()` and the operator-candidate search — using logic analogous to function overload resolution in `parse_func.c`, since operators are themselves backed by functions. [verified-by-code] (`parse_oper.c` — via `knowledge/subsystems/parser-and-rewrite.md`).



### parse_relation
The parser module (`src/backend/parser/parse_relation.c`) that manages a query's range table and name resolution: adding RTEs, looking up relation and column references within the current namespace, and expanding column lists (the machinery behind `SELECT *` and USING/NATURAL joins). [verified-by-code] (`parse_relation.c` — via `knowledge/files/src/backend/catalog/namespace.c.md`).



### parse_target
The parser module (`src/backend/parser/parse_target.c`) that builds a query's target list of `TargetEntry` nodes from SELECT / RETURNING items — expanding `*`, resolving output column names, and transforming each expression. It builds only what the SQL text names; defaults and nulls for omitted columns are filled elsewhere. [verified-by-code] (`parse_target.c` — via `knowledge/subsystems/parser-and-rewrite.md`).



### parse_type
The parser type-name resolver (`src/backend/parser/parse_type.c`): `typenameType` / `LookupTypeName` turn a grammar `TypeName` node into a resolved type OID plus typmod, honoring schema qualification, `%TYPE`, and array decoration. It is called wherever the parser must pin down a declared type. [inferred] (`parse_type.c` — via `knowledge/files/src/pl/plpgsql/src/pl_gram.md`).



### parsed_hba_lines
The in-memory parsed form of `pg_hba.conf` (a list of rule structs) that `check_hba()` scans line by line to pick an auth method; refreshed on config reload. [verified-by-code] (via `knowledge/docs-distilled/auth-pg-hba-conf.md`).



### ParseDateTime
The first stage of date/time input: it breaks a raw string into typed field tokens (`fields`/`ftype` arrays) which `DecodeDateTime`/`DecodeTimeOnly` then interpret per the active `DateStyle`. Splitting tokenization from interpretation is what lets one parser serve many datetime types. [inferred] (`datetime.h:306` — via `knowledge/files/src/backend/utils/adt/datetime.c.md`).



### ParseExprKind
The enum passed to `transformExpr` naming the syntactic context of an expression (WHERE, SELECT target, CHECK constraint, index predicate, …) so parse analysis can apply context-specific rules and error messages. [verified-by-code] (via `knowledge/files/src/include/parser/parse_expr.h.md`).



### ParseLoc
The typedef (an `int`) used for a parse/source-text location — a character offset into the original query string — carried on parse-tree nodes to drive error-cursor reporting; a value of -1 means "no location". [verified-by-code] (`nodes.h` — via `knowledge/idioms/node-types.md`).



### ParseNamespaceItem
The parser's per-FROM-item bookkeeping (an `RTE` plus visibility flags for its columns) that determines which relations and columns a column reference may resolve to at a given point in a query's namespace. [verified-by-code] (`parse_relation.c` — via `knowledge/files/src/backend/parser/parse_relation.c.md`).



### ParseState
The working context threaded through parse analysis: it carries the range
table being built, the source query text (for error positions), parameter-type
hooks, and flags controlling what expression kinds are allowed in the current
clause. [verified-by-code] (`parse_node.h:91` — via
`knowledge/files/src/backend/parser/parse_node.c.md`).



### parseTypeString
Parses a textual type name (e.g. `numeric(10,2)`, `myschema.mytype`) into a
type OID and typmod by running it through the SQL grammar, honoring the
current search_path — a NAME-to-OID resolution point relevant to Phase-D
analysis. [verified-by-code] (`plpy_spi.c:105` — via
`knowledge/files/src/pl/plpython/plpy_plpymodule.md`).



### partbounds
`src/backend/partitioning/partbounds.c` — the partition-bound arithmetic: building and comparing `PartitionBoundInfo` for LIST/RANGE/HASH partitioning, binary-searching a datum to its partition index, and the partition-wise-join bound-matching logic. The canonical home for “which partition does this key fall into”. [verified-by-code] (via `knowledge/files/src/backend/partitioning/partbounds.c.md`).



### partdesc
`src/backend/partitioning/partdesc.c` — builds and caches the `PartitionDesc` for a partitioned table: the relcache-attached array of child OIDs plus the `PartitionBoundInfo` mapping bounds to partitions. It is rebuilt on relcache invalidation and underpins both planning-time pruning and tuple routing. [verified-by-code] (via `knowledge/files/src/backend/partitioning/partdesc.c.md`).



### partial index
An index built with a `WHERE` predicate so it indexes only the rows satisfying it — shrinking the index and enabling subset-scoped unique constraints (`CREATE UNIQUE INDEX … WHERE success`). It is usable only when the planner can prove at plan time (via `predicate_implied_by`) that the query's `WHERE` implies the index predicate; a guaranteed predicate need not be rechecked at runtime, which lets a partial index feed an index-only scan on a predicate-only column. [from-docs §11.8] (via `knowledge/docs-distilled/indexes-partial.md`).



### partial_pathlist
The `RelOptInfo` list holding **partial** Paths — those that produce only a per-worker share of the relation's rows and must sit under a Gather/GatherMerge to be completed. Kept separate from `pathlist` because a partial path is not directly usable as a full-relation path. [verified-by-code] (via `knowledge/data-structures/reloptinfo.md`).



### PartitionBoundInfo
The canonicalized, sorted representation of a partitioned table's bounds (list /
range / hash) used for binary-search partition lookup and for comparing two
partition descriptors. [verified-by-code] (via
`knowledge/idioms/partition-bound-comparison.md`).



### PartitionBoundSpec
The parse-node form of a partition's bound (`FOR VALUES IN/FROM..TO/WITH`), carrying the raw range/list/hash bound before it is transformed into the canonical `PartitionBoundInfo` stored in the parent's relcache. [verified-by-code] (`partbounds.c` — via `knowledge/files/src/backend/partitioning/partbounds.c.md`).



### PartitionDesc
The cached runtime descriptor of a partitioned table's partition set: the
ordered bound info plus the child relation OIDs, built from the catalog and
attached to the relcache entry. Tuple routing and partition pruning both read
it; it is rebuilt on invalidation so concurrent ATTACH/DETACH are seen.
[verified-by-code] (via
`knowledge/files/src/include/partitioning/partdesc.h.md`).



### partitiondescdata
`PartitionDescData` (`partdesc.h:29-64`) is the relcache-cached description of a partitioned table's children — `nparts`, the child OID array, and the `PartitionBoundInfo`. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### PartitionDirectory
An opaque partitioning type (`typedef struct PartitionDirectoryData *PartitionDirectory`, forward-declared in `partdefs.h`) that caches `PartitionDesc` lookups so a query holds a stable view of each partitioned table's partition set for its duration. It is one of the core partitioning structs other headers reference without pulling in full definitions. [verified-by-code] (`partdefs.h` — via `knowledge/files/src/include/partitioning/partdefs.h.md`).



### PartitionKey
The cached descriptor of a partitioned table's partitioning strategy, key
columns/expressions, and comparison support functions, used to route tuples and
prune partitions. [verified-by-code] (via
`knowledge/idioms/partition-runtime-pruning.md`).



### PartitionPruneInfo
The plan-time structure describing how to prune partitions at execution, holding
the pruning steps and the parameters that, when known, eliminate child subplans
of an Append/MergeAppend. [verified-by-code] (via
`knowledge/idioms/partition-runtime-pruning.md`).



### PartitionPruneState
The opaque per-Append/MergeAppend executor state for runtime partition pruning, built from the planner's `PartitionPruneInfo` by `ExecInitPartitionExecPruning`. `ExecFindMatchingSubPlans(prunestate, initial_prune)` consults it (e.g. from Append/MergeAppend ReScan) to return a Bitmapset of the subplan indexes that survive pruning. [verified-by-code] (`execPartition.h.md` — via `knowledge/files/src/include/executor/execPartition.h.md`).



### PartitionTupleRouting
The executor structure built by `ExecSetupPartitionTupleRouting` that maps an
incoming tuple from a partitioned root down to the correct leaf partition's
ResultRelInfo, lazily initializing per-leaf state and tuple-conversion maps as
rows route to them. [verified-by-code] (`executor.c:221` — via
`knowledge/subsystems/executor.md`).



### password_required
A postgres_fdw user-mapping option whose default (`true`) forbids non-superusers from using a mapping that would let libpq connect without a password, blocking the classic "loopback to bypass RLS / impersonate" attack. The corpus calls its two-layered enforcement (CREATE-time superuser check plus a post-connect `PQconnectionUsedPassword` cross-check) the gold standard, which file_fdw and dblink lack. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### Path
The planner's representation of one candidate way to produce a relation's rows
(seqscan, indexscan, a particular join order), annotated with estimated startup
and total cost. The optimizer enumerates Paths into each `RelOptInfo`, keeps
the cheapest non-dominated ones, and turns the winner into a `Plan`.
[from-comment] (via `knowledge/subsystems/optimizer.md`).



### path_is_safe_for_extraction
The guard the base-backup file extractor runs on every archive member path before writing it, rejecting absolute paths and `..` traversal so a malicious tar stream cannot escape the target directory; failure is fatal (`pg_fatal`). [verified-by-code] (`astreamer_file.c:37` — via `knowledge/files/src/fe_utils/astreamer_file.c.md`).



### pathlist
A `RelOptInfo`'s list of candidate access `Path` nodes, populated by the `set_*_pathlist` routines and pruned by `add_path` cost dominance; `set_cheapest` then selects the winners into `cheapest_*_path`. [verified-by-code] (via `knowledge/data-structures/reloptinfo.md`).



### patternToSQLRegex
The fe_utils sibling of `processSQLNamePattern`, used by pg_amcheck and
others, that converts a shell-style object-name pattern into an anchored POSIX
regex for catalog matching. [verified-by-code] (`string_utils.c:1219` — via
`knowledge/issues/pg_amcheck.md`).



### PD_ALL_VISIBLE
The page-header flag bit asserting that every tuple on the page is visible to
all transactions; it lets sequential scans skip per-tuple visibility checks
and must stay in sync with the relation's visibility-map bit.
[verified-by-code] (via
`knowledge/files/src/backend/access/common/bufmask.c.md`).



### pd_checksum
The 16-bit field in a page header holding the page's data checksum when `data checksums` are enabled; it is computed over the page (with the field itself zeroed) just before write and re-verified on read. A mismatch raises a checksum-failure error and bumps `pg_stat_database.checksum_failures`. [inferred] (`checksum_impl.h:181` — via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### pd_lower
The page-header field marking the end of the line-pointer array — the low
boundary of a heap/index page's free space (free space runs from `pd_lower` up
to `pd_upper`). WAL full-page-image compression can omit the hole between the
two when `pd_lower`/`pd_upper` are set correctly. [verified-by-code] (via
`knowledge/files/src/include/storage/bufpage.h.md`).



### pd_lsn
The page-header field recording the LSN of the last WAL record that modified the page; the buffer manager refuses to flush a dirty page until WAL up to `pd_lsn` is durable (the WAL-before-data rule). [verified-by-code] (`bufpage.h:184` — via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### pd_prune_xid
A per-page hint XID in the heap page header, set by inserters/pruners to the oldest XID that pruning could remove; a cheap gate that lets a scan skip the expensive opportunistic-prune attempt when no work is yet possible. [from-comment] (via `knowledge/idioms/vacuum-hot-prune.md`).



### pd_special
The page-header offset (`PageHeaderData`, with `pd_lower` / `pd_upper`) to the start of the "special space" at the page end, used by index AMs for opaque per-page metadata. [from-docs] (via `knowledge/docs-distilled/storage-page-layout.md`).



### pd_upper
The page-header field giving the byte offset to the start of the upper (tuple) portion of free space; the gap between `pd_lower` and `pd_upper` is the page's free space. New tuples grow `pd_upper` downward while their line pointers grow `pd_lower` upward. [inferred] (via `knowledge/files/src/backend/storage/page/bufpage.c.md`).



### peer_cert_valid
The backend `Port` flag recording whether the client presented a valid X.509 certificate over TLS; sslinfo's peer-certificate introspection functions require it (in addition to `ssl_in_use`) before returning DN / extension fields. [verified-by-code] (`sslinfo.c:5` — via `knowledge/files/contrib/sslinfo/sslinfo.c.md`).



### penalty_num
The numeric-type GiST penalty macro in btree_gist; it computes how much inserting a key would enlarge a numeric key-range bounding interval, driving GiST's choose-subtree decision. [verified-by-code] (`btree_utils_num.c:25` — via `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`).



### pendingSyncHash
The backend-local hash recording relfilenodes of permanent relations created while `wal_level=minimal` (so their pages were not WAL-logged) that must instead be fsync'd at commit; aborts and parallel-worker exits discard it (workers issue no syncs). [verified-by-code] (`storage.c:71-78` — via `knowledge/files/src/backend/catalog/storage.c.md`).



### performDeletion
The dependency-aware object-drop driver: given an `ObjectAddress` it walks `pg_depend`, collects everything that must go, honours `RESTRICT`/`CASCADE`, and deletes the whole set in dependency order. Backs `DROP` and temp-namespace cleanup. [verified-by-code] (via `knowledge/files/src/backend/catalog/dependency.c.md`).



### PerformWalRecovery
The xlogrecovery.c driver that runs the main redo loop after `InitWalRecovery` has decided between crash, archive, and standby recovery, replaying records up to the consistency/recovery target. [from-comment] (via `knowledge/files/src/backend/access/transam/xlogrecovery.c.md`).



### pg_am
The system catalog of access methods (both index AMs and table AMs); each row names the handler function that, when called, returns the AM's `IndexAmRoutine` or `TableAmRoutine`. [verified-by-code] (`GetIndexAmRoutineByAmId` looks up the handler OID in `pg_am` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### pg_amop
The system catalog identifying the operators associated with each index operator family/class; one row per operator, marked as a search operator or an ordering operator by `amoppurpose`, with its strategy number. The planner consults it to decide which operators an index can satisfy. [from-comment] (via `knowledge/files/src/include/catalog/pg_amop.h.md`).



### pg_amproc
The system catalog of opclass/operator-family *support function* entries, keyed by (family, left type, right type, support-number); `amvalidate` cross-checks these rows against each AM's required-proc rules. [from-comment] (`brin_validate.c:1-12` — via `knowledge/files/src/backend/access/index/amapi.c.md`).



### pg_any_to_server
The encoding-conversion routine that converts a client-supplied string from the
current client_encoding to the server (database) encoding, applying the
registered conversion procedure and rejecting invalidly-encoded input. Its
inverse is `pg_server_to_any`. [verified-by-code] (via
`knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### PG_ARGISNULL
Macro a SQL-callable C function uses to test whether argument N was passed SQL NULL before touching it; mandatory for non-strict functions, since `PG_GETARG_*` on a NULL arg yields garbage. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/misc.c.md`).



### pg_atomic_uint32
The backend's portable 32-bit atomic integer type, manipulated only through the `pg_atomic_read_u32`/`pg_atomic_compare_exchange_u32`/`pg_atomic_fetch_add_u32` API so the right CPU instructions or fallback spinlock are chosen per platform. Direct field access is forbidden. [inferred] (via `knowledge/files/src/include/port/atomics.md`).



### pg_atomic_uint64
The 64-bit atomic integer type from `port/atomics.h`, touched only through `pg_atomic_read_u64`/`pg_atomic_write_u64`/`pg_atomic_compare_exchange_u64` etc.; used for lock-free counters and packed state words such as the buffer descriptor's `state`. [verified-by-code] (via `knowledge/files/src/include/storage/buf_internals.h.md`).



### pg_attrdef
The catalog (`pg_attrdef`) storing column `DEFAULT` expressions, one row per defaulted attribute, linked to `pg_attribute` via `adrelid`/`adnum`. Rows are materialized from parser `Constraint` nodes by `AddRelationNewConstraints` in `heap.c`, the same path that writes `pg_constraint` CHECK rows. [verified-by-code] (`heap.c:2404` — via `knowledge/files/src/backend/catalog/heap.c.md`).



### pg_attribute
The system catalog with one row per table/index/view column, covering user attnums (1..relnatts) plus the negative system attnums; its initial contents are generated at compile time by genbki.pl (there is no `pg_attribute.dat`). It records each column's type, length, alignment, not-null, defaults flags, and dropped status. [from-comment] (via `knowledge/files/src/include/catalog/pg_attribute.h.md`).



### pg_attribute_printf
A `c.h` function-attribute macro that annotates a function as taking printf-style format/argument positions, enabling the compiler's format-string checking at call sites; PG sprinkles it on every elog/ereport-adjacent and frontend-logging helper. Function pointers cannot carry it, which is why some indirect call sites lose the check. [verified-by-code] (via `knowledge/files/src/include/port.h.md`).



### pg_auth_members
The cluster-wide system catalog recording role-membership edges (member → role) created by `GRANT role TO role`, with grantor and the admin/inherit/set option flags. Privilege resolution (`has_privs_of_role`, `is_member_of_role`) walks it; the INHERIT-vs-SET distinction is what makes the two checks differ. [verified-by-code] (via `knowledge/files/src/include/catalog/pg_auth_members.h.md`).



### pg_authid
The cluster-wide (`BKI_SHARED_RELATION`) system catalog storing one row per role, including role attributes (superuser, login, createrole, replication) and the hashed `rolpassword` column. `pg_shadow` and `pg_group` are now views over it; the password column is why it is readable only by superusers. [from-comment] (via `knowledge/files/src/include/catalog/pg_authid.h.md`).



### pg_b64_decode
Decodes base64 input into a caller-supplied buffer, rejecting invalid characters and returning the decoded length or -1 on overflow; the inverse of `pg_b64_encode`, shared by frontend and backend. [verified-by-code] (`base64.c:115` — via `knowledge/files/src/common/base64.c.md`).



### pg_b64_encode
Encodes a byte buffer into base64 into a caller-supplied destination, returning the encoded length or -1 on overflow; the shared encoder behind SCRAM, GSSAPI, and `encode(…, 'base64')`. [verified-by-code] (`base64.c:48` — via `knowledge/files/src/common/base64.c.md`).



### pg_backup_archiver
The format-independent archive engine of `pg_dump` (`src/bin/pg_dump/pg_backup_archiver.c`): it reads and writes the archive header and TOC entries for the custom / directory / tar formats and drives restore, so `pg_dump.c` and `pg_restore` share one archive abstraction across output formats. [verified-by-code] (`pg_backup_archiver.c` — via `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md`).



### pg_basebackup
The client tool that takes a physical base backup of a running cluster over the replication protocol (`BASE_BACKUP` command), writing either a plain extracted directory tree or one tar per tablespace. It can stream WAL in parallel via a forked background process so the backup is self-consistent on restore. [verified-by-code] (via `knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md`).



### pg_be_sasl_mech
The backend SASL-mechanism vtable type (`sasl.h`): each mechanism (`pg_be_scram_mech`, `pg_be_oauth_mech`) is a `pg_be_sasl_mech` instance of callbacks plugged into the SASL exchange driver during authentication. [verified-by-code] (via `knowledge/subsystems/headers-wave3.md`).



### PG_BINARY
The platform file-open flag (0 on Unix, `O_BINARY` on Windows) OR'd into
`open`/`OpenTransientFile` calls to suppress text-mode CRLF translation so
byte streams are read verbatim. [from-comment] (via
`knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### pg_bitutils
The portable bit-manipulation library (`src/port/pg_bitutils.c` + `src/include/port/pg_bitutils.h`): popcount, right/left-most-set-bit, and related primitives, with a three-arm runtime dispatch (SSE4.2 `POPCNT`, other hardware paths, and a software fallback driven by a 256-entry `pg_number_of_ones` lookup table). [verified-by-code] (`pg_bitutils.c` — via `knowledge/files/contrib/intarray/_intbig_gist.md`).



### pg_buffercache
The contrib extension exposing the shared-buffer pool's contents as SQL — one row per buffer with its relfilenode, fork, block number, usage count, and pin count — plus, in newer versions, eviction helpers. It is the standard way to inspect what is cached without attaching a debugger. [verified-by-code] (via `knowledge/files/contrib/pg_buffercache/pg_buffercache_pages.c.md`).



### pg_buffercache_evict_all
A pg_buffercache function (developer/test aid) that evicts all *unpinned* shared buffers from the pool, returning how many were evicted. [from-docs] (via `knowledge/docs-distilled/pgbuffercache.md`).



### pg_buffercache_numa_pages
The pg_buffercache SRF (v1.6) reporting the NUMA node assignment of each OS memory page backing the shared buffer pool. [verified-by-code] (via `knowledge/subsystems/contrib-pg_buffercache.md`).



### pg_buffercache_pages
The pg_buffercache SRF emitting one row per shared buffer, taking an exact per-buffer spinlock snapshot of each descriptor (the accurate-but-costly view). [verified-by-code] (via `knowledge/subsystems/contrib-pg_buffercache.md`).



### pg_buffercache_summary
The pg_buffercache function (v1.4) returning lock-free aggregate counts of used / dirty / pinned buffers plus the average usage count. [verified-by-code] (via `knowledge/subsystems/contrib-pg_buffercache.md`).



### pg_buffercache_usage_counts
The pg_buffercache function (v1.4) returning a lock-free histogram of buffers bucketed by `usage_count` (0..max). [verified-by-code] (via `knowledge/subsystems/contrib-pg_buffercache.md`).



### pg_cast
The system catalog recording which type conversions exist and how each is performed (via function, binary-coercible, or I/O coercion); consulted by the parser's coercion logic. [from-docs] (via `knowledge/docs-distilled/typeconv-overview.md`).



### pg_catalog
The schema holding all built-in system catalogs, types, functions, and operators; it is implicitly first on every backend's effective `search_path`, so built-in names resolve before user objects of the same name. Security-sensitive code (e.g. postgres_fdw remote sessions) forces `search_path = pg_catalog` to avoid user-object shadowing. [from-comment] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### PG_CATCH
The cleanup arm of a `PG_TRY` block, entered only when an `ereport(ERROR)`
longjmps out of the guarded code. It runs with the error still pending, so
after releasing whatever the try-block acquired it must re-raise the error via
`PG_RE_THROW`. [from-comment] (via `knowledge/idioms/error-handling.md`).



### pg_check_frozen
A `pg_visibility` contrib probe returning the TIDs of tuples that are not actually frozen on pages the visibility map marks all-frozen — a corruption check on the VM's all-frozen bit. [from-docs] (via `knowledge/subsystems/contrib-pg_visibility.md`).



### pg_check_visible
A `pg_visibility` contrib probe returning the TIDs of tuples that are not all-visible on pages the visibility map marks all-visible — a corruption check on the VM's all-visible bit. [from-docs] (via `knowledge/subsystems/contrib-pg_visibility.md`).



### pg_checkpoint
A predefined role whose members may run `CHECKPOINT` without being superuser — one of the `pg_*` capability roles that each replace a single hardcoded `superuser()` gate. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_checksum_page
Computes the 16-bit data checksum of an 8 KB page from its contents and block number — the block number is folded in so a page written to the wrong place is detected — compared against the stored `pd_checksum` on read when checksums are enabled. [verified-by-code] (via `knowledge/files/contrib/pageinspect/pageinspect.md`).



### pg_class
The central system catalog with one row per relation (table, index, view, sequence, composite type, TOAST table, materialized view), holding relkind, relfilenode, reltuples/relpages stats, and access-method/ownership links. Most pg_class rows are written from `heap.c` (`InsertPgClassTuple`, `AddNewRelationTuple`) and many fields are maintained by inplace update. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_class.c.md`).



### pg_clean_ascii
The common-string routine that scrubs a string of control/non-ASCII bytes; it is the designated choke point against terminal-escape-sequence injection when untrusted text (e.g. application_name) is echoed to logs or a terminal. [from-comment] (via `knowledge/files/src/include/common/string.h.md`).



### pg_collation
The system catalog with one row per collation, recording its provider (libc / ICU / builtin), `collcollate`/`collctype`, encoding, and whether it is deterministic. `CollationCreate` writes the rows for CREATE COLLATION; locale changes to the underlying provider can silently invalidate stored ordering. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_collation.c.md`).



### pg_combinebackup
The tool that reconstructs a full backup from a chain of incremental backups plus their full base, reading each backup's manifest to assemble the final data directory (and pulling missing WAL from an archive via `restore_command` when needed). It underpins PostgreSQL's incremental-backup feature. [verified-by-code] (via `knowledge/files/src/fe_utils/archive.c.md`).



### pg_commit_ts
The SLRU (and on-disk directory) storing per-transaction commit timestamps when `track_commit_timestamp` is enabled. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### pg_compress_specification
The parsed representation of a compression method plus its options (e.g.
`gzip:9`, `zstd:level=3,long`), produced by `parse_compress_specification` and
consumed by the streaming-compression (`astreamer`) and backup code. It
normalizes the `method:detail` syntax used across `pg_basebackup`/`pg_dump`.
[verified-by-code] (via `knowledge/files/src/fe_utils/astreamer_zstd.c.md`).



### pg_conflict_detection
A PG18 internal replication slot (a reserved slot name) that holds back the
xid horizon on a logical-replication subscriber so it can detect
update/delete conflicts against rows a concurrent transaction may have changed.
Created when `retain_dead_tuples` / conflict tracking is enabled. [verified-by-code]
(via `knowledge/files/src/backend/replication/logical/worker.c.md`).



### pg_constraint
The system catalog storing table and domain constraints (check, foreign-key, unique, primary-key, exclusion); the relcache loads a relation's constraint info from it. [from-comment] (`relcache.c:1-26` — via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### pg_control
The cluster control file (`global/pg_control`) — not a heap relation, but documented as the `ControlFileData` struct: it records the catalog/control version, system identifier, latest checkpoint location and `CheckPoint` body, `DBState`, and WAL/block layout constants. A torn or stale control file blocks startup; `pg_resetwal` rewrites it as a last resort. [from-comment] (via `knowledge/files/src/include/catalog/pg_control.h.md`).



### pg_controldata
Both a CLI and a set of SQL functions (`pg_control_checkpoint/system/init/recovery`) that read and pretty-print `$PGDATA/global/pg_control` — the control version, system identifier, latest checkpoint, and WAL/block layout. It is the read-only inspection counterpart to the rarely-used `pg_resetwal`. [verified-by-code] (via `knowledge/files/src/backend/utils/misc/pg_controldata.c.md`).



### pg_conversion
The system catalog registering character-set conversion procedures; each row ties a (source encoding, destination encoding) pair to a SQL-callable conversion function. [from-comment] (via `knowledge/files/src/backend/utils/mb` docs).



### pg_crc32c
The CRC-32C (Castagnoli) checksum variant used throughout PostgreSQL — WAL records, backup manifests, and more. Its interface lives in `port/pg_crc32c.h`; new code must use this variant, never the legacy/traditional CRC in `pg_crc.h`. [from-comment] (via `knowledge/files/src/include/utils/pg_crc.md`).



### pg_create_logical_replication_slot
A SQL-callable function (wrapper in `slotfuncs.c`, real work in `slot.c`) that creates a named logical replication slot bound to a logical decoding output plugin, taking the slot name and plugin name (the plugin being the second argument). It sets up a `LogicalDecodingContext` to determine the start LSN; access is gated only by `has_rolreplication(GetUserId())`, with no whitelist on the named output plugin. [verified-by-code] (`slotfuncs.c.md` — via `knowledge/files/src/backend/replication/slotfuncs.c.md`).



### pg_createsubscriber
`src/bin/pg_basebackup/pg_createsubscriber.c` — the frontend tool that converts a running physical standby into a logical-replication subscriber: it creates publications/subscriptions on the upstream, sets up the standby's replication slots, and finalizes promotion so the new node continues via logical decoding instead of streaming WAL. [verified-by-code] (via `knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md`).



### pg_cryptohash_create
Allocates and initialises a cryptographic-hash context (MD5/SHA-*) over either the built-in or the OpenSSL backend; each call palloc's a context, so hot callers should reuse one. Paired with `pg_cryptohash_free`. [verified-by-code] (via `knowledge/files/contrib/uuid-ossp/uuid-ossp.c.md`).



### pg_cryptohash_ctx
pgcrypto / backend cryptohash context object holding the in-progress digest state between `init` / `update` / `final`; it is released on every success path by `pg_cryptohash_free`, though the context memory is not explicitly scrubbed (acceptable for plain hashes whose input is application data, not a secret). [verified-by-code] (`cryptohashfuncs.c:128` — via `knowledge/files/src/backend/utils/adt/cryptohashfuncs.c.md`).



### pg_cryptohash_free
Frees a `pg_cryptohash_ctx` created by `pg_cryptohash_create`, releasing the underlying OpenSSL/built-in state; must be called even on the error path to avoid leaking the context. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/cryptohashfuncs.c.md`).



### pg_current_xact_id
Returns the current transaction's 64-bit `FullTransactionId` (the wraparound-safe successor to `txid_current()`), assigning an XID if the transaction has none yet. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/xid8funcs.c.md`).



### pg_database
The cluster-wide (`BKI_SHARED_RELATION`) system catalog with one row per database, holding its name, owner, encoding, locale provider, collation/ctype, connection limit, allow-connections flag, and frozen-xid horizons. The shared nature is why database creation and `datfrozenxid` advancement are cluster-global concerns. [from-comment] (via `knowledge/files/src/include/catalog/pg_database.h.md`).



### pg_database_owner
A predefined, implicit, memberless role whose single effective member is the owner of the current database; it owns the `public` schema by default and is the mechanism behind PG 15+'s locked-down `public`. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_db_role_setting
The system catalog backing `ALTER ROLE/DATABASE ... SET`, with one row per (database, role) pair holding the GUC settings applied at session start for that combination (either is zero for a role-wide or database-wide default). Session startup applies these before the connection is handed to the client. [inferred] (via `knowledge/files/src/include/catalog/pg_db_role_setting.h.md`).



### pg_depend
The system catalog recording dependencies between database objects (one row per dependency edge), so DROP can detect what would break and CASCADE can follow the graph. This file does low-level row CRUD; the actual graph traversal lives in `dependency.c`. [from-comment] (via `knowledge/files/src/backend/catalog/pg_depend.c.md`).



### PG_DETOAST_DATUM
The fmgr macro that returns a fully de-TOASTed (decompressed and inlined) copy of a possibly-compressed/out-of-line `varlena` argument, so a function body can treat it as a flat datum. [verified-by-code] (`btree_gin.c:57-60` — via `knowledge/files/contrib/btree_gin` docs).



### pg_dump
The per-database logical dump driver: from a single connection it collects schema and data, orders objects by their dependency graph, and emits either plain SQL or an archive (custom/directory/tar) for `pg_restore`. It is the largest single C file in `bin/pg_dump` and the canonical "trust the source database" boundary in the corpus. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_dump.c.md`).



### pg_dumpall
The client driver that dumps cluster-wide state not covered by a single-database `pg_dump`: roles (`pg_authid`/`pg_roles`), tablespaces, role memberships, and per-role GUC settings, then invokes `pg_dump` for each database. Because it dumps role definitions it can emit password hashes, so its output is sensitive. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_dumpall.c.md`).



### pg_enum
The system catalog with one row per enum-type label, holding the owning type, the label text, and a sort-order float; it backs CREATE TYPE AS ENUM and ALTER TYPE ADD VALUE. Adding a value mid-transaction uses an "uncommitted enum" mechanism so the new OID is usable only where it is visible. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_enum.c.md`).



### pg_event_trigger_ddl_commands
A built-in set-returning function, callable only inside a `ddl_command_end` event trigger, that returns the list of DDL commands executed in the statement as structured rows (classid, objid, object_type, schema_name, object_identity, in_extension, and a `pg_ddl_command` value). The opaque `pg_ddl_command` entries require C-level deparse to turn into JSON/text for replication, audit, or schema-change history. [verified-by-code] (`event_trigger.c` — via `knowledge/idioms/ddl-deparse-via-event-triggers.md`).



### PG_exception_stack
The thread-global pointer to the innermost active `sigjmp_buf`; `PG_TRY` pushes a new setjmp target onto it, `PG_END_TRY` pops it, and `pg_re_throw`/`ereport(ERROR)` longjmps to it — the mechanism implementing PostgreSQL's TRY/CATCH-style error unwinding. [verified-by-code] (via `knowledge/idioms/error-handling.md`).



### pg_execute_server_program
A predefined role permitting `COPY ... PROGRAM` to run OS commands as the server user; effectively superuser-equivalent and flagged extreme-care by the docs. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_fatal
The frontend (client-program) fatal-error helper: it prints a formatted error
message to stderr and exits the process. It is the libpq-side analogue of a
backend `ereport(FATAL, …)` and appears throughout `pg_dump`, `pg_basebackup`,
and the `fe_utils` code. [verified-by-code] (via
`knowledge/files/src/fe_utils/archive.c.md`).



### pg_file_create_mode
The permission mask (`PG_FILE_MODE_OWNER`, 0600, relaxed to 0640 under group access) the server and frontend tools apply when creating files in the data directory; one of the three `pg_*_create_mode` globals forming the cluster's permission boundary. [verified-by-code] (`file_perm.c:19` — via `knowledge/files/src/common/file_perm.c.md`).



### PG_FINALLY
The unconditional-cleanup arm of a `PG_TRY` block (an alternative to
`PG_CATCH`); its body runs on both the normal and the error path, with the
pending error re-thrown automatically afterward on the error path.
[from-comment] (via `knowledge/idioms/error-handling.md`).



### pg_foreign_server
The system catalog with one row per foreign server (CREATE SERVER), tying a server name to its foreign-data wrapper, type/version, owner, and option array; user mappings and foreign tables reference it. FDWs read its options when establishing a remote connection. [from-comment] (via `knowledge/files/src/include/catalog/pg_foreign_server.h.md`).



### PG_FREE_IF_COPY
The fmgr cleanup macro that frees a detoasted/aligned copy of a varlena argument only if `PG_GETARG_*_P` actually made one (i.e. the pointer differs from the original toast datum), avoiding both leaks and double-frees. Functions that detoast bytea/text arguments are expected to pair each argument with it before returning. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### pg_freespacemap
The contrib module exposing each heap / index page's tracked free-space bytes from the Free Space Map. [from-docs] (via `knowledge/docs-distilled/storage-fsm.md`).



### PG_FUNCTION_ARGS
The macro spelling the fixed signature of every fmgr-callable C function — `(FunctionCallInfo fcinfo)` — so all SQL-callable functions share one calling convention. Argument access (`PG_GETARG_*`, `PG_ARGISNULL`) and result return (`PG_RETURN_*`) macros all operate on the implicit `fcinfo` it introduces. [from-comment] (via `knowledge/idioms/fmgr.md`).



### PG_FUNCTION_INFO_V1
The macro every dynamically-loaded C function must use to emit the `Pg_finfo`
record that tells the fmgr its calling convention is the version-1
(Datum-based) ABI. [verified-by-code] (`fmgr.h:40` — via
`knowledge/idioms/fmgr.md`).



### pg_get_viewdef
The ruleutils function reconstructing a view's defining SELECT (or a rule's action) as SQL text from its stored parse tree, used by `\d`/`psql` and pg_dump. The corpus notes it does not re-emit `WITH (security_barrier/security_invoker/check_option)` view options, so callers relying on it alone can silently lose those clauses. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/ruleutils.c.md`).



### PG_GETARG
The fmgr macro family (`PG_GETARG_INT32`, `PG_GETARG_DATUM`, `PG_GETARG_*_PP`, ...) a C-language SQL function uses to fetch its arguments by position from `FunctionCallInfo`; the `_PP` ("packed pointer") variants avoid detoasting / copying a varlena argument unless the body actually needs the flat value. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### PG_GETARG_INT32
Macro fetching call argument N as a 32-bit int inside a `PG_FUNCTION_ARGS` function (a `DatumGetInt32(PG_GETARG_DATUM(n))`); the per-type argument accessor family backing fmgr v1 functions. [verified-by-code] (via `knowledge/files/contrib/dict_int/dict_int.c.md`).



### pg_global_prng_state
The process-wide pseudo-random number generator state (`pg_prng_state`) seeded at backend start, used by callers that need fast non-cryptographic randomness — e.g. lock-wait jitter and sampling — via the `pg_prng_*` API. Cryptographic needs use `pg_strong_random` instead. [inferred] (`pg_prng.c:34` — via `knowledge/files/src/include/common/pg_prng.h.md`).



### pg_index
The system catalog with one row per index, complementing the index's own pg_class row with the indexed key columns, expression/predicate trees, uniqueness/exclusion flags, and the validity/ready/live state bits that drive concurrent index builds. The planner and executor read it to decide and execute index access. [from-comment] (via `knowledge/files/src/include/catalog/pg_index.h.md`).



### pg_inherits
The catalog (`pg_inherits`) recording table-inheritance and partition parent/child links — one `(inhrelid, inhparent, inhseqno)` row per relationship. The partition helper layer walks it to answer "who is my partition parent / ancestors / default", while the bound storage itself lives in `pg_partitioned_table`. [verified-by-code] (`partition.c:85` — via `knowledge/files/src/backend/catalog/partition.c.md`).



### pg_init_privs
The system catalog snapshotting the "initial" ACL of objects as of initdb (for system objects) or CREATE EXTENSION (for extension-owned objects), so pg_dump can emit only the *delta* between current and initial privileges rather than re-granting defaults. [from-comment] (via `knowledge/files/src/include/catalog/pg_init_privs.h.md`).



### PG_KEYWORD
The macro used in `kwlist.h` (and PL keyword lists) to declare a SQL keyword
together with its token value and category; each includer redefines the
macro to build a different table from the one shared list.
[verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_kwlists.md`).



### pg_language
The system catalog of procedural languages; rows reference the call handler, optional inline handler, and optional validator functions (in `pg_proc`) that implement the language. [verified-by-code] (via `knowledge/files/src/pl/plpgsql` docs).



### pg_largeobject
The system catalog storing large-object contents as rows of up to 2 KB data chunks keyed by LO OID and page number; per-object ownership/ACL metadata lives separately in `pg_largeobject_metadata`. [from-comment] (via `knowledge/files/src/backend/storage/large_object` docs).



### pg_largeobject_metadata
The system catalog with one row per large object, holding its owner and ACL, separate from `pg_largeobject` which stores the object's data in 2 KB chunks. It exists so large objects can have ownership and privileges independent of their byte storage. [inferred] (via `knowledge/files/src/include/catalog/pg_largeobject_metadata.h.md`).



### pg_lfind32
The SIMD-accelerated linear search over a `uint32` array; e.g. `XidInMVCCSnapshot` uses it to probe a snapshot's `subxip`/`xip` xid arrays after the fast-path xmin/xmax range check fails (falling back to `SubTransGetTopmostTransaction` on subxip overflow). [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### pg_locale_t
The opaque handle bundling a collation's locale provider (libc, ICU, or
builtin) with its provider-specific data, returned by `pg_newlocale_from_collation`
and threaded through every locale-sensitive comparison, case-folding, and
formatting routine. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/pg_locale.c.md`).



### pg_locks
The system view exposing the lock manager's currently held and awaited locks — one row per (lock, holder) — covering relation, tuple, transaction, page, and advisory locks. It exposes per-tuple LOCKTAG detail (block + offset) to unprivileged users, which the corpus flags as a monitoring-as-extraction surface. [verified-by-code] (via `knowledge/files/contrib/pgrowlocks/pgrowlocks.c.md`).



### pg_log_backend_memory_contexts
SQL function that signals a target backend (by pid) to dump its `TopMemoryContext` tree to the server log at the next `CHECK_FOR_INTERRUPTS`, via `HandleLogMemoryContextInterrupt` setting a flag consumed by `ProcessLogMemoryContextInterrupt`. [verified-by-code] (`mcxtfuncs.c:266` — via `knowledge/subsystems/utils-mmgr.md`).



### pg_log_error
The frontend logging primitive (and its siblings `pg_log_warning`, `pg_log_info`) that PG client tools and `src/fe_utils` code call to report a diagnostic to stderr without exiting; contrast `pg_fatal`, which logs and then `exit(1)`. The split lets option-parsing helpers return a failure code to the caller after emitting the message rather than aborting the whole program. [verified-by-code] (via `knowledge/files/src/fe_utils/option_utils.c.md`).



### pg_logical_emit_message
The function that writes a logical-decoding message (transactional or not) into
WAL via the `RM_LOGICALMSG_ID` resource manager, letting extensions inject
custom payloads that output plugins can read during decoding. It is the basis
for application-level signalling over logical replication. [verified-by-code]
(via `knowledge/files/src/backend/access/rmgrdesc/logicalmsgdesc.c.md`).



### pg_logicalinspect
A PG17 contrib extension that opens serialized logical-decoding snapshot files (`pg_logical/snapshots/*.snap`) on disk and surfaces their contents as SQL rows via `pg_get_logical_snapshot_meta()` and `pg_get_logical_snapshot_info()` — an inspection aid for debugging logical-replication snapshot state. [verified-by-code] (via `knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md`).



### pg_ls_dir
The SQL function listing a server directory; it (and `pg_stat_file`) are *not* transaction-snapshot consistent, so pg_rewind's `WITH RECURSIVE pg_ls_dir()` source walk can observe files appearing/disappearing mid-scan and tolerates the resulting non-atomicity by skipping vanished files. [from-comment] (via `knowledge/files/src/bin/pg_rewind/libpq_source.c.md`).



### pg_lzcompress
PostgreSQL's built-in LZ-family compressor (`pglz`), the default TOAST
compression method and the codec behind `pglz_compress`/`pglz_decompress`. It is
simple and dependency-free; `lz4`/`zstd` are the optional alternatives selected
per-column via `SET STORAGE`/`default_toast_compression`. [verified-by-code]
(via `knowledge/files/src/include/common/pg_lzcompress.h.md`).



### pg_maintain
A predefined role granting the MAINTAIN privilege (VACUUM/ANALYZE/CLUSTER/REINDEX/REFRESH/LOCK) on all relations cluster-wide. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_malloc
The frontend `malloc` wrapper (`fe_memutils.c`) that aborts with an out-of-memory message on failure, giving client programs and `libpgcommon` code backend-style "allocation never returns NULL" semantics without a memory context. [verified-by-code] (via `knowledge/files/src/common/fe_memutils.c.md`).



### pg_mbcliplen
The multibyte-aware helper that clips a string to at most N bytes without splitting a character mid-encoding; btree_gin uses it to truncate an oversize `text` to `NAMEDATALEN-1` when coercing to `name` (safe in practice mainly because such indexes use C collation). [from-comment] (via `knowledge/files/contrib/btree_gin/btree_gin.md`).



### pg_md5_encrypt
The backend helper that produces the `md5<hex>` shadow-password string by
hashing password+username; retained for the legacy `md5` authentication method
even though SCRAM is now preferred. Found alongside the SCRAM verifier code in
the password-encryption path. [verified-by-code] (via
`knowledge/files/src/backend/libpq/crypt.c.md`).



### pg_md5_hash
The `src/common` routine that MD5-hashes a buffer and writes the result as a hex string (its siblings `pg_md5_binary` and `pg_md5_encrypt` give raw bytes and the `md5`-prefixed password form); legacy MD5 authentication builds its stored verifier with it. [verified-by-code] (`md5_common.c:73` — via `knowledge/files/src/common/md5_common.c.md`).



### PG_MODULE_MAGIC
The macro a loadable C module must place at file scope so the server can
compare an ABI/version fingerprint at load time and refuse `.so` files built
against an incompatible major version. [verified-by-code] (via
`knowledge/idioms/fmgr.md`).



### PG_MODULE_MAGIC_EXT
The extended form of `PG_MODULE_MAGIC` (PG 18) that additionally embeds the extension's name and version into the module-magic block, letting the loader sanity-check that the `.so` matches the SQL-level extension metadata. Modules use one or the other, not both. [inferred] (`_int_op.c:8` — via `knowledge/files/contrib/intarray/_int_op.md`).



### pg_monitor
A predefined (bootstrap) role that grants read access to privileged monitoring
views and functions — including parts of `pg_stat_*`, `pgstattuple`, and other
statistics that are otherwise superuser-only. Granting it avoids handing out
superuser for monitoring. [verified-by-code] (via
`knowledge/files/contrib/pgstattuple/pgstatindex.c.md`).



### pg_multixact
The SLRU subsystem (and `pg_multixact/` directory, split into `offsets` and `members`) storing the membership of each MultiXactId — which transactions share-lock a tuple and with what status. Like the clog it is subject to wraparound and is truncated by vacuum past the cluster's oldest multixact horizon. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### pg_namespace
The system catalog with one row per schema; `NamespaceCreate` writes its tuples for CREATE SCHEMA. This file is only the catalog-row I/O — the search-path resolution machinery that maps unqualified names to namespaces lives in `namespace.c`. [from-comment] (via `knowledge/files/src/backend/catalog/pg_namespace.c.md`).



### pg_node_attr
The no-op annotation macro attached to a Node struct or field in the `nodes/*.h` headers that tells `gen_node_support.pl` how to generate copy/equal/out/read support — e.g. `pg_node_attr(equal_ignore)` or `read_write_ignore`. It is read by the codegen, not the C compiler. [inferred] (via `knowledge/scenarios/add-new-node-type.md`).



### pg_node_tree
The built-in pseudo-type used to store a serialized parse/plan Node tree as text in catalogs (column defaults, check constraints, index expressions, rule actions, view queries). It has no SQL input function for users — values are produced by the backend's nodeToString and read back via stringToNode. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/pseudotypes.c.md`).



### pg_noreturn
The PG18 portability macro placed on functions that never return (they
`ereport(ERROR)`/`exit`/`abort`), replacing the older `pg_attribute_noreturn()`;
it expands to C11 `[[noreturn]]` or a compiler attribute so the optimizer and
static analyzers know control does not come back. [verified-by-code] (via
`knowledge/files/contrib/pgcrypto/px.md`).



### pg_notify
The SQL function form of `NOTIFY`, queuing a (channel, payload) async notification that is delivered to `LISTEN`ing backends at the sender's commit. The queue is an SLRU-backed shared ring drained via signals; see `notify-listen-coordination`. [inferred] (via `knowledge/idioms/notify-listen-coordination.md`).



### pg_opclass
The system catalog with one row per (access method, operator-class name, schema) operator class — the named bundle that ties an input data type to the operators and support functions an index AM uses. Each opclass belongs to an operator family (`pg_opfamily`) and may be the default for its type. [from-comment] (via `knowledge/files/src/include/catalog/pg_opclass.h.md`).



### pg_operator
The system catalog with one row per operator, recording its name, left/right argument types, result type, the implementing function, and commutator/negator links (resolved via shell-operator forward references when needed). `OperatorCreate` is the CREATE OPERATOR backend and records the dependencies. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_operator.c.md`).



### pg_opfamily
The system catalog grouping related operator classes that can interoperate within one index access method (so cross-type comparisons share strategy/support entries); `pg_amop` and `pg_amproc` rows reference an opfamily via `amopfamily`/`amprocfamily`. [verified-by-code] (via `knowledge/files/src/include/catalog/pg_amop.h.md`).



### pg_overexplain
A contrib extension adding two `EXPLAIN` options, `DEBUG` and `RANGE_TABLE`, that dump planner-internal fields normally hidden: disabled-node counts, the parallel_safe flag, plan_node_id, extParam/allParam bitmapsets, and per-RTE metadata. It is the reference consumer of the `explain_per_node_hook` / `explain_per_plan_hook` EXPLAIN extensibility points. [verified-by-code] (via `knowledge/files/contrib/pg_overexplain/pg_overexplain.c.md`).



### pg_parameter_acl
The shared (cluster-wide) catalog `pg_parameter_acl` storing per-GUC access-control lists — the target of `GRANT SET`/`ALTER SYSTEM ON PARAMETER` — checked through `pg_parameter_aclcheck`. As a shared relation it appears in the hardcoded `IsSharedRelation` list alongside `pg_database`, `pg_authid`, and the other global catalogs. [verified-by-code] (`catalog.c:304` — via `knowledge/files/src/backend/catalog/catalog.c.md`).



### pg_parse_json
The JSON lexer/parser driver that tokenizes input and invokes a
`JsonSemAction` callback table, used both by the `json`/`jsonb` input functions
and by ad-hoc internal consumers (manifest parsing, statistics import). The
same parser supports incremental (chunked) parsing. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/jsonb.c.md`).



### pg_parse_query
The tcop entry that runs raw SQL text through the lexer/grammar to a list of raw parse trees, before analysis and planning; the first stage of the parse → analyze → plan → execute pipeline. [verified-by-code] (via `knowledge/architecture/query-lifecycle.md`).



### pg_partitioned_table
The catalog (`pg_partitioned_table`) holding a partitioned relation's partition key — strategy, key columns/expressions, opclasses, and collations — written by `StorePartitionKey` and cleared by `RemovePartitionKeyByRelId` in `heap.c`. It stores the key itself; per-partition bounds live on each child's `pg_class.relpartbound`, and tuple-routing dispatch is built in `partitioning/partbounds.c`. [verified-by-code] (`heap.c:3917` — via `knowledge/files/src/backend/catalog/heap.c.md`).



### pg_plan_advice
A contrib extension implementing a “plan advice” mini-language for steering planner decisions: it can round-trip *generate* advice from a finished plan and *enforce* advice during a later planning cycle. It registers an `EXPLAIN (PLAN_ADVICE)` option, installs planner hooks, and exposes five custom GUCs; the heavy lifting (join/scan advice parsing and matching) lives in sibling `pgpa_*` files. [verified-by-code] [from-README] (via `knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md`).



### pg_plan_query
The tcop wrapper that runs a single analysed-and-rewritten `Query` through the planner (`planner`/`standard_planner`) to produce a `PlannedStmt`; the plan-time counterpart of `pg_parse_query`/`pg_analyze_and_rewrite`. [verified-by-code] (`postgres.c:899` — via `knowledge/files/src/backend/tcop/postgres.c.md`).



### pg_popcount
PostgreSQL's portable population-count (set-bit-count) routine from `port/pg_bitutils.h`, dispatching to a hardware popcount instruction when available; used in hot paths such as GiST signature sizing (`sizebitvec`). [verified-by-code] (`_intbig_gist.c:208-212` — via `knowledge/files/contrib/intarray/_intbig_gist.md`).



### pg_popcount_optimized
The runtime-dispatched fast path of `pg_popcount`, resolved to the best available SIMD implementation for the host (e.g. the AArch64 Neon/SVE variants in `pg_popcount_aarch64.c`) rather than the scalar fallback. [verified-by-code] (via `knowledge/files/src/port/pg_popcount_aarch64.c.md`).



### pg_pread
The PG portability wrapper for positioned reads (`pread`), with `pg_pwrite` for writes; on platforms lacking the syscall it is emulated with seek+read. The vectored `pg_preadv`/`pg_pwritev` helpers loop over `pg_pread`/`pg_pwrite` per iovec when the real `preadv` is unavailable. [verified-by-code] (via `knowledge/files/src/include/port/pg_iovec.md`).



### pg_prng
PostgreSQL's process-local pseudo-random generator, implementing Blackman & Vigna's xoroshiro128** (a small, fast 128-bit-state PRNG) behind `pg_prng_*` calls on a global state. It is explicitly **not** cryptographically strong — security-sensitive randomness must use `pg_strong_random` instead. [verified-by-code] (`pg_prng.c:5-11` — via `knowledge/files/src/common/pg_prng.c.md`).



### pg_prng_state
The state struct (`common/pg_prng.h`) for PostgreSQL's xoroshiro128** pseudo-random generator; it is `PGDLLIMPORT`-exported so extensions share the same backbone, and it is embedded in callers like GEQO's private data and the block/row samplers. [verified-by-code] (`pg_prng.h:35` — via `knowledge/files/src/include/utils/sampling.md`).



### pg_proc
The system catalog with one row per function, procedure, and aggregate (the latter pairs with `pg_aggregate`), holding language, argument/return types, volatility, parallel-safety, cost, and the function body or symbol. `ProcedureCreate` is the universal entry used by CREATE FUNCTION/PROCEDURE/AGGREGATE/OPERATOR. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_proc.c.md`).



### pg_promote
The SQL function `pg_promote()` that promotes a standby to primary (the in-backend equivalent of `pg_ctl promote`), signaling the startup process to end recovery. [from-docs] (via `knowledge/docs-distilled/warm-standby-failover.md`).



### pg_publication
The system catalog (with `pg_publication_rel` and `pg_publication_namespace`) defining logical-replication publications — the set of tables/schemas and the operations published. `pg_publication.c` is the C API behind CREATE/ALTER PUBLICATION and the publishability predicates walsender consults. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_publication.c.md`).



### pg_publication_namespace
The system catalog recording FOR TABLES IN SCHEMA publication memberships (paired with `pg_publication_rel` for individual-table memberships). [verified-by-code] (via `knowledge/files/src/backend/replication/pgoutput/pgoutput.c.md`).



### pg_publication_rel
The system catalog mapping individual tables to the publications they belong to. [verified-by-code] (via `knowledge/files/src/backend/replication/pgoutput/pgoutput.c.md`).



### pg_pwrite
PostgreSQL's portable positioned-write wrapper (counterpart to `pg_pread`): on platforms with real `pwrite` it maps straight through, and on Windows `win32pwrite.c` emulates the offset-write semantics. [verified-by-code] (via `knowledge/files/src/port/win32pwrite.c.md`).



### PG_RE_THROW
The macro that re-raises the in-flight error from inside a `PG_CATCH` block
after cleanup, longjmp-ing control to the next outer `PG_TRY` handler (or to
the top-level abort if none). [verified-by-code] (via
`knowledge/idioms/error-handling.md`).



### pg_read_all_data
A predefined role equivalent to SELECT plus schema USAGE on everything, but still subject to row-level-security policies — RLS exemption is `BYPASSRLS`'s job, not this role's. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_read_all_settings
A predefined role letting members read all GUCs, including superuser-only ones, without holding full superuser. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_read_all_stats
A predefined role unlocking the full `pg_stat_*` monitoring surface; a component granted into the `pg_monitor` composite role. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_read_barrier
The read (acquire) memory-barrier macro that orders loads across a lock-free boundary so a reader does not observe a pointer/index update before the data it guards. It pairs with the writer's `pg_write_barrier`; the shared-memory message queue (`shm_mq`) is the canonical pairing — the reader's `pg_read_barrier` matches the writer's barrier before the byte-count store. [verified-by-code] (`shm_mq.c:2302` — via `knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).



### pg_read_server_files
A predefined (built-in) role granting its members the right to read arbitrary server-side files through SQL-reachable facilities (`COPY FROM`, file_fdw, `pg_read_file`, the basebackup file APIs). Several corpus issues note it as a broad capability whose grantees can reach data outside any single relation's ACLs. [verified-by-code] (via `knowledge/files/contrib/file_fdw/file_fdw.c.md`).



### pg_receivewal
The standalone client that connects in replication mode and streams WAL segments to a local directory (optionally managing a replication slot), used as a low-latency archive substitute or to feed an external consumer. It writes complete segments and can fsync/compress them. [verified-by-code] (via `knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md`).



### pg_recvlogical
A client tool that drives logical decoding over the replication protocol (CREATE_REPLICATION_SLOT / START_REPLICATION ... LOGICAL) to stream a slot's changes to stdout or a file. [from-docs] (via `knowledge/docs-distilled/logicaldecoding-walsender.md`).



### pg_regcomp
PostgreSQL's regex compiler (the Spencer-derived engine) that builds an NFA from a pattern; pg_trgm's per-file register flags that its work is unbounded at the trigram boundary, before the bounded NFA conversion, echoing ltree's `checkCond` catastrophic-backtracking concern. [from-comment] (`source/contrib/pg_trgm/trgm_regexp.c:737-741` — via `knowledge/issues/pg_trgm.md`).



### pg_reload_conf
`pg_reload_conf()` is the SQL function that signals SIGHUP to the postmaster so `PGC_SIGHUP` GUCs are re-read without a restart. [verified-by-code] (via `knowledge/files/contrib/auth_delay/auth_delay.c.md`).



### pg_replication_origin
The system catalog of replication origins — named markers identifying where replicated changes came from, so an apply process can track and skip its own writes and record progress. [from-comment] (via `knowledge/subsystems/replication.md`).



### pg_replslot
The data-directory subdirectory holding one durable state file per replication
slot (`state.dat`), persisting each slot's `restart_lsn`, `xmin`/`catalog_xmin`,
and plugin name across restarts. The slot manager fsyncs these on checkpoint and
on graceful shutdown. [verified-by-code] (via
`knowledge/files/src/backend/replication/slot.c.md`).



### pg_restore
The client driver that reads a `pg_dump` archive (custom/directory/tar format — not plain SQL, which is `psql`'s job) and either prints its table of contents or replays a selected, dependency-ordered subset into a target database. Selective restore and parallel restore are driven from the archive TOC. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_restore.c.md`).



### PG_RETURN_INT32
The fmgr return macro a C `Datum` function uses to hand back a 32-bit integer result, converting the `int32` to a `Datum` for the call protocol; it is the int4 member of the `PG_RETURN_*` family that mirrors the `PG_GETARG_INT32` argument accessors. [verified-by-code] (via `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_sjis/utf8_and_sjis.c.md`).



### pg_rewind
The tool that resynchronizes a diverged former primary with a new primary by copying only the blocks that changed since their histories split, far cheaper than a fresh base backup. Its header exposes the shared config and the helpers spanning `parsexlog.c`, `filemap.c`, and `timeline.c`. [verified-by-code] (via `knowledge/files/src/bin/pg_rewind/pg_rewind.h.md`).



### pg_rewrite
The system catalog with one row per rewrite rule (CREATE RULE), holding the rule's event type, enable flag, INSTEAD flag, optional WHEN qualification, and the action query tree; its primary key is `(ev_class, rulename)`. The rewriter expands these rules — including the ON SELECT rule that backs every view — between parse and plan. [from-comment] (via `knowledge/files/src/include/catalog/pg_rewrite.h.md`).



### PG_RMGR
The X-macro that registers a WAL resource manager in `rmgrlist.h`, binding an `RM_<FOO>_ID` to its redo/desc/identify/startup/cleanup/mask/decode callbacks; a new entry must be appended (never inserted mid-list, since the position is the on-disk rmgr id) and is paired with an `XLOG_PAGE_MAGIC` bump. [verified-by-code] (via `knowledge/scenarios/add-new-wal-record.md`).



### pg_saslprep
The `src/common` implementation of SASLprep (RFC 4013 stringprep) applied to SCRAM passwords before hashing; it normalizes and validates the UTF-8 codepoints, returning a status the caller checks. SASLprep operates on C strings, so callers null-terminate first. [verified-by-code] (via `knowledge/files/src/test/modules/test_saslprep/test_saslprep.c.md`).



### pg_seclabel
The system catalog storing `SECURITY LABEL` assignments for per-database objects, one row per (object, provider), so multiple label providers (e.g. sepgsql plus a custom one) can coexist on the same object via the `provider` column. Shared/global objects use `pg_shseclabel`. [from-comment] (via `knowledge/files/src/include/catalog/pg_seclabel.h.md`).



### pg_serial
The SLRU directory recording SSI serializable-transaction conflict data; like `pg_notify` / `pg_snapshots` it is non-critical and reset on crash recovery rather than WAL-restored. [from-docs] (via `knowledge/docs-distilled/wal-reliability.md`).



### pg_server_to_any
The encoding-conversion helper that converts a string from the server encoding to a requested encoding (returning the input unchanged when they already match); PL/Python relies on the fact that when it does convert to UTF-8 the result is NUL-terminated. [verified-by-code] (via `knowledge/files/src/pl/plpython/plpy_util.md`).



### pg_shdepend
The cluster-wide system catalog recording dependencies on *shared* objects (roles, tablespaces, databases) — e.g. that a role owns or has privileges on objects in some database. It is the only dependency catalog keyed by both `dbid` and the local object, so DROP ROLE/OWNED BY can find references across all databases. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_shdepend.c.md`).



### pg_signal_autovacuum_worker
A predefined role permitting cancel/terminate signals to autovacuum workers — the autovac parallel of `pg_signal_backend`. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_signal_backend
A predefined role permitting `pg_cancel_backend`/`pg_terminate_backend` against other roles' sessions, but deliberately not against superuser-owned backends. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_stash_advice
A companion contrib extension to `pg_plan_advice` that persists captured plan advice across restarts: a background worker serializes the in-shmem advice “stash” to a TSV file (`pg_stash_advice.tsv`) and reloads it at startup, parsing the whole file in private memory and only applying to shared memory on success. [verified-by-code] (via `knowledge/files/contrib/pg_stash_advice/stashpersist.c.md`).



### pg_stat_activity
The system view exposing one row per server process with its state, current/last query text, wait event, and client/application identity. Because the query and `application_name` fields can carry user-influenced strings, several corpus issues flag it as an extraction/spoofing surface. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/option.c.md`).



### pg_stat_all_tables
The cumulative-statistics view exposing per-table access counters (seq / index scans, tuples inserted / updated / deleted, `n_dead_tup`) that drive autovacuum decisions. [verified-by-code] (via `knowledge/architecture/access-methods.md`).



### pg_stat_file
The SQL function returning size/mtime/type metadata for a server file; like `pg_ls_dir` it is not transaction-snapshot consistent, so a recursive directory walk built on it (e.g. pg_rewind's source scan) can see the filesystem change mid-traversal. [from-comment] (via `knowledge/files/src/bin/pg_rewind/libpq_source.c.md`).



### pg_stat_io
The cumulative-statistics view (PG 16+) breaking I/O down by backend type, target object, and context (normal/vacuum/bulkread/bulkwrite), counting reads/writes/extends/hits. It is fed by `pgstat_count_io_op*` calls sprinkled through the storage manager. [inferred] (via `knowledge/scenarios/add-new-buffer-strategy.md`).



### pg_stat_scan_tables
A predefined (default) role granting EXECUTE on monitoring functions that take ACCESS SHARE locks and may scan whole tables (e.g. some pgstattuple functions); `pg_monitor` includes it, so the role hierarchy is `pg_monitor` ⊃ `pg_stat_scan_tables` ⊃ the function grants. [verified-by-code] (via `knowledge/files/contrib/pgstattuple/pgstattuple.c.md`).



### pg_stat_statements
The contrib extension that hooks the planner, executor, and ProcessUtility paths to aggregate per-(userid, dbid, queryid, toplevel) call counts and planning/execution/buffer/WAL metrics, normalizing literals into a canonical query text. It is near-ubiquitous in production; the corpus flags that with `track_utility=on` it can capture cleartext passwords from `CREATE/ALTER ... PASSWORD`. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### pg_stat_subscription_stats
The cumulative-stats view surfacing per-subscription apply-error and conflict counts (with per-conflict-type columns since PG 18). [from-docs] (via `knowledge/docs-distilled/logical-replication-conflicts.md`).



### pg_statistic
The system catalog holding per-(relation, attribute, inheritance) column statistics produced by ANALYZE — null fraction, average width, n-distinct, and slot-encoded most-common-values/histogram/correlation arrays. The planner reads it (via the `pg_stats` view and selectivity estimators) to cost paths; its contents can be sensitive (MCV leakage). [from-comment] (via `knowledge/files/src/include/catalog/pg_statistic.h.md`).



### pg_statistic_ext
The system catalog defining extended statistics objects (ndistinct, dependencies, MCV across multiple columns); the computed values live separately in `pg_statistic_ext_data`. [verified-by-code] (via `knowledge/files/src/backend/statistics` docs).



### pg_statistic_ext_data
The system catalog holding the *computed* values of extended statistics objects (the data side of the `pg_statistic_ext` definitions), populated by ANALYZE. [from-comment] (via `knowledge/files/src/backend/statistics` docs).



### pg_strcasecmp
PostgreSQL's locale-independent ASCII case-insensitive string compare, used for keyword/option matching so behaviour does not shift with the server locale (unlike libc `strcasecmp`). [verified-by-code] (`px-crypt.c:165` — via `knowledge/files/contrib/pgcrypto/px-crypt.md`).



### pg_strdup
The frontend `strdup` wrapper that aborts on OOM; the string-duplicating member of the `pg_malloc`/`pg_realloc`/`pg_strdup` frontend allocation family. [verified-by-code] (via `knowledge/files/src/common/fe_memutils.c.md`).



### pg_strong_random
The portability wrapper generating cryptographically-secure random bytes (from OpenSSL or the OS CSPRNG), used for SCRAM salts and nonces, query-cancel keys, RADIUS authenticators, and `gen_random_uuid()`. It is the strong counterpart to the non-cryptographic `pg_prng`. [verified-by-code] (via `knowledge/files/src/port/pg_strong_random.c.md`).



### pg_subscription
The system catalog of logical-replication subscriptions; the logical replication launcher reads it to start (or restart) the apply worker for each enabled subscription. [verified-by-code] (via `knowledge/subsystems/replication.md`).



### pg_subscription_rel
The system catalog tracking per-relation state within a logical-replication subscription (which tables are being synced and their sync progress); the apply worker re-scans it as tables are added or finish initial copy. [from-comment] (via `knowledge/subsystems/replication.md`).



### pg_subtrans
The SLRU subsystem (and `pg_subtrans/` directory) mapping each subtransaction XID to its immediate parent XID, letting visibility checks walk up to the top-level transaction. Readers consult it because once a subxid is no longer cached in `MyProc`, the parent link lives only here. [verified-by-code] (via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### pg_tablespace
The system catalog with one row per tablespace, mapping a tablespace OID to its on-disk location. This catalog file is tiny — just the directory-existence check used by CREATE TABLESPACE; the substantive tablespace logic lives in `commands/tablespace.c`. [from-comment] (via `knowledge/files/src/backend/catalog/pg_tablespace.c.md`).



### pg_tblspc
The data-directory subdirectory of symlinks, one per non-default tablespace,
pointing at the external storage location; base backups must recreate these
links (or remap them via `--tablespace-mapping`) when restoring. [verified-by-code]
(via `knowledge/files/src/fe_utils/astreamer_file.c.md`).



### pg_trgm
The trigram contrib module providing similarity matching and `LIKE`/regex index acceleration. It breaks strings into three-character trigrams, defines `%` similarity and distance operators, and ships GIN/GiST opclasses so fuzzy and pattern searches can use an index instead of a sequential scan. [verified-by-code] (via `knowledge/files/contrib/pg_trgm/trgm_op.c.md`).



### pg_trigger
The system catalog with one row per trigger (including system-generated constraint triggers), recording the firing function, BEFORE/AFTER/INSTEAD timing, ROW/STATEMENT level, the triggering events, and any column list or WHEN qualification. The executor reads it to build a relation's trigger descriptor. [from-comment] (via `knowledge/files/src/include/catalog/pg_trigger.h.md`).



### pg_truncate_visibility_map
A destructive `pg_visibility` SQL function that drops a relation's visibility-map fork; it takes `AccessExclusiveLock` and is intended for corruption recovery, not normal operation. [verified-by-code] (`source/contrib/pg_visibility/pg_visibility.c:370` — via `knowledge/files/contrib/pg_visibility/pg_visibility.c.md`).



### PG_TRY
The opening macro of PostgreSQL's structured exception-handling idiom; it
establishes a sigsetjmp landing pad so a later `ereport(ERROR)` longjmps back
here instead of unwinding the C stack by hand. It pairs with `PG_CATCH`
(cleanup on the error path) or `PG_FINALLY` (cleanup on both paths) and a
closing `PG_END_TRY`. [verified-by-code] (`elog.h:242` — via
`knowledge/idioms/error-handling.md`).



### pg_type
The system catalog with one row per data type (base, composite, domain, enum, range, multirange, array, pseudo), recording length, by-value-ness, alignment, storage, the input/output/send/receive functions, and the element/array links. `TypeCreate` is the universal type-row writer; `TypeShellMake` creates the forward-reference shell for mutually-recursive types. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_type.c.md`).



### pg_unreachable
A macro marking a code point the compiler should treat as never reached (after an exhaustive `switch` or a `noreturn` call); it expands to a compiler builtin in production and to `Assert(false)` under `--enable-cassert`. Omitting it after a full switch is a common style nit. [from-comment] (via `knowledge/files/contrib/pg_plan_advice/pgpa_walker.c.md`).



### pg_upgrade
The tool that performs an in-place major-version upgrade by dumping only the old cluster's schema, restoring it into the new cluster, then copying/linking/cloning the relation files and fixing the xid/multixact/oid counters — avoiding a full dump+reload of the data. Its `main()` is a linear pipeline with no dispatch table. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md`).



### pg_usleep
The portable microsecond-sleep helper used inside the backend (e.g. lock-retry
backoff, the `auth_delay` extension, vacuum delays). It is interruptible by
signals and is the standard way backend C code waits a short, fixed interval.
[verified-by-code] (via `knowledge/files/contrib/auth_delay/auth_delay.c.md`).



### PG_UTF8
PostgreSQL's internal encoding identifier for UTF-8; conversion helpers like `pg_any_to_server(..., PG_UTF8)` and `pg_server_to_any(..., PG_UTF8)` use it to transcode between the server encoding and UTF-8, raising on malformed sequences. [verified-by-code] (via `knowledge/files/contrib/fuzzystrmatch/daitch_mokotoff.c.md`).



### pg_verifymbstr
The backend encoding validator that checks a string is well-formed in the server encoding, raising an error on the first invalid byte sequence; conversion and PL type-input paths call it as the final gate before a string is trusted as server-encoded text. [verified-by-code] (`plpy_typeio.c:1067` — via `knowledge/files/src/pl/plpython/plpy_typeio.md`).



### PG_VERSION_NUM
The compile-time integer encoding of the server version (e.g. 170004 for 17.4) used by extensions and tools in `#if` guards to conditionally compile against API changes across major versions. It complements the human-readable `PG_VERSION` string. [inferred] (via `knowledge/files/src/fe_utils/version.c.md`).



### pg_wal
The cluster subdirectory holding the write-ahead log segment files (and `pg_wal/archive_status`), formerly named `pg_xlog`. WAL is written here first and only later applied to data files; archiving and streaming replication both read from it, and unbounded retention here (e.g. an abandoned slot) can fill the filesystem. [inferred] (via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`; see `knowledge/architecture/wal.md`).



### pg_waldump
The CLI that decodes and prints WAL records from segment files for debugging, using each resource manager's rmgrdesc routine to render record contents. The contrib `pg_walinspect` extension is its in-process, SQL-callable counterpart. [verified-by-code] (via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`).



### pg_wchar
PostgreSQL's wide-character representation and the multibyte-encoding abstraction layer (`pg_wchar.h`) providing per-encoding character-length, validation, and conversion routines (`pg_mblen`, `pg_mbstrlen`, verifymbstr). All encoding-aware text processing routes through it rather than assuming single-byte characters. [verified-by-code] (via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### pg_wcsformat
The `src/fe_utils/mbprint.c` routine that renders a (possibly multibyte) string into a `struct lineptr[]` array, expanding `\r`/`\t`/control characters and setting each line's display width; it must stay byte-for-byte in sync with `pg_wcssize`, which pre-computes the same widths and buffer size. [verified-by-code] (`mbprint.c:294` — via `knowledge/files/src/fe_utils/mbprint.c.md`).



### pg_wcssize
The `src/fe_utils/mbprint.c` companion to `pg_wcsformat`: it computes the longest-line width, the line count (height), and the bytes needed for the formatted form of a string, so psql can size its output buffer before rendering. The two functions encode the same expansion rules and must be edited together. [verified-by-code] (`mbprint.c:211` — via `knowledge/files/src/fe_utils/mbprint.c.md`).



### pg_write_all_data
A predefined role equivalent to INSERT/UPDATE/DELETE on everything, still subject to row-level-security policies. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_write_barrier
The macro emitting a store-store memory barrier so writes issued before it become visible to other CPUs before writes after it. Lock-free shared-memory producers (e.g. publishing a fully-initialized struct, then a pointer to it) pair it with `pg_read_barrier` on the consumer. [inferred] (`procarray.c:2215` — via `knowledge/subsystems/storage-ipc.md`).



### pg_write_server_files
A predefined role permitting server-side file writes (e.g. `COPY TO` a server path) that bypass database-level permission checks; effectively superuser-equivalent. [from-docs] (via `knowledge/docs-distilled/predefined-roles.md`).



### pg_xact
The cluster subdirectory (and SLRU) storing transaction commit/abort status — two bits per transaction id — formerly named `pg_clog`. Visibility checks consult it via `TransactionIdDidCommit`, but only *after* `TransactionIdIsInProgress`, because `xact.c` records commit in pg_xact before clearing `MyProc->xid`. [from-comment] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### PgAioHandle
The per-in-flight-operation handle of the AIO subsystem: it tracks one asynchronous I/O from staging through submission to completion, carrying the target, the callback chain, and the result so a backend can later wait on or reap it. [verified-by-code] (`aio.c` — via `knowledge/files/src/backend/storage/aio/aio.c.md`).



### PgAioWaitRef
A compact reference to an in-flight asynchronous I/O operation; e.g. `BufferDesc.io_wref` is a `PgAioWaitRef` that is valid only while an AIO on that buffer is in progress, so waiters can locate and await the operation. [verified-by-code] (via `knowledge/files/src/include/storage/buf_internals.h.md`).



### PgBackendStatus
The per-backend status slot in the shared `BackendStatusArray` that powers `pg_stat_activity`: it holds the current query string, state, wait event, activity timestamps, and client info, updated by the owning backend with a changecount protocol. [verified-by-code] (via `knowledge/files/src/backend/utils/activity/backend_status.c.md`).



### PGC_POSTMASTER
The most restrictive `GucContext`: a variable so marked can only be set at
server start (command line or `postgresql.conf` read by the postmaster) and
cannot be changed by reload or `SET`. [verified-by-code] (via
`knowledge/idioms/guc-variables.md`).



### PGC_SIGHUP
The GUC context level for parameters that can be changed at server reload
(SIGHUP) but not per-session — they may be set in `postgresql.conf` and take
effect on `pg_reload_conf()`, but `SET` rejects them. One of the `GucContext`
values that gates where each GUC is settable. [verified-by-code] (via
`knowledge/idioms/guc-variables.md`).



### PGC_SUSET
The GUC context level for settings that only a superuser (or a role granted
`SET` on them) may change at run time within a session — e.g. pgcrypto's
`pgcrypto.builtin_crypto_enabled`. It sits between `PGC_SIGHUP` (config-file
only) and `PGC_USERSET` (any user) in the privilege ladder. [verified-by-code]
(via `knowledge/files/contrib/pgcrypto/pgcrypto.md`).



### PGC_USERSET
The GUC context level marking a parameter any user may change at any time
within a session (the most permissive level); the context constrains who may
`SET` the variable and when. [verified-by-code] (`guc.h:71-80` — via
`knowledge/idioms/guc-variables.md`).



### PGconn
The opaque libpq client-side connection-handle struct returned by `PQconnectdb`/`PQsetdbLogin`; it holds the socket, the connection parameters, the negotiated protocol and the most recent error message. Callers treat it as a black box and pass it to every `PQ*` call until `PQfinish` frees it. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-connect.c.md`).



### PGDATA
The data directory — the filesystem root of a database cluster holding base/, global/, pg_wal/, the config files, and PG_VERSION. Also the environment variable / -D option naming it, consulted by initdb, the postmaster, and every standalone tool. [verified-by-code] (via `knowledge/files/src/bin/initdb/initdb.c.md`).



### PGDLLEXPORT
The Windows-port marker macro placed on a function declaration to force its symbol to be exported from a backend DLL; on non-Windows builds it expands to nothing. Extensions annotate their hook-installed callbacks and SQL-callable entry points with it so dynamic lookup succeeds on Windows. [verified-by-code] (via `knowledge/files/contrib/pg_plan_advice/pg_plan_advice.h.md`).



### PGDLLIMPORT
The symbol-visibility macro that must annotate every backend global variable an extension may reference, so the symbol is exported from the backend's import library on Windows; without it a global links fine on ELF platforms but fails to resolve in extensions on Windows. [verified-by-code] (via `knowledge/files/src/backend/catalog/objectaccess.c.md`).



### PgFdwConnState
The per-connection state postgres_fdw hangs off each cached libpq connection, tracking whether an async request is in flight so one remote connection is not driven by two foreign scans at once. [verified-by-code] (`connection.c` — via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### PgFdwRelationInfo
The `fdw_private` struct postgres_fdw attaches to every base/join/upper `RelOptInfo` it plans, caching pushdown decisions, remote conditions, cost estimates, and the user mapping for that relation. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.h.md`).



### PGJIT_DEFORM
The JIT compile-flag bit (`jit.h:19-24`) requesting that tuple deforming be JIT-compiled; a separate bit from `PGJIT_EXPR` (expressions), `PGJIT_INLINE` (inline small function bodies), and `PGJIT_OPT3` (LLVM `-O3`). The developer GUC `jit_tuple_deforming` toggles this bit 1:1. [verified-by-code] (via `knowledge/docs-distilled/jit-reason.md`).



### PGJIT_EXPR
One of the JIT bit-flags (alongside `PGJIT_PERFORM`, `PGJIT_OPT3`, `PGJIT_INLINE`, `PGJIT_DEFORM`) chosen by the planner per query and passed as an OR-bitmask in `JitContext.flags`. It requests JIT compilation of expressions; a typical "compile, no inline, no -O3" combination is `PGJIT_PERFORM | PGJIT_EXPR | PGJIT_DEFORM`. [verified-by-code] (`jit.h` — via `knowledge/files/src/include/jit/jit.h.md`).



### PGJIT_INLINE
One of the per-query JIT bit-flags (alongside `PGJIT_NONE`, `PGJIT_PERFORM`, `PGJIT_OPT3`, `PGJIT_EXPR`, `PGJIT_DEFORM`) chosen by the planner to request that the JIT provider inline the bodies of called functions into generated code. The inlining time it controls is one of the five `instr_time` counters tracked in `JitInstrumentation`. [verified-by-code] (`jit.h` — via `knowledge/files/src/include/jit/jit.h.md`).



### PGJIT_NONE
The zero-valued JIT compile flag (`jit.h:19-24`) meaning no JIT work is requested; the base of the `PGJIT_*` bit family (`PERFORM`/`EXPR`/`DEFORM`/`INLINE`/`OPT3`) that a plan's cost gates OR together to decide how much JIT a query earns. [verified-by-code] (via `knowledge/docs-distilled/jit-reason.md`).



### PGJIT_OPT3
A JIT bit-flag (`0x02`, `1<<1`) set by the planner when cost exceeds `jit_optimize_above_cost` (default 500000); it requests that the provider apply LLVM `-O3` optimization (expensive). It is consulted only by the provider, not by provider-agnostic `jit.c` — `llvmjit.c` keeps two LLJIT instances (`llvm_opt0_orc` / `llvm_opt3_orc`) and `llvm_compile_module` picks `LLVMCodeGenLevelAggressive` vs `None` based on this flag; it is independent of `PGJIT_INLINE`. [verified-by-code] (`jit.md` — via `knowledge/subsystems/jit.md`).



### PGJIT_PERFORM
The master JIT bit-flag (`0x01`, `1<<0`) in `JitContext.flags`/`es_jit_flags`, set by the planner when a query's estimated cost exceeds `jit_above_cost` (default 100000) to request that any JIT be done at all. `jit_compile_expr` short-circuits to false if `!(es_jit_flags & PGJIT_PERFORM)`, and expression JIT requires `PGJIT_PERFORM | PGJIT_EXPR` both set. [verified-by-code] (`jit.md` — via `knowledge/subsystems/jit.md`).



### pgoutput
The built-in logical-decoding output plugin that backs native publish/subscribe replication; the apply side loads it by the name `pgoutput` whenever a subscription's walsender connects. [from-comment] (via `knowledge/files/src/backend/replication/pgoutput` docs).



### pgp_pub_decrypt
The pgcrypto SQL function that decrypts an OpenPGP message with a public-key (asymmetric) secret key; its `keypkt` argument is attacker-influenceable, which the per-file issue register flags as a security concern. The symmetric counterpart is `pgp_sym_decrypt`. [from-comment] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### pgp_sym_decrypt
The pgcrypto SQL entry point that decrypts an OpenPGP symmetric-key (passphrase) message (`pgp_sym_encrypt` is its counterpart); the passphrase is turned into a session key through the S2K key-derivation path. [from-comment] (via `knowledge/files/contrib/pgcrypto/pgp-s2k.md`).



### PGPROC
The per-process shared-memory slot describing a backend to the rest of the
system. Every backend is assigned exactly one `PGPROC` from
`ProcGlobal->allProcs` at startup and returns it to a freelist at exit; it
holds the proc's wait state, LSNs, and lock links, and is how other backends
find and signal it. [verified-by-code] (`proc.h:184` — via
`knowledge/files/src/include/storage/proc.h.md`).



### PGPROC_MAX_CACHED_SUBXIDS
The cap (64) on how many subtransaction XIDs a backend caches inline in its `PGPROC` (the `XidCache.xids[]` array). When a backend exceeds this many live subxids the cache is marked overflowed, after which other backends must fall back to the SubTrans SLRU to resolve that backend's subxids. [verified-by-code] (`proc.h` — via `knowledge/idioms/subxact-xidcache-and-pgproc.md`).



### PGRES_COMMAND_OK
One of the libpq `ExecStatusType` result-status values, indicating a command that returned no tuples completed successfully. In fe-protocol3.c it is the status built for `CommandComplete` ('C'), and for `ParseComplete`/`CloseComplete`/`NoData` when the corresponding prepare/close/describe request is in flight. [verified-by-code] (`fe-protocol3.c.md` — via `knowledge/files/src/interfaces/libpq/fe-protocol3.c.md`).



### PGRES_TUPLES_OK
One of the libpq `ExecStatusType` result-status values, indicating a command completed successfully and returned tuples (a row-returning query). Frontend tools commonly require this status before reading rows, treating anything else as failure. [verified-by-code] (`libpq-fe.h.md` — via `knowledge/files/src/interfaces/libpq/libpq-fe.h.md`).



### PGresult
The opaque libpq object that carries the outcome of one command — result status, the row/column tuple data, and any server error fields. It is heap-allocated independently of the `PGconn` and must be released with `PQclear` to avoid leaks. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### pgs_mask
The pg_plan_advice "path generation strategy" bitmask: the planner hook clears bits in `pgs_mask` to forbid specific path-building strategies, steering the optimizer toward the advised plan shape. [from-comment] (via `knowledge/files/contrib/pg_plan_advice/pgpa_planner.c.md`).



### PGSemaphore
The backend's portable semaphore abstraction (a pointer to a platform-specific struct) used to implement blocking waits for latches, LWLock contention fallback, and ProcArray sleeps. Backends are each handed one from a shared array at startup. [inferred] (via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### PGSemaphoreLock
Decrements a `PGSemaphore`, blocking if the count would go negative — the portable semaphore-wait primitive underlying latches and some lock waits, with SysV / POSIX / win32 backend implementations. [verified-by-code] (`pg_sema.h:24` — via `knowledge/files/src/include/storage/pg_sema.h.md`).



### PGShmemHeader
The header at the start of the main shared-memory segment recording its total size, the free-space offset, and the dynamic-shmem control area; `PGSharedMemoryIsInUse` also reads it (via the key/id) to detect whether a segment is still owned by a live cluster. [verified-by-code] (`shmem.c:224-272` — via `knowledge/subsystems/storage-ipc.md`).



### pgstat_count_io_op
The fast inline path that bumps a backend's per-`(object, context, op)` I/O counters; `pgstat_count_io_op_time` additionally records timing, called from `bufmgr.c` around reads/writes/extends. [verified-by-code] (via `knowledge/files/src/backend/utils/activity/pgstat_io.c.md`).



### pgstat_count_io_op_time
The timing-aware variant of `pgstat_count_io_op` that records an I/O operation against a given (`io_object`, `io_context`, `io_op`) along with elapsed time measured from a start timestamp, plus operation count and byte total. Its timing brackets pair with `pgstat_prepare_io_time` / `pgstat_get_io_time_now`. [verified-by-code] (`pgstat_io.c` — via `knowledge/files/src/backend/utils/activity/pgstat_io.c.md`).



### PgStat_Counter
The `int64` typedef for a cumulative-statistics counter in the pgstat subsystem; every per-object metric (block reads, tuples returned, WAL bytes, …) is a PgStat_Counter accumulated in a backend's pending stats and periodically flushed to shared memory / the stats file. [verified-by-code] (via `knowledge/files/src/backend/utils/activity/pgstat_lock.c.md`).



### PGSTAT_FILE_FORMAT_ID
The version stamp written at the head of the cumulative-statistics file (`pg_stat/`); the stats subsystem refuses to load a file whose id does not match the running server, discarding stale stats rather than misreading them. Changing the on-disk stats layout requires bumping it. [inferred] (`pgstat.h:221` — via `knowledge/files/src/include/pgstat.h.md`).



### pgstat_get_wait_event
The core function that decodes a backend's packed `wait_event_info` integer (read from `PGPROC` or exposed as `pg_stat_activity.wait_event`) into the human-readable wait-event name; its sibling `pgstat_get_wait_event_type` returns the category. Sampling extensions such as pg_wait_sampling reuse these to label the wait field they read straight out of each `PGPROC`. [from-comment] (via `knowledge/ideologies/pg_wait_sampling.md`).



### pgstat_get_wait_event_type
The core function returning the *category* of a packed `wait_event_info` value (LWLock, Lock, BufferPin, IO, IPC, Timeout, …); paired with `pgstat_get_wait_event` (which returns the specific event name) to render `pg_stat_activity.wait_event_type` and `wait_event`. [from-comment] (via `knowledge/ideologies/pg_wait_sampling.md`).



### PgStat_KindInfo
The per-statistics-kind descriptor (a callback vtable plus size/flags) registered in the pgstat subsystem; it tells the cumulative-stats machinery how to size, fixed-or-variable, flush, and serialize entries of one stats kind, enabling pluggable custom stats. [verified-by-code] (via `knowledge/files/src/include/utils/pgstat_internal.md`).



### PGSTAT_MIN_INTERVAL
The minimum interval (1 s) between flushes of pending cumulative statistics to shared memory; pgstat force-flushes sooner only when accumulated pending updates exceed a threshold. [verified-by-code] (via `knowledge/files/src/backend/utils/activity/pgstat.c.md`).



### pgstat_register_kind
The extension entry point (`pgstat.c:1508`) that registers a custom cumulative-statistics kind with its shmem/flush callbacks, letting out-of-core code participate in the pgstat framework (see test_custom_stats). [verified-by-code] (via `knowledge/files/src/backend/utils/activity/pgstat.c.md`).



### pgstat_report_stat
The cumulative-statistics flush workhorse: it pushes a backend's pending stats into shared memory, requires being outside a transaction, and is throttled — returning the number of milliseconds until the next call is due. [verified-by-code] (`pgstat.c:723` — via `knowledge/files/src/backend/utils/activity/pgstat.c.md`).



### pgstat_report_wait_end
Clears the current backend's wait event after a sleep/IO/lock completes; paired with `pgstat_report_wait_start`, and called in auxiliary-process cleanup (`LWLockReleaseAll`, `ConditionVariableCancelSleep`, `pgstat_report_wait_end`). [verified-by-code] (via `knowledge/files/src/backend/utils/activity/wait_event.c.md`).



### pgstat_report_wait_start
Sets the current backend's wait event (visible in `pg_stat_activity.wait_event`); `perform_spin_delay` calls `pgstat_report_wait_start(WAIT_EVENT_SPIN_DELAY)` only once it is actually sleeping, since reporting every busy spin would dominate profiling overhead. [from-comment] (via `knowledge/files/src/backend/utils/activity/wait_event.c.md`).



### pgtypes_alloc
The ECPG pgtypeslib allocator: `calloc(1L, size)` returning zero-filled memory, setting `errno = ENOMEM` and returning NULL on failure — the standard allocation entry for the date/time/numeric/interval helper library. [verified-by-code] (via `knowledge/files/src/interfaces/ecpg/pgtypeslib/common.c.md`).



### pgtypes_fmt_replace
An internal ECPG pgtypeslib helper that performs format-string substitution for date/time formatting, keyed by a `replace_type` switch over the `PGTYPES_TYPE_*` selector tags; it works through a `union un_fmt_comb` discriminated value. [verified-by-code] (`pgtypeslib_extern.h:12-24` — via `knowledge/files/src/interfaces/ecpg/pgtypeslib/pgtypeslib_extern.h.md`).



### pgwin32_signal_event
The Windows event object PostgreSQL's emulated-signal layer sets to wake a process for pending signals; its ordering relative to semaphore operations matters in the win32 semaphore implementation. [from-comment] (via `knowledge/files/src/backend/port/win32_sema.c.md`).



### pgxactoff
A backend's dense offset into the ProcArray's parallel arrays of transaction status (xid, subxid summary, vacuumFlags); `GetSnapshotData` iterates by `pgxactoff` over these cache-friendly arrays rather than chasing PGPROC pointers. [verified-by-code] (via `knowledge/idioms/subxact-visibility-and-overflow.md`).



### ph_node
The `pairingheap_node` embedded in a `SnapshotData`, used together with the `active_count`/`regd_count` refcounts by snapmgr.c to order registered snapshots in a pairing heap so the oldest still-registered xmin can be found cheaply. [verified-by-code] (via `knowledge/files/src/include/utils/snapshot.h.md`).



### PickSplit
The GiST/SP-GiST opclass support function that, when a page overflows, decides
how to partition its entries between the two resulting pages — the quality of
this split governs index shape and search efficiency. [verified-by-code] (via
`knowledge/docs-distilled/spgist.md`).



### PinBuffer
Increments a buffer's pin count (and bumps its usage count) so the clock-sweep
cannot evict it while a backend holds a reference; every buffer access must
pin before touching the page. [verified-by-code] (`bufmgr.c:3280-3372` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### pl_comp
`src/pl/plpgsql/src/pl_comp.c` — the PL/pgSQL function *compiler*: `plpgsql_compile` parses a function body once (driving `pl_gram.y`), resolves variable/type/row datums, and caches the resulting `PLpgSQL_function` keyed on function OID + argument types, so later calls skip re-parsing. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### pl_exec
`src/pl/plpgsql/src/pl_exec.c` — the PL/pgSQL statement *executor*: it walks the compiled `PLpgSQL_stmt` tree (`exec_stmt` dispatch), evaluates expressions via SPI, manages the variable estate and `FOUND`/diagnostics, and implements `EXCEPTION` blocks through internal subtransactions. The largest file in the PL/pgSQL handler. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### pl_funcs
`src/pl/plpgsql/src/pl_funcs.c` — PL/pgSQL support utilities: namespace (`ns_*`) push/pop and name lookup used during compilation, statement-type name strings, and the `free_function` memory teardown. The plumbing the compiler and executor lean on rather than a parse or execution stage itself. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_funcs.md`).



### pl_gram
`src/pl/plpgsql/src/pl_gram.y` — the Bison grammar for the PL/pgSQL procedural language: it parses a function body into the `PLpgSQL_stmt` tree, treating embedded SQL/expressions as opaque token runs handed to the main SQL parser later. Paired with the `pl_scanner.c` lexer. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_gram.md`).



### pl_handler
`src/pl/plpgsql/src/pl_handler.c` — the PL/pgSQL language glue: `plpgsql_call_handler` (the `LANGUAGE plpgsql` entry point that compiles then executes), `plpgsql_inline_handler` (DO blocks), `plpgsql_validator` (CREATE FUNCTION checking), and `_PG_init` defining the `plpgsql.*` GUCs. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



### pl_scanner
`src/pl/plpgsql/src/pl_scanner.c` — the PL/pgSQL lexer wrapper around the core SQL flex scanner, adding PL/pgSQL-only keyword recognition and the pushback buffer that `pl_gram.y` uses to look ahead. It reuses `scan.l` token rules so PL/pgSQL and SQL stay lexically consistent. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_scanner.md`).



### plain_crypt_verify
The password-auth verifier (paired with `encrypt_password`) that checks a client-supplied plaintext or hash against a stored MD5 / SCRAM verifier. [from-docs] (via `knowledge/docs-distilled/auth-password.md`).



### Plan
The finished, executable tree produced by `create_plan` from the chosen Path —
a tree of plan nodes (`SeqScan`, `HashJoin`, `Agg`, …) carrying target lists,
qualifications, and cost estimates but no live execution state. The executor
instantiates it into a parallel `PlanState` tree at `ExecutorStart`. [inferred]
(via `knowledge/files/src/include/nodes/plannodes.h.md`).



### plan_cache_mode
The GUC (enum `PlanCacheMode`: `AUTO` / `FORCE_GENERIC_PLAN` / `FORCE_CUSTOM_PLAN`) read inside `choose_custom_plan` to override the plancache's automatic generic-vs-custom decision on a per-session basis. [verified-by-code] (`plancache.h:31` — via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### PlanCacheRelCallback
The relcache-invalidation callback registered by the plan cache; on a relevant
relation change it sets `is_valid = false` on the affected CachedPlanSource (and
its generic plan) without destroying anything, deferring the actual replan to
the next `GetCachedPlan`. [verified-by-code] (`plancache.c:2126` — via
`knowledge/subsystems/utils-cache.md`).



### PlanCacheSysCallback
The plancache syscache-invalidation callback (`plancache.c:2319`) registered for coarse-trigger caches (`NAMESPACEOID`, `OPEROID`, `AMOPOPID`, `FOREIGNSERVEROID`, `FOREIGNDATAWRAPPEROID`); rather than tracking fine-grained dependencies it simply calls `ResetPlanCache`, choosing cheap blanket correctness over per-plan tracking. It contrasts with `PlanCacheObjectCallback` (PROCOID/TYPEOID) and `PlanCacheRelCallback`, which mark only the affected sources invalid. [verified-by-code] (`plancache.c:2319` — via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### PlanDirectModify
The optional `FdwRoutine` callback enabling the direct-modify optimization: when an UPDATE/DELETE can be pushed entirely to the remote side, it replaces the ModifyTable+ForeignScan pair with a single foreign statement executed via `Begin/Iterate/EndDirectModify`. [verified-by-code] (via `knowledge/subsystems/foreign.md`).



### PlanForeignModify
The FDW callback invoked at plan time for `INSERT`/`UPDATE`/`DELETE` on a foreign table; it returns FDW-private state (e.g. the remote SQL) that the later `BeginForeignModify`/`ExecForeignInsert` execution callbacks consume. [from-comment] (via `knowledge/files/src/include/foreign/fdwapi.h.md`).



### PlanInvalItem
A cached-plan dependency record `{int cacheId; uint32 hashValue;}` naming one syscache row a plan depends on; when a matching invalidation arrives, plancache marks the plan stale and forces re-planning. [verified-by-code] (`plancache.c:34` — via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### PlannedStmt
The top node of a finished plan handed from planner to executor: it wraps the
plan tree plus the range table, result-relation list, command type, and
`hasReturning`/`canSetTag` flags. `ProcessUtility` vs the executor branch on
whether a statement produces a `PlannedStmt`. [verified-by-code] (`utility.c:96`
— via `knowledge/subsystems/tcop.md`).



### planner
The optimizer stage that turns a `Query` into an executable `Plan` tree.
`planner()` / `standard_planner()` drive `subquery_planner` on the top query,
enumerate and cost candidate Paths, pick the cheapest, and hand it to
`create_plan` to materialize the final plan. [verified-by-code] (via
`knowledge/files/src/backend/optimizer/plan/planner.c.md`).



### planner_hook
The global function pointer that lets an extension intercept or wholly replace `standard_planner`, e.g. to inject hints or substitute a cached plan. Chained extensions save the previous value and call through it. [inferred] (via `knowledge/files/src/backend/optimizer/plan/planner.c.md`).



### PlannerGlobal
The planner's per-statement global state, shared across all subquery levels of one planning run — it accumulates the final range table, the relations and PlanInvalItems the plan depends on, subplans, and parallel-safety flags that go into the finished PlannedStmt. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### PlannerInfo
The central planner working struct (the "query level"): it holds the join-tree,
the `RelOptInfo` array, equivalence classes, and accumulated paths for one query
or subquery level. Almost every optimizer routine takes a `PlannerInfo *root`.
[verified-by-code] (`analyzejoins.c:1869` — via
`knowledge/subsystems/optimizer.md`).



### PlanState
The per-execution mutable mirror of a `Plan` node: `ExecInitNode` builds a
`PlanState` tree shadowing the `Plan` tree, holding tuple slots, expression
states, and instrumentation, and `ExecProcNode` pulls tuples through it. Plan
is read-only and shareable; PlanState is per-execution. [inferred] (via
`knowledge/files/src/include/nodes/execnodes.h.md`).



### plpgsql_estate_setup
The PL/pgSQL routine that initializes a `PLpgSQL_execstate` for a function/DO/CALL invocation, wiring in the shared simple-expression `EState` (`simple_eval_estate`) among other per-call execution context. [from-comment] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### PLpgSQL_execstate
The per-call runtime state of an executing PL/pgSQL function, set up by `plpgsql_exec_function` (`pl_exec.c:493`): the datum array, argument install, the `plpgsql_exec_error_callback` traceback frame, and fields like `cur_error` (the matched EXCEPTION's error, read by `GET STACKED DIAGNOSTICS` and bare `RAISE`). Passed to the `PLpgSQL_plugin` callbacks so instrumentation can inspect live execution. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### PLpgSQL_expr
The PL/pgSQL node wrapping one SQL expression or query embedded in a function body; `plpgsql_parser_setup` wires the main parser's param hooks to it so `$n` references resolve to PL/pgSQL variables at parse-analyze time. [verified-by-code] (`pl_comp.c:25` — via `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### plpgsql_free_function_memory
The PL/pgSQL routine that releases a compiled `PLpgSQL_function`'s memory — its SPI plans and the function's parse-tree storage — when the function cache evicts or invalidates the entry; `funccache.c` calls it as the free callback. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_funcs.md`).



### PLpgSQL_function
The compiled in-memory AST of a PL/pgSQL function produced by `pl_comp.c`: the namespace, the `datums[]` variable array, and the statement tree that `exec_stmt_*` walks; the language handler caches it and hands it to `plpgsql_exec_function`. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### PLpgSQL_plugin
The PL/pgSQL instrumentation hook table (`plpgsql.h:1124`): a plugin (debugger/profiler such as pldebugger or plpgsql_check) sets the first five callbacks (`func_setup`/`func_beg`/`func_end`/`stmt_beg`/`stmt_end`) in its `_PG_init`, and PL/pgSQL fills in the next five (`error_callback`, `assign_expr`, `assign_value`, `eval_datum`, `cast_value`) so the plugin can reuse interpreter internals. Both sides find the table through the `"PLpgSQL_plugin"` rendezvous variable. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/plpgsql.md`).



### plpy_elog
`src/pl/plpython/plpy_elog.c` — PL/Python's error bridge: it converts a thrown PG `ErrorData` into a Python exception (and back), builds the `plpy.SPIError` hierarchy carrying SQLSTATE/detail/hint, and formats Python tracebacks into PG `errcontext` lines. [verified-by-code] (via `knowledge/files/src/pl/plpython/plpy_elog.md`).



### plpy_main
`src/pl/plpython/plpy_main.c` — the PL/Python call handler entry points (`plpython3_call_handler`, `plpython3_inline_handler`, `plpython3_validator`) plus `_PG_init`, interpreter initialization, and the per-session execution-context stack that tracks the currently executing PL/Python procedure. [verified-by-code] (via `knowledge/files/src/pl/plpython/plpy_main.md`).



### plpy_procedure
`src/pl/plpython/plpy_procedure.c` — builds and caches the `PLyProcedure` for a function: it compiles the Python source into a code object once, records argument/return type I/O routines, and keys the cache on function OID so subsequent calls reuse the compiled procedure. [verified-by-code] (via `knowledge/files/src/pl/plpython/plpy_procedure.md`).



### plpy_spi
`src/pl/plpython/plpy_spi.c` — the SPI bridge backing `plpy.execute`, `plpy.prepare`, `plpy.commit`, and `plpy.rollback`. Every PG-throwing SPI call is wrapped in `BeginInternalSubTransaction` so a thrown `ereport` becomes a catchable Python exception instead of a longjmp through the Python C stack. [verified-by-code] (via `knowledge/files/src/pl/plpython/plpy_spi.md`).



### plpy_typeio
`src/pl/plpython/plpy_typeio.c` — the type-conversion layer between PG `Datum`s and Python objects: input/output routines per PG type (scalars, arrays, composites, and bytea/`bytes`), built from cached `FmgrInfo`s, used whenever arguments cross into Python or results cross back out. [verified-by-code] (via `knowledge/files/src/pl/plpython/plpy_typeio.md`).



### PLyObject_AsString
The PL/Python type-I/O helper that stringifies an arbitrary `PyObject *` into a server-encoding-aware palloc'd C string; it is exported for transform modules and underlies the scalar and `record_in` conversion paths from Python values back to PostgreSQL text. [verified-by-code] (`plpy_typeio.c:1027-1070` — via `knowledge/files/src/pl/plpython/plpy_typeio.md`).



### pnstrdup
Duplicates at most n bytes of a string into palloc'd memory and NUL-terminates the copy; the length-bounded `pstrdup`, used to detach a substring from a larger buffer. [verified-by-code] (`dict_int.c:93,96` — via `knowledge/files/contrib/dict_int/dict_int.c.md`).



### PointerGetDatum
The macro that packages a C pointer as a `Datum` for return or argument
passing through fmgr — the encoding side of by-reference value passing (its
inverse is `DatumGetPointer`). It performs no copy: the pointed-to value must
outlive the `Datum`, so callers are careful about memory-context lifetime.
[from-comment] (via `knowledge/files/src/include/postgres.h.md`).



### PopActiveSnapshot
Removes the top entry from the active-snapshot stack, undoing a
`PushActiveSnapshot`; the push/pop discipline must balance or the snapshot
that bounds the xmin horizon is held too long or freed too early. [verified-by-code]
(via `knowledge/data-structures/snapshot-lifecycle.md`).



### portal
The backend-local object holding the execution state of a single query or
cursor — its plan, parameters, and memory contexts — between bind and the
fetching of results. Portals are created under `TopPortalContext` (e.g. by
`CreateNewPortal`) and torn down when the statement completes or the cursor
closes. [verified-by-code] (`portalmem.c:237` — via
`knowledge/files/src/backend/utils/mmgr/portalmem.c.md`).



### PortalContext
The memory context holding the executable state of the currently active portal
(cursor / query). It is made the current context while a portal runs, so
per-execution allocations are reclaimed when the portal is dropped.
[verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### PortalDefineQuery
The portalmem.c routine that populates a freshly created portal with its prepared-statement name, source text, command tag, `CachedPlanSource`, and `CachedPlan`. It is the point where cached-plan refcount ownership transfers to the portal (released later by `PortalReleaseCachedPlan` inside `PortalDrop`), so it must NOT `ereport` between accepting the refcount and storing `cplan` or the refcount the caller incremented via `GetCachedPlan` would leak. [verified-by-code] (`portalmem.c:284` — via `knowledge/files/src/backend/utils/mmgr/portalmem.c.md`).



### PortalDrop
Tears down a portal: it removes the portal from the portal hash table early
(so abort-retry is idempotent) and then releases its resources and memory
context. [verified-by-code] (`portalmem.c:516` — via
`knowledge/subsystems/utils-mmgr.md`).



### PortalRun
The tcop entry point that executes a portal (a named, runnable query container)
and routes its result tuples to a `DestReceiver`. The extended-query and simple-
query paths both funnel through it; `PortalRun(FETCH_ALL, dest)` drains a portal
to completion. [verified-by-code]
(via `knowledge/files/src/backend/tcop/postgres.c.md`).



### PortalRunFetch
Executes a FETCH/MOVE against an open cursor's portal, driving the underlying plan forward or backward by the requested count and honouring the portal's scrollability and materialized-tuplestore backing. [verified-by-code] (via `knowledge/files/src/backend/executor/spi.c.md`).



### PortalStart
The step that readies a portal for execution after planning: it chooses the
execution strategy, creates the executor state (for an optimizable query), and
pushes the active snapshot, before `PortalRun` pulls tuples.
[verified-by-code] (`pquery.c:430` — via `knowledge/subsystems/tcop.md`).



### posix_fadvise
The kernel page-cache hint PostgreSQL uses (`POSIX_FADV_DONTNEED`/`WILLNEED`); `pre_sync_fname` uses `sync_file_range` if available else `posix_fadvise` as a best-effort writeback hint, and the buffer manager coalesces writeback hints through it. [verified-by-code] (via `knowledge/files/src/common/file_utils.c.md`).



### post_parse_analyze_hook
The extension hook fired at the end of parse analysis, after a raw parse tree becomes an analyzed `Query`; extensions chain it to rewrite or inspect the query tree before planning. Apache AGE, for instance, uses it to swap a `cypher()` call for a separately-parsed subquery. [verified-by-code] (via `knowledge/ideologies/apache-age.md`).



### postgres_fdw
The contrib Foreign Data Wrapper for connecting to another PostgreSQL server. It pushes down `WHERE` clauses, joins, aggregates, and `RETURNING` where safe, manages a libpq connection cache, and is the reference implementation that exercises most of the FDW API. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### PostgresMain
The entry point of a per-connection backend: after authentication it runs the
"traffic cop" loop that reads a client message and dispatches simple-query
(`Q`) or extended-protocol (`P`/`B`/`E`) requests through parse → rewrite →
plan → execute. It runs for the life of the session in the forked backend.
[verified-by-code] (`postgres.c:4274` — via
`knowledge/files/src/backend/tcop/postgres.c.md`).



### PostingItem
A GIN internal-page pointer pairing a child block number with the highest heap TID reachable through it, the downlink form used on the posting-tree (entry-tree leaf overflow) side of a GIN index. [verified-by-code] (`gindatapage.c` — via `knowledge/files/src/backend/access/gin/gindatapage.c.md`).



### postmaster
The supervisor process. It owns the shared-memory and semaphore pools, listens
for connections, and forks a fresh backend on each accept; it deliberately
stays *out* of shared memory so a crashing backend can never corrupt the
supervisor — a load-bearing invariant of the whole process model.
[from-comment] (`postmaster.c:14-23` — via
`knowledge/files/src/backend/postmaster/postmaster.c.md`).



### postmaster_child_launch
The single fork dispatcher for every postmaster child — called from `BackendStartup`, `StartChildProcess`, `StartAutovacuumWorker`, and `StartBackgroundWorker` — centralizing the fork (or, under EXEC_BACKEND, the re-exec) of all backend processes. [verified-by-code] (via `knowledge/files/src/backend/postmaster/launch_backend.c.md`).



### PostmasterContext
The memory context holding data needed only during startup (e.g. the parsed
pg_hba/pg_ident configuration). A freshly forked backend deletes it once it no
longer needs that startup-only data. [verified-by-code]
(`postgres.c:4388-4391` — via `knowledge/subsystems/tcop.md`).



### PostmasterMain
The postmaster's top-level setup routine — parses options, creates shared memory and semaphores, opens the listen sockets, and enters ServerLoop to accept connections and fork a backend per client. [verified-by-code] (via `knowledge/subsystems/main.md`).



### pq_beginmessage
Starts composing a wire-protocol message: it initialises the `StringInfo` buffer and stashes the message-type byte, to be finished by `pq_endmessage` which prepends the length. The send-side framing primitive in `pqformat.c`. [verified-by-code] (`pqformat.c:87` — via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### pq_cleanup_redirect_to_shm_mq
The parallel-worker cleanup registered via `on_dsm_detach`: when a worker's message-queue DSM detaches, it undoes the redirection of protocol output back onto the shared `shm_mq`, restoring normal `pq` behavior before exit. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqmq.c.md`).



### pq_getbyte
The backend libpq call reading a single byte from the client (typically the message-type byte) after `pq_startmsgread`; paired with `pq_getmessage` to consume the message body. [verified-by-code] (via `knowledge/files/src/backend/libpq/auth-sasl.c.md`).



### pq_getmessage
The backend libpq routine that reads one length-prefixed frontend protocol message into a `StringInfo`, used after `pq_startmsgread`/`pq_getbyte` have consumed the message-type byte (e.g. in the SASL authentication exchange). [verified-by-code] (via `knowledge/files/src/backend/libpq/auth-sasl.c.md`).



### pq_getmsgint
Reads a big-endian integer of the given width from an incoming protocol message buffer, advancing the cursor and erroring on underrun; the receive-side counterpart of `pq_sendint*`, used by type receive functions. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### pq_getmsgtext
The wire-protocol read helper that pulls a counted string out of an incoming
`StringInfo` message buffer and converts it from client to server encoding,
used while parsing protocol messages and certain binary `recv` functions.
[verified-by-code] (via `knowledge/files/contrib/ltree/ltree_io.c.md`).



### PQ_GSS_MAX_PACKET_SIZE
The 16384-byte cap (including the uint32 length header) on each GSSAPI-wrapped packet; larger payloads are split, so the GSS wrap is a stream frame, not a per-query blob. [verified-by-code] (`be-secure-gssapi.c:54` — via `knowledge/docs-distilled/gssapi-enc.md`).



### pq_init
The backend routine (`backend_startup.c`, called from `BackendInitialize`) that allocates the connection's `Port`, sets up the `FeBeWaitSet`, and initializes the frontend/backend protocol send/receive buffers for a freshly accepted client socket. [verified-by-code] (via `knowledge/subsystems/libpq-backend.md`).



### pq_parse_errornotice
`pq_parse_errornotice` (`pqmq.c:228`) is the receiver side of the parallel-worker error protocol: it reconstructs an `ErrorData` from a serialized ErrorResponse / NoticeResponse so the leader can re-throw a worker's error. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqmq.c.md`).



### pq_putmessage
The backend libpq routine that writes a typed protocol message to the client's output buffer; `pq_putmessage_v2` is the protocol-v2 compatibility variant retained only for the "unsupported protocol version" error path. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqcomm.c.md`).



### pq_sendint32
Appends a 32-bit integer in network byte order to an outgoing message `StringInfo`; the send-side primitive a binary-output (send) function uses, e.g. emitting a count followed by its elements. [verified-by-code] (via `knowledge/files/src/backend/libpq/pqformat.c.md`).



### pq_startmsgread
The backend libpq call that begins reading one incoming protocol message; it must be balanced by a matching `pq_endmsgread`/`pq_getmessage`, and calling it twice without closing the first read is a protocol-state bug. [from-comment] (via `knowledge/files/src/backend/libpq/pqcomm.c.md`).



### PQcancel
Sends a cancel request for the query currently running on a connection, using the secret cancel key captured at connect time over a fresh short-lived socket. The newer `PQcancelBlocking`/`PQcancelPoll` API supersedes it but the semantics are the same: interrupt, do not close. [inferred] (`fe-cancel.c:382` — via `knowledge/files/src/interfaces/libpq/fe-connect.c.md`).



### PQclear
Frees a `PGresult` and all the tuple storage it owns. Every result handed back by libpq must be cleared exactly once; forgetting it is the classic libpq memory leak. [inferred] (via `knowledge/files/src/include/libpq/libpq-be-fe.h.md`).



### pqcommmethods
`PQcommMethods` (`libpq.h:36-46`) is the backend's function-pointer vtable for frontend I/O (put / flush / startcopyout / etc.), swapped to redirect protocol traffic — e.g. during COPY. [verified-by-code] (via `knowledge/subsystems/libpq-backend.md`).



### PQconnectdbParams
The libpq entry point that opens a connection from parallel `keywords[]`/`values[]` arrays (with optional `expand_dbname`); PG's own tools wrap it to add connection-string parsing, password prompting/retry, a server-version check, and a forced `SET search_path = pg_catalog`. [verified-by-code] (`connectdb.c:79-151` — via `knowledge/files/src/bin/pg_dump/connectdb.c.md`).



### PQconnectPoll
Drives the non-blocking libpq connection state machine one step at a time, returning `PGRES_POLLING_READING`/`PGRES_POLLING_WRITING`/`PGRES_POLLING_OK` so an event-loop caller knows which socket condition to wait for next. It is the engine behind `PQconnectStart`-style asynchronous connects. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-connect.c.md`).



### PQconsumeInput
The libpq call that drains all currently-available data from the server socket into libpq's input buffer without blocking; an async client loops on socket-readable, calls it, then `PQisBusy`/`PQgetResult` to make progress. [verified-by-code] (via `knowledge/files/src/test/examples/testlibpq2.c.md`).



### PQerrorMessage
Returns the human-readable text of the most recent error on a `PGconn` (or the message attached to a failed `PGresult` via `PQresultErrorMessage`). The string is owned by the handle and is overwritten by the next failing call. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-connect.c.md`).



### PQescapeIdentifier
The libpq routine that safely quotes a string as a SQL identifier for the given connection, honoring the server's encoding; unlike the connectionless `PQescapeString` it cannot be fooled by client-encoding/`standard_conforming_strings` mismatches. [verified-by-code] (`fe-exec.c:4234` — via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### PQescapeLiteral
The libpq routine that quotes a string as a SQL literal for a specific connection, allocating the escaped result (caller `PQfreemem`s it) and using the connection's encoding/`standard_conforming_strings` to choose the correct escaping. [verified-by-code] (`fe-exec.c:4234` — via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### PQescapeStringConn
The libpq client-side helper that escapes a string for safe interpolation into a SQL literal, honoring the connection's encoding and `standard_conforming_strings`; client programs that build SQL by hand should use it (or `PQescapeLiteral`) rather than ad-hoc quoting. [verified-by-code] (via `knowledge/files/contrib/oid2name/oid2name.c.md`).



### PQexec
The synchronous libpq entry point that submits a command string and blocks until the server finishes, returning a single (last) `PGresult`. It is the simplest query path; the async `PQsendQuery`/`PQgetResult` pair is used when the caller must not block. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### PQExpBuffer
libpq's resizable string buffer — the frontend/client analogue of the backend's `StringInfo` — used to assemble queries, connection strings, and protocol messages in client-side code. [verified-by-code] (via `knowledge/files/src/interfaces/libpq` docs).



### PQfinish
Closes a libpq connection and frees the `PGconn` and all memory associated with it. After it returns the handle is invalid and must not be reused; it is the mandatory teardown counterpart to `PQconnectdb`. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-connect.c.md`).



### PQgetResult
The libpq call that returns the next `PGresult` from an asynchronous command, returning NULL when the current command is fully consumed; looping until NULL is mandatory after `PQsendQuery`. It underlies the synchronous `PQexec` as well. [inferred] (via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### PqGSSSendBuffer
The backend staging buffer holding the encrypted GSSAPI bytes queued for write, sized against `PQ_GSS_MAX_PACKET_SIZE`. [verified-by-code] (`be-secure-gssapi.c:69` — via `knowledge/docs-distilled/gssapi-enc.md`).



### PQsendQuery
The libpq entry point that submits a command without blocking for the result; paired with `PQgetResult` it drives asynchronous query processing and is the way to see every result of a multi-statement string (which `PQexec` collapses to the last). [verified-by-code] (`fe-exec.c:2427` — via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### predicate_implied_by
The planner's predicate-implication test (in `predtest.c`) that decides whether a partial index is usable: it must *prove* the query's `WHERE` clause mathematically implies the index predicate. Called as `predicate_implied_by(index->indpred, all_clauses, false)` from the index-path builder. The prover is deliberately weak — it handles simple inequality implication (`x<1` ⟹ `x<2`), otherwise requiring an exact structural match — and a parameterized clause like `x < ?` never implies a constant predicate. [verified-by-code `source/src/backend/optimizer/path/indxpath.c:1134`, prover entry `source/src/backend/optimizer/util/predtest.c:154` @c1702cb51363] (via `knowledge/docs-distilled/indexes-partial.md`).



### PredicateLockPage
Takes an SSI predicate lock at page granularity, recording a read dependency so
the serializable conflict detector can spot dangerous rw-antidependencies and
abort to preserve serializability. [verified-by-code] (via
`knowledge/idioms/predicate-locks.md`).



### PredicateLockPageSplit
SSI bookkeeping that transfers predicate locks from an index page to the new page created by a page split, so that serialization-conflict detection is not lost across the split. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtinsert.c.md`).



### PrefetchBuffer
Issues an asynchronous OS read-ahead (posix_fadvise / AIO) for a relation block so a later `ReadBuffer` finds it already in flight or resident; the building block behind effective_io_concurrency-driven prefetching such as WAL recovery prefetch. [inferred] (via `knowledge/files/src/backend/access/transam/xlogprefetcher.c.md`).



### PrepareToInvalidateCacheTuple
The catcache helper that, given a changed catalog tuple, computes which
catcache entries (by cache id and hash) must be invalidated, feeding the
invalidation machinery. [verified-by-code] (via
`knowledge/files/src/backend/utils/cache/catcache.c.md`).



### PrepareTransaction
The xact.c routine implementing PREPARE TRANSACTION: it writes the two-phase state file and refuses to prepare if any open portal or held cursor still exists. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



### preprocess_targetlist
Early planner pass (`preptlist.c`) that expands and normalizes the query's target list — adding junk columns for `FOR UPDATE`/`ctid`, resjunk sort/group entries, and the columns an UPDATE/DELETE needs — before path generation. [verified-by-code] (via `knowledge/files/src/backend/optimizer/prep/preptlist.c.md`).



### primary_conninfo
The standby-side GUC holding the libpq connection string the walreceiver uses to
reach the primary for streaming replication; `pg_basebackup -R` and
`recovery_gen` write it into the generated `postgresql.auto.conf`/standby
signal setup. [verified-by-code] (via
`knowledge/files/src/fe_utils/recovery_gen.c.md`).



### printtup
The default client `DestReceiver`'s hot path: it switches to a per-tuple context, materialises a `TupleTableSlot`'s attributes, and emits a `'D'` DataRow protocol message (int16 natts, then per-attr int32 length + bytes, `-1` for NULL). [verified-by-code] (via `knowledge/files/src/backend/access/common/printtup.c.md`).



### PriorCmdInvalidMsgs
The accumulated list of catalog invalidation messages generated by commands
earlier in the current transaction, held so they can be broadcast at commit and
replayed on abort cleanup. [verified-by-code] (via
`knowledge/idioms/syscache-invalidation-flow.md`).



### private_data
The opaque per-injection-point payload registered via `InjectionPointAttach(name, library, function, private_data, size)`; the attached callback receives it when the named injection point fires, letting a test carry state to its handler. [verified-by-code] (`injection_point.c:17` — via `knowledge/files/src/backend/utils/misc/injection_point.c.md`).



### proc_exit
The backend's orderly-exit routine: it runs all registered `on_proc_exit` and
`before_shmem_exit` callbacks (releasing shared resources, detaching shmem) in
LIFO order, then calls `exit()`. Backend cleanup hangs off it rather than off
raw `exit`. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/ipc.c.md`).



### PROC_HDR
The `ProcGlobal` shared structure holding the global `PGPROC` free lists (normal / autovacuum / bgworker / walsender), the `allProcs` array, and cache-friendly mirror arrays (`xids[]`, `statusFlags[]`) that duplicate hot PGPROC fields for fast scans. [verified-by-code] (via `knowledge/files/src/include/storage/proc.h.md`).



### ProcArray
The shared-memory array of pointers to active backends' `PGPROC`s, used to take
snapshots (which xids are in-progress), compute the oldest visible xid, and
find backends to signal. `GetSnapshotData` walks it under `ProcArrayLock`.
[from-comment] (via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).



### ProcArrayAdd
The function that inserts a backend's PGPROC into the shared ProcArray, holding `ProcArrayLock` exclusively and performing a `pgxactoff` shuffle so the dense arrays stay packed (counterpart to `ProcArrayRemove`). Only the moved entry's `PGPROC->pgxactoff` needs updating, not every other backend's. [verified-by-code] (`procarray.c` — via `knowledge/files/src/backend/storage/ipc/procarray.c.md`).



### ProcArrayApplyXidAssignment
The standby-side routine that processes an `XLOG_XACT_ASSIGNMENT` record,
folding a batch of reported subtransaction xids into the known-assigned-xids
machinery so recovery snapshots account for subxids without per-subxid WAL.
[verified-by-code] (via `knowledge/idioms/subxact-visibility-and-overflow.md`).



### ProcArrayEndTransaction
Clears a backend's XID from the shared ProcArray at transaction end — the step
that makes the transaction's effects visible to others; all FATAL exit paths
must reach it so the proc slot does not linger. [verified-by-code] (via
`knowledge/files/src/backend/utils/init/postinit.c.md`).



### ProcArrayInstallImportedXmin
The procarray routine that atomically installs an imported snapshot's xmin into the current backend's PGPROC without letting the global xmin move backwards; the sibling of ProcArrayInstallRestoredXmin. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### ProcArrayLock
The LWLock guarding the `ProcArray` (the set of live `PGPROC`s). Snapshot
building takes it SHARED (`GetSnapshotData`); transaction commit/abort and
backend exit take it EXCLUSIVE to update visibility. Its contention is a known
scalability pressure point. [verified-by-code] (`procarray.c:2170` — via
`knowledge/subsystems/storage-ipc.md`).



### ProcArrayRemove
Removes a backend's PGPROC from the shared proc array at backend exit (or after a prepared-xact commit), publishing its final XID state so other backends' snapshots stop seeing it as in-progress. [from-comment] (via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### ProcDiePending
The backend-global flag set by the SIGTERM handler to request a clean `FATAL` exit; like `QueryCancelPending` it is acted on at the next `CHECK_FOR_INTERRUPTS`, not in the signal handler itself. [inferred] (via `knowledge/ideologies/pgsql-http.md`).



### process_equivalence
The equivalence-class builder (`equivclass.c`) that folds a mergejoinable `=` qual into an EquivalenceClass, letting the planner later derive implied equalities and choose which side to index. It assumes EC memory lives for the whole planning cycle and silently ignores quals whose operator families do not match. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### process_shared_preload_libraries_in_progress
The global boolean that is true only while the postmaster is loading `shared_preload_libraries`; an extension's `_PG_init` tests it to tell a preload start (where it may request shmem and register static bgworkers) from a later on-demand `LOAD`/`CREATE EXTENSION`. [inferred] (via `knowledge/scenarios/add-new-extension.md`).



### ProcessInterrupts
The routine where a backend actually services a pending interrupt (query cancel, termination, recovery conflict) once `CHECK_FOR_INTERRUPTS` observes `InterruptPending` set and it is safe (outside a critical section) to act. [verified-by-code] (via `knowledge/files/src/include/miscadmin.h.md`).



### processlogmemorycontextinterrupt
The `mcxt.c` handler for the `pg_log_backend_memory_contexts(pid)` signal, which dumps the target backend's memory-context tree to the server log at the next interrupt point. [verified-by-code] (via `knowledge/subsystems/utils-mmgr.md`).



### ProcessParallelMessage
The leader-side handler that translates a protocol message received from a parallel worker (error, notice, etc.) into the equivalent local action or ereport. [verified-by-code] (via `knowledge/files/src/backend/access/transam/parallel.c.md`).



### ProcessParallelMessages
The leader-side handler that drains and dispatches messages (errors, notices, tuples, xact commands) sent by parallel workers over their shared-memory queues when the `ParallelMessagePending` flag is set. [verified-by-code] (`parallel.c` — via `knowledge/files/src/backend/access/transam/parallel.c.md`).



### processSQLNamePattern
The fe_utils routine that turns a psql `\d`-style name pattern into SQL
WHERE-clause conditions against the catalogs, safely quoting the literal
pieces. It is the single chokepoint that makes `\d*` pattern matching
injection-safe across psql and pg_dump. [verified-by-code] (via
`knowledge/files/src/fe_utils/string_utils.c.md`).



### ProcessStartupPacket
The postmaster-side routine that reads and validates a new connection's startup packet (protocol version, database/user, GUC settings, SSL/GSS negotiation) before the backend is forked and authentication proper begins. [inferred] (via `knowledge/community/user-questions/2026-06-21.md`).



### ProcessUtility
The dispatch point for non-optimizable statements — DDL, transaction control,
COPY, VACUUM, and the like — that bypass the planner/executor. It is the
canonical hook target (`ProcessUtility_hook`) for extensions wanting to
intercept commands. [verified-by-code] (`utility.c:504` — via
`knowledge/subsystems/tcop.md`).



### ProcessUtility_hook
The hook point through which extensions intercept utility (non-optimizable)
statements; `ProcessUtility` dispatches down the hook chain and ultimately to
`standard_ProcessUtility`. [verified-by-code] (`utility.c:548` — via
`knowledge/files/src/backend/tcop/utility.c.md`).



### ProcessUtilitySlow
The branch of utility-command processing that handles statements needing full
parse-analyze and dependency tracking (most DDL), as opposed to the fast path
for simple commands. [verified-by-code] (via
`knowledge/idioms/process-utility-hook-chain.md`).



### ProcGlobal
The shared `PROC_HDR` structure anchoring all `PGPROC`s: the `allProcs` array
plus the per-class free lists (regular, autovacuum, bgworker, walsender) and
cache-friendly mirrored arrays of xids/status flags scanned during snapshot
building. [verified-by-code] (`proc.h:444` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### procLatch
The latch embedded in each backend's `PGPROC`, used to wake a sleeping process from another backend or a signal handler. Latch waits combined with socket/timeout events via `WaitEventSet`/`WaitLatch` are the backend's standard sleep primitive. [inferred] (`proc.h:258` — via `knowledge/files/src/include/storage/proc.h.md`).



### PROCLOCK
A shared-memory hash entry in the heavyweight lock manager linking one `PGPROC` (a backend) to one `LOCK` object, recording which backend holds or awaits which lock. Together with the `LOCK` table and per-backend `LOCALLOCK` cache it forms the lock manager's core state. [from-comment] (`lock.c:13-26` — via `knowledge/subsystems/storage-lmgr.md`).



### procLocks
The dlist on a heavyweight `LOCK` object linking every `PROCLOCK` (one per holding/waiting PGPROC); `CleanUpLock` garbage-collects the `LOCK` once `nRequested` reaches zero. [from-README] (via `knowledge/subsystems/storage-lmgr.md`).



### ProcLockWakeup
The proc.c routine that, after a lock holder releases, walks a lock's `waitProcs` wait queue and grants the lock to each waiter whose requested mode conflicts with neither the current `grantMask` nor the requests of un-wakable predecessors, dequeuing and `ProcWakeup`-ing each. It maintains a per-mode blocked-waiters mask so a run of compatible requests is granted in arrival order, and it requires the lock's partition LWLock held EXCLUSIVE; it is called from `LockRelease`/`UnGrantLock` and from the deadlock detector's soft-cycle rearrangement. [verified-by-code] (`proc.c:1809-1855` — via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### ProcNumber
A backend's dense 0-based index into the shared PGPROC and proc arrays (the modern successor to "backend id"); used as a lease-holder identity, e.g. the `acquired_by` of a replication-origin session. [verified-by-code] (via `knowledge/files/src/include/replication/origin.h.md`).



### PROCSIG_CATCHUP_INTERRUPT
A procsignal reason (in `procsignal.h`) used by the shared-invalidation (sinval) machinery to nudge backends that have fallen too far behind on the sinval message queue. When a backend lags more than `SIG_THRESHOLD = 2048` messages, `SICleanupQueue` drops its LWLocks and `SendProcSignal(..., PROCSIG_CATCHUP_INTERRUPT, ...)` to make it catch up; the lock is released first because the signal send can be slow. [verified-by-code] (`storage-ipc.md` — via `knowledge/subsystems/storage-ipc.md`).



### ProcSignal
The shared-memory mechanism for sending and handling inter-backend signals
(e.g. sinval catchup, barrier, recovery conflict) by setting flags a backend
checks at `CHECK_FOR_INTERRUPTS`. [verified-by-code] (via
`knowledge/subsystems/storage-ipc.md`).



### procsignal_sigusr1_handler
The `SIGUSR1` handler installed via `ProcSignal` that dispatches multiplexed inter-backend signals (catchup interrupts, barrier/recovery-conflict notifications, parallel-message wakeups). A process must have run `InitPostgres`/`ProcSignalInit` to receive them — which is why preload-time bgworkers that want signals still initialize as backends even without a database connection. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/procsignal.c.md`).



### ProcSignalBarrier
The mechanism for forcing every backend to process a global state change
(e.g. relmapper or smgr invalidation) before the initiator proceeds: the
emitter bumps a generation counter, signals all backends via `ProcSignal`, and
waits until each has absorbed the barrier. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/procsignal.c.md`).



### ProcSleep
The lock-manager primitive that puts a backend to sleep on its PGPROC
semaphore while it waits for a heavyweight lock, after `JoinWaitQueue` has
inserted it into the lock's wait queue. It wakes on the deadlock-timeout
SIGALRM (re-checking `got_deadlock_timeout`) or when `ProcWakeup` grants the
lock. [verified-by-code] (`proc.c:1348` — via
`knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### ProcState
The per-backend slot in the sinval shared array (`sinvaladt.c`) tracking that backend's read position in the shared-invalidation message ring; a reader updates its own slot under a shared lock. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/sinvaladt.c.md`).



### ProjectSet
The executor node that evaluates set-returning functions in a target list,
emitting one output row per result-set element (replacing the old
`nodeResult`-with-SRF behavior). [verified-by-code] (via
`knowledge/subsystems/executor.md`).



### provider_failed_loading
One of the two sticky JIT load-state flags in `jit.c` (`provider_successfully_loaded` / `provider_failed_loading`); `provider_init` sets `failed = true` *before* attempting `load_external_function` so that an `ereport(ERROR)` during load doesn't trigger silent retry storms on later JIT requests. [verified-by-code] (via `knowledge/files/src/backend/jit/jit.c.md`).



### provider_init
The lazy, `jit_enabled`-gated routine in `jit.c` that `dlopen`s the `jit_provider` library and calls `_PG_jit_provider_init` on the first query that needs JIT; its `if (!jit_enabled)` early-out is why `jit=off` avoids the LLVM load entirely. [verified-by-code] (`jit.c:68,74` — via `knowledge/docs-distilled/jit-extensibility.md`).



### provolatile
The `pg_proc` column classifying a function as IMMUTABLE (`i`), STABLE (`s`), or VOLATILE (`v`); the planner uses it to decide constant-folding, caching, and index usability. [from-comment] (via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### prune_append_rel_partitions
The planner-side pruning entry (`partprune.c`) that discards child rels of an Append whose partitions provably cannot match, before path generation. [verified-by-code] (via `knowledge/files/src/backend/partitioning/partprune.c.md`).



### PruneState
The working struct threaded through heap page pruning that records which line pointers become dead, redirected, or unused, the frozen-xid horizon, and the change accumulator that becomes one `XLOG_HEAP2_PRUNE` WAL record. [verified-by-code] (`pruneheap.c` — via `knowledge/files/src/backend/access/heap/pruneheap.c.md`).



### ps_status
The process-title machinery (`set_ps_display`, `init_ps_display`) that updates
what `ps`/`top` show for each backend — typically the current command and the
client identity. When `update_process_title` is on (the Unix default) it can
leak SQL text, including literal passwords, to any local user. [verified-by-code]
(via `knowledge/files/src/include/utils/ps_status.h.md`).



### psprintf
`printf`-style formatting that `palloc`s a correctly sized result buffer in the current memory context and returns it, so the caller never sizes the buffer by hand. [verified-by-code] (via `knowledge/idioms/memory-contexts.md`).



### PSQLexec
psql's internal helper for running a backslash-command's behind-the-scenes SQL (e.g. catalog lookups for `\d`), as opposed to a user's typed query; it honors `ECHO_HIDDEN` so the generated SQL can be shown. `SendQuery` is the path for user-entered statements. [inferred] (via `knowledge/files/src/bin/psql/common.c.md`).



### pstrdup
Duplicates a NUL-terminated string into the current memory context via palloc; the context-aware `strdup` whose result is freed automatically at context reset (or on an ereport longjmp). [verified-by-code] (via `knowledge/files/contrib/sepgsql/selinux.c.md`).



### ptrack map
The fixed-size shared-memory map maintained by the external extension `postgrespro/ptrack` recording, per data block, the LSN at which it was last modified; fed by smgr write hooks patched into core (`mdwrite_hook`/`mdextend_hook`), persisted out-of-band at checkpoint, and queried by `ptrack_get_pagemapset` so incremental backups can skip WAL summarization. Engineered to over-approximate — false positives allowed, false negatives never. [verified-by-code] (external repo — via `knowledge/ideologies/ptrack.md`).



### ptrack_get_pagemapset
The SQL function the external extension `postgrespro/ptrack` exposes to return, per relation file, a bitmap of blocks changed since a given `start_lsn` — the read side of ptrack's block-level incremental backup, consumed in practice by `pg_probackup`. It reads the in-memory ptrack map with `pg_atomic_read_u64` and re-derives the file set itself rather than consulting `pg_class`. [verified-by-code] (external repo — via `knowledge/ideologies/ptrack.md`).



### publish_via_partition_root
A publication option that makes logical replication publish partitioned-table changes as the root table rather than the leaf partition; `pg_publication.c`'s partition-tree resolution (`GetTopMostAncestorInPublication`, `filter_partitions`) and tablesync honor it. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_publication.c.md`).



### pull_up_subqueries
The planner-prep pass (in `prepjointree.c`) that flattens eligible subqueries in `FROM` up into the parent query's jointree, letting their relations participate directly in join-order search instead of being planned as opaque subplans. [inferred] (via `knowledge/community/user-questions/2026-06-17.md`).



### PullFilter
In pgcrypto's streaming framework, a pull-model filter that wraps a source and
transforms bytes as they are read (e.g. decompression, decryption) in the OpenPGP
pipeline. [verified-by-code] (via `knowledge/subsystems/contrib-pgcrypto.md`).



### PushActiveSnapshot
Pushes a snapshot onto the backend's active-snapshot stack so it becomes what "the current command" sees; paired with PopActiveSnapshot, it scopes visibility around each executed command and is tracked by the snapshot manager. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### PushFilter
The push-model counterpart to `PullFilter` in pgcrypto: a filter that transforms
bytes as they are written downstream (e.g. compression, encryption) when
producing OpenPGP output. [verified-by-code] (via
`knowledge/subsystems/contrib-pgcrypto.md`).



### PushFilter / PullFilter
pgcrypto's streaming I/O abstraction: a `PushFilter` chain transforms bytes on
the way out (encrypt, compress) and a `PullFilter` chain transforms them on the
way in (decrypt, decompress), each stage wrapping the next. The PGP compression
code adapts zlib `deflate`/`inflate` as filter stages this way. [from-comment]
(via `knowledge/files/contrib/pgcrypto/pgp-compress.md`).



### px_find_digest
The pgcrypto PX-library lookup that resolves a named message digest into a `PX_MD` handle; some callers (e.g. `crypt-sha.c`) use it directly rather than through the HMAC wrapper. [from-comment] (via `knowledge/files/contrib/pgcrypto/px-hmac.md`).



### px_memset
pgcrypto's indirection over `memset` (through a volatile function pointer) used to scrub key/secret buffers so the compiler cannot optimise the wipe away; e.g. `clear_and_pfree` wipes a `text` before freeing it. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### PyObject
CPython's universal reference-counted object handle; in PL/Python every SQL
value, plan, cursor, and the `plpy` module itself is exchanged as a `PyObject *`
across the embedding boundary. PL/Python maps each SQLSTATE to a `PyObject *`
exception class so SQL errors surface as catchable Python exceptions.
[verified-by-code] (via
`knowledge/files/src/pl/plpython/plpy_plpymodule.md`).



### qsort_arg
PostgreSQL's in-house quicksort taking a comparator plus an opaque `arg` pointer (`qsort_arg_comparator`), used wherever the comparison needs context the two elements alone don't carry — a collation, a `SortSupport`, or tuplesort state. It is generated from the same `sort_template.h` machinery as the type-specialized sorts. [verified-by-code] (via `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`).



### Query
The parse-analysis output: a normalized tree describing one SQL statement's
semantics — its range table, target list, join tree, and qualifications —
after names and types are resolved but before planning. The rewriter transforms
Querys (applying rules/views); the planner consumes them. [from-comment] (via
`knowledge/files/src/include/nodes/parsenodes.h.md`).



### query_buf
One of the three `PQExpBuffer`s psql's `MainLoop` owns: SQL text accumulates into `query_buf` until a semicolon or EOF triggers `SendQuery`, after which `query_buf` and `previous_buf` are swapped by pointer so `\g`/`\p`/`\w` can reach the last-executed query. [verified-by-code] (`mainloop.c:443-449` — via `knowledge/files/src/bin/psql/mainloop.c.md`).



### query_int
intarray's query type for `int4[]` containment searches (the `@@` operator); the GIN opclass's `ginint4_queryextract` walks a `query_int` to extract indexable values and pick a `GIN_SEARCH_MODE_*`, where a negation such as `! 42` forces a full-index scan. [verified-by-code] (`_int_gin.c:37-40` — via `knowledge/files/contrib/intarray/_int_gin.md`).



### query_planner
The core of the optimizer that, given the FROM-clause relations and join
restrictions, builds base-relation `RelOptInfo`s and runs join-order search to
produce the cheapest join `RelOptInfo`; `grouping_planner` wraps it to add
grouping/aggregation/sort/limit on top. [verified-by-code] (via
`knowledge/subsystems/optimizer.md`).



### QueryCancelPending
The flag set by a `SIGINT` (statement cancel) handler; `CHECK_FOR_INTERRUPTS`
notices it at safe points and throws to abort the current query without killing
the backend. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### QueryDesc
The "bag of everything" the executor needs to run one query — plan tree, snapshot, dest receiver, params, instrumentation — constructed by tcop/SPI/SQL-functions and passed to `ExecutorStart`/`Run`/`End`. [from-comment] (via `knowledge/files/src/include/executor/execdesc.h.md`).



### QueryEnvironment
The per-query container for objects that exist only for the duration of a
query but aren't in the catalog — most notably ephemeral named relations (the
transition tables a statement-level trigger sees). `create_queryEnv()`
`palloc0`s one and the parser/executor consult it to resolve such names.
[verified-by-code] (via
`knowledge/files/src/backend/utils/misc/queryenvironment.c.md`).



### queryId
The 64-bit hash fingerprint of a normalized query tree, computed by the jumble machinery and surfaced in `pg_stat_activity` and `pg_stat_statements` to group executions of the same statement shape. Constants are replaced by placeholders before hashing. [inferred] (via `knowledge/subsystems/contrib-pg_stat_statements.md`).



### QueryItem
The union element of a compiled `tsquery` (`ts_type.h`): either an operand (`QI_VAL`) or an operator (`QI_OPR`), stored as a polish-notation array that matching and `tsquery_cleanup` walk recursively. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/tsquery.c.md`).



### queryjumble
The query-normalization machinery that walks a parse tree, substitutes constants
with placeholders, and computes a stable `queryId` hash so different literal
values collapse to one entry. It is what `pg_stat_statements` and
`compute_query_id` group statistics by. [verified-by-code] (via
`knowledge/files/src/include/nodes/queryjumble.h.md`).



### QueryRewrite
The top entry of the rule-rewriter: it takes a single parse-analysed `Query`
and returns a list of Querys after applying ON SELECT (view expansion) and
non-SELECT rules, re-acquiring locks on rewritten range-table entries. It is the
stage between parse-analysis and planning. [verified-by-code]
(`rewriteHandler.c:4780-4870` — via
`knowledge/files/src/backend/rewrite/rewriteHandler.c.md`).



### quickdie
The backend's `SIGQUIT` handler under the postmaster: on a sibling crash it does `_exit(2)` immediately with no atexit callbacks, no cleanup, and no shared-memory touching, because shared state may be corrupt. [verified-by-code] (via `knowledge/subsystems/tcop.md`).



### quote_ident
Returns a SQL identifier suitably double-quoted only when necessary — i.e. when it contains characters outside `[a-z0-9_]`, starts with a digit, or collides with a keyword. Catalog-dumping and DDL-emitting code uses it (and `quote_identifier`) to produce reparseable names. [inferred] (via `knowledge/files/src/backend/utils/adt/quote.c.md`).



### quote_identifier
The routine that returns a SQL identifier, double-quoting it only when necessary
(it contains uppercase/special characters or collides with a reserved keyword).
It is what `pg_dump`, `ruleutils`, and `format('%I', …)` rely on to emit safe,
round-trippable identifiers. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/quote.c.md`).



### quote_literal_cstr
Returns a SQL string literal (single-quoted, with embedded quotes/backslashes escaped) for a C string; the safe way to interpolate a value into dynamically-built SQL, used by trigger code generating statements. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### quote_nullable
`quote_nullable()` renders a value as a SQL literal, emitting unquoted `NULL` for NULL input; used with `format('%L')` to build injection-safe dynamic SQL. [from-docs] (via `knowledge/docs-distilled/plpgsql-statements.md`).



### random_page_cost
The planner cost-model unit (default 4.0) for a non-sequential page fetch; index scans and other random-access paths multiply page counts by it, in contrast to the cheaper seq_page_cost. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/costsize.c.md`).



### RangeTblEntry
A range-table entry (RTE): one element of a query's rtable describing a relation, subquery, join, function, CTE, or values-scan the query references; expression nodes name columns by (rtindex, attno) into this list. [verified-by-code] (`nodes/parsenodes.h:1137` — via `knowledge/subsystems/parser-and-rewrite.md`).



### RangeTblEntry (RTE)
A range-table entry: the parse/plan-tree node describing one relation reference
in a query's FROM clause — a table, subquery, join, function, or CTE. Its
`rtekind` discriminates the variant, and other query nodes refer to RTEs by a
1-based range-table index (`varno`) rather than by pointer. [verified-by-code]
(`parsenodes.h:1137` — via
`knowledge/files/src/include/nodes/parsenodes.h.md`).



### RangeType
The varlena on-disk representation of a single range value (lower/upper bounds plus flag byte); a multirange is parsed and assembled as an array of `RangeType`. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/multirangetypes.c.md`).



### RangeVar
The parse-node (`primnodes.h`) representing a possibly-schema-qualified relation name (plus relpersistence and inheritance flags) before it is resolved to an OID. `makeRangeVar` builds one (defaulting relpersistence=PERMANENT, inh=true); name-resolution entries like `RangeVarGetRelid`/`RangeVarGetRelidExtended` and the `relation_openrv`/`table_openrv` openers turn it into a locked relation. [verified-by-code] (`primnodes.h:73`, `makefuncs.c:472` — via `knowledge/files/src/include/nodes/primnodes.h.md`).



### RangeVarCallbackForStats
The relation-open callback used by extended-statistics DDL to verify, under the right lock, that the named relation still exists and the caller may create statistics on it, closing the lookup/lock race window. [verified-by-code] (via `knowledge/files/src/backend/statistics/extended_stats_funcs.c.md`).



### RangeVarGetRelid
The namespace.c routine resolving a `RangeVar` (possibly schema-qualified name) to a relation OID, optionally taking a lock and running a callback before the lock to guard against concurrent rename/drop. [verified-by-code] (via `knowledge/files/src/backend/catalog/namespace.c`-derived doc, `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### RangeVarGetRelidExtended
Resolves a `RangeVar` (schema-qualified name) to a relation OID while taking the requested lock atomically, with `RVR_MISSING_OK`/`RVR_NOWAIT`/`RVR_SKIP_LOCKED` flags and an optional callback to re-check permissions across the name→lock race. [verified-by-code] (via `knowledge/files/src/include/catalog/namespace.h.md`).



### raw_buf
One of the four parsing buffers in `CopyFromStateData` (with `input_buf`, `line_buf`, `attribute_buf`): the raw bytes read from the COPY source (`COPY_FILE`/`COPY_FRONTEND`/`COPY_CALLBACK`) before line and attribute splitting. [verified-by-code] (via `knowledge/files/src/include/commands/copyfrom_internal.h.md`).



### raw_parser
The first parser stage: it runs the flex scanner and bison grammar over a query string and returns a list of raw parse trees (`RawStmt`), before any catalog lookup or semantic analysis. PL/pgSQL installs hooks around it so it can recognize and substitute its own variable references during compilation. [from-comment] (via `knowledge/files/src/pl/plpgsql/src/pl_comp.md`).



### RawParseMode
The enum (in `parser.h`) passed to `raw_parser(const char *str, RawParseMode mode)` selecting which grammar sub-entry the parser uses: `RAW_PARSE_DEFAULT` (a semicolon-separated `List<RawStmt>`), `RAW_PARSE_TYPE_NAME` (a single `TypeName`, used by `format_type`), `RAW_PARSE_PLPGSQL_EXPR`, and `RAW_PARSE_PLPGSQL_ASSIGN1/2/3` (where n = number of dotted names in the assignment target). It lets PL/pgSQL reuse the main grammar, and each mode maps deterministically to one parse shape (INV-PARSER-MODE-DETERMINISTIC). [verified-by-code] (`parser.h` — via `knowledge/files/src/include/parser/parser.h.md`).



### RawStmt
The grammar-output wrapper around one raw (un-analyzed) parse-tree statement,
carrying its byte offsets within the query string. The rewriter/analyzer
consumes a list of `RawStmt`s, one per statement in a multi-command string.
[verified-by-code] (`nodes/parsenodes.h:2187` — via
`knowledge/subsystems/parser-and-rewrite.md`).



### rd_att
The `RelationData` field holding a relation's `TupleDesc` (`rel->rd_att`, with `rd_att->natts` giving the column count); the cached descriptor every tuple-forming and -deforming path reads. [verified-by-code] (via `knowledge/files/contrib/btree_gist/btree_utils_num.c.md`).



### rd_fdwroutine
The cached `FdwRoutine` callback table hung off a foreign table's `RelationData` (relcache); invariant INV-FDWROUTINE governs when it is populated. [from-comment] (via `knowledge/files/src/include/utils/rel.md`).



### rd_indexcxt
A per-index memory context hung off `RelationData` (`rd_indexcxt`) holding relcache-owned index support data (opclass info, support-function cache); freed when the relcache entry is dropped. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### rd_partdesc
The `RelationData` field caching a partitioned table's `PartitionDesc`; it is populated lazily by `RelationGetPartitionDesc` (in partcache.c) rather than at relcache build time, and is invalidated along with the rest of the relcache entry. [from-comment] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### rd_partkey
`rd_partkey` (owned by `partcache.c`) is the relcache-cached partition key — strategy, attrs, exprs, collations, opclasses, support functions; preserved across relcache rebuilds because a partition key never changes after creation. [from-comment] (via `knowledge/subsystems/utils-cache.md`).



### rd_rel
The `Form_pg_class` pointer cached inside a `Relation`, giving fast access to the relation's pg_class row (relkind, relam, relnatts, relhasindex, frozen xid, …) without a syscache lookup. It is one of the most-read fields in the backend. [inferred] (`postgres_fdw.c:5269` — via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### read_stream
The high-level streaming-read API (`read_stream.h`/`.c`) that most callers use instead of the raw AIO interface: a caller supplies a callback yielding a sequence of block numbers, and the stream issues lookahead/prefetch reads and hands back pinned buffers in order. It is the PG18-era replacement for ad-hoc `ReadBuffer` loops in sequential and bitmap scans. [verified-by-code] (via `knowledge/files/src/backend/storage/aio/read_stream.c.md`).



### READ_STREAM_FULL
A `read_stream` begin-flag signaling that the caller will read every block with no skips, so the stream should not ramp up its look-ahead gradually. It is required when the consumer might request blocks via the stream callback that could fall outside the relation, and is commonly combined with `READ_STREAM_USE_BATCHING` by VACUUM, amcheck, pg_prewarm, and similar full-relation scanners. [verified-by-code] (`read-stream-prefetch.md` — via `knowledge/idioms/read-stream-prefetch.md`).



### read_stream_next_buffer
The read-stream API call that returns the next already-pinned buffer in a sequential/prefetched scan (optionally with per-buffer callback data), hiding the AIO prefetch machinery behind a simple pull interface. [verified-by-code] (via `knowledge/files/src/backend/storage/aio/read_stream.c.md`).



### READ_STREAM_USE_BATCHING
A read_stream flag that opts the stream into AIO batch mode; under it the caller's callback operates with strict restrictions — it must not block (without first calling `pgaio_submit_staged`) and must not start another nested batch. [verified-by-code] (`read_stream.h` — via `knowledge/files/src/include/storage/read_stream.h.md`).



### ReadBuffer
The canonical bufmgr entry that returns a pinned buffer for a given relation/fork/block, reading it from storage on a cache miss; the foundation under `ReadBufferExtended`/`StartReadBuffers`. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ReadBufferExtended
The general buffer-read entry point taking an explicit fork number and
read-mode (`RBM_NORMAL`, `RBM_ZERO_ON_ERROR`, …), used when the plain
`ReadBuffer` defaults don't fit — e.g. reading the visibility-map fork or
tolerating a torn page. It returns a pinned `Buffer`; the caller still must
`LockBuffer` for content access. [verified-by-code] (via
`knowledge/files/contrib/pageinspect/pageinspect.md`).



### ReadBufferWithoutRelcache
A buffer-read entry point that takes an explicit `RelFileLocator`/fork rather
than an open `Relation`, for code paths that have no relcache entry — recovery
redo, and cross-database or bootstrap reads. It returns a pinned buffer like
`ReadBuffer` but bypasses the smgr lookup through the relcache.
[verified-by-code] (`bufmgr.c:818-1031` — via
`knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### ReadHead
The pg_dump/pg_restore archiver routine that reads and validates an archive's header (the reverse of `WriteHead`): it parses the PGDMP magic, version, int/offset sizes, format byte, and compression algorithm, applying bounds checks (`intSize > 32` → fatal; version outside `K_VERS_1_0`..`K_VERS_MAX` → fatal; format mismatch → fatal). It is an early hardening surface for malicious archives. [verified-by-code] (`pg_backup_archiver.c:4196-4321` — via `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md`).



### ReadInt
The pg_dump/pg_restore archiver deserializer counterpart to `WriteInt`, reading a variable-byte-count signed integer; it version-gates on the explicit sign byte because pre-1.0 archives lacked one. In the custom format it drives length-prefixed block parsing (`_readBlockHeader`, `_skipData`, `_CustomReadFunc`), making it a key surface for hardening against attacker-controlled archives fed to a superuser pg_restore. [verified-by-code] (`pg_backup_archiver.c:2156-2212` — via `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md`).



### ReadNextFullTransactionId
A `varsup.c` accessor (`varsup.c:283`) returning the cluster's next-to-be-assigned `FullTransactionId` without allocating one, complementing `GetNewTransactionId` (which assigns) and `AdvanceNextFullTransactionIdPastXid`. It reads the value from shared transaction state for callers that need the current XID frontier as a 64-bit full XID. [verified-by-code] (`varsup.c` — via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### ReadRecord
The recovery routine that reads the next WAL record from the
`XLogReaderState`, validating its CRC and handling cross-page/segment
continuation; the loop heart of redo. [verified-by-code] (via
`knowledge/idioms/crash-recovery-startup.md`).



### ReadStream
The PG 17+ streaming-read abstraction: a caller supplies a callback that yields
the next block number, and the ReadStream issues read-ahead I/O (combining and
prefetching) so sequential-ish scans overlap I/O with computation without
hand-rolling prefetch. [verified-by-code] (via
`knowledge/idioms/read-stream-prefetch.md`).



### ReadyForQuery
The protocol message (tag 'Z') the backend sends at the end of each message-processing cycle to signal it is idle and report transaction status (idle / in-transaction / failed); the client may then send its next query. [verified-by-code] (via `knowledge/architecture/query-lifecycle.md`).



### ReceiveSharedInvalidMessages
The inval.c routine that pulls pending shared-invalidation messages from the sinval queue and applies each via a callback, falling back to `InvalidateSystemCaches` when the queue has overflowed; driven by `AcceptInvalidationMessages`. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### RECENTLY_DEAD
The `HEAPTUPLE_RECENTLY_DEAD` verdict from the `HTSV_Result` enum (`heapam.h:136`): a tuple whose `xmax` has committed but is still `>= OldestXmin`, so it is dead yet possibly visible to an older snapshot and cannot be removed. VACUUM/pruning leaves a `RECENTLY_DEAD` tuple alone unless it is followed in the HOT chain by a hard `DEAD` tuple, and CLUSTER/rewrite copies it verbatim (xmin/xmax/cmin/cmax/infomask) to preserve its visibility. [verified-by-code] (`heapam_visibility.c.md` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### RecentXmin
A cached lower-bound XID captured when a snapshot is taken — no transaction
below it is still in progress — used as a cheap early-out in visibility checks
before consulting the full snapshot. [verified-by-code] (via
`knowledge/idioms/snapshot-static-and-current.md`).



### Recheck Cond
The `EXPLAIN` line on a Bitmap Heap Scan reporting the original index condition re-evaluated against each heap tuple — needed when the in-memory bitmap went *lossy* (stored whole-page bits instead of per-tuple TIDs because it would have exceeded `work_mem`). [from-docs §14.1] (via `knowledge/docs-distilled/using-explain.md`).



### recheckforeignscan
The FDW callback that re-fetches and re-validates a locked foreign row during EvalPlanQual after a concurrent update to another table in the join. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeForeignscan.c.md`).



### record_out
The composite-type output function that serializes a `record`/row Datum to its parenthesized text form with per-field quoting and escaping; pageinspect's gist functions hand-reimplement its escaping rules for their tuple output. [from-comment] (via `knowledge/files/contrib/pageinspect/gistfuncs.c.md`).



### record_recv
The binary-input function for the generic `record`/composite pseudo-type: it
reads a wire-format tuple (column count, then per-column OID + length + binary
datum) and reconstructs a `HeapTuple`/`Datum`. The counterpart to `record_send`.
[verified-by-code] (via `knowledge/files/contrib/hstore/hstore_io.c.md`).



### RecordCacheArray
The backend-local array, indexed by record typmod, that caches `TupleDesc`s for
anonymous/composite record types so repeated lookups of the same row type are
O(1). [verified-by-code] (via `knowledge/idioms/typcache-entry-and-lookup.md`).



### RecordCacheHash
The backend-local hash table keyed by TupleDesc that assigns and looks up record typmods for anonymous composite (RECORD) types. [verified-by-code] (via `knowledge/idioms/typcache-record-typmod-and-shared.md`).



### recordDependencyOn
Inserts one `pg_depend` row recording that a dependent object depends on a referenced object with a given `deptype`; the single write primitive every higher-level dependency-recording helper funnels through. [verified-by-code] (via `knowledge/files/src/backend/catalog/pg_depend.c.md`).



### RecordNewMultiXact
The multixact routine that durably records a freshly allocated MultiXactId,
writing both its starting member offset and its member rows (bank-hopping
across SLRU banks as needed) so the next allocation's offset chains off this
one's end. [verified-by-code] (`multixact.c:816-961` — via
`knowledge/idioms/multixact-slru.md`).



### RecordPageWithFreeSpace
The routine that updates a relation's free-space map for one heap page after its free space changes; heap redo defers the call until after the buffer is released, and only issues it when the change is material. [verified-by-code] (via `knowledge/files/src/backend/access/heap/heapam_xlog.c.md`).



### RecordTransactionAbort
The xact.c routine that stamps a transaction's CLOG status as aborted at rollback; together with `RecordTransactionCommit` it is the only writer of final commit-status bits, calling `TransactionIdSetTreeStatus` so the xid and all its subxids flip atomically. [verified-by-code] (via `knowledge/files/src/backend/access/transam/clog.c.md`).



### RecordTransactionCommit
The routine that makes a transaction durable: it snapshots pending invalidation
messages, writes (and flushes, per `synchronous_commit`) the commit WAL record,
and marks the xid committed in CLOG — strictly before sinval broadcast so other
backends never see the commit before its catalog effects. [from-comment]
(`inval.c:30` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### recovery_min_apply_delay
GUC delaying replay on a standby by a fixed interval; it delays only COMMIT records (other WAL is replayed immediately), so the standby lags the primary by roughly this amount for visible changes. [from-README] (via `knowledge/docs-distilled/runtime-config-replication.md`).



### RecoveryInProgress
The cheap check that returns true while the server is still replaying WAL
(crash or archive/standby recovery) and has not yet reached a consistent,
read-write state. Many operations gate on it — e.g. a transaction notes
`startedInRecovery` so it knows it ran read-only against a standby snapshot.
[verified-by-code] (via
`knowledge/files/src/backend/access/transam/xact.c.md`).



### RecursiveUnion
The executor node implementing `WITH RECURSIVE`: it repeatedly evaluates the recursive term against a working table until no new rows appear, using a hash table or tuplestore to deduplicate in `UNION` mode. [verified-by-code] (via `knowledge/files/src/include/executor/nodeRecursiveunion.md`).



### RedoRecPtr
The cached WAL position from which recovery would start (the latest
checkpoint's redo point); `GetRedoRecPtr` exposes it and it gates whether a
page change needs a full-page image. [verified-by-code] (`xlog.c:6937` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### redostartlsn
`RedoStartLSN` is the LSN at which crash/archive recovery must begin replay; if it precedes the checkpoint record's location, the record there must still be read. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlogrecovery.c.md`).



### reduce_outer_joins
The planner optimisation that detects strict qualifiers above an outer join's nullable side and demotes the outer join to an inner or anti-join; it must run after expression preprocessing has canonicalised the quals. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### RefetchForeignRow
The FDW callback that re-fetches a foreign row by its row-identifier for EPQ
rechecks under concurrent updates, the foreign-table analogue of re-reading a
heap tuple. [verified-by-code] (via
`knowledge/idioms/fdw-routine-callbacks.md`).



### REGBUF_STANDARD
A `XLogRegisterBuffer` flag (`0x08`) declaring that a registered buffer uses the standard page layout, so the WAL machinery may omit the free space between `pd_lower` and `pd_upper` (the "hole") from a full-page image. It is one of the REGBUF_* flag family that also includes `REGBUF_WILL_INIT`, `REGBUF_NO_IMAGE`, and `REGBUF_KEEP_DATA`. [verified-by-code] (`xloginsert.h` — via `knowledge/files/src/include/access/xloginsert.h.md`).



### REGBUF_WILL_INIT
The `XLogRegisterBuffer` flag declaring that redo will re-initialize the
page from scratch, so the record need not carry the page's prior contents
and full-page-image logging is suppressed for it. [verified-by-code] (via
`knowledge/subsystems/access-nbtree.md`).



### regd_count
Snapshot refcount field: the number of `ResourceOwner` registrations (plus pairing-heap membership) keeping a *registered* snapshot alive; managed by snapmgr.c alongside `active_count`, and when both reach zero the snapshot may be freed. [verified-by-code] (`snapshot.h:37` — via `knowledge/idioms/snapshot-active-stack-and-registered.md`).



### regex_t
The compiled-regular-expression object produced by `pg_regcomp` from the backend's bundled Spencer regex engine; `pg_regexec` runs it against input. Type code and `~`/`SIMILAR TO` operators cache it to avoid recompiling per row. [inferred] (via `knowledge/files/src/backend/regex/regcomp.c.md`).



### RegisterBackgroundWorker
The static registration call a module makes from `_PG_init` (under
`shared_preload_libraries`) to have the postmaster start a background worker;
the runtime counterpart is `RegisterDynamicBackgroundWorker`. [verified-by-code]
(via `knowledge/docs-distilled/bgworker.md`).



### RegisterBuiltinShmemCallbacks
The newer shared-memory bootstrap mechanism (in `ipci.c`) that expands `subsystemlist.h` to register each built-in subsystem's shmem size-request and init callbacks, replacing the older hand-maintained enumeration of shmem-using subsystems. [verified-by-code] (`ipci.c` — via `knowledge/files/src/backend/storage/ipc/ipci.c.md`).



### RegisterCatcacheInvalidation
The internal inval routine that records a `(cacheId, hashValue, dbId)` catcache invalidation for the current command, queued for broadcast at command end / commit; receivers match by hash, not TID, so VACUUM FULL stays safe. [verified-by-code] (`inval.c:604` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### RegisterCustomRmgr
The rmgr.c API (`rmgr.c:107`) an extension calls at load time to claim a custom `RmgrId` and install its `RmgrData` callback table, so its WAL records can be replayed and described. [verified-by-code] (`rmgr.c:107` — via `knowledge/files/src/backend/access/transam/rmgr.c.md`).



### RegisterDynamicBackgroundWorker
The runtime API a backend calls to ask the postmaster to start a background
worker on the fly (as opposed to `RegisterBackgroundWorker` at shared_preload
time), optionally learning the worker's PID through a
`BackgroundWorkerHandle`. [verified-by-code] (`bgworker.h:69-75` — via
`knowledge/idioms/bgworker-and-parallel.md`).



### RegisteredSnapshots
The count/set of snapshots registered with a resource owner and pinned in the
backend; while non-empty they hold back the xmin horizon, which is why leaks
here stall vacuum. [verified-by-code] (via
`knowledge/data-structures/snapshot-lifecycle.md`).



### RegisterExtensionExplainOption
The hook by which a loaded extension adds a custom EXPLAIN option keyword and its handler, so third-party modules (e.g. pg_plan_advice, pg_overexplain) can extend EXPLAIN output without a core patch. [verified-by-code] (via `knowledge/files/contrib/pg_plan_advice/pg_plan_advice.c.md`).



### RegisterRelcacheInvalidation
The internal inval routine that records a relcache invalidation (by relation OID plus database OID) for the current command, queued alongside catcache invalidations for broadcast at command end / commit. [verified-by-code] (`inval.c:632` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### RegisterShmemCallbacks
The modern shared-memory-region API: an extension registers a `ShmemCallbacks` table (`request_fn`/`init_fn`/`attach_fn`) via this call so its segment is sized at request time and initialized/attached at the right startup phase, replacing the older `shmem_request_hook`/`shmem_startup_hook` pair. [verified-by-code] (via `knowledge/scenarios/add-new-shared-memory-region.md`).



### RegisterSnapshot
Bumps a snapshot's reference count and tracks it under the active resource
owner so it survives past the call that took it; `UnregisterSnapshot` releases
it. Callers that stash a snapshot (cursors, held portals, long-lived scans) must
register it or risk it being recycled out from under them. [from-comment] (via
`knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### RegisterSubXactCallback
The function that registers a callback to be invoked on subtransaction events (start/commit/abort of a subxact), paired with `UnregisterSubXactCallback`; it is the subtransaction-level counterpart to `RegisterXactCallback`. [verified-by-code] (`xact.c` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### RegisterTwoPhaseRecord
Called during PREPARE to append a typed record (locks, pg_notify, invalidation messages, etc.) into the two-phase state file that a later COMMIT/ROLLBACK PREPARED replays, letting subsystems persist their own prepared-xact state. [verified-by-code] (`twophase.c` — via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### RegisterXactCallback
Installs a callback invoked at transaction-event boundaries
(commit/abort/prepare), the hook extensions use to flush or roll back their own
transaction-scoped state. [verified-by-code] (via
`knowledge/idioms/commit-transaction-sequence.md`).



### regression_main
The shared `pg_regress` test-driver framework function (declared in `pg_regress.h`) that each test-suite `main` forwards to with suite-specific callbacks; the ECPG variant, for example, is a one-line forwarder passing three ecpg callbacks. [verified-by-code] (`pg_regress_ecpg.c:259-266` — via `knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md`).



### ReInitializeDSM
The parallel-executor callback phase (`ExecXxxReInitializeDSM`) that resets a node's already-allocated DSM shared state before a rescan of the parallel plan, so a re-run reuses the segment instead of re-estimating and re-allocating it. It sits between `InitializeDSM` (first setup) and `InitializeWorker` in the parallel-node protocol. [verified-by-code] (via `knowledge/files/src/backend/executor/nodeCustom.c.md`).



### relacl
The `pg_class` ACL column holding a table's `aclitem[]` grants; a NULL `relacl` means "default privileges apply" (owner holds all, plus PUBLIC's built-in defaults) rather than an empty ACL. [from-docs] (via `knowledge/docs-distilled/ddl-priv.md`).



### relation
The internal name for any table-like object (table, index, sequence,
materialized view, composite type) — anything with a `pg_class` row and a
relfilenode. The in-memory `RelationData`/`Relation` handle caches a relation's
catalog metadata, tuple descriptor, and access-method routines. [from-README]
(via `knowledge/idioms/catalog-conventions.md`).



### relation_close
Drops the reference (and optionally the lock) on a relcache entry opened with `relation_open`; `table_close`/`index_close`/`sequence_close` all forward to it. [verified-by-code] (via `knowledge/files/src/backend/access/common/relation.c.md`).



### relation_open
Takes the requested lock then resolves a relcache entry via `RelationIdGetRelation`, asserting that some lock is held when `lockmode == NoLock` (outside bootstrap); the low-level open that `table_open`/`index_open` build on. [verified-by-code] (`relation.c:47` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### relation_openrv
Opens a relation named by a `RangeVar`: resolves it via `RangeVarGetRelid` (namespace search) then calls `relation_open`. It calls `AcceptInvalidationMessages()` first when locking, because GRANT/REVOKE update ACLs without taking a relation lock. [from-comment] (via `knowledge/files/src/backend/access/common/relation.c.md`).



### RelationBuildDesc
Builds a `RelationData` entry from the catalogs on a relcache miss; it runs
under a recursion-and-retry guard (`InProgressEnt`) so invalidations arriving
mid-build are handled correctly. [verified-by-code] (`relcache.c:166` — via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).



### relationbuildpartitiondesc
`RelationBuildPartitionDesc` (`partdesc.c`) builds a relation's `PartitionDesc` whenever the relcache entry is (re)built, reading the children's bounds from the catalog. [verified-by-code] (via `knowledge/subsystems/partitioning.md`).



### RelationBuildTupleDesc
The relcache load step that reads a relation's pg_attribute rows to construct its TupleDesc, called from RelationBuildDesc while building a RelationData. [verified-by-code] (via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### RelationCacheInitFilePostInvalidate
The closing step of the relcache init-file invalidation bracket: it releases `RelCacheInitLock` after the init file has been deleted and the shared-invalidation messages have been sent at commit (`AtEOXact_Inval`). [verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### RelationCacheInitFilePreInvalidate
The relcache init-file (pg_internal.init) invalidation pre-step that unlinks the stale cache file before catalog changes commit; it is paired with RelationCacheInitFilePostInvalidate. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationCacheInitialize
The first phase of relcache bring-up during backend startup: it creates the relcache hash table and the CacheMemoryContext, before the init file or catalog can be consulted to populate entries for the shared and bootstrap catalogs. [verified-by-code] (`relcache.c` — via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationCacheInvalidate
The relcache handler for shared-invalidation-queue overflow and `DISCARD ALL`, performing a two-phase full sweep of the relcache; it first calls `RelationMapInvalidateAll` and runs `smgrreleaseall` between phases. It is invoked from `inval.c`'s `LocalExecuteInvalidationMessage`, distinct from the per-relation `RelationCacheInvalidateEntry`. [verified-by-code] (`relcache.c` — via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationCacheInvalidateEntry
Marks a single relcache entry invalid in response to a targeted sinval message,
so the next `RelationIdGetRelation` rebuilds it from the catalogs.
[verified-by-code] (via `knowledge/idioms/syscache-invalidation-flow.md`).



### RelationClearRelation
The relcache routine that rebuilds (or discards) a `Relation` entry whose
catalog state changed, carefully preserving the struct address so existing
pointers stay valid across the refresh. [verified-by-code] (via
`knowledge/idioms/relcache-build.md`).



### RelationClose
Drops one reference from a relcache entry opened by `relation_open`; the entry stays cached for reuse and is only physically freed at transaction end or on invalidation, so close is a refcount decrement, not a free. [verified-by-code] (`relation.c` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### RelationData
The in-memory relation descriptor (`Relation`) cached by the relcache — one
per open relation, keyed by OID and built on demand from
`pg_class`/`pg_attribute`/etc. — holding everything the executor needs about a
table or index. [verified-by-code] (`relcache.c:10` — via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).



### relationfindrepltuplebyindex
The logical-replication apply routine that locates a target tuple via the replica-identity index, falling back to a sequential scan when no usable index exists. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### RelationGetBufferForTuple
The heap-insertion helper that picks (or extends to) a page with room for a new
tuple: it tries the relation's cached target block, consults the FSM, and may
extend the relation, returning a pinned, exclusively-locked buffer. It also
encodes the two-buffer lock-ordering rule used by cross-page UPDATE.
[from-comment] (`hio.c:500` — via
`knowledge/files/src/include/access/hio.h.md`).



### RelationGetDescr
The macro returning a relation's `TupleDesc` (`rel->rd_att`) — the column
layout used to form and deform tuples. amcheck-style invariants compare a
tuple's stored attribute count against `RelationGetDescr(rel)->natts`.
[verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### RelationGetIndexList
Returns the list of index OIDs on a relation from the relcache (cached and refreshed on invalidation); the starting point for code that must consider every index, e.g. building a change-notification payload or planning index maintenance. [verified-by-code] (via `knowledge/files/contrib/tcn/tcn.c.md`).



### RelationGetNumberOfBlocks
Returns the current block count of a relation fork by asking smgr (`smgrnblocks`); the upper bound for any block-scanning loop and a value that can grow under concurrent extension. [verified-by-code] (via `knowledge/files/contrib/pageinspect/btreefuncs.c.md`).



### RelationGetRelationName
Macro returning the `char *` name of a relation from its cached `pg_class` form; handy for error messages, often combined with `psprintf` to build a string without pre-sizing a buffer. [verified-by-code] (via `knowledge/files/src/common/psprintf.c.md`).



### RelationGetRelid
The rel.h accessor macro returning a relation's OID (rd_id) from its open Relation handle; ubiquitous throughout the backend wherever an OID is needed from an already-open relation. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationIdGetRelation
Looks up a `Relation` by OID in the relcache, building the entry from the
catalogs on a miss and bumping its reference count; paired with
`RelationClose`. [verified-by-code] (via
`knowledge/idioms/catalog-conventions.md`).



### RelationMapUpdateMap
Records a new relfilenumber for a mapped (nailed/shared) catalog in the relation-map file, the indirection that lets catalogs like pg_class be rewritten by VACUUM FULL/CLUSTER even though their own physical location can't be stored in themselves. [verified-by-code] (`relmapper.c` — via `knowledge/files/src/backend/utils/cache/relmapper.c.md`).



### RelationNeedsWAL
A macro that is true when a relation's changes must be WAL-logged (a permanent relation, sufficient `wal_level`, and not currently in an unlogged/init-fork or in-place exception); access methods gate `log_newpage` and redo-record emission on it. [verified-by-code] (via `knowledge/files/src/include/utils/rel.md`).



### relationOids
The list of relation (and other dependency) OIDs a cached plan was built against, recorded so that an invalidation on any of them marks the `CachedPlanSource` stale and forces a replan. It is how DDL on a referenced table invalidates prepared statements. [inferred] (`plancache.c:393` — via `knowledge/subsystems/utils-cache.md`).



### RelationPutHeapTuple
Places an already-prepared heap tuple onto a target buffer page during insert
and stamps the tuple's `t_self` with the resulting TID. [verified-by-code]
(via `knowledge/files/src/backend/access/heap/heapam.c.md`).



### RelationRebuildRelation
The relcache rebuild that reconstructs a `Relation` entry in place after an invalidation, deliberately preserving the `RelationData` pointer so that code holding the pointer stays valid across the rebuild. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationRelationId
The relation OID of the `pg_class` catalog (1259), declared via `CATALOG(pg_class,1259,RelationRelationId) BKI_BOOTSTRAP ...`. It is the `classId` used in an `ObjectAddress` to denote a table/relation object, with a non-zero `objectSubId` (the attnum) identifying a specific column. [verified-by-code] (`pg_class.h.md` — via `knowledge/files/src/include/catalog/pg_class.h.md`).



### RelationSetNewRelfilenumber
Assigns a relation a fresh relfilenumber (new physical storage) and updates pg_class plus invalidation; used by TRUNCATE, table rewrite / VACUUM FULL, and heap creation. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelationTruncate
Truncates a relation's storage to zero (or a given) length at the smgr level and
WAL-logs it; used by `TRUNCATE` and by VACUUM when it can shrink the relation's
trailing empty pages. [verified-by-code] (via
`knowledge/idioms/vacuum-truncate-relation.md`).



### relcache (relation cache)
The per-backend cache of `RelationData` entries, so opening a frequently-used
table doesn't re-read its `pg_class`/`pg_attribute`/index metadata each time. It
is kept coherent by shared-invalidation messages and can be rebuilt in place to
preserve pointer identity. [from-comment] (via
`knowledge/files/src/backend/utils/cache/relcache.c.md`).



### RelcacheInitFileInval
The flag/mechanism marking the relcache init file (the on-disk cache of
nailed/critical catalog entries) stale, forcing a rebuild so backends don't load
an outdated bootstrap snapshot. [verified-by-code] (via
`knowledge/idioms/syscache-invalidation-flow.md`).



### release_context
The JIT-provider vtable callback that frees a `JitContext` and its compiled code; `jit.c` forwards to it, and it also runs from the resource-owner callback at (sub)xact end. [verified-by-code] (via `knowledge/files/src/backend/jit/jit.c.md`).



### ReleaseBuffer
Drops one pin on a shared or local buffer without touching its content lock; the unpin half of the pin/unpin discipline, called once per `ReadBuffer` to let the buffer become evictable again. [verified-by-code] (via `knowledge/files/contrib/pgstattuple/pgstatapprox.c.md`).



### ReleaseCurrentSubTransaction
The xact.c routine that commits the current internal subtransaction (the success path of a PL/pgSQL `BEGIN ... EXCEPTION` block); its rollback counterpart is `RollbackAndReleaseCurrentSubTransaction`. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### ReleaseSysCache
The mandatory release call that pairs with every non-Copy `SearchSysCache*` hit; skipping it leaks the pin and raises a "cache reference leak" warning at transaction end. [verified-by-code] (via `knowledge/idioms/catalog-conventions.md`).



### RelFileLocator
The physical identity of a relation's storage: the
`(spcOid, dbOid, relNumber)` triple that names the on-disk file set, distinct
from the relation's catalog OID. `smgropen`/`smgrcreate` and WAL records use it
so storage survives catalog OID reuse. [verified-by-code] (`storage.c:122` — via
`knowledge/files/src/backend/catalog/storage.c.md`).



### RelFileLocatorBackend
A relation's physical-file identity (`RelFileLocator`) extended with the
backend that owns it, so temporary relations — whose files are private to one
backend — are distinguished from shared/permanent ones; tested via
`RelFileLocatorBackendIsTemp`. [verified-by-code] (`bufmgr.c:4786-4793` — via
`knowledge/subsystems/storage-buffer.md`).



### relfilenode
The on-disk file identifier for a relation's main fork, distinct from its catalog OID; commands like CLUSTER/VACUUM FULL swap `relfilenode` (via `swap_relation_files`) to atomically replace a table's storage. [verified-by-code] (`swap_relation_files` at line 1529 — via `knowledge/files/src/backend/commands` cluster docs).



### relfilenode (RelFileLocator)
The on-disk identity of a relation's storage — the (tablespace, database,
relfilenode-number) triple expressed as a `RelFileLocator` — distinct from the
catalog OID so operations like `TRUNCATE`/`CLUSTER` can swap storage without
changing the OID. The path on disk is derived from it by `relpathbackend`.
[from-comment] (via `knowledge/files/src/common/relpath.c.md`).



### RelFileNumber
The integer that names a relation's on-disk file within its tablespace/
database — the "relfilenode" portion of a `RelFileLocator`, distinct from the
relation's catalog OID so that `TRUNCATE`/`VACUUM FULL`/rewrites can swap
storage without changing the OID. `pg_upgrade` preserves these explicitly via
`binary_upgrade_next_heap_pg_class_relfilenumber`. [verified-by-code] (via
`knowledge/files/src/include/catalog/binary_upgrade.h.md`).



### relfrozenxid
The `pg_class` column recording a relation's freeze horizon: every tuple in the relation is either frozen or has `xmin` at least this XID. VACUUM advances it, and a value within `vacuum_failsafe_age` of wraparound triggers emergency freezing. [verified-by-code] (`vacuumlazy.c:2462-2476` — via `knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).



### relids
A `Relids` (Bitmapset) identifying a set of base relations by their rangetable index — the dominant Bitmapset use in the planner, carried on `RelOptInfo.relids` and used to key parameterized paths and join relations. [verified-by-code] (via `knowledge/data-structures/bitmapset.md`).



### RelIdToTypeIdCacheHash
A secondary reverse-index hash in typcache.c that maps a pg_class relid to the OID of the cached composite type whose `typrelid == relid`. It exists so `TypeCacheRelCallback` can find the composite typcache entry to invalidate from just a relcache event's relid, and an entry is dropped once the typcache entry no longer caches any composite-dependent data. [verified-by-code] (`typcache.c.md` — via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### relNumber
The `RelFileNumber` component of a `RelFileLocator` — the per-tablespace-unique number that, with the spc/db OIDs, names a relation's physical files on disk. It is usually but not always equal to the relation's pg_class OID (it changes on rewrite). [inferred] (`buf_internals.h:161` — via `knowledge/subsystems/storage-buffer.md`).



### RelOptInfo
The planner's per-relation bookkeeping node: for each base or join relation it
accumulates candidate `Path`s, row/width estimates, and available columns. Join
planning combines smaller `RelOptInfo`s into larger ones until the whole join
tree has a cheapest Path. [from-comment] (via
`knowledge/subsystems/optimizer.md`).



### relptr
A "relative pointer" — an offset stored relative to a known base address rather
than an absolute pointer — so a structure living in a shared or relocatable
memory region (e.g. the freepage manager, DSA) stays valid regardless of where
each process maps the region. [verified-by-code] (via
`knowledge/files/src/include/utils/relptr.md`).



### RELSEG_SIZE
The build-time number of blocks per physical segment file (default 131072,
i.e. 1 GB at 8 kB blocks); a relation larger than one segment is stored as
`<relfilenode>`, `.1`, `.2`, ... files. [verified-by-code] (via
`knowledge/files/src/backend/storage/file/buffile.c.md`).



### reltuples
The `pg_class` column holding the planner's cached estimate of a relation's live row count, refreshed by ANALYZE and VACUUM and scaled by the optimizer when the physical page count has changed. [from-comment] (via `knowledge/files/contrib/postgres_fdw` and `knowledge/subsystems/optimizer.md`).



### reorder buffer
The logical-decoding component that buffers each in-progress transaction's
change stream and replays it, in commit order, to the output plugin only once
the transaction commits — turning the interleaved physical WAL back into
per-transaction logical change sets. Large transactions can spill to disk.
[from-comment] (via
`knowledge/files/src/backend/replication/logical/reorderbuffer.c.md`).



### ReorderBuffer
The logical-decoding component that reassembles interleaved WAL changes into per-transaction, commit-ordered streams, spilling large transactions to disk and replaying them at commit (or streaming them for in-progress decoding). [verified-by-code] (via `knowledge/files/src/include/replication/reorderbuffer.h.md`).



### ReorderBufferChange
A single decoded WAL event (insert/update/delete/message/...) buffered inside logical decoding; changes are accumulated per `ReorderBufferTXN` and replayed to the output plugin in commit order. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/reorderbuffer.c.md`).



### ReorderBufferCommit
Replays a logical transaction at COMMIT time (`reorderbuffer.c:2882`): it streams the transaction's buffered changes, in order, through the output plugin via `ReorderBufferReplay`, having stitched sub-transactions onto the top-level one first. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/reorderbuffer.c.md`).



### ReorderBufferTXN
The per-xid container inside the reorder buffer holding a transaction's decoded `ReorderBufferChange`s plus bookkeeping (commit time, base snapshot, subtxns, invalidation messages); one exists per in-flight top-level or sub transaction. [verified-by-code] (via `knowledge/files/src/include/replication/reorderbuffer.h.md`).



### REPACK
The in-place table-reorganization command (`pg_repack`-style `REPACK`, PG 18) that rewrites a table to remove bloat and re-cluster it while holding weaker locks than `CLUSTER`/`VACUUM FULL` for most of the operation. Its planner/executor wiring lives behind `repack.h`. [verified-by-code] (via `knowledge/files/src/include/commands/repack.h.md`).



### repalloc
Resizes a palloc'd chunk in the current memory context, preserving contents and returning the (possibly moved) pointer; throws on OOM like palloc. The grow primitive behind dynamic buffers such as `StringInfo` and `mbuf`. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/mbuf.md`).



### replication slot
A named, persistent server-side marker that records how far a consumer
(physical standby or logical subscriber) has confirmed receiving WAL, so the
primary retains the WAL (and, for logical, the catalog xmin) that consumer still
needs. Slots prevent premature WAL removal at the cost of unbounded retention if
a consumer disappears. [from-comment] (via
`knowledge/files/src/backend/replication/slot.c.md`).



### ReplicationSlot
The in-memory (shared) representation of a replication slot — physical or logical — pinning the WAL and (for logical) the catalog xmin a consumer still needs; its durable subset is `ReplicationSlotPersistentData`, checkpointed to `pg_replslot`. [verified-by-code] (via `knowledge/files/src/include/replication/slot.h.md`).



### ReplicationSlotControlLock
An LWLock guarding the replication-slot array: taken in shared mode to iterate over slots and in exclusive mode to flip a slot's `in_use` flag. It sits alongside `ReplicationSlotAllocationLock` (which serializes allocate/free) and each slot's per-slot spinlock `mutex` (which protects mutable fields). [verified-by-code] (`slot.c` — via `knowledge/files/src/backend/replication/slot.c.md`).



### ReplicationSlotRelease
Detaches the current backend from the replication slot it has acquired (clears active_pid and the in-memory acquired state) without dropping the slot, so the slot's retained-WAL and xmin guarantees persist for the next consumer. [verified-by-code] (via `knowledge/subsystems/replication.md`).



### ReplicationSlotsComputeRequiredXmin
The aggregator that scans all replication slots and computes the minimum xmin
any slot still needs, feeding the global oldest-xmin so VACUUM does not remove
tuples a logical or physical consumer may still require. [verified-by-code]
(`slot.c:1220` — via `knowledge/subsystems/replication.md`).



### ReplOriginId
The compact 2-byte identifier for a replication origin (the node that produced a change); stored alongside commit timestamps in pg_commit_ts and stamped on WAL commit records so logical replication can avoid re-applying its own changes. [verified-by-code] (`commit_ts.c:55-59` — via `knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### ReportApplyConflict
Emits a structured log message describing a logical-replication apply conflict —
including the conflict type and the local and remote tuples — before the apply
worker's default ERROR halts replication for operator intervention. [verified-by-code]
(via `knowledge/idioms/apply-conflict-resolution.md`).



### RequestAddinShmemSpace
Called from an extension's `shmem_request_hook` to add bytes to the postmaster's shared-memory size calculation, reserving room the extension will later carve up in its `shmem_startup_hook`. Forgetting it makes `ShmemInitStruct` fail when the segment is already full. [inferred] (`ipci.c:44` — via `knowledge/files/src/backend/storage/ipc/ipci.c.md`).



### RequestCheckpoint
The routine (reached for a `CHECKPOINT` command, among other callers) that
signals the checkpointer to perform a checkpoint, optionally blocking until it
completes depending on the requested flags. [verified-by-code]
(`xlog.c::RequestCheckpoint` — via `knowledge/subsystems/tcop.md`).



### RequestNamedLWLockTranche
Called from `shmem_request_hook` to reserve a contiguous block of LWLocks under a named tranche at postmaster startup; the locks are later retrieved with `GetNamedLWLockTranche`. This is the static, preload-time way to obtain LWLocks for an extension. [inferred] (`lwlock.c:625` — via `knowledge/scenarios/add-new-lwlock-tranche.md`).



### require_auth
The libpq connection option enforcing an allowed-authentication-method allowlist: `conn->allowed_auth_methods` is checked per request, and for `AUTH_REQ_OK` the code additionally insists `client_finished_auth` was latched (SCRAM verified, OAuth bearer sent, etc.) unless the user explicitly permitted `trust`. [verified-by-code] (via `knowledge/files/src/interfaces/libpq/fe-auth.c.md`).



### ReScan
The executor's restart operation: `ExecReScan(node)` cooperatively resets a plan-subtree's state so it can be re-evaluated (e.g. for the inner side of a nested loop or a correlated subplan), reusing already-built structures where possible. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### ReScanForeignScan
The FDW callback that restarts a foreign scan from the beginning (e.g. for the
inner side of a nestloop with changed parameters), resetting cursor state.
[verified-by-code] (via `knowledge/idioms/fdw-iterate-scan.md`).



### ReserveXLogInsertLocation
Reserves a byte range in the WAL insertion stream by advancing the shared CurrBytePos, returning the start LSN that a record's xl_prev is stamped with before its CRC is computed. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### reset_after_error
One of the three JIT-provider vtable callbacks (with `compile_expr` and `release_context`); `jit.c` forwards `reset_after_error` to the loaded provider to discard JIT state after an error. [verified-by-code] (via `knowledge/files/src/backend/jit/jit.c.md`).



### ResetCancelConn
The fe_utils cancel-handling routine that clears the connection registered as the Ctrl-C cancel target (freeing the `PGcancel` and setting it NULL). Frontend tools bracket each query with `SetCancelConn`/`ResetCancelConn` so the SIGINT handler only ever cancels the currently in-flight connection; the swap nulls the pointer before freeing so the handler can never see a mid-free pointer. [verified-by-code] (`cancel.c:106` — via `knowledge/files/src/fe_utils/cancel.c.md`).



### ResetExprContext
The executor macro that resets an `ExprContext`'s `ecxt_per_tuple_memory` child context, freeing all per-tuple scratch allocations from expression evaluation. Each plan node owning an ExprContext is responsible for calling it once per row (e.g. NestLoop calls it at the top of each `ExecNestLoop`); the ordering trap is that resetting before clearing a slot whose `tts_values[]` point into that memory leaves the slot dangling. [verified-by-code] (`nodeNestloop.c:92` — via `knowledge/data-structures/exprcontext.md`).



### ResetLatch
Clears a process latch's set flag so a subsequent `WaitLatch` will block until
newly signalled; it asserts the caller owns the latch and must be called
before re-checking the work condition to avoid lost wakeups.
[verified-by-code] (`latch.c:374-388` — via
`knowledge/subsystems/storage-ipc.md`).



### ResolveRecoveryConflictWithSnapshot
The standby-side routine called during WAL redo (btree delete/vacuum, heap prune, …) that cancels read-only queries whose snapshot predates a record's `snapshotConflictHorizon`, so the cleanup the record describes can be applied. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtxlog.c.md`).



### RESOURCE_RELEASE_AFTER_LOCKS
The third and final phase of `ResourceOwnerRelease`, run post-commit after locks have been released, used to free resources that depended on those locks (e.g. relcache pins). The phase ordering (`BEFORE_LOCKS` → `LOCKS` → `AFTER_LOCKS`) matters because some cleanup must happen only after lock release. [verified-by-code] (`resowner.c` — via `knowledge/data-structures/resourceowner.md`).



### RESOURCE_RELEASE_BEFORE_LOCKS
The first phase of resource-owner release, run before locks are dropped, in which buffer pins, tuple descriptors, relcache references, and similar resources are freed. [verified-by-code] (via `knowledge/files/src/backend/utils/resowner/resowner.c.md`).



### ResourceOwner
The per-scope bookkeeper that records the buffers, relcache pins, catcache
references, locks, and files a (sub)transaction or portal acquired, so they can
all be released deterministically at commit/abort even on error. New owners nest
under a parent. [from-comment] (`pl_handler.c:223` — via
`knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



### ResourceOwnerDesc
The const descriptor a resource kind registers with the resource-owner machinery, naming the kind and specifying its `release_phase`, `release_priority`, a `ReleaseResource` callback, and an optional `DebugPrint`. Resources with larger `release_priority` are released first; extensions ship their own `ResourceOwnerDesc` (allocated once, since it is const) to slot custom resources into the cleanup ordering. [verified-by-code] (via `knowledge/data-structures/resourceowner.md`).



### ResourceOwnerEnlarge
Ensures a `ResourceOwner` has room to remember one more resource of a kind
before the resource is actually acquired, so the subsequent remember step cannot
fail partway and leak. [verified-by-code] (via
`knowledge/data-structures/resourceowner.md`).



### ResourceOwnerForget
The resource-owner API call (`resowner.c:561`) that removes a previously `ResourceOwnerRemember`'d resource from the owner's tracking array. It is the inverse of `ResourceOwnerRemember`; specialized variants like `ResourceOwnerForgetLock` exist for resource kinds with dedicated storage. [verified-by-code] (`resowner.c` — via `knowledge/files/src/backend/utils/resowner/resowner.c.md`).



### ResourceOwnerRelease
Walks a resource owner at transaction/subtransaction end (or error) and releases
everything it tracks — buffer pins, locks, file descriptors, tudescs — in a
defined phase order. [verified-by-code] (via
`knowledge/data-structures/resourceowner.md`).



### ResourceOwnerReleaseAll
The internal routine driving bulk release of an owner's remembered resources of a given phase. As of fix `ef01ca6dbc` (bug #19527, backpatched to 17) it forgets each item from the owner before invoking `kind->ReleaseResource`, so an error thrown mid-release cannot re-enter abort cleanup and double-free the same item — "prefer to leak the item than crash." [verified-by-code] (`resowner.c` — via `knowledge/upstream-deltas/2026-06-23.md`).



### ResourceOwnerRemember
The resource-owner registration call (`resowner.h:148-150`) that records a resource (buffer pin, lock, catcache ref, etc.) of a given kind against an owner so it is automatically released at transaction end. It is paired with `ResourceOwnerForget` (the inverse) and must be preceded by `ResourceOwnerEnlarge` to ensure space; specialized variants like `ResourceOwnerRememberLock` exist for kinds with dedicated storage. [verified-by-code] (`resourceowner.md` — via `knowledge/data-structures/resourceowner.md`).



### restart_after_crash
GUC (default on) making the postmaster reinitialize and restart the cluster after a backend crash rather than exiting; turning it off is used by supervisors that prefer to manage restarts externally. [from-README] (via `knowledge/docs-distilled/runtime-config-error-handling.md`).



### restart_lsn
The replication-slot field marking the oldest WAL location the slot still requires, so the server must retain WAL from this point forward; advancing consumers move it forward and free older segments. A stalled or abandoned slot pins `restart_lsn`, causing unbounded WAL retention. [verified-by-code] (via `knowledge/files/src/backend/replication/walsender.c.md`; see `knowledge/subsystems/replication.md`).



### restore_command
The recovery configuration command that fetches an archived WAL segment (or other fixed-size file) by shelling out to an operator-supplied command string; archive recovery and `pg_combinebackup` use it to pull WAL that is no longer present locally. Its shell-interpolation of `%f`/`%p` is a long-standing injection-surface caveat. [verified-by-code] (via `knowledge/files/src/fe_utils/archive.c.md`).



### RestoreArchive
The pg_restore core routine that walks a parsed archive's table-of-contents
and replays each entry's SQL/data into the target database (or a script); it
is also reused in a special mode to build the tar format's `restore.sql`.
[from-comment] (via `knowledge/files/src/bin/pg_dump/pg_backup_tar.c.md`).



### RestoreArchivedFile
Runs the `restore_command` to fetch a WAL segment (or other archived file)
from the archive into pg_wal during recovery, validating the result before
use. [verified-by-code] (`xlogarchive.c:55` — via
`knowledge/files/src/backend/access/transam/xlogarchive.c.md`).



### RestoreOptions
The pg_dump/pg_restore struct (in `pg_backup.h`) holding the full bag of restore-time switches — `createDB`, `noOwner`, `disable_triggers`, `dropSchema`, `if_exists`, `single_txn`, `txn_size`, `cparams`, `restrict_key`, the object-id filter list, etc. It is exposed by value to pg_dump/pg_restore (flat-copied per parallel worker and `memcpy`'d for temporary restore scripts), so any field reorder/insertion is an ABI break requiring the binaries be recompiled as one unit. [verified-by-code] (`pg_backup.h:97-169` — via `knowledge/files/src/bin/pg_dump/pg_backup.h.md`).



### RestoreSnapshot
Reconstructs a `Snapshot` from its serialized byte form, used by parallel
workers to install the leader's snapshot and by exported-snapshot import.
[verified-by-code] (via
`knowledge/idioms/snapshot-export-historic-parallel.md`).



### RestoreTransactionSnapshot
The snapmgr.c routine a parallel worker calls to install the leader's serialized transaction snapshot as its own; it forwards to `SetTransactionSnapshot`, which sets `TransactionXmin` from the snapshot and registers the worker's xmin dependency on the leader's PGPROC. Snapshots cannot be taken during parallel mode, so this Serialize/Restore handoff (paired with `RestoreSnapshot` and `ProcArrayInstallRestoredXmin`) is how workers acquire a consistent view. [verified-by-code] (`snapmgr.c:1853` — via `knowledge/idioms/snapshot-export-historic-parallel.md`).



### RestrictInfo
The planner's wrapper around a single qualification clause, caching derived facts — referenced relids, selectivity estimates, whether it is a mergejoinable/hashable equality, pushed-down vs join clause — so the optimizer evaluates a clause's properties once and reuses them across candidate paths. [verified-by-code] (via `knowledge/files/src/backend/optimizer/util/restrictinfo.c.md`).



### RestrictSearchPath
The guc.c convenience wrapper that forces `search_path = pg_catalog, pg_temp` for the current GUC nest level, so function/operator name resolution during maintenance is confined to trusted schemas. Introduced for CVE-2023-2454, it pairs with `SwitchToUntrustedUser`; `index_build` wraps user-defined expression/predicate evaluation in it (under `SECURITY_RESTRICTED_OPERATION`) and extensions call it before running SPI/deparse. [verified-by-code] (`guc.c:2153` — via `knowledge/files/src/backend/utils/misc/guc.c.md`).



### ResultRelInfo
The executor's per-target-relation state for INSERT/UPDATE/DELETE/MERGE — the open relation, index lists, trigger info, RETURNING projection, and ON CONFLICT helpers; partitioned targets build one per touched leaf via `ExecInitPartitionInfo`. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### RESUME_INTERRUPTS
The macro paired with `HOLD_INTERRUPTS()` that decrements `InterruptHoldoffCount`; when all three hold counts reach zero (`INTERRUPTS_CAN_BE_PROCESSED()`), pending interrupts may again be serviced. It re-enables interrupt processing previously suspended by a matching `HOLD_INTERRUPTS()`. [verified-by-code] (`miscadmin.h` — via `knowledge/files/src/include/miscadmin.h.md`).



### retain_dead_tuples
A subscription option that makes the logical-replication apply worker retain dead tuples (advertising a conflict-detection horizon) so update/delete conflicts can be detected; pg_upgrade preserves `sub_retain_dead_tuples` across upgrades. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/worker.c.md`).



### RetrieveInstrumentation
The parallel-executor callback phase (`ExecXxxRetrieveInstrumentation`) that copies each parallel worker's accumulated instrumentation counters out of DSM back into the leader's `PlanState` at the end of a parallel scan, so `EXPLAIN ANALYZE` can report combined per-node statistics. [verified-by-code] (via `knowledge/files/src/include/executor/nodeSort.h.md`).



### RETURNING
The clause on `INSERT`/`UPDATE`/`DELETE`/`MERGE` that makes the statement return rows computed from the affected tuples (with `OLD`/`NEW` aliases in newer versions). The executor's ModifyTable node projects the `RETURNING` target list per modified row; FDWs must report which columns they can return remotely. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md`).



### ReturnSetInfo
The `fmgr` struct passed to a set-returning function carrying the expected
return mode, the `econtext`, and (in materialize mode) the `Tuplestorestate`
and `TupleDesc` the function fills. [verified-by-code] (via
`knowledge/idioms/fmgr.md`).



### RevalidateCachedQuery
The plan-cache routine invoked by `GetCachedPlan` when a source has been marked
invalid: it re-analyzes and re-rewrites the saved query, and also forces
re-analysis when `active_search_path`, the user, or the RLS environment changed
since the last call. [verified-by-code] (`plancache.c:684` — via
`knowledge/subsystems/utils-cache.md`).



### REVMAP_PAGE_MAXITEMS
The number of `ItemPointerData` slots in a BRIN revmap page's contents area (`RevmapContents.rm_tids[REVMAP_PAGE_MAXITEMS]`), computed from the `PageGetContents` capacity. It bounds how many range-summary tuple pointers one revmap page can hold. [verified-by-code] (`brin_page.h` — via `knowledge/files/src/include/access/brin_page.h.md`).



### revmap_physical_extend
The BRIN routine (`brin_revmap.c`) that grows the reverse map by claiming the next block: it evacuates any regular index tuples off that block and reinitializes it as a revmap page, updating the metapage's `lastRevmapPage`. [verified-by-code] (via `knowledge/idioms/brin-revmap.md`).



### RevmapContents
The on-disk layout of a BRIN revmap page: an array ItemPointerData rm_tids[REVMAP_PAGE_MAXITEMS] mapping heap page ranges to the TIDs of their summary index tuples. [verified-by-code] (via `knowledge/files/contrib/pageinspect/brinfuncs.c.md`).



### rewriteHandler
`src/backend/rewrite/rewriteHandler.c` — the query rewriter (rule system): `QueryRewrite` applies `pg_rewrite` rules, expanding views into their underlying queries, processing `INSTEAD`/`ALSO` rules, and handling `INSERT/UPDATE/DELETE` on updatable views plus row-level-security qualifiers. It runs between parse-analysis and planning in the query pipeline. [verified-by-code] (via `knowledge/files/src/backend/rewrite/rewriteHandler.c.md`).



### RewriteQuery
The rule-rewriter driver that applies INSTEAD/ALSO rules and view expansion to
a parse-analyzed `Query`, potentially producing several result queries from
one input. [verified-by-code] (`rewriteHandler.c:4044` — via
`knowledge/subsystems/parser-and-rewrite.md`).



### ri_fkey_cascade_del
`RI_FKey_cascade_del` (`ri_triggers.c`) is the C trigger function implementing `ON DELETE CASCADE`: it re-enters the executor through a cached per-(fk,pk,action) SPI plan to delete the referencing rows. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/ri_triggers.c.md`).



### ri_triggers
`src/backend/utils/adt/ri_triggers.c` — the C implementation of referential-integrity enforcement: the built-in trigger functions (`RI_FKey_check_ins`, `...cascade_del`, `...restrict_upd`, etc.) that a `FOREIGN KEY` constraint fires, run as parameterized SPI queries against the referenced/referencing tables, with a per-session query-plan cache. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/ri_triggers.c.md`).



### RLS
Row-Level Security — per-row visibility and modifiability policies attached to a table (`CREATE POLICY`). `rowsecurity.c` injects the applicable policy quals into the query's `securityQuals` during rewrite, so the planner treats them as leak-proof filters enforced before user-supplied predicates. [verified-by-code] (via `knowledge/files/src/backend/rewrite/rowsecurity.c.md`).



### rm_decode
A resource manager's WAL-decode callback slot in its `RmgrData` entry; logical decoding invokes it to turn that rmgr's WAL records into logical change events. [from-comment] (via `knowledge/idioms/wal-page-write-flush.md` and `knowledge/subsystems/access-transam.md`).



### RM_HEAP2_ID
The resource-manager id for the heap's second WAL rmgr, carrying the heap operations that did not fit in `RM_HEAP_ID`'s 8-opcode budget — multi-insert, freeze, visibility-map, and prune/vacuum records. [verified-by-code] (`heapdesc.c:264` — via `knowledge/files/src/backend/access/rmgrdesc/heapdesc.c.md`).



### rm_identify
A resource manager's callback returning a short human-readable name for a WAL record's info bits, used by `pg_waldump` alongside `rm_desc`. [from-docs] (via `knowledge/docs-distilled/custom-rmgr.md`).



### rm_redo
The redo callback in a resource manager's `RmgrData` entry; WAL recovery dispatches each record to the `rm_redo` of the rmgr id in its header to reapply the change. Adding a WAL record type means implementing the matching case in that rmgr's redo. [inferred] (`xlogrecovery.c:1883` — via `knowledge/subsystems/access-transam.md`).



### rmgr (resource manager)
A WAL resource manager: each subsystem that emits WAL (heap, btree, transaction
commit, …) registers a record-type id and callbacks (notably `rm_redo`) in the
global `RmgrTable[RM_MAX_ID + 1]`. Recovery dispatches each WAL record to its
rmgr's redo function to replay the change. [verified-by-code] (`rmgr.c`
`RmgrTable` — via `knowledge/files/src/backend/access/transam/rmgr.c.md`).



### RmgrData
The eight-callback table a resource manager registers (via `RegisterCustomRmgr` for custom rmgrs) so that WAL replay, identification, and `pg_waldump` description dispatch on its `RmgrId`. [from-docs] (via `knowledge/docs-distilled/wal-for-extensions.md`).



### RmgrId
The `uint8` resource-manager identifier (built from `rmgrlist.h`) tagging every WAL record so redo, description, and identification dispatch to the right rmgr; helper macros distinguish builtin from custom ids. [verified-by-code] (via `knowledge/files/src/include/access/rmgr.h.md`).



### RmgrTable
The static dispatch table mapping each resource-manager id (RM_HEAP_ID, RM_XLOG_ID, …) to its rmgr callbacks (redo, desc, identify, startup, cleanup); WAL replay indexes it by a record's rmid to find the redo routine. [verified-by-code] (`rmgr.c:50` — via `knowledge/subsystems/access-transam.md`).



### rolbypassrls
The `pg_authid` boolean column backing the BYPASSRLS attribute — exemption from row-level-security policies, grantable without full superuser and explicitly not grantable by CREATEROLE. [verified-by-code] (`pg_authid.h:37-43` — via `knowledge/docs-distilled/role-attributes.md`).



### rolcanlogin
The `pg_authid` boolean backing the LOGIN attribute — the only distinction between a "user" and a "group", since both are the same `pg_authid` row. [verified-by-code] (`pg_authid.h:37-43` — via `knowledge/docs-distilled/role-attributes.md`).



### rolcreatedb
The `pg_authid` boolean backing the CREATEDB attribute. [verified-by-code] (`pg_authid.h:37-43` — via `knowledge/docs-distilled/role-attributes.md`).



### rolcreaterole
The `pg_authid` boolean backing the CREATEROLE attribute; a CREATEROLE role auto-grants itself ADMIN on roles it creates but cannot create superusers or grant REPLICATION/BYPASSRLS. [verified-by-code] (`pg_authid.h:37-43` — via `knowledge/docs-distilled/role-attributes.md`).



### RollbackAndReleaseCurrentSubTransaction
Aborts the current subtransaction and pops it, the C-level primitive behind PL
exception blocks and `plpy.subtransaction()`/SPI subxact rollback.
[verified-by-code] (`plpy_spi.c:447-539` — via
`knowledge/files/src/pl/plpython/plpy_spi.md`).



### rolreplication
The `pg_authid` boolean backing the REPLICATION attribute — lets the role open a walsender replication connection; requires LOGIN. [verified-by-code] (`pg_authid.h:37-43` — via `knowledge/docs-distilled/role-attributes.md`).



### rolsuper
The `pg_authid` boolean backing the SUPERUSER attribute, commented "read this field via superuser() only!"; it bypasses every permission check except LOGIN. [verified-by-code] (`pg_authid.h:37-43` — via `knowledge/docs-distilled/role-attributes.md`).



### ROW_MARK_REFERENCE
An ExecRowMark markType for a row that is merely referenced (not locked) and must be re-fetched by TID during EvalPlanQual, including the FDW RefetchForeignRow path. [verified-by-code] (via `knowledge/idioms/epq-multi-table.md`).



### row_security
GUC (`on`/`off`/`force`) controlling whether row-level security policies are applied; `off` errors rather than silently bypassing policies for non-owners. rls.h notes the result must be three-state to stay correct under `row_security=off`. [verified-by-code] (via `knowledge/files/src/include/utils/rls.h.md`).



### RowDescription
The protocol message (tag 'T') that precedes result rows, describing each result column's name, table/column OID, type OID, typmod, and format code; printtup builds it from the query's TupleDesc. [verified-by-code] (via `knowledge/files/src/backend/access/common/printtup.c.md`).



### RowExclusiveLock
The table lock level taken by ordinary INSERT/UPDATE/DELETE (and by catalog
DML such as `performDeletion` opening `pg_depend`); it conflicts with schema
changes but not with other writers. [verified-by-code] (via
`knowledge/files/src/backend/catalog/dependency.c.md`).



### RowShareLock
The heavyweight table-level lock mode taken by `SELECT ... FOR UPDATE/SHARE`; it
conflicts only with `EXCLUSIVE`/`ACCESS EXCLUSIVE`, so row-locking readers don't
block ordinary writers. [verified-by-code] (via
`knowledge/idioms/ri-fkey-check.md`).



### RS_EPHEMERAL
One of the replication-slot persistency modes: an ephemeral slot is dropped automatically if the creating session errors or disconnects before it is persisted, used as the transient state while a slot is being initialized (vs `RS_PERSISTENT`). [verified-by-code] (via `knowledge/files/src/include/replication/slot.h.md`).



### rtable
A `Query`'s range table: the ordered list of `RangeTblEntry` nodes naming every relation, subquery, function, CTE, or join the query references, indexed by `varno`/rangetable index. Only the `rt_fetch` helpers in `parsetree.h` are permitted to index into it positionally. [verified-by-code] (via `knowledge/subsystems/parser-and-rewrite.md`).



### RTE_RELATION
The range-table-entry kind denoting a plain base relation (table, matview,
etc.), as opposed to subquery/join/function RTEs; the planner routes it to
`set_plain_rel_pathlist` to build scan paths. [verified-by-code]
(`allpaths.c:834` — via `knowledge/subsystems/optimizer.md`).



### RTE_RESULT
A range-table-entry kind representing a degenerate single-row source, substituted for a FROM-less `SELECT` (or `INSERT … VALUES()`) when preprocessing produces an empty jointree (`replace_empty_jointree`). It executes as a `T_Result` plan node (`create_resultscan_plan` / `cost_resultscan`), and leftover RTE_RESULT entries are removed by `remove_useless_result_rtes`; `planmain.c` short-circuits a jointree that is exactly one RTE_RESULT into a `GroupResultPath`. [verified-by-code] (`parser-and-rewrite.md` — via `knowledge/subsystems/parser-and-rewrite.md`).



### RTE_SUBQUERY
The range-table-entry kind for a sub-SELECT appearing in a query's FROM clause;
its `subquery` field holds the nested `Query`. It is one of the RTEKind values
(`RTE_RELATION`, `RTE_SUBQUERY`, `RTE_FUNCTION`, `RTE_VALUES`, …) that classify
every entry in a query's range table. [verified-by-code] (via
`knowledge/files/src/backend/parser/parse_relation.c.md`).



### ru_inblock
The `getrusage(2)` `struct rusage` field counting filesystem block *input* operations (physical reads). pg_stat_kcache brackets each executor run with `getrusage(RUSAGE_SELF, …)` and attributes the delta to the statement, scaling by `RUSAGE_BLOCK_SIZE` to report bytes read from storage. [verified-by-code] (via `knowledge/ideologies/pg_stat_kcache.md`).



### ru_oublock
The `getrusage(2)` `struct rusage` field counting filesystem block *output* operations (physical writes). pg_stat_kcache reports the per-statement delta scaled by `RUSAGE_BLOCK_SIZE` as bytes written to storage. [verified-by-code] (via `knowledge/ideologies/pg_stat_kcache.md`).



### RUSAGE_BLOCK_SIZE
The constant pg_stat_kcache multiplies the kernel's block-count `getrusage` fields (`ru_inblock` / `ru_oublock`) by, to report physical read/write volume in bytes rather than in kernel filesystem blocks. [verified-by-code `pg_stat_kcache.c:1340-1341`] (via `knowledge/ideologies/pg_stat_kcache.md`).



### s_lock
The spinlock *slow path* in `storage/lmgr/s_lock.c` — `SpinLockAcquire` first tries an inline test-and-set (the `s_lock.h` hardware-TAS macros); only on contention does it fall back to `s_lock()`, which spins with exponential backoff and eventually `PANIC`s on a stuck-spinlock timeout. Spinlocks guard only a handful of instructions and must never block or `ereport`. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/s_lock.c.md`).



### SaltedPassword
In SCRAM, `PBKDF2-HMAC-SHA-256(password, salt, iterations)` — the iterated
hash from which the client/server keys derive. libpq computes it once during
authentication and keeps it in the SCRAM state for reuse when verifying the
server signature. [verified-by-code] (`fe-auth-scram.c:792-797` — via
`knowledge/files/src/interfaces/libpq/fe-auth-scram.c.md`).



### SAOP
ScalarArrayOpExpr — a “scalar array operation” expression of the form `expr op ANY (array)` / `op ALL (array)` (e.g. `x = ANY('{1,2,3}')`). Since PG17 nbtree executes a SAOP natively inside a single index scan via array-key preprocessing (`_bt_preprocess_array_keys`), advancing through the array elements in index order rather than relying on a BitmapOr of separate scans. [verified-by-code] (via `knowledge/files/src/backend/access/nbtree/nbtpreprocesskeys.c.md`).



### SASL
Simple Authentication and Security Layer — the RFC 4422 challenge/response framework PostgreSQL's wire protocol uses to carry SCRAM exchanges; the backend drives the mechanism through a pg_be_sasl_mech vtable. [verified-by-code] (`auth-sasl.c:50` — via `knowledge/files/src/backend/libpq/auth-sasl.c.md`).



### saslprep
The SASLprep (RFC 4013 / stringprep) normalization applied to UTF-8 passwords
before SCRAM hashing, so visually-equivalent Unicode inputs hash identically.
The backend applies it when storing a SCRAM verifier; mismatched client/server
normalization would otherwise break authentication. [verified-by-code] (via
`knowledge/files/src/include/common/saslprep.h.md`).



### SaveCachedPlan
Hands a freshly built generic `CachedPlan` to the plancache for caching under its `CachedPlanSource`, moving it into the cache's own memory context. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/plancache.c.md`).



### ScalarArrayOpExpr
The expression node for `scalar op ANY/ALL (array)` (the parsed form of
`IN (...)` and `= ANY (array)`): it holds the per-element operator, a
`useOr` flag distinguishing ANY from ALL, and the left/right argument
expressions. The planner can turn it into an index scan or a hashed lookup;
fmgr special-cases its arg at `fmgr.c:1925-1931`. [verified-by-code] (via
`knowledge/files/src/backend/utils/fmgr/fmgr.c.md`).



### ScanKey
One element of the comparison-predicate array an index scan is opened with: a
(attribute, strategy/operator, comparison value) triple, optionally flagged for
NULL handling or `ScalarArrayOp`. AMs preprocess the `ScanKey[]` to drop
redundant or contradictory clauses before scanning. [from-comment] (via
`knowledge/files/src/backend/access/nbtree/nbtpreprocesskeys.c.md`).



### ScanKeyData
The struct describing one index/heap scan qualification — a
(strategy number, comparison function, attribute number, argument) tuple plus
flag bits (e.g. `SK_ISNULL`, `SK_SEARCHNULL`). `ScanKeyInit` fills one in, and
AMs evaluate an array of them to decide which tuples match.
[verified-by-code] (via `knowledge/files/src/include/access/skey.h.md`).



### ScanKeyInit
Initialises a `ScanKeyData` in place from an attribute number, a strategy
number, a comparison `RegProcedure`, and an argument `Datum` — the standard way
to build the qual array handed to an index or heap scan. Because the function is
looked up by OID, callers must pass a trusted comparison proc.
[verified-by-code] (via `knowledge/files/src/include/access/valid.h.md`).



### ScanKeywordList
The generated lookup table (`gen_keywordlist.pl` emits `*_d.h`) consumed by `ScanKeywordLookup`: a sorted offset array plus a packed value blob plus per-keyword token/category data. [from-comment] (via `knowledge/files/src/pl/plpgsql/src/pl_kwlists.md`).



### ScanKeywordLookup
The binary-search routine that maps an identifier to a keyword token using a generated `ScanKeywordList` (an offset table plus a packed value blob); it is shared by the backend lexer and PL/pgSQL. [from-comment] (via `knowledge/subsystems/parser-and-rewrite.md`).



### ScanKeywords
The master SQL keyword table — a `ScanKeywordList` (string pool + offsets + perfect-hash function) generated into `kwlist_d.h` from `parser/kwlist.h` and defined in `src/common/keywords.c`, with parallel `ScanKeywordCategories[]` and `ScanKeywordBareLabel[]` arrays. `ScanKeywordLookup` probes it to classify identifier-shaped tokens; the lexer, ECPG's keyword lookup, frontend identifier-quoting, and `pg_get_keywords()` all consume it. [verified-by-code] (`keywords.c:7` — via `knowledge/files/src/common/keywords.c.md`).



### SCRAM
Salted Challenge Response Authentication Mechanism (SCRAM-SHA-256, RFC 7677) — PostgreSQL's default password authentication; the server stores a salted, iterated verifier and proves knowledge without the cleartext password crossing the wire, run inside the SASL exchange. [verified-by-code] (`auth-scram.c:481` — via `knowledge/files/src/backend/libpq/auth-scram.c.md`).



### scram_common
The shared SCRAM-SHA-256 constants and primitives (salted-password derivation,
client/server keys, channel-binding tags) used by both the backend verifier and
the libpq client, keeping the two sides of the challenge-response in agreement.
[verified-by-code] (via
`knowledge/files/src/include/common/scram-common.h.md`).



### SCRAM_MAX_KEY_LEN
A SCRAM size constant defined as `SCRAM_MAX_KEY_LEN = SCRAM_SHA_256_KEY_LEN` (32 bytes), sized for the largest SCRAM hash currently wired (only SHA-256 today). It is the dimension for fixed `uint8[SCRAM_MAX_KEY_LEN]` stack buffers throughout the SCRAM implementation (e.g. `Ui`/`Ui_prev` in `scram-common.c`, `scram_ClientKey`/`scram_ServerKey` in the server state, `SaltedPassword` in libpq); adding SCRAM-SHA-512 would require bumping it and re-sizing those call sites. [verified-by-code] (`scram-common.h` — via `knowledge/files/src/include/common/scram-common.h.md`).



### search_path
The session GUC listing the schemas, in order, that unqualified object names resolve against (plus the implicit `pg_catalog` first and an optional temp schema). It is a recurring security concern: SECURITY DEFINER functions and remote FDW sessions pin it (e.g. `SET search_path = pg_catalog`) to prevent object-shadowing attacks. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### SearchCatCacheInternal
The inline fast path of a catalog-cache lookup (catcache.c): it hashes the search keys, probes the matching bucket, and falls through to SearchCatCacheMiss on a miss. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/catcache.c.md`).



### SearchCatCacheList
The catcache entry point that returns a `CatCList` of all catalog tuples matching a partial key (fewer keys than the cache's full key), caching the list so repeated lookups such as "all operators named +" avoid re-scanning the catalog. [verified-by-code] (`catcache.c` — via `knowledge/files/src/backend/utils/cache/catcache.c.md`).



### SearchCatCacheMiss
The catcache slow path taken when a key isn't cached: it scans the underlying
catalog (by index when possible), builds a `CatCTup`, and inserts it before
returning. [verified-by-code] (via
`knowledge/idioms/syscache-catcache-internals.md`).



### SearchSysCache
The primary entry point for a syscache lookup by key, returning a reference-
counted `HeapTuple` (or a cached negative entry meaning "no such row" so the
miss is not re-scanned). Callers must `ReleaseSysCache` the result.
[verified-by-code] (`catcache.c:1621` — via
`knowledge/subsystems/utils-cache.md`).



### SearchSysCache1
Looks up a single-key catalog tuple through the syscache (the cached catalog reader), returning a HeapTuple that must be released with ReleaseSysCache; the numbered variants (…1/…2/…3/…4) take that many key columns. [verified-by-code] (via `knowledge/idioms/catalog-conventions.md`).



### SearchSysCacheExists
The existence-test family of syscache lookups (`SearchSysCacheExists1`…) that
returns a boolean without materializing or pinning the tuple — cheaper than
`SearchSysCache` + `ReleaseSysCache` when only "does a row exist" matters.
[verified-by-code] (`syscache.c:13` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SearchSysCacheExists1
Tests existence of a catalog row by a single key through the syscache without returning the tuple (no `ReleaseSysCache` needed); the cheap "does this OID still exist?" probe, e.g. inside `try_relation_open`. [verified-by-code] (`relation.c:88` — via `knowledge/files/src/backend/access/common/relation.c.md`).



### SearchSysCacheLocked1
A syscache lookup variant that also takes a lock on the found catalog tuple,
used where a caller must read a catalog row safely against concurrent in-place
updates (e.g. of `pg_class` relfrozenxid). [verified-by-code]
(`syscache.c:283` — via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SecondarySnapshot
A non-registered snapshot kept for internal uses (such as some catalog or
RI checks) distinct from the transaction snapshot, refreshed as needed.
[verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### SecretBuf
A proposed corpus-tracked shared primitive: a buffer type for holding secret material (keys/passwords) with guaranteed wipe-on-free, raised as the natural home for duplicated secret-scrubbing logic spread across the backend. [inferred] (via `knowledge/issues/common.md`).



### SectionMemoryManager
The LLVM `RTDyldMemoryManager` subclass PostgreSQL's JIT installs so emitted
code/data sections are allocated from memory it controls and can free when the
`JitContext` is torn down. [verified-by-code] (via
`knowledge/idioms/jit-provider-and-context.md`).



### secure_open_server
The backend dispatcher that, per connection, branches to the TLS (`be_tls_open_server`) or GSSAPI open path after the pre-startup `SSLRequest`/`GSSENCRequest` negotiation. [verified-by-code] (`be-secure.c:116` — via `knowledge/docs-distilled/ssl-tcp.md`).



### security_barrier
A flag on a view (and the RTE it expands to) that forbids the planner from pushing user-supplied qualifiers below the view's own quals, preventing a cheap but leaky function from seeing rows the view was meant to hide. It is the mechanism behind security_barrier views and row-level security. [inferred] (via `knowledge/subsystems/optimizer.md`).



### SECURITY_RESTRICTED_OPERATION
The `SecurityRestrictionContext` flag that forbids changing session state
(SET ROLE, creating temp objects, etc.) while running otherwise-untrusted
code such as index expressions, triggers, and maintenance commands.
[verified-by-code] (via `knowledge/idioms/commit-transaction-sequence.md`).



### selinux_catalog
The sepgsql translation table mapping PostgreSQL object classes and permissions to their SELinux security-class/permission bit positions; because the encoding is bit-position dependent, its ordering is contractual. [from-comment] (via `knowledge/files/contrib/sepgsql/sepgsql.h.md`).



### SendProcSignal
Sets a reason flag in a target backend's ProcSignal slot and sends it SIGUSR1 — the mechanism for inter-backend requests like recovery-conflict, barrier, and catchup signals; the recipient services it at the next CHECK_FOR_INTERRUPTS. [verified-by-code] (via `knowledge/subsystems/storage-ipc.md`).



### SendQuery
The central psql routine that submits a user-typed query, manages the (auto)commit/transaction state, applies `\timing`, handles `FETCH_COUNT` cursor chunking, and prints results or errors. It is the heart of the psql main loop. [inferred] (via `knowledge/files/src/bin/psql/common.c.md`).



### SendSharedInvalidMessages
Broadcasts a batch of accumulated invalidation messages into the shared sinval
queue so other backends will flush the affected cache entries; commit records
the messages before this broadcast (commit-before-broadcast ordering).
[verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### sepgsql_compute_create
The sepgsql routine that asks the SELinux security server for the label a newly created object should receive; for schema creation the label parent is the current database's security label. [from-comment] (via `knowledge/files/contrib/sepgsql/schema.c.md`).



### seq_page_cost
The planner GUC (default 1.0) that is the unit cost of a sequential 8 KB page read; every other cost constant such as `random_page_cost` and `cpu_tuple_cost` is calibrated relative to it. It anchors the whole abstract cost scale. [inferred] (via `knowledge/idioms/cost-units-gucs.md`).



### SeqScan
The sequential-scan plan/executor node that reads every live tuple of a relation block by block through the table AM, applying the scan qual; the baseline access path the planner costs all others against. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### SerializablePredicateListLock
The lightweight lock guarding an SSI predicate-lock target list while a serializable transaction acquires or upgrades a SIREAD lock, part of the fine-grained locking that keeps predicate-lock bookkeeping scalable. [verified-by-code] (`predicate.c` — via `knowledge/files/src/backend/storage/lmgr/predicate.c.md`).



### serializablexact
`SERIALIZABLEXACT` is the per-serializable-transaction SSI record holding its SIREAD predicate locks and `RWConflictData` edges; commit-time analysis aborts one transaction in a dangerous `Tin → Tpivot → Tout` structure. [from-comment] (via `knowledge/subsystems/storage-lmgr.md`).



### serialized_snapshot
In logical-decoding snapshot building, a snapshot persisted to disk so a restarting decoder or a new slot can reuse it; `last_serialized_snapshot` (an `XLogRecPtr`) debounces redundant re-serialization of the same builder state. [from-comment] (via `knowledge/files/src/include/replication/snapbuild_internal.h.md`).



### SerializedSnapshotData
The flat, pointer-free layout a snapshot is marshalled into for transport
through shared memory to parallel workers (or to an exported-snapshot file).
[verified-by-code] (via
`knowledge/idioms/snapshot-export-historic-parallel.md`).



### SerializeSnapshot
Flattens a Snapshot into a byte buffer (SerializedSnapshotData) for transfer to parallel workers; it is paired with RestoreSnapshot on the worker side. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### ServerKey
In SCRAM, `HMAC(SaltedPassword, "Server Key")`; the server signs the auth
message with it so the client can authenticate the server in turn (mutual auth).
It is stored (alongside `StoredKey`) in the SCRAM verifier in `pg_authid`.
[verified-by-code] (`auth-scram.c:1189` — via
`knowledge/files/src/backend/libpq/auth-scram.c.md`).



### ServerLoop
The postmaster's accept loop after startup: it selects on the listen sockets, accepts each client connection, and forks a backend to handle it, while also reaping dead children and launching background processes. [verified-by-code] (`postmaster.c:1678` — via `knowledge/files/src/backend/postmaster/postmaster.c.md`).



### set_base_rel_sizes
The planner pass (`allpaths.c`) that estimates each base relation's row count and width (applying restriction selectivities and partition pruning) before `set_base_rel_pathlists` generates its access paths. [verified-by-code] (via `knowledge/files/src/backend/optimizer/path/allpaths.c.md`).



### set_baserel_size_estimates
The optimizer routine (costsize.c) that fills a base relation's row-count and width estimates from statistics and restriction-clause selectivity, run per base rel during `set_rel_size` in the size-estimation pass. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### set_cheapest
The optimizer step that, after all paths for a `RelOptInfo` have been added, selects the cheapest-total and cheapest-startup paths (and cheapest parameterized variants) into the rel's `cheapest_*` fields for the join search to build on. [inferred] (via `knowledge/files/src/backend/optimizer/util/pathnode.c.md`).



### set_config
The SQL-callable function form of SET — `set_config(name, value, is_local)` — used, for example, by walreceiver and postgres_fdw to force a secure `search_path` onto a connection at setup time. [verified-by-code] (via `knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md`).



### set_join_pathlist_hook
The planner hook an extension sets to inject custom join paths — the join-level counterpart to `set_rel_pathlist_hook` for base relations. [from-docs] (via `knowledge/docs-distilled/custom-scan.md`).



### set_option
The per-membership boolean in `pg_auth_members` (default true) controlling whether the member may `SET ROLE` to the granted role — the SET axis, evaluated by `is_member_of_role`. [verified-by-code] (`pg_auth_members.h:53` — via `knowledge/docs-distilled/role-membership.md`).



### set_plan_references
The final planner pass (setrefs.c), run after `create_plan`, that fixes up a finished plan tree: it flattens range-table references, resolves Var attnos to child output positions, and records dependencies for plan-cache invalidation. [verified-by-code] (`setrefs.c:290` — via `knowledge/subsystems/optimizer.md`).



### set_rel_pathlist
The Stage-1 planner routine (`allpaths.c`) that, for each base rel, generates its candidate scan Paths — sequential, index, bitmap, TID — and their parallel partial variants, filling `pathlist`/`partial_pathlist`. [verified-by-code] (via `knowledge/architecture/planner.md`).



### set_rel_pathlist_hook
The planner hook invoked after the core code has generated the candidate access paths for a base relation, letting an extension add or remove `Path`s for that rel; FDW-like and acceleration extensions chain it (alongside `planner_hook`) to inject custom scan paths. [inferred] (via `knowledge/ideologies/pg_lake.md`).



### set_rel_size
The planner pass that estimates each base relation's output row count and width before path generation, dispatching by RTE kind (plain table, subquery, CTE, function); its estimates feed the cost model that `set_rel_pathlist` then uses. [verified-by-code] (via `knowledge/architecture/planner.md`).



### set_sentinel
A memory-debug macro (in `utils/memdebug.h`) that writes the sentinel byte `0x7E` just past an allocation so `sentinel_ok` can detect a one-byte overrun under memory-debug builds. [from-comment] (via `knowledge/subsystems/utils-mmgr.md`).



### set_transmission_modes
postgres_fdw's helper that, before deparsing a `Const` or direct-modify SET clause, pushes a GUC nest level forcing `datestyle=ISO`, `intervalstyle=postgres`, `extra_float_digits=3`, and `search_path=pg_catalog`, so output functions emit a remote-parsable, locale-independent text form; `reset_transmission_modes` unwinds it. [verified-by-code] (`postgres_fdw.c:4108` — via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### SET_VARSIZE
The macro that writes the total length (4-byte header plus data) into a
varlena's header — the standard final step when constructing a varlena datum
in the long (uncompressed) form. [verified-by-code] (via
`knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### SetCancelConn
The frontend cancel-handling routine that designates which libpq connection a Ctrl-C/SIGINT should send a cancel request to: it replaces the module-global `cancelConn` with a fresh `PQgetCancel(conn)` and frees the old one (nulling the pointer first so the signal handler never sees a mid-free object). Tools bracket each blocking query with `SetCancelConn(conn)` … `ResetCancelConn()`; `SetCancelConn(NULL)` disables cancellation for operations not issued via the normal query path. [verified-by-code] (`cancel.c:76` — via `knowledge/files/src/fe_utils/cancel.c.md`).



### SetConstraintState
The mutable per-transaction record of deferred-constraint trigger settings
(from `SET CONSTRAINTS`), carried alongside the after-trigger event list; it
must be preserved and `query_depth` reset correctly when a subtransaction
aborts mid-statement. [verified-by-code] (via
`knowledge/idioms/trigger-during-error.md`).



### SetHintBits
The hint-bit setter in `heapam_visibility.c`, called by the `HeapTupleSatisfies*`
routines once a referenced xact's commit/abort is known; it sets the
`HEAP_XMIN/XMAX_COMMITTED/INVALID` bit and dirties the page via
`MarkBufferDirtyHint` (not WAL-logged). [verified-by-code] (via
`knowledge/idioms/hint-bits-setbufferdirty.md`).



### SetHintBitsExt
The extended hint-bit setter in `heapam_visibility.c` (called by the
`HeapTupleSatisfies*` routines once a referenced xact's fate is known) that
marks the tuple and dirties the page via `MarkBufferDirtyHint` — a non-WAL-logged
dirty-hint. [verified-by-code] (via `knowledge/wiki-distilled/Hint_Bits.md`).



### SetHintBitsState
The state threaded through HeapTuple visibility checking that decides whether an xmin/xmax commit/abort hint bit may be set now, deferring the mark until the commit record is known flushed so a torn hint bit can't outrun its WAL. [verified-by-code] (`heapam_visibility.c` — via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### SetLatch
Sets a process's latch, waking it from a `WaitLatch` sleep; it is the
edge-triggered "you have work / wake up" signal between backends and is
async-signal-safe, so signal handlers (e.g. the postmaster's
`handle_pm_*_signal`) set a flag and call `SetLatch` to break the main loop out
of its wait. [verified-by-code] (via
`knowledge/files/src/backend/postmaster/postmaster.c.md`).



### SetOp
The executor plan node implementing `INTERSECT`, `INTERSECT ALL`, `EXCEPT`, and `EXCEPT ALL` via one of two strategies: sorted (reads a sorted child) or hashed (builds a hash table over one side). `UNION` itself does not flow through `SetOp` — it uses `Append` + `Unique` instead. [verified-by-code] (`nodeSetOp.md` — via `knowledge/files/src/include/executor/nodeSetOp.md`).



### SetSecurityLabel
The internal routine that binds a security label string to an object under a
given provider (the catalog-write half of the `SECURITY LABEL` machinery).
sepgsql computes the SELinux context for a new object and then calls
`SetSecurityLabel` to record it. [verified-by-code] (via
`knowledge/files/contrib/sepgsql/database.c.md`).



### settransactionidlimit
`SetTransactionIdLimit` recomputes the wraparound safety thresholds (the warn-limit / stop-limit and the ~3M / ~11M margins) from the oldest `datfrozenxid` after each database-wide VACUUM. [verified-by-code] (via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### SetTransactionSnapshot
The static snapmgr installer used by both ImportSnapshot and RestoreTransactionSnapshot: it calls GetSnapshotData, overwrites xmin/xmax/xip/subxip from the source snapshot, then re-installs xmin atomically without letting the global xmin go backwards. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### SetupHistoricSnapshot
Installs a historic snapshot plus the tuplecid HTAB for logical decoding, so catalog visibility (HeapTupleSatisfiesHistoricMVCC) follows the reorder buffer's cmin/cmax resolution. [verified-by-code] (via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### SetUserIdAndSecContext
Sets the current user id and a security-context bitmask together, the atomic way
to enter/leave a `SECURITY_RESTRICTED_OPERATION` or local-userid-change region
(also restored in parallel workers). [verified-by-code] (via
`knowledge/idioms/parallel-state-propagation.md`).



### SFRM_Materialize
One of the two set-returning-function return modes (the other being value-per-call / `SRF_FIRSTCALL`): the function builds the *entire* result set into a `Tuplestore` up front and hands it back via the `ReturnSetInfo`, rather than emitting one row per call. Chosen by modern SRFs (often through the `SetSingleFuncCall` helper); many observability extensions use it while lighter ones keep the classic value-per-call idiom. [from-code] (via `knowledge/files/contrib/tablefunc/tablefunc.md`).



### shadow_pass
The stored authentication verifier for a role (the contents of
`pg_authid.rolpassword`) — either an `md5…` hash or a `SCRAM-SHA-256$…`
verifier — checked against the client's response during password
authentication. Never the cleartext password. [verified-by-code] (via
`knowledge/files/src/backend/libpq/crypt.c.md`).



### shared_buffers
GUC sizing the main shared buffer pool (`NBuffers` 8 KB pages, default 128 MB); SLRU buffer counts auto-size from it when left at 0, and pg_prewarm repopulates it after a restart. [verified-by-code] (via `knowledge/files/src/backend/utils/init/globals.c.md`).



### shared_preload_libraries
The GUC naming shared libraries the postmaster loads at startup, before any backend forks, so an extension can run `_PG_init`, reserve shared memory, register background workers, and install process-wide hooks. It is `PGC_POSTMASTER` (change requires restart); modules needing shared state or LSM-style hooks must use it rather than per-session `LOAD`. [from-comment] (via `knowledge/files/contrib/sepgsql/label.c.md`).



### SharedBufHash
The partitioned shared hash table mapping a `BufferTag` (relation+fork+block) to a buffer id; lookups/inserts/deletes go through `buf_table.c` under the matching `BufMappingPartitionLock`, which the caller must already hold. [verified-by-code] (via `knowledge/subsystems/storage-buffer.md`).



### SharedFileSet
A `FileSet` extended with DSM-backed reference counting so parallel-query workers can share a set of temporary files; the last process to detach from the DSM segment cleans them up. [verified-by-code] (via `knowledge/files/src/backend/storage/file/sharedfileset.c.md`).



### SharedInvalidationMessage
The union representing one catalog-cache invalidation event (catcache, relcache,
smgr, snapshot, etc.) that is queued locally and broadcast through the sinval
ring to other backends at commit. [verified-by-code] (via
`knowledge/idioms/syscache-invalidation-flow.md`).



### SharedRecordTypmodRegistry
The opaque shared structure (declared in `typcache.h`) that lets parallel
workers agree on blessed record typmods, so an anonymous `RECORD` type assigned a
typmod in the leader resolves to the same tuple descriptor in a worker. It is
attached to the parallel DSM and backed by `dshash`. [verified-by-code] (via
`knowledge/files/src/include/utils/typcache.h.md`).



### SharedTuplestore
A cross-worker, on-disk spill backing store (the `sts_` API) used by parallel hash join to hold per-batch inner and outer tuples. Its control struct lives in shared memory (`SharedTuplestore { nparticipants; flags; meta_data_size; name[NAMEDATALEN]; participants[FLEX] }`) with a per-participant `SharedTuplestoreParticipant { LWLock lock; BlockNumber read_page; ... }` whose lock serialises read-cursor advancement; data is written in 32 KiB chunks (`STS_CHUNK_PAGES = 4`) to a shared `BufFile`, with each backend holding a local `SharedTuplestoreAccessor`. [verified-by-code] (`sharedtuplestore.c.md` — via `knowledge/files/src/backend/utils/sort/sharedtuplestore.c.md`).



### ShareLock
The table-level lock mode (and the heavyweight conflict class) that permits
concurrent readers but blocks writers; `CREATE INDEX` (non-concurrent) holds it
so the table can be read but not modified during the build. Verification tools
note when an operation needs only `ShareLock` versus a stronger mode.
[verified-by-code] (via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### ShareUpdateExclusiveLock
The self-conflicting table lock level held by VACUUM, ANALYZE, CREATE INDEX
CONCURRENTLY and similar maintenance; it permits ordinary reads and writes but
serialises against other maintenance on the same relation. [verified-by-code]
(via `knowledge/files/src/backend/access/brin/brin_revmap.c.md`).



### SHIFT_JIS_2004
A Japanese encoding (`PG_SHIFT_JIS_2004` in `enum pg_enc`) whose conversion procs live in `utf8_and_sjis2004.c` (`shift_jis_2004_to_utf8` / `utf8_to_shift_jis_2004`, conversion OIDs 42 and 63) using the `LUmapSHIFT_JIS_2004_combined` mapping tables; a direct EUC_JIS_2004 ↔ SHIFT_JIS_2004 transcoder (no UTF-8 trip) lives in `utf8_and_euc2004.c`. The conversion proc guards its arguments with `CHECK_ENCODING_CONVERSION_ARGS(PG_SHIFT_JIS_2004, PG_UTF8)`. [verified-by-code] (`utf8_and_sjis2004.c` — via `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_sjis2004/utf8_and_sjis2004.c.md`).



### shm_mq
The single-reader, single-writer shared-memory message queue — a pipe-like construct living in a DSM region, used chiefly to ferry tuples and error messages between a parallel-query leader and its workers. Writers block when full and readers when empty, coordinated through process latches. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).



### shm_mq (shared-memory message queue)
A single-reader/single-writer ring buffer living in a DSM segment, the standard
way a parallel leader and worker stream bytes (tuples, errors, tuple counts) to
each other. `shm_mq_send`/`shm_mq_receive` block on the peer's latch and report
`SHM_MQ_DETACHED` when the other end goes away. [from-comment] (via
`knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).



### shm_mq_receive
Reads the next message from a shared-memory message queue, returning a pointer directly into the ring buffer (zero-copy when the message doesn't wrap). Parallel workers use `shm_mq` pairs to stream tuples and errors back to the leader. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/shm_mq.c.md`).



### shm_toc
The shared-memory table-of-contents: a magic number, spinlock, and key→offset entry array laid over a DSM segment so cooperating processes can publish and find named sub-allocations by integer key — the addressing layer beneath parallel query. [verified-by-code] (`shm_toc.c:29` — via `knowledge/subsystems/storage-ipc.md`).



### shm_toc_lookup
The reader half of the parallel-query DSM "table of contents": given a `shm_toc` and an integer key, it returns the address of a previously inserted segment, with a `noError` flag (`shm_toc_lookup(toc, KEY, noError)`) controlling whether a missing key returns NULL or errors. It is an unsynchronized linear scan — safe without locking because TOC entries grow monotonically and are written under `shm_toc::toc_mutex`, while parallel workers only read after the DSM is fully populated. [verified-by-code] (`storage-ipc.md` — via `knowledge/subsystems/storage-ipc.md`).



### shmem_request_hook
The `_PG_init`-time hook an extension sets so it can call `RequestAddinShmemSpace` and `RequestNamedLWLockTranche` while the postmaster is still sizing shared memory. It only fires for libraries loaded via `shared_preload_libraries`. [inferred] (`lwlock.c:625` — via `knowledge/scenarios/add-new-lwlock-tranche.md`).



### shmem_startup_hook
The hook an extension sets to carve out and initialize its slice of shared memory once the segment exists, typically calling `ShmemInitStruct` under the `AddinShmemInitLock`. It runs in every backend (and the postmaster) after attach, complementing `shmem_request_hook`. [inferred] (`lwlock.c:519` — via `knowledge/scenarios/add-new-lwlock-tranche.md`).



### ShmemCallbacks
Hooks (e.g. `shmem_request_hook` / `shmem_startup_hook`) that an extension sets
from `_PG_init` so it can request additional shared memory and initialize its
structures during postmaster startup. [verified-by-code] (via
`knowledge/architecture/process-model.md`).



### ShmemIndex
The hash table (itself in shared memory) mapping a string name to the address and size of each registered shared-memory structure, so backends can attach to shared areas by name during startup. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/shmem.c.md`).



### ShmemInitHash
The legacy entry point (`shmem_hash.c:116-140`) for creating a hash table in shared memory, wrapping `ShmemInitStruct` plus `shmem_hash_create`; its comment advises new code to use `ShmemRequestHash` instead. Because this path performs the hash init by hand rather than via callbacks, it registers the area as `SHMEM_KIND_STRUCT` (opaque) rather than `_HASH`; it is the call extensions use at `shmem_startup_hook` time to set up shared state. [from-comment] (`shmem_hash.c.md` — via `knowledge/files/src/backend/storage/ipc/shmem_hash.c.md`).



### ShmemInitStruct
Allocates a named fixed-size block in the main shared-memory segment at startup (or, in a child after fork/exec, looks up the already-created block). It is the primitive that most subsystem `*ShmemInit` routines and the extension `GetNamedDSMSegment` helpers build on. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc` shmem docs).



### ShmemRequestStruct
The pattern of reserving a named shared-memory region during the
`shmem_request_hook` phase (via `RequestAddinShmemSpace`) so its size is counted
before the segment is created. [inferred] (via
`knowledge/subsystems/storage-ipc.md`).



### shutdown_cb
The archive-module shutdown callback (`ArchiveModuleCallbacks.shutdown_cb`) invoked when the archiver process exits, giving a WAL-archiving module a chance to release resources; a module that holds no persistent state (like `basic_archive`) may leave it `NULL`. [verified-by-code] (via `knowledge/files/contrib/basic_archive/basic_archive.c.md`).



### SICleanupQueue
The shared-invalidation maintenance routine that reclaims space in the SI message ring once all backends have consumed enough messages, signalling laggards to catch up or reset. [verified-by-code] (`sinvaladt.c:578` — via `knowledge/files/src/backend/storage/ipc/sinvaladt.c.md`).



### sig_atomic_t
The C type guaranteed to be read/written atomically with respect to asynchronous signals; PostgreSQL uses `volatile sig_atomic_t` for flags a signal handler sets and the main loop polls — e.g. `got_deadlock_timeout` set by `CheckDeadLockAlert` from the timer handler and inspected by `ProcSleep`, or a latch's `is_set`. [verified-by-code] (`proc.c:93` — via `knowledge/data-structures/pgproc-fields.md`).



### SIGHUP
The signal the postmaster (and, propagated, each backend) treats as "reload configuration": it re-reads `postgresql.conf`/`pg_hba.conf` and applies any changed `PGC_SIGHUP`-class GUCs without a restart. Backends already running pick up the change at the next `CHECK_FOR_INTERRUPTS`/config-reload point, so in-flight queries may not see it immediately. [from-comment] (via `knowledge/files/contrib/sepgsql/uavc.c.md`).



### SIGINT
The signal PostgreSQL backends handle as a query-cancel request (and the postmaster as fast shutdown). A backend's SIGINT handler sets a flag that the next `CHECK_FOR_INTERRUPTS` observes, raising a `QUERY CANCELED` error at a safe point rather than interrupting mid-operation. [verified-by-code] (via `knowledge/files/src/backend/tcop/postgres.c.md`).



### sigint_interrupt_enabled
The psql flag that, with `sigint_interrupt_jmp`, forms psql's only concurrency boundary: every function blocking on user input (`gets_interactive`, `simple_prompt_extended`, `handleCopyIn`) sets it after the caller has `sigsetjmp`'d, so a SIGINT longjmps out of the blocking read rather than merely flagging `cancel_pressed`. [from-comment] (via `knowledge/files/src/bin/psql/common.h.md`).



### SIGTERM
The signal used to request graceful termination — `SIGTERM` to the postmaster means smart shutdown, and to a backend means terminate-this-session. Handlers set a pending flag consumed at the next `CHECK_FOR_INTERRUPTS`/latch wait so shutdown happens at a safe point with cleanup callbacks run. [verified-by-code] (via `knowledge/files/src/backend/postmaster/bgwriter.c.md`).



### SIMD
Single Instruction, Multiple Data — vectorized CPU instructions PostgreSQL uses in hot loops (e.g. byte scanning, JSON/encoding, hashing) via `pg_attribute_*` helpers and architecture-specific intrinsics, with a scalar fallback when the vector path is unavailable. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/encode.c.md`).



### simple_heap_insert
Inserts a single tuple into a heap with a frozen command id and no speculative-insertion machinery; the catalog-write building block beneath `CatalogTupleInsert`. [verified-by-code] (via `knowledge/files/src/backend/catalog/indexing.c.md`).



### simple_prompt
Frontend helper that prints a prompt and reads a line from the terminal with echo optionally disabled (for passwords); used by `psql`, `connect_utils.c`, and other client tools. [verified-by-code] (`connect_utils.c:48-49` — via `knowledge/files/src/fe_utils/connect_utils.c.md`).



### simple_rel_array
The planner's per-query array of `RelOptInfo*` indexed by range-table index (rti), allocated by `setup_simple_rel_arrays` during `query_planner`; its sibling `simple_rte_array` indexes the RangeTblEntries in parallel. [verified-by-code] (`relnode.c:113` — via `knowledge/files/src/backend/optimizer/plan/planmain.c.md`).



### SimpleLruGetBankLock
The SLRU helper that maps a page number to the bank LWLock guarding it; banked
SLRU locking (PG 17+) shards a single control lock into per-bank locks so
unrelated multixact/clog pages can be read concurrently. [verified-by-code]
(via `knowledge/idioms/multixact-slru.md`).



### SimpleLruReadPage
The SLRU read primitive (`slru.c:550`) — finds or evicts a buffer slot, reads the requested page from the segment file if not resident, and returns the slot holding it; used by CLOG, multixact, subtrans, commit-ts, and async. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### SimpleLruReadPage_ReadOnly
The fast-path SLRU page fetch that takes only the shared control lock when the requested page is already resident in a buffer, falling back to the exclusive-lock read path (`SimpleLruReadPage`) on a miss. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### SimpleLruRequest
An SLRU I/O request descriptor (page number plus read/write intent) queued against a `SlruCtl` bank; the SLRU machinery serves it under the bank's control lock, evicting the least-recently-used page when the buffer set is full. [verified-by-code] (via `knowledge/files/src/test/modules/test_slru/test_slru.c.md`).



### SimpleLruTruncate
The slru.c routine that removes obsolete SLRU segment files older than a given `cutoffPage` (the highest page to keep), using `TransactionIdPrecedes`-style 32-bit modular comparison via the SLRU's `PagePrecedes` callback. VACUUM advancing the xmin/oldest horizon drives it on clog, subtrans, and multixact-offsets SLRUs; SLRUs that call it must pass `SlruPagePrecedesUnitTests` (the multixact members SLRU truncates through a custom directory-scan path instead). [verified-by-code] (`slru.c:1458` — via `knowledge/files/src/backend/access/transam/slru.c.md`).



### SimpleLruWritePage
The SLRU write primitive (`slru.c:781`) that flushes one buffer slot's page back to its segment file, used at checkpoint and during buffer eviction in any SLRU pool. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### SimpleLruZeroPage
Zero-initialises a fresh SLRU page in a buffer slot and marks it dirty; called under the SLRU control lock when an SLRU (e.g. pg_subtrans or pg_multixact) is extended to a new page. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### sinvalreadlock
`SInvalReadLock` is the LWLock protecting concurrent readers of the sinval message ring (paired with `SInvalWriteLock` for writers); per-backend `maxMsgNum` bookkeeping uses a per-array spinlock instead. [verified-by-code] (via `knowledge/idioms/sinvaladt-broadcast.md`).



### SInvalWriteLock
The LWLock a backend takes EXCLUSIVE to append a shared-cache-invalidation message to the `sinvaladt` queue, serializing writers; its release publishes the new `maxMsgNum` to readers. [verified-by-code] (via `knowledge/idioms/sinvaladt-broadcast.md`).



### size_t
The C standard unsigned type for object sizes and counts, used throughout the backend for allocation sizes and buffer lengths. PostgreSQL also defines `Size` as an alias; allocation request sizes are bounded by `MaxAllocSize` (1 GB minus header) unless the `_huge` allocators are used. [verified-by-code] (via `knowledge/files/src/include/utils/memutils.h.md`).



### sizebitvec
intarray's GiST signature helper returning the number of set bits in a signature vector (via `pg_popcount`); distance/penalty math like `hemdist` uses it, e.g. `SIGLENBIT(siglen) - sizebitvec(other)` counts the other signature's unset bits. [verified-by-code] (`_intbig_gist.c:230-244` — via `knowledge/files/contrib/intarray/_intbig_gist.md`).



### SKIP_PAGES_THRESHOLD
The run-length threshold (32) below which lazy vacuum reads a stretch of all-visible pages anyway rather than skipping them via the visibility map, so that I/O stays sequential. [verified-by-code] (via `knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).



### SLAB_BLOCKLIST_COUNT
In the Slab allocator, the number of block free-lists bucketed by how many free chunks each block currently has, which lets the allocator pick a block to allocate from in O(1). [verified-by-code] (via `knowledge/files/src/backend/utils/mmgr/slab.c.md`).



### SlabContext
A `MemoryContext` type specialized for many same-sized chunks (e.g. reorder-buffer
tuples); it allocates fixed-size slots from blocks and reclaims whole blocks,
avoiding `AllocSet` fragmentation for uniform workloads. [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### SlabContextCreate
Constructs a Slab memory context, which allocates many fixed-size chunks from
blocks and can free whole blocks back, avoiding `AllocSet` fragmentation for
uniform-sized objects (e.g. reorder-buffer changes). [verified-by-code] (via
`knowledge/idioms/memory-context-api-and-dispatch.md`).



### slock_t
The platform-specific spinlock type manipulated by `SpinLockInit/Acquire/Release`, used to guard very short critical sections over a handful of shared-memory fields where an LWLock would be too heavy. Spinlocks must never be held across anything that can block or error, since they have no deadlock detection and no interrupt servicing. [verified-by-code] (via `knowledge/files/src/backend/access/brin/brin.c.md`).



### slot_compile_deform
The JIT routine that emits LLVM IR to deform a tuple directly into a `TupleTableSlot`'s value/null arrays, replacing the interpreted `slot_getsomeattrs` fast path for hot plans. [verified-by-code] (`llvmjit_deform.c:34-540` — via `knowledge/files/src/backend/jit/llvm` docs).



### slot_deform_heap_tuple
The generic tuple-deforming routine that walks a `HeapTuple`'s attributes left-to-right, honoring nulls and alignment, to populate a slot's `tts_values`/`tts_isnull` arrays; JIT can replace it with an unrolled, type-specialized deformer. [verified-by-code] (via `knowledge/idioms/jit-tuple-deform-and-inline.md`).



### slot_getsomeattrs
Deconstructs columns 1..`attnum` of a `TupleTableSlot` into its `tts_values` / `tts_isnull` arrays, calling the slot's `getsomeattrs` callback so only the attributes a plan actually references get deformed. Expression evaluation emits it lazily before reading a Var. [verified-by-code] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### SLRU
Simple LRU — the fixed-size, page-buffered cache layer for the dense numbered logs that don't live in the main buffer pool (clog/xact-status, commit_ts, multixact, subtrans, notify), with its own simple replacement and fsync logic. [verified-by-code] (`commit_ts.c:150` — via `knowledge/subsystems/access-transam.md`).



### SLRU (simple LRU)
A small fixed-page cache for dense, sequentially-numbered on-disk state that the
main buffer pool does not manage — commit status (clog), subtransaction
parents, multixact, and similar. Clients drive it through the
`SlruCtl`/`SlruShared` interface declared in `slru.h` and implemented in
`slru.c`. [from-comment] (`slru.h:12` — via
`knowledge/files/src/include/access/slru.h.md`).



### SLRU_PAGES_PER_SEGMENT
The number of SLRU buffer pages (32) packed into one on-disk segment file for logs such as `pg_xact`, `pg_subtrans`, and `pg_multixact`. [verified-by-code] (via `knowledge/files/src/include/pg_config_manual.h.md`).



### SlruSelectLRUPage
The SLRU buffer-replacement routine that picks the least-recently-used page slot to evict when every slot is occupied and a new page must be read in. [verified-by-code] (via `knowledge/files/src/backend/access/transam/slru.c.md`).



### SlruSharedData
The shared-memory control block of an SLRU pool (`slru.h:48-106`) — the buffer page array, per-slot page numbers and status, LRU counters, and the per-bank lock array that lets different page ranges be locked independently. [verified-by-code] (via `knowledge/files/src/include/access/slru.h.md`).



### smgr (storage manager)
The abstraction layer between the buffer manager and physical relation files.
`smgr.c` maintains a hashtable of `SMgrRelation` handles (cached open files) and
forwards reads, writes, extends, and truncates to the underlying `md.c`
magnetic-disk implementation. [from-comment] (`smgr.c:1` — via
`knowledge/files/src/backend/storage/smgr/smgr.c.md`).



### smgrDoPendingDeletes
The load-bearing transaction-cleanup routine that walks the pending-relation-delete list at the current nest level and, for each entry whose `atCommit` matches `isCommit`, unlinks the physical file via `smgrdounlinkall`; it removes a list entry before deleting so a retry cannot double-process. Called from both `CommitTransaction` and `AbortTransaction`. [verified-by-code] (`storage.c:673-735` — via `knowledge/files/src/backend/catalog/storage.c.md`).



### smgrDoPendingSyncs
The commit-time counterpart to `smgrDoPendingDeletes`: for every relfilenode still in `pendingSyncHash` (and not also being deleted) it issues `smgrimmedsync(MAIN_FORKNUM)`, durably flushing relations that skipped WAL under `wal_level=minimal`; aborts and parallel workers discard the hash instead. [verified-by-code] (`storage.c:741` — via `knowledge/files/src/backend/catalog/storage.c.md`).



### smgropen
Returns (creating if needed) the `SMgrRelation` handle for a `RelFileLocator`+backend — the entry point to the storage-manager layer. It is cheap and cache-backed, so callers re-open freely rather than stash the handle. [verified-by-code] (via `knowledge/files/src/backend/catalog/storage.c.md`).



### SMgrRelation
The storage-manager handle for a relation's physical files, obtained from
`smgropen` on a `RelFileLocator`. It is the layer `md.c` implements and through
which buffer reads/writes, extends, and truncates reach the filesystem.
[verified-by-code] (`storage.c:122` — via
`knowledge/files/src/backend/catalog/storage.c.md`).



### smgrwrite
Writes one already-filled buffer block to a relation fork through the storage manager (`md.c`), without WAL or buffer-pool involvement; used by bulk-write paths and during recovery. [verified-by-code] (via `knowledge/files/src/backend/storage/smgr/bulk_write.c.md`).



### SN_env
The Snowball stemmer's per-call environment struct; `dict_snowball` calls the generated `stem(SN_env *)` functions imported from the libstemmer sources to reduce a word to its stem. [verified-by-code] (`dict_snowball.c:16` — via `knowledge/files/src/backend/snowball/dict_snowball.c.md`).



### SnapBuild
The logical-decoding snapshot builder that reconstructs a historic MVCC
snapshot from the WAL stream so that catalog tuples can be interpreted
correctly as of each decoded change. [from-comment] (via
`knowledge/subsystems/contrib-pg_logicalinspect.md`).



### SnapBuildExportSnapshot
The logical-decoding routine that produces an exportable snapshot id at a
consistent point during slot creation, so a client can `SET TRANSACTION
SNAPSHOT` and read a base copy of the data consistent with where streaming will
begin. [verified-by-code] (`snapbuild.c:542` — via
`knowledge/subsystems/replication.md`).



### SnapBuildOnDisk
The on-disk serialized form of a logical-decoding snapshot builder, written to `pg_logical/snapshots/` so a restarting or newly-connecting logical slot can resume building a consistent historic snapshot without replaying all WAL from the slot's start. [verified-by-code] (via `knowledge/files/contrib/pg_logicalinspect/pg_logicalinspect.c.md`).



### SnapBuildProcessChange
The snapshot-builder hook (`snapbuild.c:642`) called before each decoded change; it decides whether the current historic snapshot can yet see the change's transaction and so whether decoding has reached a consistent point. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/snapbuild.c.md`).



### SnapBuildState
The four-phase enum (`snapbuild.h:30-59`) tracking logical-decoding snapshot construction: `SNAPBUILD_START = -1`, `SNAPBUILD_BUILDING_SNAPSHOT = 0`, `SNAPBUILD_FULL_SNAPSHOT = 1`, and `SNAPBUILD_CONSISTENT = 2`. The numeric values are load-bearing because the `pg_logicalinspect` extension's `get_snapbuild_state_desc()` maps them to display strings ("start", "building", "full", "consistent") and must be kept in sync. [from-comment] (`snapbuild.h.md` — via `knowledge/files/src/include/replication/snapbuild.h.md`).



### snapshot
A `SnapshotData` value that captures which tuple versions a query may see. Its
`SnapshotType` selects the visibility regime — the seven types are `MVCC`,
`SELF`, `ANY`, `TOAST`, `DIRTY`, `HISTORIC_MVCC`, and `NON_VACUUMABLE` — and a
single struct is reused across table AMs instead of a per-AM callback.
[from-comment] (`snapshot.h:19-30` — via
`knowledge/files/src/include/utils/snapshot.h.md`).



### snapshot builder (snapbuild)
The logical-decoding machinery that reconstructs, from the WAL stream alone, a
historical catalog snapshot valid enough to decode each transaction's row
changes with the right relation/type metadata. It must reach a consistent
starting point (tracking running xacts) before decoding can emit changes.
[from-comment] (via
`knowledge/files/src/backend/replication/logical/snapbuild.c.md`).



### SNAPSHOT_MVCC
The standard snapshot type whose visibility rule is "committed before the snapshot was taken and not in-progress"; `HeapTupleSatisfiesMVCC` implements it and the visibility dispatcher passes `state = NULL` for the single-tuple case. [verified-by-code] (via `knowledge/files/src/include/utils/snapshot.h.md`).



### SnapshotAny
A pseudo-snapshot whose visibility function accepts every tuple regardless of xmin/xmax — used by maintenance code (VACUUM scans, amcheck, pgstattuple) that must see all physical tuples, dead or live, not a transactional view. [from-comment] (via `knowledge/files/contrib/pgstattuple/pgstattuple.c.md`).



### snapshotConflictHorizon
The XID carried by many WAL records marking the newest transaction whose
visibility could conflict with replay of that record. On a hot standby it
drives recovery-conflict cancellation of queries that might still need the
about-to-be-removed tuples. [from-comment] (via
`knowledge/files/src/backend/access/spgist/spgxlog.c.md`).



### SnapshotData
The read-side struct recording which transactions count as committed at snapshot time (xmin/xmax plus the in-progress `xip` array and a snapshot type); it holds the visibility horizon, not the rows themselves. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### SnapshotDirty
A special snapshot under which in-progress (uncommitted) tuples are treated as
visible, used by uniqueness checks and `EvalPlanQual`-style lookups that must see
rows other transactions are still writing. [verified-by-code] (via
`knowledge/docs-distilled/index-locking.md`).



### SnapshotResetXmin
Recomputes and lowers the backend's advertised xmin in `MyProc` after snapshots
are unregistered, releasing the vacuum horizon the backend was holding back.
[verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### SnapshotSelf
A special non-MVCC snapshot under which a tuple is visible if inserted by the
current command and not yet deleted; used for catalog scans that must see
in-progress changes within the same command. [verified-by-code] (via
`knowledge/idioms/snapshot-static-and-current.md`).



### Sort
Plan/executor node that buffers its child's entire output and returns it in sorted order via the tuplesort machinery, spilling to a temp file once the set exceeds `work_mem`; planners insert it to satisfy `ORDER BY`, merge joins, and grouping that needs ordered input. [inferred] (via `knowledge/subsystems/executor.md`).



### sort_template
The X-macro header `src/include/lib/sort_template.h` that generates type-specialized, inlined quicksort variants: a caller defines `ST_SORT`, `ST_ELEMENT_TYPE`, `ST_COMPARATOR_TYPE_NAME`, etc., then `#include`s it to emit a dedicated sort (e.g. `qsort_arg`, or `isort` in intarray) with no per-call function-pointer overhead. [verified-by-code] (`lib/sort_template.h` — via `knowledge/files/contrib/intarray/_int.md`).



### SortSupport
An optimization interface letting a datatype supply an inlinable comparator (and sometimes abbreviated keys) to tuplesort, avoiding a full fmgr call per comparison; opclasses register it via a SortSupport support function. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/sortsupport.c.md`).



### SortTuple
The fixed-size handle `tuplesort` manipulates: a pointer to the full tuple plus the first sort key inlined (`datum1` / `isnull1`) so the common single-key comparison avoids a dereference. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/tuplesortvariants.c.md`).



### SpecialJoinInfo
The planner struct (built in initsplan.c) describing a non-inner join — its outer/anti/semi type and minimum left/right relid sets — so the join-order search respects the join's commutativity and associativity limits. [verified-by-code] (via `knowledge/files/src/backend/optimizer/plan/initsplan.c.md`).



### SpGistSearchItem
The pairing-heap node driving an ordered (nearest-neighbor or plain) SP-GiST
index scan; it represents a pending tree item with its distance keys, and
`pairingheap_SpGistSearchItem_cmp` orders the queue so the scan returns items
in distance order. [verified-by-code] (`spgist_private.h:165-243` — via
`knowledge/idioms/spgist-scan-and-consistent.md`).



### spgMatchNode
The SP-GiST `choose` result that directs an insertion to descend into the N'th existing child node of an inner tuple (as opposed to adding a node or splitting the tuple). [verified-by-code] (via `knowledge/idioms/spgist-insert-and-picksplit.md`).



### spgSplitTuple
The SP-GiST `choose` result that splits an inner tuple into a prefix part and a postfix part to make room for a divergent value; illegal on fixed/unlabeled-node or `allTheSame` tuples. [verified-by-code] (via `knowledge/idioms/spgist-insert-and-picksplit.md`).



### SPI (Server Programming Interface)
The in-backend API (`SPI_connect`, `SPI_execute`, `SPI_prepare`, …) that lets C
code and PL handlers run SQL through the regular parser/planner/executor while
managing their own memory and snapshot nesting. It is how triggers, PL/pgSQL,
and many extensions issue queries. [from-comment] (via
`knowledge/idioms/spi.md`).



### SPI_commit
The SPI call that commits the current transaction from inside a nonatomic-context SPI procedure (e.g. a CALLed procedure), starting a fresh one; it and `SPI_rollback` (plus `SPI_commit_and_chain`) only work when SPI was connected in nonatomic mode. [from-README] (via `knowledge/docs-distilled/spi-transaction.md`).



### SPI_connect
Opens a Server Programming Interface session for the current backend, setting up the SPI memory context and procedure nesting so the caller can run SQL from C; balanced by `SPI_finish`. The canonical referential-integrity trigger demo uses it. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### spi_connect_ext
`SPI_connect_ext` opens an SPI session with option flags — notably `SPI_OPT_NONATOMIC`, which enables in-procedure transaction control (`SPI_commit` / `SPI_rollback`). [from-docs] (via `knowledge/docs-distilled/plpgsql-transactions.md`).



### SPI_copytuple
The SPI helper that copies a `HeapTuple` into the surrounding (saved) memory context so it outlives `SPI_finish`; used together with `SPI_returntuple`/`SPI_modifytuple` when a PL handler must hand a row back to its caller. [verified-by-code] (via `knowledge/docs-distilled/spi-memory.md`).



### SPI_execute
The SPI entry point that parses, plans and executes a one-shot query string in
a single call, capturing results in `SPI_tuptable`; the workhorse used by PLs
and C code to run SQL from inside the backend. [verified-by-code] (via
`knowledge/files/src/pl/plpython/plpy_spi.md`).



### SPI_finish
The Server Programming Interface call that tears down the SPI session opened by `SPI_connect`, freeing the SPI memory context and restoring the caller's context; every `SPI_connect` must be balanced by it (including on the error path). It is the close bracket around C/PL code that runs SQL via `SPI_execute`/`SPI_prepare`. [inferred] (via `knowledge/files/contrib/lo/lo.c.md`; see `knowledge/idioms/spi.md`).



### SPI_getvalue
Returns a column of an SPI result tuple as a freshly-palloc'd C string (running the type's output function), given the tuple, its descriptor, and a 1-based column number; NULL for a SQL NULL column. [verified-by-code] (via `knowledge/files/contrib/spi/refint.c.md`).



### SPI_keepplan
The SPI call that marks a prepared plan to survive past `SPI_finish`, moving
it under a long-lived context so a PL can cache the plan across invocations.
[verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### SPI_OPT_NONATOMIC
The SPI connect flag (`1 << 0`) passed to `SPI_connect_ext(options)` that opens an SPI session in non-atomic mode, permitting transaction control (`COMMIT`/`ROLLBACK`) inside the connection. PL handlers set it only when their caller is itself non-atomic (e.g. a procedure invoked by `CALL`), passing it down so embedded SQL can commit/rollback. [verified-by-code] (`spi.md` — via `knowledge/files/src/include/executor/spi.md`).



### SPI_palloc
The SPI allocation call that allocates in the caller's (pre-`SPI_connect`) memory context rather than SPI's own, so the result survives `SPI_finish`; part of the survivor set an SPI caller uses to return data past the SPI boundary. [verified-by-code] (via `knowledge/docs-distilled/spi-memory.md`).



### SPI_prepare
The SPI entry point that parses and plans a query string into a reusable
prepared-statement handle without executing it; the planned statement is
one-shot unless retained with `SPI_keepplan`. [verified-by-code] (via
`knowledge/idioms/spi.md`).



### spi_rollback
`SPI_rollback` rolls back the current transaction from within a procedure; permitted only in a non-atomic SPI context (a `CALL`, not a plain function). [from-docs] (via `knowledge/docs-distilled/spi.md`).



### SPI_tuptable
The global the Server Programming Interface fills with the result rows (a `SPITupleTable`) of the most recent `SPI_execute`; PL handlers read it together with `SPI_processed` to return query results. [verified-by-code] (via `knowledge/idioms/spi.md`).



### spinlock
The lowest-level mutual-exclusion primitive — a busy-wait lock held for only a
handful of instructions, with no deadlock detection and no wait queue. Used to
protect tiny shared structures (and to bootstrap LWLocks); long or blocking
work must never happen under one. [from-comment] (via
`knowledge/files/src/backend/storage/lmgr/s_lock.c.md`).



### SpinLockAcquire
Takes a spinlock — a busy-wait mutex for very short critical sections over a few
shared-memory words; the holder must not block, call into other modules,
ereport, or run `CHECK_FOR_INTERRUPTS`. [verified-by-code] (via
`knowledge/idioms/spinlock-discipline.md`).



### SpinLockRelease
Releases a spinlock taken by `SpinLockAcquire`; together they bracket the tiny
critical section over a few shared words, during which the holder must not block
or run interrupt checks. [verified-by-code] (via
`knowledge/idioms/spinlock-discipline.md`).



### SQL_ASCII
The default server encoding (`PG_SQL_ASCII = 0` in `enum pg_enc`, which MUST stay zero); it is the "byte-soup" mode in which PostgreSQL performs no encoding validation or conversion and treats data as raw bytes. The single-byte match paths (e.g. `SB_MatchText` in `like.c`) and `canonicalize_path` (which assumes server-safe encoding) rely on it, and several extensions (jsonb_plperl) require UTF-8 instead and warn that SQL_ASCII may misbehave. [verified-by-code] (`pg_wchar.h` — via `knowledge/files/src/include/mb/pg_wchar.h.md`).



### sql_drop
The `EventTriggerEvent` fired after objects are dropped, whose payload is consumed via `pg_event_trigger_dropped_objects()`; mapped by `evtcache.c` to enabled event-trigger functions. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### SQL_STR_DOUBLE
A C macro (`source/src/include/c.h:1255`) that tests whether a character must be doubled when emitting a single-quoted SQL string literal: `SQL_STR_DOUBLE(ch, true)` expands to `((ch) == '\'' || (ch) == '\\')`. The second argument is `escape_backslash`; when off (standard-conforming strings), only the single quote is doubled. [verified-by-code] (`quote.c.md` — via `knowledge/files/src/backend/utils/adt/quote.c.md`).



### SQLSTATE
The five-character machine-readable error code (SQL-standard class plus PostgreSQL subclass) attached to every report, chosen with errcode() from the symbolic names in errcodes.txt; clients branch on it rather than on message text. [verified-by-code] (`elog.h:69` — via `knowledge/idioms/error-handling.md`).



### SRF
Set-Returning Function — a function that returns a set of rows rather than a single value, used in the `FROM` clause or target list. `funcapi.h` defines the two protocols: value-per-call (return one row each invocation via `SRF_RETURN_NEXT`) and materialize (build a whole `Tuplestore` then return it). [verified-by-code] (via `knowledge/files/src/include/funcapi.h.md`).



### SRF_IS_FIRSTCALL
The set-returning-function macro that is true on a value-per-call SRF's first invocation, signalling it to allocate and initialize its `FuncCallContext`. [verified-by-code] (via `knowledge/files/src/include/funcapi.h.md`).



### SRF_RETURN_NEXT
A set-returning-function macro (`funcapi.h:311-318`) used in ValuePerCall mode that bumps `call_cntr`, sets the `ReturnSetInfo`'s `isDone = ExprMultipleResult`, and returns the result Datum. It assumes `fcinfo->resultinfo` is a `ReturnSetInfo`, so invoking an SRF via `DirectFunctionCall` crashes; `SRF_RETURN_NEXT_NULL` is the NULL-returning variant. [verified-by-code] (`funcapi.h.md` — via `knowledge/files/src/include/funcapi.h.md`).



### SS_process_sublinks
The subselect-planning routine (`subselect.c`) that rewrites each `SubLink` in an expression tree into a `SubPlan` (or a `Param` of kind PARAM_EXEC for uncorrelated initplans), depositing the finished child plan into the global `subplans` list. [verified-by-code] (via `knowledge/idioms/utility-stmt-planning.md`).



### SSI (serializable snapshot isolation)
PostgreSQL's implementation of `SERIALIZABLE` via predicate locks (SIREAD
locks) that track read/write dependencies between concurrent transactions; when
a dangerous structure of rw-conflicts forms, one transaction is aborted with a
serialization failure. The bookkeeping lives in `predicate.c`. [from-comment]
(via `knowledge/files/src/backend/storage/lmgr/predicate.c.md`).



### SSL
Secure Sockets Layer — the historical name (now TLS) for PostgreSQL's encrypted transport, enabled with `ssl = on` and configured via certificate/key files. The `sslinfo` contrib module exposes the negotiated cipher and client-certificate details to SQL. [verified-by-code] (via `knowledge/files/contrib/sslinfo/sslinfo.c.md`).



### ssl_in_use
The flag on the backend's `Port` (`MyProcPort->ssl_in_use`) recording whether the current client connection is TLS-encrypted; sslinfo's introspection functions gate every result on it, returning NULL on a non-TLS connection. [verified-by-code] (`sslinfo.c:5` — via `knowledge/files/contrib/sslinfo/sslinfo.c.md`).



### SSLok
The backend variable set to `'S'` or `'N'` in response to an `SSLRequest`, telling the client whether to start TLS or continue in plaintext. [verified-by-code] (`backend_startup.c:582` — via `knowledge/docs-distilled/ssl-tcp.md`).



### SSLRequest
The pre-startup message a client sends (carrying `NEGOTIATE_SSL_CODE`) to request TLS on the ordinary port before sending its StartupMessage. [verified-by-code] (`pqcomm.h:128` — via `knowledge/docs-distilled/ssl-tcp.md`).



### standard_conforming_strings
The GUC (on by default since 9.1) that makes ordinary `'...'` string literals treat backslashes literally per the SQL standard; libpq's escaping routines must know its server-side value to quote correctly, which is why the connectionless `PQescapeString` is unsafe. [verified-by-code] (`deparse.c:2880` — via `knowledge/files/contrib/postgres_fdw/deparse.c.md`).



### standard_executorstart
`standard_ExecutorStart` (`execMain.c:143`) is the default body of the `ExecutorStart` hook: it sets up the `EState` and per-query memory context and calls `InitPlan`. [verified-by-code] (via `knowledge/files/src/backend/executor/execMain.c.md`).



### standard_join_search
The default join-order search driver (what `join_search_hook` wraps): for each join level it enumerates candidate relation pairs and keeps the cheapest paths, building up the final joinrel. [verified-by-code] (`allpaths.c:3948` — via `knowledge/subsystems/optimizer.md`).



### standard_planner
The default top-level planner entry point — the function `planner_hook` wraps. It sets up `PlannerGlobal`, computes parallel-safety, calls `subquery_planner`, picks the cheapest path, runs `set_plan_references`/`SS_finalize_plan`, and returns a finished `PlannedStmt`. [verified-by-code] (via `knowledge/subsystems/optimizer.md`).



### standard_ProcessUtility
The default implementation of the utility-statement dispatcher; `ProcessUtility` calls through the `ProcessUtility_hook` chain, and a module that installs the hook typically ends by calling `standard_ProcessUtility` to do the real work (CREATE / DROP / ALTER / COPY / ...). [verified-by-code] (`utility.c:11` — via `knowledge/files/src/backend/tcop/utility.c.md`).



### StandbyModeRequested
The startup-process flag set when a `standby.signal` file is present, meaning replay should continue indefinitely (streaming/reading archived WAL) rather than stopping at the end of available WAL. [verified-by-code] (via `knowledge/idioms/crash-recovery-startup.md`).



### START_CRIT_SECTION
Opens a critical section in which any `ereport(ERROR)` is promoted to PANIC,
used to bracket the buffer-modify + WAL-emit sequence so a backend can never
abort with the page changed but the WAL unwritten. No palloc-failure or
interrupt may escape until `END_CRIT_SECTION`. [from-comment] (`hio.c:35-38` —
via `knowledge/subsystems/access-heap.md`).



### start_lsn
The inclusive lower bound of a WAL byte range; SQL WAL readers like `pg_walinspect` decode the records between `(start_lsn, end_lsn)`. [verified-by-code] (`pg_walinspect.c:7` — via `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`).



### start_postmaster
The pg_upgrade helper that boots a target cluster's postmaster (old or new) so the tool can read schema/state and restore/adjust catalogs; pg_upgrade registers an atexit handler so the postmaster is stopped even on abnormal exit. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/server.c.md`).



### START_REPLICATION
The replication-protocol command a standby or logical client sends to begin
streaming WAL from a position: `START_REPLICATION [SLOT s] PHYSICAL X/X
[TIMELINE n]` for physical, or `... SLOT s LOGICAL X/X (options)` for logical
decoding. Parsed by the replication grammar `repl_gram.y`. [verified-by-code]
(via `knowledge/files/src/backend/replication/repl_gram.y.md`).



### StartParallelWorkerTransaction
The `xact.c` entry point (looked up via `PARALLEL_KEY_TRANSACTION_STATE` in the DSM TOC) that reconstructs the leader's transaction state — top XID, subxact stack, command ID — into a parallel worker's `CurrentTransactionState`. It is not a regular `StartTransactionCommand`: workers join the leader's existing transaction rather than starting their own, so they cannot allocate their own XID; it is the inverse of the leader's `SerializeTransactionState`. [verified-by-code] (`parallel-state-propagation.md` — via `knowledge/idioms/parallel-state-propagation.md`).



### StartReadBuffers
A PG17+ asynchronous/batched buffer-read entry point that initiates a multi-block read (used together with `StartReadBuffer` and `WaitReadBuffers`, e.g. by read_stream.h). The `ReadBuffersOperation` private members must not be touched by the caller between `StartReadBuffers` and `WaitReadBuffers`. [verified-by-code] (`bufmgr.h` — via `knowledge/files/src/include/storage/bufmgr.h.md`).



### StartTransaction
The xact.c routine that begins a top-level transaction: it allocates a transaction state, sets the start timestamp and isolation level, and initializes resource owners — but defers acquiring a real XID until `AssignTransactionId` is forced by a write. [verified-by-code] (`xact.c:2106` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### StartTransactionCommand
The state-smart xact.c entry point that postgres.c calls before executing each client command — starting a new transaction or continuing the existing one — paired with `CommitTransactionCommand` afterward. [from-README] (via `knowledge/files/src/backend/access/transam/README.md`).



### startup_cb
The logical-decoding output-plugin callback invoked once when decoding of a slot begins, where the plugin inspects options, declares whether it wants binary output, and allocates its private state. It is paired with `shutdown_cb` at teardown. [inferred] (via `knowledge/idioms/output-plugin-callbacks.md`).



### startup_cost
The `Path` field estimating the cost incurred before the first output row can be produced — e.g. building a hash table or sorting. A node with a high startup but low per-row cost can still win for plans that consume all rows. [inferred] (via `knowledge/idioms/cost-join-paths.md`).



### StartupSUBTRANS
Recovery-time initialisation of pg_subtrans that re-zeros the latest subtrans page so the SLRU is consistent before normal operation resumes. [from-comment] (via `knowledge/files/src/backend/access/transam/subtrans.c.md`).



### StartupXLOG
The startup-process entry point that performs WAL replay / crash recovery and
brings the cluster to a consistent state before normal operation begins.
[verified-by-code] (`xlog.c:5846` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### statement_timeout
GUC aborting a statement that runs longer than the limit; it is armed as `STATEMENT_TIMEOUT` alongside `LOCK_TIMEOUT` in `ProcSleep`, and is the last-resort backstop for pathological CPU-bound operators (e.g. ltree backtracking) that `check_stack_depth` cannot catch. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/proc.c.md`).



### StaticAssert
A compile-time assertion (`StaticAssertDecl` / `StaticAssertStmt`) that
fails the build if a constant condition is false; used to pin struct sizes
and flag/enum invariants that must not silently drift. [from-comment] (via
`knowledge/subsystems/contrib-hstore_plperl.md`).



### StaticAssertDecl
The compile-time assertion macro (a declaration-context `_Static_assert`
wrapper) used to enforce invariants the compiler can check — struct field
ordering, size relationships, enum bounds — turning a silent miscompile into a
build error. Several load-bearing catalog/PL conventions lack one (a recurring
corpus issue). [from-comment] (via
`knowledge/files/src/pl/plpgsql/src/plpgsql.md`).



### StaticAssertStmt
The compile-time assertion macro PG uses to enforce invariants the compiler
can check — array lengths matching an enum count, struct sizes, flag-bit
non-overlap — failing the build rather than the running server. e.g.
`StaticAssertStmt(lengthof(arr) == NUM_TAGS, ...)` keeps a lookup table in sync
with its enum. [verified-by-code] (via
`knowledge/files/contrib/pg_plan_advice/pgpa_ast.h.md`).



### STATISTIC_KIND_MCELEM
The `pg_statistic` slot kind holding most-common-element statistics for array (and tsvector) columns; the planner uses it to estimate `&&`, `@>`, and `<@` selectivity. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/array_typanalyze.c.md`).



### statistic_proc_security_check
The ANALYZE guard that ensures a column's `typanalyze`/statistics function is only run with privileges the table owner legitimately has, preventing a malicious leaky function from being executed with elevated rights during analyze. [verified-by-code] (via `knowledge/files/src/backend/commands` analyze docs).



### STATS_MAX_DIMENSIONS
The hard cap (8) on the number of attributes per extended-statistics object. It is structurally hard-coded across multiple representations (e.g. `MCVList.types[STATS_MAX_DIMENSIONS]` and the `int2vector stxkeys` signature), so raising it would require touching all of them coherently. [verified-by-code] (`statistics.h` — via `knowledge/files/src/include/statistics/statistics.h.md`).



### STATUS_OK
One of the `STATUS_OK / STATUS_ERROR / STATUS_EOF` return-code constants defined in `c.h`, used pervasively by the libpq backend authentication path. Functions like `ClientAuthentication()`, `CheckSASLAuth()`, and password verification return `STATUS_OK` on success; the `auth_delay` hook, for example, sleeps only when `status != STATUS_OK`. [verified-by-code] (`c.h.md` — via `knowledge/files/src/include/c.h.md`).



### std_strings
The connection's `standard_conforming_strings` state that libpq string-escaping consults via `SQL_STR_DOUBLE` to decide whether a backslash needs doubling. The no-`PGconn` escaping path uses a static `static_std_strings` defaulting to `false`, which is unsafe for non-ASCII data against a modern server — prefer `PQescapeLiteral` / `PQescapeStringConn`. [from-comment] (`fe-exec.c:4234-4248` — via `knowledge/files/src/interfaces/libpq/fe-exec.c.md`).



### std_typanalyze
The default ANALYZE type-analysis function: it installs the standard most-common-values / histogram / correlation compute callback for a column, and is what custom `typanalyze` functions (e.g. for arrays) call first to set up the standard slots. [verified-by-code] (via `knowledge/files/src/backend/commands` analyze docs).



### StoredKey
In SCRAM, `H(ClientKey)` — the value actually kept in the `pg_authid`
verifier. During authentication the server reconstructs a candidate client key
from the client proof and the computed client signature, hashes it, and compares
to `StoredKey`, so the plaintext-equivalent client key is never stored.
[verified-by-code] (`auth-scram.c:1147-1189` — via
`knowledge/files/src/backend/libpq/auth-scram.c.md`).



### str_tolower
The locale-aware lowercasing routine used by `formatting.c` and the `lower()`
SQL function; it honors the collation's provider (libc/ICU/builtin) and handles
multibyte encodings, unlike a naive byte-wise downcase. Paired with `str_toupper`
and `str_initcap`. [verified-by-code] (via
`knowledge/files/src/backend/utils/adt/formatting.c.md`).



### StrategyGetBuffer
The buffer-manager clock-sweep routine that selects a victim buffer to evict (or
draws from the free list / the supplied `BufferAccessStrategy` ring) when a new
page must be read in. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### StrategyNumber
The small integer naming an operator's role within an opclass (e.g. btree's 1..5
for `< <= = >= >`), letting the AM map a WHERE-clause operator to index semantics.
[verified-by-code] (via `knowledge/idioms/typcache-entry-and-lookup.md`).



### STREAM_ABORT
The logical-replication protocol message (LOGICAL_REP_MSG_STREAM_ABORT) that aborts a streamed in-progress transaction or one of its subtransactions on the apply side, discarding the spooled changes. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/applyparallelworker.c.md`).



### stream_abort_cb
Logical-decoding output-plugin callback invoked when a streamed (sub)transaction aborts, so the plugin can discard the partially-streamed changes. [from-docs] (via `knowledge/docs-distilled/logicaldecoding-output-plugin.md`).



### STREAM_COMMIT
The logical-replication protocol message (LOGICAL_REP_MSG_STREAM_COMMIT) that concludes a streamed in-progress large transaction on the apply side, committing the spooled changes. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/worker.c.md`).



### stream_commit_cb
Logical-decoding output-plugin callback that commits a streamed transaction — one of the two terminators of a stream (the other being `stream_prepare_cb`). [from-docs] (via `knowledge/docs-distilled/logicaldecoding-output-plugin.md`).



### stream_prepare_cb
Logical-decoding output-plugin callback that prepares a streamed two-phase transaction, terminating the stream in place of `stream_commit_cb`. [from-docs] (via `knowledge/docs-distilled/logicaldecoding-streaming.md`).



### STREAM_START
The logical-replication protocol message (wire byte `S`) that frames the beginning of a streamed (in-progress) transaction, paired with STREAM_STOP (`E`), STREAM_COMMIT (`c`), STREAM_ABORT (`A`), and STREAM_PREPARE (`p`). The lowercase/uppercase convention distinguishes streamed from non-streamed message variants. [verified-by-code] (`logicalproto.h` — via `knowledge/files/src/include/replication/logicalproto.h.md`).



### stream_start_cb
Logical-decoding output-plugin callback marking the start of a block of changes for an in-progress (streamed) transaction; paired with `stream_stop_cb`. [from-docs] (via `knowledge/docs-distilled/logicaldecoding-streaming.md`).



### STREAM_STOP
A logical-replication streaming protocol message that ends a chunk of an in-progress (uncommitted) transaction's changes, complementing `STREAM_START`/`STREAM_COMMIT`/`STREAM_ABORT`. On the subscriber it is the point where a parallel apply worker commits its current spool segment (saving the spool offset) and, per the leader/worker locking protocol, where the leader takes its lock before sending the message. [verified-by-code] (`applyparallelworker.c` — via `knowledge/idioms/apply-streaming-and-parallel.md`).



### stream_stop_cb
Logical-decoding output-plugin callback marking the end of a streamed-transaction change block opened by `stream_start_cb`. [from-docs] (via `knowledge/docs-distilled/logicaldecoding-output-plugin.md`).



### string_utils
`src/fe_utils/string_utils.c` — the frontend (client/utility) string helpers: SQL identifier and literal quoting (`fmtId`, `appendStringLiteralConn`), `PQExpBuffer` building, and shell-argument escaping shared by psql, pg_dump, and the other `src/bin` tools so they emit correctly quoted SQL. [verified-by-code] (via `knowledge/files/src/fe_utils/string_utils.c.md`).



### StringInfo
The resizable string/byte buffer (`StringInfoData`: data, len, maxlen, cursor)
used everywhere PostgreSQL builds up text or binary output — error messages,
wire-protocol messages, COPY data. `appendStringInfo*` grow it via `repalloc`;
`cursor` tracks read position when it backs an incoming message. [from-comment]
(via `knowledge/files/src/common/stringinfo.c.md`).



### StringInfoData
The resizable byte-buffer struct (`data`/`len`/`maxlen`/`cursor`) that is PG's backend-wide alternative to ad-hoc `realloc` and to the frontend `PQExpBuffer`; `makeStringInfo` allocates one initialised to `STRINGINFO_DEFAULT_SIZE` (1024). [verified-by-code] (`stringinfo.c:71-75` — via `knowledge/files/src/common/stringinfo.c.md`).



### stringToNode
The node-tree deserializer (inverse of `outfuncs.c`'s `nodeToString`) that
rebuilds a Node tree from its textual representation; used to load stored
rules, views, and other catalog-serialized plans. [verified-by-code] (via
`knowledge/files/src/backend/nodes/readfuncs.c.md`).



### SUB_COMMITTED
A transient CLOG transaction status (`TRANSACTION_STATUS_SUB_COMMITTED = 3`, alongside `IN_PROGRESS`, `COMMITTED`, `ABORTED`) marking a subtransaction whose work is done while the top-level transaction is still open. It exists to preserve single-page atomicity when a transaction tree straddles multiple CLOG pages: `TransactionIdSetTreeStatus` first marks off-page subxids `SUB_COMMITTED`, then sets the parent `COMMITTED`, enforcing the recovery rule "if the parent is COMMITTED, every subxact is at least SUB_COMMITTED." [from-comment] (`clog-slru.md` — via `knowledge/idioms/clog-slru.md`).



### SubLink
A parse-tree node representing a sub-SELECT appearing in an expression — EXISTS, IN, ANY/ALL, scalar, or expression sublink; the planner later converts it into a SubPlan or, where possible, pulls it up into a join. [verified-by-code] (via `knowledge/subsystems/parser-and-rewrite.md`).



### suboverflowed
The snapshot boolean set when the ProcArray's per-backend subxid cache overflowed, meaning the `subxip` list is incomplete; visibility for affected subxids must then be resolved through `pg_subtrans` instead of the array. [verified-by-code] (via `knowledge/idioms/subxact-visibility-and-overflow.md`).



### SubPlan
A planner/executor representation of a sub-SELECT that is evaluated per outer
row (or per comparison) — `SS_process_sublinks` turns a correlated SubLink into
a SubPlan attached to the parent expression tree, with ALL/ANY/EXISTS getting
specialised SubPlan subtypes. Contrast with InitPlan, which runs once.
[from-comment] (via
`knowledge/files/src/backend/optimizer/plan/subselect.c.md`).



### subplans
The cumulative list in `PlannerGlobal` of finished `Plan` nodes for the query's SubPlans, indexed by SubPlan id; it is the source of truth into which `SS_process_sublinks` deposits each initplan/subplan as planning completes. [verified-by-code] (via `knowledge/data-structures/plannerinfo.md`).



### subquery_planner
The recursive entry point that plans one query level (a SELECT/INSERT/UPDATE/DELETE/MERGE Query): it pulls up sublinks and subqueries, flattens the jointree, builds base RelOptInfos, finds the cheapest join order, and hands off to grouping_planner for the upper rels. Set-operation arms and uncorrelated subqueries are each planned by their own subquery_planner call. [from-comment] (via `knowledge/files/src/backend/optimizer/prep/prepunion.c.md`; see `knowledge/subsystems/optimizer.md`).



### SubqueryScan
The plan/exec node wrapping a sub-select's output; a trivial one (adding no real projection) is deleted in setrefs.c by `trivial_subqueryscan` once final target lists are known. [from-comment] (via `knowledge/files/src/backend/optimizer/plan/setrefs.c.md`).



### SubscriptingRefState
The out-of-line per-expression state struct for container subscripting operations (array/jsonb element get and assign), defined in `execExpr.h` immediately after `ExprEvalStep`. Because it is too large to fit inline within the 64-byte-capped `ExprEvalStep` union, both the `sbsref_subscript` and `sbsref` d-union members hold only a pointer to a single shared `SubscriptingRefState` — the first step initializes it and subsequent steps read and update it. It is the canonical model for the out-of-line state pattern. [verified-by-code] (`execExpr.h:785-812` — via `knowledge/idioms/exprevalstep-shape.md`).



### SubscriptRoutines
The vtable a type's subscript handler returns (`subscripting.h`): `transform` (parse-analyze the subscript expression), `exec_setup`, and the fetch/assign steps — the pluggable-subscripting API shared by array subscripting and jsonb subscripting. [verified-by-code] (`jsonbsubs.c:403` — via `knowledge/files/src/include/nodes/subscripting.h.md`).



### SubTrans
Shorthand for the pg_subtrans SLRU, which maps each subtransaction xid to its immediate parent xid; snapshot code falls back to it when a backend's in-PGPROC subxid cache has overflowed. [verified-by-code] (via `knowledge/files/src/backend/access/transam/subtrans.c.md`).



### SUBTRANS_XACTS_PER_PAGE
The number of subtransaction parent-xid entries stored per SLRU page in the pg_subtrans machinery; it maps an xid to its (page, offset) position. [verified-by-code] (via `knowledge/files/src/backend/access/transam/subtrans.c.md`).



### subtransaction (subtrans)
A nested transaction created by a `SAVEPOINT` (or PL exception block) that can
roll back independently of its parent; each gets its own `TransactionId`. The
`pg_subtrans/` SLRU maps a subxid to its parent so visibility checks can walk up
to the top-level xid. [from-comment] (via
`knowledge/files/src/backend/access/transam/subtrans.c.md`).



### subtransaction_buffers
The GUC sizing the pg_subtrans SLRU's shared buffer pool (0 = auto-scale from `shared_buffers`); it directly affects the cost of the `pg_subtrans` lookups that overflowed-subxact visibility falls back to. [from-docs] (via `knowledge/idioms/subxact-subtrans-slru.md`).



### SubTransactionId
A backend-local counter identifying a savepoint/subtransaction within the
current top-level transaction (distinct from the XID a subxact may or may not
acquire). Used to scope resource ownership and rollback-to-savepoint.
[from-README] (via
`knowledge/files/src/backend/access/transam/README.md`).



### SubTransCtl
The SLRU control object for the `pg_subtrans` (subtransaction → parent XID) log; `ExtendSUBTRANS` grows it as XIDs are assigned and `SubTransGetParent` / `SubTransSetParent` read and write the parent linkage. [verified-by-code] (via `knowledge/files/src/backend/access/transam/subtrans.c.md`).



### SubTransGetParent
The single-step `pg_subtrans` SLRU lookup (`subtrans.c:125-156`) that returns the immediate parent TransactionId of a subtransaction xid, or `InvalidTransactionId` if the xid is not normal. It asserts the xid is at or after `TransactionXmin`, takes no lock across iterations, and is the building block that `SubTransGetTopmostTransaction` calls repeatedly to walk up the subxact chain to the top-level xid. [verified-by-code] (`subxact-subtrans-slru.md` — via `knowledge/idioms/subxact-subtrans-slru.md`).



### SubTransGetTopmostTransaction
Walks the subtrans SLRU parent chain from a given XID up to the topmost
transaction id, the lookup that lets visibility code map a subtransaction's XID
to the transaction whose commit/abort decides its fate. [verified-by-code] (via
`knowledge/docs-distilled/subxacts.md`).



### SubTransSetParent
Records a subtransaction's parent XID in the subtrans SLRU when the
subtransaction is assigned an XID, building the chain
`SubTransGetTopmostTransaction` later walks. [verified-by-code] (via
`knowledge/idioms/subxact-visibility-and-overflow.md`).



### subxip
The snapshot array of committed sub-transaction xids, parallel to the top-level `xip` array; consulted for visibility when a subxact's parent is still running. It is bounded, and overflow flips `suboverflowed`, after which visibility must fall back to `pg_subtrans`. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### suffix truncation
The B-tree optimization that drops non-key (`INCLUDE`) columns — and trailing *key* columns once the remaining prefix already uniquely describes leaf tuples — from upper-tree pages, so `INCLUDE` payload does not bloat internal pages the way adding the column to the key would. [from-docs §11.9] (via `knowledge/docs-distilled/indexes-index-only-scans.md`; home `knowledge/files/src/backend/access/nbtree/nbtdedup.c.md`).



### summarize_range
The BRIN routine (`brin.c`) that builds the summary tuple for one page range — scanning the range's heap tuples, folding them into the opclass union via `brin_form_tuple`, and installing the result over its placeholder. [verified-by-code] (via `knowledge/idioms/brin-summarize-and-scan.md`).



### SupportRequestSelectivity
One of the planner-support-function request types (`supportnodes.h`): a function
can register a support function that the planner calls to supply selectivity,
cost, row-count, or index-condition simplifications it could not derive
generically. The mechanism that lets functions like `LIKE` or range operators
teach the optimizer about themselves. [verified-by-code] (via
`knowledge/files/src/include/nodes/supportnodes.h.md`).



### sv2cstr
The PL/Perl helper that converts a Perl `SV` to a palloc'd, UTF-8-decoded C string when marshalling values from Perl code back into the backend. [verified-by-code] (via `knowledge/files/src/pl/plperl` docs).



### SwitchToUntrustedUser
The helper (paired with `RestoreUserContext`) that temporarily drops to a
less-privileged user id while running code that shouldn't execute with the
caller's privileges — e.g. maintenance commands touching user-defined index
expressions or a SECURITY-sensitive index build. It captures the prior
user/SecContext so the switch is reliably undone. [verified-by-code] (via
`knowledge/files/src/include/utils/usercontext.h.md`).



### sync_pgdata
The common file-utils routine that recursively fsyncs a data directory for crash safety; note its `walkdir` treats mid-walk `opendir`/`readdir` errors as non-fatal, so a transient EIO can let it return "success" without every file having been fsynced. [verified-by-code] (via `knowledge/files/src/common/file_utils.c.md`).



### synchronized_standby_slots
GUC naming physical slots that must confirm WAL receipt before a logical walsender may send changes downstream, preventing logical subscribers from getting ahead of physical standbys; `StandbySlotsHaveCaughtup` gates the wakeup. [verified-by-code] (via `knowledge/files/src/backend/replication/slot.c.md`).



### synchronous_commit
The transaction-level GUC deciding whether commit waits for WAL durability: when on, `RecordTransactionCommit` calls `XLogFlush(XactLastRecEnd)` (and, for the sync-replication levels, waits for standby ack) before returning; when off, commit returns before the flush. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### synchronous_standby_names
GUC listing the standbys (and quorum/priority rules) required for synchronous commit; a dedicated Bison grammar (`syncrep_gram.y`) parses it, `SYNC_STANDBY_DEFINED` marks it non-empty, and check/assign hooks validate it. [verified-by-code] (via `knowledge/files/src/backend/replication/syncrep_gram.y.md`).



### SyncRepRequested
The macro `max_wal_senders > 0 && synchronous_standby_names` non-empty, telling a committing backend whether it must wait for synchronous-standby acknowledgement before returning. [verified-by-code] (via `knowledge/files/src/include/replication/syncrep.h.md`).



### SyncRepWaitForLSN
The routine a committing backend calls under synchronous replication to block
until enough standbys have confirmed the commit LSN (per `synchronous_commit`
level and `synchronous_standby_names`). [verified-by-code] (`syncrep.c:149` —
via `knowledge/subsystems/replication.md`).



### SysCache
The static array (indexed by the `SysCacheIdentifier` enum, populated from a genbki-generated `cacheinfo[]`) that backs the syscache — a named-cache facade over the lower-level catcache. Public API `SearchSysCacheN`, `SearchSysCacheLockedN`, `SearchSysCacheCopyN`, and `SysCacheGetAttr` look up catalog rows by key through it. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### syscache (system cache)
The indexed front end over catcache: a fixed table of well-known catalog
lookups (`RELOID`, `PROCOID`, `TYPEOID`, …) addressed by an enum, accessed
through `SearchSysCache1..4` and `GetSysCacheOid`. It is the normal way backend
C code reads a single catalog row. [from-comment] (via
`knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SysCacheGetAttr
Extracts one attribute (handling NULLs) from a tuple obtained via the syscache, given the cache id and attnum; the standard way to read a column off a `SearchSysCache` result before `ReleaseSysCache`. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/syscache.c.md`).



### SysCacheIdentifier
The enum that names each system cache; `SysCache[]` is a global `CatCache *` array indexed by it, populated from a genbki-generated `cacheinfo[]` at `InitCatalogCache`. [verified-by-code] (`syscache.c:87` — via `knowledge/subsystems/utils-cache.md`).



### SysCacheInvalidate
Propagates a catalog change to the syscaches by issuing the appropriate
invalidation messages for the affected cache(s), so stale catcache/relcache
entries are dropped. [verified-by-code] (via
`knowledge/idioms/syscache-invalidation-flow.md`).



### SysScanDesc
The descriptor returned by `systable_beginscan`, which hides whether a
catalog scan runs as an index scan or a sequential scan behind one interface, so
catalog-reading code (`SearchSysCache` misses, `RelationBuildDesc`, …) doesn't
care which. `systable_getnext` and `systable_endscan` operate on it.
[verified-by-code] (`genam.c:388` — via
`knowledge/files/src/backend/access/index/genam.c.md`).



### systable_beginscan
The genam wrapper for reading a system catalog: it picks an index scan when an
index is usable (`indexOK`, an OID is supplied, and system indexes aren't
ignored) and otherwise does a heap sequential scan applying the scan keys via
`HeapKeyTest` — hiding the choice behind a `SysScanDesc`. Catalog readers use it
so they work even when an index is being rebuilt. [verified-by-code]
(`genam.c:388-490` — via
`knowledge/files/src/backend/access/index/genam.c.md`).



### system_identifier
A 64-bit value generated at `initdb` (from timestamp and PID) stamped into `pg_control` and every WAL page; replication and tools like `pg_rewind` compare it to refuse mixing data from unrelated clusters. [verified-by-code] (`pg_rewind.c:743-790` — via `knowledge/files/src/bin/pg_rewind/pg_rewind.c.md`).



### t_cid
The command-id field of a heap tuple header, overlaid in a union with the ctid speculative-insertion token. When a tuple is both inserted and deleted by different commands of the same transaction it holds a combo CID (see `combocid-handling`) rather than a raw cmin/cmax. [inferred] (via `knowledge/idioms/combocid-handling.md`).



### t_ctid
The field in a heap tuple header holding an item pointer that normally points to the tuple itself, but for an updated row points to the next (newer) version, forming the update/HOT chain that MVCC and the executor follow to find the live tuple. A self-pointing `t_ctid` marks the chain end. [verified-by-code] (via `knowledge/files/src/include/access/htup_details.h.md`).



### t_data
The `HeapTupleHeader t_data` pointer inside the in-memory `HeapTupleData` wrapper (`htup.h:62`); when it points into a shared buffer the caller MUST hold a pin on that buffer — an invariant not encoded in the struct (a documented footgun). [from-comment] (via `knowledge/subsystems/access-heap.md`).



### t_hoff
The heap-tuple header field giving the byte offset from the start of the tuple to its user data — i.e. the size of the (possibly null-bitmap- and OID-extended) header, MAXALIGN'd. amcheck checks it equals the recomputed `expected_hoff` derived from the header size and the null bitmap. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### t_info
A `uint16` header field: in nbtree index tuples it packs the tuple size plus status bits like `INDEX_ALT_TID_MASK` (distinguishing pivot/posting tuples); in SP-GiST inner tuples it stores a 14-bit `nextOffset` plus flag bits (including the NIL-pointer flag). [verified-by-code] (via `knowledge/idioms/spgist-tree-and-tuples.md`).



### t_infomask
The 16-bit flag word in a heap tuple header (`HeapTupleHeaderData`) recording xmin/xmax commit status hint bits, the HASNULL/HASVARWIDTH layout flags, and lock state such as `HEAP_XMAX_IS_MULTI`. Visibility checks read and lazily set these bits. [inferred] (`htup_details.h:188` — via `knowledge/data-structures/heap-tuple-layout.md`).



### t_infomask2
The second infomask in the heap tuple header: its low bits hold the attribute count (`HEAP_NATTS_MASK`) and the high bits carry HOT-update and key-update flags such as `HEAP_HOT_UPDATED` and `HEAP_KEYS_UPDATED`. Splitting the flags across two masks kept the header at its historic width. [inferred] (`htup_details.h:153` — via `knowledge/subsystems/access-heap.md`).



### t_rangetblentry
The `T_RangeTblEntry` node tag a `query_tree_walker` callback must handle when `QTW_EXAMINE_RTES_BEFORE` / `_AFTER` is set, so range-table entries are visited rather than silently skipped. [verified-by-code] (via `knowledge/idioms/query-tree-walkers.md`).



### t_self
The `ItemPointerData` in a `HeapTuple` recording the tuple's own physical location (block, offset) — its TID; preserved across operations that expand or copy the tuple in memory. [verified-by-code] (`htup.h:58-60` — via `knowledge/data-structures` heap-tuple docs).



### t_tid
The `ItemPointerData` at the front of a heap tuple header. In a live tuple it normally points at itself; after an update it becomes the ctid forward-link to the newer version, which is how update chains and HOT chains are walked. [inferred] (via `knowledge/idioms/combocid-handling.md`).



### t_xmax
The heap tuple-header field holding the deleting/locking transaction's XID — or, when `HEAP_XMAX_IS_MULTI` is set, a MultiXactId; with `t_xmin` it drives MVCC visibility. [verified-by-code] (`htup_details.h:122` — via `knowledge/data-structures` heap-tuple docs).



### t_xmin
The heap tuple-header field (in `HeapTupleFields`) holding the inserting transaction's XID; together with `t_xmax` it is the basis of MVCC visibility decisions. [verified-by-code] (`htup_details.h:122` — via `knowledge/data-structures` heap-tuple docs).



### t_xvac
A legacy heap-header field (union with `t_cid`) once used by `VACUUM FULL`'s move machinery to record the vacuuming xid; freezing a tuple with a set `t_xvac` is always mandatory. [verified-by-code] (via `knowledge/data-structures/heap-tuple-layout.md`).



### table_close
Releases a table relation opened with `table_open`, optionally keeping the lock until transaction end; the relation-cleanup call paired with `table_open`, forwarding to `relation_close`. [verified-by-code] (via `knowledge/files/contrib/sepgsql/relation.c.md`).



### table_open
The table access-method wrapper around `relation_open` that opens a relation by
OID with a given lockmode and asserts the relation is a table-like object (not
an index). Paired with `table_close`; the index analogue is `index_open`.
[verified-by-code] (via
`knowledge/files/src/backend/access/common/relation.c.md`).



### table_rewrite
The `EventTriggerEvent` fired when a DDL command rewrites a table's on-disk representation (e.g. some `ALTER TABLE ... TYPE`); mapped by `evtcache.c` to enabled event-trigger functions. [verified-by-code] (via `knowledge/subsystems/utils-cache.md`).



### TableAmRoutine
The struct of callbacks defining a pluggable table access method — tuple insert/update/delete/lock, scan begin/getnext, index-fetch, vacuum, analyze, and size estimation; heap is the built-in implementation returned by its handler. [verified-by-code] (`tableamapi.c:27` — via `knowledge/files/src/backend/access/table/tableamapi.c.md`).



### TAR_BLOCK_SIZE
The standard tar block size constant, `TAR_BLOCK_SIZE = 512` (`pgtar.h:17`), used throughout PG's tar handling for base backups, `pg_dump` tar-format archives, and the replication protocol. Because it is a power of two, padding to a block boundary can be computed with `TYPEALIGN(TAR_BLOCK_SIZE, len) - len`. [verified-by-code] (`pgtar.h.md` — via `knowledge/files/src/include/pgtar.h.md`).



### TargetEntry
A node in a query or plan's target list: an expression paired with its output
resno, column name, and `resjunk` flag. The plpgsql simple-expression fast path,
for example, peels a plan down to a single `Result` and caches that node's lone
TargetEntry expression. [verified-by-code]
(via `knowledge/files/src/pl/plpgsql/src/pl_exec.md`).



### targrows
The target number of sample rows ANALYZE aims to collect — derived from the largest per-column statistics target (default ~300 * target); `acquire_sample_rows` uses two-stage block + reservoir sampling to draw approximately this many rows. [verified-by-code] (via `knowledge/idioms/analyze-block-and-reservoir-sampling.md`).



### TAS_SPIN
The spinlock test-and-set spin macro: on most platforms it retries `TAS()` in a tight loop (with a delay/backoff on repeated failure) until the lock word is acquired. [verified-by-code] (via `knowledge/files/src/include/storage/s_lock.h.md`).



### tbm_add_page
The `TIDBitmap` call that marks an entire heap page as a match (a lossy, whole-page entry) rather than adding individual tuple offsets — used by scans like BRIN that qualify at page granularity. [verified-by-code] (via `knowledge/idioms/tidbitmap-build-and-iterate.md`).



### tbm_add_tuples
Records a set of heap TIDs into a `TIDBitmap`, switching a page entry from exact (per-offset bits) to lossy (whole-page) when the bitmap outgrows its work-memory budget. Bitmap index scans build the bitmap this way before the heap scan reads it back. [inferred] (via `knowledge/idioms/tidbitmap-build-and-iterate.md`).



### tbm_create
The constructor for a `TIDBitmap`, given a memory budget (and optionally a DSA for shared/parallel use); the first call in the bitmap lifecycle of create -> add tuples/pages -> iterate -> free. [verified-by-code] (via `knowledge/idioms/tidbitmap-build-and-iterate.md`).



### tbm_intersect
The TIDBitmap operation computing `a &= b` (bitmap AND), used to combine multiple bitmap index scans; it may upgrade pages to lossy mid-operation to stay within memory. [verified-by-code] (`tbm_intersect` at line 528 — via `knowledge/files/src/backend/nodes/tidbitmap.c.md`).



### tbm_lossify
The `TIDBitmap` memory-pressure fallback that converts exact per-tuple page entries into lossy page-only entries when the bitmap would exceed `work_mem`, trading precision (forcing a later recheck) for bounded memory. [verified-by-code] (via `knowledge/idioms/tidbitmap-build-and-iterate.md`).



### TBM_ONE_PAGE
A TIDBitmap PagetableEntry status meaning the bitmap currently holds exactly one page's entry inline (entry1) — the small-bitmap optimisation used before the bitmap grows into a hash table. [verified-by-code] (via `knowledge/idioms/tidbitmap-structure-and-lossy.md`).



### tbm_union
The `TIDBitmap` operation that ORs another bitmap into this one, the mechanism behind a `BitmapOr` executor node combining child bitmap-index-scan results. [verified-by-code] (via `knowledge/idioms/tidbitmap-build-and-iterate.md`).



### TBMIterateResult
The per-page result struct yielded by iterating a `TIDBitmap` (`tidbitmap.h`): a block number plus either an offset array (exact) or a lossy flag telling the heap scan it must recheck every tuple on the page. [verified-by-code] (via `knowledge/idioms/tidbitmap-build-and-iterate.md`).



### TCFLAGS_HAVE_PG_TYPE_DATA
A typcache entry flag indicating the cached pg_type fields are populated; a relevant invalidation clears it so the next lookup reloads them. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### TCFLAGS_OPERATOR_FLAGS
A composite bitmask in the type cache (`typcache.c:122-125`) covering all the operator- and support-proc-related flag bits — defined as the complement of the basic flags (`~(HAVE_PG_TYPE_DATA | CHECKED_DOMAIN_CONSTRAINTS | DOMAIN_BASE_IS_COMPOSITE)`). On a `pg_opclass` invalidation, `TypeCacheOpcCallback` clears this mask on every cache entry, wiping everything operator-related while preserving the basic pg_type and domain data. [verified-by-code] (`typcache-entry-and-lookup.md` — via `knowledge/idioms/typcache-entry-and-lookup.md`).



### temp_buffers
GUC sizing a backend's local buffer pool for temporary-table pages; `localbuf.c` derives a per-backend pin limit of `num_temp_buffers / 4` and rejects `SET temp_buffers` once local buffers have been allocated in the session. [verified-by-code] (via `knowledge/files/src/backend/storage/buffer/localbuf.c.md`).



### TerminateBackgroundWorker
The lifecycle call that sets a registered background worker's terminate flag (sending SIGTERM); the worker is then auto-unregistered once stopped. It is one cause for a worker not being restarted (alongside `bgw_restart_time = BGW_NEVER_RESTART` or exit code 0). [verified-by-code] (`bgworker.c` — via `knowledge/files/src/backend/postmaster/bgworker.c.md`).



### TerminateBufferIO
The bufmgr I/O-coordination routine that ends an in-progress buffer read/write, clears `BM_IO_IN_PROGRESS`, updates validity/dirty flags, and wakes backends blocked in `WaitIO`; it is the close-out partner of `StartSharedBufferIO`. [verified-by-code] (`bufmgr.c:7148` — via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### text_ops
The default B-tree operator class for `text`, which compares under the column's collation (locale-aware). Because collated comparison is not prefix-compatible with `LIKE` outside the C locale, a `text_ops` index cannot accelerate `LIKE` there — that is what `text_pattern_ops` exists for. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### text_pattern_ops
The B-tree operator class that compares `text` values strictly byte-by-byte, bypassing locale collation, so the index can serve `LIKE` and anchored POSIX-regex prefix matches even when the database is **not** in the C locale (the default `text_ops` index cannot). A column may therefore need two indexes — one with `text_pattern_ops` for pattern matches and one with the default opclass for `<`/`>`/`ORDER BY` — since a single index carries one opclass. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### text_to_cstring
Converts a `text` varlena Datum to a palloc'd NUL-terminated C string (un-toasting if needed); the inverse of `CStringGetTextDatum`, and a place to watch for missing length caps on attacker-supplied text. [verified-by-code] (via `knowledge/files/contrib/fuzzystrmatch/dmetaphone.c.md`).



### TID (ItemPointer)
A tuple identifier: the physical address of a tuple on disk, encoded as an
`ItemPointerData` of block number plus a 1-based line-pointer offset within that
page. A heap tuple's own location is its `t_self` TID, and indexes store TIDs as
the pointers from index keys to heap rows. [verified-by-code] (`htup.h:62` — via
`knowledge/files/src/include/access/htup.h.md`).



### TIDBitmap
An in-memory, potentially lossy set of heap TIDs produced by a bitmap index scan; pages that overflow the per-page budget are marked lossy (page number only), forcing the bitmap-heap-scan recheck to re-evaluate every tuple on them. [from-comment] (via `knowledge/files/src/backend/access/gin/ginget.c.md`).



### TidStore
The compact, shared-memory-capable data structure for storing a large set of
TIDs (item pointers) used by VACUUM to remember dead tuples — successor to the
old flat array, with radix-tree internals so it scales and can be shared by
parallel vacuum workers. Parallel index cleanup reads dead TIDs from a shared
`TidStore`. [verified-by-code] (via
`knowledge/files/src/backend/commands/vacuumparallel.c.md`).



### TidStoreCreateShared
Creates a `TidStore` backed by a DSA segment so parallel vacuum workers and the leader share one radix-tree of dead TIDs, replacing the old fixed-size dead-tuple array with a memory-bounded, shareable structure. [verified-by-code] (`tidstore.c` — via `knowledge/files/src/backend/access/common/tidstore.c.md`).



### TidStoreGetBlockOffsets
Extracts the sorted array of item offsets recorded for one heap block from a `TidStore`, the read side used by vacuum's second heap pass to know which line pointers on a page were collected as dead. [verified-by-code] (`tidstore.c` — via `knowledge/files/src/backend/access/common/tidstore.c.md`).



### TidStoreIsMember
Tests whether a given ItemPointer is present in a `TidStore`, the membership probe index vacuum uses to decide if an index entry's heap TID has been collected as dead and should be removed. [verified-by-code] (`tidstore.c` — via `knowledge/files/src/backend/access/common/tidstore.c.md`).



### TidStoreIsShared
The predicate testing whether a TidStore (VACUUM's dead-TID collection) lives in shared memory (a parallel vacuum) versus backend-local memory, selecting the shared vs local radix-tree code path. [verified-by-code] (via `knowledge/idioms/vacuum-tid-store.md`).



### TidStoreMemoryUsage
The accessor returning the current bytes consumed by a TidStore (the radix-tree
TID store VACUUM uses to remember dead tuples); the caller polls it against its
own `maintenance_work_mem` budget to decide when to stop the first heap pass.
[verified-by-code] (via `knowledge/idioms/vacuum-tid-store.md`).



### TidStoreSetBlockOffsets
The vacuum `TidStore` write path that records the dead item offsets for one heap
block, encoding them into a `BlocktableEntry` keyed by block number in the radix
tree. [verified-by-code] (via `knowledge/idioms/vacuum-tid-store.md`).



### TimeADT
The on-disk/in-memory representation of SQL `TIME` (time of day without zone)
— a 64-bit microsecond count since midnight — declared alongside `DateADT` and
`TimeTzADT`. The adt layer's date/time functions take and return these typed
integers rather than raw `int64`. [verified-by-code] (via
`knowledge/files/src/include/utils/date.h.md`).



### TIMELINE_HISTORY
A replication-protocol command (`TIMELINE_HISTORY tli`) in the walsender replication grammar that requests the timeline history file for a given timeline ID. [verified-by-code] (`repl_gram.y` — via `knowledge/files/src/backend/replication/repl_gram.y.md`).



### TimeLineID
A `uint32` identifying a WAL timeline; it is incremented at each archive recovery or standby promotion so that histories that diverge after a failover get distinct timelines (and distinct WAL segment / history-file names). [verified-by-code] (via `knowledge/files/src/include/access/xlogbackup.h.md`).



### TimestampTz
The storage type for `timestamp with time zone`: a signed 64-bit count of
microseconds from the Postgres epoch (2000-01-01), stored in UTC and rendered in
the session time zone on output. Conversion helpers like
`timestamptz_to_time_t(TimestampTz)` bridge it to Unix time.
[verified-by-code] (via `knowledge/files/src/include/utils/date.h.md`).



### timingsafe_bcmp
A constant-time memory comparison returning zero iff two equal-length buffers match, used so that comparisons of secrets (MACs, authentication tags, tokens) do not leak how many leading bytes matched via timing. It replaces `memcmp` on security-sensitive equality checks. [verified-by-code] (via `knowledge/files/src/port/timingsafe_bcmp.c.md`).



### TLS
Transport Layer Security — the encryption layer for client connections, negotiated after the `SSLRequest` packet. `be-secure.c` and its OpenSSL backend wrap the socket so subsequent protocol traffic is encrypted; certificate verification can also drive `cert` authentication. [verified-by-code] (via `knowledge/files/src/backend/libpq/be-secure.c.md`).



### TM_BeingModified
A `TM_Result` value meaning the target tuple is currently being updated/locked by another in-progress transaction; the caller takes a `LOCKTAG_TUPLE` heavyweight lock (for fairness) and then waits on the conflicting xact's xmax before retrying. [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### TM_Deleted
A `TM_Result` value returned by `HeapTupleSatisfiesUpdate`/`heap_update`/`heap_delete` meaning the target tuple was already deleted by a now-committed transaction; the caller (e.g. EvalPlanQual) must treat the row as gone. [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### TM_Updated
A `TM_Result` code returned by a table-AM delete/update/lock when the target row was concurrently updated; the caller (e.g. the executor's `ExecUpdate`) must follow the update chain or re-check under the new version. [verified-by-code] (`tableam.c:302-407` — via `knowledge/files/src/backend/access/table/tableam.c.md`).



### TOAST
The Oversized-Attribute Storage Technique — values too large for a heap page are compressed and/or split into chunks stored in a side TOAST relation, leaving an 18-byte pointer in the main tuple; a per-column storage strategy controls when it kicks in. [verified-by-code] (`toast_internals.c:1` — via `knowledge/files/src/backend/access/common/toast_internals.c.md`).



### TOAST (The Oversized-Attribute Storage Technique)
PostgreSQL's mechanism for values too large to fit inline in a heap tuple:
oversized attributes are compressed and/or moved out-of-line into an associated
TOAST table, leaving a small pointer in the row. Reads transparently
reconstruct the value via the detoasting path. [verified-by-code]
(`detoast.c:205` — via
`knowledge/files/src/backend/access/common/detoast.c.md`).



### toast_compression
The module implementing the pluggable TOAST compression methods — historic PGLZ and LZ4 — behind the per-column `STORAGE`/compression setting, providing the compress/decompress entry points used when a value is too large to store inline. The chosen method is recorded in the toast pointer so decompression knows which codec to use. [verified-by-code] (via `knowledge/files/src/backend/access/common/toast_compression.c.md`).



### toast_fetch_datum
Reassembles an out-of-line TOAST value: given a `varatt_external` pointer it opens the toast relation and index, builds a `SnapshotToast`, and runs an ordered index scan on `chunk_id`, `memcpy`-ing each chunk into a flat varlena. Called by `detoast_attr` for EXTERNAL data. [verified-by-code] (via `knowledge/files/src/backend/access/common/detoast.c.md`).



### toast_internals
`src/backend/access/common/toast_internals.c` — the low-level TOAST machinery shared by heap and other table AMs: chunking an oversized varlena into the TOAST relation (`toast_save_datum`), deleting toasted values (`toast_delete_datum`), fetching/decompressing them back, and the per-value compression dispatch. [verified-by-code] (via `knowledge/files/src/backend/access/common/toast_internals.c.md`).



### TOAST_MAX_CHUNK_SIZE
The maximum number of payload bytes stored per row in a TOAST table, chosen so four toast chunks plus headers fit one page. An out-of-line value is sliced into chunks of this size, numbered sequentially, and reassembled on detoast. [inferred] (`heaptoast.h:82` — via `knowledge/files/src/include/access/heaptoast.md`).



### toast_pointer
A `varatt_external` datum describing an out-of-line TOAST value (value id, external size, raw size, toast-relation OID); it is extracted from an on-disk attribute via `VARATT_EXTERNAL_GET_POINTER`, which copies through a `varattrib_1b_e *` to dodge old-GCC alignment assumptions. [verified-by-code] (`detoast.h:22` — via `knowledge/files/src/include/access/detoast.h.md`).



### toast_save_datum
Stores an out-of-line TOAST value: it allocates a fresh `chunk_id`, splits the datum into chunks written to the relation's TOAST table and index, and returns a `varatt_external` pointer. [verified-by-code] (`toast_internals.c:119-375` — via `knowledge/files/src/backend/access/common` toast docs).



### TOAST_TUPLE_THRESHOLD
The heap-tuple size above which the TOASTer kicks in to compress and/or move attributes out of line; it is derived from `TOAST_TUPLES_PER_PAGE = 4` (i.e. the largest body that lets 4 tuples share a page). The companion `TOAST_TUPLE_TARGET` must be ≤ `TOAST_TUPLE_THRESHOLD` (a larger target is meaningless). [verified-by-code] (`heaptoast.h` — via `knowledge/files/src/include/access/heaptoast.md`).



### TOC
Table Of Contents — in a `pg_dump` archive, the ordered list of dumpable objects (`TocEntry`s) with their dependencies, allowing `pg_restore` to select, reorder, and parallelize restoration. The directory and custom archive formats both serialize a TOC separate from the object data. [verified-by-code] (via `knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md`).



### tokenizedauthline
`TokenizedAuthLine` is the intermediate lexed form of one `pg_hba.conf` / `pg_ident.conf` line (fields split, continuations joined) before it is parsed into an `HbaLine`. [from-comment] (via `knowledge/subsystems/libpq-backend.md`).



### TopMemoryContext
The root of a backend's memory-context tree, living for the whole process
lifetime; it is effectively `malloc`. Almost nothing should allocate here
directly — doing so is a backend-lifetime leak — but it parents the long-lived
caches (`CacheMemoryContext`, etc.). [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### TopPortalContext
The long-lived parent memory context under which every portal's own context is
created; owned by `portalmem.c` together with the portal-name hash table.
[verified-by-code] (`portalmem.c:93` — via
`knowledge/subsystems/utils-mmgr.md`).



### TopTransactionContext
The memory context whose lifetime is the current top-level transaction; it is
reset/deleted at commit or abort, making it the natural home for state that must
survive across statements but not across the transaction (e.g. PL subtransaction
bookkeeping lists). [from-comment] (`memutils.h:52-67` — via
`knowledge/files/src/include/utils/memutils.h.md`).



### total_cost
The field of a `Path` holding the planner's estimate of the cost to return the entire result, in abstract page/CPU cost units. Together with `startup_cost` it is what `add_path` compares when pruning dominated paths. [inferred] (via `knowledge/idioms/cost-join-paths.md`).



### track_commit_timestamp
GUC enabling recording of each transaction's commit timestamp in the commit_ts SLRU (queryable via `pg_xact_commit_timestamp`); recorded in `pg_control`, with a precise point at which reads become safe after an off→on transition. [verified-by-code] (via `knowledge/files/src/backend/access/transam/commit_ts.c.md`).



### track_io_timing
GUC enabling per-operation I/O timing (built on `instr_time`) that feeds `pg_stat_statements`, `EXPLAIN (ANALYZE, BUFFERS)`, and the pgstat I/O view; when off, the pgstat I/O cells record counts but not accumulated time. [verified-by-code] (via `knowledge/files/src/backend/utils/activity/pgstat_io.c.md`).



### transaction_timeout
GUC aborting any transaction (idle or active) that runs longer than the limit — a stricter bound than `statement_timeout` or `idle_in_transaction_session_timeout` alone; one of the ms-valued timeout GUCs in `proc.h`. pg_dump sets it to 0. [verified-by-code] (via `knowledge/files/src/include/storage/proc.h.md`).



### transactiongroupupdatexidstatus
`TransactionGroupUpdateXidStatus` (`clog.c:449-662`) batches many backends' CLOG status updates through a CAS-queued leader/follower dance, so only the group leader takes the CLOG bank lock. [verified-by-code] (via `knowledge/idioms/clog-slru.md`).



### TransactionId
A 32-bit transaction identifier (XID) stamped into each tuple's xmin/xmax to drive MVCC visibility; XIDs are assigned lazily on first write and wrap around, so they are compared modulo-2^31 and frozen by vacuum to stay ahead of wraparound. [verified-by-code] (`varsup.c:299` — via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### TransactionId (xid)
A 32-bit transaction identifier stamped into each tuple's xmin/xmax. Special
values include `InvalidTransactionId` (0); the 32-bit space wraps around, so
PostgreSQL also carries a 64-bit `FullTransactionId` to reason about age
without ambiguity. [verified-by-code] (`transam.h:3-4` — via
`knowledge/files/src/include/access/transam.h.md`).



### TransactionIdCommitTree
The clog routine that atomically marks a top-level xid and all its committed subtransaction xids as committed in pg_xact; called from the commit path after the WAL commit record is durable. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



### TransactionIdDidAbort
Reports whether an xid is *recorded* aborted in CLOG. It is deliberately unusable on its own for visibility, because a backend that crashed while running leaves no abort record — abortedness is inferred by elimination (not in progress AND not committed). [from-comment] (via `knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### TransactionIdDidCommit
The transam routine that consults `pg_xact` (CLOG) to decide whether a given
xid committed. Visibility code must call `TransactionIdIsInProgress` (or
`XidInMVCCSnapshot`) *first*: `xact.c` records the commit in CLOG before
clearing `MyProc->xid`, so consulting CLOG too early could make a just-committed
xact look crashed. [from-comment] (`heapam_visibility.c:13-35` — via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### TransactionIdEquals
A transam.h macro (declared in `transam.h`) testing bit-pattern equality of two TransactionIds; it backs the SQL `xideq`/`xidneq` operators in `xid.c`. Equality is reflexive on the raw 32-bit value, not on epoch-aware logical identity, so it is used pervasively in subxact lookups (matching against the xidcache, PGPROC subxids, and topmost-xid checks) where bare-xid comparison is intended. [verified-by-code] (`xid.c.md` — via `knowledge/files/src/backend/utils/adt/xid.c.md`).



### TransactionIdFollows
The transam.h comparison that treats xids as circular: it returns true when the first xid is logically newer than the second, accounting for 32-bit wraparound. [verified-by-code] (via `knowledge/files/src/include/access/transam.h.md`).



### TransactionIdGetStatus
Reads a transaction's commit/abort status (and any commit-LSN/subcommitted bit)
from the CLOG SLRU, the authoritative visibility decision once an xid is no
longer in-progress. [verified-by-code] (via `knowledge/idioms/clog-slru.md`).



### TransactionIdIsCurrentTransactionId
Tests whether an XID belongs to the current transaction or one of its
subtransactions, by scanning the in-backend XID cache; a fast local check that
needs no shared-memory lock. [verified-by-code] (via
`knowledge/data-structures/snapshot-lifecycle.md`).



### TransactionIdIsInProgress
The check (scanning the PGPROC array) for whether an xid is still running.
Visibility code must call it before `TransactionIdDidCommit` (which reads
pg_xact); reversing the order can let a just-committed xact momentarily look
aborted — a documented race-ordering invariant. [from-comment]
(`heapam_visibility.c:13` — via `knowledge/subsystems/access-heap.md`).



### TransactionIdIsValid
A transam.h macro (declared in `transam.h`) that tests whether a TransactionId is not `InvalidTransactionId`. It is the standard guard across the heap and transaction code — gating hint-bit setting, prune-xid checks, and subxact-parent walks — and sits alongside related predicates `TransactionIdIsNormal`, `TransactionIdEquals`, and the FullTransactionId variant `FullTransactionIdIsValid`. [verified-by-code] (`transam.h.md` — via `knowledge/files/src/include/access/transam.h.md`).



### TransactionIdPrecedes
The 32-bit-wraparound-safe comparison declaring XID `a` "before" XID `b` using
modulo-2^31 arithmetic; the correct way to order transaction ids rather than a
plain integer `<`. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### TransactionIdSetTreeStatus
Atomically records the commit (or abort) status of a top transaction and all its
subtransactions in CLOG, ensuring a reader never sees a partially-committed
subtree. [verified-by-code] (via `knowledge/idioms/clog-slru.md`).



### TransactionIdToPage
The clog/subtrans SLRU address macro mapping a TransactionId to the SLRU page number that holds its status/parent entry (companion to the per-page offset macro). [verified-by-code] (via `knowledge/idioms/clog-slru.md`).



### TransactionState
The per-(sub)transaction state node forming the transaction stack — nesting
level, state machine value, resource owner, subxid — that the transaction
manager pushes/pops across BEGIN/SAVEPOINT/COMMIT. [verified-by-code] (via
`knowledge/idioms/subtransaction-stack.md`).



### TransactionTreeSetCommitTsData
Records the commit timestamp (and optional replication-origin node id) for a top transaction and all its committed subxids into the commit_ts SLRU, the write side of the `pg_xact_commit_timestamp` feature. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



### TransactionXmin
The backend's earliest XID still considered running for visibility — the lower
bound of its oldest live snapshot — published in `MyProc` to constrain the global
vacuum horizon. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### TransamVariables
The shared transaction-system state struct (formerly `ShmemVariableCache`)
holding `nextXid`, `oldestXid`, `latestCompletedXid`, and the OID counter — the
authoritative source for XID allocation and horizon decisions. [verified-by-code]
(via `knowledge/idioms/subxact-visibility-and-overflow.md`).



### transformExprRecurse
The recursive workhorse of parse analysis in `parse_expr.c` that lowers a raw grammar expression node to its analyzed `Expr` form — for example turning a `ParamRef` into a `Param`, or resolving a `ColumnRef` to a `Var`. [verified-by-code] (via `knowledge/idioms/node-types.md`).



### transformStmt
The parse-analysis dispatcher (`analyze.c`) that switches on `nodeTag(parseTree->stmt)` to route each raw statement to its `transform*` routine, producing a `Query` tree; the standard route for a feature is to have it return a `CMD_SELECT`/`CMD_INSERT` Query rather than hand-rolling a plan. [verified-by-code] (via `knowledge/subsystems/parser-and-rewrite.md`).



### TransInvalidationInfo
The per-(sub)transaction invalidation-bookkeeping struct: it carries the command message lists plus `my_level` and a `parent` pointer so subtransaction abort can discard exactly that level's queued invalidations, and `PriorCmdInvalidMsgs` holds messages already folded in by `CommandCounterIncrement`. [verified-by-code] (`inval.c:48` — via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### transInvalInfo
The per-transaction accumulator of pending shared-invalidation messages and relcache-flush requests built up as a backend modifies catalogs; at commit it is handed to `CommandEndInvalidationMessages`/sinval so other backends learn of the changes. Subtransactions stack their own sub-list onto it. [inferred] (`inval.c:1247` — via `knowledge/subsystems/utils-cache.md`).



### TransitionCaptureState
The small struct that, together with a tuplestore, captures OLD/NEW rows for
trigger transition tables during a data-modifying statement; the after-trigger
machinery threads it through so statement-level triggers can later read the
collected rows. [verified-by-code] (via
`knowledge/idioms/trigger-transition-tables.md`).



### triConsistent
The GIN opclass support function (support number 6) — the ternary form of `consistent` returning GIN_TRUE/GIN_FALSE/GIN_MAYBE from a `check[]` array — letting a scan short-circuit before every key's presence is known. [from-docs] (via `knowledge/docs-distilled/gin.md`).



### TriggerData
The context struct a C-language trigger function receives (via
`fcinfo->context`): it carries the event flag bits (BEFORE/AFTER, ROW/STATEMENT,
INSERT/UPDATE/DELETE), the `Relation`, the old/new `HeapTuple`s, and any
transition tables. The trigger reads it to learn what fired and returns the
(possibly modified) tuple. [from-comment] (via
`knowledge/docs-distilled/trigger-interface.md`).



### TruncateSUBTRANS
The routine (`subtrans.c`) that discards pg_subtrans SLRU pages older than the oldest xid any snapshot could still need (`oldestXact`), reclaiming subxact-parent-link storage after a checkpoint/xid-horizon advance. [verified-by-code] (via `knowledge/idioms/subxact-subtrans-slru.md`).



### try_relation_open
The lock-first-then-check variant of `relation_open`: it takes the lock, tests existence via `SearchSysCacheExists1(RELOID, ...)`, and on a miss releases the now-useless lock and returns NULL instead of erroring. It backs `try_table_open`. [verified-by-code] (via `knowledge/files/src/backend/access/common/relation.c.md`).



### try_table_open
The soft-failure table open: `try_relation_open` (lock-first, return NULL on a missing relation) plus `validate_relation_as_table`; returns NULL instead of erroring when the OID no longer names a table. [verified-by-code] (via `knowledge/files/src/backend/access/table/table.c.md`).



### TsmRoutine
The callback struct returned by a tablesample method's `tsm_handler` function (`tsmapi.h:55`), driving `TABLESAMPLE` block/row selection; the built-in methods are `SYSTEM` (block-level) and `BERNOULLI` (row-level). [verified-by-code] (`tsmapi.h:55` — via `knowledge/docs-distilled/tablesample-method.md`).



### tts_isnull
The companion null-flag array of a `TupleTableSlot`, parallel to `tts_values`: entry i is true when column i+1 of the current tuple is SQL NULL. The two arrays together are the slot's deformed-tuple cache. [inferred] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### tts_mcxt
The memory context owning a `TupleTableSlot` and the deform-produced `tts_values[]`/`tts_isnull[]` arrays; resetting it invalidates any pointers those arrays hold into detoasted or copied data. [verified-by-code] (via `knowledge/data-structures/tupletableslot.md`).



### tts_tid
The `TupleTableSlot` field holding the on-disk row identity (`ItemPointerData`); it is meaningful only on slots backed by a real heap row (buffer/heap slots), not virtual slots, and pairs with `tts_tableOid` to name the source row. [verified-by-code] (via `knowledge/data-structures/tupletableslot.md`).



### tts_values
The per-attribute `Datum` array of a `TupleTableSlot`; after `slot_getsomeattrs`/`slot_getallattrs` it holds the deformed column values for the slot's current tuple. Executor expression evaluation reads operands straight out of it. [inferred] (via `knowledge/files/src/backend/executor/execTuples.c.md`).



### tuple deforming
Turning an on-disk tuple into its in-memory `Datum` array (the null-bitmap checks and alignment math of `slot_deform_heap_tuple`); one of the two operations JIT accelerates (with expression evaluation), by generating straight-line code specific to a table's layout and the columns actually extracted. [verified-by-code] (via `knowledge/docs-distilled/jit-reason.md`).



### tuple_data_split
A `pageinspect` SQL function that splits a raw heap-tuple bytea into a per-attribute array given the tuple's `t_infomask`/`t_infomask2`/`t_bits`; the per-file doc flags it as the module's most dangerous function because it trusts caller-supplied infomask bytes against the raw data. [verified-by-code] (via `knowledge/files/contrib/pageinspect/heapfuncs.c.md`).



### TupleConstr
The optional constraint block hanging off a `TupleDesc`, carrying column defaults, generated-column expressions, CHECK constraints, and the not-null / has-generated flags for a relation's row type. [verified-by-code] (`tupdesc.c` — via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### TupleDesc
A tuple descriptor: the runtime description of a row shape — an array of
`Form_pg_attribute` entries (name, type, length, alignment, …) plus optional
constraint/default info — that tells code how to form and deform tuples. It is
reference-counted when cached against a relation. [from-comment] (via
`knowledge/files/src/backend/access/common/tupdesc.c.md`).



### TupleDescAttr
The accessor macro for tuple-descriptor attribute metadata: `TupleDescAttr(tupdesc, i)` returns the full `FormData_pg_attribute *` for column `i` (name, type OID, typmod, length, byval, alignment, storage, etc.). It is the required way to read attributes — code must not index the descriptor's packed `compact_attrs` array directly with the wide form. [verified-by-code] (`tupdesc.h` — via `knowledge/data-structures/tupledesc.md`).



### TupleDescFinalize
The finalization step called after a TupleDesc's attributes are populated (via `TupleDescInitEntry` etc.); it validates the descriptor and populates the compact-attribute arrays (`compact_attrs`). It is required before the descriptor is used — the compact-attrs state is undefined until Finalize runs. [verified-by-code] (`tupdesc.c` — via `knowledge/data-structures/tupledesc.md`).



### TupleDescInitEntry
Fills one attribute slot of a `TupleDesc` by looking up the `pg_type` row for a given type OID (name, length, alignment, etc.); the per-column initialiser used when building a descriptor programmatically. [verified-by-code] (`tupdesc.c:900` — via `knowledge/files/src/backend/access/common/tupdesc.c.md`).



### TupleHashTable
The simplehash-based hash table in `execGrouping.c` shared by hash aggregation, hashed SubPlan/IN, SetOp, and recursive-union dedup; constructed by `BuildTupleHashTable`. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### TupleQueueReader
The leader-side reader that pulls tuples out of a worker's shm_mq tuple queue
during a Gather/Gather Merge, deserializing `MinimalTuple`s into the leader's
slot. [verified-by-code] (via `knowledge/idioms/parallel-gather-merge.md`).



### tuplestore_puttupleslot
The tuplestore insertion call that stores the minimal-tuple copy of a `TupleTableSlot`'s current row; the standard way executor nodes (materialize, function scan, window) accumulate rows into a spillable tuplestore. [verified-by-code] (via `knowledge/files/src/backend/utils/sort/tuplestore.c.md`).



### Tuplestorestate
The opaque state object of the tuplestore — a read/write, optionally rescannable tuple buffer that lives in memory up to `work_mem` and then spills to disk; the Material node and SRFs in materialize mode stash their output in one so the parent can re-read or mark/restore. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### TupleTableSlot
The executor's universal tuple container, abstracting over how a tuple is
physically stored behind a `TupleTableSlotOps` vtable. Four built-in slot kinds
exist — Virtual, HeapTuple, MinimalTuple, and BufferHeapTuple — plus
extension-defined ones, letting every plan node pass tuples uniformly.
[verified-by-code] (via
`knowledge/files/src/include/executor/tuptable.h.md`).



### TupleTableSlotOps
The virtual-method table defining a tuple slot's behavior (virtual / heap /
minimal / buffer-heap), letting the executor handle tuples uniformly regardless
of their underlying storage form. [verified-by-code] (via
`knowledge/idioms/tableam-vtable-lifecycle.md`).



### two-phase commit (2PC)
The protocol behind `PREPARE TRANSACTION` / `COMMIT PREPARED`: a transaction's
state is persisted (in `pg_twophase/` and WAL) so it survives a restart and can
be committed or rolled back later by any backend, enabling external transaction
managers. `twophase.c` manages the GXACT state in shared memory. [from-comment]
(via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### two_phase
The logical-replication subscription/slot option that enables decoding of
prepared (two-phase commit) transactions at PREPARE time rather than only at
COMMIT PREPARED, so the changes reach the subscriber as a prepared transaction.
Interacts with slot creation and the apply worker's transaction handling.
[verified-by-code] (via
`knowledge/files/src/backend/replication/logical/worker.c.md`).



### twophase_rmgr
The static dispatch tables mapping each `TwoPhaseRmgrId` (lock manager, predicate locks, multixact, pgstat, ...) to its prepare/commit/abort/recover callbacks, so two-phase commit can persist and replay each subsystem's per-transaction state across a `PREPARE TRANSACTION`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/twophase_rmgr.c.md`).



### TwoPhaseShmemInit
The shared-memory initializer for the two-phase-commit (prepared-transaction) subsystem; paired with `TwoPhaseShmemSize`, it is registered as an `{size_fn, init_fn}` slot so the shmem bootstrap lays out the `GlobalTransaction` array at startup. [verified-by-code] (`twophase.c:196-199` — via `knowledge/files/src/backend/access/transam/twophase.c.md`).



### type_id
The type-OID field of a `TypeCacheEntry`, the key under which `lookup_type_cache` caches a type's resolved metadata (typlen / typbyval / typalign, comparison and hash operators with their `FmgrInfo`s, the tuple descriptor for composites, etc.). [verified-by-code] (via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### TypeCacheConstrCallback
The typcache invalidation callback fired on a pg_constraint change; it walks the threaded domain-with-constraints list to flush cached domain constraint information. [from-comment] (via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### TypeCacheEntry
The per-type cached bundle the typcache builds on demand — comparison/hash operators and procs, btree/hash opclass info, type length/byval/align, and composite tuple descriptors — so hot paths avoid repeated catalog lookups. [verified-by-code] (via `knowledge/files/src/include/utils/typcache.h.md`).



### TypeCacheHash
The process-local hash table (`hash_create("Type information cache", ...)`)
keyed by type OID that backs `lookup_type_cache`; its entries cache a type's
comparison/hash support, tuple descriptor, and domain-constraint data across
calls. [verified-by-code] (`typcache.c:205` — via
`knowledge/idioms/typcache-entry-and-lookup.md`).



### TypeCacheRelCallback
The relcache invalidation callback (registered via `CacheRegisterRelcacheCallback`) that keeps composite-type caches in sync with `ALTER TABLE`. Given a `relid`, it looks up `RelIdToTypeIdCacheHash` to invalidate the composite type whose `typrelid == relid`, also walking every domain entry (threaded via `firstDomainTypeEntry`/`nextDomain`) to reset operator flags for domains over composites; `relid == InvalidOid` sweeps all composites plus domain-over-composite entries. [verified-by-code] (`typcache.c.md` — via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### unicode_normalize
PostgreSQL's Unicode normalization routine (NFC/NFD/NFKC/NFKD), validated by `norm_test` against the Unicode Consortium's official normalization test vectors; underlies SQL `normalize()` and `IS NORMALIZED`. [verified-by-code] (via `knowledge/files/src/common/unicode/norm_test.c.md`).



### UnlockBufHdr
Releases the per-buffer header spinlock taken to read/modify a `BufferDesc`'s
state word; many state changes now use atomic ops, but the header lock still
guards compound updates. [verified-by-code] (via
`knowledge/idioms/spinlock-discipline.md`).



### UnlockBufHdrExt
The buffer-header unlock primitive that atomically releases `BM_LOCKED` while applying a set/clear of state bits and a refcount delta in one store; it deliberately cannot adjust the usage count, which needs separate capping. [verified-by-code] (via `knowledge/data-structures/bufferdesc-state.md`).



### UnlockRelationOid
Releases a heavyweight relation lock taken with `LockRelationOid`; normally locks are held to transaction end, so explicit unlock is reserved for narrow, well-understood cases (e.g. early release of a catalog lock). [verified-by-code] (via `knowledge/files/src/backend/access/common/relation.c.md`).



### UnlockReleaseBuffer
Convenience that releases a buffer's content lock and then unpins it in one call; the standard cleanup at the end of a read-modify loop over a page. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_gin.md`).



### UnpinBuffer
The bufmgr routine that drops one pin from a shared buffer, decrementing the backend-local ref count and the shared `BM_...` pin count; when the last pin is released it wakes any waiter blocked for exclusive access. [verified-by-code] (`bufmgr.c` — via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### UnregisterSnapshot
Drops a snapshot's registration with its resource owner; when the last
registration goes away the backend can lower its advertised xmin via
`SnapshotResetXmin`. [verified-by-code] (via
`knowledge/idioms/snapshot-active-stack-and-registered.md`).



### update_controlfile
The shared `src/common` routine that rewrites `global/pg_control`: it stamps the time, recomputes the CRC, copies the struct into a `PG_CONTROL_FILE_SIZE` zero-padded buffer, and does a single `write()` plus optional fsync. The backend caller is the checkpointer (holding `ControlFileLock`); frontend callers are `pg_controldata`/`pg_resetwal`/`pg_rewind`/`pg_upgrade`. [verified-by-code] (`controldata_utils.c:189-284` — via `knowledge/files/src/common/controldata_utils.c.md`).



### UpdateActiveSnapshotCommandId
Advances the command-id recorded in the active snapshot after a `CommandCounterIncrement`, so a query started later in the same transaction can see the effects of earlier commands within that transaction. [verified-by-code] (`snapmgr.c` — via `knowledge/files/src/backend/utils/time/snapmgr.c.md`).



### UpdateDomainConstraintRef
Refreshes a `DomainConstraintRef` held by an executor expression so that a cached domain-check expression picks up CHECK/NOT NULL constraint changes, keeping long-lived plans consistent with ALTER DOMAIN. [verified-by-code] (`typcache.c` — via `knowledge/files/src/backend/utils/cache/typcache.c.md`).



### UpgradeTask
The pg_upgrade task-framework object (opaque, `task.c`): built by `upgrade_task_create`, it batches per-database catalog queries to run against every database of the old/new cluster, replacing ad-hoc per-database connection loops. [verified-by-code] (`task.c:117` — via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md`).



### USE_ASSERT_CHECKING
The compile-time symbol enabled by a `--enable-cassert` / cassert build; it
turns on every `Assert()` plus extra invariant checks (node-tag checks, memory
sentinel bytes via `MEMORY_CONTEXT_CHECKING`, randomized free fills). Off in
production builds, so asserts must never have side effects. [verified-by-code]
(`nodes.h:173-183` — via
`knowledge/files/src/backend/nodes/value.c.md`).



### USE_INJECTION_POINTS
The build-time flag (enabled via `meson setup -Dinjection_points=true`) that activates the entire injection-point framework; when undefined, the `INJECTION_POINT*` macros become no-ops (`((void) name)`). It is meant to be off in production because an enabled production build allows arbitrary deferred `dlopen` plus symbol execution at first-hit attach, with the build gate as the sole defense. [verified-by-code] (`injection_point.h` — via `knowledge/files/src/include/utils/injection_point.h.md`).



### USE_LZ4
The build-time macro guarding optional LZ4 support across PostgreSQL. When undefined, LZ4 code paths are `#ifdef`-stubbed to `pg_fatal`/`ereport(ERROR, ERRCODE_FEATURE_NOT_SUPPORTED)` — covering TOAST compression (`toast_compression.c`, where `DEFAULT_TOAST_COMPRESSION` becomes `TOAST_LZ4_COMPRESSION` only if defined), pg_dump's `compress_lz4.c`, base backup, WAL `xloginsert.c`, and frontend astreamers. [verified-by-code] (`toast_compression.c` — via `knowledge/files/src/backend/access/common/toast_compression.c.md`).



### user_opts
The pg_upgrade `UserOpts` global capturing command-line-derived options (jobs, check mode, socket dir, etc.); one of the four driver-wide globals declared in `pg_upgrade.h`. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md`).



### usercontext
The helper pair (`GetUserIdAndSecContext`/`SetUserIdAndSecContext`,
`SwitchToUntrustedUser`/`RestoreUserContext`) that temporarily switches the
current user id and security context — e.g. so maintenance commands run index
expressions or triggers under the table owner rather than the invoking
superuser, closing a privilege-escalation hole. [verified-by-code] (via
`knowledge/files/src/include/utils/usercontext.h.md`).



### UserMapping
The catalog object (pg_user_mapping) binding a local role to remote credentials and options for a foreign server; postgres_fdw keys its per-backend connection cache solely on `UserMapping.umid`. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### UserOpts
The pg_upgrade struct (`user_opts` global) holding parsed command-line options such as `check`, `live_check`, jobs, and socket directory that steer the upgrade run. [verified-by-code] (via `knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md`).



### UtfToLocal
One of the two shared character-set conversion drivers in `conv.c` (with `LocalToUtf`); per-encoding glue functions under `conversion_procs/` call it with a radix tree to transcode from UTF-8 to a server-local encoding. [verified-by-code] (via `knowledge/files/src/backend/utils/mb/_conversion_procs.md`).



### UtilityTupleDescriptor
Returns the result `TupleDesc` for a utility statement that produces rows (e.g. `EXPLAIN`, `FETCH`, `SHOW`), letting callers describe the result before the statement executes. [verified-by-code] (via `knowledge/files/src/include/tcop/utility.h.md`).



### VacAttrStats
The per-column working struct passed to a type's ANALYZE typanalyze/compute_stats callbacks; it holds the sampled values, the target stats slots (`stakind`/`stavalues`), and the outputs (null fraction, avg width, n_distinct) later written to `pg_statistic`. [verified-by-code] (via `knowledge/files/src/backend/utils/adt/rangetypes_typanalyze.c.md`).



### vacuum
The maintenance operation that reclaims space from dead tuples, updates the
free-space and visibility maps, and advances `relfrozenxid` to hold off
transaction-id wraparound. Lazy `VACUUM` runs concurrently with normal access;
`VACUUM FULL` rewrites the table to compact it under an exclusive lock.
[from-comment] (via
`knowledge/files/src/backend/access/heap/vacuumlazy.c.md`).



### vacuum_cost_delay
The sleep duration applied when a VACUUM's `VacuumCostBalance` exceeds `vacuum_cost_limit`; default 0 (disabled) for manual VACUUM, while autovacuum uses `autovacuum_vacuum_cost_delay` (default 2 ms) out of the box. [from-README] (via `knowledge/docs-distilled/runtime-config-vacuum.md`).



### vacuum_cost_limit
The accumulated cost budget after which a cost-delayed VACUUM sleeps; `vacuum_delay_point` compares `VacuumCostBalance` against it and sleeps when exceeded (default 200, honoring the failsafe disable). [verified-by-code] (via `knowledge/files/src/backend/commands/vacuum.c.md`).



### vacuum_delay_point
The cost-based-delay checkpoint called inside VACUUM's scan loops: it reads `VacuumCostBalance` accumulated by the buffer manager and sleeps when it exceeds `vacuum_cost_limit` (honoring the failsafe). It must be called only while no buffer lock is held. [verified-by-code] (via `knowledge/files/src/backend/commands/vacuum.c.md`).



### vacuum_rel
The per-relation entry point inside `commands/vacuum.c` (`vacuum_rel`, line 2012) — opens the relation, runs sanity/permission checks, dispatches to the table AM via `table_relation_vacuum`, then recurses into the relation's TOAST table. The outer `vacuum()` loop calls it once per target relation. [verified-by-code] (via `knowledge/files/src/backend/commands/vacuum.c.md`).



### VacuumCostBalance
The accumulating cost counter the buffer manager increments on each VACUUM page hit/miss/dirty; when it exceeds `vacuum_cost_limit`, `vacuum_delay_point` sleeps for `vacuum_cost_delay`. Initialized among the VACUUM-costing globals. [verified-by-code] (via `knowledge/files/src/backend/commands/vacuum.c.md`).



### validate_cb
The callback slot a pluggable OAuth token-validator module fills in to check a presented bearer token; test modules like `fail_validator` supply one that raises `FATAL` immediately to exercise the failure path. [verified-by-code] (via `knowledge/files/src/test/modules/oauth_validator/fail_validator.c.md`).



### validateinputlsns
`ValidateInputLSNs` is pg_walinspect's strict range check, rejecting start / end LSN pairs that are reversed or point past the current insert position. [verified-by-code] (via `knowledge/subsystems/contrib-pg_walinspect.md`).



### ValuePerCall
One of the two set-returning-function (SRF) return modes (the other being Materialize), in which the function returns one row per call using the `FuncCallContext`/`SRF_*` machinery. Because a ValuePerCall SRF may not be run to completion (e.g. a LIMIT can stop it short), it MUST NOT hold non-memory resources such as file descriptors or locks between calls. [from-comment] (`funcapi.h` — via `knowledge/files/src/include/funcapi.h.md`).



### ValuesScan
The executor plan node (`nodeValuesscan.c`) that scans a `VALUES (...), (...)` clause, evaluating each row's List of Exprs into the result slot one row per call. Rows are compiled to ExprStates eagerly for small lists or lazily for large ones (with JIT triggered when `jit_above_cost` is exceeded), and the same node sits below ModifyTable to feed `INSERT ... VALUES`. [verified-by-code] (`nodeValuesscan.c` — via `knowledge/files/src/backend/executor/nodeValuesscan.c.md`).



### Var
The expression node representing a reference to a column: it carries the
range-table index (`varno`) and attribute number (`varattno`) identifying which
relation's which column, resolved during parse analysis. Plan-time rewriting
renumbers Vars (e.g. to `OUTER_VAR`/`INNER_VAR`) as columns flow up the plan
tree. [inferred] (via `knowledge/files/src/include/nodes/primnodes.h.md`).



### varatt_external
The 18-byte on-disk TOAST pointer struct stored inline in a row when a value is pushed out of line: it records the toast-table value OID, the compressed/raw sizes, and the toast relation's relid. `detoast_attr` follows it to reassemble the value. [inferred] (`varatt.h:32` — via `knowledge/files/src/include/varatt.h.md`).



### VARATT_IS_COMPRESSED
The varlena TOAST macro that tests whether an attribute value is stored compressed, so it must be detoasted/decompressed before use. [verified-by-code] (via `knowledge/files/src/backend/access/common/toast_internals.c.md`).



### VARATT_IS_EXTERNAL
The varlena macro that is true when a datum is a TOAST pointer stored out-of-line (external), as opposed to an inline (possibly compressed) or short-header value. [verified-by-code] (via `knowledge/files/src/include/varatt.h.md`).



### varattno
The `Var` field giving the column number within the referenced relation (1-based); `varattno = 0` denotes a whole-row Var that yields the entire tuple as a composite value. [verified-by-code] (via `knowledge/data-structures/var-const-nodes.md`).



### varchar_pattern_ops
The `varchar` counterpart of `text_pattern_ops`: a byte-by-byte B-tree operator class that makes `LIKE`/anchored-prefix matching index-usable on `varchar` columns in a non-C locale. [from-docs §11.10] (via `knowledge/docs-distilled/indexes-opclass.md`).



### VARDATA_ANY
The macro returning a pointer to a varlena's data payload while
transparently handling both the 1-byte (short) and 4-byte (long) header
layouts; pair with `VARSIZE_ANY_EXHDR` for the length. [verified-by-code]
(via `knowledge/subsystems/contrib-citext.md`).



### variable_conflict
The plpgsql GUC (`PGC_SUSET` enum `error|use_variable|use_column`, default `error`) resolving the ambiguity when a PL/pgSQL variable name matches a query column; superuser-only because changing it can silently alter query meaning, overridable per-function via `#variable_conflict`. [verified-by-code] (via `knowledge/files/src/pl/plpgsql/src/pl_handler.md`).



### varlena
The variable-length datum layout (a 4-byte length header followed by payload) used by text, bytea, arrays, and other non-fixed types; the header encodes whether the value is compressed, short (1-byte), or stored out of line (TOAST). [verified-by-code] (`c.h:775-779` — via `knowledge/idioms/memory-contexts.md`).



### varno
The `Var` field indexing into the query's range table to name which relation the variable comes from; special sentinel values (`INNER_VAR`, `OUTER_VAR`, `INDEX_VAR`) mark executor-context Vars that reference a child plan's output rather than a real rangetable entry. [verified-by-code] (via `knowledge/data-structures/var-const-nodes.md`).



### varnullingrels
The `Var` Bitmapset naming the outer joins whose nulling could turn this variable's value NULL; it lets the planner distinguish a column as seen above vs below an outer join so equivalence and qual placement stay correct. It is set semantically rather than copied and is ignored when comparing Vars for physical equality. [verified-by-code] (via `knowledge/data-structures/var-const-nodes.md`).



### VARSIZE
The varlena accessor macro returning the total stored size (including the length header) of a variable-length datum; the `VARSIZE_ANY_EXHDR` variant returns the payload size excluding the header. Code that builds or validates text/bytea results uses it to bound copies and enforce server-side size limits. [verified-by-code] (via `knowledge/files/contrib/pgcrypto/pgp-pgsql.md`).



### VARSIZE_ANY_EXHDR
The macro giving a varlena's payload length excluding its header, for either
the short or long header form; the companion of `VARDATA_ANY`.
[verified-by-code] (via `knowledge/subsystems/contrib-citext.md`).



### varstr_cmp
The backend's collation-aware variable-length string comparator (driving `text`/`varchar` ordering); it dispatches to `strcoll`/ICU under the given collation OID. citext is the cautionary case: its ordering operators call `varstr_cmp` (so sorting is collation-aware) while its equality functions deliberately use `strcmp` after downcasing. [verified-by-code] (`citext.c:56-58` — via `knowledge/files/contrib/citext/citext.md`).



### varstr_levenshtein
The core Levenshtein edit-distance routine carrying a `trusted` flag: the untrusted (SQL-reachable) path caps the insert/delete/substitute costs so a caller can't inflate them to blow up the inner loop, so any new caller must pass `trusted=false` unless it is a known-safe internal site. [from-comment] (via `knowledge/files/src/include/utils/varlena.md`).



### VARTAG_ONDISK
The `varattrib_1b_e` tag identifying an on-disk TOAST pointer datum, as opposed to an indirect (in-memory) or expanded external datum. [verified-by-code] (via `knowledge/files/src/include/varatt.h.md`).



### verify_heapam
`contrib/amcheck/verify_heapam.c` — amcheck's heap corruption checker exposed as `verify_heapam()`: it scans a heap relation page by page validating line pointers, tuple header sanity, xmin/xmax against CLOG/clog bounds, TOAST pointer consistency, and HOT-chain invariants, returning one row per detected problem. [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_heapam.md`).



### verify_nbtree
`contrib/amcheck/verify_nbtree.c` — amcheck's B-tree checker behind `bt_index_check()` / `bt_index_parent_check()`: it walks an nbtree validating per-page key ordering, sibling-link coherence, and (with `heapallindexed`) that every heap tuple is reachable through the index, optionally re-descending from the root (`bt_rootdescend`). [verified-by-code] (via `knowledge/files/contrib/amcheck/verify_nbtree.md`).



### virtualtransactionid
`VirtualTransactionId` (vxid) is a (backendId, localXid) pair assigned to every transaction immediately — before any real XID — so read-only transactions never consume permanent XID space. [from-docs] (via `knowledge/docs-distilled/transactions.md`).



### VirtualXID
A *virtual transaction id* (`VirtualTransactionId` = `procNumber + localTransactionId`) that names a backend's current transaction without burning a real `TransactionId`. Read-only transactions never assign a real xid, so locks and waits key on the VXID; `VirtualXactLockTableInsert` lets others `VirtualXactLock`-wait on a backend until it ends. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### visibility map (VM)
A two-bits-per-page relation fork (`VISIBILITYMAP_FORKNUM`) marking pages whose
tuples are all-visible (and optionally all-frozen) to every transaction. It lets
index-only scans skip heap fetches and lets `VACUUM` skip clean pages; the bits
are cleared whenever a page is modified. [from-comment] (via
`knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### VISIBILITYMAP_ALL_FROZEN
The visibility-map bit (0x02) asserting every tuple on a heap page is frozen, so VACUUM may skip the page entirely for xid-wraparound purposes; it implies all-visible as well. [verified-by-code] (via `knowledge/idioms/visibility-map-update.md`).



### VISIBILITYMAP_ALL_VISIBLE
The visibility-map bit meaning every tuple on the heap page is visible to all transactions; it enables index-only scans to skip the heap and lets vacuum skip the page. [verified-by-code] (via `knowledge/files/src/include/access/visibilitymapdefs.h.md`).



### visibilitymap_set
Sets a heap page's all-visible (and optionally all-frozen) bits in the visibility map; the caller is responsible for WAL-logging the underlying heap change that justified the bits. [verified-by-code] (`visibilitymap.c:255` — via `knowledge/files/src/backend/access/heap/visibilitymap.c.md`).



### vl_len_
The 4-byte varlena length header that begins every variable-length datum (`struct varlena`, and embedded in types like `cube` and `lquery`); it is set with `SET_VARSIZE` and read with `VARSIZE`, and the type's `typalign` governs how arrays of such varlenas are laid out. [verified-by-code] (`cubedata.h:18` — via `knowledge/files/contrib/cube/cubedata.h.md`).



### VM_ALL_VISIBLE
The visibility-map bit an index-only scan consults for each candidate heap page: set → the row is known all-visible and returned straight from the index; clear → the heap tuple must still be visited to test MVCC visibility, giving no win over a plain index scan. The runtime check is `VM_ALL_VISIBLE(scandesc->heapRelation, …)`. [verified-by-code `source/src/backend/executor/nodeIndexonlyscan.c:164` @c1702cb51363] (via `knowledge/docs-distilled/indexes-index-only-scans.md`).



### VXID
A virtual transaction id — the pair (backend proc number, local counter) that names a transaction before it has been assigned a real XID, so read-only transactions can be referenced (e.g. in locks and `pg_locks`) without consuming an XID. It becomes associated with a permanent XID only if and when the transaction first writes. [from-comment] (via `knowledge/files/src/backend/access/transam/README.md`).



### wait_event_info
The `pgstat`-encoded wait-event identifier passed to `WaitLatch` / `WaitEventSetWait`; while the backend blocks it becomes the `wait_event_type` / `wait_event` columns shown in `pg_stat_activity`. [verified-by-code] (`waiteventset.c:101` — via `knowledge/files/src/include/storage/waiteventset.h.md`).



### WaitBufHdrUnlocked
A buffer-manager spin loop (`bufmgr.c:7575`) that waits for a concurrent holder of the buffer header spinlock (`BM_LOCKED`) to release it, without itself acquiring the lock. It is the same spin loop as `LockBufHdr` minus the acquire, and is used inside CAS retry loops in `PinBuffer`, `MarkBufferDirty`, and similar paths that must re-read `desc->state` after a contended header lock. [verified-by-code] (`bufmgr.c.md` — via `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`).



### WaitEventSet
A reusable set of wait conditions (sockets, latches, postmaster-death) a
backend blocks on in one `epoll`/`kqueue`/`poll` call, multiplexing client I/O,
inter-process latches, and shutdown detection. Long-lived sets avoid rebuilding
the kernel structure each wait. [verified-by-code] (via
`knowledge/files/src/backend/storage/ipc/waiteventset.c.md`).



### WaitEventSetWait
The latch.c entry point that sleeps on a `WaitEventSet` (latch + sockets + postmaster-death) until an event fires or the timeout elapses; the waiter's `maybe_sleeping` flag lets a concurrent `SetLatch` know a wakeup is required. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/latch.c.md`).



### WaitForBackgroundWorkerStartup
Blocks until a dynamically registered background worker has started (or failed to), returning its PID; the standard way a launcher confirms a worker came up before relying on it. [verified-by-code] (via `knowledge/idioms/bgworker-and-parallel.md`).



### WaitForParallelWorkersToAttach
Blocks until each launched parallel worker has either attached to the DSM or
failed to start, so the leader can reliably detect missing workers before
relying on their participation. [verified-by-code] (via
`knowledge/idioms/parallel-worker-coordination.md`).



### WaitForParallelWorkersToFinish
Blocks the leader until every launched parallel worker has reported completion
(propagating any worker error via the error queue), the join point before
`DestroyParallelContext`. [verified-by-code] (via
`knowledge/idioms/bgworker-and-parallel.md`).



### WaitForProcSignalBarrier
Blocks until every backend has absorbed a previously-emitted `EmitProcSignalBarrier` generation, giving the caller a cluster-wide barrier that a global state change (e.g. flipping checksums on) has been observed everywhere before it proceeds. [verified-by-code] (via `knowledge/files/src/backend/postmaster/datachecksum_state.c.md`).



### WaitLatch
The convenience wrapper that waits on a single latch (plus optional timeout and
postmaster-death) by building a one-shot `WaitEventSet`. Latches are the
backend's edge-triggered "you have work / wake up" primitive, set with
`SetLatch` from another process or a signal handler. [verified-by-code]
(`waiteventset.c:88` — via `knowledge/subsystems/storage-ipc.md`).



### WaitLatchOrSocket
The latch.c convenience wrapper (`latch.c:222`) that builds a one-shot `WaitEventSet` over the latch, postmaster death, a timeout, and optionally a socket's readability/writability — the `WL_SOCKET_*` events are only available through this entry. [verified-by-code] (via `knowledge/files/src/backend/storage/ipc/latch.c.md`).



### WaitLSNType
The category of LSN a backend can wait for in `xlogwait.c` (e.g. replay vs flush); each type has its own pairing-heap of waiters keyed by target LSN. [verified-by-code] (`xlogwait.c:99` — via `knowledge/files/src/backend/access/transam/xlogwait.c.md`).



### WaitReadBuffers
The buffer-manager routine that completes a batch of asynchronous/streamed read
requests, waiting for the I/O to land before the caller uses the pages; part of
the read-stream prefetch path. [verified-by-code] (via
`knowledge/subsystems/storage-buffer.md`).



### WaitXLogInsertionsToFinish
Waits until every in-progress WAL insertion up to a target LSN has completed, by scanning the `NUM_XLOGINSERT_LOCKS` insertion locks; called before a flush so that no partially-copied record is ever flushed to disk. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### WAL (xlog)
The write-ahead log: every change is recorded as an XLOG record and flushed to
durable storage *before* the modified data pages are written back, which is
what makes crash recovery possible. `XLogInsertRecord` appends records on the
fast path; `StartupXLOG` replays them during recovery. [from-comment]
(`xlog.c:6-28` — via
`knowledge/files/src/backend/access/transam/xlog.c.md`).



### wal_consistency_checking
The GUC listing resource managers for which the server, during recovery, must
compare its replayed page image against the full-page image captured at insert
time — a developer/debugging aid that catches redo routines that don't exactly
reproduce the original page change. [verified-by-code] (via
`knowledge/files/src/backend/access/rmgrdesc/xlogdesc.c.md`).



### wal_level
The GUC controlling how much information is written to WAL (`minimal`, `replica`, `logical`), trading log volume against the features it enables — archiving/streaming need `replica`, logical decoding needs `logical`. Under `minimal`, certain operations (e.g. a permanent relation created in the same transaction) skip WAL and instead fsync the file at commit, tracked via `pendingSyncHash`. [verified-by-code] (via `knowledge/files/src/backend/catalog/storage.c.md`).



### wal_log_hints
GUC forcing hint-bit updates to be WAL-logged (via full-page images) so they are safe under replication/checksums; `XLogHintBitIsNeeded() = (wal_log_hints || DataChecksumsNeedWrite())`, and it is recorded in `pg_control`. [verified-by-code] (via `knowledge/files/src/include/access/xlog.h.md`).



### wal_segment_size
The size of a single WAL segment file (fixed at initdb); clients like pg_basebackup learn it via `SHOW wal_segment_size` (`RetrieveWalSegSize`), and trusting the server-reported value is a noted trust boundary. [verified-by-code] (via `knowledge/files/src/bin/pg_basebackup/streamutil.c.md`).



### wal_sync_method
GUC selecting the syscall used to flush WAL to disk (`fdatasync` default on Linux, plus `open_datasync`, `fsync`, etc.); pg_test_fsync measures each so operators can pick, and platform shims (win32fdatasync) back the choices. [verified-by-code] (via `knowledge/files/src/bin/pg_test_fsync/pg_test_fsync.c.md`).



### wal_writer_delay
GUC setting the WAL writer's sleep between flush rounds; async-commit transactions are guaranteed to reach disk within roughly `3 × wal_writer_delay`. Declared in `walwriter.h` with `wal_writer_flush_after`. [verified-by-code] (via `knowledge/files/src/backend/postmaster/walwriter.c.md`).



### WALBufMappingLock
The LWLock protecting the mapping of WAL buffer slots to LSNs (which in-memory buffer currently holds which WAL page); it guards *page allocation* into the WAL buffers, distinct from `WALWriteLock` which guards the write-out. [verified-by-code] (via `knowledge/idioms/wal-buffer-state.md`).



### WalRcv
The global pointer to the walreceiver's shared `WalRcvData` control struct; its `WalRcvState` field walks STOPPED → STARTING → CONNECTING → STREAMING as the receiver attaches to the primary. [verified-by-code] (via `knowledge/files/src/include/replication/walreceiver.h.md`).



### WalRcvData
The single shared-memory control struct for the walreceiver (`extern WalRcvData *WalRcv`), tracking receiver state, the received/written/flushed LSNs, and the primary conninfo; most fields are guarded by its spinlock `mutex`. [verified-by-code] (via `knowledge/files/src/include/replication/walreceiver.h.md`).



### walreceiver
The standby-side process that connects to a primary's walsender, receives the
streamed WAL, writes and flushes it locally, and reports flush/apply positions
back for synchronous replication. It runs `WalReceiverMain` and hands received
WAL to the startup process for replay. [from-comment] (via
`knowledge/files/src/backend/replication/walreceiver.c.md`).



### WalReceiverMain
The entry point of the walreceiver process: it connects to the primary, streams WAL, and runs the receive / flush / reply state machine under the startup process's direction. [verified-by-code] (via `knowledge/files/src/backend/replication/walreceiver.c.md`).



### WalSegSz
The configured WAL segment size in bytes (default 16 MB, fixed at initdb);
many tools must read it from pg_control before computing segment file names, a
known ordering hazard in pg_rewind. [verified-by-code] (via
`knowledge/files/src/bin/pg_rewind/pg_rewind.h.md`).



### walsender
The primary-side backend that streams WAL to a connected standby or
logical-replication client, speaking the replication sub-protocol over a normal
libpq connection. Each connected standby has its own walsender running
`WalSndLoop`; for logical replication it drives the decoding output plugin.
[from-comment] (via `knowledge/files/src/backend/replication/walsender.c.md`).



### WalSnd
One walsender's shared-memory slot (`WalSnd` in `walsender_private.h`), holding its state, sent/write/flush/apply LSNs, and latch; the array of them lives under `WalSndCtl`. [verified-by-code] (via `knowledge/files/src/include/replication/headers.md`).



### WalSndCtl
The shared-memory control struct for walsenders and synchronous replication; it holds the per-wait-mode `SyncRepQueue` arrays and the released-LSN watermarks, protected by `SyncRepLock`. [verified-by-code] (`syncrep.h:21-27` — via `knowledge/files/src/backend/replication/syncrep.c.md`).



### WalUsage
The instrumentation counter struct (`instrument.c`) tracking WAL records, full-page images, and bytes generated during execution (and optionally planning); reported by `EXPLAIN (WAL)` and aggregated by pg_stat_statements. [verified-by-code] (via `knowledge/files/contrib/pg_stat_statements/pg_stat_statements.c.md`).



### WALWriteLock
The LWLock serializing the write (and flush) of WAL buffers out to the WAL segment files; a backend needing WAL flushed either does the write under this lock or waits for whoever holds it. Ranks in the WAL/xlog tranche group. [verified-by-code] (`xlog.c` — via `knowledge/idioms/lwlock-rank-discipline.md`).



### WIDTH_THRESHOLD
The ANALYZE size cutoff (~1024 bytes) above which a sampled value is deemed too wide to store in statistics; such values are counted toward width but skipped for MCV/histogram, so a column of very wide values yields non-null counts with empty distributional stats. [verified-by-code] (via `knowledge/idioms/analyze-mcv-histogram-correlation.md`).



### WindowAgg
The executor node (`nodeWindowAgg.c`) that evaluates window functions over the ordered, partitioned frames produced by an upstream sort. [verified-by-code] (via `knowledge/subsystems/executor.md`).



### WindowFunc
The parse/plan node representing a window-function call (e.g. `rank() OVER w`), carrying the function OID, argument list, and a reference to the `WindowClause` that defines its partition/order frame. [verified-by-code] (`parse_func.c` — via `knowledge/files/src/backend/parser/parse_func.c.md`).



### wipe_mem
The memory-debug macro (in `utils/memdebug.h`) that clobbers freed allocations with byte `0x7F` under `CLOBBER_FREED_MEMORY`, catching use-after-free; the sentinel byte is `0x7E`. [from-comment] (via `knowledge/subsystems/utils-mmgr.md`).



### WL_EXIT_ON_PM_DEATH
The `WaitLatch` event flag that makes a latch wait terminate the process if
the postmaster dies — the standard way background loops avoid lingering as
orphans after a crash. [verified-by-code] (via
`knowledge/subsystems/contrib-postgres_fdw.md`).



### WL_LATCH_SET
A WaitEventSet / WaitLatch event bit requesting a wakeup when the process latch is set; wait loops commonly OR it with WL_EXIT_ON_PM_DEATH. [verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/condition_variable.c.md`).



### WL_POSTMASTER_DEATH
A `WaitEventSet` wakeup bit indicating the postmaster has died; backends include it (or the auto-exit variant) in every wait so they can shut down promptly when the parent is gone. [verified-by-code] (`waiteventset.c:20-33` — via `knowledge/files/src/backend/storage/ipc` latch/waiteventset docs).



### WordEntry
The per-lexeme header inside a `tsvector`'s on-disk representation, recording each lexeme's byte offset, length, and whether position data follows. [verified-by-code] (via `knowledge/files/src/include/tsearch/ts_type.h.md`).



### work_mem
The GUC bounding the memory a single query operation (sort, hash, hash-join build, bitmap) may use before spilling to temporary disk files; a complex query may use several multiples of it concurrently across operations. It is the chief knob trading RAM against spill I/O for executor working state. [inferred] (via `knowledge/files/contrib/pgcrypto/mbuf.md`).



### worker_spi
`src/test/modules/worker_spi/worker_spi.c` — the canonical background-worker example module: it both statically registers workers at `shared_preload_libraries` time and launches them dynamically, demonstrates `BackgroundWorkerInitializeConnection`, the `WaitLatch` main loop with `WL_EXIT_ON_PM_DEATH`, and the `SIGHUP`/`SIGTERM` handler skeleton plus an SPI query each cycle. The reference any new bgworker is cloned from. [verified-by-code] (via `knowledge/files/src/test/modules/worker_spi/worker_spi.c.md`).



### WorkTableScan
The executor node that scans the working table of a recursive CTE
(`WITH RECURSIVE`), feeding each iteration's new rows back into the recursive
term until no rows are produced. [verified-by-code] (via
`knowledge/subsystems/executor.md`).



### write_relcache_init_file
The routine that serializes the nailed and critical-index relcache entries to the `pg_internal.init` cache file (per-DB and shared `global/` copies), stamped with `RELCACHE_INIT_FILEMAGIC` (0x573266); `load_relcache_init_file` reads it back at backend startup. [verified-by-code] (via `knowledge/files/src/backend/utils/cache/relcache.c.md`).



### WriteInt
The pg_dump/pg_restore archiver's low-level serializer for a signed integer: it writes a variable byte-count encoding with an explicit sign byte (paired with `ReadInt`, which version-gates because pre-1.0 archives had no sign byte). It is one of the shared binary-IO primitives (`ReadInt`/`WriteInt`/`ReadStr`/`WriteStr`/`ReadOffset`/`WriteOffset`) used by every archive format to frame TOC entries and data blocks. [verified-by-code] (`pg_backup_archiver.c:2156-2212` — via `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md`).



### WriteRqst
The XLogwrtRqst request (Write and Flush LSNs) that WAL flush code fills in to ask XLogWrite how far the WAL must be written out and fsynced. [verified-by-code] (via `knowledge/idioms/wal-page-write-flush.md`).



### WriteStr
The pg_dump/pg_restore archiver serializer for a string: it emits a length-prefix integer (via `WriteInt`) followed by the payload bytes, with a length of -1 (read back by `ReadStr`) signifying NULL. It is used to frame the text fields of each TOC entry (tag, desc, defn, dropStmt, namespace, owner, dependency strings, etc.). [verified-by-code] (`pg_backup_archiver.c:2214-2251` — via `knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md`).



### XACT_EVENT_PRE_COMMIT
An XactEvent delivered to registered XactCallbacks just before a transaction commits; postgres_fdw, for example, uses it to flush and commit its remote transactions. [verified-by-code] (via `knowledge/files/contrib/postgres_fdw/connection.c.md`).



### xactCompletionCount
A `uint64` counter in `TransamVariables`, bumped under `ProcArrayLock` every time a transaction completes; `GetSnapshotData` remembers it so that if nothing has committed since the last snapshot it can reuse the previously computed snapshot, avoiding a full ProcArray scan. [verified-by-code] (via `knowledge/subsystems/storage-ipc.md`).



### XactCtl
The SlruCtl control object for the pg_xact (clog) SLRU; clog page reads/writes and the group-commit LSN array hang off XactCtl->shared. [verified-by-code] (via `knowledge/idioms/clog-slru.md`).



### xactgetcommittedinvalidationmessages
Called by `RecordTransactionCommit` to snapshot the pending shared-invalidation messages into the commit WAL record, so the commit is recorded *before* the SI messages are broadcast (`AtEOXact_Inval`). [verified-by-code] (via `knowledge/files/src/backend/utils/cache/inval.c.md`).



### XactLastRecEnd
The end-LSN of the current transaction's last WAL record; at commit it is what `XLogFlush` flushes to (under `synchronous_commit`) or what `XLogSetAsyncXactLSN` advertises to the walwriter for asynchronous commit. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XactLockTableWait
Blocks until a given transaction ends by taking a share lock on that
transaction's self-exclusive "transaction lock"; used to wait out a concurrent
updater (e.g. in tuple-lock and index-build conflict resolution).
[verified-by-code] (via `knowledge/files/src/backend/storage/lmgr/lmgr.c.md`).



### XactLogCommitRecord
The xact.c routine that assembles the WAL commit record — carrying subxact xids, dropped-relation and invalidation data, and the replication origin — for a committing transaction; its abort sibling is `XactLogAbortRecord`. [verified-by-code] (`xact.c:5870` — via `knowledge/files/src/backend/access/transam/xact.c.md`).



### XidCacheRemoveRunningXids
The procarray routine that removes a set of subtransaction xids from a backend's PGPROC subxid cache at subtransaction abort or cache overflow. [verified-by-code] (via `knowledge/files/src/include/storage/procarray.h.md`).



### XidCacheStatus
The per-backend PGPROC state (a count plus an overflowed flag) tracking how many cached subtransaction xids the backend holds and whether that cache has overflowed. [verified-by-code] (via `knowledge/idioms/subxact-xidcache-and-pgproc.md`).



### XidGenLock
The LWLock that serialises transaction-id assignment and protects the shared
`nextXid` / epoch counters in `ShmemVariableCache`. `GetNewTransactionId`
holds it while bumping the counter and advancing the CLOG/subtrans page
boundaries. [verified-by-code]
(via `knowledge/files/src/backend/access/transam/varsup.c.md`).



### XidInMVCCSnapshot
The visibility helper that decides whether a given XID counts as "in progress"
relative to an MVCC snapshot (checking it against the snapshot's xmin/xmax and
xip array) — the snapshot-based analog of `TransactionIdIsInProgress`.
[from-comment] (via
`knowledge/files/src/backend/access/heap/heapam_visibility.c.md`).



### xip
The snapshot's in-progress xid array — the set of transactions that were running when the snapshot was taken and are therefore invisible even though their xids fall between `xmin` and `xmax`. Together with `subxip` it is how `HeapTupleSatisfiesMVCC` decides in-flight-transaction visibility. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### xl_info
The one-byte `info` field of every WAL record header: its high 4 bits are rmgr-private opcode bits (which sub-operation) and its low 4 bits are the generic `XLR_*` flags (e.g. has-full-page-image), the field the rmgrdesc routines first switch on when decoding. [verified-by-code] (via `knowledge/architecture/wal.md`).



### xl_prev
The WAL record header field holding the LSN of the previous record — a backward link that lets recovery and tools verify contiguity and scan the log in reverse; it is filled in at insert time from the reserved position. [verified-by-code] (via `knowledge/architecture/wal.md`).



### xl_running_xacts
The WAL record (emitted by `LogStandbySnapshot`, normally from the bgwriter) that lists the currently in-progress XIDs, letting a hot-standby assemble its initial MVCC snapshot before it has seen a full transaction history. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### xlhp_cleanup_lock
`XLHP_CLEANUP_LOCK` is a prune-record flag (`heapam_xlog.h:300-342`) demanding the redo apply hold a cleanup (super-exclusive) lock; required when moving tuple data, but not for freeze-only or `LP_DEAD`→`LP_UNUSED`-only records. [from-comment] (via `knowledge/files/src/include/access/heapam_xlog.h.md`).



### XLOG_BLCKSZ
The WAL page (block) size, normally 8 kB, set at build time by the `--with-wal-blocksize` configure option. Each WAL segment file (normally 16 MB) is split into pages of this size; the WAL writer batches `npages * XLOG_BLCKSZ` bytes per `pg_pwrite`. [from-docs][verified-by-code] (`xlog.c` — via `knowledge/docs-distilled/wal-internals.md`).



### XLOG_BTREE_REUSE_PAGE
The nbtree WAL record emitted when a deleted, now-recyclable B-tree page is
about to be reused; it carries a `snapshotConflictHorizon` so standbys can
cancel conflicting queries before the page changes identity.
[verified-by-code] (via
`knowledge/files/src/backend/access/nbtree/nbtxlog.c.md`).



### xlog_checkpoint_redo
`XLOG_CHECKPOINT_REDO` is the WAL record marking the exact redo point of an online checkpoint, added so the checkpoint's start LSN is itself a replayable record. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLOG_FPI_FOR_HINT
A special WAL record emitted by `MarkBufferDirtyHint()` when it dirties an otherwise-clean page for a hint-bit-only write while data checksums or `wal_log_hints` are enabled. The full-page image it carries protects the hint-bit write against torn-page hazards; during recovery no WAL is written so such hint updates are simply skipped. [verified-by-code] (`xlog.c` — via `knowledge/architecture/wal.md`).



### XLOG_INCLUDE_ORIGIN
The XLogSetRecordFlags option that stamps the current replication origin onto a WAL record, so downstream origin filtering (used by logical replication to avoid loops) works. [verified-by-code] (via `knowledge/files/src/backend/replication/logical/message.c.md`).



### xlog_internal
`src/include/access/xlog_internal.h` — the private WAL header defining the physical log format: `XLogPageHeaderData` / `XLogLongPageHeaderData`, the `XLogRecPtr`↔segment/file-name macros (`XLByteToSeg`, `XLogFileName`), `XLOG_BLCKSZ`, and the `XLogRecord` on-disk struct. Included by WAL internals rather than general backend code. [verified-by-code] (via `knowledge/files/src/include/access/xlog_internal.h.md`).



### XLOG_PAGE_MAGIC
The magic number stamped in each WAL page header (`XLogPageHeaderData`); it is bumped whenever the on-disk WAL format changes so a server refuses to replay incompatible WAL. A new WAL record type that changes page layout requires bumping it. [inferred] (`xlog_internal.h:35` — via `knowledge/scenarios/add-new-wal-record.md`).



### XLOG_RUNNING_XACTS
A WAL record type (`0x10`, defined among the standby `xl_info` codes in `standbydefs.h`) carrying a periodic snapshot of the currently-running XIDs. A hot standby consumes these records to build a visibility snapshot for read queries during recovery. [verified-by-code] (`standbydefs.h` — via `knowledge/files/src/include/storage/standbydefs.h.md`).



### XLOG_SWITCH
The WAL record type that forces the current WAL segment to be closed and a new one started; emitting it requires acquiring all 8 WAL insertion locks via `WALInsertLockAcquireExclusive` to lock out every concurrent inserter (same as `XLOG_CHECKPOINT_REDO`). [verified-by-code] (`xlog.c` — via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### XLOG_XACT_ASSIGNMENT
A WAL record that batches the association of subtransaction XIDs with their top-level parent, so that a standby can reconstruct the same subxid→parent view its snapshots need. Backends buffer `unreportedXids[]` before emitting it. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xact.c.md`).



### xlogbackgroundflush
`XLogBackgroundFlush` is the WAL writer's opportunistic flush: it advances the on-disk flush point up to a page boundary without forcing a full `XLogFlush`, smoothing fsync cost. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### XLogBeginInsert
Begins assembling a new WAL record; the caller then registers buffers and
data and finally calls `XLogInsert` to finalize it. [verified-by-code] (via
`knowledge/subsystems/access-transam.md`).



### XLogCtl
The large shared-memory control struct for the WAL system, holding the insert/write/flush pointers, the WAL buffer cache bookkeeping, and the insertion-lock array. Nearly every xlog operation reads or advances a field in it under one of its locks. [inferred] (`xlog.c:403` — via `knowledge/files/src/backend/access/transam/xlog.c.md`).



### XLogFlush
Forces WAL up to a given LSN to be written and fsynced to durable storage;
the barrier a backend must cross before reporting a commit or evicting a
dirty buffer whose WAL isn't yet flushed (WAL-before-data).
[verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLogHintBitIsNeeded
The macro `(wal_log_hints || DataChecksumsNeedWrite())` deciding whether a hint-bit change must be WAL-logged (as a full-page image) to be crash/replica safe; the first hint-write on a page after a checkpoint therefore emits WAL when true. [verified-by-code] (via `knowledge/files/src/include/access/xlog.h.md`).



### XLogInitBufferForRedo
During redo, obtains a buffer for a referenced block and, when the WAL record is flagged `INIT_PAGE`, reinitialises the page rather than reading the old contents; used by AM redo handlers (e.g. BRIN) that fully overwrite a page. [verified-by-code] (`brin_xlog.c:71-115` — via `knowledge/files/src/backend/access/brin` docs).



### XLogInsert
Finalizes the WAL record begun by `XLogBeginInsert`: it assembles the record
from the registered buffers and data, copies it into the WAL buffers under
the insertion locks, and returns the record's end LSN. [verified-by-code]
(via `knowledge/subsystems/access-transam.md`).



### XLogInsertRecord
The low-level routine that copies a fully-assembled WAL record into the WAL insertion buffers under an insertion lock and returns the end LSN. `XLogInsert` is the public wrapper that builds the record from registered buffers/data and calls it. [inferred] (`xloginsert.c:522` — via `knowledge/subsystems/access-transam.md`).



### XLogNeedsFlush
The predicate testing whether a given LSN has yet to be flushed to durable WAL; used by hint-bit setting (skip the bit if the commit record is not on disk) and by bulk-read buffer rings (reject dirtying a page whose WAL is not yet flushed). [verified-by-code] (via `knowledge/subsystems/access-heap.md`).



### XLogReadBufferForRedo
The redo-side helper that locks and reads the buffer a WAL record targets
and reports whether the record still needs applying — handling
already-applied pages and restoring full-page images when present.
[verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLogReader
The reusable WAL-reading state machine (an `XLogReaderState`) that decodes the WAL byte stream into records independent of how the bytes are sourced; recovery, logical decoding, and `pg_walinspect` all instantiate one. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLogReaderState
The WAL-decoder state object that reads and validates records sequentially
from a pluggable page source; shared by crash/archive recovery, logical
decoding, and `pg_walinspect`. [verified-by-code] (via
`knowledge/subsystems/contrib-pg_walinspect.md`).



### XLogReadRecord
The `XLogReader` driver that returns the next decoded WAL record, calling the caller-supplied page-read callback to fetch bytes; it underlies redo, logical decoding, and `pg_walinspect`. [verified-by-code] (`xlogreader.c:391` — via `knowledge/files/src/backend/access/transam/xlogreader.c.md`).



### xlogrecdata
`XLogRecData` is the linked chain of buffer/data fragments that `xloginsert.c` assembles to describe one WAL record before `XLogInsert` copies it into the WAL buffers. [from-README] (via `knowledge/files/src/backend/access/transam/README.md`).



### XLogRecordAssemble
The routine (`xloginsert.c`) that walks the registered buffers and data chunks of a pending WAL record and serializes them into the `XLogRecData` chain (with block images and CRC) that `XLogInsertRecord` then copies into the WAL buffers. [verified-by-code] (via `knowledge/subsystems/access-transam.md`).



### XLogRecPtr
A 64-bit Log Sequence Number (LSN) naming a byte position in the WAL stream,
conventionally printed as `%X/%X`; ordering and durability decisions are
expressed as comparisons between these. [verified-by-code] (via
`knowledge/subsystems/access-transam.md`).



### XLogRegisterBuffer
Called while building a WAL record to associate a pinned buffer with a block-reference slot, so redo can locate the page and (with `REGBUF_STANDARD`) apply full-page-image logic. The buffer's changed bytes are attached separately with `XLogRegisterBufData`. [inferred] (`generic_xlog.c:299` — via `knowledge/scenarios/add-new-wal-record.md`).



### XLogRegisterData
Attaches a chunk of "main data" (not tied to any buffer) to the WAL record currently being assembled between `XLogBeginInsert` and `XLogInsert`. Redo reads it back with `XLogRecGetData`. [inferred] (`xloginsert.h:44` — via `knowledge/scenarios/add-new-wal-record.md`).



### XLogSetRecordFlags
Sets per-record flags on the WAL insertion currently being assembled (`xloginsert.c:464`) — e.g. `XLOG_MARK_UNIMPORTANT` (skip for synchronous-commit purposes) or `XLOG_INCLUDE_ORIGIN` — before the matching `XLogInsert`. [verified-by-code] (via `knowledge/files/src/backend/access/transam/xloginsert.c.md`).



### XLogWrite
The routine that writes filled WAL buffers out to the current segment file (and fsyncs per `wal_sync_method`), advancing the shared write pointer. `XLogFlush` calls it to guarantee a given LSN is durable before a commit returns. [inferred] (`xlog.c:2325` — via `knowledge/idioms/wal-page-write-flush.md`).



### xmax
The transaction id that deleted or locked a heap tuple (`HeapTupleHeader.t_xmax`); zero/invalid means the row is live. When `HEAP_XMAX_IS_MULTI` is set the field is a MultiXactId rather than a plain xid. A snapshot's `xmax` is the first xid not yet seen — everything `>= xmax` is treated as future/invisible. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### xmin
The transaction id that inserted a heap tuple, stored in `HeapTupleHeader.t_xmin`; MVCC visibility asks whether `xmin` committed relative to the scanning snapshot before a row is considered visible. A snapshot also carries an `xmin` horizon — the oldest xid still running — below which every transaction is known committed or aborted. [verified-by-code] (via `knowledge/data-structures/snapshot-lifecycle.md`).



### XML_PARSE_NOENT
The libxml2 parse option PostgreSQL sets (alongside `XML_PARSE_DTDATTR`) in `xml_parse` via `xmlCtxtReadDoc`; it requests substitution/expansion of entities. Because it would normally expand external entities too, PG instead blocks external resolution by installing `xmlPgEntityLoader` globally (which returns the empty string for every external entity), so only internally-defined entities actually expand. [verified-by-code] (`xml.c` — via `knowledge/files/src/backend/utils/adt/xml.c.md`).



### XML_PARSE_NONET
The conventional libxml2 flag for blocking network access during XML parsing — notably NOT set by PostgreSQL's `xml.c`. Instead, the XXE defense is implemented through a custom external-entity loader (`xmlPgEntityLoader`) that returns the empty string for every external entity, a uniform approach that also blocks `file://` reads where `XML_PARSE_NONET` would not; the corpus flags the omission as architecturally fragile should a future libxml2 change bypass the entity loader. [verified-by-code] (`xml.c` — via `knowledge/files/src/backend/utils/adt/xml.c.md`).



### yyscan_t
The opaque reentrant-scanner state handle produced by a flex scanner generated with `%option reentrant`; PG's core and PL/pgSQL scanners pass it explicitly instead of using flex globals, so multiple scans can be active. It is allocated by `yylex_init` and freed by `yylex_destroy`. [inferred] (`pgpa_ast.h:152` — via `knowledge/files/contrib/pg_plan_advice/pgpa_ast.h.md`).
