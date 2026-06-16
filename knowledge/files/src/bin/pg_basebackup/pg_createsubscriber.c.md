# pg_createsubscriber.c

## Purpose

Tool added in v17 that converts a stopped physical-replication standby
into a logical-replication subscriber. Given a standby's data dir and
the publisher's connection string, it: (1) starts the standby in a
restricted mode, (2) checks both ends, (3) stops the standby, (4)
creates publications + logical replication slots on the publisher with
a known consistent LSN, (5) writes recovery params to promote at that
LSN, (6) starts the subscriber, (7) waits for promotion, (8) creates
disabled subscriptions on the new subscriber pointing at those slots,
(9) advances replication origin to the LSN, (10) enables subscriptions,
(11) stops, (12) randomizes the system identifier (so the resulting
cluster can never be confused with its old self).

## Role in pg_basebackup directory

Stands alone — does NOT use the base-backup streaming protocol. Its
input is a *pre-existing* standby data directory (created earlier by
pg_basebackup or similar). Shares directory + Makefile with
pg_basebackup but otherwise independent.

## Wire/protocol surface

Many libpq SQL connections, NOT the replication protocol:

- Publisher: connects to each database to issue
  `CREATE PUBLICATION`, `pg_create_logical_replication_slot`,
  `pg_log_standby_snapshot`, `DROP PUBLICATION`, `DROP_REPLICATION_SLOT`.
  Lines 1794, 1546, 935, 1872, 1600.
- Subscriber (local short-lived cluster started under restricted
  parameters): `CREATE SUBSCRIPTION ... WITH (create_slot=false,
  enabled=false, slot_name=..., copy_data=false, two_phase=...)`,
  `pg_replication_origin_advance`, `ALTER SUBSCRIPTION ... ENABLE`,
  `DROP SUBSCRIPTION`. Lines 1985, 2048, 2143, 1255.
- Subscriber control: spawns `pg_ctl start/stop` (lines 1673, 1724)
  and `pg_resetwal` (line 708). Uses `find_other_exec` to locate
  matching-version binaries.

Also reads the standby's `pg_control` directly via
`get_controlfile()` to fetch the system identifier (lines 681, 719).

## Key functions

- `main()` line 2235 — option parse, `geteuid() != 0` check (line 2319),
  start-stop choreography.
- `check_data_directory(datadir)` line 449 — basic stat + PG_VERSION
  major-version match.
- `get_primary_sysid` / `get_standby_sysid` (lines 641, 681) — fetch
  sysid from publisher SQL vs subscriber pg_control. Must match
  (line 2633).
- `start_standby_server` line 1673 — wraps `pg_ctl start` with hardened
  args:
  - `sync_replication_slots=off`, `idle_replication_slot_timeout=0`
    (line 1681, 1684).
  - `restricted_access`: `listen_addresses=''`,
    `unix_socket_permissions=0700`, custom socket_dir (line 1697-1699).
  - Optional `max_logical_replication_workers=0` so apply doesn't run.
- `stop_standby_server` line 1724 — `pg_ctl stop -D ... -s -m fast`.
- `setup_publisher` line 867 — per-db: create publication (if not
  exists), create logical slot, retain last slot's LSN. After all
  dbs, calls `pg_log_standby_snapshot()` on the publisher to ensure
  the WAL stream has a record at or past the consistent LSN.
- `setup_recovery` line 1380 — writes recovery params to
  `pg_createsubscriber.conf` inside subscriber's datadir, then
  `WriteRecoveryConfig` to add an `include_if_exists` line to
  `postgresql.auto.conf`. Sets `recovery_target_lsn = <consistent_lsn>`,
  `recovery_target_inclusive=false`, `recovery_target_action=promote`.
  `recovery_params_set = true` is the flag used by
  `cleanup_objects_atexit` to rename the conf file out of the way on
  exit (whether success OR failure — see line 204).
- `wait_for_end_recovery` line 1748 — polls `pg_is_in_recovery()` with
  `WAIT_INTERVAL = 1`s until recovery ends or `recovery_timeout`.
  Sets `recovery_ended = true` on success.
- `setup_subscriber` line 1344 — per-db:
  `check_and_drop_existing_subscriptions`, optionally
  `check_and_drop_publications`, then `create_subscription`,
  `set_replication_progress`, `enable_subscription`.
- `create_subscription` line 1985 — escapes all four identifier+
  literal inputs (pubname, subname, pubconninfo, replslotname) via
  `PQescapeIdentifier` / `PQescapeLiteral`.
- `modify_subscriber_sysid` line 708 — picks new sysid as
  `(tv_sec<<32) | (tv_usec<<12) | (getpid()&0xFFF)`, writes via
  `update_controlfile`, then spawns `pg_resetwal -D <subscriber_dir>`.
- `cleanup_objects_atexit` line 201 — runs on any exit path:
  - Always: rename `pg_createsubscriber.conf` →
    `pg_createsubscriber.conf.disabled` (durable_rename).
  - If `!success`: best-effort drop publication + drop slot on
    publisher for each `dbinfo.made_*` flag. If can't reconnect to
    publisher, log a hint telling the user to clean up manually.
  - If `standby_running`, stop it.

