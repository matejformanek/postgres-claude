---
source_url: https://www.postgresql.org/docs/current/pgwaldump.html
fetched_at: 2026-06-29T19:54:00Z
anchor_sha: 02f699c14163
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
family: wal-control-recovery-tools (2026-06-29 refill)
---

# pg_waldump — decode WAL segment files to human-readable records

`pg_waldump` is the offline CLI twin of the `pg_walinspect` SQL extension: it
reads raw WAL segment files out of `pg_wal/` and prints one decoded record per
line, **without a running server**. It is the first reach for "what actually
got written to WAL" forensics in `wal-and-xlog` / `debugging` work.

## Non-obvious claims (each `[from-docs]` unless tagged)

- **Wrong-results warning.** "Can give wrong results when the server is
  running." Run it only against an offline cluster or a read-only standby —
  a live primary can be rewriting the segment under you. `[from-docs]`
- **No server, but same OS user.** It reads files directly; you must run as the
  user that owns the data directory. No backend is started, so **no extensions
  are loaded** — custom resource managers can't be named, only referenced
  numerically as `custom###` (3-digit ID). `[from-docs]`
- **Default WAL search path:** current dir → `./pg_wal` → `$PGDATA/pg_wal`,
  overridable with `-p`/`--path`. Positional `startseg [endseg]` name the
  segment files to walk. `[from-docs]`
- **Timeline isolation.** Only the records on the selected `-t`/`--timeline`
  are displayed; records from other timelines in the same segment range are
  ignored. Timeline accepts decimal or hex (`0x11`). `[from-docs]`
- **`.partial` segments are unreadable** — the trailing partial segment of a
  promoted standby must be renamed/removed by hand before pg_waldump will read
  the range. `[from-docs]`
- **SIGINT prints stats.** Ctrl-C makes it dump the summary statistics before
  exiting (not supported on Windows). `[from-docs]`

## Filtering options (the developer-relevant half)

| Flag | Filters on |
|---|---|
| `-r`, `--rmgr=rmgr` | Resource manager name. `-r list` enumerates valid rmgrs (Heap, Btree, XLOG, Transaction, …). Custom rmgrs only as `custom###`. |
| `-R`, `--relation=tblspc/db/rel` | Only records touching that relation (tablespace OID / db OID / relfilenode). |
| `-B`, `--block=N` | Only records modifying block N — **requires `-R`**. |
| `-F`, `--fork=main\|fsm\|vm\|init` | Only the named relation fork. |
| `-w`, `--fullpage` | Only records carrying a full-page image (FPI). |
| `-x`, `--xid=xid` | Only records for that transaction ID. |
| `-n`, `--limit=N` | Stop after N records. |
| `-s`, `--start=LSN` / `-e`, `--end=LSN` | Bound the LSN range read. |

## Output / mode options

- `-z`, `--stats[=record]` — aggregate count+size and FPI count+size. Default
  groups per-rmgr; `--stats=record` breaks down per record type. This is the
  "where is my WAL volume going" view. `[from-docs]`
- `-b`, `--bkp-details` — per-record backup-block (FPI) metadata.
- `-f`, `--follow` — poll for new WAL every second after hitting end-of-stream
  (tail -f for WAL on a live-ish cluster).
- `-q`, `--quiet` — errors only; use for "does this WAL range parse cleanly?"
  validation.
- `--save-fullpage=DIR` — extract every FPI to files named
  `TIMELINE-LSN.RELTABLESPACE.DATOID.RELNODE.BLKNO__FORK`
  (e.g. `00000001-000000010000000F.1663.13962.13965.0__main`). TIMELINE is
  `%08X`, LSN is `%08X-%08X`, FORK ∈ {main,fsm,vm,init}. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/pgwalinspect.md]]` — the SQL-callable twin
  (`pg_get_wal_record_info`, `pg_get_wal_stats`); pg_waldump is the offline
  file-level equivalent of the same decode path.
- `[[knowledge/docs-distilled/wal-internals.md]]` — XLogRecord physical format;
  what the per-line output is decoding.
- `[[knowledge/docs-distilled/custom-rmgr.md]]` — why custom rmgrs show as
  `custom###` here (no extension load offline).
- `[[knowledge/docs-distilled/generic-wal.md]]` — generic WAL records as they
  appear in the dump.
- `[[knowledge/docs-distilled/storage-page-layout.md]]` — the page an FPI
  restores; `--save-fullpage` output is one raw 8KB page per file.
- Skill: `wal-and-xlog` (WAL record authoring + redo), `debugging`.
