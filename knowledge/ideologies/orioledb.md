# orioledb — a whole storage engine that needed PostgreSQL itself patched (table-AM + custom rmgr + undo-log MVCC + COW checkpoints, no buffer manager)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `orioledb/orioledb` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-09 (see Sources footer).

## Domain & purpose

OrioleDB is "a cloud-native storage engine for PostgreSQL (a solution to
PostgreSQL's wicked problems)" (`README.md:1-2`) `[from-README]`. It is a
transactional table storage engine you select per-table with `CREATE TABLE ...
USING orioledb` (`README.md:end`), built on the table-access-method framework
"and other standard Postgres extension interfaces" (`README.md:18-22`). Its
pitch is to fix the four chronic complaints about heap+MVCC Postgres at once:
bloat and the need for VACUUM, transaction-id wraparound, buffer-mapping
contention on many-core servers, and a page-level WAL that is hard to replicate
actively-actively. Its claimed mechanisms: **UNDO-log MVCC** (old row versions
evict to an undo log, not the main store, so deletes reclaim space immediately
and VACUUM is unnecessary), **default 64-bit transaction ids** (no wraparound),
**no buffer mapping + lock-less in-memory page reading** (in-memory pages hold
direct links to their storage pages), **copy-on-write checkpoints** feeding a
**row-level WAL** that parallel-applies and is aimed at raft/multimaster
(`README.md:24-58`) `[from-README]`.

The reason it earns the longest entry in this corpus is the thing the README
states almost in passing: building it requires **a patched PostgreSQL fork**
(`github.com/orioledb/postgres`) checked out at an exact pinned commit, and the
build *refuses to compile against any other patchset* (`README.md:Build from
source`, the `.pgtags` pin + "Wrong orioledb patchset version" error)
`[from-README]`. Every other ideology in `knowledge/ideologies/` lives inside
core's sanctioned seams. OrioleDB is the case that proves where those seams run
out: to ship this engine, its authors had to *add new hooks to Postgres itself*.
It is simultaneously a contrib-style extension (`include/orioledb.h:9` carries
the `contrib/orioledb/...` IDENTIFICATION header) and a downstream core fork.

## How it hooks into PG

OrioleDB **must** be in `shared_preload_libraries` — `_PG_init` returns
immediately unless `process_shared_preload_libraries_in_progress`
(`src/orioledb.c:469-470`) `[verified-by-code]`, the table-AM handler hard-errors
with "orioledb must be loaded via shared_preload_libraries"
(`src/tableam/handler.c:1523` region / `src/orioledb.c:1523`)
`[verified-by-code]`, and on first init it creates its own on-disk directories
`orioledb_data/` and `orioledb_undo/` (`src/orioledb.c:472-474`,
`include/orioledb.h:107-108`).

The load-bearing fact is the **hook surface it installs**, because most of these
hooks *do not exist in core PostgreSQL* — they are added by the orioledb/postgres
patchset (`src/orioledb.c:1255-1270`) `[verified-by-code]`:

| Hook installed | Exists in core? | Role |
|---|---|---|
| `RegisterCustomRmgr(ORIOLEDB_RMGR_ID=129, &rmgr)` | yes (custom-rmgr API) | OrioleDB's own WAL resource manager (see below) |
| `CheckPoint_hook = o_perform_checkpoint` | **no — patchset** | run OrioleDB's copy-on-write checkpoint inside core's checkpoint |
| `after_checkpoint_cleanup_hook` | **no — patchset** | reclaim post-checkpoint undo/data files |
| `get_xidless_commit_lsn_hook` | **no — patchset** | commit-LSN for xid-less (64-bit-xid) transactions |
| `snapshot_hook` / `snapshot_register_hook` / `snapshot_deregister_hook` | **no — patchset** | drive undo-retention from snapshot lifecycle |
| `reset_xmin_hook` | **no — patchset** | undo-retain horizon maintenance |
| `RedoShutdownHook` / `CustomErrorCleanupHook` | **no — patchset** | recovery + error-path cleanup of engine state |
| `CacheRegisterUsercacheCallback` | **no — patchset** | invalidate OrioleDB's parallel catalog (`o_tables`) |
| `get_relation_info_hook` / `set_plain_rel_pathlist_hook` | yes (planner hooks) | planner integration for OrioleDB rels |
| `RegisterXactCallback(undo_xact_callback)` + `RegisterSubXactCallback` | yes | tie undo apply/discard to xact + subxact boundaries |

