# `src/backend/backup/basebackup_incremental.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1054
- **Source:** `source/src/backend/backup/basebackup_incremental.c`

Incremental-backup support module (PG17+). Holds an
`IncrementalBackupInfo` built from the prior backup's manifest
plus a merged block-reference table loaded from WAL summary files;
answers `GetFileBackupMethod` on a per-segment basis to decide
whether the basebackup driver should send a full copy or only the
modified blocks. The actual sending happens in `basebackup.c`'s
`sendFile`. [from-comment]

## API / entry points

- `CreateIncrementalBackupInfo(mcxt)` (line 151) — palloc the
  struct, initialise a 10 000-entry simplehash for files, set up
  the incremental JSON manifest parser. [verified-by-code]
- `AppendIncrementalManifestData(ib, data, len)` (line 193) — feed
  client chunks into a growing `StringInfo`. When the buffer
  passes `MAX_CHUNK = 128 KiB`, drain everything except the last
  `MIN_CHUNK = 1 KiB` through the incremental JSON parser. The
  `MIN_CHUNK` tail buffer ensures the manifest's trailing checksum
  line is still in memory at finalisation time.
  [verified-by-code]
- `FinalizeIncrementalManifest(ib)` (line 226) — flush the last
  chunk with `final=true`, free buffer + parser state.
  [verified-by-code]
- `PrepareForIncrementalBackup(ib, backup_state)` (line 262) — the
  big one. Walk the manifest's WAL ranges against the server's
  `readTimeLineHistory(backup_state->starttli)`, identify earliest
  and latest TLI mentioned, validate that ranges align on
  timeline-switch LSNs, wait via `WaitForWalSummarization` for the
  summarizer to catch up to `backup_state->startpoint`, then load
  all required summaries into `ib->brtab`. Sets
  `backup_state->istartpoint` / `istarttli`. [verified-by-code]
- `GetIncrementalFilePath(dboid, spcoid, relfilenumber, forknum,
  segno)` (line 622) — `<reldir>/INCREMENTAL.<segfile>` for
  segno==0, else `INCREMENTAL.<segfile>.<segno>`.
  [verified-by-code]
- `GetFileBackupMethod(...)` (line 660) — the core per-file
  decision. Returns BACK_UP_FILE_FULLY or
  BACK_UP_FILE_INCREMENTALLY and populates the output arrays.
  [verified-by-code]
- `GetIncrementalHeaderSize(num_blocks)` (line 878) — `3*sizeof(uint32)
  + num_blocks * sizeof(BlockNumber)`, rounded up to a BLCKSZ
  multiple only when block data follows. [verified-by-code]
- `GetIncrementalFileSize(num_blocks)` (line 906) — header size +
  `BLCKSZ * num_blocks`. [verified-by-code]

## When `GetFileBackupMethod` returns FULL

1. `size % BLCKSZ != 0` or `size > RELSEG_SIZE * BLCKSZ` (corrupt
   or oversized segment) — line 691.
2. `forknum == FSM_FORKNUM` — FSM is not WAL-logged so summaries
   say nothing useful (line 698).
3. File not present in prior manifest (line 723) — also checks
   the manifest for an `INCREMENTAL.*` entry (the prior backup may
   itself have been incremental).
4. A "whole database OID/tablespace OID created since prior
   backup" entry exists in the block-ref table (line 740) —
   shorthand for "everything new".
5. limit_block (truncation point) lies before this segment (line
   779).
6. >90% of blocks would need to be sent anyway (line 816) — the
   "send the whole file" heuristic.

Otherwise: read `BlockRefTableEntryGetBlocks` into the absolute
block-number array, qsort, transpose to segment-relative numbers
(line 820-835), then return INCREMENTALLY with
`truncation_block_length` clamped between `size/BLCKSZ` and
`relative_limit` and capped at `RELSEG_SIZE`. [verified-by-code]

## Notable invariants / details

- **Summaries are loaded into one merged in-memory `BlockRefTable`**
  (line 570-611). The header comment for `struct
  IncrementalBackupInfo` acknowledges memory pressure but argues
  "in-memory format converging to little more than 1 bit per
  block". [from-comment]
- **Sanity errors all use `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE`**
  with detailed errmsg telling the user which TLI/LSN combination
  is wrong; e.g. line 411-414 catches "manifest requires WAL from
  initial timeline N starting at X/Y, but that timeline begins at
  X/Z". This is the chief defence against bogus prior manifests.
  [verified-by-code]
- **Standby corner case at line 429-436:** if the prior backup's
  end_lsn exceeds `backup_state->startpoint`, ereport raises the
  errhint "This can happen for incremental backups on a standby
  if there was little activity since the previous backup." A real
  operational footgun. [verified-by-code]
- **Two-lifespan file race** (lines 711-721): a file that existed
  in the prior backup, was dropped, then recreated with the same
  name is sent incrementally — this is unsafe in general but
  rescued by WAL replay during restore, which (per comment) will
  recreate the file with correct contents.
  [from-comment, INV: relies on WAL replay covering the gap]
- **Manifest version 1 is rejected** (line 944) — incremental
  backup requires manifest format v2+. [verified-by-code]
- **System-identifier check at line 953** — if the prior manifest
  was taken on a different cluster's pg_control system identifier,
  fail loudly. [verified-by-code]

## Potential issues

- Line 711-721 — the "file dropped and recreated" comment relies
  on "WAL replay to reach backup consistency should remove and
  recreate the file anyway". If reconstruction happens before
  WAL replay (e.g. someone uses pg_combinebackup output without
  going through recovery), the resulting file would mix old and
  new lifespans. The comment acknowledges "but in this type of
  case, ... the initial bogus contents should not matter" — but
  this is a load-bearing assumption with no enforcement.
  [ISSUE-undocumented-invariant: incremental restore correctness
  depends on WAL replay running afterwards (likely)]
- Line 816 — the 90% threshold is hard-coded with the comment
  "perhaps it ought to be configurable". A site with very large
  segments and an unusual workload shape might want to tune this.
  [ISSUE-stale-todo: hard-coded 90% threshold for full-vs-incremental
  (nit)]
- Line 790 — overflow detection on `start_blkno`/`stop_blkno` is
  defensive but the input bounds (`size <= RELSEG_SIZE * BLCKSZ`
  enforced at line 691) already prevent the case. Dead-but-cheap
  belt-and-braces. [ISSUE-dead-path: overflow check at line 790
  is unreachable given prior bounds (nit)]
- Line 458 — `WaitForWalSummarization` is documented as "If WAL
  summarization gets disabled while we're waiting, this will
  return immediately, and we'll error out further down if the WAL
  summaries are incomplete." The error message in that case (line
  522-527) does not mention that `summarize_wal` may be off; an
  operator hitting this will see "no summaries for that timeline
  and LSN range exist" without a hint pointing at the GUC.
  [ISSUE-doc-drift: missing errhint about summarize_wal=off case
  (maybe)]
- Line 105 — the comment for `manifest_files` warns "if that turns
  out to be a problem, we might have to decide not to retain this
  information, or to make it optional". Hot research direction for
  large clusters. [ISSUE-stale-todo: file-list memory footprint
  acknowledged but not addressed (nit)]
