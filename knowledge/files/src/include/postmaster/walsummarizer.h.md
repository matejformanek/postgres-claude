# walsummarizer.h

- **Source:** `source/src/include/postmaster/walsummarizer.h`
- **Depth:** skim

## Symbols

- `WalSummarizerMain` — the `B_WAL_SUMMARIZER` `main_fn`.
- `WalSummarizerShmemSize`, `WalSummarizerShmemInit`.
- `GetWalSummarizerState` / progress accessors used by SQL functions
  (`pg_get_wal_summarizer_state`).
- GUC globals: `summarize_wal`, `wal_summary_keep_time`.

See also `backup/walsummary.h` for the summary-file format.