The `RmgrData rmgr` it registers (`src/orioledb.c:393-403`) `[verified-by-code]`
is a full custom resource manager — `.rm_redo = orioledb_redo`, `.rm_desc`,
`.rm_identify`, `.rm_decode = orioledb_decode` (logical decoding of OrioleDB's
*own* row-level WAL), `.rm_startup`/`.rm_cleanup` wired to OrioleDB's recovery
finish hook. Cross-ref `[[knowledge/architecture/wal]]` (custom rmgr is core's
sanctioned WAL-extension seam — OrioleDB uses it for an entire alternate WAL
stream, not one record type), `[[knowledge/subsystems/storage-buffer]]`,
`[[knowledge/architecture/access-methods]]`, `[[knowledge/architecture/mvcc]]`.

The table AM itself is a near-complete `TableAmRoutine`
(`src/tableam/handler.c:2471-2540`, `orioledb_tableam_handler` at `:2544`)
`[verified-by-code]`: `slot_callbacks`, `scan_begin`, `tuple_insert`,
`tuple_insert_with_arbiter`, `tuple_delete`, `tuple_update`,
`relation_set_new_filelocator`, `index_build_range_scan`, `relation_size`,
`relation_needs_toast_table`, etc. — unlike pg_duckdb's deliberately-stub AM,
OrioleDB genuinely implements the callbacks, but reroutes them into its own
B-tree/undo/checkpoint machinery rather than `heapam` + `smgr` + the buffer
manager.

## Where it diverges from core idioms

### 1. It bypasses the buffer manager and smgr entirely — its own page pool, segment files, and a relation "size" computed from B-tree leaf counts

Core tables live in `relfilenode` segment files mediated by `smgr` and cached in
the shared `BufferDesc` array with a buffer-mapping hash table. OrioleDB has
**neither**. In-memory pages are an OrioleDB page pool (`include/orioledb.h`
`main_buffers_count` / `min_pool_size` sizing in `_PG_init`,
`include/utils/page_pool.h`), pages are `ORIOLEDB_BLCKSZ = 8192` but compressed
in `ORIOLEDB_COMP_BLCKSZ = 512` units (`include/orioledb.h:122-126`), and data
lives in OrioleDB's own `orioledb_data/` tree of `ORIOLEDB_SEGMENT_SIZE = 1 GiB`
segments (`:107,126`). Because there is no `smgr` fork to `stat`,
`orioledb_calculate_relation_size` *synthesizes* the size by walking each index +
TOAST B-tree and multiplying `TREE_NUM_LEAF_PAGES(td) * ORIOLEDB_BLCKSZ`
(`src/tableam/handler.c:1274-1312`) `[verified-by-code]`. There is no in-buffer
mapping and (per README) in-memory page reads use direct memory links without
atomics — "lock-less page reading" (`README.md:39-46`) `[from-README]`. This is
the deepest divergence: the engine reuses Postgres' executor, planner, catalog,
and fmgr, but replaces the entire storage substrate beneath the table AM.
Cross-ref `[[knowledge/subsystems/storage-buffer]]` (the buffer manager + smgr
substrate it replaces), `[[knowledge/idioms/locking-overview]]`.

### 2. MVCC lives in an UNDO log (circular RAM buffer + `orioledb_undo/` files), so deletes free space immediately and there is no VACUUM

Heap MVCC keeps every tuple version inline and relies on VACUUM to reclaim dead
ones. OrioleDB evicts old versions into an **undo log** with a precise location
algebra (`include/transam/undo.h:17-55`) `[verified-by-code]`: a circular
in-RAM buffer (`lastUsedLocation`, `advanceReservedLocation`, a reserved vs
ready-for-reservation split) backstopped by spill files, with a chain of
monotone horizons —
`cleanedLocation <= minProcRetainLocation <= minProcTransactionRetainLocation <=
minProcReservedLocation <= lastUsedLocation <= advanceReservedLocation`. Snapshot
registration drives retention (the `snapshot_register_hook` /
`undo_snapshot_register_hook` patchset hook, `src/orioledb.c:1268-1269`), and
xact/subxact callbacks (`undo_xact_callback`, `undo_subxact_callback`, `:1256-1257`)
discard or apply undo at commit/abort. The README's claim — page-level undo
records let space be reclaimed "as soon as possible" and "dedicated VACUUMing of
tables is not needed" (`README.md:48-53`) `[from-README]` — is the user-visible
payoff. This is a wholesale replacement of `knowledge/architecture/mvcc`'s
core model, implemented above the table AM rather than inside heapam.
Cross-ref `[[knowledge/architecture/mvcc]]`, `[[knowledge/subsystems/access-heap]]`,
`[[knowledge/idioms/memory-contexts]]` (undo reservation is its own allocator
discipline, not palloc).

