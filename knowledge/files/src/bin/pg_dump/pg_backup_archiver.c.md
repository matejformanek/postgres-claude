---
path: src/bin/pg_dump/pg_backup_archiver.c
anchor_sha: 4b0bf0788b0
loc: 5280
depth: deep
---

# pg_backup_archiver.c

- **Source path:** `source/src/bin/pg_dump/pg_backup_archiver.c`
- **Lines:** 5280
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_archiver.h` (the private types), `pg_backup.h` (public surface), `pg_backup_db.c` (SQL execution layer), `pg_backup_custom.c`/`pg_backup_directory.c`/`pg_backup_null.c`/`pg_backup_tar.c` (format backends), `parallel.c` (`DispatchJobForTocEntry`, `WaitForWorkers`, `ParallelState`), `lib/binaryheap.c` (ready-heap for parallel restore), `compress_io.c` (`CompressFileHandle`).

## Purpose

Central archive driver. Owns:

1. The `Archive` lifecycle: `CreateArchive` → `_allocAH` → format-specific `InitArchiveFmt_*`.
2. TOC management: `ArchiveEntry`, `WriteToc`/`ReadToc`, `buildTocEntryArrays`, `SortTocFromFile`.
3. Restore driver: `RestoreArchive` (serial 3-pass + parallel dispatch) and `restore_toc_entry` (single-TE worker).
4. Parallel restore engine: `restore_toc_entries_prefork` / `_parallel` / `_postfork`, `fix_dependencies`, `move_to_ready_heap`, `pop_next_work_item`, `parallel_restore`.
5. The shared serializer for low-level binary IO: `ReadInt`/`WriteInt`/`ReadStr`/`WriteStr`/`ReadOffset`/`WriteOffset`/`WriteHead`/`ReadHead`.
6. SQL-emission helpers used by every format: `_printTocEntry`, `_doSetFixedOutputState`, `_doSetSessionAuth`, `_selectOutputSchema`, `_selectTablespace`, `_selectTableAccessMethod`, `_becomeUser`, `_becomeOwner`, `_disableTriggersIfNecessary`, `_enableTriggersIfNecessary`.
7. LO buffering: `StartRestoreLOs`/`StartRestoreLO`/`EndRestoreLO`/`EndRestoreLOs`, `dump_lo_buf`.
8. Error context: `warn_or_exit_horribly` and the `stage`/`currentTE` annotation.
9. The big `ahwrite` multiplexer (write to compressor / send to DB / store in LO buf / write to custom-out).

This is the **structural spine of pg_dump's output side and pg_restore's input side**. Everything format-specific delegates back through here.

## Top-of-file comment
> "Private implementation of the archiver routines." [from-comment, archiver.c:5]

## Public surface (extern from `pg_backup.h` and `pg_backup_archiver.h`)

Among many: `CreateArchive`, `OpenArchive`, `CloseArchive`, `SetArchiveOptions`, `ProcessArchiveRestoreOptions`, `RestoreArchive`, `ArchiveEntry`, `PrintTOCSummary`, `WriteData`, `StartLO`/`EndLO`, `SortTocFromFile`, `archputs`/`archprintf`, `NewRestoreOptions`, `NewDumpOptions`, `InitDumpOptions`, `dumpOptionsFromRestoreOptions`, `StartRestoreLOs`/`StartRestoreLO`/`EndRestoreLO`/`EndRestoreLOs`, `WriteHead`/`ReadHead`/`WriteToc`/`ReadToc`, `WriteDataChunks`/`WriteDataChunksForTocEntry`, `WriteInt`/`ReadInt`/`WriteStr`/`ReadStr`/`WriteOffset`/`ReadOffset`, `CloneArchive`/`DeCloneArchive`, `TocIDRequired`, `getTocEntryByDumpId`, `checkSeek`, `ahwrite`/`ahprintf`, `warn_or_exit_horribly`, `parallel_restore`.

## Major flows

### 1. Allocate + open: `_allocAH` (2398-2513)

- malloc-and-zero `ArchiveHandle`.
- Initialize `version = K_VERS_SELF`, `intSize = sizeof(int)`, `offSize = sizeof(pgoff_t)`, `encoding = 0`, `std_strings = true`, `exit_on_error = true`.
- Open a `CompressFileHandle` over stdout (no compression) and stash in `AH->OF` — this is where `ahwrite` writes by default.
- On Windows + fmt != archNull, `_setmode(stdin/stdout, O_BINARY)` to prevent CRLF mangling. [verified-by-code, archiver.c:2472-2481]
- If `fmt == archUnknown`, call `_discoverArchiveFormat`.
- Dispatch to `InitArchiveFmt_Custom/Null/Directory/Tar`.

### 2. Discover format: `_discoverArchiveFormat` (2266-2392)

- If fSpec is a directory: format = archDirectory; look for `toc.dat[.gz/.lz4/.zst]`.
- Else fread 5 magic bytes; if `"PGDMP"` → archCustom.
- Else fread more, check for `"--\n-- PostgreSQL database dump\n--\n\n"` text-header → pg_fatal "input file appears to be a text format dump. Please use psql."
- Else check `isValidTarHeader(lookahead)` → archTar.
- The lookahead is preserved (`AH->lookahead`, `lookaheadLen`) so tar's first member read consumes from it before reading from disk.

### 3. Restore: `RestoreArchive` (349-853)

Top-level orchestrator. Steps:

1. Parallel-mode prereqs: `numWorkers > 1 && useDB && ClonePtr != NULL && ReopenPtr != NULL` and `version >= K_VERS_1_8`. Try `ReopenPtr` immediately (must succeed).
2. Reject compressed archive if format lacks decompression support.
3. `buildTocEntryArrays` (index `tocsByDumpId[]`, `tableDataId[]`).
4. If `ropt->useDB`: `ConnectDatabaseAhx` with overridden version bounds (`min=0, max=9999999`). Set `noTocComments = 1` (no SQL comments → cleaner error reporting).
5. Detect implied schema-less restore (no REQ_SCHEMA entries) → unset `dumpSchema`.
6. Set up output file via `SetOutput` if `ropt->filename` or compression.
7. Emit `"-- PostgreSQL database dump"` header + `\restrict <restrict_key>\n` line.
8. `_doSetFixedOutputState` — emit `SET statement_timeout = 0;`, `SET lock_timeout = 0;`, `SET idle_in_transaction_session_timeout = 0;`, `SET transaction_timeout = 0;`, `SET client_encoding`, `SET standard_conforming_strings`, `SET ROLE`, search_path, `SET check_function_bodies = false`, `SET xmloption = content`, `SET client_min_messages = warning`, `SET row_security = on/off`. If `txn_size > 0`, also begin a transaction. [verified-by-code, archiver.c:3439-3497]
9. If `ropt->dropSchema`: iterate TOC in reverse, emit appropriate DROP for each (with IF EXISTS injection if requested). Handles BLOB METADATA specially via `IssueCommandPerBlob`. Has hand-rolled "find DROP X" / "insert IF EXISTS" rewriter for ALTER TABLE, CONSTRAINT, etc. [verified-by-code, archiver.c:512-726]
10. If parallel: `restore_toc_entries_prefork` (does PRE_DATA serially, then disconnect parent) → fork workers via `ParallelBackupStart` → `restore_toc_entries_parallel` → `restore_toc_entries_postfork` (reconnect leader, do any leftovers).
11. Else: 3-pass loop (MAIN, ACL, POST_ACL).
12. Commit single_txn or transaction-size txn.
13. Emit footer (`\unrestrict KEY`, "Completed on" timestamp, "database dump complete").

### 4. Single-TE restore: `restore_toc_entry` (862-1118)

Three-step pipeline per TocEntry:

- **Schema component** (`reqs & REQ_SCHEMA`): special-case DATABASE/DATABASE PROPERTIES (exit txn block), emit defn via `_printTocEntry`, on TABLE create handle `noDataForFailedTables` flag (set `WORKER_INHIBIT_DATA` or call `inhibit_data_for_failed_table`). If created, mark sibling DATA's `created=true` (or return `WORKER_CREATE_DONE` to parent).
- **Data component** (`reqs & REQ_DATA`):
  - If BLOBS / BLOB COMMENTS: switch outputKind, set search_path to pg_catalog, call `PrintTocDataPtr`.
  - Else: `_disableTriggersIfNecessary` → `_becomeOwner` → `_selectOutputSchema` → optional **TRUNCATE-before-COPY in parallel** (only if `is_parallel && te->created && !is_load_via_partition_root(te)` — comment 1017-1031 explains the wal_level=minimal optimization). Then `te->copyStmt` (set outputKind to OUTPUT_COPYDATA) or fallback OUTPUT_OTHERDATA → `PrintTocDataPtr` → `EndDBCopyMode` if needed → `_enableTriggersIfNecessary`.
- **Stats component** (`reqs & REQ_STATS`): `_printTocEntry(... TOC_PREFIX_STATS)`.
- Bump `txnCount` for `--transaction-size` mode; commit if reached.
- Set status to `WORKER_IGNORED_ERRORS` if `n_errors > 0`.

### 5. Parallel restore: prefork / parallel / postfork (4371-4640)

**Prefork** (`restore_toc_entries_prefork`, 4372-4481):

- `fix_dependencies(AH)`: zero `depCount` to `nDeps`, **repoint POST_DATA dependencies from TABLE → TABLE DATA** (so indexes wait for data), fix pre-8.4 missing BLOB_COMMENTS→BLOBS dep, count incoming dependencies into `revDeps`, fill `lockDeps` for POST_DATA items (TABLE / TABLE DATA siblings they'd need locks on).
- Linearly restore PRE_DATA items in `RESTORE_PASS_MAIN` (skipping ACLs/POST_ACL). Items that we skip are added to `pending_list` for later.
- Commit txn (if `txn_size > 0`) and `DisconnectDatabase` parent so we don't exceed `--jobs N`.

**Parallel** (`restore_toc_entries_parallel`, 4494-4601):

- Build `binaryheap` `ready_heap` sized to `tocCount`.
- Initially move all `depCount==0 && _tocEntryRestorePass(te)==current_pass` items from pending → ready_heap.
- Main loop:
  - `pop_next_work_item(ready_heap, pstate)` — sequential scan of heap, picking first item that has no `has_lock_conflicts` against any currently-running worker's TE.
  - If found: if reqs == 0, skip (just `reduce_dependencies`); else `DispatchJobForTocEntry(... ACT_RESTORE, mark_restore_job_done, ready_heap)`.
  - If none ready: if all workers idle, advance pass (MAIN → ACL → POST_ACL), refill ready_heap from pending. If at `RESTORE_PASS_LAST`, break.
  - Else `WaitForWorkers(WFW_ONE_IDLE or WFW_GOT_STATUS)`.
- On finish: `Assert(binaryheap_empty(ready_heap))`.

**Postfork** (`restore_toc_entries_postfork`, 4612-4640):

- Reconnect leader. Reset fixed state.
- Iterate any items still on the pending_list (shouldn't happen except for circular-dep pathology) and run them serially.

### 6. Worker callbacks: `mark_restore_job_done` (4851-4876)

In leader, after a worker reports done:

- `WORKER_CREATE_DONE` (10) → `mark_create_done` (set `ted->created = true`).
- `WORKER_INHIBIT_DATA` (11) → `inhibit_data_for_failed_table` (zero `ted->reqs`); bump `n_errors`.
- `WORKER_IGNORED_ERRORS` (12) → bump `n_errors`.
- Otherwise non-zero → `pg_fatal("worker process failed: exit code %d")`.
- `reduce_dependencies` — drop `depCount` on each item in `revDeps`; if now 0 and in current pass and still on pending list, move to ready_heap.

### 7. Clone: `CloneArchive` (5196-5252)

Called from each parallel worker to get its own AH:

- Flat-copy `ArchiveHandle`. Flat-copy `RestoreOptions`.
- Reset `connection / connCancel / currUser / currSchema / currTableAm / currTablespace = NULL`.
- `pg_strdup` the saved password (so clones can reconnect without prompting).
- `n_errors = 0`, `lo_buf = NULL`.
- **Force `clone->public.ropt->txn_size = 0`** (line 5234) — workers must commit after every command so the leader sees results. [verified-by-code, archiver.c:5230-5234]
- `ConnectDatabaseAhx` with parent's cparams.
- If read mode, replay `_doSetFixedOutputState`.
- Format-specific `ClonePtr(clone)`.

### 8. `_printTocEntry` (3945-4164)

The schema-emitter, called for every entry that has schema content. Responsibilities:

- `_becomeOwner / _selectOutputSchema / _selectTablespace / _selectTableAccessMethod` (skipping table AM for partitioned tables — done as ALTER post-defn at line 4152-4153).
- Emit header comment (`-- Name: foo; Type: TABLE; Schema: public; Owner: alice`) unless `noTocComments`. Sanitizes name/schema/owner via `sanitize_line`. [verified-by-code, archiver.c:3962-4009]
- Emit definition. Five branches:
  1. SCHEMA + noOwner + non-comment defn → emit hand-built `CREATE SCHEMA %s;` (avoids old AUTHORIZATION clause). Uses `fmtId(te->tag)`.
  2. BLOB METADATA → `IssueCommandPerBlob("SELECT pg_catalog.lo_create('", "')")`.
  3. ACL LARGE OBJECTS → `IssueACLPerBlob`.
  4. `te->defnLen && format != archTar` → pg_fatal (defnDumper already called, format shouldn't re-call us).
  5. `te->defnDumper` → call it, get string, ahprintf + free. Records `defnLen` for the second-call short-circuit.
  6. `te->defn` → just ahprintf it. Bump `txnCount` by `(nsemis - 1)` for transaction-size mode (rough semicolon count, skipping FUNCTION/PROCEDURE).
- Emit `ALTER … OWNER TO …` if `!noOwner`. BLOB METADATA again gets per-blob fan-out.
- For partitioned tables: `_printTableAccessMethodNoStorage` (does `ALTER TABLE … SET ACCESS METHOD …`).
- If `_tocEntryIsACL(te)`: clear `currUser` since ACL commands can contain SET SESSION AUTH.

### 9. `_doSetSessionAuth` (3505-3537) and `_becomeUser` (3599-3615)

`_doSetSessionAuth(AH, user)` builds `SET SESSION AUTHORIZATION '<user>';` using `appendStringLiteralAHX`. **NB: pg_fatal (not `warn_or_exit_horribly`) if RestoringToDB and the SET fails** — the comment says "NOT warn_or_exit_horribly... use -O instead to skip this." [verified-by-code, archiver.c:3520-3530] [from-comment, archiver.c:3527]

`_becomeUser` caches `currUser` to avoid redundant SET SESSION AUTH.

### 10. `_disableTriggersIfNecessary` (1144-1168) and `_enableTriggersIfNecessary` (1170-1194)

Only in data-only restore + `--disable-triggers`. **Becomes superuser** via `_becomeUser(AH, ropt->superuser)` — comment 1156-1160:

> "Become superuser if possible, since they are the only ones who can disable constraint triggers. If -S was not given, assume the initial user identity is a superuser. (XXX would it be better to become the table owner?)"

Then emits `ALTER TABLE <qid> DISABLE TRIGGER ALL;\n`. [verified-by-code, archiver.c:1144-1168] [from-comment, archiver.c:1155-1160]

This is the **"root-only" path** the Phase D watch-list flags: trigger disabling requires superuser, and pg_dump emits these commands in a restore that's expected to be run as superuser. If `ropt->superuser` is attacker-controlled (via `-S` flag), there's no escalation because the actor already had that privilege. But the `SET SESSION AUTHORIZATION` path means if attacker controls the dump file's table tags or trigger names, those flow into `fmtQualifiedId(te->namespace, te->tag)` which uses `fmtId` — identifier-safe quoting. Should be fine. `[fine]`

### 11. `ahwrite` (1871-1915)

Multiplexer over four sinks:

- `AH->writingLO` true → buffer into `lo_buf`, flush via `dump_lo_buf` when full (which either `lo_write`s direct-to-DB or emits `SELECT pg_catalog.lowrite(0, <bytea>)`).
- `AH->CustomOutPtr` set (tar's restore.sql trick) → forward to it.
- `RestoringToDB(AH)` true → `ExecuteSqlCommandBuf` (which dispatches to COPY/PARSE/EXEC).
- Else → `CompressFileHandle->write_func` (final fallback to file).

### 12. Header/TOC IO

- `WriteHead` (4170-4193) — emits PGDMP magic, version, intSize, offSize, format, compression algo, broken-out time fields, db name, server version, dumper version.
- `ReadHead` (4196-4321) — reverse, with bounds checks: `intSize > 32 → pg_fatal`; `version < K_VERS_1_0 || > K_VERS_MAX → pg_fatal`; `format != AH->format → pg_fatal` (after init step).
- `WriteToc`/`ReadToc` (2632-2900) — serialize/deserialize each TE: dumpId, hadDumper, oid pair as decimal strings (historical), tag, desc, section, defn, dropStmt, copyStmt, namespace, tablespace, tableam, relkind, owner, withOids flag, deps[] terminated by NULL. ReadToc handles old version gracefully (defaults for missing fields).
- `WriteInt` / `ReadInt` (2156-2212) — variable-byte-count signed int with explicit sign byte. **Pre-1.0 archives had no sign byte** — `ReadInt` checks version. [verified-by-code, archiver.c:2196-2199]
- `WriteOffset` / `ReadOffset` (2076-2154) — pgoff_t with a `K_OFFSET_*` flag byte. ReadOffset version-gates: pre-1.7 uses int. **`if (AH->ReadBytePtr(AH) != 0) pg_fatal("file offset in dump file is too large")`** when `offSize > sizeof(pgoff_t)`. [verified-by-code, archiver.c:2148-2150]
- `WriteStr` / `ReadStr` (2214-2251) — length-prefix int then payload; `len=-1` means NULL.

### 13. `_tocEntryRequired` (3008-3369)

The big switch that turns command-line filters into per-TE `REQ_*` bits. Handles:

- binary_upgrade special-case for pg_largeobject_metadata / pg_shdepend.
- ENCODING/STDSTRINGS/SEARCHPATH → `REQ_SPECIAL`.
- STATISTICS DATA / EXTENDED STATISTICS DATA gated by `dumpStatistics`.
- DATABASE / DATABASE PROPERTIES gated by `createDB`.
- ROLE / TABLESPACE / DROP_GLOBAL — always REQ_SCHEMA.
- `--no-acl/-comments/-policies/-publications/-security-labels/-subscriptions` filters.
- Section filters from `--section`.
- `idWanted[]` from `-L` file.
- `--schema/--table/--index/--function/--trigger` filters with selective-dump rules.
- Strip schema / data / stats bits based on `dumpSchema/dumpData/dumpStatistics`.

### 14. The 3-pass restore reason

Comment at archiver.h:182-200 explains it. Pass MAIN restores most items; Pass ACL restores ACL/DEFAULT ACL/ACL LANGUAGE; Pass POST_ACL restores EVENT TRIGGER, MATERIALIZED VIEW DATA, and comments/security-labels on event triggers. The comment marks this `XXX` as something that should be replaced by real ACL-dependency tracking.

## Phase D notes [parallel safety, attacker-controlled-archive, hostile dumper]

### Parallel-worker safety

- **`tocsByDumpId` and `tableDataId` are leader-built** in `buildTocEntryArrays` (2011-2049) before workers fork. Workers inherit the pointers via `CloneArchive`'s flat memcpy. Workers READ these arrays but never modify them. `[fine]`
- **`te->reqs` is mutated by `mark_create_done` / `inhibit_data_for_failed_table`** in the leader after a worker callback (lines 4862-4868). The TE is owned by leader; the worker that just finished is no longer touching it. But `te->reqs` was also read by the worker via `restore_toc_entry` (line 882: `reqs = te->reqs`). Worker captured a local snapshot. `[fine]` [verified-by-code, archiver.c:5161-5187]
- **`te->dataLength` is set by `_PrepParallelRestore`** in the leader before workers fork; never mutated after. `[fine]`
- **`te->created`** set by leader (`mark_create_done`) after worker reports `WORKER_CREATE_DONE`. Subsequent worker that picks up the sibling TABLE DATA reads `te->created` to decide TRUNCATE-before-COPY. Ordering is enforced by the dependency edge: TABLE DATA can't be dispatched until TABLE's CREATE returns. `[fine]`
- **`pending_prev`/`pending_next`/`depCount`/`revDeps[]`/`lockDeps[]`** — leader-only mutation; workers don't see them. `[fine]`
- **`AH->connection` per-clone.** Each clone has its own libpq conn. The leader's conn is `NULL` during parallel phase. `[fine]`
- **`AH->lo_buf`** is per-clone (`clone->lo_buf = NULL` in CloneArchive). `[fine]`
- **`tar` and `null` formats lack `ClonePtr`** — parallel restore is rejected at the top of `RestoreArchive` (line 367-368: `pg_fatal("parallel restore is not supported with this archive file format")`). `[fine]`

### Attacker-controlled-archive (pg_restore at superuser)

- **`_discoverArchiveFormat` lookahead is 512 bytes**; magic-string discrimination is tight (PGDMP / text-header / tar header). No buffer overruns since the buffer is sized to `512` and only reads 5+up-to-507. `[fine]` [verified-by-code, archiver.c:2278-2389]
- **`ReadHead` bounds-checks `intSize ≤ 32`**, **version ≤ K_VERS_MAX**, **format == AH->format**. Date fields go through `mktime` with a fallback to `tm_isdst = -1` on failure. No raw bytes from the file flow into pointers or sizes here. `[fine]`
- **`ReadToc` malloc grows `deps[]` array by doubling** starting at 100, with no upper bound (line 2853: `depSize *= 2; deps = pg_realloc_array(deps, DumpId, depSize)`). A hostile TOC with billions of dependency entries would OOM. `pg_realloc` then pg_fatals cleanly on OOM. `[maybe — phase D]` — DoS but not memory corruption.
- **`getTocEntryByDumpId(AH, id)`** bounds-checks `id > 0 && id <= maxDumpId`. Returns NULL otherwise. Callers should null-check. Most call sites do. `[fine]`
- **`SortTocFromFile`** parses user-provided `-L` file via `strtol` and `idWanted[id-1]`; bounds-checked `id > 0 && id <= maxDumpId`. Out-of-range lines are warned and skipped. `[fine]` [verified-by-code, archiver.c:1626-1633]
- **`processEncodingEntry`** parses `te->defn` to extract encoding name — pg_fatal on malformed. Encoding string fed to `pg_char_to_encoding` which has its own validation. `[fine]`
- **`processStdStringsEntry`** parses `te->defn` looking for `'on'` or `'off'`. If neither, pg_fatal. `[fine]`
- **`processSearchPathEntry`** stores `te->defn` verbatim as `AH->public.searchpath` — emitted into the restore script as a raw SQL command. If the archive's defn for SEARCHPATH contains a `; DROP TABLE …;` payload, the restore script will include it. **The dumper controls SEARCHPATH defn**, but if an attacker has tampered with an existing archive, they can inject. `[maybe — phase D]` [verified-by-code, archiver.c:2947-2955]
- **`_printTocEntry` Branch 5 (te->defn → ahprintf)** writes the dump's stored defn verbatim into the restore output. **This is the canonical sink for "dump file content → SQL".** A hostile archive can inject any SQL it wants here. The defense is the threat-model assumption that pg_restore source archives are trusted by the operator. `[maybe — phase D]` [verified-by-code, archiver.c:4079-4081]
- **`ahprintf(AH, "%s", te->defn)`** uses `"%s"` not the defn as format string. Safe against format-string attacks. `[fine]`
- **`fmtId` and `fmtQualifiedId`** are used throughout to escape identifiers (`te->tag`, `te->namespace`). Identifier-quoting is correct against `"` injection. `[fine]`
- **`sanitize_line(te->tag, false)`** for TOC summary comment lines — strips newlines / control chars. Comment header in `_printTocEntry` uses this. `[fine]`
- **Drop-stmt rewriter (612-679)** searches for `"DROP X"` in `te->dropStmt` and inserts `" IF EXISTS"`. If the dropStmt is malformed or the marker isn't found, it falls back to emitting the original unmodified — with a warning. **Not exploitable**, just imperfect rewriting. `[fine]`
- **`ALWAYS_SECURE_SEARCH_PATH_SQL` is sent on every new connection** (db.c:135) — defense against schema-confusion attacks during dump-driving queries. The restore output **also** sets `search_path` (in `_doSetFixedOutputState` via the `SEARCHPATH` TOC entry). `[fine]`

