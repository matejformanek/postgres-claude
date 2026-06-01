# pgarch.h

- **Source:** `source/src/include/postmaster/pgarch.h`
- **Depth:** skim

## Symbols

- `PgArchiverMain` — the `B_ARCHIVER` `main_fn`.
- `PgArchWakeup()` — backend-side helper to nudge the archiver when WAL
  segments are made ready.
- `PgArchShmemSize`, `PgArchShmemInit`.
- `XLogArchiveNotify` / status-file helpers may live here or in
  `access/xlog_internal.h` depending on tree.
