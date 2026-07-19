# timeline.c

- **Source path:** `source/src/backend/access/transam/timeline.c`
- **Lines:** 593
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/timeline.h` (not in
  this task list but exists), `xlog.c` (the timeline-switching callers
  `XLogInitNewTimeline`, `SwitchIntoArchiveRecovery`), `xlogarchive.c`,
  `xlogrecovery.c`.

## Purpose

Read/write timeline history files (`<tli>.history`). Each file lists
all parent-timeline switchpoints up to but not including this
timeline. Files are archived alongside WAL segments and used by
recovery to choose the right timeline branch. [from-comment]
`timeline.c:3-22`.

## Top-of-file comment (verbatim)

```
timeline.c
   Functions for reading and writing timeline history files.

A timeline history file lists the timeline changes of the timeline, in
a simple text format. They are archived along with the WAL segments.

The files are named like "<tli>.history". For example, if the database
starts up and switches to timeline 5, the timeline history file would be
called "00000005.history".

Each line in the file represents a timeline switch:

<parentTLI> <switchpoint> <reason>
...
The fields are separated by tabs. Lines beginning with # are comments,
and are ignored. Empty lines are also ignored.
```
[from-comment] `timeline.c:3-22`.

## Public surface

- `restoreTimeLineHistoryFiles(begin, end)` — `timeline.c:51`
  [verified-by-code]
- `readTimeLineHistory(targetTLI)` — `timeline.c:77` [verified-by-code]
- `existsTimeLineHistory(probeTLI)` — `timeline.c:223` [verified-by-code]
- `findNewestTimeLine(startTLI)` — `timeline.c:265` [verified-by-code]
- `writeTimeLineHistory(newTLI, parentTLI, …)` — `timeline.c:305`
  [verified-by-code]
- `writeTimeLineHistoryFile(tli, content, size)` — `timeline.c:464`
  [verified-by-code]
- `tliInHistory(tli, expectedTLEs)` — `timeline.c:527` [verified-by-code]
- `tliOfPointInHistory(ptr, history)` — `timeline.c:545` [verified-by-code]
- `tliSwitchPoint(tli, history, *nextTLI)` — `timeline.c:573`
  [verified-by-code]

## Key types

- `TimeLineHistoryEntry` (declared in `timeline.h`) —
  `{ TimeLineID tli; XLogRecPtr begin; XLogRecPtr end; }` representing
  one line of a parsed history file.

## Key invariants and locking

1. **Timeline 1 has no history file.** `existsTimeLineHistory(1)`
   returns false. [verified-by-code] `timeline.c:223-…` (function
   body not shown, but the standard convention).

2. **History files are immutable once written.** `writeTimeLineHistory`
   writes via a temp file + atomic rename. [verified-by-code]
   `timeline.c:305-…`.

3. **Switchpoint < endpoint of next TLI.** The history is consulted
   to determine whether a recovery point lies in a given timeline's
   range. `tliOfPointInHistory` does this lookup.

## Functions of note

### `readTimeLineHistory` — `timeline.c:77-…` [verified-by-code]

Parses `<tli>.history`, returns a `List *` of `TimeLineHistoryEntry`.
Tries to fetch from archive if not present locally.

### `writeTimeLineHistory` — `timeline.c:305-…` [verified-by-code]

Builds the new history by appending a switch line to the parent's
history, writes via `OpenTransientFile` + `rename`, optionally
calls into the archive.

### `tliOfPointInHistory` / `tliSwitchPoint` — `timeline.c:545, 573`
[verified-by-code]

Used by `xlogrecovery.c:checkTimeLineSwitch` and standby promotion
to validate that an LSN+TLI combination is legal.

## Cross-references

- `xlog.c:XLogInitNewTimeline` — at promotion / recovery end,
  calls `writeTimeLineHistory`.
- `xlogrecovery.c:rescanLatestTimeLine` — uses
  `findNewestTimeLine` / `tliInHistory`.
- `xlogarchive.c` — used to fetch / archive history files.
- `replication/walreceiver.c` — fetches history from primary.

## Open questions

- `restoreTimeLineHistoryFiles` interaction with `restore_command`
  fallback when archive empty not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 13
- `[from-comment]`: 2
- `[unverified]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)

- [subsystems/access-transam.md](../../../../../subsystems/access-transam.md)