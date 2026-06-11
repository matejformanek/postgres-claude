# `src/bin/pg_waldump/pg_waldump.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1546
- **Source:** `source/src/bin/pg_waldump/pg_waldump.c`

The CLI for `pg_waldump`: decodes and prints PostgreSQL WAL records.
Drives `XLogReaderState` from `access/xlogreader.c` with three
custom callback flavors — file mode (read from a directory of WAL
segments) and tar mode (PG18 addition, read from a tar archive via
`archive_waldump.c`). Supports filtering by rmgr, xid, relation,
block, fork, or full-page-write status, plus a `--stats` summary
mode and a `--save-fullpage` mode that decompresses block images to
files. [verified-by-code]

## API / entry points

- `main()` — getopt loop fills `XLogDumpConfig` + `XLogDumpPrivate`,
  installs the SIGINT handler, picks file-mode vs tar-mode
  callbacks, allocates `XLogReaderState`, runs `XLogFindNextRecord`
  to locate the first valid record at or after `--start`, then
  loops calling `XLogReadRecord` until EOF, `--limit N`, or
  `time_to_stop` (SIGINT). [verified-by-code]
- `WALDumpReadPage`/`WALDumpOpenSegment`/`WALDumpCloseSegment` —
  file-mode XLogReader callbacks. Open uses a 10× retry with 500 ms
  sleep to handle `--follow` mode where the next segment might not
  exist yet (line 374-388). [verified-by-code]
- `TarWALDumpReadPage`/`TarWALDumpOpenSegment`/
  `TarWALDumpCloseSegment` — tar-mode callbacks; dispatch to
  `archive_waldump.c` for hash-table-backed reads or fall back to
  a real fd if the segment had been spilled to the temp dir.
  [verified-by-code]
- `XLogDumpDisplayRecord` — emits one record's text representation
  (`rmgr`, lengths, xid, lsn, prev, desc, blk refs). [verified-by-code]
- `XLogDumpDisplayStats` — print rmgr / per-record stats table when
  `-z` requested. [verified-by-code]
- `XLogRecordSaveFPWs` — used when `--save-fullpage` is set; calls
  `RestoreBlockImage` per block ref and writes the decompressed
  page bytes to
  `<savepath>/<tli>-<startlsn-hi>-<startlsn-lo>.<spc>.<db>.<rel>.<blk>_<fork>`.
  [verified-by-code]

## Notable invariants / details

- Uses `#define FRONTEND 1` + `postgres.h` (line 12-13) to pull in
  backend headers like `access/xlog_internal.h`. [verified-by-code]
- Path resolution for the WAL directory: tries
  `--path`, then if no `--path`, tries `.`, `pg_wal`, `$PGDATA/pg_wal`
  (line 286-329, `identify_target_directory`). [verified-by-code]
- Timeline default is 1 (line 994); overridable via `-t` which
  accepts decimal or hex (strtoul base-0, line 1169).
  [verified-by-code]
- `-r/--rmgr list` prints all rmgrs and exits (line 1087-1091).
  `-r custom003` is the only way to filter on an unloaded custom
  rmgr (line 1100). Built-in rmgrs are matched case-insensitively
  by name. [verified-by-code]
- `-R t/d/r` filter accepts spcOid/dbOid/relFileNumber. Both spcOid
  and relNumber must be valid; dbOid is allowed to be 0 (for
  shared catalogs). [verified-by-code]
- `--save-fullpage` directory is required to be empty if it
  exists; created if missing (line 122-145).
  [verified-by-code]
- SIGINT handler sets a `volatile sig_atomic_t time_to_stop`; the
  main loop checks at the top of each iteration (line 1453-1457).
  On Windows, no handler is installed (line 968-970).
  [verified-by-code]
- The tar-mode path enters via `--path foo.tar.{gz,lz4,zst}`; the
  extension is parsed by `parse_tar_compress_algorithm`. The
  archive-name detection accepts the form from both `--path`
  (line 1244-1248) and a positional argument (line 1289-1293).
  [verified-by-code]
- `--follow` is rejected with a tar archive (line 1368-1372),
  because the archive can't grow during decoding.
  [verified-by-code]
- `cleanup_tmpwal_dir_atexit` (line 875) closes any open WAL file
  before `rmtree` so Windows can delete the dir.
  [verified-by-code]
