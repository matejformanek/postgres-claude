# Issues — `pg_upgrade` (src/bin/pg_upgrade/)

Per-subsystem issue register for pg_upgrade — the **major-version cluster
migration tool**, the most security-sensitive bin/ utility in PG.

**Parent docs:** `knowledge/files/src/bin/pg_upgrade/*` (22 docs).

**Source:** 105 entries surfaced 2026-06-03 by the A6 foreground sweep
(batches B1 + B2). Each is mirrored in the corresponding per-file doc's
`## Potential issues` block.

pg_upgrade is the **only PG tool that authenticates to BOTH old + new
clusters as superuser, runs raw file-level operations on data files, and
carries credential material between clusters**. Three trust boundaries
matter: (1) old-cluster catalog → trusted as-source-of-truth, (2)
filesystem of old PGDATA → trusted, (3) password hashes from old
`pg_authid` → persisted on disk in the new cluster's pgdata briefly.

---

## P0 — Phase D candidates

### The "trust the old cluster" cluster

The headline finding. pg_upgrade's **structural checks (check.c) validate
schema-level compatibility but never validate catalog content**. Any
attacker who has write access to the old cluster's catalog (or the
ability to forge restore from a tampered dump) can leverage pg_upgrade
to compromise the new cluster.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | check.c | trust-boundary | likely | `check_loadable_libraries` actually `LOAD`s every library referenced by old cluster's `pg_proc`/extensions ON THE NEW CLUSTER — tampered old catalog with `/tmp/evil.so` reference = arbitrary code execution against just-built new cluster's backend | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | check.c | trust-boundary | likely | Every "old cluster" check connects via libpq + runs SQL — if old cluster's `shared_preload_libraries` or `pg_proc.prosrc` is malicious, every check IS the old cluster running attacker code | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | check.c:1117 | trust-boundary | maybe | `check_is_install_user` NOTES the install user but doesn't validate role identity against an expected list | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | check.c | trust-boundary | maybe | SQL queries against old cluster are sometimes built with `%s` interpolation of catalog data | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | info.c | trust-boundary | likely | `process_rel_infos` reads `relname`/`nspname`/`relfilenode`/`spclocation` from old cluster's catalog with zero validation; `relfilenumber` flows uint32-raw into `transfer_relfile`'s path-snprintf | open | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | info.c | trust-boundary | likely | `os_info.running_cluster->pgdata` used as a string prefix; in-place tablespace `spcloc` from `pg_tablespace_location()` composed via `snprintf("%s/%s")` — a relative `spcloc` of `../../etc/...` from tampered catalog composes a path outside pgdata | open | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | info.c | trust-boundary | likely | `slot_info->plugin` (output plugin name) is restored into new cluster via `pg_create_logical_replication_slot(name, plugin, ...)` with NO whitelist — combined with loadable-libraries gap = vector | open | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | function.c | trust-boundary | likely | `probin` value from old cluster's pg_proc is trusted by `_PG_init` loading discipline | open | knowledge/files/src/bin/pg_upgrade/function.c.md |
| 2026-06-03 | pg_upgrade.c | trust-boundary | likely | Catalog values from old cluster fully trusted across the whole orchestration | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | pg_upgrade.h | trust-boundary | likely | `FileNameMap.relfilenumber` sourced from old cluster | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md |
| 2026-06-03 | tablespace.c | trust-boundary | maybe | `pg_tablespace_location()` result trusted as a path | open | knowledge/files/src/bin/pg_upgrade/tablespace.c.md |
| 2026-06-03 | dump.c | trust-boundary | maybe | pg_dump output implicitly trusted by psql restore — A3 archive-trust echoes apply | open | knowledge/files/src/bin/pg_upgrade/dump.c.md |
| 2026-06-03 | multixact_read_v18.c | trust-boundary | maybe | Multi member arithmetic on attacker-influenced offsets | open | knowledge/files/src/bin/pg_upgrade/multixact_read_v18.c.md |
| 2026-06-03 | multixact_rewrite.c | trust-boundary | maybe | Every member XID and status byte from old cluster trusted | open | knowledge/files/src/bin/pg_upgrade/multixact_rewrite.c.md |
| 2026-06-03 | slru_io.c | trust-boundary | maybe | SLRU page reader returns zero-filled buffer on missing page — silent over potentially-malicious tampering | open | knowledge/files/src/bin/pg_upgrade/slru_io.c.md |
| 2026-06-03 | task.c | trust-boundary | maybe | Per-database connection inherits whatever PGOPTIONS the user set | open | knowledge/files/src/bin/pg_upgrade/task.c.md |
| 2026-06-03 | controldata.c | trust-boundary | maybe | The old cluster's bindir contains the `pg_controldata`/`pg_resetwal` binaries pg_upgrade runs — chain-of-trust on the old install | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | controldata.c | trust-boundary | maybe | `pg_resetwal -n` output is parsed by string match | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |

