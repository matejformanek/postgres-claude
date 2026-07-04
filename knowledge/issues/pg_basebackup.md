# Issues — `pg_basebackup` (src/bin/pg_basebackup/)

Per-subsystem issue register for pg_basebackup + pg_receivewal +
pg_recvlogical + pg_createsubscriber. See `knowledge/issues/README.md`
for tag taxonomy.

**Parent docs:** `knowledge/files/src/bin/pg_basebackup/*` (12 docs).

**Source:** 53 entries surfaced 2026-06-03 by the A4 foreground sweep
(batches B4 + part of B5). Each is mirrored in the corresponding
per-file doc's `## Potential issues` block.

pg_basebackup is the **backup-stream trust boundary on the receiver
side**. It receives bytes from a server it has authenticated to but
does not necessarily trust the file-system layout, paths, or scalar
configuration values that come back. This is **the mirror image of
A3's pg_dump "trust the source" finding**: pg_dump trusts the *archive
file on disk it reads back* (third-party tampering window); pg_basebackup
trusts the *server it streams from* (compromise/buggy window).

---

## P0 — Phase D candidates

### Server-controlled paths and modes (the backup-stream trust cluster)

The structural Phase D headline for this directory. pg_basebackup blindly
accepts server-supplied absolute paths, modes, and segment sizes — the
local filesystem permissions of the running user are the only filter.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_basebackup.c:1145-1150 | trust-boundary | likely | Server-controlled `spclocation` becomes an output directory; only `-T olddir=newdir` user mapping filters it. If the user has no matching `-T` for a tablespace, a hostile/buggy server announcing `/etc/...` would extract there | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | pg_basebackup.c:1357 | trust-boundary | maybe | `archive_name` sanitized for `..`/`/`/`\`/leading-`.`, but the actual member-name validation in the tar stream is delegated to `fe_utils/astreamer_tar.c` — out of scope for this batch | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | streamutil.c:367-394 | trust-boundary | likely | Server-reported `data_directory_mode` (via `SHOW data_directory_mode`) sets the local umask for ALL files pg_basebackup creates; a server announcing `0777` would produce world-readable backups; validation is only `sscanf` success | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/streamutil.c.md |
| 2026-06-03 | streamutil.c | trust-boundary | maybe | Server-reported `wal_segment_size` becomes the local WAL framing assumption — capped by `IsValidWalSegSize` to 1 GiB (cap mitigates) | open | knowledge/files/src/bin/pg_basebackup/streamutil.c.md |
| 2026-06-03 | pg_basebackup.c:2858 | path-traversal | maybe | `--waldir` value is NOT validated as absolute before `symlink(xlog_dir, linkloc)` | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | pg_basebackup.c | trust-boundary | nit | Server-driven progress messages contain server-supplied text — terminal-escape injection echo | open | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | astreamer_inject.c | trust-boundary | maybe | Server-controlled tar member name decides where injected content lands (recovery signal files); receives tablespace map + recovery conf injection | open | knowledge/files/src/bin/pg_basebackup/astreamer_inject.c.md |
| 2026-06-03 | astreamer_inject.c | undocumented-invariant | nit | Hard-coded `uid=04000`, `gid=02000` in injected tar headers | open | knowledge/files/src/bin/pg_basebackup/astreamer_inject.c.md |
| 2026-06-03 | astreamer_inject.c | undocumented-invariant | nit | `member.size += recoveryconfcontents->len` arithmetic uncommented (length-update invariant) | open | knowledge/files/src/bin/pg_basebackup/astreamer_inject.c.md |
| 2026-06-03 | receivelog.c | trust-boundary | maybe | Server can announce arbitrary `next_tli` and next-startpos; sanity-checked but allows upward jumps | open | knowledge/files/src/bin/pg_basebackup/receivelog.c.md |
| 2026-06-03 | receivelog.c | trust-boundary | maybe | Timeline-history filename comes from server response | open | knowledge/files/src/bin/pg_basebackup/receivelog.c.md |
| 2026-06-03 | receivelog.c | trust-boundary | maybe | WAL data `dataStart` and offset relationship server-derived; consistency not independently verified | open | knowledge/files/src/bin/pg_basebackup/receivelog.c.md |
| 2026-06-03 | pg_receivewal.c | trust-boundary | maybe | Target dir trusts any 24-hex-char filename as a resumable WAL segment; hostile pre-seeded file shifts `FindStreamingStart` LSN | open | knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md |
| 2026-06-03 | pg_recvlogical.c | path-traversal | maybe | Outfile opened without `O_NOFOLLOW`; symlink swap before open could redirect append | open | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md |

**Phase D pitch — coordinated trust hardening:**
1. Validate `spclocation` against the supplied `-T` mapping table; **reject any unmapped tablespace** instead of using server path as-is.
2. Cap `data_directory_mode` (reject any mode with world-writable bits; clamp to `0700`/`0750`).
3. Require `--waldir` be an absolute path.
4. Add `O_NOFOLLOW` to pg_recvlogical's outfile open.
5. Document the `astreamer_tar.c` member-name sanitization and audit it (it's the next read — see "Corpus gaps surfaced" below).

### Secret-scrub gaps (mirror of A2 libpq + A4 psql findings)

Same gap as libpq and psql.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | streamutil.c | secret-scrub | likely | `password` stored in process-global static; freed without `explicit_bzero` | open | knowledge/files/src/bin/pg_basebackup/streamutil.c.md |
| 2026-06-03 | streamutil.c | undocumented-invariant | nit | `simple_prompt(prompt, echo=false)` is the only password capture path | open | knowledge/files/src/bin/pg_basebackup/streamutil.c.md |
| 2026-06-03 | pg_basebackup.c | secret-scrub | likely | `recoveryconfcontents` (PQExpBuffer) contains generated `primary_conninfo` including password if user passes one; injected into tar stream and written to recovery configuration in the new cluster | open | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | pg_createsubscriber.c:1460,214,47-48 | secret-scrub | likely | Publisher conninfo (may include password) written to `pg_createsubscriber.conf` inside subscriber data dir; on exit renamed to `.disabled` but NOT shredded — intentionally retained "for debugging" | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |

### pg_createsubscriber state-transition risks

New tool; multi-step state machine (stop standby → promote → create subs
→ drop slots) with weak rollback.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_createsubscriber.c | state-transition | likely | Partial failure midway through `setup_publisher` leaves publisher in inconsistent state | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |
| 2026-06-03 | pg_createsubscriber.c | state-transition | likely | `recovery_ended = true` means the standby has been irreversibly promoted; later failure cannot be rolled back | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |
| 2026-06-03 | pg_createsubscriber.c | state-transition | maybe | `modify_subscriber_sysid` writes new sysid; failure window between sysid write and other catalog updates | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |
| 2026-06-03 | pg_createsubscriber.c | trust-boundary | maybe | `pg_log_standby_snapshot()` called on the publisher — assumes publisher trustworthiness | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |
| 2026-06-03 | pg_createsubscriber.c | trust-boundary | nit | `find_other_exec` for pg_ctl + pg_resetwal trusts $PATH / argv[0] resolution | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |
| 2026-06-03 | pg_createsubscriber.c | undocumented-invariant | nit | Pidfile-based "is standby running" check is racy | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |
| 2026-06-03 | pg_createsubscriber.c | wire-protocol | nit | Subscriber port has no clash detection beyond the bind-fails-noisy path | open | knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md |

### Tar handling + DoS

Echo of A3's pg_dump tar findings.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | walmethods.c | tar-parsing | nit | Tar method silently inherits ustar's 11-octal-digit 8 GiB size cap; not reachable today because `IsValidWalSegSize` caps WAL segment at 1 GiB; mirror of A3 pg_dump finding | open | knowledge/files/src/bin/pg_basebackup/walmethods.c.md |
| 2026-06-03 | walmethods.c | dos | maybe | No compression-ratio guard on incoming WAL data — decompression bomb | open | knowledge/files/src/bin/pg_basebackup/walmethods.c.md |
| 2026-06-03 | walmethods.c | undocumented-invariant | nit | `tarChecksum` of header written WITHOUT the checksum field itself zeroed first (POSIX requirement); review for compliance | open | knowledge/files/src/bin/pg_basebackup/walmethods.c.md |
| 2026-06-03 | walmethods.c | state-transition | maybe | `tar_close` patches the header in place after write — fsync window | open | knowledge/files/src/bin/pg_basebackup/walmethods.c.md |
| 2026-06-03 | walmethods.c | undocumented-invariant | nit | tar method's `existsfile` always returns false (assumes target dir empty); contract undocumented | open | knowledge/files/src/bin/pg_basebackup/walmethods.c.md |
| 2026-06-03 | pg_basebackup.c | tar-parsing | maybe | 8 GiB tar member size cap inherited from the standard tar parser | open | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | pg_basebackup.c | dos | maybe | Server-compressed tar with client-side extraction passes the compressed bytes through `astreamer_zstd_decompressor`/etc. — no decompression-ratio bound | open | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | pg_basebackup.c | state-transition | nit | bg-child `atexit` can race with bg-pipe write | open | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |
| 2026-06-03 | pg_basebackup.c | state-transition | nit | pg_wal symlink created BEFORE BaseBackup connection established | open | knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md |

---

## P1 — Wire-protocol invariants & receivelog state

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_recvlogical.c:582 | wire-protocol | maybe | Newline-as-record-separator not enforced against plugin output; binary-emitting plugin produces mis-framed file silently | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md |
| 2026-06-03 | pg_recvlogical.c | wire-protocol | nit | `-o NAME=VALUE` plugin option not quote-escaped into `START_REPLICATION` command | landed (a75bd485b5ea, triaged 2026-06-17 — now via `AppendQuotedIdentifier`/`AppendQuotedLiteral`) | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md |
| 2026-06-03 | pg_recvlogical.c | state-transition | maybe | No CLI to flip `two_phase`/`failover` on an existing slot — must drop+recreate | open | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md |
| 2026-06-03 | pg_recvlogical.c | undocumented-invariant | nit | SIGINT during stream leaves slot on the server | open | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md |
| 2026-06-03 | pg_recvlogical.c | info-disclosure | nit | Verbose mode prints every flush LSN with slot name | open | knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md |
| 2026-06-03 | pg_receivewal.c | undocumented-invariant | nit | SIGINT leaves replication slot on server — wedges WAL retention if archiver host dies | open | knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md |
| 2026-06-03 | pg_receivewal.c | stale-todo | nit | ZSTD WAL compression rejected as not-yet-supported despite ZSTD basebackup support | open | knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md |
| 2026-06-03 | pg_receivewal.c | dos | nit | 5-second `pg_usleep` in reconnect loop delays signal handling | open | knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md |
| 2026-06-03 | pg_receivewal.c | info-disclosure | nit | Verbose mode logs every keepalive/segment boundary at INFO; observable WAL LSN cadence | open | knowledge/files/src/bin/pg_basebackup/pg_receivewal.c.md |
| 2026-06-03 | receivelog.c | state-transition | maybe | Open file left in `.partial` state after error path | open | knowledge/files/src/bin/pg_basebackup/receivelog.c.md |
| 2026-06-03 | receivelog.c | undocumented-invariant | nit | `static` globals (`walfile`, etc.) document the single-stream-at-a-time invariant by accident, not by comment | open | knowledge/files/src/bin/pg_basebackup/receivelog.c.md |

---

## P2 — Stale TODOs

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | receivelog.c:541 | stale-todo | nit | `FIXME: we might send it ok, but get an error` on the TIMELINE_HISTORY error path (mis-cited as pg_basebackup.c:542 at seed — the FIXME is in receivelog.c, absent from pg_basebackup.c at seed anchor 4b0bf0788b0 and current) | open · triaged 2026-07-04 | knowledge/files/src/bin/pg_basebackup/receivelog.c.md |

---

## Corpus gaps surfaced (out of batch)

The next read for completing the pg_basebackup trust-audit:

- `src/fe_utils/astreamer_tar.c` — actual tar member parsing, where the `..`/`/` filter happens (or doesn't) on inner-member names. Cited by pg_basebackup.c:1357 but not audited.
- `src/fe_utils/astreamer_zstd.c` / `astreamer_gzip.c` / `astreamer_lz4.c` — compression decompressors; need the compression-ratio bound audit.
- `src/backend/replication/basebackup_*.c` — server side of the wire protocol; pairs with this register to close the both-sides trust model.

---

## What this register is mirror-image to

| pg_dump (A3) trust model | pg_basebackup (A4) trust model |
|---|---|
| Trust the archive file (writer authenticated, file could be tampered) | Trust the server (authenticated, server could be compromised/buggy) |
| `_printTocEntry` writes `te->defn` verbatim → SQL replay at restore | streamutil writes server `wal_segment_size`/`data_directory_mode` verbatim → local config |
| Custom-format malloc of attacker-chosen size | Tar parser delegates inner-member-name validation to astreamer_tar.c (next audit) |
| Directory-format path-traversal via `te->filename` | `spclocation` + `archive_name` paths from server |
| `pg_dumpall expand_dbname=true` redirect via `datname` | `pg_createsubscriber` `find_other_exec` trusts $PATH |

Both have the **same coordinated Phase D hardening shape**: enumerate
the bytes that flow from the upstream (file or wire), reject any that
imply a privileged outcome (absolute paths, world-writable modes,
size-prefix overflow, `..` traversal). The two patches likely belong
in the same series.

---

## Summary by tag type

| Type | Count |
|---|---:|
| trust-boundary | 17 |
| secret-scrub | 4 |
| state-transition | 8 |
| undocumented-invariant | 10 |
| wire-protocol | 4 |
| dos | 4 |
| tar-parsing | 2 |
| path-traversal | 1 |
| info-disclosure | 2 |
| stale-todo | 2 |
| **Total** | **54** (one entry counted in two cells where multi-tagged) |

Severity headline: ~6 `likely`, ~17 `maybe`, rest `nit`.