### 3. Its index is a primary-key B-tree, so TIDs are synthetic — ANALYZE samples against a fabricated `ItemPointer`

OrioleDB tables are index-organized: the row lives in a primary-key B-tree
(`include/btree/*`, `PrimaryIndexNumber`), not a heap addressed by
`(block,offset)` TIDs. So like hydra-columnar and zombodb, it must *fabricate*
ItemPointers to satisfy core APIs that assume heap TID semantics. In the
ANALYZE/acquire-sample path it builds a `fake_iptr` and hand-increments its
block/offset as it walks leaf pages, wrapping offset at `InvalidOffsetNumber`
(`src/tableam/handler.c:2008-2055`) `[verified-by-code]`, sampling over
`TREE_NUM_LEAF_PAGES` rather than physical heap blocks. The `ORelOids`
triple `(datoid, reloid, relnode)` (`include/orioledb.h:272-299`) is OrioleDB's
own relation identity, distinct from core's `RelFileLocator`. Cross-ref
`[[knowledge/ideologies/hydra-columnar]]`, `[[knowledge/ideologies/zombodb]]`,
`[[knowledge/ideologies/cstore_fdw]]` — the four "synthetic-TID over a non-heap
store" cases; OrioleDB is the one that also brings its own WAL + undo + checkpoint.

### 4. A second, parallel catalog (`o_tables` / `o_indices` / sys-trees) shadows pg_class

OrioleDB cannot store its per-relation metadata (B-tree shape, compression,
index descriptors) in heap catalogs it has replaced, so it keeps its **own
catalog** in system trees — `include/catalog/o_tables.h`,
`include/catalog/o_indices.h`, `include/catalog/o_sys_cache.h`,
`include/catalog/sys_trees.h` `[verified-by-code]` — versioned by
`ORIOLEDB_SYS_TREE_VERSION` (`include/orioledb.h:102`). Core `pg_class`/`pg_index`
rows still exist (the table AM needs them), but the authoritative storage
metadata lives in the shadow catalog, kept in sync via the
`CacheRegisterUsercacheCallback` invalidation hook (`src/orioledb.c:1259`). This
mirrors pg_duckdb's two-catalog problem but at the storage layer rather than the
execution layer. Cross-ref `[[knowledge/idioms/catalog-conventions]]`,
`[[knowledge/ideologies/pg_duckdb]]`.

### 5. A private, self-versioning on-disk format with one-way on-the-fly conversion — a parallel `pg_control`/catversion scheme

Core gates binary compatibility with `catversion.h` + `pg_control`. OrioleDB
maintains an entire **parallel version matrix** in `include/orioledb.h:62-104`
`[verified-by-code]`: `ORIOLEDB_BINARY_VERSION = 9` (hard incompatibility —
cluster refuses to start on mismatch, written into the checkpoint control file),
plus independently-bumped `ORIOLEDB_WAL_VERSION`, `ORIOLEDB_CHECKPOINT_CONTROL_VERSION`,
`ORIOLEDB_SYS_TREE_VERSION`, `ORIOLEDB_PAGE_VERSION`, `ORIOLEDB_COMPRESS_VERSION`,
each with a documented **one-way conversion rule**: a lower on-disk version is
converted seamlessly on first read; a *higher* version makes the cluster shut
down (or, for WAL during logical decoding, fail the decode but keep running).
This is a from-scratch reimplementation of the compatibility discipline core
spent decades on, because OrioleDB's data, WAL, and checkpoints are simply not
Postgres' formats. Cross-ref `[[knowledge/idioms/catalog-conventions]]`,
`[[knowledge/architecture/wal]]`.

### 6. Copy-on-write checkpoints + row-level WAL, run via patchset checkpoint hooks

