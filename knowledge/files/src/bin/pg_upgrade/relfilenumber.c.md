# relfilenumber.c

## Purpose

Physically transfer every relation file from the old cluster to the
new cluster after the new cluster's schema has been restored. Walks
the `FileNameMap[]` array produced by info.c::gen_db_file_maps and,
per relation, copies/clones/links/swaps the main fork file, the
`_fsm` (free space map), and the `_vm` (visibility map) — plus all
1 GB segment extensions (`.1`, `.2`, …). The "touches every relation"
file. ~640 lines.

## Role in pg_upgrade

Called from `pg_upgrade.c::main()` line 188 as
`transfer_all_new_tablespaces(...)`. Runs AFTER `disable_old_cluster`
in `--link` / `--swap` mode (so the old cluster cannot be restarted
to corrupt the now-shared files). Delegates per-file work to
`file.c` (`cloneFile`, `copyFile`, `copyFileByRange`, `linkFile`)
or, for the rare format conversion, `rewriteVisibilityMap`.

`--swap` mode (added in v18) takes a different path: instead of
per-file copy, it `rename(2)`s the entire database directory from
old to new, then swaps catalog files (pg_restore-generated) back
into place. Faster but irreversible.

## Key functions

- `transfer_all_new_tablespaces(old_db_arr, new_db_arr, old_pgdata,
  new_pgdata)` line 107 — top-level. Switches on `transfer_mode` to
  print a status line, then either runs serially
  (`parallel_transfer_all_new_dbs(..., NULL, NULL)`) or spawns one
  child per tablespace for parallel execution.
- `transfer_all_new_dbs(old_db_arr, new_db_arr, old_pgdata,
  new_pgdata, old_tablespace, new_tablespace)` line 172 — iterates
  old databases, advances past any "extra" new DBs (e.g. the
  default `postgres` DB if it was dropped on the old cluster),
  calls `gen_db_file_maps` (info.c), then `transfer_single_new_db`.
  Final `sync_queue_sync_all()` + `sync_queue_destroy()` flushes
  the --swap sync queue. [verified-by-code lines 180-221]
- `prepare_for_swap(old_tablespace, new_tablespace, db_oid, ...)`
  line 238 — `--swap` only. Builds the three paths:
  `old_catalog_dir` (`<old_tblspc>/moved_for_upgrade/<oid>_old_catalogs`),
  `new_db_dir` (the destination — `<new_tblspc>/<oid>`),
  `moved_db_dir` (the pg_restore output moved aside —
  `<old_tblspc>/moved_for_upgrade/<oid>`). Creates the
  `moved_for_upgrade` directory in the OLD cluster (so the
  `delete_old_cluster` script cleans it up), then does two
  `rename(2)` operations:
  1. Move new cluster's DB dir aside (into `moved_db_dir`).
  2. Move old cluster's DB dir into the new cluster's place.
  Returns false if the old DB doesn't exist in this tablespace
  (e.g. user only put some DBs in a tablespace).
- `parse_relfilenumber(filename)` line 324 — strtoul-based parse
  of a filename to RelFileNumber. Rejects leading zero, errors,
  empty parse, zero, > `PG_UINT32_MAX`. Comment notes the code is
  "lifted from parse_filename_for_nontemp_relation". Returns
  `InvalidRelFileNumber` on rejection.