- `XLogDumpDisplayStats` uses `ngettext` for "1 byte" vs "N bytes"
  pluralisation. [verified-by-code]

## Potential issues

- Line 393: `pg_fatal("could not find file \"%s\": %m", fname);`
  uses `%m` but `errno` is `ENOENT` from the last failed
  `open_file_in_directory` only IF the retry path actually fell
  through. On a non-ENOENT error we `break` (line 390) and the
  errno is preserved. OK. [verified-by-code]
- Line 374-388: `--follow` retry waits up to 10 × 500 ms = 5 s for
  the next segment. After that it pg_fatals. If the server is
  slow to roll, the user sees a spurious fatal. The hardcoded
  retry count is documented in the comment.
  [verified-by-code] [ISSUE-undocumented-invariant: --follow retry
  budget is fixed at 5 s with no flag to extend (nit)]
- Line 1175: option `-t` allows hex (`strtoul` base 0). If a user
  has a TLI of e.g. `0123` they may be surprised that it parses as
  octal 83 rather than decimal 123.
  [verified-by-code] [ISSUE-undocumented-invariant: -t/--timeline
  parses base 0 (decimal + 0x hex + 0 octal); octal leading-zero
  surprise (maybe)]
- Line 641: `snprintf("%08X-%08X-%08X.%u.%u.%u.%u%s", tli, lsn_hi,
  lsn_lo, spc, db, rel, blk, forkname)`. If a fork name contains
  characters problematic for the filesystem (it shouldn't, fork
  names are fixed: main, fsm, vm, init), the format would leak
  through. The bound at line 636 (`fork >= 0 && fork <=
  MAX_FORKNUM`) is safe.
  [verified-by-code]
- Line 1100: parsing custom rmgr name as `custom%03d` — this would
  also accept `custom123abc` (sscanf stops at non-digit), then the
  range check rejects the value. But the trailing garbage isn't
  diagnosed, so `-r custom123abc` would either succeed silently or
  fail with a confusing message depending on whether 123 maps to
  a valid custom rmgr ID. [verified-by-code]
  [ISSUE-correctness: -r custom### parser doesn't reject trailing
  garbage; ambiguous diagnosis (nit)]
- Line 1196: `sscanf("%u", &filter_by_xid)` will accept `12abc`
  silently as 12. [verified-by-code] [ISSUE-correctness: -x XID
  parser accepts trailing garbage (nit)]
- Line 1071: `sscanf("%d", &stop_after_records)` likewise.
  [verified-by-code]
- Line 1040: `sscanf("%u", &filter_by_relation_block)` likewise.
  [verified-by-code]
- Line 152 comment "XXX this probably doesn't do very well on
  Windows" on `split_path`. Known limitation: forward-slash split
  only. [verified-by-code] [ISSUE-stale-todo: split_path is
  forward-slash only; potentially wrong on Windows backslash
  paths (maybe)]
- Line 37 banner-comment: "For any code change or issue fix here,
  it is highly recommended to give a thought about doing the same
  in pg_walinspect contrib module as well." This is the
  drift-risk acknowledgment. There is real risk that bug fixes
  land in one place and not the other. [verified-by-code]
  [ISSUE-doc-drift: pg_walinspect mirrors much of pg_waldump
  logic; risk of divergent fixes documented in code comment
  (maybe)]
- Line 1297-1299: when STARTSEG file fails to open after
  `identify_target_directory` succeeded, the message is "could not
  open file \"%s\"" without `%m`, so the error reason is lost.
  [verified-by-code] [ISSUE-style: missing %m in
  pg_fatal("could not open file ..", fname) at line 1299 (nit)]
- Line 1543: `bad_argument` label returns EXIT_FAILURE without
  printing usage, only the hint. Stylistically fine but a user
  invoking with a typo gets no inline help.
  [verified-by-code]
- WAL record version mismatch: `pg_waldump` does NOT version-gate
  the records it dumps against the local PG version. If a user
  dumps WAL produced by a PG with a different `XLOG_PAGE_MAGIC`
  the XLogReader will reject; but if a record format changed
  *within* the same magic (rare but possible across minors),
  pg_waldump may decode it wrongly. The desc functions assume the
  current source-tree layout. [verified-by-code]
  [ISSUE-correctness: pg_waldump decodes assuming current-source
  WAL record layouts; cross-version WAL may be misdecoded if
  magic matches but record format differs (maybe)]
