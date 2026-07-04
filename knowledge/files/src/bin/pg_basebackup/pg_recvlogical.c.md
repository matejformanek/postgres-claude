# `src/bin/pg_basebackup/pg_recvlogical.c`

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`
(quote-escaping claim re-verified at `a75bd485b5ea`, 2026-06-17 — see
"Plugin output trust" below: the `-o` not-escaped issue was fixed there.)

## Purpose

Standalone client for logical-decoding streams. Three actions on a
named logical replication slot: `--create-slot`, `--start`,
`--drop-slot`. While streaming, it writes the output plugin's bytes
verbatim to a file (or stdout), separated by newlines, fsyncs on an
interval, and feeds back write/flush LSNs to the server.
`[from-comment]` (header 1-11).

## Role in the pipeline

```
primary walsender + output plugin ── COPY BOTH (logical) ──> pg_recvlogical
                                                                │
                                                                └── outfile (append, with \n between records)
```

Unlike `pg_receivewal` it speaks the **logical** START_REPLICATION
form and the COPY payload is plugin-defined (text or binary).
pg_recvlogical does **not** interpret the bytes — it just writes
them. Default plugin is `test_decoding` (line 61).

## Key functions

| Function                  | Lines     | Notes |
|---------------------------|-----------|-------|
| `main`                    | 692-1045  | Option parse, action dispatch, outer reconnect loop. |
| `StreamLogicalLog`        | 220-663   | `START_REPLICATION SLOT ... LOGICAL` + main read/write loop. |
| `sendFeedback`            | 128-178   | Builds `StandbyStatusUpdate` reply. Tracks last_written / last_fsync. |
| `flushAndSendFeedback`    | 1054-1064 | Wraps `OutputFsync` + `sendFeedback`. |
| `OutputFsync`             | 187-215   | fsync outfile if regular file; updates `output_fsync_lsn`. |
| `prepareToTerminate`      | 1070-1098 | Best-effort `PQputCopyEnd`+`PQflush`, then verbose log line. |
| `sigexit_handler` / `sighup_handler` | 674-688 | SIGINT/SIGTERM → abort; SIGHUP → reopen outfile. |

## State / globals

```
outfile, verbose, two_phase, failover, noloop,
standby_message_timeout, fsync_interval,
startpos, endpos,
do_create_slot, slot_exists_ok, do_start_slot, do_drop_slot,
replication_slot, options[], noptions, plugin,
outfd, time_to_abort, stop_reason, output_reopen,
output_isfile, output_last_fsync, output_needs_fsync,
output_written_lsn, output_fsync_lsn
```
(lines 43-72). `outfd` is the live file descriptor; `output_isfile`
gates whether `fsync()` is meaningful (set by `fstat` + `S_ISREG`,
line 358).

## Phase D notes

### Output path safety

- `outfile` comes from `-f / --file`. Special-case `"-"` means
  stdout (line 341). Otherwise opened with `O_CREAT | O_APPEND |
  O_WRONLY | PG_BINARY` and mode `pg_file_create_mode` (line 344).
- No symlink check. If `outfile` already exists as a symlink, follow
  it. With `O_APPEND` an attacker symlink to a victim file would
  cause logical-decoding bytes to be appended there. The user runs
  pg_recvlogical, so the victim file must be writable by that user
  anyway — typical Unix consequence, but document it.
  `[ISSUE-path-traversal: outfile opened without O_NOFOLLOW, symlink swap before open could redirect append (maybe)]`
- SIGHUP triggers reopen (line 327-333) — careful interleaving with
  rotation; the previous fd is fsynced before close
  (`OutputFsync(now)` line 330) so no data loss.

### Plugin output trust

- pg_recvlogical never parses the WALData payload contents. It only
  reads the 25-byte CopyData header (lines 521-527: msgtype +
  dataStart + walEnd + sendTime) and writes the remainder verbatim
  followed by a literal `'\n'` (lines 562-587). `[verified-by-code]`
- That trailing `'\n'` (line 582) means the on-disk format assumes
  the plugin's record itself contains no embedded LF — true for
  `test_decoding` but **not enforced**. A plugin emitting binary
  containing 0x0A will be silently mis-parsed by downstream
  consumers that split on newline.
  `[ISSUE-wire-protocol: assumed newline-delimited output not enforced; binary plugin output mis-frames silently (maybe)]`
- **(Resolved upstream in `a75bd485b5ea`.)** The slot name, `-o` option
  names, and `-o` option values are now quote-escaped: the
  `START_REPLICATION SLOT` builder calls `AppendQuotedIdentifier(query,
  replication_slot)` (line 252), `AppendQuotedIdentifier(query,
  options[i*2])` (line 266) for each option name, and
  `AppendQuotedLiteral(query, options[i*2+1])` (line 272) for each option
  value. Previously these were raw `appendPQExpBuffer(query, "\"%s\"" / "
  '%s'", …)` interpolations with **no** escaping for an embedded `"` / `'`
  — the footgun this doc used to flag. `[verified-by-code, pg_recvlogical.c:250-273 @ a75bd485b5ea]`
  `[ISSUE-wire-protocol: -o option name/value not quote-escaped — RESOLVED a75bd485b5ea]`

### fsync discipline

- Default `fsync_interval = 10s` (line 49). `OutputFsync` is the only
  fsync site; it short-circuits if `output_isfile` is false (stdout
  or tty, line 209-211) and if `output_needs_fsync` is false.
- The `output_fsync_lsn` advances **inside `OutputFsync`** before
  the fsync (line 192). If the fsync subsequently `pg_fatal`s
  (line 213-214), the feedback message reporting that flush LSN was
  not actually sent — recovery-side OK because the connection dies,
  but the static `last_fsync_lsn` in `sendFeedback` could lie if
  we somehow continued. We don't continue, so it's safe.
  `[verified-by-code]`
- `fsync_interval <= 0` short-circuits before clearing
  `output_needs_fsync` (line 201) — odd but harmless.

### Replication-slot lifecycle

- Slot create: `CreateReplicationSlot(...)` line 1003, passing
  `two_phase` and `failover` from CLI.
- Slot drop: line 993. Both are pure short-circuits when
  `--start` is also passed (start runs after create on same conn,
  line 1010-1011, with `startpos` reset to invalid so the slot's own
  confirmed_flush is used).
- Combination guards live in main lines 906-942: `--drop-slot`
  excludes `--create-slot`/`--start`; `--enable-two-phase` and
  `--enable-failover` are only valid with `--create-slot`.
- SIGINT during streaming: `prepareToTerminate` sends `PQputCopyEnd`
  best-effort. The slot itself stays on the server; consumer is
  expected to drop it explicitly. Same operational gotcha as
  pg_receivewal.

### `--two-phase` / `--failover` state-transition

- Both are slot-create-time flags. They are validated to be
  `--create-slot`-only (lines 927-942) and then passed straight
  through to `CreateReplicationSlot` (line 1004-1005). There is no
  CLI to *advance* an existing slot to two-phase or to set failover
  later; that lives in server-side SQL (`pg_replication_slot_advance`,
  `ALTER_REPLICATION_SLOT`).
  `[ISSUE-state-transition: no CLI path to flip two_phase / failover on an existing slot — must drop+recreate (maybe)]`

### Password handling

- Same as pg_receivewal — `GetConnection()` from streamutil.c does
  it. pg_recvlogical never touches the password string. See B4.

### Resumption semantics

- Start LSN: explicit `-I/--startpos` overrides slot state; otherwise
  `startpos = InvalidXLogRecPtr` so the server picks
  `confirmed_flush_lsn`.
- On reconnect inside the outer `while(true)` loop (1014-1044), the
  `startpos` global has been advanced by `OutputFsync`
  (line 199) so we resume from the last fsynced LSN. This implicit
  global mutation in a "sender" function is the kind of pattern that
  trips up readers. `[from-comment]` (lines 194-200 explain it).

## Potential issues

- `[ISSUE-path-traversal: outfile opened without O_NOFOLLOW (maybe)]`
- `[ISSUE-wire-protocol: newline-as-record-separator not enforced against plugin output (maybe)]`
- ~~`[ISSUE-wire-protocol: -o NAME=VALUE not quote-escaped into START_REPLICATION (low)]`~~ — RESOLVED upstream in `a75bd485b5ea` (now via `AppendQuotedIdentifier`/`AppendQuotedLiteral`).
- `[ISSUE-state-transition: no CLI to alter two_phase/failover on existing slot (maybe)]`
- `[ISSUE-undocumented-invariant: SIGINT during stream leaves the slot on the server (low)]`
- `[ISSUE-info-disclosure: verbose mode prints every flush LSN with slot name (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