- `swap_catalog_files(maps, size, old_catalog_dir, new_db_dir,
  moved_db_dir)` line 355 — `--swap` only. Two passes:
  1. opendir(new_db_dir) — for each regular file, if its parsed
     `relfilenumber` is NOT in the `maps` array (= not a user
     relation = it's a catalog file from pg_restore), `rename` it
     to `old_catalog_dir`. Map lookup via `bsearch`, hence the
     prior `qsort(maps, ..., FileNameMapCmp)`.
  2. opendir(moved_db_dir) — for each regular file NOT in maps,
     rename it back into `new_db_dir`. This brings the
     pg_restore-generated catalog into place. Files that ARE in
     maps (user relations) are left as the old cluster's files.
     Each restored catalog file is pushed onto the sync queue
     (`sync_queue_push`) if `do_sync` because pg_restore was run
     with `fsync=off`.
- `do_swap(maps, size, old_tablespace, new_tablespace)` line 445 —
  qsort the maps by relfilenumber, then call `prepare_for_swap` +
  `swap_catalog_files` for the given tablespace, or for ALL
  tablespaces (default + each user tablespace) if old_tablespace
  is NULL.
- `transfer_single_new_db(maps, size, old_tablespace, new_tablespace)`
  line 495 — non-swap mode. Iterates the map array; for each
  matching tablespace, calls `transfer_relfile` for `""` (main),
  `"_fsm"`, `"_vm"`. Decides whether the VM needs format
  conversion (`vm_must_add_frozenbit`) based on
  `VISIBILITY_MAP_FROZEN_BIT_CAT_VER` (= 9.6 catalog version).
- `transfer_relfile(map, type_suffix, vm_must_add_frozenbit)` line
  548 — the leaf. Iterates segno from 0 upward; for each segment
  builds `old_file` and `new_file` paths as
  `<tblspc><suffix>/<dboid>/<relfilenumber><type><.segno>`. Stats
  the old file; non-existence on a non-zero seg or fork → return
  (we've walked past the end). `unlink(new_file)` to remove
  whatever initdb/pg_restore put there, then call the right
  transfer routine:
  - `vm_must_add_frozenbit && _vm` → `rewriteVisibilityMap` (always
    rewrite, even in link mode — different file format means we
    can't hardlink).
  - else dispatch on `transfer_mode` → cloneFile / copyFile /
    copyFileByRange / linkFile.

## Sync queue (for --swap)

Lines 23-99. A 1024-entry queue of file paths. Designed for the
`--swap` post-restore catalog files. Operations:
- `sync_queue_push(fname)` calls `pre_sync_fname(fname, false)` (a
  hint to the OS to start writeback), enqueues. Auto-flushes when
  full via `sync_queue_sync_all`.
- `sync_queue_sync_all` runs `fsync_fname` on every queued path.
- The whole queue is destroyed in `transfer_all_new_dbs` after the
  loop.

Rationale (comment lines 23-40): per-file fsync immediately after
rename is much slower than batching plus issuing
pre_sync_fname hints; this strategy lets the kernel pipeline writes.

## State / globals

Reads `user_opts.transfer_mode`, `user_opts.do_sync`,
`user_opts.jobs`, `old_cluster.{pgdata,num_tablespaces,tablespaces,
tablespace_suffix,controldata.cat_ver}`, same for `new_cluster`.

File-local statics: `sync_queue[SYNC_QUEUE_MAX_LEN]`,
`sync_queue_inited`, `sync_queue_len`.

## Phase D notes

[ISSUE-trust-boundary: `parse_relfilenumber` only validates the
input as a uint32 (line 334), but `transfer_relfile` (line 568)
uses `map->relfilenumber` from `info.c` WITHOUT going through
`parse_relfilenumber` (high)] — Two paths into the relfilenumber:
1. From the old cluster's `pg_class.relfilenode` via
   `info.c::process_rel_infos` line 625. NO validation. A
   `relfilenode = 0` or `relfilenode = UINT_MAX` from a tampered
   catalog flows straight into `snprintf` of a path.
2. From a filename in `swap_catalog_files`, validated by
   `parse_relfilenumber` (line 374, 401).
Path (1) — the catalog path — is the dominant path and skips
validation. Realistic impact: a `relfilenode = 0` would create a
file named "0" (the InvalidOid sentinel). Catalog corruption
already has many other paths to mischief; this is one symptom.

[ISSUE-path-traversal: `prepare_for_swap` builds
`<old_tblspc>/moved_for_upgrade/<db_oid>_old_catalogs` via snprintf
into `MAXPGPATH` (line 272) (low)] — `old_tblspc` is composed from
`old_tablespace + suffix` where `old_tablespace` is operator-supplied
(via -d / -b) but already canonicalised in option.c. `db_oid` is a
uint32 from the catalog. The fixed string `moved_for_upgrade` and
the `_old_catalogs` suffix are appended — these are not
operator-controllable. Truncation-on-overflow is silent (snprintf
doesn't pg_fatal here unlike `make_outputdirs`), so an overly long
operator-supplied path could be silently shortened.

[ISSUE-state-transition: `prepare_for_swap` does two `rename(2)`s
in sequence (lines 292, 296) — a crash between them leaves the
new DB dir at `<moved_db_dir>` and the new DB location EMPTY (low)]
— Documented elsewhere by the "must re-initdb" guidance. The two
renames are not atomic; recovery is full-rerun-after-reinitdb.

[ISSUE-state-transition: `--swap` cannot upgrade from < v10 (check.c
line 785) because seq tuple format changed in v10 and VM format
changed in 9.6 — gated by `Assert(!vm_must_add_frozenbit)` at line
516] — Documented gating, not a bug.

[ISSUE-correctness: `transfer_relfile`'s `unlink(new_file)` (line
602) silently ignores errors (low)] — If the new file exists but
unlink fails (permissions, etc.), the subsequent `linkFile` /
`cloneFile` / `copyFile` will fail with a less-helpful error.

[ISSUE-info-disclosure: `pg_log(PG_STATUS, "%s", old_file)` line
605 logs the full path of every relation file being transferred] —
For large clusters this is large but expected. Path includes the
tablespace location which may reveal filesystem layout. Same
posture as pg_basebackup / pg_dump.

[ISSUE-undocumented-invariant: segment-loop in `transfer_relfile`
relies on contiguous .1/.2/.3 numbering — if a relation has segment
.1 but not .0 (impossible by construction but the code doesn't
check) the loop would `return` immediately on segment 0 missing for
a `type_suffix==""` case] — Actually for `segno==0 && type_suffix[0]==0`
the stat check is SKIPPED (line 584); the code unconditionally
attempts the transfer for the main fork's seg 0. So a missing main
file segment 0 would fail in `copyFile/linkFile/cloneFile` proper —
defensible. [verified-by-code]

[ISSUE-stale-todo: `pg_fatal("should never happen")` for
`TRANSFER_MODE_SWAP` inside the switch at line 639] — Reachability
gate that documents the contract; not a bug.

## Potential issues

[ISSUE-correctness: `strncpy(sync_queue[sync_queue_len++], fname,
MAXPGPATH)` (line 81) — `strncpy` does NOT NUL-terminate if
`strlen(fname) >= MAXPGPATH` (low)] — In practice paths fit in
MAXPGPATH because they're built via earlier snprintf-into-MAXPGPATH
buffers. But the pattern is fragile; `strlcpy` would be safer.

[ISSUE-dead-code: `FileNameMapCmp` (line 308) uses `pg_cmp_u32`
which is correct, but the sort happens ONLY in `do_swap` (line
456). Non-swap modes never sort — `bsearch` is only used in swap
mode.] — Note for refactors.
