---
path: src/bin/pg_dump/pg_restore.c
anchor_sha: f25a07b2d94c
loc: 709
depth: deep
---

# pg_restore.c

- **Source path:** `source/src/bin/pg_dump/pg_restore.c`
- **Last verified commit:** `f25a07b2d94c`
- **LOC:** 709

> **Anchor note (2026-06-22, pg-quality-auditor AUDIT mode):** upstream
> commit `7ca548f23a60` ("Revert non-text output formats for pg_dumpall")
> reverted the matching pg_restore-side support for **restoring a whole
> cluster from a pg_dumpall archive**. Gone at this anchor: the entire
> `toc.glo` / `map.dat` detection, `restore_all_databases`,
> `restore_global_objects`, `get_dbnames_list_to_restore`,
> `get_dbname_oid_list_from_mfile`, `file_exists_in_directory`,
> `restore_one_database` split, and the `--exclude-database` /
> `--globals-only` options. The file is back to its long-standing shape:
> a single-archive restore driver with exactly three functions (`main`,
> `usage`, `read_restore_filters`). This doc was previously pinned at
> `4b0bf0788b0` (LOC 1331) and is rewritten to match (−622 LOC).

## Purpose

CLI driver that reads ONE pg_dump archive (custom / directory / tar
format, NOT plain SQL — that's what `psql` is for) and either prints its
TOC (`-l`), scripts the restore to stdout/file (`-f`), or replays it into
a target database (`-d`). It is a thin wrapper around the archive layer
(`OpenArchive`, `SetArchiveOptions`, `ProcessArchiveRestoreOptions`,
`RestoreArchive`, `PrintTOCSummary`, `CloseArchive`) in
`pg_backup_archiver.c`. There is no cluster-wide / multi-database restore
mode — that was reverted with `7ca548f23a60`. [from-comment,
pg_restore.c:1-40; verified-by-code, pg_restore.c:488-529]

## Public surface

- `main(int argc, char **argv)` (59) — option parsing, validation, and a
  single restore/list/script dispatch.
- File-static: `usage` (533), `read_restore_filters` (619).
  [verified-by-code, pg_restore.c:59, 533, 619]

## Top-level structure (all inside `main`)

1. **Parse opts → `RestoreOptions *opts`** (88-329): `getopt_long` into a
   `cmdopts[]` table (88-147) mirroring pg_dump's vocabulary — filters,
   `-j` jobs, schema/table/function/index/trigger include lists,
   `--clean`, `--create`, `--if-exists`, `--single-transaction`,
   `--transaction-size`, `--section`, `--restrict-key`. (No
   `--exclude-database` or `--globals-only` — those were dumpall-archive
   only.)
2. **Get the input file spec** (332-335) as the trailing positional arg;
   complain on extra args (338-344).
3. **Require -f, -d, or -l** (347-348). Reject `-d` + `-f` together
   (351-359); reject `-d` + `--restrict-key` (361-363).
4. **Restrict-key handling** (367-378): when scripting (no `-d`), generate
   or validate a `--restrict-key` token. pg_dump's output uses `\restrict
   <key>` to put psql in restricted mode so the dump's contents cannot
   smuggle psql meta-commands client-side.
5. **Reject conflicting `-only` / `no-` combos** (380-433): `-a`/`-s`/
   `--statistics-only` mutual exclusion, `--statistics` vs
   `--no-statistics`, `-c` vs `-a`, `-1` vs `--transaction-size` (419),
   `-C` vs `-1` (427), `-1` vs multiple jobs (432).
6. **Derived flags** (440-445): compute `dumpData`, `dumpSchema`,
   `dumpStatistics`; comment notes nonsensical combos are already excluded
   by step 5. `--if-exists` requires `--clean` (459-461).
7. **Format detection** (465-486): `-F c|custom`/`d|directory`/`t|tar`;
   `p|plain` is rejected with "please use psql" (480-481); anything else
   is "unrecognized archive format".
8. **Open + restore** (488-527): `OpenArchive` → `SetArchiveOptions` →
   `on_exit_close_archive` cleanup hook → optional `SortTocFromFile`
   (`-L`) → set `numWorkers` → either `PrintTOCSummary` (`-l`) or
   `ProcessArchiveRestoreOptions` + `RestoreArchive`.
9. **Summary** (520-527): warn "errors ignored on restore: N" if any TOC
   entries failed; exit code is `AH->n_errors ? 1 : 0`; `CloseArchive`.
   [verified-by-code, pg_restore.c:59-530]

## Internal landmarks

- `read_restore_filters` (619) — reads include/exclude rules from a
  `--filter=FILENAME` file via the shared `filter_read_item` parser
  (628). Object-type support is asymmetric:
  - **include** allows function (647), index (652), schema (657), table
    (660), trigger (665); table-data / database / extension / foreign-data
    are rejected "not allowed" (636-645).
  - **exclude** allows ONLY schema (693-694); every other type is rejected
    (678-691).
  [verified-by-code, pg_restore.c:619-708]
- `usage` (533) — help text.

## Invariants & gotchas

- **Single-archive only.** pg_restore restores exactly one archive; there
  is no map.dat-driven multi-database mode at this anchor. To restore a
  full cluster, replay the pg_dumpall text stream through psql.
  [verified-by-code, pg_restore.c:332-335, 488]
- **Plain format is rejected, not restored.** `-F p` exits with "archive
  format \"p\" is not supported; please use psql" (480-481) — pg_restore
  only consumes the binary archive formats. [verified-by-code,
  pg_restore.c:476-482]
- **One of -d / -f / -l is mandatory** (347-348). Without a target DB or
  output file or list request, there is nothing to do.
- **`-d` and `-f` are mutually exclusive** (351-359) — restore-to-DB vs
  script-to-file are different modes.
- **`--restrict-key` is rejected with `-d`** (361-363) — when restoring
  directly to a database there is no psql layer for the key to fence.
- **Single-txn ↔ parallel jobs are mutually exclusive** (432-433). The
  archive layer cannot multiplex one transaction across worker
  connections. [verified-by-code, pg_restore.c:431-433]
- **`-C` requires autocommit, so `--create` vs `--single-transaction` is
  forbidden** (427-429) — can't `CREATE DATABASE` inside a txn block.
  [from-comment, pg_restore.c:423-429]
- **`--single-transaction` and `--transaction-size` cannot coexist**
  (419-421); both force `exit_on_error` when set (290, 317).
- **`--if-exists` requires `--clean`** (459-461) — `--if-exists` modifies
  the DROPs that `--clean` emits; with no `--clean` there are no DROPs.
- **`-R` is a no-op** kept for backwards compatibility (236-238).
- **`-j` is capped at `PG_MAX_JOBS`** (206-208), same cap as pg_dump.
- **The on-exit cleanup hook is installed before any connection exists**
  (492-497) — the cleanup is a no-op while `AH`'s connection is still
  NULL, so an early `exit_nicely` is safe. [from-comment,
  pg_restore.c:492-497]

## Cross-refs

- Archive layer: `pg_backup_archiver.c` (`OpenArchive`, `RestoreArchive`,
  `ProcessArchiveRestoreOptions`, `PrintTOCSummary`, `SortTocFromFile`,
  `SetArchiveOptions`, `CloseArchive`).
- Producer: `knowledge/files/src/bin/pg_dump/pg_dump.c.md` — pg_dump emits
  the archive pg_restore consumes. (pg_dumpall no longer produces an
  archive for pg_restore; see its anchor note.)
- Restrict-key origin: `knowledge/files/src/bin/pg_dump/pg_dump.c.md`
  (`\restrict <key>` / `\unrestrict <key>`).
- Filter file format: shared with `pg_dump`/`pg_dumpall` via
  `bin/pg_dump/filter.c`.

<!-- issues:auto:begin -->
- [Issue register — `pg_dump`](../../../../issues/pg_dump.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: `--restrict-key` not verified against the dump]**
  `pg_restore.c:361-378` — when scripting, pg_restore generates/accepts a
  key and emits it; there is no mechanism here to verify it matches a key
  embedded in the archive. The key in pg_dump's output is trusted by the
  consuming psql side only. Severity: nit / question.
- **[ISSUE-nit: derived-flag expression is dense]**
  `pg_restore.c:440-445` — the three-way `dumpData`/`dumpSchema`/
  `dumpStatistics` computations pack several precedence rules into one
  boolean each, relying on the earlier conflict checks (380-433) to have
  excluded the nonsensical inputs. Correct but hard to audit in isolation.
  Severity: nit.

## Tally

`[verified-by-code]=14 [from-comment]=3 [inferred]=0 [unverified]=0`
