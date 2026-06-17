# pg_bulkload — a direct-path loader that builds heap+index pages in private memory and `write(2)`s them past the buffer cache and WAL, re-implementing durability out-of-band

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `ossc-db/pg_bulkload` @ branch `master` (pg_bulkload 3.2). All
> `file:line` cites below point into THAT repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against the files fetched on 2026-06-16 (see Sources footer). Read
> alongside `[[knowledge/ideologies/cstore_fdw.md]]` and
> `[[knowledge/ideologies/hydra-columnar.md]]` — the corpus's other
> raw-page-IO / smgr-and-WAL-bypassing extensions.

## Domain & purpose

pg_bulkload is "a high speed data loading tool" that "load[s] data to a database
... bypassing PostgreSQL shared buffers" (`README.md:1-6`) `[from-README]`. Its
fast path (`WRITER=DIRECT`, the default — `lib/writer.c:48-50`
`[verified-by-code]`) formats incoming rows into full 8 KB heap pages in a
*private* backend buffer and writes those pages straight to the relation's data
files with `write(2)`, skipping `heap_insert`, the shared buffer pool, the
free-space map, and — for the bulk of the load — the WAL. It is, almost exactly,
the **inverse of the `COPY` contract**: where core `COPY` still routes every
tuple through the table AM, shared buffers, and WAL so that crash recovery and
replication just work, pg_bulkload trades all of that machinery for raw write
throughput and then re-implements crash safety *outside* WAL via a per-relation
`pg_loadstatus` (LSF) file plus a standalone `pg_bulkload` recovery binary that
zero-fills the half-written pages. It also carries ETL features (input
validation, transformation) (`README.md:8`) `[from-README]`, but the durability
bypass is why it belongs in this corpus.

## How it hooks into PG

pg_bulkload is **not** a background worker and installs **no** hooks. It is an
ordinary loadable module (`PG_MODULE_MAGIC`, `lib/pg_bulkload.c:45`) whose entire
backend surface is one SQL-callable SRF, `pg_bulkload(text[])`
(`PG_FUNCTION_INFO_V1(pg_bulkload)`, `lib/pg_bulkload.c:47-49`)
`[verified-by-code]`. The whole load runs synchronously *inside a normal
backend*, driven from that function:

- The `.control` is minimal — `relocatable = false`, `module_pathname =
  '$libdir/pg_bulkload'`, version templated as `BULKLOAD_VERSION`
  (`lib/pg_bulkload.control.in:3-5`) `[verified-by-code]`.
- `pg_bulkload()` requires `superuser()` (`lib/pg_bulkload.c:190-193`)
  `[verified-by-code]`, parses a control-file option array via
  `untransformRelOptions` (`:493`), and builds a **Reader** (parser/source
  pipeline) and a **Writer** (`ParseOptions`, `:476-527`) `[verified-by-code]`.
- The driver loop is hand-rolled: read a `HeapTuple`, `WriterInsert` it, reset
  the per-tuple context, repeat until `rd->limit` (`lib/pg_bulkload.c:266-289`)
  `[verified-by-code]`. STEP 3 then closes the writer, which flushes pages and
  merges indexes (`:293-307`).
- The frontend `pg_bulkload` command and the `PARALLEL`/`MULTI_PROCESS` mode
  drive the same SRF over libpq (`DirectWriterSendQuery` builds a
  `SELECT * FROM pgbulkload.pg_bulkload(ARRAY[...])`,
  `lib/writer_direct.c:468-481`) `[verified-by-code]`.

The Writer is a vtable (`init`/`insert`/`close`/`param`/`dumpParams`/`sendQuery`,
`include/writer.h:43-75`) with three concrete implementations —
`DirectLoader` (private buffers), `BufferedWriter` (shared buffers, the
core-faithful path), `ParallelWriter` (`include/pg_bulkload.h:41-46`,
`include/writer.h:79-84`) `[verified-by-code]`. Everything below concerns the
DIRECT writer, the divergent one.