Core's checkpoint flushes dirty shared buffers and fsyncs smgr forks. OrioleDB
substitutes **copy-on-write checkpoints** (`include/checkpoint/checkpoint.h`,
`o_perform_checkpoint` installed on the patchset `CheckPoint_hook`,
`src/orioledb.c:1260`) `[verified-by-code]` that produce a structurally
consistent snapshot at every instant and enable **row-level WAL** instead of
page-level WAL + full-page images (`README.md:54-58`) `[from-README]`. Row-level
WAL is what makes "parallel apply (done)" and the multimaster ambition plausible;
it is emitted and replayed through the custom rmgr (`orioledb_redo` /
`orioledb_decode`, `src/orioledb.c:397-401`). The price is the two patchset
hooks core does not expose — there is no in-core way to interpose a wholly
different checkpoint or WAL stream, which is precisely why OrioleDB is a fork.
Cross-ref `[[knowledge/architecture/wal]]`, `[[knowledge/architecture/wal]]`.

## Notable design decisions (cited)

- **`relocatable = true`** (`orioledb.control:5`) and `default_version = '1.8'`
  with `comment = 'OrioleDB -- the next generation transactional engine'`
  (`:1-4`) — the SQL-facing extension is relocatable; the *engine* is pinned to a
  patched server, not to a schema, so relocatability is cheap.
- **64-bit transaction ids by default** (`README.md:30-32`) `[from-README]` —
  the `include/transam/oxid.h` `OXid` type replaces 32-bit `TransactionId`,
  removing wraparound; this is invisible at the SQL surface but is why
  freeze/anti-wraparound VACUUM is absent.
- **ICU/C/POSIX collations only** (`README.md:Collations`) `[from-README]` —
  OrioleDB's B-tree key encoding can't use arbitrary libc collations, so the
  README instructs initializing the whole cluster (or database from `template0`)
  with `--locale=C/POSIX` or an ICU locale. A storage engine dictating cluster
  initdb flags is unusual for an "extension".
- **The build refuses a non-matching server** — `.pgtags` pins the exact
  patched-PG commit per major version and the makefile emits "Wrong orioledb
  patchset version: expected <hash>, got <hash>" otherwise (`README.md:Build`)
  `[from-README]`. This is a hard, code-enforced statement that it is not a
  drop-in extension.
- **Rewind is platform-gated** — `orioledb_enable_rewind_check_hook` refuses to
  enable rewind on Windows and on systems lacking `setsid()`
  (`src/orioledb.c:407-420+`) `[verified-by-code]`, because OrioleDB's rewind
  restarts the instance from within the extension.
- **An S3 subsystem ships in-tree** — `include/s3/{checkpoint,checksum,control,
  headers,queue,requests,worker}.h` `[verified-by-code]` with
  `ORIOLEDB_S3_PART_SIZE = 1 MiB` (`include/orioledb.h:128`): checkpoints can be
  offloaded to object storage, the literal "cloud-native" claim.
- **`ASAN_UNPOISON_MEMORY_REGION` shimmed** when no ASan header is present
  (`include/orioledb.h:35-46`) — the page pool hand-manages memory regions and is
  ASan-instrumented, a sign storage is `malloc`/region-based, not palloc-arena.

## Links into corpus

- `[[knowledge/architecture/access-methods]]` + `access-method-apis` skill — the
  near-complete `TableAmRoutine` (`src/tableam/handler.c:2471-2540`) that reroutes
  every callback into OrioleDB's B-tree/undo/checkpoint engine; contrast with
  pg_duckdb's stub AM and cstore_fdw's FDW-as-storage.
- `[[knowledge/subsystems/storage-buffer]]` (buffer manager + smgr)
  — the substrate OrioleDB *replaces*: its own page pool + segment files + no
  buffer mapping; `relation_size` synthesized from B-tree leaf counts.
- `[[knowledge/architecture/mvcc]]` — UNDO-log MVCC (`include/transam/undo.h`)
  and 64-bit xids supplant heap-inline versions + VACUUM + wraparound.
- `[[knowledge/architecture/wal]]` — custom rmgr 129 + row-level WAL +
  `orioledb_decode` logical decoding of a private WAL stream.
- `[[knowledge/architecture/wal]]` — copy-on-write checkpoints on
  the patchset `CheckPoint_hook`.
