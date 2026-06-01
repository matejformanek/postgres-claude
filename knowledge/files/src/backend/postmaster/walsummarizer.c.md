# walsummarizer.c

- **Source:** `source/src/backend/postmaster/walsummarizer.c` (1744 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim (top comment + structure)

## Purpose

Newer aux process (PG 17) that scans the WAL and emits **WAL summary files**
recording which blocks of which relation forks were modified in a given LSN
range. These summaries power incremental base backups (`pg_basebackup
--incremental`). [from-comment] `:5-15`

Also responsible for **deleting** stale summary files older than a
configurable threshold, but only after the corresponding WAL itself has been
removed. [from-comment] `:12-15`

## Lifecycle

- Singleton aux process. `main_fn = WalSummarizerMain` (proctypelist.h).
- Controlled by `summarize_wal` GUC. When off, postmaster doesn't start it.
- Standard aux signal handling via `interrupt.c` helpers.

## Key structures

- A shmem struct (`:55+`) records: current summarized LSN, summary file
  rotation state, and process-state flags.

## Related files

- `backup/walsummary.c` — summary file format + readers.
- `common/blkreftable.c` — block-reference table data structure.
- `backup/basebackup_incremental.c` — consumer.
- Header: `postmaster/walsummarizer.h`.

## Open

Detailed walk of the summarization algorithm and LSN-range bookkeeping is
deferred to a dedicated backup/walsummary subsystem doc.
