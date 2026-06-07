# cstore_fdw — a columnar storage engine smuggled through the FDW API (before table-AM existed)

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `citusdata/cstore_fdw` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> the files fetched on 2026-06-07 (see Sources footer).

## Domain & purpose

cstore_fdw is an ORC-inspired **columnar store** for PostgreSQL: it lays each
column out separately on disk in stripes/blocks, compresses value streams, and
keeps per-block min/max "skip indexes" so a scan reads only the columns and row
blocks a query touches (`README.md:53-74`, `:279-289`) `[from-README]`. Its
historical importance is the *mechanism*, not the format: cstore_fdw shipped
years before PostgreSQL had a pluggable table access method (v12, 2019), so it
built a full local storage engine **on top of the foreign-data-wrapper API** —
an API designed for reaching *out* to remote/external data, here bent into
managing local files inside `$PGDATA`. The repo's own top-of-README banner
records the ending: columnar storage "is now part of the Citus extension, which
uses the table access method API to give a much more native experience [and]
supports streaming replication, archival, rollback, and simplifies pg_upgrade"
(`README.md:1-3`) — i.e. the table-AM successor gained exactly the things the
FDW-based design could not have. cstore_fdw is the cleanest worked example of
the question: *how far can you push the FDW API toward being a storage engine,
and where does it structurally break?* It supports PostgreSQL 9.3–12
(`README.md:113-114`) and is now archived/superseded.

## How it hooks into PG

cstore_fdw requires `shared_preload_libraries = 'cstore_fdw'`
(`README.md:120-123`) `[from-README]` — mandatory, because it installs a
`ProcessUtility_hook` that must be live before the first backend statement
(see `extension-development` skill §"lazy vs preload"). The SQL install script
wires up an unusually *broad* surface for a "wrapper" (`cstore_fdw--1.7.sql`):

| Object created | Role |
|---|---|
| `cstore_fdw_handler() RETURNS fdw_handler` + `CREATE FOREIGN DATA WRAPPER` | the FDW entry point (`cstore_fdw--1.7.sql:6-18`) |
| `cstore_ddl_event_end_trigger()` on `ddl_command_end` | **provisions storage** after `CREATE SERVER` / `CREATE FOREIGN TABLE` (`:20-27`) |
| `cstore_drop_trigger()` on `SQL_DROP` (plpgsql) → `cstore_clean_table_resources(oid)` | **reclaims storage** on `DROP` (`:34-59`) |
| `cstore_table_size(regclass)` | UDF introspection of on-disk size (`:29-32`) |

`_PG_init` chains a single hook (`cstore_fdw.c:194-199`)
`[verified-by-code]`:

```c
PreviousProcessUtilityHook = (ProcessUtility_hook != NULL) ?
                             ProcessUtility_hook : standard_ProcessUtility;
ProcessUtility_hook = CStoreProcessUtility;
```

and the FDW handler (`cstore_fdw.c:1237-1265`) fills a `FdwRoutine` with the
full scan + modify callback set: `GetForeignRelSize`/`GetForeignPaths`/
`GetForeignPlan`, `BeginForeignScan`/`IterateForeignScan`/`EndForeignScan`,
`AnalyzeForeignTable`, and the write path `PlanForeignModify`/
`BeginForeignModify`/`ExecForeignInsert`/`EndForeignModify` (+ the v11
`BeginForeignInsert`/`EndForeignInsert` COPY entry points, +
`IsForeignScanParallelSafe` on ≥ 9.6). Cross-ref `[[knowledge/subsystems/foreign]]`,
`[[knowledge/subsystems/tcop]]` (which owns the `ProcessUtility` path).

## Where it diverges from core idioms

### 1. The FDW is a *storage engine*, not a wrapper — storage lives in `$PGDATA` raw files, bypassing smgr / bufmgr / WAL entirely

