# `src/include/access/timeline.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**45 lines.**

## Role

Functions and the in-memory representation for reading/writing
**timeline history files** (the `00000NNN.history` files in
`pg_wal/`). A timeline is incremented every time a standby is
promoted or PITR diverges from the previous WAL stream; the history
file records the divergence point so that walreceiver / archive
recovery can pick the right WAL files.
[verified-by-code] `source/src/include/access/timeline.h:1-10`

## Public API

`TimeLineHistoryEntry` struct (lines 25-30):
- `tli` (TimeLineID) — the timeline this entry covers.
- `begin` (XLogRecPtr, inclusive) — first byte on this TLI.
- `end` (XLogRecPtr, exclusive; `InvalidXLogRecPtr` = infinity) —
  switchpoint where the next TLI takes over.

Eight externs (lines 32-42):
- `readTimeLineHistory(targetTLI)` → `List *` of entries (newest first).
- `existsTimeLineHistory(probeTLI)` → bool.
- `findNewestTimeLine(startTLI)` → highest TLI with a history file.
- `writeTimeLineHistory(newTLI, parentTLI, switchpoint, reason)` —
  emit a new `.history` file on promotion.
- `writeTimeLineHistoryFile(tli, content, size)` — raw write
  (used by walreceiver to copy a primary's file).
- `restoreTimeLineHistoryFiles(begin, end)` — pull from archive.
- `tliInHistory(tli, expectedTLEs)` → bool.
- `tliOfPointInHistory(ptr, history)` → which TLI owns `ptr`.
- `tliSwitchPoint(tli, history, *nextTLI)` → `XLogRecPtr`.

## Invariants

- **INV-history-newest-first:** "from newest to oldest"
  [verified-by-code] line 21. The `List` ordering is part of the
  contract; callers iterate front-to-back for the most-recent TLI.
- **INV-history-contiguous:** "the 'begin' and 'end' pointers of all
  the entries form a contiguous line from beginning of time to
  infinity" [verified-by-code] lines 22-23. Gaps are corruption.
- **INV-history-half-open:** `[begin, end)` — begin inclusive, end
  exclusive. `tliOfPointInHistory` depends on this. [verified-by-code]
  lines 28-29.
- **InvalidXLogRecPtr == 0** as `end` means "still current TLI"
  (infinity sentinel).

## Notable internals

`readTimeLineHistory` parses the text history file format:
`<tli>\t<switchpoint>\t<reason>\n`. The reason field is free-form
("at restore point ...", "no recovery target specified", "to LSN ...").

For TLI 1, there is no `.history` file by convention — a fresh
cluster starts on TLI 1 with no history.

## Trust-boundary / Phase D surface

History files come from one of three sources during recovery:
1. Local `pg_wal/`.
2. Restored from `restore_command` (operator-controlled).
3. Streamed from primary via walreceiver.

The parser trusts the file's textual content. A malicious operator
who can plant a `.history` file in `pg_wal/` BEFORE startup can
influence which TLI/switchpoint the cluster picks — but they
already have filesystem access, so this is not a fresh attack
surface, just a consideration for forensics.

**A8 cross-link:** logical replication uses `catalog_xmin` to keep
catalog rows around for output plugins; after a failover the new
primary's TLI bumps, and the standby's recovery cluster echoes the
TLI to walreceiver. A mismatched history file (or one written
to the wrong TLI) is one of the failure modes that triggers the
"requested WAL segment has already been removed" class of replication
breakage.

## Cross-refs

- `access/xlogdefs.h` — `TimeLineID`, `XLogRecPtr`.
- `access/xlog.h` — `XLOG_PAGE_MAGIC` and TLI bump points.
- `src/backend/access/transam/timeline.c` — implementation.
- `replication/walreceiver.h` — consumer that copies history files
  from primary.
- `subsystems/replication-overview.md` — TLI bumps on promotion.

## Issues

- **ISSUE-doc**: header doesn't mention the on-disk text format of
  the `.history` file; the format is a de-facto API for backup
  tools (pg_basebackup, pgbackrest, barman) but is documented only
  in `timeline.c` comments.