Cross-ref `[[knowledge/idioms/fmgr]]`, `.claude/skills/fmgr-and-spi/SKILL.md`,
`.claude/skills/extension-development/SKILL.md`.

## Where it diverges from core idioms

### 1. Heap pages are built in private memory and `write(2)`-ed directly, never touching shared buffers

The DirectWriter `palloc`s a 1024-block private buffer
(`self->blocks = palloc(BLCKSZ * BLOCK_BUF_NUM)`, `BLOCK_BUF_NUM == 1024`,
`lib/writer_direct.c:104,158`) and treats it as a ring of heap pages
(`GetCurrentPage`, `:113-114`). `DirectWriterInsert` calls `PageInit` /
`PageAddItem` directly on those private pages, sets the tuple's `xmin`/`cmin` by
hand from a cached `xid`/`cid` (`:300-319`) `[verified-by-code]` — there is no
`heap_insert`, no `RelationGetBufferForTuple`, no buffer pin, no FSM consult.
When the ring fills, `flush_pages` `write(2)`s the blocks to a file descriptor it
opened itself via `BasicOpenFilePerm` on a path it computed from the relation's
`RelFileLocator`/`RelFileNode` with `relpath` (`open_data_file`, `:654-721`;
write loop `:626-637`) `[verified-by-code]`. This bypasses `smgr` /
`md.c` entirely — pg_bulkload re-derives the segment filename
(`%s.%u` for segno>0, mirroring `_mdfd_openmesg`, `:690-700`) and seeks itself.
It even open-codes data-checksum stamping (`PageSetChecksumInplace` per page when
`DataChecksumsEnabled()`, `:593-609`) `[verified-by-code]` — work `smgrextend`
would normally own. The target relation is held under `AccessExclusiveLock` for
the whole load (`table_open(... AccessExclusiveLock)`,
`lib/writer_direct.c:177-181`), which is what makes appending past the existing
EOF without buffer coordination safe.

Contrast with `[[knowledge/ideologies/cstore_fdw.md]]` and
`[[knowledge/ideologies/hydra-columnar.md]]`, which also do raw page IO — but
into *their own* file formats; pg_bulkload writes the **real core heap format**
so the rows are visible to ordinary `seqscan` afterward.

### 2. WAL is skipped for the data — exactly ONE page is logged, only to pin the XID

This is the sharp one. The bulk of the load emits **no WAL**. The only WAL record
the DIRECT path writes is a single `log_newpage` of the *first* block, and the
comment is explicit about why (`lib/writer_direct.c:513-553`) `[verified-by-code]`:

> "Log the first page that pg_bulkload adds to WAL to ensure the current XID will
> be recorded in xlog. ... if the first page WAL entry were not recorded,
> PostgreSQL would not remember the XID being used for this loading. This may
> cause an inconsistent database state after recovery." (`:513-537`)

So it `log_newpage(... exist_cnt, loader->blocks)` then `XLogFlush(recptr)` once,
guarded by `create_cnt == 0 && !RELATION_IS_LOCAL(...) && relpersistence !=
UNLOGGED` (`:538-553`) `[verified-by-code]`. Every subsequent page is written
with bare `write(2)` and `pg_fsync` (`close_data_file`, `:728-741`) and never
reaches the log. This means a DIRECT-loaded relation is **not crash-safe by
WAL** and **not streamed to physical replicas** for those pages — the loader has
deliberately stepped outside the redo contract. (Index builds make the parallel
choice: `SpoolerOpen(..., use_wal=false, ...)`, `lib/writer_direct.c:186`, and
the B-tree builder then gates WAL on `self->use_wal && XLogIsNeeded()`,
`lib/pg_btree.c:503-511`) `[verified-by-code]`.

### 3. Crash safety is re-implemented OUTSIDE WAL: a `pg_loadstatus` file + a standalone `pg_bulkload` recovery binary