A normal FDW owns no storage: it translates scans into requests against a
remote source. cstore_fdw instead writes its own on-disk format with plain
stdio through PostgreSQL's virtual-FD wrapper — `AllocateFile(filename, "w")`
for a fresh data file, `"r+"` to append, and a separate `.footer` file opened
`PG_BINARY_W` (`cstore_writer.c:100`, `:114`, `:387`), with bytes pushed by raw
`fwrite` inside `WriteToFile` (`cstore_writer.c:932-943`). There is **no
`SMgrRelation`, no buffer manager, no `relfilenode`, and no WAL record anywhere
in the write path.** This is the load-bearing divergence and the source of
every limitation the README's successor banner lists: because nothing is
WAL-logged, cstore tables have **no crash recovery, no physical/logical
replication, and no PITR/archival** — the data files simply are not part of the
durability story core manages for heap relations. Cross-ref
`[[knowledge/architecture/wal]]`, `[[knowledge/subsystems/storage-buffer]]`,
`[[knowledge/architecture/access-methods]]` (the table-AM API that *is* the
right home for this, which cstore_fdw predates — see `access-method-apis`
skill).

### 2. Event triggers stand in for the storage lifecycle hooks the FDW API never provided

A foreign table has no storage, so core never calls an extension to *create* or
*destroy* backing files on `CREATE`/`DROP`. cstore_fdw manufactures that
lifecycle out of **DDL event triggers** — the single most distinctive design
move in the extension:

- **Provisioning** on `ddl_command_end`: `cstore_ddl_event_end_trigger`
  inspects the parse tree; on `CreateForeignServerStmt` for the cstore FDW it
  `CreateCStoreDatabaseDirectory(MyDatabaseId)`, and on `CreateForeignTableStmt`
  it opens the just-created relation `AccessExclusiveLock` and calls
  `InitializeCStoreTableFile` to lay down an empty data file + valid footer
  (`cstore_fdw.c:218-271`, `:934-948`) `[verified-by-code]`. The comment at
  `:256-262` candidly explains *why* an event trigger and not a cleaner hook:
  "We have no chance to hook into server creation to create data directory for
  it during database creation time" — the FDW API offers no such seam.
- **Reclamation** on `SQL_DROP`: a plpgsql `cstore_drop_trigger` walks
  `pg_event_trigger_dropped_objects()` and calls
  `cstore_clean_table_resources(objid)` for each dropped table/foreign table
  (`cstore_fdw--1.7.sql:39-59`). The actual unlink is
  `DeleteCStoreTableFiles` → bare `unlink()` on both the data file and the
  `.footer`, warning (not erroring) on failure (`cstore_fdw.c:899-925`).

The changelog shows how much of the extension's bug history is *this* seam
leaking: "Removed table files when a schema, extension or database is dropped"
(1.6), "Removed table data when cstore_fdw table is indirectly dropped" (1.5),
"No such file or directory warning when attempting to drop database" (1.6.1)
(`README.md:341-356`). Reconstructing DROP-cascade semantics from event
triggers is exactly the kind of thing core's storage manager gets for free.
Cross-ref `[[knowledge/idioms/error-handling]]` (the WARNING-not-ERROR choice
on a failed unlink).

### 3. `ProcessUtility_hook` pre-intercepts `COPY` to redirect it into the columnar writer

Because the relation has no heap, core's `COPY ... FROM` would fail with
"cannot copy to foreign table". cstore_fdw's utility hook detects a `CopyStmt`
naming a cstore table (`CopyCStoreTableStatement`) and diverts it to
`CStoreProcessCopyCommand` → `CopyIntoCStoreTable`, which reuses core's COPY
parser to read rows and feeds each into `CStoreWriteRow`
(`cstore_fdw.c:307-315`, `:533-572`) `[verified-by-code]`. The hook similarly
special-cases `DROP`, `TRUNCATE`, and `ALTER TABLE` on cstore tables
(`DroppedCStoreFilenameList`, `TruncateCStoreTables`,
`CStoreProcessAlterTableCommand` at `:777`, `:877`, `:718`). This is the
ProcessUtility-hook-as-DDL-rewriter idiom turned into a storage-engine control
plane. Cross-ref `[[knowledge/subsystems/tcop]]`.

### 4. No MVCC, no row-level locking: append-only at `ShareUpdateExclusiveLock`, writes serialized per table

