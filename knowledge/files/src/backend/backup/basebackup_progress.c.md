# `src/backend/backup/basebackup_progress.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~240
- **Source:** `source/src/backend/backup/basebackup_progress.c`

## Purpose

A bbsink layer that does **two** things at once: drives the
`pg_stat_progress_basebackup` view, **and** updates load-bearing fields
in the shared `bbsink_state` (current tablespace number, bytes_done)
that downstream sinks depend on. The header comment is emphatic that
this is **not optional** — `basebackup.c` always installs it, even if
the client didn't ask for PROGRESS. [from-comment]
(`basebackup_progress.c:5-17`)

## The "lol slot mechanics" — bbsink_state side effects

Two pieces of bbsink_state get updated here and **nowhere else**:

- `state->bytes_done` — incremented inside `archive_contents` before
  forwarding (`basebackup_progress.c:166`). Compression sinks downstream
  read this to compute "done so far" in their own status reporting.
- `state->tablespace_num` — incremented inside `end_archive` (after
  forwarding) (`basebackup_progress.c:144`). One tablespace == one
  archive — `basebackup_server.c` reads this to derive
  `base.tar` / `<tblspc-oid>.tar` filenames.

So if you tried to **omit** the progress sink (e.g. an extension that
swaps in its own minimal stack), the resulting backup would write all
files into `base.tar` and never advance the bytes counter. The
header comment exists because someone tried that and it was confusing.

## Sink ops

`bbsink_progress_ops`: only `begin_backup`, `archive_contents`,
`end_archive` are custom; everything else `bbsink_forward_*`s straight
through. (`basebackup_progress.c:42-52`)

## Progress params

Maintained in `MyBEEntry->st_progress_param[]` via
`pgstat_progress_update_param` (from `backend_progress.c`):

| Slot | Meaning |
|---|---|
| `PHASE` | one of `WAITING_FOR_CHECKPOINT`, `ESTIMATING_BACKUP_SIZE`, `STREAMING_DATABASE_FILES`, `WAITING_FOR_WAL_ARCHIVING`, `TRANSFERRING_WAL_FILES`. Updated by `basebackup.c` AND `basebackup_progress.c`. |
| `BACKUP_TYPE` | `FULL` or `INCREMENTAL`. Set in `bbsink_progress_new`. |
| `BACKUP_TOTAL` | size estimate; -1 → NULL in view. Set on backup-begin (if estimated) and refined upward inside `archive_contents` to avoid done > total. |
| `BACKUP_STREAMED` | running bytes_done. |
| `TBLSPC_TOTAL` | `list_length(tablespaces)` — set on begin_backup. |
| `TBLSPC_STREAMED` | bumped per `end_archive`, guarded so it never exceeds total (because the WAL-included case marks last tblspc complete before the last archive's end). |

## End-of-archive guard

The guard on `tablespace_num + 1 <= total` (`basebackup_progress.c:131-133`)
exists because when `WAL` option is true, the WAL archive is sent
*after* the last tablespace, but tablespace counting and the streamed
counter need to stay consistent. Without the guard, you'd see "5 of 4
tablespaces streamed" while WAL is streaming.

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 3