Because WAL can't undo the unlogged pages, pg_bulkload ships its own recovery
subsystem. At init it writes a `LoadStatus` record to
`$PGDATA/pg_bulkload/<dbOid>.<relid>.loadstatus`
(`BULKLOAD_LSF_PATH`, `include/pg_loadstatus.h:31-41`) recording the relation,
its `RelFileLocator`, `exist_cnt` (blocks present before the load) and
`create_cnt` (blocks pg_bulkload appended) (`include/pg_loadstatus.h:45-59`)
`[verified-by-code]`. The file is fsync'd up front, and an *existing* LSF for the
same table is a hard error — "recovery process haven't been executed after
failing load" (`DirectWriterInit`, `lib/writer_direct.c:214-238`)
`[verified-by-code]`. As pages flush, `UpdateLSF` rewrites `create_cnt` and
fsyncs the LSF *before* the data write (`:612-613,749-767`) `[verified-by-code]`;
on clean close `UnlinkLSF` deletes it (`:769-780`).

Recovery is a **separate frontend binary** (`bin/recovery.c`), not a backend redo
routine. On a crash it scans `$PGDATA/pg_bulkload/` for `*.loadstatus`
(`GetLSFList`, `bin/recovery.c:257-300`), checks the cluster did not shut down
cleanly (`GetDBClusterState` reads `pg_control`, `:319-351`), and for each LSF
overwrites the appended block range `[exist_cnt, exist_cnt+create_cnt)` with
**blank pages** — `ClearLoadedPage` zero-fills the data file
(`bin/recovery.c:211-212, 396-468`) `[verified-by-code]`. This is the precise
inverse of core's WAL-*replay* recovery: instead of redoing logged changes
forward, pg_bulkload's tool *erases* the unlogged pages backward to the
pre-load EOF, using its own out-of-band log file as the source of truth.
Cross-ref `.claude/skills/wal-and-xlog/SKILL.md`,
`[[knowledge/idioms/crash-recovery-startup.md]]`,
`[[knowledge/subsystems/access-transam.md]]`.

### 4. Indexes are rebuilt by direct page merge, not `index_insert` per tuple

DirectWriter does not call `aminsert`/`index_insert` for each row. It spools
index tuples into a `tuplesort` (`SpoolerInsert`, called from
`DirectWriterInsert`, `lib/writer_direct.c:322`) and at close performs a
**sort + merge build** of new B-tree files. `_bt_mergebuild`
(`lib/pg_btree.c:468-562`) flushes the existing index buffers
(`FlushRelationBuffers` under `AccessExclusiveLock`, `:524-525`), reads the
pre-existing leaf stream (`BTReaderInit`, `:528`), assigns a fresh relfilenode
(`RelationSetNewRelfilenode`, `:542`), and then either fast-path-loads the sorted
spool (`_bt_load`, `:555`) or merges the two sorted streams into freshly written
leaf pages (`_bt_mergeload`, `:567`+, which on PG≥17 drives
`smgr_bulk_start_rel` / `smgr_bulk_finish`, `:585,796`) `[verified-by-code]`.
This is core's `nbtsort` "build the tree bottom-up" strategy repurposed to *merge
into an already-populated index*, which the core API does not expose. Cross-ref
`.claude/skills/access-method-apis/SKILL.md`,
`[[knowledge/subsystems/access-nbtree.md]]`,
`[[knowledge/idioms/relfilenumber-rewrite.md]]`.

### 5. It vendors core's `nbtsort.c` internals — one copy per PG major version

