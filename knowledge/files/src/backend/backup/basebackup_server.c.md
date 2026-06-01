# `src/backend/backup/basebackup_server.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~260
- **Source:** `source/src/backend/backup/basebackup_server.c`

Server-side target sink: writes backup archives to a directory on the
postgres server's filesystem instead of streaming them back through the
replication connection. Used by `pg_basebackup --target=server:/path`.

## Access control

- The detail-check callback (`server_check_detail`, registered in
  `basebackup_target.c`) verifies the executing role has membership in
  `pg_write_server_files`. Otherwise ereport `ERRCODE_INSUFFICIENT_PRIVILEGE`.
- Path must be an absolute path; relative paths are rejected.

## Sink behavior

- On `begin_archive(filename)`: `OpenTransientFile(<pathname>/<filename>)`
  with `O_WRONLY | O_CREAT | O_EXCL`. Exclusive create — the target
  directory must not contain a stale file with that name. (Practical
  upshot: the directory should be fresh.)
- `archive_contents` and `manifest_contents` `pg_pwrite`-style write the
  buffer.
- `end_archive` / `end_manifest`: fsync the file (via `pg_fsync` in
  `WAIT_EVENT_BASEBACKUP_SYNC`), then close.
- `cleanup` removes any partially-written file on backup failure (via
  the bbsink_state's tracking of the currently-open file). [from-comment]