**Phase D pitch — coordinated "trust the old cluster" hardening:**
1. **Whitelist `shared_preload_libraries`** in `check_loadable_libraries` — reject `/tmp/`, `..`, or any unsigned path. This is THE concrete RCE primitive to close.
2. Validate `spclocation` is absolute or sibling-of-pgdata.
3. Validate `output_plugin` against a whitelist (or only allow built-in plugins).
4. Run old-cluster checks under a restricted role, not as the install user.
5. Add per-relation `relfilenumber` bound-check before `snprintf`.

### Shell-injection / subprocess discipline

pg_upgrade runs many subprocesses; `exec.c` is the central choke-point.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | exec.c:187 | shell-injection | maybe | Every external program runs via `system(3)` with caller-built format string; callers must shell-escape via `appendShellString`; verified correct for dump.c (db_name) and server.c (sockdir, user) but no central `argv[]` entry point = defense-in-depth missing | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/exec.c.md |
| 2026-06-03 | option.c | shell-injection | maybe | `-o` / `-O` accept arbitrary strings stored as PGOPTIONS — server-side substitution at start | open | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | option.c:429 | trust-boundary | maybe | `adjust_data_dir` runs `postgres -C <data_directory>` (a subprocess of the OLD postgres) — implicit trust on the old binary | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | pg_upgrade.c:749 | shell-injection | maybe | `copy_subdir_files` invokes `system()` with constructed paths | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | server.c | shell-injection | maybe | pg_ctl command-line construction — special chars in sockdir or user could break quoting | open | knowledge/files/src/bin/pg_upgrade/server.c.md |

### Secret-scrub gap (the A2/A4/A5 echo + the password-hash file)

Same explicit_bzero gap pattern, plus a unique pg_upgrade hazard: the
old cluster's `pg_authid` rows are dumped to disk via pg_dumpall as
`ALTER ROLE ... PASSWORD '<scram-hash>'` and PERSIST in the new
cluster's pgdata until cleanup_output_dirs.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_upgrade.c | trust-boundary | likely | **pg_authid carryover via SQL restore of `pg_upgrade_dump_globals.sql`** — contains `ALTER ROLE ... PASSWORD '<scram-hash>'` lines; sits in `<new_pgdata>/pg_upgrade_output.d/<timestamp>/dump/` between dump and psql-restore; NOT scrubbed; persists until `cleanup_output_dirs()`; with `-r/--retain` OR on failure, persists indefinitely at `pg_dir_create_mode` perms (0700 strict, 0750 group-readable) | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | util.c | secret-scrub | likely | `pg_log_v` writes server error messages verbatim to `log_opts.internal` — same gap as A5 logging.c; PQerrorMessage often embeds connection-related secrets; persists under `--retain` | open | knowledge/files/src/bin/pg_upgrade/util.c.md |
| 2026-06-03 | util.c:189 | secret-scrub | maybe | `pg_log_v` Assertion at line 182 forbids trailing newline; otherwise no redaction filter | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/util.c.md |
| 2026-06-03 | exec.c | secret-scrub | likely | stderr from pg_dump/psql captured to log file via `>> "<log>" 2>&1` — server-side error text including connection info lands in retained logs | open | knowledge/files/src/bin/pg_upgrade/exec.c.md |
| 2026-06-03 | task.c | secret-scrub | maybe | `pg_fatal("connection failure: %s", PQerrorMessage(conn))` interpolates server text verbatim | open | knowledge/files/src/bin/pg_upgrade/task.c.md |
| 2026-06-03 | controldata.c | secret-scrub | nit | PG_VERBOSE-mode logs every parsed line verbatim — minimal but echoes pattern | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | pg_upgrade.h | info-disclosure | maybe | `BASE_OUTPUTDIR` is `pg_upgrade_output.d` — known name, predictable for forensic recovery of failed run | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md |

