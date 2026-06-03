# tablespace.c

## Purpose

Discovers user-defined tablespaces in the old cluster via SQL
(`pg_tablespace_location()`), builds parallel `tablespaces[]` arrays
for old and new `ClusterInfo`, and computes the version-suffixed
subdirectory (`PG_<major>_<catver>`) the new cluster will use.

## Role in pg_upgrade

Called from `pg_upgrade.c:setup()` after the old server is up. The
populated `cluster->tablespaces[]` array drives `transfer.c`'s
per-tablespace iteration which in turn calls into `file.c` for each
relfilenode.

## Key functions

- `init_tablespaces()` `tablespace.c:19` — orchestrator. Calls
  `get_tablespace_paths()`, sets suffixes on both clusters, and
  refuses same-version-with-tablespaces upgrade unless they're
  in-place tablespaces with different paths (line 35).
- `get_tablespace_paths()` `tablespace.c:50` — connects to old
  cluster's `template1`, executes the tablespace catalog query
  (line 58, excluding `pg_default`/`pg_global`), and for each result:
  - If `is_absolute_path(spcloc)` (line 98): treat as a traditional
    out-of-data-dir tablespace; same path used for both clusters.
  - Else (in-place tablespace): prefix with `<pgdata>/`. Each cluster
    gets its own absolute path.
  - `stat()` check (line 118) — refuses missing dir or non-dir.
- `set_tablespace_directory_suffix()` `tablespace.c:142` — formats
  `/PG_<major_version_str>_<cat_ver>` per cluster.

## State / globals

Reads/writes `old_cluster.tablespaces[]`, `.num_tablespaces`,
`.tablespace_suffix`, same on `new_cluster`.

## Phase D notes

[from-code] **Same-path collision check** (line 36): if the version
suffix would be identical (`old_cluster.tablespace_suffix ==
new_cluster.tablespace_suffix`) AND any individual tablespace path
also matches, pg_upgrade refuses. This prevents the old and new
cluster from clobbering each other's data files under the same
PG_x_y directory.

[from-comment] **Tablespace symlinks under `pg_tblspc/`** are *not*
handled in this file — `is_absolute_path()` only tests the string
returned by `pg_tablespace_location()`. The actual filesystem walk
during transfer happens in `transfer.c` and `file.c`. Symlink-
following on the link/clone path is the kernel's behavior; pg_upgrade
does not pass `O_NOFOLLOW` anywhere.

[ISSUE-trust-boundary: `pg_tablespace_location()` result is trusted
without canonicalization (maybe-low)] — `tablespace.c:87,100`. If a
superuser on the old cluster set `CREATE TABLESPACE ... LOCATION
'/etc/postgres-attack'`, pg_upgrade would target that path. But
creating a tablespace already requires superuser, so this is the
same trust boundary that already governs the running server.

[ISSUE-stale-todo: "If that changes, it will likely become necessary
to run the above query on the new cluster, too" (low)] —
`tablespace.c:91`. Future-proofing comment but no actual TODO marker.
The current model assumes tablespaces don't move during upgrade.

[ISSUE-correctness: per-tablespace `stat()` only checks the OLD
cluster's tablespace dir, never the new one (maybe-low)] —
`tablespace.c:118`. New-cluster dir creation happens later under
`file.c` / `transfer.c`. If a user mis-configures `pg_tblspc/` symlinks
on the new cluster, the failure point is deferred.
