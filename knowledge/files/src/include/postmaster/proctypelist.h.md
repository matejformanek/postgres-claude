# proctypelist.h

- **Source:** `source/src/include/postmaster/proctypelist.h` (54 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

The canonical, X-macro-style table of every PostgreSQL process type.
Included multiple times by callers that define `PG_PROCTYPE(bktype,
bkcategory, description, main_func, shmem_attach)` differently each time.
[from-comment] `:5-9, :32-33`

## The table

`PG_PROCTYPE(B_<TYPE>, category, description, MainFunc, shmem_attach)`.
Highlights:

| BackendType | Main fn | shmem_attach |
|---|---|---|
| `B_ARCHIVER` | `PgArchiverMain` | true |
| `B_AUTOVAC_LAUNCHER` | `AutoVacLauncherMain` | true |
| `B_AUTOVAC_WORKER` | `AutoVacWorkerMain` | true |
| `B_BACKEND` | `BackendMain` | true |
| `B_BG_WORKER` | `BackgroundWorkerMain` | true |
| `B_BG_WRITER` | `BackgroundWriterMain` | true |
| `B_CHECKPOINTER` | `CheckpointerMain` | true |
| `B_DATACHECKSUMSWORKER_*` | NULL (postmaster doesn't directly launch) | false |
| `B_DEAD_END_BACKEND` | `BackendMain` | true |
| `B_INVALID` | NULL | false |
| `B_IO_WORKER` | `IoWorkerMain` | true |
| **`B_LOGGER`** | `SysLoggerMain` | **false** ← only attached aux! |
| `B_SLOTSYNC_WORKER` | `ReplSlotSyncWorkerMain` | true |
| `B_STANDALONE_BACKEND` | NULL | false |
| `B_STARTUP` | `StartupProcessMain` | true |
| `B_WAL_RECEIVER` | `WalReceiverMain` | true |
| `B_WAL_SENDER` | NULL (type-switched from `B_BACKEND` at auth) | true |
| `B_WAL_SUMMARIZER` | `WalSummarizerMain` | true |
| `B_WAL_WRITER` | `WalWriterMain` | true |

[from-code] `proctypelist.h:34-53`

## Why an X-macro

`launch_backend.c:179-184` consumes the list to build `child_process_kinds[]`.
Other files (e.g. tools / debug dumps) can re-include with their own
`PG_PROCTYPE` definition.

## Note on WAL senders

The header comment (`:21-25`) explains: wal senders begin as `B_BACKEND`
and switch to `B_WAL_SENDER` after replication-auth, hence no direct
`main_fn` — but the type is in the list so `PostmasterChildName` works.
