---
path: src/bin/pg_dump/pg_backup_archiver.h
anchor_sha: f25a07b2d94c
loc: 476
depth: deep
---

# pg_backup_archiver.h

- **Source path:** `source/src/bin/pg_dump/pg_backup_archiver.h`
- **Lines:** 476
- **Last verified commit:** `f25a07b2d94c`

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** re-pinned
> `4b0bf0788b0`→`f25a07b2d94c` (LOC 477→476, cosmetic). The `7ca548f23a60`
> pg_dumpall revert did not alter the private archiver interface. Verified
> cites: K_VERS_MAX 82, worker exit codes 90-97, `_archiveHandle` 215-217,
> `_tocEntry` 348, REQ_* flags 210-213, K_VERS list through 1.16. AUDIT
> clean.
- **Companion files:** `pg_backup.h` (public part exposed to pg_dump), `pg_backup_archiver.c` (implementation), `parallel.h` (`ParallelState`), `pg_backup_custom.c`/`pg_backup_directory.c`/`pg_backup_tar.c`/`pg_backup_null.c` (per-format `Init…` callbacks declared at lines 463-466).

## Purpose

The "private" interface layer. Defines:

1. Archive format version macros (`K_VERS_1_0` … `K_VERS_1_16`, `K_VERS_SELF`, `K_VERS_MAX`). [verified-by-code, archiver.h:46-82]
2. The full `_archiveHandle` (aka `ArchiveHandle`) struct and the `_tocEntry` (aka `TocEntry`) struct. [verified-by-code, archiver.h:215-393]
3. The 25+ function-pointer callbacks each archive-format backend must populate. [verified-by-code, archiver.h:122-151]
4. Worker exit codes (`WORKER_OK`, `WORKER_CREATE_DONE`, `WORKER_INHIBIT_DATA`, `WORKER_IGNORED_ERRORS`) used by `parallel_restore` to signal back to the leader. [verified-by-code, archiver.h:90-97]
5. Helper enums: `T_Action`, `sqlparseState`, `ArchiverStage`, `ArchiverOutput`, `RestorePass`, `REQ_*` bit flags. [verified-by-code, archiver.h:116-213]
6. Macros: `READ_ERROR_EXIT(fd)` / `WRITE_ERROR_EXIT` (pg_fatal wrappers), `appendStringLiteralAHX`, `appendByteaLiteralAHX`.

## Archive version history (from the macro comments)

The version-major-minor-rev is packed into one int via `MAKE_ARCHIVE_VERSION`. Each bump documents a payload change:

- `1.2` — "Allow No ZLIB"
- `1.3` — "BLOBS"
- `1.4` — "Date & name in header"
- `1.5` — "Handle dependencies"
- `1.6` — "Schema field in TOCs"
- `1.7` — "File Offset size in header"
- `1.8` — "change interpretation of ID numbers and dependencies"
- `1.9` — "add default_with_oids tracking"
- `1.10` — "add tablespace"
- `1.11` — "add toc section indicator"
- `1.12` — "add separate BLOB entries"
- `1.13` — "change search_path behavior"
- `1.14` — "add tableam"
- `1.15` — "add compression_algorithm in header"
- `1.16` — "BLOB METADATA entries and multiple BLOBS, relkind" — current.

[from-comment, archiver.h:47-73]

`K_VERS_MAX = MAKE_ARCHIVE_VERSION(K_VERS_MAJOR, K_VERS_MINOR, 255)` — pg_restore accepts any rev ≤ 255 of the current major/minor. [verified-by-code, archiver.h:82]

## Key structs

### `_archiveHandle` (215-342) [extends `Archive`]

First member is `Archive public` (an actual value, not pointer), enabling bidirectional cast. [verified-by-code, archiver.h:217]

Important fields (a subset):