cstore_fdw has no per-tuple visibility and no `DELETE`/`UPDATE`/single-row
`INSERT` (`README.md:157-158`) `[from-README]`. Concurrency is enforced purely
by a **table-level lock**: both the COPY path and the
`INSERT INTO ... SELECT` path open the relation
`ShareUpdateExclusiveLock` — "to allow concurrent reads, but block concurrent
writes" (`cstore_fdw.c:561-564`, `:2344`) `[verified-by-code]`. So the whole
MVCC apparatus (xmin/xmax, snapshots, HOT, tuple locks) that a heap table — or
a proper table AM — would provide is replaced by one coarse writer lock. Each
write operation appends new stripes to the file and rewrites the footer; there
is no in-place mutation. Cross-ref `[[knowledge/architecture/mvcc]]`,
`[[knowledge/idioms/locking-overview]]`. (Contrast the table-AM `TM_Result`
MVCC-outcome contract in the `access-method-apis` skill — the entire surface
cstore_fdw does without.)

### 5. `ExecForeignInsert` still detoasts through the heap tuple machinery

Even though storage is columnar and toast tables don't exist for it,
`CStoreExecForeignInsert` materializes the slot to a `HeapTuple`, checks
`HeapTupleHasExternal`, and `toast_flatten_tuple`s any external attributes
*itself* before writing the row (`cstore_fdw.c:2363-2388`)
`[verified-by-code]`. It has to flatten toast pointers eagerly because once the
source heap row is gone there is no toast relation behind the columnar file to
dereference them later — a concrete instance of "we get none of heap's
satellite machinery, so we inline what we need at write time."

### 6. Metadata serialized via external protobuf-c, not PG's own on-disk/node formats

Table and stripe metadata (the footer) is serialized with **protobuf-c**
(`cstore.proto` + `cstore_metadata_serialization.c`), making `protobuf-c-devel`
a hard build dependency (`README.md:80-92`) `[from-README]`. Core PG serializes
its own structures with `nodeToString`/`outfuncs` or fixed on-disk page
layouts; reaching for an external IDL/codec for an on-disk catalog-like
structure is a clean divergence from in-tree idioms (and a portability/version
tax — the footer carries its own `CSTORE_MAGIC_NUMBER "citus_cstore"` +
major/minor version, `cstore_fdw.h:48-51`). Block value streams are compressed
with core's `pglz_compress`/`pglz_decompress` (`cstore_compression.c:82`,
`:146-161`) — so compression reuses a core primitive, but the metadata
container does not.

### 7. The columnar format is reimplemented from scratch in the header's struct zoo

`cstore_fdw.h` defines a complete ORC-like type hierarchy with no core
analogue: `TableFooter` → `StripeMetadata`, `StripeFooter`, `StripeBuffers` →
`ColumnBuffers` → `ColumnBlockBuffers`/`ColumnBlockData`, plus the skip-index
types `StripeSkipList` / `ColumnBlockSkipNode` carrying `hasMinMax` +
`minimumValue`/`maximumValue` per block (`cstore_fdw.h:127-251`)
`[verified-by-code]`. The skip node's min/max is what lets a scan drop whole
row blocks whose range contradicts the `WHERE` clause (`README.md:279-289`) —
a private, file-format-level analogue of BRIN's min/max summarization, but
implemented entirely outside the index-AM machinery. Defaults: 150 000 rows per
stripe, 10 000 rows per block (`cstore_fdw.h:34-35`).

## Notable design decisions (cited)

- **Default storage under `$PGDATA/cstore_fdw`.** If the `filename` option is
  omitted, files land in a managed directory inside the data dir
  (`README.md:127-133`); `CreateCStoreDatabaseDirectory`/
  `RemoveCStoreDatabaseDirectory` manage per-database subdirectories keyed by
  `MyDatabaseId` (`cstore_fdw.c:1078`, `:1162`). A user-supplied absolute
  `filename` is allowed, which is why COPY is gated by
  `CheckSuperuserPrivilegesForCopy` — "Only superuser can copy from or to local
  file" (`cstore_fdw.c:555-556`).
- **Citus-awareness baked into the FDW.** The header hardcodes
  `pg_dist_partition` column numbers (`cstore_fdw.h:61-69`) and the utility
  hook checks `DistributedTable`/`DistributedWorkerCopy` to defer COPY to Citus
  when the cstore table is also distributed (`cstore_fdw.c:1008`, `:1056`) — a
  sibling-extension coupling. Cross-ref `[[knowledge/ideologies/citus]]`.
