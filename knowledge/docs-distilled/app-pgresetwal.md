---
source_url: https://www.postgresql.org/docs/current/app-pgresetwal.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_resetwal — clear WAL and rewrite pg_control (LAST RESORT)

`pg_resetwal` clears `pg_wal/` and rewrites the `pg_control` file's counters so
a cluster whose WAL or control file is corrupt can start at all. It is the
nuclear option: **it can cause data loss and unrecoverable inconsistency** and
exists only for the case where the server won't start because of control/WAL
corruption. `[from-docs]`

## Non-obvious claims

- **Refuses to run on a live server.** It checks for the `postmaster.pid` lock
  file and aborts if present. Only remove a stale lock after confirming no
  postmaster process is alive. `[from-docs]`
- **Mandatory post-procedure: dump + reinit + reload.** After a forced reset
  the docs are explicit — run `pg_dumpall`, `initdb` a fresh cluster, restore
  the dump, then repair inconsistencies. The reset gets you a *startable* but
  not *trustworthy* cluster; do not run queries against it for normal use.
  `[from-docs]`
- **`-D` is NOT taken from `$PGDATA`** for safety — the data directory must be
  named explicitly on the command line. `[from-docs]`
- **`-n`/`--dry-run` is the safe first move:** prints the values it *would*
  write (reconstructed from the filesystem) and exits without touching
  anything. `[from-docs]`
- **`-f`/`--force` is required to proceed on an uncleanly-shut-down or
  corrupt-control cluster** — the dangerous override modes need it. `[from-docs]`
- **Same-major-version only.** `[from-docs]`

## Override switches (used when pg_control is unreadable)

| Flag | Sets |
|---|---|
| `-o`, `--next-oid=oid` | Next OID (not critical to get exact). |
| `-x`, `--next-transaction-id=xid` | Next XID. |
| `-e`, `--epoch=epoch` | Next XID epoch. |
| `-c`, `--commit-timestamp-ids=xid,xid` | Oldest, newest XID with commit timestamps. |
| `-m`, `--multixact-ids=mxid,mxid` | Next, oldest MultiXactId. |
| `-O`, `--multixact-offset=off` | Next MultiXact offset. |
| `-u`, `--oldest-transaction-id=xid` | Oldest unfrozen XID. |
| `-l`, `--next-wal-file=walfile` | WAL starting location (by next segment filename). |
| `--wal-segsize=MB` | WAL segment size (power of 2, 1–1024 MB) — **can change an existing cluster's segment size without re-initdb**. |
| `--char-signedness={signed\|unsigned}` | Default char signedness (pg_upgrade use only). |

## How it guesses when pg_control is gone

When the control file is unreadable, pg_resetwal scans the on-disk SLRU/WAL
directories to infer safe values (all filenames hex):
- `pg_wal/` largest segment → default `-l`.
- `pg_xact/` smallest×0x100000 → safe `-u`; (largest+1)×0x100000 → safe `-x`.
- `pg_multixact/offsets/` (largest+1)×0x10000 / smallest×0x10000 → `-m` pair.
- `pg_multixact/members/` (largest+1)×0x10000 → `-O`.
- `pg_commit_ts/` smallest / largest → `-c` pair.

Values may be given with a `0x` prefix. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/app-pgcontroldata.md]]` — the read side; these
  switches rewrite exactly the fields pg_controldata dumps.
- `[[knowledge/docs-distilled/transaction-id.md]]`,
  `[[knowledge/docs-distilled/subxacts.md]]`,
  `[[knowledge/docs-distilled/two-phase.md]]` — XID/multixact/epoch counters reset here.
- `[[knowledge/docs-distilled/wal-internals.md]]` — what "clear the WAL" discards.
- Skill: `wal-and-xlog`, `debugging`.
