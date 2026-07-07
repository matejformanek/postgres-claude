---
name: pg-upgrade-internals
description: PostgreSQL's `pg_upgrade` — the tool that upgrades a data directory in-place from one major version to another without a dump-restore. Covers `src/bin/pg_upgrade/` architecture, the pre-upgrade checks, catalog dump-restore, relfilenode preservation (or rewriting), the two allocation strategies (link vs copy vs clone), and the "check for known upgrade issues" list. Loads when the user asks about pg_upgrade internals, common upgrade failures ("could not connect to source cluster", ERROR at pg_dump extraction, relfilenumber mismatch), --link vs --clone vs --copy tradeoffs, upgrade-blocking features (unlogged tables, sequences, extensions), or extension upgrade paths. Skip when the ask is about major-version release notes semantics (see `wiki-distilled` corpus) or about pg_dump alone.
when_to_load: Debug pg_upgrade failures; understand what pg_upgrade does under the hood; audit changes that might break future upgrades (relcache invalidation, catalog format changes); work on the pg_upgrade codebase itself.
companion_skills:
  - catalog-conventions
  - vacuum-autovacuum
  - process-lifecycle
---

# pg-upgrade-internals — the in-place major-version upgrader

`pg_upgrade` avoids the classic dump-restore round trip for major version upgrades (13→14, 14→15, etc.). Instead:

