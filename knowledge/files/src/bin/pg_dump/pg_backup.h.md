---
path: src/bin/pg_dump/pg_backup.h
anchor_sha: f25a07b2d94c
loc: 347
depth: deep
---

# pg_backup.h

- **Source path:** `source/src/bin/pg_dump/pg_backup.h`
- **Lines:** 347
- **Last verified commit:** `f25a07b2d94c`

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** re-pinned
> `4b0bf0788b0`→`f25a07b2d94c`. The `7ca548f23a60` pg_dumpall revert left
> this public header untouched (LOC 347). Verified cites: ArchiveFormat
> 39-46, ArchiveMode 48-53, CatalogId 278-283, DumpId 285-287,
> `restrict_key` still in RestoreOptions. AUDIT clean.
- **Companion files:** `pg_backup_archiver.h` (private ArchiveHandle layered on top), `pg_backup_archiver.c` (implementation), `pg_dump.c` (primary consumer), `pg_restore.c` (also consumes), `pg_dumpall.c`.

## Purpose

Public interface that `pg_dump`/`pg_restore`/`pg_dumpall` use to talk to the archiver subsystem. Defines: `ArchiveFormat` enum, `ArchiveMode` enum, `teSection` enum, `ConnParams`, `RestoreOptions`, `DumpOptions`, the public-side `Archive` struct (opaque-by-convention; `ArchiveHandle` extends it in `pg_backup_archiver.h`), `CatalogId`, `DumpId`, and the API entry points (`CreateArchive`, `OpenArchive`, `RestoreArchive`, `WriteData`, `StartLO`/`EndLO`, `ArchiveEntry`, …). [from-comment, pg_backup.h:1-21]

## Public surface

### Enums

- `ArchiveFormat` — `archUnknown=0, archCustom=1, archTar=3, archNull=4, archDirectory=5`. NB: `2` is skipped (was the historical "files" format). [verified-by-code, pg_backup.h:39-46]
- `ArchiveMode` — `archModeAppend / archModeWrite / archModeRead`. [verified-by-code, pg_backup.h:48-53]
- `teSection` — `SECTION_NONE / SECTION_PRE_DATA / SECTION_DATA / SECTION_POST_DATA`. [verified-by-code, pg_backup.h:55-61]
- `_dumpPreparedQueries` — one per cached prepared query in pg_dump. `NUM_PREP_QUERIES` derived. [verified-by-code, pg_backup.h:63-81]
- `trivalue` — `TRI_DEFAULT / TRI_NO / TRI_YES`, used for password-prompt tri-state. [verified-by-code, pg_backup.h:32-37]

### Structs

- `ConnParams` (84-95): `dbname / pgport / pghost / username / promptPassword / override_dbname`. `dbname` may itself be a connstring; comment on line 88 notes the override applies only to the bare dbname. [verified-by-code, pg_backup.h:84-95]
- `RestoreOptions` (97-169): wide bag of restore-time switches — `createDB / noOwner / disable_triggers / dropSchema / dump_inserts / if_exists / single_txn / txn_size / idWanted[] / cparams / compression_spec / suppressDumpWarnings / restrict_key …`. Note `superuser` is a plain `char *` (the username to become for trigger-disabling and similar privileged steps). [verified-by-code, pg_backup.h:97-169]
- `DumpOptions` (171-221): mirror of `RestoreOptions` for dump-time. Largely parallel field set. [verified-by-code, pg_backup.h:171-221]
- `Archive` (227-259): the "public" archive handle returned to pg_dump. Contains `dopt`, `ropt`, `numWorkers`, `sync_snapshot_id`, `encoding`, `std_strings`, `searchpath`, `use_role`, `exit_on_error`, `n_errors`, and `is_prepared[]`. **Last comment: `/* The rest is private */`** — the actual storage `ArchiveHandle` (in `pg_backup_archiver.h`) is allocated by `_allocAH()` and aliased to `Archive *` for callers. [verified-by-code, pg_backup.h:227-259]
- `CatalogId` (278-283): `{ Oid tableoid; Oid oid; }` — the comment on line 280 explicitly says **"this struct must not contain any unused bytes"** because it gets hashed as raw bytes elsewhere. [verified-by-code, pg_backup.h:278-283]

### Typedefs / callbacks

