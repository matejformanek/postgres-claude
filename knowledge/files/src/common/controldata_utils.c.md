---
path: src/common/controldata_utils.c
anchor_sha: 4b0bf0788b0
loc: 284
depth: read
---

# controldata_utils.c

- **Source path:** `source/src/common/controldata_utils.c`
- **Lines:** 284
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/controldata_utils.h`, `catalog/pg_control.h` (defines `ControlFileData`), `port/pg_crc32c.h`.

## Purpose

Read and write `pg_control` (`global/pg_control`), the cluster's single source of truth for crash recovery state — checkpoint LSN, system identifier, on-disk-format flags, and CRC. Same source compiles for backend (ereport / `OpenTransientFile` / `pg_fsync` / wait-event reporting) and frontend (`pg_fatal` / `open` / `fsync` / `pg_log_warning`). [from-comment, controldata_utils.c:43-50]

## Role in PG

Both. Backend caller of `update_controlfile` is the checkpointer (`WriteControlFile` in `xlog.c`) and end-of-recovery code; it locks `ControlFileLock` first. Frontend callers (`pg_controldata`, `pg_resetwal`, `pg_rewind`, `pg_upgrade`) typically run with the server stopped.

## Key functions

- `get_controlfile(DataDir, *crc_ok_p)` (52-60) — compose `<DataDir>/global/pg_control`, delegate to `get_controlfile_by_exact_path`. [verified-by-code, controldata_utils.c:52-60]
- `get_controlfile_by_exact_path(ControlFilePath, *crc_ok_p)` (68-178) — `palloc_object(ControlFileData)`, `open(O_RDONLY)`, single `read()` of `sizeof(ControlFileData)`, validate length, close. CRC is computed over `offsetof(ControlFileData, crc)` and compared to the stored `crc` field. Byte-order sanity check at line 166: if `pg_control_version % 65536 == 0 && pg_control_version / 65536 != 0`, that's a tell-tale of an endian mismatch — backend `elog(ERROR)`, frontend just warns. [verified-by-code, controldata_utils.c:68-178]
- **Frontend-only retry loop** (lines 84-87, 145-163). If CRC fails and we haven't retried ≥10 times AND **(it's our first retry OR the CRC we just got differs from the previous bad CRC)**, sleep 10ms and re-read. The loop terminates when two consecutive bad CRCs match (then `*crc_ok_p` is left `false` and the caller decides what to do). This handles racing against a backend's `update_controlfile` write on systems where the read is not atomic with the write. [verified-by-code, controldata_utils.c:84-163]
- `update_controlfile(DataDir, *ControlFile, do_sync)` (189-284) — set `time`, recompute CRC, copy into a `PG_CONTROL_FILE_SIZE` zero-padded stack buffer, single `write()`, optional fsync, close. Backend version uses `BasicOpenFile` (not `OpenTransientFile`!) because every failure raises PANIC — no fd leak to worry about (line 219-222). [verified-by-code, controldata_utils.c:189-284]

## State / globals

None. All state is on the stack or the caller's `ControlFile` pointer.

## Phase D notes

- **Partial-write window during update.** A single `write(PG_CONTROL_FILE_SIZE = 8192)` is not guaranteed atomic on any filesystem. If the OS crashes mid-write, the on-disk `pg_control` is a torn mix. The frontend reader's retry loop (line 154-162) only handles **a racing writer**, not a torn-write-on-disk; if the torn state survives reboot, both halves' CRC fails and PG refuses to start. There is **no shadow / two-copy mechanism for `pg_control`**. [verified-by-code, controldata_utils.c:209-252] [ISSUE-state-transition: pg_control single-file update has no torn-write protection; mitigated only by the file being smaller than typical sector size on modern HW (maybe-high)]
- **CRC discipline.** Recompute is done BEFORE the write (line 200-205), so the CRC stamps the bytes that will land on disk. Good. [verified-by-code, controldata_utils.c:200-205]
- **Backend PANICs on any write error** (line 223-225, 244-247, 261-265, 275-279). This is correct — `pg_control` corruption is unrecoverable. [verified-by-code, controldata_utils.c:223-279]
- **Frontend `update_controlfile` does NOT fsync the parent directory.** The rename pattern in `file_utils.c:durable_rename` does; `update_controlfile` overwrites in-place and never relinks. So a crash between `write` and `fsync(parent)` could leave the file's new content reachable but not durable on filesystems that don't journal metadata cross-fsync. [verified-by-code, controldata_utils.c:257-272] [maybe — Phase D]
- **`O_WRONLY | PG_BINARY, pg_file_create_mode` on frontend** — the frontend open uses `pg_file_create_mode` even though the file should already exist (we never use O_CREAT). On `open()`-without-O_CREAT the mode is ignored, so this is harmless but confusing. [verified-by-code, controldata_utils.c:229-230]
- **Byte-order check is half a warning.** Frontend `get_controlfile_by_exact_path` only warns on endian mismatch (line 171-175); the caller has the `ControlFileData` and may misinterpret every field. This is the documented behavior of `pg_controldata` ("would be incorrect"). [verified-by-code, controldata_utils.c:166-175]

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=14 [maybe]=2`
