---
source_url: https://www.postgresql.org/docs/current/app-initdb.html
fetched_at: 2026-07-18
anchor_sha: 03480907e9ff
app: src/bin/initdb/initdb.c
---

# initdb — bootstrap a new database cluster

Creates a fresh `PGDATA`: the directory skeleton, the shared (cluster-wide)
catalogs in `global/`, and the three initial databases `template1`, `template0`,
`postgres`. Under the hood it runs the backend in **bootstrap mode**
(`postgres --boot`) to execute the BKI script that builds `template1`, then makes
`template0` and `postgres` by copying `template1`.

## Non-obvious claims

- Only **`template1` is actually built** by the bootstrap backend from the BKI
  script; `template0` and `postgres` are then created by *copying* `template1`.
  `template0` is given a **fixed OID** and set `ALLOW_CONNECTIONS = false` +
  `datcollversion = NULL` so it stays a pristine, connection-frozen fallback.
  `[verified-by-code source/src/bin/initdb/initdb.c:20-22,2047,2059,2068]`
- `template1` is the default source for `CREATE DATABASE` (objects added to it
  propagate to future DBs); `template0` must never be modified — it exists so a
  corrupted `template1` can be rebuilt and so `CREATE DATABASE … TEMPLATE
  template0` can pick a *different* encoding/locale than `template1`. `[from-docs]`
- **Data checksums are ON by default as of PG 18** — `data_checksums = true` in
  the source; `--no-data-checksums` opts out. (Historically this was off-by-default
  and `-k`/`--data-checksums` had to be requested.) Checksum failures surface in
  `pg_stat_database`. `[verified-by-code source/src/bin/initdb/initdb.c:167]`
- WAL segment size (`--wal-segsize`, default 16 MB, power of two 1–1024) is a
  **one-shot, init-time-only** decision — it cannot be changed on an existing
  cluster; the value is baked in and passed to the bootstrap backend as
  `-X <bytes>`. `[verified-by-code source/src/bin/initdb/initdb.c:169,1636]`
- Three locale providers via `--locale-provider`: `libc` (default; OS locales),
  `icu` (requires ICU compiled in, uses `--icu-locale`/`--icu-rules`), and
  `builtin` (must be one of exactly `C`, `C.UTF-8`, or `PG_UNICODE_FAST` via
  `--builtin-locale`). Default encoding is locale-derived, or for a C/POSIX
  locale it is `UTF8` under the ICU provider vs `SQL_ASCII` under libc.
  `[from-docs]`
- **initdb must not run as root** — it must run as the OS user that will own the
  server process, because that user must own all the created files. `[from-docs]`
- `-S`/`--sync-only` does *nothing but* fsync an existing data directory and exit
  (e.g. after flipping `fsync` off→on); `-N`/`--no-sync` skips durability entirely
  (test-only); `--no-sync-data-files` skips only `base/`+tablespace dirs while
  still syncing `pg_wal/`/`pg_xact/` (internal tooling). `[from-docs]`
- `-c name=value` / `--set name=value` forcibly writes GUC defaults into the
  generated `postgresql.conf` at init time — the escape hatch for an environment
  whose out-of-the-box defaults won't let the server even start. `[from-docs]`
- `-A`/`--auth` (and `--auth-host`/`--auth-local`) prepopulate `pg_hba.conf`;
  the default `trust` is a convenience the docs explicitly warn against for any
  multi-user host. `-g`/`--allow-group-access` relaxes the default owner-only
  file mode to group-readable (ignored on Windows). `[from-docs]`
- Created layout: `base/`, `global/` (shared catalogs), `pg_wal/`, `pg_xact/`,
  `PG_VERSION`, `postgresql.conf`, `pg_hba.conf`. `-X`/`--waldir` puts `pg_wal/`
  on a separate disk (via symlink). `[from-docs]`

## Links into corpus

- Bootstrap/BKI script that `template1` is built from:
  `[[knowledge/docs-distilled/bki.md]]`, `[[knowledge/docs-distilled/bki-structure.md]]`,
  `[[knowledge/docs-distilled/system-catalog-initial-data.md]]`.
- The `postgres --boot` mode initdb drives: `[[knowledge/docs-distilled/app-postgres.md]]`.
- Collation providers chosen here: the `collation-provider` skill,
  `[[knowledge/docs-distilled/collation.md]]`, `[[knowledge/docs-distilled/locale.md]]`.
- On-disk cluster layout produced: `[[knowledge/docs-distilled/storage-file-layout.md]]`,
  `[[knowledge/docs-distilled/creating-cluster.md]]`.
- Data-checksum page mechanics: `[[knowledge/docs-distilled/storage-page-layout.md]]`,
  `[[knowledge/docs-distilled/app-pgchecksums.md]]`.