### Hostile dumper (data being dumped is malicious)

- **INSERT data is escaped by pg_dump.c's emitter** before WriteData. The format backends here trust their input. `[fine]`
- **BLOB content via `appendByteaLiteralAHX`** — binary-safe. `[fine]`
- **`\restrict <KEY>` / `\unrestrict <KEY>` framing** around the entire restore script blocks psql meta-commands inside dump output (archiver.c:471-481 comment). The KEY is a random token; an attacker who somehow guesses it AND injects an `\unrestrict KEY\n\!cmd\n\restrict KEY` sequence into a defn would bypass. The threat model is malicious *server response* to dump queries, not malicious archive file. [from-comment, archiver.c:471-481]

### Cross-worker connection / data races

- **`AH->connCancel` is `volatile`** — read by SIGINT handler. CloneArchive sets to NULL; ConnectDatabaseAhx fills in via `set_archive_cancel_info`. `[fine]`
- **`AH->savedPassword` is pg_strdup'd per-clone**, but the leader retains the original. Process-memory has N copies during parallel. `[maybe — phase D]` — multi-copy in heap, same as we noted for db.c.
- **`stdin` / `stdout` `_setmode` on Windows** is process-global. If pg_dump opens an archive while a child has already done `_setmode`, mixed binary/text mode could corrupt subsequent writes. Practically not an issue because the order is fixed. `[fine]`

