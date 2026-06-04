# src/include/replication/syncrep.h

## Purpose

Exports for **synchronous replication**: the mechanism by which a
committing backend on the primary can wait for one or more standbys to
acknowledge WAL receive/flush/apply before COMMIT returns. Defines the
`SyncRepConfigData` parsed representation of the
`synchronous_standby_names` GUC, the wait modes
(`SYNC_REP_WAIT_WRITE/FLUSH/APPLY`), and the candidate-standby
selection API used by walsender and committing backends. Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

When `synchronous_commit > local_flush` and
`synchronous_standby_names` is non-empty, every COMMIT enters
`SyncRepWaitForLSN` after the local WAL flush. The backend goes to
sleep on a latch until a walsender wakes it via `SyncRepReleaseWaiters`
after observing that the chosen-quorum of standbys reported back at the
required level. The selection grammar (`FIRST N (name1, name2, ...)`
priority mode or `ANY N (...)` quorum mode) is parsed by
`syncrep_gram.y` into a `SyncRepConfigData` blob that is stored as
"extra" data for the GUC.

## Key types/struct fields

- `SyncRepRequested()` macro (lines 18-19) — `max_wal_senders > 0 &&
  synchronous_commit > SYNCHRONOUS_COMMIT_LOCAL_FLUSH`. [verified-by-code]
- Wait modes (lines 23-25): `SYNC_REP_WAIT_WRITE`, `SYNC_REP_WAIT_FLUSH`,
  `SYNC_REP_WAIT_APPLY`. `NUM_SYNC_REP_WAIT_MODE = 3` (line 27).
  [verified-by-code]
- syncRepState constants (lines 30-32): `SYNC_REP_NOT_WAITING`,
  `SYNC_REP_WAITING`, `SYNC_REP_WAIT_COMPLETE`. [verified-by-code]
- Method constants (lines 35-36): `SYNC_REP_PRIORITY` (FIRST N) vs
  `SYNC_REP_QUORUM` (ANY N). [verified-by-code]
- `SyncRepStandbyData` (lines 42-54) — snapshot copy of WalSnd fields
  taken by `SyncRepGetCandidateStandbys` to avoid holding the WalSnd
  spinlock while iterating: `pid`, `write` / `flush` / `apply` LSNs,
  `sync_standby_priority`, `walsnd_index`, `is_me`. [from-comment]
- `SyncRepConfigData` (lines 63-72) — flat malloc'd blob (GUC extra
  data; cannot use palloc): `num_sync` (N), `syncrep_method`
  (priority or quorum), `nmembers`, and `member_names` as an FLEXIBLE_ARRAY
  of nul-terminated C strings. [from-comment]
- `SyncRepStandbyNames` (line 77) — the raw GUC string. [verified-by-code]
- `SyncRepWaitForLSN(XLogRecPtr lsn, bool commit)` (line 80) — backend
  entry point called from `RecordTransactionCommit` after local flush.
  [verified-by-code]
- `SyncRepReleaseWaiters(void)` (line 87) — walsender entry point that
  wakes any backends whose required LSN has now been satisfied.
  [verified-by-code]
- `SyncRepGetCandidateStandbys` (line 90) — returns a `palloc`'d array
  of `SyncRepStandbyData`; used by both walsender (to decide who
  qualifies) and the `pg_stat_replication` view. [verified-by-code]
- syncrep grammar entry points (lines 99-105): `syncrep_yyparse`,
  `syncrep_yylex`, `syncrep_yyerror`, `syncrep_scanner_init`,
  `syncrep_scanner_finish`. The grammar accepts `ANY NUM '(' list ')'`
  and `FIRST NUM '(' list ')'` (`syncrep_gram.y:70-71`).
  [verified-by-code]

## Phase D notes

Standby selection is by `application_name` — a string the standby
chooses in its `primary_conninfo` (`application_name=foo`) and sends in
the libpq startup packet. The primary's only authentication of "yes,
this connection IS that named standby" is the underlying replication
auth (`pg_hba.conf` `replication` line + role with REPLICATION). Any
standby allowed to connect for replication can claim ANY
application_name; a malicious standby that names itself `standby1`
can be counted toward the synchronous quorum even if the operator
intended a different physical machine. This is a known design choice
documented in the user manual but worth flagging — the primary trusts
the standby's self-declared name.

`SyncRepConfigData` lives in malloc'd memory because GUC "extra" data
must outlive backend memory contexts. The flat layout (lines 60-72)
allows it to be copied as a single byte blob into shared
postmaster-level GUC state. A bug in the parser that miscounts
`nmembers` versus the FLEXIBLE_ARRAY bytes would read out of bounds.

`SyncRepWaitForLSN` puts the committing backend into an
interruptible wait (CHECK_FOR_INTERRUPTS); however the user manual
warns that cancelling the wait does NOT roll back the commit — the WAL
is already on disk locally, only the acknowledgement is missing. This
is an asymmetry that confuses operators: "ctrl-C cancelled my COMMIT"
but the change is persisted.

## Potential issues

- [ISSUE-trust-boundary: standby self-declares its `application_name`
  in the libpq startup packet; primary trusts it for sync-rep quorum
  membership; pg_hba `replication` line + REPLICATION role is the only
  enforcement (sev=likely)]
- [ISSUE-undocumented-invariant: cancelling `SyncRepWaitForLSN` does
  not undo the local WAL flush — header does not say this; only the
  user manual does (sev=maybe)]
- [ISSUE-state-transition: `SyncRepConfigData` is malloc'd as GUC
  extra; the FLEXIBLE_ARRAY of `nmembers` nul-terminated strings has
  no per-string length cap on the parser side beyond identifier rules,
  so a pathological GUC value can produce a very large extra blob held
  cluster-wide (sev=unlikely)]
- [ISSUE-info-disclosure: `pg_stat_replication` exposes
  `SyncRepStandbyData` (pid, lsns, priority) to any role that can see
  the view (default `pg_monitor`); names of sync standbys leak through
  `synchronous_standby_names` GUC visibility (sev=unlikely)]
