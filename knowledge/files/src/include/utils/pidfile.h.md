# `utils/pidfile.h` — postmaster.pid lock-file format

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/pidfile.h`)

## Role

Documents the line-by-line format of `$PGDATA/postmaster.pid` (the file
that prevents concurrent postmaster starts and that tools like
`pg_ctl status` parse to learn about the running cluster). Pure constants
header — no functions.

## Public API

Line index constants — `source/src/include/utils/pidfile.h:37-44`:

- `LOCK_FILE_LINE_PID 1` — postmaster PID (or negative for standalone backend).
- `LOCK_FILE_LINE_DATA_DIR 2` — data directory path.
- `LOCK_FILE_LINE_START_TIME 3` — postmaster start timestamp (time_t).
- `LOCK_FILE_LINE_PORT 4` — port number.
- `LOCK_FILE_LINE_SOCKET_DIR 5` — first Unix socket directory (empty if none).
- `LOCK_FILE_LINE_LISTEN_ADDR 6` — first listen_address (IP or "*"; empty if no TCP).
- `LOCK_FILE_LINE_SHMEM_KEY 7` — shared memory key (empty on Windows).
- `LOCK_FILE_LINE_PM_STATUS 8` — postmaster status string.

PM status values — `:51-54`:
- `PM_STATUS_STARTING "starting"`.
- `PM_STATUS_STOPPING "stopping"`.
- `PM_STATUS_READY "ready   "` (padded).
- `PM_STATUS_STANDBY "standby "` (padded).

## Invariants

- File is structured as one-value-per-line newline-delimited text.
  [from-comment, `:17-32`]
- Lines 1-3 are written at postmaster start.
- Lines 4+ are added later via `AddToDataDirLockFile()`; line 5
  starts empty and is filled when first Unix socket opens. Onlookers
  must NOT assume lines 4+ appear in any particular order.
  [from-comment, `:29-32`]
- All `PM_STATUS_*` strings are padded to the same length so they can
  be overwritten in place without a rewrite-and-rename dance.
  [from-comment, `:46-49`]
- A negative `LOCK_FILE_LINE_PID` value signals a standalone backend
  (single-user mode), not a postmaster. [from-comment, `:21`]
- Socket lock files (per Unix socket directory) use lines 1-5 with
  line 5 being that socket directory. [from-comment, `:34-35`]

## Notable internals

Padding `"ready"` to `"ready   "` (3 trailing spaces) is deliberate —
in-place update without truncation/rename means `pg_ctl` and other
readers won't see a transiently-empty file.

## Trust-boundary / Phase D surface

- **What information is exposed?** PID, data directory path, port,
  socket directory, listen address, shmem key, PM status. ALL of this
  is OS-discoverable by any local user (PID via `ps`, port via
  `netstat`, etc.), so postmaster.pid doesn't add a new leak in the
  default Unix permissions case. But it concentrates the info in one
  file. [ISSUE-audit-gap: postmaster.pid concentrates discovery info
  (PID, path, port, socket, listen-addr, shmem key) in a single
  world-readable file (nit; PG sets 0600 on $PGDATA)]
- **Does it contain passwords or connection info?** NO. No connection
  strings, no role names, no auth material. Confirmed by the explicit
  enumeration above. [verified-by-comment, `:17-28`]
- **Shmem key on Windows**: empty. Windows-specific code path; the
  format remains stable. [from-comment, `:27`]
- **Concurrent-rewrite safety**: `AddToDataDirLockFile` rewrites in
  place per the padding invariant — not atomic-rename. Crash during
  write produces a half-written line; readers must handle short reads
  gracefully. [ISSUE-correctness: postmaster.pid writes are not
  atomic-rename; crash mid-write leaves partial line (nit; tools
  re-read with backoff)]
- **No version number** in the file — line numbers are the contract.
  Adding line 9 in a future PG version is backwards-compatible (tools
  ignore unknown lines), but reordering would break every consumer.
  [ISSUE-api-shape: format has no version number; consumers
  pattern-match on line index (nit)]

## Cross-refs

- `source/src/backend/utils/init/miscinit.c` — `CreateDataDirLockFile`,
  `AddToDataDirLockFile`.
- `source/src/bin/pg_ctl/pg_ctl.c` — primary consumer.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-audit-gap: postmaster.pid concentrates discovery info in one
   file; PG sets $PGDATA 0700 by default but admins can break that
   (nit)] — `source/src/include/utils/pidfile.h:17-32`.
2. [ISSUE-correctness: in-place writes are not atomic-rename; crash
   mid-write leaves a partial line (nit)] —
   `source/src/include/utils/pidfile.h:46-49`.
3. [ISSUE-api-shape: format has no version number; consumers depend on
   line-index stability (nit)] —
   `source/src/include/utils/pidfile.h:37-44`.