## Cross-references

- `_disableTriggersIfNecessary` → `_becomeUser(AH, ropt->superuser)` — knowledge/files/src/bin/pg_dump/pg_backup.h.md flags `superuser` as a sensitive struct field.
- `restore_toc_entries_parallel`'s lock-conflict check → `has_lock_conflicts` (4646-4661) which uses `te->lockDeps[]` set by `identify_locking_dependencies` (5057-5113).
- `IssueCommandPerBlob`, `IssueACLPerBlob`, `DropLOIfExists` → `pg_backup_db.c` (this file calls them but they live there).
- `parallel.c` provides: `DispatchJobForTocEntry`, `WaitForWorkers`, `ParallelBackupStart`/`End`, `IsEveryWorkerIdle`, `WFW_*` flags.
- `lib/binaryheap.c` (`binaryheap_allocate`, `binaryheap_add`, `binaryheap_get_node`, `binaryheap_remove_node`, `binaryheap_empty`, `binaryheap_size`) — TOC scheduler in parallel restore.

## Open questions

- The "XXX would it be better to become the table owner?" comment in `_disableTriggersIfNecessary` (1158-1160) — pg_dump becomes superuser to disable triggers because non-owner can't disable constraint triggers, but the table owner CAN. Why hasn't this been changed to use the owner? Possibly old-version compatibility. `[unverified]`
- `WriteToc`'s second pass for the custom format relies on `te->defnLen` short-circuit + fseek. Tar's `_CloseArchive` runs the full TOC twice (once for tar member, once for restore.sql) but `defnLen` is set after the first run — the second run hits the defnLen-set branch and pg_fatals... wait, archiver.c:4046 has `else if (te->defnLen && AH->format != archTar)` — tar is exempted. So tar can call defnDumper twice (comment 4053-4060 acknowledges this; says worst case is restore.sql disagreeing with archive on stats data). `[fine]` [verified-by-code, archiver.c:4046-4070]
- The `ngettext` calls (e.g. line 254 in ExecuteSqlQueryForSingleRow, line 1502 EndRestoreLOs) — i18n-correct plural handling for messages. `[fine]`
- Race: `binaryheap` is per-leader and not shared with workers. Worker sees its TE via message-passing from `DispatchJobForTocEntry` (parallel.c). Leader-only access pattern is enforced by parallel.c. `[unverified]`

## Confidence tag tally
`[verified-by-code]=32 [from-comment]=8 [from-readme]=0 [inferred]=0 [unverified]=3 [maybe]=5 [fine]=22`