- `DumpId` = `int` with `InvalidDumpId = 0`. [verified-by-code, pg_backup.h:285-287]
- `SetupWorkerPtrType` (pg_backup.h:292) — supplied by pg_dump or pg_restore at archive-creation time, called once per worker (clone) to bring its per-worker connection up.

### API functions

`ConnectDatabaseAhx`, `DisconnectDatabase`, `GetConnection`, `WriteData`, `StartLO`/`EndLO`, `CloseArchive`, `SetArchiveOptions`, `ProcessArchiveRestoreOptions`, `RestoreArchive`, `OpenArchive`, `CreateArchive`, `PrintTOCSummary`, `NewRestoreOptions`/`NewDumpOptions`/`InitDumpOptions`/`dumpOptionsFromRestoreOptions`, `SortTocFromFile`, `archputs`/`archprintf`. The macro `appendStringLiteralAH(buf,str,AH)` projects the public `encoding`/`std_strings` into `appendStringLiteral`. [verified-by-code, pg_backup.h:289-345]

## Key invariants

- **`Archive` is the public face of `ArchiveHandle`.** `pg_backup_archiver.h` declares `struct _archiveHandle { Archive public; … }` so casts in both directions are safe. The "/\* The rest is private \*/" terminator (line 258) marks the ABI boundary. [verified-by-code, pg_backup.h:258; pg_backup_archiver.h:215-342]
- **`CatalogId` is hashed as raw bytes** (line 280 comment "must not contain any unused bytes"); on most ABIs that's fine since both fields are 32-bit `Oid`s, but adding any field requires checking the hashing code. [from-comment, pg_backup.h:278-281]
- **DumpId is a process-local sequential int**, NOT stable across two pg_dump invocations. `InvalidDumpId == 0`, so DumpId arrays are typically `[1..maxDumpId]`. [verified-by-code, pg_backup.h:285-287; archiver.c:2016-2017]

## Phase D notes [security / ABI]

- **ABI fragility.** `RestoreOptions` and `DumpOptions` are exposed by value to pg_dump/pg_restore and copied around (cf. `tar`'s `_CloseArchive` doing `memcpy(ropt, AH->public.ropt, sizeof(RestoreOptions))` to spin up a temporary ropt for the restore.sql script). Any reorder or insertion in `RestoreOptions` requires recompiling pg_dump/pg_restore as one unit; mixing object files across versions would corrupt the copy. `[maybe — phase D]`
- **Credentials in struct.** `ConnParams.dbname` may itself be a connstring (line 87 comment) containing a password. The struct is `pg_malloc`ed and not scrubbed on disconnect — `cparams` lives inside `RestoreOptions` and `DumpOptions` for the lifetime of the archive handle. Process memory dump or core file would expose a connstring with password. `[maybe — phase D]`
- **`superuser` is a plain string** stashed for later `SET SESSION AUTHORIZATION`. Not sensitive (it's a username), but combined with `_disableTriggersIfNecessary` in archiver.c that does `_becomeUser(AH, ropt->superuser)` it forms a privilege-escalation vector if `superuser` is attacker-controlled (e.g. via `--superuser=… ; DROP …`). `fmtId` defends against quoting injection in normal paths, but the value flows through `SET SESSION AUTHORIZATION` which uses `appendStringLiteralAHX` (string-literal, not identifier). `[maybe — phase D]`
- **`restrict_key`** (line 168) is the random token threaded through `\restrict <token>` / `\unrestrict <token>` in the plain-text output to gate psql meta-commands; the comment in archiver.c:471-481 documents the malicious-source threat model. The token is generated elsewhere; the header only stores it. `[maybe — phase D]`

## Cross-references

- Implementation: `pg_backup_archiver.c` (everything declared `extern` here).
- Private extension: `pg_backup_archiver.h` (`ArchiveHandle`, `TocEntry`, function pointers).
- Consumers: `pg_dump.c`, `pg_restore.c`, `pg_dumpall.c`.

## Open questions

- Why is `archiveFormat == 2` skipped? Historical "files" format presumably removed; not documented here. [unverified]
- Does `is_prepared[]` ever need to be cloned to worker children? `CloneArchive` (archiver.c:5196) does a flat memcpy of `ArchiveHandle`, which copies the `is_prepared` pointer — workers share the array with the leader. May be benign because workers re-prepare via `setupWorkerPtr`, but worth confirming. `[unverified — phase D-adjacent]`

## Confidence tag tally
`[verified-by-code]=12 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=2 [maybe]=4`