To get at those bottom-up build routines, `lib/pg_btree.c` `#include`s a
**version-pinned copy of core's `nbtsort.c`** — a ladder of seventeen
`#include "nbtree/nbtsort-NN.c"` arms from `nbtsort-8.3.c` through
`nbtsort-18.c`, selected by `PG_VERSION_NUM` (`lib/pg_btree.c:48-92`)
`[verified-by-code]`, plus a shared `nbtsort-common.c` for PG≥14
(`:90-92`). `#error unsupported PostgreSQL version` brackets both ends
(`:48-49, 86-87`). This is a textbook **ABI/source-coupling smell**: the
extension carries private copies of `static` backend internals because the
public AM surface doesn't let an extension merge into an index, so every new PG
major requires a new vendored `nbtsort-NN.c`. Compare cstore_fdw's version churn
problem `[[knowledge/ideologies/cstore_fdw.md]]`.

## Notable design decisions (cited)

- **Toasting is done by hand before page placement.** `DirectWriterInsert` calls
  `heap_toast_insert_or_update` when `t_len > TOAST_TUPLE_THRESHOLD`
  (`lib/writer_direct.c:257-263`) `[verified-by-code]` — the loader owns the
  TOAST decision the heap AM would normally make.
- **Tuple headers are stamped manually.** It clears `HEAP_XACT_MASK` /
  `HEAP2_XACT_MASK`, sets `HEAP_XMAX_INVALID`, and writes `xmin`/`cmin`/`xmax`
  directly from the cached load XID (`:305-319`) `[verified-by-code]` — no
  `heap_prepare_insert`.
- **heap-AM only.** On PG≥12 it rejects any relation whose `relam !=
  HEAP_TABLE_AM_OID` (`VerifyTarget`, `lib/pg_bulkload.c:425-430`)
  `[verified-by-code]` — the direct page format is the *core heap* format, so a
  custom table AM is unsupported.
- **TRUNCATE is run as real DDL.** With `TRUNCATE=YES` it builds a
  `TruncateStmt` and calls `ExecuteTruncate` + `CommandCounterIncrement`
  (`TruncateTable`, `lib/pg_bulkload.c:436-454`) `[verified-by-code]` — this is
  what lets the load be safely unlogged on a relation created/truncated in the
  same xact.
- **The LSF directory is auto-created.** `ValidateLSFDirectory` mkdirs
  `$PGDATA/pg_bulkload` (mode 0700) if missing (`lib/writer_direct.c:785-807`)
  `[verified-by-code]`.
- **`PageSetTLI` is redefined to clobber the checksum field** on PG≥9.3
  (`lib/writer_direct.c:74-77`) `[verified-by-code]` — a compatibility shim
  papering over the pd_tli→pd_checksum page-header change.

## Links into corpus

- `[[knowledge/ideologies/cstore_fdw.md]]` — sibling raw-page-IO extension that
  also bypasses smgr/buffers, but writes its *own* columnar format and shares the
  per-PG-version source-coupling pain.
- `[[knowledge/ideologies/hydra-columnar.md]]` — another WAL/buffer-bypass
  storage extension; contrast its durability story with pg_bulkload's LSF tool.
- `[[knowledge/ideologies/pg_repack.md]]` / `[[knowledge/ideologies/pg_squeeze.md]]`
  — also rewrite heap+index files out-of-band; useful neighbors on "rebuild a
  relation around the planner."
- `[[knowledge/idioms/crash-recovery-startup.md]]` — the WAL-replay recovery that
  pg_bulkload's `bin/recovery.c` deliberately stands *outside* of.
- `[[knowledge/idioms/relfilenumber-rewrite.md]]` — `RelationSetNewRelfilenode`
  for the rebuilt index files.
- `[[knowledge/subsystems/access-nbtree.md]]`,
  `[[knowledge/subsystems/access-heap.md]]`,
  `[[knowledge/subsystems/storage-buffer.md]]` — the three subsystems the DIRECT
  writer routes *around*.
- `.claude/skills/wal-and-xlog/SKILL.md`,
  `.claude/skills/access-method-apis/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`.

## Anthropology takeaway