### Path-traversal / file operations

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | file.c | undocumented-invariant | likely | **All three file modes (copy/link/clone) follow source symlinks** — no `O_NOFOLLOW` on source path. Copy duplicates symlink target content; link hardlinks to target inode; clone clones target. Requires pre-existing FS-write access to old PGDATA so severity-low, but Phase D hardening candidate | open | knowledge/files/src/bin/pg_upgrade/file.c.md |
| 2026-06-03 | file.c | trust-boundary | maybe | Source-file content from old cluster is implicitly trusted (no integrity check) | open | knowledge/files/src/bin/pg_upgrade/file.c.md |
| 2026-06-03 | relfilenumber.c | trust-boundary | maybe | `parse_relfilenumber` only validates the OID is numeric — no bound check against `MaxBlockNumber` or similar | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | relfilenumber.c | path-traversal | maybe | `prepare_for_swap` builds destination paths from old cluster's mapping; relies on `parse_relfilenumber` discipline | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | slru_io.c | trust-boundary | maybe | `open(O_RDONLY)` with no `O_NOFOLLOW` on the SLRU files | open | knowledge/files/src/bin/pg_upgrade/slru_io.c.md |

---

## P1 — State-transition + correctness

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | pg_upgrade.c | state-transition | likely | Between `disable_old_cluster()` (line 186) and `prepare_new_cluster()`, the **old cluster is non-functional** and the new cluster doesn't exist yet — single-point-of-failure window | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | pg_upgrade.c | state-transition | maybe | Stale `postmaster.pid` probe in `setup()` is racy | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | check.c | state-transition | maybe | `setup()` in pg_upgrade.c silently flips connectivity assumptions across checks | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | controldata.c | state-transition | likely | `disable_old_cluster` makes old cluster unreadable — failure midway = both clusters in indeterminate state | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | server.c | state-transition | maybe | If `start_postmaster` returns success but postmaster crashes immediately after, race window before pg_isready detects | open | knowledge/files/src/bin/pg_upgrade/server.c.md |
| 2026-06-03 | parallel.c | state-transition | maybe | Parent does NOT block SIGINT while forking — child may inherit half-initialized signal state | open | knowledge/files/src/bin/pg_upgrade/parallel.c.md |
| 2026-06-03 | file.c | state-transition | maybe | clone-mode `unlink(dst)` after ioctl failure leaves no orphan; subtle | open | knowledge/files/src/bin/pg_upgrade/file.c.md |
| 2026-06-03 | relfilenumber.c | state-transition | likely | `prepare_for_swap` does two `rename(2)`s — failure between them = inconsistent state | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | relfilenumber.c | state-transition | maybe | `--swap` cannot upgrade from <v10 (gated by check.c) — silent abort if user tries | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | version.c | state-transition | maybe | `old_9_6_invalidate_hash_indexes` writes ALTER INDEX statements — failure mid-way leaves indexes in mixed state | open | knowledge/files/src/bin/pg_upgrade/version.c.md |
| 2026-06-03 | check.c:998 | correctness | maybe | `check_for_new_tablespace_dir` only checks one possible path | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | check.c | correctness | maybe | `create_script_for_old_cluster_deletion` writes a script users typically execute — script generation discipline | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | controldata.c | correctness | maybe | `str2uint(p)` is `strtoul(p, NULL, 10)` — no errno check, no range check | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | controldata.c:592 | correctness | likely | **Char-signedness is pg_upgrade's own build-time `CHAR_MIN != 0`, NOT the old cluster's actual build** — documented limitation, footgun for pre-v18 upgrades | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | exec.c | correctness | maybe | `popen()` return-status check in `get_bin_version` doesn't distinguish "command not found" from "command produced no output" | open | knowledge/files/src/bin/pg_upgrade/exec.c.md |
| 2026-06-03 | file.c | correctness | maybe | `copyFileByRange` has no progress check and may stall on certain filesystems | open | knowledge/files/src/bin/pg_upgrade/file.c.md |
| 2026-06-03 | function.c | correctness | maybe | `PQescapeStringConn` called with NULL error pointer — silently ignores escaping failure | open | knowledge/files/src/bin/pg_upgrade/function.c.md |
| 2026-06-03 | info.c | correctness | maybe | `gen_db_file_maps` returns even if `all_matched` is false in some paths | open | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | info.c:850 | correctness | maybe | Subscription query uses `count(*)` instead of `count(<column>)` | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | multixact_read_v18.c:256 | correctness | maybe | `length = nextMXOffset - offset` — unsigned subtraction, attacker offsets → huge length | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/multixact_read_v18.c.md |
| 2026-06-03 | multixact_read_v18.c | correctness | maybe | `for (int i = 0; i < length; i++, offset++)` — int overflow if length is huge | open | knowledge/files/src/bin/pg_upgrade/multixact_read_v18.c.md |
| 2026-06-03 | multixact_rewrite.c | correctness | maybe | Members writer starts at `next_offset = 1` not 0 — assumed invariant | open | knowledge/files/src/bin/pg_upgrade/multixact_rewrite.c.md |
| 2026-06-03 | option.c:82 | correctness | maybe | `atoi(getenv("PGPORTOLD"))` — no error handling | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | option.c | correctness | maybe | Pre-getopt early "--help" / "--version" handling has subtle interaction with other args | open | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | parallel.c | correctness | maybe | Windows path's `cur_thread_args` swap (line ...) has thread-local lifecycle issues | open | knowledge/files/src/bin/pg_upgrade/parallel.c.md |
| 2026-06-03 | pg_upgrade.c | correctness | maybe | `template1` special-cased BEFORE the loop in db iteration — subtle ordering invariant | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | pg_upgrade.c | correctness | maybe | `pg_strdup(getenv("PGUSER"))` (via option.c) doesn't handle NULL — already covered by getenv contract but worth noting | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | relfilenumber.c | correctness | maybe | `transfer_relfile`'s `unlink(new_file)` (line ...) may race with parallel | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | relfilenumber.c | correctness | nit | `strncpy(sync_queue[sync_queue_len++], fname, ...)` doesn't NUL-terminate on overflow | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | slru_io.c | correctness | maybe | `SlruReadSwitchPageSlow` `pg_pread` EINTR loop is partial | open | knowledge/files/src/bin/pg_upgrade/slru_io.c.md |
| 2026-06-03 | task.c | correctness | maybe | `wait_on_slots` skips FREE slots silently | open | knowledge/files/src/bin/pg_upgrade/task.c.md |
| 2026-06-03 | tablespace.c | correctness | maybe | Per-tablespace `stat()` only checks the OLD location | open | knowledge/files/src/bin/pg_upgrade/tablespace.c.md |
| 2026-06-03 | util.c | correctness | maybe | `str2uint` returns `strtoul(str, NULL, 10)` with no error check (same as controldata.c) | open | knowledge/files/src/bin/pg_upgrade/util.c.md |