- `[[knowledge/idioms/catalog-conventions]]` — the shadow `o_tables`/`o_indices`
  catalog and the parallel version-matrix compatibility scheme.
- `[[knowledge/ideologies/hydra-columnar]]`, `[[knowledge/ideologies/zombodb]]`,
  `[[knowledge/ideologies/cstore_fdw]]`, `[[knowledge/ideologies/pg_duckdb]]` —
  the "abuse a pluggable PG API" family. OrioleDB is the maximal case: it not
  only fabricates synthetic TIDs over a non-heap store (like all four) but
  required *adding hooks to core* — the only ideology in the corpus that is a
  fork-plus-extension rather than an in-seam extension.
- `.claude/skills/extension-development/SKILL.md` — `shared_preload_libraries`
  hard requirement, custom rmgr registration, the many `*_hook` install points.
- `.claude/skills/access-method-apis/SKILL.md` — table-AM callback contract
  OrioleDB satisfies; `.claude/skills/wal-and-xlog/SKILL.md` — custom rmgr +
  redo function contract.

## Anthropology takeaway (for STATE.md / cross-corpus)

OrioleDB redraws the boundary the rest of `knowledge/ideologies/` maps. The other
nine "diverge from core" extensions answer *how far can you bend a pluggable API
before it breaks?* — index-AM (zombodb), table-AM (hydra-columnar, cstore_fdw),
FDW (wrappers, cstore_fdw), planner/executor (pg_duckdb, citus), PL (plv8 — see
queue), no-new-C (pgmq). OrioleDB answers the next question: *what if the API
isn't enough?* Its reply is to fork Postgres and add the missing seams
(`CheckPoint_hook`, `snapshot_hook`, `get_xidless_commit_lsn_hook`,
`after_checkpoint_cleanup_hook`, `reset_xmin_hook`), then ship the engine as an
"extension" against that fork. **Phase-D relevance:** the patchset hook list at
`src/orioledb.c:1255-1270` is a concrete enumeration of the extension points core
*lacks* for pluggable storage engines — a ready-made wishlist for any "make the
table-AM seam wide enough to host OrioleDB-class engines in unmodified core"
proposal (the recurring pgsql-hackers "pluggable storage isn't pluggable enough"
thread).

## Sources

Fetched 2026-06-09 (branch `main`):

- `https://api.github.com/repos/orioledb/orioledb/git/trees/main?recursive=1`
  @ 2026-06-09 → HTTP 200 (tree listing; used for header/dir discovery).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/README.md`
  @ 2026-06-09 → HTTP 200 (8627 bytes).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/orioledb.control`
  @ 2026-06-09 → HTTP 200 (5 lines).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/include/orioledb.h`
  @ 2026-06-09 → HTTP 200 (20292 bytes; version matrix, ORelOids, sizing macros).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/include/tableam/handler.h`
  @ 2026-06-09 → HTTP 200 (7254 bytes).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/src/tableam/handler.c`
  @ 2026-06-09 → HTTP 200 (77706 bytes; TableAmRoutine, calculate_relation_size,
  ANALYZE fake_iptr — deep-read of cited regions, remainder skimmed).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/src/orioledb.c`
  @ 2026-06-09 → HTTP 200 (56979 bytes; _PG_init, rmgr struct, hook installs).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/include/transam/undo.h`
  @ 2026-06-09 → HTTP 200 (18774 bytes; undo-location algebra).
- `https://raw.githubusercontent.com/orioledb/orioledb/main/include/checkpoint/checkpoint.h`
  @ 2026-06-09 → HTTP 200 (8584 bytes, skimmed).

All cites are `[verified-by-code]` against the fetched headers/`.c` (hook
installs, rmgr struct, table-AM routine, relation-size synthesis, ANALYZE
synthetic-TID, undo algebra, version matrix, control file) except the
end-user/performance narrative (UNDO eviction reclaiming space, lock-less reads,
no-VACUUM, 64-bit-xid wraparound elimination, row-level-WAL parallel apply,
collation restrictions, build-refusal), which is `[from-README]`. The undo
engine internals, page pool, checkpoint COW mechanics, S3 worker, and B-tree
implementation were skimmed at the header level, not deep-read; claims about
*those* rest on header declarations + README, tagged where they exceed a cite.
