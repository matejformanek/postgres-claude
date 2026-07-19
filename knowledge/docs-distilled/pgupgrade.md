---
source_url: https://www.postgresql.org/docs/current/pgupgrade.html
fetched_at: 2026-07-18
anchor_sha: 03480907e9ff
app: src/bin/pg_upgrade
---

# pg_upgrade — in-place major-version upgrade

The server application that upgrades a cluster across major versions **without a
dump/restore of user data**. It works because the on-disk heap/index page format
rarely changes between majors — only the *catalog layout* does — so pg_upgrade
rebuilds the catalogs in a freshly-initdb'd new cluster and then reuses the old
cluster's data files verbatim (link/copy/clone/swap), preserving relfilenumbers
and pg_class OIDs so the reused files still resolve. See the deeper corpus skill
`pg-upgrade-internals` for the C-level mechanics.

## Non-obvious claims

- The user-data file format being version-stable is the *entire* reason
  pg_upgrade exists; catalogs are re-dumped (schema-only, via `pg_dump
  --binary-upgrade`) and re-created, then the old data files are attached by
  **preserving relfilenumber + pg_class OID + tablespace mapping** so the new
  catalogs point at the old files. `[from-docs]`
- Five file-transfer modes with sharply different safety profiles:
  `--copy` (default; 2× disk, old cluster stays usable), `--link` (hardlinks,
  1× disk, **old cluster unusable once the new one starts**), `--clone`
  (reflink CoW on Btrfs/XFS/APFS; near-instant, old cluster untouched),
  `--copy-file-range` (Linux/FreeBSD, may share physical blocks), and `--swap`
  (moves the data dirs — **fastest for many relations but destructively
  modifies the old cluster**). `--link`/`--clone`/`--swap` require old and new
  data dirs on the *same filesystem*. `[from-docs]`
- The internal pipeline: schema dump (`--binary-upgrade`) → **freeze all rows**
  in the new cluster → transfer files → `pg_control` rewrite to set the next
  OID / next XID / next multixact → sync WAL. The `pg_control` update is the
  atomic "commit" of the whole upgrade. `[from-docs]`
- **Optimizer statistics ARE now carried over** by default (`pg_statistic`),
  *except* `CREATE STATISTICS` extended stats, extension stats, and the
  cumulative-stats system — those must be regenerated. `--no-statistics`
  disables the transfer. Post-upgrade the docs recommend
  `vacuumdb --all --analyze-in-stages --missing-stats-only` then a full
  `--analyze-only` pass. `[from-docs]`
- **Non-upgradable objects**: a database is rejected if any column uses an
  OID-referencing `reg*` type whose referent isn't stable across the dump —
  `regcollation regconfig regdictionary regnamespace regoper regoperator regproc
  regprocedure`. But `regclass`, `regrole`, `regtype` ARE upgradable (their OIDs
  are stable / preserved). `[from-docs]`
- `--check` runs the full compatibility validation (binary bit-width via
  `pg_controldata`, `reg*` scan, extension availability) **without modifying
  either cluster** — the old server may even stay running. Pass the same mode
  flag (`--link`/`--clone`/…) to `--check` to get mode-specific validation.
  `[from-docs]`
- Default port during upgrade is **50432** (env `PGPORTNEW`), not 5432 — chosen
  so a stray client can't connect to the half-built cluster mid-upgrade.
  `[from-docs]`
- `--link` reversibility hinges on one file: after linking but *before* the new
  cluster is started, the old cluster is recoverable by renaming
  `$PGDATA/global/pg_control.old` back to `pg_control`. Once the new cluster
  starts, the shared inodes make the old cluster unsafe → restore from backup.
  `--swap` has no such escape hatch past the "no longer safe to start" message.
  `[from-docs]`
- Working files land in `pg_upgrade_output.d/<ISO-timestamp>/` (schema dumps +
  logs), auto-removed on success and **retained on failure** for diagnosis.
  `-r`/`--retain` keeps them even on success. `[from-docs]`
- `-j`/`--jobs` parallelizes across databases *and* tablespaces (rule of thumb:
  number of CPU cores); it does nothing for a single-database single-tablespace
  cluster. `[from-docs]`
- PG18 adds `--set-char-signedness=signed|unsigned` for the platform-dependent
  default `char` signedness, so a cluster physically migrated to a
  different-signedness platform reads its data correctly. `[from-docs]`

## Links into corpus

- C-level mechanics (relfilenumber preservation, `--binary-upgrade` dump hooks,
  upgrade blockers): the `pg-upgrade-internals` skill.
- `pg_control` fields rewritten (next OID/XID/multixact): the WAL/xlog corpus and
  `[[knowledge/docs-distilled/app-pgcontroldata.md]]`.
- The freeze step and why frozen rows are required across the version boundary:
  `[[knowledge/docs-distilled/routine-vacuuming.md]]`, `mvcc.md`.
- `initdb` of the new cluster, which must match old-cluster locale/encoding:
  `[[knowledge/docs-distilled/app-initdb.md]]`.
- Logical-replication upgrade path (slots) is a *separate* procedure (docs §29.13),
  not handled by the generic pg_upgrade flow.