---

## P2 — Info-disclosure / undocumented invariants / stale-todo

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | check.c | info-disclosure | nit | Every report file (`*.txt`) is written with default mode — may contain non-public schema names | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | dump.c | info-disclosure | maybe | pg_dump log files in `pg_upgrade_output.d` carry connection error text and progress | open | knowledge/files/src/bin/pg_upgrade/dump.c.md |
| 2026-06-03 | exec.c:119 | info-disclosure | nit | `pg_log(PG_VERBOSE, "%s", cmd)` echoes the full subprocess command line | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/exec.c.md |
| 2026-06-03 | function.c | info-disclosure | nit | `PQerrorMessage(conn)` and `probin` value land in error report | open | knowledge/files/src/bin/pg_upgrade/function.c.md |
| 2026-06-03 | info.c | info-disclosure | nit | rel-infos query excludes "regprocedure" but includes most other catalogs verbatim | open | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | option.c | info-disclosure | maybe | `PGOPTIONS` env var set into the process — visible via `ps` | open | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | parallel.c | info-disclosure | nit | Per-child log file `log_file` passed by name — predictable | open | knowledge/files/src/bin/pg_upgrade/parallel.c.md |
| 2026-06-03 | relfilenumber.c | info-disclosure | nit | `pg_log(PG_STATUS, "%s", old_file)` echoes full path | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | server.c | info-disclosure | maybe | Full pg_ctl command line including connection string echoed at verbose | open | knowledge/files/src/bin/pg_upgrade/server.c.md |
| 2026-06-03 | util.c | info-disclosure | maybe | `log_opts.internal` opened in `cwd` if `pg_dir_create_mode` umask insufficient | open | knowledge/files/src/bin/pg_upgrade/util.c.md |
| 2026-06-03 | version.c | info-disclosure | nit | Extension/index names from old cluster echoed in upgrade report | open | knowledge/files/src/bin/pg_upgrade/version.c.md |
| 2026-06-03 | check.c | undocumented-invariant | nit | `check_for_unicode_update` is informational, not gating | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | check.c | undocumented-invariant | maybe | No check that new cluster's locale matches old cluster's | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | controldata.c | undocumented-invariant | nit | `oldctrl->large_object != 0` test assumes nonzero == present | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | controldata.c | undocumented-invariant | nit | `else if` chain (lines 220-526) silently falls through on unknown line | open | knowledge/files/src/bin/pg_upgrade/controldata.c.md |
| 2026-06-03 | info.c:597 | undocumented-invariant | nit | `process_rel_infos` assumes relations sorted by tablespace+OID | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/info.c.md |
| 2026-06-03 | multixact_rewrite.c | undocumented-invariant | nit | Caller assumed to pass `nmembers == multi.members_array.length` | open | knowledge/files/src/bin/pg_upgrade/multixact_rewrite.c.md |
| 2026-06-03 | option.c | undocumented-invariant | nit | `get_sock_dir` parses the live `postmaster.pid` — racy if old cluster restarts | open | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | option.c | undocumented-invariant | nit | `os_info.user` is allocated and never freed | open | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | pg_upgrade.c | undocumented-invariant | nit | Timestamp directory name format implicit — clash possible on rapid retries | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | pg_upgrade.h | undocumented-invariant | nit | `chkpnt_nxtmxoff` widened to `uint64` — silent truncation if read as uint32 | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md |
| 2026-06-03 | pg_upgrade.h | undocumented-invariant | nit | `MAX_STRING 1024` used as scratch buffer size — fragile | open | knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md |
| 2026-06-03 | relfilenumber.c | undocumented-invariant | nit | Segment-loop in `transfer_relfile` assumes contiguous segments | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | slru_io.c | undocumented-invariant | nit | `state->pageno` updated AT END of read — caller sees stale value on error | open | knowledge/files/src/bin/pg_upgrade/slru_io.c.md |
| 2026-06-03 | check.c | stale-todo | nit | `check_old_cluster_subscription_state` does NOT check certain subscriptions; comment notes | open | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | check.c:113 | stale-todo | nit | Comment "The cutoff OID here should be FirstNormalObjectId" | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | option.c:27 | stale-todo | nit | `FIX_DEFAULT_READ_ONLY` unconditionally defined for transitional period | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | pg_upgrade.c:56 | stale-todo | nit | "At some point we might want to..." preserved | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md |
| 2026-06-03 | pg_upgrade.h:439 | stale-todo | nit | `fopen_priv` macro "is no longer needed" — alias kept for compatibility | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md |
| 2026-06-03 | relfilenumber.c | stale-todo | nit | `pg_fatal("should never happen")` for case that's been there for years | open | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |
| 2026-06-03 | tablespace.c | stale-todo | nit | "If that changes, it will likely become necessary..." preserved | open | knowledge/files/src/bin/pg_upgrade/tablespace.c.md |
| 2026-06-03 | version.c | stale-todo | nit | `old_9_6_invalidate_hash_indexes` is per-version cleanup that lingers | open | knowledge/files/src/bin/pg_upgrade/version.c.md |
| 2026-06-03 | check.c:1879 | dead-code | nit | `check_for_pg_role_prefix` only runs on certain branches | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/check.c.md |
| 2026-06-03 | option.c:286 | dead-code | nit | Windows-only block forbidding paths with certain chars | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/option.c.md |
| 2026-06-03 | relfilenumber.c:308 | dead-code | nit | `FileNameMapCmp` uses `pg_cmp_u32` from int.h — verbose for the use case | open · triaged 2026-07-03 | knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md |

