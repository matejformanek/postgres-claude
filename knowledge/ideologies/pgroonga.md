# PGroonga — ideology / divergence-from-core notes

> Extension: `pgroonga/pgroonga` @ `main` (control reports `default_version = '4.0.7'`).
> One durable "how this diverges from core PG design" doc. Line cites are into
> the upstream PGroonga tree (`src/...`, `data/...`), NOT into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`. Cites are approximate where WebFetch reported
> "~line"; treat any single-line cite as ±10 lines pending a local clone.

## Domain & purpose

PGroonga is a PostgreSQL **index access method** that delegates full-text
search to the embedded **Groonga** C library. Its pitch is language-agnostic
FTS: unlike core PG's `tsvector`/`tsquery` + GIN stack (which leans on
language-specific dictionaries and parsers), Groonga's tokenizers handle CJK
and other scripts well, so PGroonga markets itself as "Super fast and all
languages supported full text search index based on Groonga"
[from-README; `pgroonga.control`]. It exposes a family of custom search
operators (`&@`, `&@~`, `&^`, `&~`, `&=`, …) and an index AM named `pgroonga`
that you attach with `USING pgroonga`. In effect it bolts an entire foreign
search engine (Groonga, with its own storage, tokenizers, and query language)
onto PG's pluggable-index API. `[inferred from README + data/pgroonga.sql]`

## How it hooks into PG

- **CREATE ACCESS METHOD + index AM handler.** The SQL bootstrap registers a
  C handler returning `index_am_handler` and creates the AM:
  ```sql
  CREATE FUNCTION pgroonga_handler(internal)
      RETURNS index_am_handler AS 'MODULE_PATHNAME', 'pgroonga_handler' LANGUAGE C;
  CREATE ACCESS METHOD pgroonga TYPE INDEX HANDLER pgroonga_handler;
  ```
  `[verified-by-code: data/pgroonga.sql]`. The handler is declared
  `PG_FUNCTION_INFO_V1(pgroonga_handler)` `[verified-by-code: src/pgroonga.c:328]`.
  It builds an `IndexAmRoutine` and wires the standard callbacks; from the
  code the live ones include `ambuild` → `PGrnCreate()`
  `[verified-by-code: src/pgroonga.c:3099-3154]`, plus `aminsert`,
  `ambulkdelete`/`amvacuumcleanup`, `amgettuple`, `amgetbitmap`,
  `amcostestimate`, and `amoptions` (`PGrnInitializeOptions()` at
  `src/pgroonga.c:1664`) `[inferred from callback wiring]`. PGroonga is an
  *unordered, no-return* AM: it serves search predicates, not ordered scans
  or index-only scans, so the search operators are its raison d'être rather
  than `ORDER BY` pushdown. `[inferred]`

- **Opclasses / strategies / operators.** Each datatype gets an operator class,
  e.g. `pgroonga_text_full_text_search_ops_v2 DEFAULT FOR TYPE text USING
  pgroonga AS OPERATOR 12 &@, OPERATOR 28 &@~, OPERATOR 29 &@*`
  `[verified-by-code: data/pgroonga.sql]`. Strategy numbers are PGroonga's own
  numbering, not btree's 1–5: 12 `&@` (match), 28 `&@~` (Groonga query
  language), 29 `&@*` (semantic/similar), 16 `&^` (prefix), 22 `&~` (regexp),
  38 `&=` (equal), and array/`v2` variants (18, 20, 21, 30, 35, 40, …), plus a
  set of deprecated operators (`&?`, `&>`, `&^>`, …). `[verified-by-code:
  data/pgroonga.sql]` Support functions are detected at runtime by strategy
  number (`PGrnIsQueryStrategyIndex`, `PGrnIsRegexpStrategyIndex`,
  `PGrnIsForPrefixSearchIndex`, `PGrnIsForSemanticSearchIndex`)
  `[verified-by-code: src/pgroonga.c:2751-2931]`.

- **`_PG_init`.** Beyond registering GUCs (`PGrnInitializeVariables()`), it
  initializes the *Groonga runtime itself*: `grn_init()`, a Groonga logger,
  Groonga thread-limit hook, segfault/abort signal handlers, shared-memory
  state + a `before_shmem_exit` callback, and the match-escalation threshold
  `[verified-by-code: src/pgroonga.c:1622-1677]`. This is a heavier `_PG_init`
  than a typical hook-installing extension — it stands up a second engine.

- **Custom WAL resource manager.** PGroonga registers a PG **custom RM**
  (`PGRN_WAL_RESOURCE_MANAGER_ID 138`, claimed on the PG wiki's custom-RM
  registry) with its own record types: `CREATE_TABLE 0x10`, `CREATE_COLUMN
  0x20`, `SET_SOURCES 0x30`, `RENAME_TABLE 0x40`, `INSERT 0x50`, `DELETE
  0x60`, `REMOVE_OBJECT 0x70`, `REGISTER_PLUGIN 0x80`, `BULK_INSERT 0x90`
  `[verified-by-code: src/pgrn-wal-custom.h]`. This is the bridge that lets a
  non-WAL-logged external store ride PG's WAL stream (details below).

- **GUCs.** ~19 custom GUCs under the `pgroonga.` prefix, including
  `pgroonga.enable_wal`, `pgroonga.max_wal_size`,
  `pgroonga.enable_wal_resource_manager`, `pgroonga.enable_crash_safe`,
  `pgroonga.match_escalation_threshold`, `pgroonga.lock_timeout`,
  `pgroonga.enable_row_level_security`, `pgroonga.enable_custom_scan`,
  `pgroonga.enable_parallel_build_copy`, and Groonga log path/level knobs
  `[verified-by-code: src/pgrn-variables.c:~265-465]`.

## Where it diverges from core idioms

1. **Index storage lives OUTSIDE PG's storage manager.** A core index AM
   stores pages through `smgr`/buffer manager in the relation's fork files.
   PGroonga does not: each PG database gets a **separate Groonga database
   directory** under the data dir, opened/created at
   `join_path_components(path, GetDatabasePath(MyDatabaseId,
   MyDatabaseTableSpace), PGrnDatabaseBasename)` then
   `grn_db_open(ctx, path)` or `grn_db_create(ctx, path, NULL)`
   `[verified-by-code: src/pgroonga.c:1594-1631]`. The actual index data
   (lexicons, columns, postings) is Groonga's on-disk format, managed by
   Groonga's own page/lock machinery — invisible to PG's buffer cache,
   `pg_class.relpages`, `pageinspect`, etc. The PG index relation is little
   more than a handle that names the matching Groonga objects (sources table
   named via `PGrnSourcesTableNameFormat` keyed by `relNumber`)
   `[verified-by-code: src/pgroonga.c:3107]`.

2. **MVCC / visibility is bolted on via a stored ctid + heap recheck.**
   Groonga has no concept of `xmin`/`xmax`/snapshots. PGroonga stores each
   heap tuple's `ctid` as a Groonga column and, at scan time, unpacks it and
   rechecks liveness against the heap before yielding a match: it reads the
   ctid accessor, `PGrnCtidUnpack(...)`, and `if (!PGrnCtidIsAlive(table,
   &ctid)) return 0.0;` `[verified-by-code: src/pgroonga.c:1821-1830]`. There
   is explicit HOT-chain / post-VACUUM ctid-resolution handling
   (`ctidResolveTable`, `[ignore][not-hot]`) `[from-comment:
   src/pgroonga.c:~1958-1970]`. So visibility correctness is the AM's manual
   job, layered on top of an engine that knows nothing about transactions —
   the opposite of core AMs, which lean on PG snapshots + index-entry
   liveness. `[inferred]`

3. **Crash safety / WAL is a hand-built bridge, not native WAL-logging.**
   Because the Groonga store is external and not WAL-logged by PG, a crash or
   a physical replica would otherwise see a stale/torn Groonga DB. PGroonga
   solves this two ways: (a) its own **WAL bridge** that records logical
   Groonga operations (`PGrnWALStart/Finish/Abort`, `PGrnWALInsert*`,
   `PGrnWALCreateTable/Column`, `PGrnWALDelete`) and a replayer
   `PGrnWALApply(Relation index)` that re-applies them to rebuild the Groonga
   DB on a replica `[verified-by-code: src/pgrn-wal.h]`; and (b) a
   **`pgrn_crash_safer`** background component that, when the WAL role is
   `GRN_WAL_ROLE_SECONDARY` and the custom RM is disabled, drives recovery
   per-database (`pgrn_crash_safer_statuses_use(...)`,
   `..._get_main_pid(...)`, released in `PGrnBeforeShmemExit`)
   `[verified-by-code: src/pgroonga.c:1603-1627, 1354-1380]`. The newer path
   is the **custom WAL resource manager** (RM id 138) which threads Groonga
   operations into PG's real WAL stream so they replicate/recover natively
   `[verified-by-code: src/pgrn-wal-custom.h]`. Either way, this is durability
   re-implemented at the extension layer — core AMs get it for free from
   `xlog`.

4. **Memory: Groonga's allocator runs outside MemoryContext.** Allocations
   inside the Groonga library (`grn_ctx`, tables, columns, query buffers) are
   Groonga-managed, not `palloc`'d, so they do not participate in PG's
   per-query/per-tuple MemoryContext reset discipline. PGroonga must
   explicitly open/close `grn_obj`s — note the VACUUM hazard comment: "We need
   to close opened grn_objs after VACUUM. Because VACUUM may remove opened but
   unused grn_objs. If we use a removed grn_obj, the process will be crashed."
   `[from-comment: src/pgroonga.c:~1450-1460]`. Lifetime management is manual
   and engine-specific, the classic foreign-allocator divergence.

5. **A whole second engine is initialized in the postmaster lifecycle.**
   `_PG_init` running `grn_init()`, installing Groonga signal handlers, and a
   logger means the extension co-hosts Groonga's runtime inside the PG backend
   process — a far larger surface than a typical hook extension.
   `[verified-by-code: src/pgroonga.c:1622-1677]`

## Notable design decisions (with cites)

- **Handler indirection through `index_am_handler`** rather than any custom
  node — PGroonga is a well-behaved pluggable AM at the catalog level even
  though everything below the callbacks is foreign. `pgroonga_handler` at
  `src/pgroonga.c:328` (decl); `CREATE ACCESS METHOD pgroonga` in
  `data/pgroonga.sql`. `[verified-by-code]`
- **`ambuild` = "stand up Groonga schema, then bulk-load."** `PGrnCreate()`
  creates the sources table, then per-attribute lexicons + data columns
  (`PGrnCreateLexicon`, `PGrnCreateDataColumn`)
  `[verified-by-code: src/pgroonga.c:3099-3139]`, with a bulk-insert WAL path
  (`PGrnBuildStateData.bulkInsertWALData`, `isBulkInsert`, `walRoleKeep`)
  `[verified-by-code: src/pgroonga.c:245-253]`.
- **ctid stored as a Groonga `UInt64` column**, packed/unpacked by
  `PGrnCtidPack`/`PGrnCtidUnpack`, is the linchpin that maps Groonga hits back
  to heap TIDs and enables the visibility recheck
  `[verified-by-code: src/pgroonga.c:1821-1830]`.
- **Runtime strategy-number dispatch** instead of fixed support-function
  slots: the scan path inspects which operator/strategy drove the query and
  branches into query-language vs regexp vs prefix vs semantic search
  `[verified-by-code: src/pgroonga.c:2751-2931]`.
- **`v2` opclass generation + deprecated-operator carry** shows long-lived
  on-disk/SQL-API compatibility discipline (multiple operator generations
  coexist) `[verified-by-code: data/pgroonga.sql]`.
- **Custom RM id 138 publicly claimed** on the PG custom-WAL-RM registry — a
  deliberate choice to use PG-native WAL replication for an external store
  `[from-comment: src/pgrn-wal-custom.h]`.

## Links into corpus

- Index AM machinery: [[access-method-apis]] — `IndexAmRoutine`
  (`ambuild`/`aminsert`/`amgettuple`/`amgetbitmap`/`ambulkdelete`), opclass /
  strategy / support-function registration, TID semantics for a non-heap
  store. PGroonga is a textbook "foreign store behind the index-AM API" case.
- Catalog wiring: [[catalog-conventions]] — `CREATE ACCESS METHOD`, `pg_am`,
  `pg_opclass`, `pg_amop`, `pg_amproc`.
- Subsystems: [[subsystems/access-heap]] (the heap PGroonga rechecks ctids
  against), [[subsystems/wal]] / [[wal-and-xlog]] (custom resource manager,
  redo), [[subsystems/access-gin]] (the core FTS AM PGroonga competes with).
- Idioms: [[idioms/memory-contexts]] (contrast: Groonga's own allocator),
  [[bgworker-and-extensions]] (the `pgrn_crash_safer` worker),
  [[gucs-config]] (the `pgroonga.*` GUC family).
- **Sibling "FTS / search index AM" ideologies:**
  - [[zombodb]] — also an index AM that delegates search to an external
    engine, but **REMOTE** (Elasticsearch over HTTP). **Contrast:** PGroonga
    keeps the engine **LOCAL and embedded** (Groonga compiled in, DB files
    under the PG data dir, in-process `grn_*` calls), so it can integrate with
    PG's WAL/crash-recovery via a custom RM; ZomboDB ships docs to a separate
    ES cluster and reconciles visibility over the network. Local-embedded vs
    remote-service is the headline axis.
  - [[pg_textsearch]] — BM25 ranking implemented as a native PG index AM
    (storage *inside* PG). Contrast: PGroonga's storage is external.
  - [[pgvector]] — another search-flavored AM (ANN/vector), but storage is
    native PG pages; useful contrast for "AM with native storage" vs
    PGroonga's "AM as a façade over a foreign engine."

## Sources

| URL | HTTP | Fetched (UTC) |
|---|---|---|
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/pgroonga.control | 200 | 2026-06-14T00:00:00Z |
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/README.md | 200 (sparse; tech details point off-site) | 2026-06-14T00:00:00Z |
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/src/pgroonga.c | 200 (very large; fetched/skimmed in segments) | 2026-06-14T00:00:00Z |
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/data/pgroonga.sql | 200 | 2026-06-14T00:00:00Z |
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/src/pgrn-wal.h | 200 | 2026-06-14T00:00:00Z |
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/src/pgrn-wal-custom.h | 200 | 2026-06-14T00:00:00Z |
| https://raw.githubusercontent.com/pgroonga/pgroonga/main/src/pgrn-variables.c | 200 | 2026-06-14T00:00:00Z |

**Fetch notes / substitutions:**
- The GitHub *tree* API (`api.github.com/.../git/trees/main`) returned **403**
  via WebFetch and the `github` MCP is scoped to a single allowlisted repo, so
  paths were verified by fetching raw URLs directly rather than from a tree
  listing. The manifest-hinted paths all resolved (no 404s).
- Manifest hint said "a header like `src/pgrn-*.h`": substituted with the two
  most load-bearing headers for this doc, `src/pgrn-wal.h` and
  `src/pgrn-wal-custom.h`, plus `data/pgroonga.sql` (the AM/operator bootstrap)
  and `src/pgrn-variables.c` (GUCs). NOTED as additions beyond the 4-6 hint.
- `src/pgroonga.c` is too large for one WebFetch pass; the `pgroonga_handler`
  body specifically was beyond the fetched window, so the per-callback
  function-name mapping is `[inferred]` from surrounding wiring rather than
  read line-by-line. The handler *declaration* (line 328) and `ambuild`/
  recheck/`_PG_init` regions WERE read. Confirm exact callback assignments
  against a local clone before relying on them for a patch.