1. Extract catalog schema from OLD cluster via pg_dump.
2. Load that schema into NEW cluster (which is initdb'd fresh).
3. Copy / link / clone the DATA files (heap + index) from OLD to NEW.
4. Fix up sequences, set relfilenumbers, invalidate catalog caches.
5. Old cluster is left intact but not used; can be deleted.

The wins: minutes instead of hours for TB-scale databases. The costs: OLD and NEW must be compatible (same architecture, same tablespaces, no on-disk-format-breaking changes).

## The file map

Under `src/bin/pg_upgrade/`:

| File | Role |
|---|---|
| `pg_upgrade.c` | Main driver — orchestrates the sequence. |
| `check.c` | Pre-upgrade checks: OLD/NEW cluster state, blocking features, extension versions. |
| `controldata.c` | Reads `pg_control` from both clusters — critical for catalog-version alignment. |
| `dump.c` | Calls `pg_dumpall --binary-upgrade` on OLD cluster. Special dump mode that preserves OIDs. |
| `exec.c` | Utility for running external commands (pg_dumpall, pg_dump, psql). |
| `file.c` | The data-file relocation — implements `--link`, `--copy`, `--clone` (aka `--copy-file-range` on Linux). |
| `function.c` | Extension function checking. |
| `info.c` | Enumerates relations + their storage paths. |
| `option.c` | Command-line + config file processing. |
| `parallel.c` | Parallel workers for the file-copy phase (up to `--jobs N`). |
| `relfilenumber.c` | Sets up relfilenumbers in NEW cluster to match OLD, or generates new ones if needed. |
| `server.c` | Starts + stops OLD and NEW clusters as needed. |
| `tablespace.c` | Handles tablespaces (may not be present, may be at unusual paths). |
| `util.c` | Log formatting, error handling. |
| `version.c` | Version-check logic — cluster compatibility rules. |

## The upgrade phases

1. **Setup** — parse options, start OLD + NEW clusters briefly to check compatibility.
2. **Compatibility check** — via `check.c`. If OLD has features NEW doesn't support (e.g. a removed contrib module), abort. Common blockers: unsupported extensions, incompatible large-object storage, etc.
3. **Catalog schema dump** — `pg_dumpall --binary-upgrade` — a special mode that preserves the underlying OIDs and generates relation-creation SQL with `RESET-STATE` markers.
4. **NEW cluster prep** — initdb the NEW cluster.
5. **Schema load** — psql the dump into the NEW cluster.
6. **relfilenumber alignment** — for each relation, set the NEW cluster's relfilenumber to match the OLD's. This is how the data files can move without touching content.
7. **Data file relocation** — link / copy / clone from OLD's data directory to NEW's.
8. **Sequence + statistics fixup** — sequences need special handling; ANALYZE the NEW cluster (usually as a hint, not immediate).
9. **Cleanup** — stop NEW cluster; user restarts against NEW.

## --link vs --copy vs --clone

| Mode | What happens | Trade-off |
|---|---|---|
| `--copy` (default) | Actual byte-copy of every file | Slow (essentially a `cp -r`), but OLD stays fully usable. |
| `--link` | Hard-link data files from OLD to NEW | Fast, but OLD is destroyed once NEW is used (writes to NEW modify shared inodes). |
| `--clone` (Linux `copy_file_range`) | Reflink / snapshot the files if filesystem supports | Fast + OLD stays independent (COW). Requires btrfs, xfs (with reflinks), zfs, or macOS APFS. |

Default is copy for safety. `--link` is what production admins use for zero-downtime (with a snapshot before).

## Extension handling

pg_upgrade doesn't UPDATE extensions — it just runs `CREATE EXTENSION` in the NEW cluster with whatever version was in OLD. To upgrade an extension:

- After pg_upgrade completes: `ALTER EXTENSION <name> UPDATE;`.
- Some extensions have breaking changes across major PG versions; check their docs.

## Common upgrade blockers

`check.c` runs these:

- **Removed features** — old PG had features NEW removed (e.g. `WITH OIDS`, deprecated hash indexes' on-disk format).
- **Unlogged tables** — sometimes need special handling (they're re-init'd on NEW cluster).
- **Some extensions** — old versions may not have a compatible NEW-version equivalent.
- **Catalog version mismatch** — NEW catalog version must be compatible (usually just "newer than OLD").
- **Data type on-disk format change** — rare, but a type whose binary format changed across versions blocks upgrade.

## Common patch shapes

### Add a new upgrade check

- New function in `check.c` that queries OLD cluster + reports incompatibility.
- Wire into the check dispatch.
- Add error message.
- Test with a fixture cluster having the problem.

### Debug pg_upgrade failure

- Log file: `pg_upgrade_output.d/`.
- Common: "could not find function X" — extension missing on NEW cluster.
- Common: "role NOT FOUND in NEW cluster" — pg_dumpall didn't include a role (shouldn't happen but has).
- Common: file copy failed — permission or space issue.

### Support a new upgrade path (e.g., cross-architecture)

Very rare. Would touch controldata.c version-compat rules + relfilenumber.c on-disk-format assumptions.

### Extend --clone to a new filesystem

Very platform-specific — check.c detects filesystem type + capabilities; file.c dispatches to the appropriate syscall.

## Pitfalls

- **`--link` destroys OLD** — writes to NEW go to the shared inodes. Any restart on OLD after that is dangerous. Snapshot filesystem before running `--link`.
- **Extensions must exist on NEW cluster's system BEFORE pg_upgrade** — pg_upgrade just calls CREATE EXTENSION. If NEW's system doesn't have the .so files, error.
- **Custom types / operators / functions must have IMMUTABLE marks preserved** — pg_dump respects them but broken volatility marks cause plan changes.
- **`pg_stat_*` counters reset** — cumulative stats don't survive the upgrade. Some argue this is a feature (fresh view); adjust monitoring accordingly.
- **`autovacuum` on NEW starts fresh** — needs to catch up on freeze work. Common surprise: heavy autovac after upgrade.
- **Timezone data version differences** — OLD stored data in one tzdata version; NEW may have different. Rare but has caused DST-crossing bugs.
- **Tablespaces at unusual paths** — pg_upgrade handles most cases but exotic setups (mount points that differ between OLD and NEW dir layouts) can trip it.
- **Manual mid-upgrade restart is dangerous** — if you kill pg_upgrade mid-run, the NEW cluster may be in an inconsistent state. Best: initdb NEW again and retry.
- **PostgreSQL upstream doesn't support "downgrade"** — going from PG 15 back to PG 14 requires dump-restore.

## Related corpus

- **Subsystems**: `access-transam` (catalog version alignment), `catalog-conventions`.
- **Sessions**: `2026-06-03-a6-bin-upgrade.md` — deep-read of pg_upgrade internals (36 docs, 170 issues, including `check_loadable_libraries` RCE primitive).
- **Related**: `backup-and-recovery` (base backup can be a pre-upgrade snapshot).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/bin/pg_upgrade/pg_upgrade.c
python3 scripts/corpus-chain.py --file src/bin/pg_upgrade/check.c
```

## Boundary

**Use this skill** for pg_upgrade internals + upgrade-check code + relfilenumber preservation.

**Don't use** for:
- **`pg_dump` alone** — logical dump-restore, different tool.
- **`pg_dumpall`** — used by pg_upgrade but separate concerns.
- **Base backup / streaming replication** — see `backup-and-recovery` and `physical-replication`.
- **Minor-version upgrades** — those are drop-in binary swaps, no pg_upgrade needed.
- **Rolling upgrades via logical replication** — a different strategy; use `logical-replication` skill.