- **`relocatable = true`, `superuser` default.** The control file is otherwise
  unremarkable (`cstore_fdw.control:1-5`); the privilege gating that matters is
  done in C at COPY time, not via `trusted`/`schema` in the control file.
- **`IsForeignScanParallelSafe` returns true but doesn't parallelize.** The
  callback (added for the 1.7 "make foreign scan parallel safe" fix,
  `README.md:334`) marks scans safe to run inside a parallel worker without
  itself splitting a scan across workers (`cstore_fdw.c:2421-2425`).
- **`_PG_fini` actually restores the hook** (`cstore_fdw.c:206-209`) — unusual,
  since core effectively never unloads modules; harmless but a tell of the
  pre-9.x era this code grew up in.

## Links into corpus

- `[[knowledge/subsystems/foreign]]` — the FDW/`FdwRoutine` machinery
  cstore_fdw fills out; the single most important cross-reference, since the
  whole ideology is "FDW API repurposed as a storage engine."
- `[[knowledge/architecture/access-methods]]` + `access-method-apis` skill —
  the table-AM API (v12) that is the *correct* home for a pluggable storage
  engine and that cstore_fdw predates; its successor (Citus columnar) migrated
  onto exactly this.
- `[[knowledge/architecture/wal]]` + `[[knowledge/subsystems/storage-buffer]]`
  — the durability/buffer-manager stack cstore_fdw bypasses by writing raw
  `$PGDATA` files via `AllocateFile`/`fwrite`; explains the missing
  replication/archival/crash-safety.
- `[[knowledge/architecture/mvcc]]` + `[[knowledge/idioms/locking-overview]]` —
  the MVCC + row-locking model replaced by a single `ShareUpdateExclusiveLock`
  append-only writer.
- `[[knowledge/subsystems/tcop]]` — `ProcessUtility_hook` is where COPY/DROP/
  TRUNCATE/ALTER get pre-intercepted; tcop owns the utility path.
- `[[knowledge/idioms/error-handling]]` — the `unlink`-and-WARNING storage
  reclamation in the event-trigger DROP path.
- `[[knowledge/ideologies/citus]]` — the sibling extension cstore_fdw couples
  to (`pg_dist_partition`) and the home of its table-AM successor.
- `.claude/skills/extension-development/SKILL.md` — `shared_preload_libraries`
  requirement, single-hook chaining, FDW handler + validator + event-trigger
  install pattern.

## Sources

Fetched 2026-06-07 (branch `master`):

- `https://api.github.com/repos/citusdata/cstore_fdw/git/trees/master?recursive=1`
  @ 2026-06-07 → HTTP 200 (tree listing).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/README.md`
  @ 2026-06-07 → HTTP 200 (412 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_fdw.h`
  @ 2026-06-07 → HTTP 200 (353 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_fdw.c`
  @ 2026-06-07 → HTTP 200 (2438 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_fdw.control`
  @ 2026-06-07 → HTTP 200 (5 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_fdw--1.7.sql`
  @ 2026-06-07 → HTTP 200 (60 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_writer.c`
  @ 2026-06-07 → HTTP 200 (1017 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_reader.c`
  @ 2026-06-07 → HTTP 200 (1382 lines).
- `https://raw.githubusercontent.com/citusdata/cstore_fdw/master/cstore_compression.c`
  @ 2026-06-07 → HTTP 200 (171 lines).

> Queue manifest named `cstore.h`; the real header is `cstore_fdw.h` (no
> `cstore.h` exists in the tree) — fetched the correct path. Added
> `cstore_fdw.control`, `cstore_fdw--1.7.sql`, `cstore_writer.c`,
> `cstore_reader.c`, and `cstore_compression.c` beyond the manifest for the
> storage-format, event-trigger-install, and raw-file-IO detail.

All cites are `[verified-by-code]` against the fetched `.c`/`.h`/`.sql` (hook
install, `FdwRoutine` fill, event-trigger bodies, `AllocateFile`/`fwrite` write
path, lock levels, struct shapes) except the end-user workflow, format
benefits, and version-support claims, which are `[from-README]`. The
protobuf-c metadata-serialization internals (`cstore.proto`,
`cstore_metadata_serialization.c`) were not fetched; statements about *that*
the footer uses protobuf-c are `[from-README]` (build-deps section) plus the
tree listing, not verified against the serializer source.
