# `src/bin/pg_archivecleanup/pg_archivecleanup.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~401
- **Source:** `source/src/bin/pg_archivecleanup/pg_archivecleanup.c`

Standalone WAL-archive janitor. Removes archived WAL segments older than a
specified "oldest kept" segment from a local directory. Designed primarily
to be plugged into `archive_cleanup_command` on a standby (replacing the
`%r` placeholder with the current restart point), but also usable as a
one-shot CLI. The archive is assumed to be a directory of regular files;
non-local archives are out of scope and the customizable section near the
top of the file is an explicit invitation to fork. [from-comment]

## API / entry points

- `main` — argument parsing, `Initialize` (stat check), `SetWALFileNameForCleanup`
  (parse the cut-off filename), then `CleanupPriorWALFiles`. [verified-by-code]
- `Initialize` — stat-checks `archiveLocation` is a directory; exits 2 if not.
  [verified-by-code]
- `SetWALFileNameForCleanup` — accepts a bare WAL segment name, a `.partial`
  filename, or a `.backup` history file. For the latter two, parses the TLI/log/seg
  prefix and reconstructs the canonical segment name. This prefix-only logic
  matters: a naive string compare would treat `…0010.partial` as later than
  `…0010` and incorrectly retain segment `0010`. [from-comment]
- `CleanupPriorWALFiles` — scans `archiveLocation`, applies `TrimExtension`
  to chop an optional user-supplied `-x` suffix, accepts files matching
  `IsXLogFileName`, `IsPartialXLogFileName`, or (with `-b`)
  `IsBackupHistoryFileName`, then compares the trailing 16 hex chars
  (logId+segId) against the cut-off filename. The TLI prefix
  (bytes 0..7) is deliberately ignored to avoid prematurely deleting parent
  timeline segments. [verified-by-code]

## Notable invariants / details

- The cut-off is **exclusive**: only files strictly older than
  `exclusiveCleanupFileName` are removed (see the `>= 0` skip at line 139).
  [verified-by-code]
- Alphanumeric comparison on segment names works because PG zero-pads the
  16 hex digits. [from-comment]
- TLI is intentionally not compared, "so we won't prematurely remove a segment
  from a parent timeline" (line 127-131 comment). The trade-off is that
  segments on extinct sibling timelines may live longer than necessary.
  [from-comment]
- `-x EXT` strips a trailing extension (e.g. `.gz`) before classification,
  but the file is unlinked under its original (extended) name. The comment
  warns that with `additional_ext` long enough to overflow `MAXPGPATH` the
  truncation is harmless because the filename then no longer matches the
  WAL/backup pattern. [from-comment]
- `-n / --dry-run` prints the candidate file to stdout for piping; nothing
  is unlinked. [verified-by-code]
- `unlink` errors are fatal (`pg_fatal`), so a permission glitch midway through
  leaves a partially-cleaned archive. [verified-by-code]

## Potential issues

- `pg_archivecleanup.c:104` — uses the `errno = 0, (xlde = readdir(...))`
  idiom and checks `errno` after the loop, but does not save errno across
  the `unlink` syscalls inside the loop. On Linux glibc `readdir` does set
  errno to 0 on EOF, so it's correct, but it's the kind of pattern that
  has bitten other PG tools. [ISSUE-correctness: readdir/errno interaction
  is portable per POSIX, but fragile if loop body grows (nit)]
- `pg_archivecleanup.c:163-166` — `unlink` failure is fatal mid-scan.
  No transactionality; on a transient ENOSPC/EBUSY the archive is left in
  an arbitrary state. [ISSUE-correctness: half-cleaned archive on failure (nit)]
- `pg_archivecleanup.c:316` — getopt string `"bdnx:"` matches the long
  options. No `-D` and PGDATA is not used; this tool is purely
  archive-location-driven. [verified-by-code]
- The "Customizable section" delimiter comments at lines 37-50 and 252-255
  date back to the original release and read more as historical artifact
  than active extension point — extension authors would fork rather than
  patch in place today. [ISSUE-stale-todo: customizable-section banner
  is anachronistic (nit)]
