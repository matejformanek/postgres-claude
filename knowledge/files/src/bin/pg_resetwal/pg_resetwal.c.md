# `src/bin/pg_resetwal/pg_resetwal.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1317
- **Source:** `source/src/bin/pg_resetwal/pg_resetwal.c`

The "last resort" WAL reset tool — zeroes the write-ahead log when it is
corrupted beyond recovery, optionally rebuilding pg_control. Theory of
operation (from the header comment, lines 6-19): read existing pg_control;
if unreadable, *guess* default values; modify pg_control to a "shutdown"
state with a checkpoint record at the start of a new XLOG segment past
the end of the old log; delete the old WAL, archive_status, and
WAL-summary files; write one empty XLOG file with just that checkpoint
record. Existing data-page LSNs become "in the past" and recovery is
no longer attempted.

**This tool can silently corrupt a cluster.** Resetting WAL discards
uncommitted transactions (obvious) AND can also discard committed
transactions whose effects had not yet reached on-disk data pages by
the time the cluster crashed. The user is expected to dump and reload
afterwards. The CLI tries to make it hard to fire by accident, but
the safeguards are mostly heuristic. [from-comment]
[ISSUE-security: cluster corruption by design — see "dangerous defaults"
below]

## API / entry points

- `main` — argument parsing, then in order: refuse root (Unix only,
  line 388), get a restricted token on Windows
  (`get_restricted_token`), set umask from PGDATA perms, `chdir(DataDir)`,
  `CheckDataVersion` (PG_VERSION must match major version),
  refuse if `postmaster.pid` exists (line 417),
  `read_controlfile` (or `GuessControlValues` if absent/corrupt),
  `FindEndOfXLOG`, print "would do" values if `-n` (dry-run) or guessed
  values, apply CLI overrides, then `RewriteControlFile` +
  `KillExistingXLOG` + `KillExistingArchiveStatus` +
  `KillExistingWALSummaries` + `WriteEmptyXLOG`.
- `CheckDataVersion` — refuses on PG_VERSION major mismatch. Comment
  notes that pg_control mismatch is NOT a hard error because recovering
  from corrupt pg_control is the very reason to run this tool. [from-comment]
- `read_controlfile` — open + read + CRC-check. On CRC mismatch,
  `guessed = true` and we keep the data. On version mismatch or short
  read, return false and `GuessControlValues` takes over.
  Also returns false if `xlog_seg_size` is invalid even if everything
  else is sane. [verified-by-code]
- `GuessControlValues` — hard-coded defaults: timeline 1, NextXID =
  FirstNormalTransactionId, NextOID = FirstGenbkiObjectId, etc. Builds
  a fresh `system_identifier` from `gettimeofday() << 32 | getpid()`.
  The XXX-comment at line 740 acknowledges this should try to scrape
  values from the old XLOG, but it doesn't. [from-comment]
- `PrintControlValues(guessed)` — single big printf block; called when
  we have something to show before the user authorizes the reset.
- `PrintNewControlValues` — prints just the fields the user overrode +
  the first new WAL segment filename.
- `RewriteControlFile` — sets `state = DB_SHUTDOWNED`, points checkPoint
  at the new redo location, zeroes recovery/backup LSNs, forces
  `wal_level = WAL_LEVEL_MINIMAL` and small max_* settings (line 922-934),
  then `update_controlfile(".", &ControlFile, true)`. The comment notes
  that the max_* values "don't really matter as long as wal_level=minimal".
  [from-comment]
- `FindEndOfXLOG` — scans `pg_wal/` for the highest segno (across all
  TLIs, by design — "Better too large a result than too small"). Then
  converts to the new seg size and `++` to land in virgin territory.
  [from-comment]
- `KillExistingXLOG`, `KillExistingArchiveStatus`, `KillExistingWALSummaries`
  — recursive `unlink` of pg_wal/, pg_wal/archive_status/, pg_wal/summaries/
  entries that match well-defined filename patterns.
- `WriteEmptyXLOG` — builds a single XLogLongPageHeader + a single
  XLOG_CHECKPOINT_SHUTDOWN record (with the checkpoint copy from
  ControlFile), CRC, writes that page + zeros the rest of the segment,
  fsyncs. [verified-by-code]
- `strtouint32_strict` / `strtouint64_strict` — strtoul-with-no-negatives.
  [verified-by-code]

## Notable invariants / details

- Refuses to run if `postmaster.pid` exists (line 417-428). This is the
  primary safety net against running on a live cluster. A user with
  write access to PGDATA can defeat it trivially. [verified-by-code]
- Refuses to run as root on Unix (line 388-394). [verified-by-code]
- Without `-f`, refuses if (a) pg_control had to be guessed (line 526-532)
  or (b) `ControlFile.state != DB_SHUTDOWNED` (line 537-543). With `-f`
  it proceeds anyway. The latter is exactly when running this tool is
  most likely to cause silent data loss. [verified-by-code]
- The new system_identifier from `GuessControlValues` (line 689-691) is
  built from time + pid only — replicas/backups derived from the old
  cluster will refuse to attach. [verified-by-code]