pg_bulkload is the corpus's sharpest worked example of **"bypass the WAL/buffer
contract for bulk-load speed, then re-implement durability out-of-band."** Core
PostgreSQL's central bargain is that *every* mutation goes through shared buffers
and WAL, so that exactly one mechanism — redo replay from the log — restores
consistency after any crash. pg_bulkload breaks that bargain on purpose: it
builds heap pages in private memory, `write(2)`s them past `smgr`, logs only a
single page (and that only to keep the XID honest in the log,
`lib/writer_direct.c:513-537`), and rebuilds indexes by direct page-merge. Having
left the redo contract, it must bring its own recovery: a fsync-ordered
`pg_loadstatus` file records the appended block range, and a *separate frontend
binary* (`bin/recovery.c`) zero-fills that range on crash — WAL-replay's exact
inverse, undo-by-erasure driven by an out-of-band log. The tell-tale cost of
living outside the public AM surface is the seventeen vendored `nbtsort-NN.c`
copies (`lib/pg_btree.c:48-92`): when the abstraction you need (merge into an
index, append unlogged to a heap) isn't exported, you copy core internals and pay
the per-major-version ABI tax forever. For a planner/reviewer this is the canonical
case to weigh against any "skip WAL for speed" proposal: the speed is real, but
durability, physical replication, and PITR for the loaded pages are *not* free —
they have to be rebuilt by hand, and the rebuild lives in a fragile,
version-coupled corner of the extension.

## Sources

Fetched 2026-06-16 from `https://raw.githubusercontent.com/ossc-db/pg_bulkload/master/<path>`
(all via authenticated `curl`):

- `README.md` @ 2026-06-16 → HTTP 200 (1302 bytes; read for purpose / buffer-bypass thesis).
- `lib/pg_bulkload.control.in` @ 2026-06-16 → HTTP 200 (197 bytes; control template).
- `include/pg_bulkload.h` @ 2026-06-16 → HTTP 200 (1900 bytes; pipeline diagram, Writer enum).
- `include/writer.h` @ 2026-06-16 → HTTP 200 (2862 bytes; Writer vtable + factory decls).
- `lib/pg_bulkload.c` @ 2026-06-16 → HTTP 200 (17032 bytes; deep-read — SRF entry, driver loop, VerifyTarget, TruncateTable, ParseOptions).
- `lib/writer.c` @ 2026-06-16 → HTTP 200 (2143 bytes; writer dispatch, DIRECT default).
- `lib/writer_direct.c` @ 2026-06-16 → HTTP 200 (21691 bytes; deep-read — THE core divergence: private page buffer, manual header stamping, log_newpage-once WAL decision, flush/write loop, LSF lifecycle).
- `lib/pg_btree.c` @ 2026-06-16 → HTTP 200 (33459 bytes; read merge-build path, use_wal gate, vendored nbtsort ladder).
- `lib/reader.c` @ 2026-06-16 → HTTP 200 (36893 bytes; skimmed top for parser/reader pipeline context).
- `include/pg_loadstatus.h` @ 2026-06-16 → HTTP 200 (1349 bytes; LoadStatus union, LSF path macro). *(supplementary fetch, not in original manifest)*
- `include/pg_btree.h` @ 2026-06-16 → HTTP 200 (1073 bytes; Spooler struct incl. use_wal flag). *(supplementary)*
- `bin/recovery.c` @ 2026-06-16 → HTTP 200 (29134 bytes; read recovery driver, GetLSFList, GetDBClusterState, ClearLoadedPage zero-fill). *(supplementary — the crash-safety story)*
- `lib/recovery.c` @ 2026-06-16 → HTTP 404 (recovery lives in `bin/recovery.c`, substituted above).

All cites are `[verified-by-code]` against the fetched files except the
high-throughput / buffer-bypass *motivation* and the ETL feature set, which are
`[from-README]`. The behavioral claim that unlogged DIRECT pages are absent from
physical replication / PITR is `[inferred]` from the single-`log_newpage` WAL
decision (`lib/writer_direct.c:538-553`) — no streaming-replica test was run.
