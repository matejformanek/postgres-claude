# `src/bin/pg_basebackup/pg_receivewal.c`

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

Standalone client that connects to a primary in replication mode and
streams WAL segments to a local directory, optionally creating /
dropping a replication slot. Used as a standby "warm archive"
substitute or to feed a third-party archive (RESTORE/REPLAY of WAL).
Supports gzip / LZ4 compression and `--synchronous` immediate flush.
`[from-comment]` (header lines 1-12).

## Role in the pipeline

```
primary walsender ── COPY BOTH ──> pg_receivewal
                                     │
                                     └── basedir/000000010000000000000001[.partial][.gz|.lz4]
```

Replaces (in spirit) what a `archive_command` would do, but does it
over the streaming protocol so files are available with much lower
latency. Drives the `walmethod` abstraction from
`receivelog.c` / `walmethods.c` via `CreateWalDirectoryMethod()`
(line 588). `[verified-by-code]`

## Key functions

| Function                  | Lines     | Notes |
|---------------------------|-----------|-------|
| `main`                    | 623-927   | Option parse, slot create/drop short-circuits, reconnect loop. |
| `StreamLog`               | 499-608   | Per-connection setup; calls `RunIdentifySystem`, computes start LSN, calls `ReceiveXlogStream`. |
| `FindStreamingStart`      | 267-494   | Scans `basedir/` for the highest-numbered completed WAL segment to resume from. |
| `is_xlogfilename`         | 115-181   | Recognizes plain / `.partial` / `.gz` / `.lz4` suffix combinations. |
| `stop_streaming`          | 183-228   | Callback wired into `StreamCtl.stream_stop`; honors `endpos` and SIGINT. |
| `get_destination_dir` / `close_destination_dir` | 234-257 | Thin opendir/closedir helpers; fatal on failure. |
| `sigexit_handler`         | 616-621   | Sets `time_to_stop`. |
| `disconnect_atexit`       | 67-72     | `PQfinish(conn)` only. Does NOT drop slots. |

## State / globals

```
basedir, verbose, compresslevel, noloop,
standby_message_timeout, time_to_stop,
do_create_slot, slot_exists_ok, do_drop_slot,
do_sync, synchronous,
replication_slot, compression_algorithm, endpos
```
(lines 43-56). Connection state (`conn`, `dbhost`, …) lives in
`streamutil.c` (see B4 doc).

`stop_streaming` keeps two static locals `prevtimeline` / `prevpos`
(186-187) used only for the "switched to timeline" log line.

## Phase D notes

### Output directory trust

- `basedir` comes from `-D / --directory` or the positional argument,
  passed straight to `opendir`. No symlink resolution, no refusal of
  e.g. `/tmp/foo` — caller is trusted to point at a sensible
  directory. `[verified-by-code]` (line 240).
- File creation goes through `walmethods.c` (B4 territory), which
  uses `pg_file_create_mode` honoring the server-side
  `data_directory_mode` retrieved during `GetConnection()` (the
  `umask(pg_mode_mask)` on line 870 is the reason this works). So
  `--allow-group-access` on the *server* propagates to
  pg_receivewal's WAL files. `[inferred]`
- Existing files in the directory: `FindStreamingStart` parses any
  file matching `0..9A..F`+suffix as a WAL segment (line 285). A
  hostile file named e.g. `000000010000000000000001.partial` would be
  *resumed-from*, potentially mixing attacker content with new WAL.
  Mitigation: the directory is meant to be owned by the user running
  pg_receivewal, but it's not enforced. `[ISSUE-trust-boundary: target dir trusts any 24-hex-char filename as a resumable WAL segment (maybe)]`

### fsync discipline

- Default is `do_sync = true` (line 52). `--no-sync` flips it (line
  744), accompanied by a startup banner from the docs.
- `--synchronous` (line 741) sets `stream.synchronous` so each WAL
  flush is immediate; otherwise flushes piggyback on segment boundary
  / status interval. Implementation lives in `receivelog.c`.
- `FindStreamingStart`'s LZ4 size check reads the whole file once
  (lines 367-457) to decode `WalSegSz`; gzip relies on the 4-byte
  ISIZE footer (327-365). The gzip ISIZE is mod 2^32, so a >4GB
  segment would alias. Not currently an issue because PG's wal seg
  size max is 1GB. `[from-comment]` (line 298-303).

### Replication-slot lifecycle

- `--create-slot` / `--drop-slot` are pure short-circuits in `main`
  (875-895): connect, do the slot DDL, `exit(0)`. No retry.
- During streaming: slot is named via `-S`; cleanup on Ctrl-C does
  NOT drop the slot — only `PQfinish(conn)` runs in
  `disconnect_atexit`. That is by design (the slot should persist so
  the next invocation can resume) but the docs need to remind
  operators to drop it manually when retiring an archiver host.
  `[ISSUE-undocumented-invariant: SIGINT leaves replication slot on server, can wedge WAL retention if archiver host dies (low)]`

### Password handling

- All credentials flow through `streamutil.c`'s `GetConnection()`
  (line 511, 831). pg_receivewal stores nothing itself — same
  scrubbing-gap as B4 (no `PQconninfoFree` call observed in
  streamutil for the password string). See B4 doc.

### Reconnect loop

- `main` loops forever calling `StreamLog()` (906-926), sleeping
  `RECONNECT_SLEEP_TIME` (5s) on failure. `--no-loop` makes a single
  disconnect fatal. The sleep is a busy-`pg_usleep`, not a `select`
  on a signal-pipe, so SIGTERM during the sleep delays exit by up to
  5s. `[verified-by-code]`

### Compression-spec parsing

- `parse_compress_options` / `parse_compress_specification` /
  `validate_compress_specification` come from `compression.c`.
- ZSTD is rejected hard at line 815 ("not yet supported"). Stale
  TODO — the rest of the codebase handles ZSTD for basebackup.
  `[ISSUE-stale-todo: ZSTD WAL compression rejected as not-yet-supported despite ZSTD basebackup support (low)]`

## Potential issues

- `[ISSUE-trust-boundary: target dir trusts any 24-hex-char filename as a resumable WAL segment (maybe)]` — `FindStreamingStart` scans the basedir and parses any matching filename as a segment to resume; a hostile pre-seeded file could shift the start LSN.
- `[ISSUE-undocumented-invariant: SIGINT leaves replication slot on server (low)]` — by design but operators sometimes miss it.
- `[ISSUE-stale-todo: ZSTD WAL compression unsupported at line 815 (low)]`
- `[ISSUE-dos: 5-second pg_usleep in the reconnect loop delays signal handling (low)]`
- `[ISSUE-info-disclosure: verbose mode logs every keepalive / segment boundary at INFO; if stderr is redirected to a shared log, observers learn the WAL LSN cadence (maybe)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