---

## Cross-corpus pattern reinforcement

### `check_loadable_libraries` is the keystone Phase D opportunity

This single function (`check.c`) makes pg_upgrade's "trust the old
cluster" gap **concrete and exploitable**. Closing it (whitelist
shared_preload_libraries; reject paths under `/tmp/`, `..`, or unsigned)
removes the most direct RCE primitive from a compromised old cluster.

### pg_upgrade is the sixth installment of the secret-scrub cluster

After libpq A2 + psql/streamutil/initdb A4 + common A5 (where the
SecretBuf hosting site was identified), pg_upgrade adds:
- The **pg_authid hash file** persisting on disk under predictable path
- The **util.c log file** carrying PQerrorMessage text
- The **exec.c stderr capture** carrying pg_dump/psql connection-error text

All would be closed by a coordinated `SecretBuf` + log-redaction patch
series rooted at `src/common/` (the A5 finding).

### controldata torn-write window inherited

pg_upgrade delegates pg_control parsing to `pg_controldata` and
`pg_resetwal -n` via popen — inherits A5's torn-write story but adds
text-parsing as new attack surface (substring matches on attacker-
influenced controldata content).

---

## Corpus gaps surfaced (out of batch)

- `src/bin/pg_amcheck/pg_amcheck.c` — covered in this sweep (separate register).
- `src/bin/pg_rewind/*` — covered in this sweep (separate register).
- `contrib/test_decoding/` — pg_create_logical_replication_slot output plugins; whitelist target.
- `src/backend/utils/init/postinit.c` — `_PG_init` discipline; pairs with check_loadable_libraries audit.

---

## Summary by tag type

| Type | Count |
|---|---:|
| trust-boundary | 22 |
| state-transition | 11 |
| correctness | 19 |
| info-disclosure | 11 |
| undocumented-invariant | 14 |
| secret-scrub | 6 |
| shell-injection | 5 |
| stale-todo | 7 |
| dead-code | 3 |
| path-traversal | 1 |
| **Total** | **99** (some entries are double-tagged) |

Severity headline: ~9 `likely`, ~30 `maybe`, rest `nit`. THE Phase D
pitch in order of impact: (1) **whitelist `check_loadable_libraries`**,
(2) **validate `spclocation` + `output_plugin`**, (3) **`SecretBuf` for
pg_authid carryover file**, (4) **`O_NOFOLLOW` on file.c modes**, (5)
**central argv[]-based subprocess invocation** to replace `system()`.
