---
source_url: https://www.postgresql.org/docs/current/creating-cluster.html
fetched_at: 2026-07-08
anchor_sha: 4c75cc786301
chapter: "§19.2 Creating a Database Cluster"
maps_to_skills: [build-and-run, collation-provider, catalog-conventions]
maps_to_corpus: [knowledge/docs-distilled/storage-init.md, knowledge/docs-distilled/locale.md, knowledge/docs-distilled/bki.md, knowledge/docs-distilled/kernel-resources.md]
---

# Creating a database cluster — what initdb bakes in (§19.2)

`initdb` (`src/bin/initdb/initdb.c`) writes the on-disk cluster: the data dir,
the three template/bootstrap DBs, and the *frozen-at-creation* invariants
(checksums, locale, encoding) that can't be changed later without a re-init.

## Non-obvious claims

- **Data checksums are now ON by default (PG 18+).** `initdb.c:167` declares
  `static bool data_checksums = true;` `[verified-by-code]` — the historical
  `-k`/`--data-checksums` flag is now the *default*, and `--no-data-checksums`
  is the opt-out. Checksum state is written at bootstrap (`bootstrap_template1`,
  `initdb.c:1571`, guarded by `if (data_checksums)` at `:1637`
  `[verified-by-code]`) and is cluster-wide + permanent at initdb time (toggle
  offline later only via `pg_checksums`). Older docs/tutorials that say "pass
  `-k` to enable" are stale for PG 18. `[verified-by-code]`
- **Three databases are created, two of them templates.** `template1` is
  bootstrapped first (`bootstrap_template1`), then cloned into `template0`
  (`make_template0`, `initdb.c:2040`) and `postgres` (`make_postgres`,
  `initdb.c:2094`) `[verified-by-code]`. `template0` is the pristine untouched
  copy (source for `CREATE DATABASE ... TEMPLATE template0`); `template1` is the
  one you customize. `[from-docs]`
- **Locale and encoding are frozen at creation.** `--locale` (or environment
  `LC_*`) and `--encoding` are chosen once; `LC_COLLATE`/`LC_CTYPE` bake into the
  template DBs and drive index sort order forever after. Changing them means
  re-initdb — and a cluster can't move to an *incompatible* OS collation version
  without risking corrupt indexes (the collversion-mismatch trap). `[from-docs]`
- **`initdb` locks the data dir down and refuses to clobber.** It sets `0700`
  dirs / `0600` files (or `0750`/`0640` with `--allow-group-access`), revokes all
  other access, and *refuses to run* if `$PGDATA` exists and is non-empty — a
  guard against accidental overwrite. `[from-docs]`
- **Don't use a mount point as `$PGDATA` directly.** Create a PG-user-owned
  subdirectory inside the mount and put the data dir there — a bare mount root
  causes ownership/`lost+found` grief. `[from-docs]`
- **NFS rules are load-bearing for durability:** mount `hard` (never `soft` — a
  `soft` mount turns a network blip into a data-eating I/O error because PG won't
  retry the syscall), and use the server-side `sync` export so `fsync` truly
  reaches stable storage; `async` on the *client* mount is fine because PG issues
  `fsync` explicitly. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/storage-init.md]] — the on-disk layout `initdb`
  writes (`PG_VERSION`, `base/`, `global/`, `pg_wal/`).
- [[knowledge/docs-distilled/locale.md]] — the frozen `LC_COLLATE`/`LC_CTYPE`
  semantics this page pins at creation.
- [[knowledge/docs-distilled/bki.md]] — the bootstrap BKI stream
  `bootstrap_template1` replays to build the initial catalog.
- [[knowledge/docs-distilled/kernel-resources.md]] — the systemd `RemoveIPC` /
  system-user requirement the new cluster's OS account must satisfy.