- `-l NEXTWALFILE` raises the TLI/segno floor (line 444-445, 501-505)
  but does not validate they are sensible relative to the existing data.
  [verified-by-code]
- `-c OLD,NEW`, `-m MX,OLDMX`, `-O OFFSET`, `-x XID`, `-u OLDXID`, `-o OID`,
  `-e EPOCH`, `--char-signedness`, `--wal-segsize` override individual
  fields. None of these are sanity-cross-checked beyond "is it a parseable
  uint32/64 and not zero/Invalid where forbidden" (lines 199-353).
  XXX-comment at line 286-289 says "It'd be nice to have more sanity
  checks here" w.r.t. multixact wraparound. [from-comment]
- `state = DB_SHUTDOWNED` is unconditionally set in `RewriteControlFile`
  (line 914) — there's no "dry-run after" mode; once you cross the
  Rubicon you've crossed it. [verified-by-code]
- `WriteEmptyXLOG`'s checkpoint record uses `XLR_BLOCK_ID_DATA_SHORT`
  block data with `sizeof(CheckPoint)` payload (line 1162-1163); the
  resulting record must be parseable by xlog.c on the next startup.
  [verified-by-code]
- The new XLOG file is opened with `O_EXCL` (line 1179) after `unlink`
  (line 1177), so we won't overwrite a concurrently-created file but
  will silently `unlink` whatever was there. [verified-by-code]
- WAL summary filename pattern is 40 hex chars + `.summary` (line 1103)
  — must stay in sync with `walsummary.c`. [verified-by-code]
- Uses `#define FRONTEND 1` then `#include "postgres.h"` (line 35) for
  the XLOG includes, same hack as `pg_controldata`. [from-comment]

## Potential issues — dangerous defaults

- `pg_resetwal.c:537-543` — `--force` lets the user proceed past a dirty
  shutdown, which is the single largest data-loss footgun in the
  PostgreSQL toolset. The error text only says "data to be lost"; no
  recommended dump-and-reload after running. [ISSUE-security: --force
  silently authorizes possible data corruption; docs > error message
  (likely)]
- `pg_resetwal.c:417-428` — postmaster.pid presence check is the only
  guard against concurrent live use. No advisory file lock; an operator
  who deleted the pid file by hand (a common "fix" for orphaned pid
  files) can now legally run pg_resetwal against a running cluster.
  [ISSUE-security: postmaster.pid heuristic only (likely)]
- `pg_resetwal.c:683-691` — synthesizes a brand new system_identifier
  on guess, which invalidates every basebackup, replica, and pg_rewind
  history. Documented in user docs but the tool itself does not warn
  inline. [ISSUE-correctness: silent loss of cluster identity (likely)]
- `pg_resetwal.c:286-289` — XXX-comment admits multixact validation is
  inadequate. With `-m` you can set `nextMulti < oldestMulti` and
  produce a cluster that wraps around immediately. [ISSUE-stale-todo:
  multixact sanity-check still missing (maybe)]
- `pg_resetwal.c:309-322` — `-l` validates only the character set
  (hex+length), not whether the resulting TLI/segno exceeds what's on
  disk. A user can roll the WAL forward arbitrarily.
  [ISSUE-correctness: -l validation is lexical only (nit)]
- `pg_resetwal.c:740` — XXX-comment notes the guesser should grovel
  through old XLOG for better values; not done. Result: every guessed
  cluster restarts with `NextXID = FirstNormalTransactionId = 3`,
  which guarantees XID-reuse against any committed work.
  [ISSUE-stale-todo: long-standing XXX, never addressed (maybe)]
- `pg_resetwal.c:937` — `update_controlfile(".", &ControlFile, true)`
  fsyncs the control file but the WAL deletion happens AFTER the control
  file is committed. If the kernel crashes between these two steps the
  control file says "fresh start at new segno" but old WAL files are
  still present. On restart the system would replay them. Probably
  harmless but worth a comment.
  [ISSUE-correctness: control-file before WAL-delete ordering (maybe)]
- `pg_resetwal.c:1032` — `unlink` failure during WAL deletion is fatal
  via `pg_fatal`, leaving control file already rewritten and the data
  directory in a partly-cleaned state. No rollback.
  [ISSUE-correctness: half-deleted WAL on unlink failure (likely)]
- `pg_resetwal.c:236-242` — `strtoul` (NOT `strtouint32_strict`) for
  `newest_commit_ts_xid_val`; inconsistent with the other XID parsers.
  Sign-checking is absent. [ISSUE-correctness: -c uses strtoul, not
  strict variant (nit)]
- `pg_resetwal.c:611-617` — when pg_control is absent, the user is
  told to `touch pg_control` to proceed. That's a deliberate footgun
  release valve; PG admins should know what they're doing.
  [verified-by-code]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Bump CATALOG_VERSION_NO](../../../../scenarios/bump-catversion.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_resetwal`](../../../../issues/pg_resetwal.md)
<!-- issues:auto:end -->
