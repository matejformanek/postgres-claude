# `src/backend/backup/walsummaryfuncs.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~210
- **Source:** `source/src/backend/backup/walsummaryfuncs.c`

SQL-callable functions that expose WAL-summary state: list summary
files in `pg_wal/summaries/`, dump a single summary's contents
block-by-block, and read the WAL summarizer process state. Three
functions total; each is a set-returning function except
`pg_get_wal_summarizer_state`. [verified-by-code]

## API / entry points

- `pg_available_wal_summaries()` (line 33) — set-returning;
  returns one row per file in `pg_wal/summaries/`, with `(tli,
  start_lsn, end_lsn)`. Calls `GetWalSummaries(0,
  InvalidXLogRecPtr, InvalidXLogRecPtr)` which matches everything.
  [verified-by-code]
- `pg_wal_summary_contents(tli int8, start_lsn pg_lsn, end_lsn
  pg_lsn)` (line 70) — open one summary file, iterate over each
  `(rlocator, forknum)`, emit a row per modified block. When
  `limit_block != InvalidBlockNumber`, also emits one synthetic row
  with `limit_block = true` so the caller can detect truncation
  markers. [verified-by-code]
- `pg_get_wal_summarizer_state()` (line 178) — one-row composite
  with `(summarized_tli, summarized_lsn, pending_lsn,
  summarizer_pid)`. `summarizer_pid` is NULL when no summarizer is
  running. [verified-by-code]

## Notable invariants / details

- TLI is passed at the SQL level as `int8` because SQL has no
  unsigned types and TLI is `uint32`; the function explicitly
  range-checks `1 <= raw_tli <= PG_INT32_MAX` (line 94).
  [verified-by-code]
- `MAX_BLOCKS_PER_CALL = 256` (line 28) — block-list batching limit
  for `BlockRefTableReaderGetBlocks`. [verified-by-code]
- `CHECK_FOR_INTERRUPTS()` is called in three places (outer
  `foreach` over summary list, outer loop over relations, inner
  loop over block batches) so a long dump can be cancelled.
  [verified-by-code]
- No explicit privilege check in the file itself. Access control
  is set up by the catalog: these functions are restricted via
  `REVOKE EXECUTE ... FROM PUBLIC` and `GRANT TO pg_read_server_files`
  in `system_functions.sql` / `pg_proc.dat`. [inferred]

## Potential issues

- Line 33 — `pg_available_wal_summaries()` calls `GetWalSummaries`
  with `tli=0` which is documented as "any TLI". The directory
  scan itself does not return TLI in sorted order; the SRF returns
  rows in inode/filename order. Stable but undocumented at the SQL
  level. [ISSUE-doc-drift: order of pg_available_wal_summaries rows
  is unspecified (nit)]
- Line 178 — `pg_get_wal_summarizer_state` reads
  `summarizer_pid < 0` to mean "not running" then NULLs the
  column. Negative-pid sentinel is convention not enforced by a
  symbolic constant. [ISSUE-style: magic-negative summarizer_pid
  sentinel (nit)]
- Privilege enforcement is implicit (catalog GRANT/REVOKE). A code
  reader cannot confirm "who can call these" from this file alone
  — there is no `pg_read_server_files`/`role_has_privs_of` test in
  the body. Documenting the catalog-side ACL in a header comment
  would help auditing. [ISSUE-undocumented-invariant: access
  control lives entirely in pg_proc catalog (maybe)]
