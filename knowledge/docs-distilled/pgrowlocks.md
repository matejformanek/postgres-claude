---
source_url: https://www.postgresql.org/docs/current/pgrowlocks.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pgrowlocks (row-level lock introspection)

`pgrowlocks` scans a heap and decodes each tuple's `xmax` + infomask into the
**row-level locks currently held** — the SQL way to see what `SELECT ... FOR
UPDATE` / `FOR SHARE` and multixact members are doing, and the practical
companion to debugging `HEAP_XMAX_IS_MULTI` interactions. It needs **`SELECT`
privilege** on the table (or `pg_stat_scan_tables` / superuser). `[from-docs]`

## Signature + columns

`pgrowlocks(text) returns setof record`:

- `locked_row` (`tid`) — the locked row's TID. `[from-docs]`
- `locker` (`xid`) — the locking xact ID, **or the multixact ID** when `multi`.
  `[from-docs]`
- `multi` (`boolean`) — true ⇒ `locker` is a multixact (the `HEAP_XMAX_IS_MULTI`
  case). `[from-docs]`
- `xids` (`xid[]`) — the locker xact IDs (multiple when `multi`). `[from-docs]`
- `modes` (`text[]`) — per-locker lock mode, one of `For Key Share`, `For
  Share`, `For No Key Update`, `No Key Update`, `For Update`, `Update`.
  `[from-docs]`
- `pids` (`integer[]`) — the locking backends' PIDs. `[from-docs]`

## Behavior worth knowing

- Takes **`AccessShareLock`** on the table and reads every row; it **blocks** if
  someone holds `ACCESS EXCLUSIVE`. Only rows that are *currently locked* appear
  — unlocked rows are skipped. `[from-docs]`
- When `multi = true`, it decodes the multixact into its constituent member
  xids and their individual modes — i.e. it does the `MultiXactId` member
  expansion that `heap_lock_tuple` writes. `[from-docs]`
- **Not a self-consistent snapshot**: a new row lock may be taken or an old one
  freed mid-scan; "not very speedy for a large table". `[from-docs]`

## Links into corpus

- Multixact / tuple-lock mechanics (`HEAP_XMAX_IS_MULTI`, the mode lattice): the
  `locking` skill's tuple-lock section + [subsystems/storage-lmgr.md](../subsystems/storage-lmgr.md)
- Infomask decode at the byte level: [docs-distilled/pageinspect.md](./pageinspect.md) (`heap_tuple_infomask_flags`)
- MVCC xmax semantics: [docs-distilled/mvcc.md](./mvcc.md)
- Relevant skills: `locking` (the six-layer taxonomy; this is the heavyweight
  row-lock layer made visible), `debugging`.
