# src/include/commands/dbcommands_xlog.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 60 [verified-by-code]

## Role

WAL record definitions for the `RM_DBASE_ID` resource manager — covers
`CREATE DATABASE` (both `FILE_COPY` and `WAL_LOG` strategies) and
`DROP DATABASE`.

## Public API

- `XLOG_DBASE_CREATE_FILE_COPY` (0x00), `XLOG_DBASE_CREATE_WAL_LOG` (0x10),
  `XLOG_DBASE_DROP` (0x20) — info-byte masks (`dbcommands_xlog.h:21-23`
  [verified-by-code]).
- `xl_dbase_create_file_copy_rec` — `db_id`, `tablespace_id`, `src_db_id`,
  `src_tablespace_id` (`:29-35`).
- `xl_dbase_create_wal_log_rec` — `db_id`, `tablespace_id` only; individual
  blocks logged separately (`:42-46`).
- `xl_dbase_drop_rec` — `db_id`, `ntablespaces`, flexible
  `tablespace_ids[FLEXIBLE_ARRAY_MEMBER]` (`:48-53`); `MinSizeOfDbaseDropRec`
  for size calc (`:54`).
- Redo trio: `dbase_redo`, `dbase_desc`, `dbase_identify` (`:56-58`).

## Invariants

- INV-DBXLOG-INFO-MASK: high nibble of WAL `xl_info` selects the record kind;
  low 4 bits reserved per `xlog.h` convention.
- `FILE_COPY` strategy: single record covers the whole CREATE (header comment
  line 27 [from-comment]). Recovery re-runs the directory copy without
  per-block FPI. **Crash-window risk:** if the OS dies mid-`copydir`, recovery
  re-copies from source — but if source files have been written to since (e.g.
  in a hot-standby chain), the copy is point-in-time inconsistent. PG17
  shifted default to `WAL_LOG` for this reason.
- `WAL_LOG` strategy: per-block WAL via standard buffer-manager records;
  this xlog rec is just the marker.

## Notable internals

- `xl_dbase_drop_rec` is variable-length — readers MUST consult `ntablespaces`
  before iterating `tablespace_ids[]`. Forgetting this is a classic over-read.

## Trust boundary / Phase D surface

- **Replication replay echo (A8).** A logical or physical standby replays
  `dbase_redo` with effectively-superuser privilege; a corrupt FILE_COPY
  record pointing `src_db_id` at an attacker-chosen template directory could
  smuggle files into the standby cluster. Mitigation: replication stream
  authenticity (TLS / `replication` privilege) gates this — header does not
  defend against a hostile WAL stream.

## Cross-references

- `commands/dbcommands.h` — front-end DDL entry.
- `access/xlogreader.h` — `XLogReaderState` type used by redo signatures.
- `access/rmgrlist.h` — `RM_DBASE_ID` slot binds these funcs (A17 sibling).

## Issues / drift

- `[ISSUE-DOC: FILE_COPY vs WAL_LOG crash-window trade-off not documented in header — only in release-notes / source comments under createdb.c (medium)] — source/src/include/commands/dbcommands_xlog.h:25-46`
- `[ISSUE-TRUST: no warning that dbase_redo runs with full file-system access on standby; A8 hostile-WAL-stream surface (medium)] — source/src/include/commands/dbcommands_xlog.h:56`