- `version`, `intSize`, `offSize`, `format` — what the file claims.
- `sqlparse` (sqlparseInfo) — used while feeding INSERT data into ExecuteSimpleCommands.
- `readHeader`, `lookahead`, `lookaheadSize`, `lookaheadLen`, `lookaheadPos` — single-shot peek buffer used during `_discoverArchiveFormat` to disambiguate `PGDMP` vs tar header vs text dump. [from-comment, archiver.h:234-243]
- The 25+ `…Ptr` function-pointer slots: `ArchiveEntryPtr / StartDataPtr / WriteDataPtr / EndDataPtr / WriteBytePtr / ReadBytePtr / WriteBufPtr / ReadBufPtr / ClosePtr / ReopenPtr / WriteExtraTocPtr / ReadExtraTocPtr / PrintExtraTocPtr / PrintTocDataPtr / StartLOsPtr / EndLOsPtr / StartLOPtr / EndLOPtr / SetupWorkerPtr / WorkerJobDumpPtr / WorkerJobRestorePtr / PrepParallelRestorePtr / ClonePtr / DeClonePtr / CustomOutPtr`. [verified-by-code, archiver.h:251-284]
- DB-connection state: `archdbname`, `savedPassword`, `use_role`, `connection` (PGconn *), `connCancel` (PGcancel *, volatile — signal handler reads it). [verified-by-code, archiver.h:286-292]
- LO buffer: `loFd`, `writingLO`, `loCount`, `lo_buf / lo_buf_used / lo_buf_size` — the LO data is buffered here before `lo_write` or `lowrite()` SQL emission. [verified-by-code, archiver.h:299-334]
- `currUser / currSchema / currTablespace / currTableAm` — cached so we don't emit redundant SETs. Cleared on reconnect (archiver.c:3576-3587).
- `txnCount` — counter for `--transaction-size` mode.
- `stage`, `lastErrorStage`, `currentTE`, `lastErrorTE` — diagnostic context used by `warn_or_exit_horribly` to attach "while INITIALIZING / PROCESSING TOC / FINALIZING" + the last TOC entry. [verified-by-code, archiver.h:337-341; archiver.c:1923-1956]
- `restorePass` (RestorePass) — only used during parallel restore. [verified-by-code, archiver.h:339]

### `_tocEntry` (348-393)

Doubly-linked circular list node. Fields:

- Identity: `catalogId`, `dumpId`, `section`, `tag`, `namespace`, `tablespace`, `tableam`, `relkind`, `owner`, `desc`.
- Content: `defn`, `dropStmt`, `copyStmt`.
- Dependencies: `dependencies[nDeps]` (DumpId array).
- Data callbacks: `dataDumper`, `dataDumperArg`, `formatData` (format-specific per-TE state, e.g. file offset for custom).
- Lazy-defn: `defnDumper`/`defnDumperArg`/`defnLen` — lets the format module produce defn text on the fly to save memory (used by stats data, archiver.h:375-377; archiver.c:2698-2704).
- Working state: `dataLength` (used by parallel scheduling to pick big-first), `reqs` (REQ_* bitmask from `_tocEntryRequired`), `created` (set when CREATE TABLE succeeded; used to gate TRUNCATE-before-COPY parallel optimization).
- Parallel-only: `pending_prev / pending_next` (in pending_list), `depCount` (unsatisfied dependency count), `revDeps[nRevDeps]` (reverse dep graph), `lockDeps[nLockDeps]` (TABLE/TABLE DATA dumpIds we'd need exclusive lock on; populated by `identify_locking_dependencies`).

[verified-by-code, archiver.h:348-393]

### Helper enums

- `T_Action`: `ACT_DUMP / ACT_RESTORE` — what a worker is doing.
- `sqlparseState`: `SQL_SCAN / SQL_IN_SINGLE_QUOTE / SQL_IN_DOUBLE_QUOTE`. **NB the comment says "We assume that INSERT data will not contain SQL comments, E'' literals, or dollar-quoted strings, so this is much simpler than a full SQL lexer."** (archiver.c:308-311) — that assumption is a Phase D candidate; see archiver.c notes.
- `ArchiverStage`: `STAGE_NONE / STAGE_INITIALIZING / STAGE_PROCESSING / STAGE_FINALIZING`.
- `ArchiverOutput`: `OUTPUT_SQLCMDS / OUTPUT_COPYDATA / OUTPUT_OTHERDATA` — drives the dispatch inside `ExecuteSqlCommandBuf`.
- `RestorePass`: `RESTORE_PASS_MAIN / RESTORE_PASS_ACL / RESTORE_PASS_POST_ACL`. Big top-of-enum comment (182-200) explains why ACLs are interleaved in the TOC but need a 3-pass restore: data before ACLs, matview REFRESH and event triggers after ACLs. Marked `XXX` as something to be replaced by real ACL-dependency tracking. [from-comment, archiver.h:182-208]

### REQ_* flags (210-213)

`REQ_SCHEMA = 0x01`, `REQ_DATA = 0x02`, `REQ_STATS = 0x04`, `REQ_SPECIAL = 0x08`. Set by `_tocEntryRequired` (archiver.c:3008); read by `restore_toc_entry`, `_tocEntryRestorePass`, parallel scheduler. SPECIAL is used for ENCODING/STDSTRINGS/SEARCHPATH (consumed during ReadToc).

### Worker exit codes (90-97)

- `WORKER_OK = 0`
- `WORKER_CREATE_DONE = 10` — signal "CREATE TABLE succeeded; mark sibling DATA member as `created=true`"
- `WORKER_INHIBIT_DATA = 11` — signal "CREATE TABLE failed; suppress sibling DATA"
- `WORKER_IGNORED_ERRORS = 12` — child exit but with non-fatal SQL errors; bump n_errors.

**Comment line 91-93: "We reserve 0 for normal success; 1 and other small values should be interpreted as crashes."** So values 1-9 are crash-shaped. [from-comment, archiver.h:90-93]

## Macros worth knowing

- `READ_ERROR_EXIT(fd)` / `WRITE_ERROR_EXIT` (103-114) — pg_fatal on any IO failure, distinguishing EOF from `errno`. **Every format backend uses these — they unconditionally `exit(1)`.** That means a truncated/corrupt archive aborts the whole pg_restore process rather than failing the TOC entry. Acceptable for restore, but means there's no "best-effort partial restore" path. [verified-by-code, archiver.h:103-114]
- `MAKE_ARCHIVE_VERSION(M,m,r) = ((M)*256+m)*256+r` — 24-bit packing. Implies M, m, r each must fit in a byte (asserted indirectly via `K_VERS_MAX` using rev=255).

## Phase D notes [attacker-controlled-archive surface]

- **Format dispatch is via function pointers** populated by `InitArchiveFmt_*`. If an attacker can flip `AH->format` mid-read or supply a header that picks a different format than the data, dispatch goes to the wrong reader. `_discoverArchiveFormat` (archiver.c:2266) determines format from the magic bytes, then `_allocAH` calls the corresponding `InitArchiveFmt_*`. The format byte from `ReadHead` (archiver.c:4246) is cross-checked against the format already chosen (`pg_fatal("expected format (%d) differs from format found in file (%d)")`), so a mismatch is caught. [verified-by-code, archiver.c:4246-4250] `[fine]`
- **`intSize` ≤ 32 check** (archiver.c:4234-4239) — caps integer-size byte at 32 to prevent absurd loop counts in ReadInt. A hostile archive setting `intSize = 255` is rejected. `[fine]`
- **`offSize` is not bounds-checked** at ReadHead; it's just read as a byte. ReadOffset (archiver.c:2092) loops `off < AH->offSize` reading bytes, discarding ones past `sizeof(pgoff_t)` (with a fatal if any high byte is nonzero — "file offset in dump file is too large"). So a giant `offSize` causes a long byte-skip loop but eventually pg_fatal. `[maybe — phase D]` — denial of service via large offSize-times-tocCount, but bounded by the file size since each iter reads a byte.
- **`K_VERS_MAX` envelope.** Restore accepts archives up to current major.minor with any rev. Older archives are gated via `if (AH->version < K_VERS_1_X)` checks throughout. An archive claiming a *higher* major or minor than K_VERS_MAX is rejected by `ReadHead` (archiver.c:4230-4232). Note: a malicious archive can claim e.g. `1.7` to skip the offsetFlg byte path — see ReadOffset. `[maybe — phase D]`
- **`ArchiveHandle.connection` is shared** with signal handlers via the `volatile connCancel` member. The cancel-info wiring is in pg_backup_db.c. `[fine]`

## Cross-references

- Implementation: `pg_backup_archiver.c`.
- Public side: `pg_backup.h`.
- Format backends: `pg_backup_custom.c`, `pg_backup_directory.c`, `pg_backup_null.c`, `pg_backup_tar.c`.
- Parallel infrastructure: `parallel.c` / `parallel.h` (declares `ParallelState`, `DispatchJobForTocEntry`, `WaitForWorkers`).

## Open questions

- The `XXX` on RESTORE_PASS_POST_ACL (archiver.h:198-199) — actually plumbing ACL dependencies through `dependencies[]` would let us delete the 3-pass loop. Why hasn't it happened? Compatibility with old archives is one reason (the comment says so). [unverified]
- Why is `intSize` capped at 32 specifically? Likely "any value ≥ 8 is already absurd" + safety margin. [inferred, archiver.c:4234-4236]

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=4 [from-readme]=0 [inferred]=1 [unverified]=2 [maybe]=3 [fine]=2`