## State / globals

- `dbinfos` (struct) — array of per-db pub/sub info.
- `num_dbs`, `num_pubs`, `num_subs`, `num_replslots`.
- `primary_slot_name` — the standby's `primary_slot_name`, picked up
  from check_subscriber. To be dropped after success.
- `subscriber_dir`, `pg_ctl_path`, `pg_resetwal_path`.
- `recovery_ended`, `standby_running`, `recovery_params_set` —
  state-machine flags driving cleanup decisions.
- `dry_run` — short-circuits every state-changing operation but still
  logs what would happen.

## Phase D notes

[ISSUE-state-transition: partial-failure midway through `setup_publisher`
loop leaves publications + slots scattered across multiple databases
(state-transition, maybe)] — `setup_publisher` (line 867) creates
publications and slots on one DB at a time inside a loop. If
connection to DB N+1 fails after we've already created pub+slot on
DB N, the `cleanup_objects_atexit` does try to drop them (line 240
checks `made_publication || made_replslot` per dbinfo). But this
cleanup requires the publisher to still be reachable; if not (line
253 fallthrough), only a warning is logged. Slots without consumers
retain WAL indefinitely. [verified-by-code]

[ISSUE-state-transition: `recovery_ended = true` means the standby
was promoted and any failure after this point is unrecoverable —
explicit warning at line 231 (state-transition, by design)] —
The user has to recreate the physical replica. Documented.
[verified-by-code]

[ISSUE-trust-boundary: `pg_log_standby_snapshot()` called on the
publisher (line 935) requires SUPERUSER or `pg_log_backend_memory_contexts`
membership; pg_createsubscriber doesn't pre-check that the publisher
role has it (undocumented-invariant, low)] — Failure would error
late in the choreography. `check_publisher` validates wal_level,
slot counts, etc. but not function privilege. [verified-by-code]

[ISSUE-secret-scrub: publisher conninfo string is written to
`pg_createsubscriber.conf` via `WriteRecoveryConfig` (line 1460)
which renames to disabled on exit (line 214) but doesn't shred
content (secret-scrub, maybe)] — If the publisher conninfo
contains a password, that password lands in the disabled file inside
the subscriber's data dir, world-readable per the data-dir umask.
The disabled file IS the "useful for debugging" artifact mentioned
in the comment at line 47-48. Plain-text credentials in the data
directory until manually removed. [verified-by-code]

[ISSUE-undocumented-invariant: pidfile-based "is standby running"
check (line 2645) is racy — the file exists if the standby was
SIGKILLed without cleanup (state-transition, low)] — Stat the
pidfile, refuse if exists. False positive forces user to manually
remove stale pidfile. False negative (race) is unreachable because
this happens before we start the standby ourselves. [verified-by-code]

[ISSUE-wire-protocol: subscriber port has no clash detection beyond
"if the user picked the same port the existing standby was on, it
might be already in use" (line 2304 default `50432`)
(state-transition, low)] — `start_standby_server` passes
`-c listen_addresses=''` so only Unix socket → port collisions don't
actually matter on listen. But the port is also used in
`get_sub_conninfo` to form the subscriber conninfo, and that conninfo
gets baked into the persisted `CREATE SUBSCRIPTION` if (somehow) the
subscription persists past tool exit. Not exploited in normal flow.
[verified-by-code]

[ISSUE-state-transition: `modify_subscriber_sysid` writes
controlfile then runs `pg_resetwal` (lines 738, 746). If
update_controlfile succeeds and pg_resetwal fails, the cluster has
a new sysid but stale WAL — irreparably broken cluster
(state-transition, low)] — No transaction wraps these two steps;
nothing can. The risk window is small (it's the last step before
"Done!"). [verified-by-code]

[ISSUE-trust-boundary: `find_other_exec` for pg_ctl + pg_resetwal
trusts PATH/dirname of argv[0] (state-transition, low)] —
`get_exec_path` (line 412) calls `find_other_exec(argv0, progname,
versionstr, exec_path)`. The version-string check (line 419)
guarantees the located binary reports the same PG_VERSION, which is
a reasonable integrity check. Doesn't defeat a same-version trojan
in the same directory. [verified-by-code]

`canonicalize_path` is applied to `subscriber_dir`, `log_dir`,
`socket_dir` from argv (lines 2349, 2353, 2366, 2471). Good.

`PQescapeIdentifier` / `PQescapeLiteral` are used everywhere that
takes user-supplied names into SQL (lines 1563, 1616, 1996-1999,
2060-2061, 2151). SQL injection surface looks tight.
[verified-by-code]

Search-path is secured on every connection — `connect_database` line
604 runs `ALWAYS_SECURE_SEARCH_PATH_SQL`. [verified-by-code]

`atexit(cleanup_objects_atexit)` registered at line 2625, after
`dbinfos.dbinfo` is allocated (line 2622). Comment line 2619-2621
notes the ordering requirement. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_basebackup`](../../../../issues/pg_basebackup.md)
<!-- issues:auto:end -->
