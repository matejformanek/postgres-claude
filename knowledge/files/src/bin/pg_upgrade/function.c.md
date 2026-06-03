# function.c

## Purpose

Carries user-defined C-language function and logical-replication
output-plugin library dependencies across the upgrade. Collects the
distinct set of `probin` values from `pg_proc` on the OLD cluster +
slot plugin names, sorts them, and verifies each one loads on the NEW
cluster via `LOAD '<libname>'`.

## Role in pg_upgrade

Two-phase. `get_loadable_libraries()` runs against the OLD cluster
during info-gathering. `check_loadable_libraries()` runs against the
NEW cluster after it's been started, before any data transfer. If
any library is missing on the new cluster, pg_upgrade aborts with a
human-readable file listing the misses.

## Key functions

- `library_name_compare(p1, p2)` `function.c:29` (static qsort cmp) —
  sort by length first, then alphabetically, then dbnum. The
  length-first ordering ensures `hstore` is probed before
  `hstore_plpython` so transform-module load tests don't fail (the
  comment at line 21 documents this).
- `process_loadable_libraries(dbinfo, res, arg)` `function.c:60`
  (static task.c callback) — stores PGresult * per-database for
  later iteration.
- `get_loadable_libraries()` `function.c:77` — runs `SELECT DISTINCT
  probin FROM pg_proc WHERE prolang = ClanguageId AND probin IS NOT
  NULL AND oid >= FirstNormalObjectId` through the parallel
  UpgradeTask framework. Also adds per-database logical-slot plugin
  names (line 144-153, skipping invalid slots). Stores results in
  `os_info.libraries[]`.
- `check_loadable_libraries()` `function.c:171` — qsorts the
  collected libraries, then for each unique name issues `LOAD
  '<escaped>'` via libpq on a fresh connection to `new_cluster`'s
  template1. Each library that fails gets a paragraph written to
  `<basedir>/loadable_libraries.txt` followed by `pg_fatal` if any
  failures.

## State / globals

`os_info.libraries` (array), `os_info.num_libraries`. Set in
get_loadable_libraries, consumed in check_loadable_libraries.

## Wire surface

The `cmd` buffer at function.c:197 is `char cmd[7 + 2*MAXPGPATH + 1]`
sized as `strlen("LOAD ''") + 2*MAXPGPATH + 1`. Body:
- `strcpy(cmd, "LOAD '")` line 203.
- `PQescapeStringConn(conn, cmd+strlen(cmd), lib, llen, NULL)` line
  204. Note: NULL `error` out-param — escape failures are silently
  ignored (PQescapeStringConn returns 0 on encoding errors but the
  output buffer still gets bytes).
- `strcat(cmd, "'")` line 205.

## Phase D notes

[from-code] **`$libdir/` prefix stripping** (line 128-129) — starting
v19, if a probin starts with `$libdir/`, the prefix is stripped so
the library-search path is used. Means a v18 cluster with `probin =
'$libdir/myext.so'` gets checked as `LOAD 'myext.so'` against the new
cluster.

[ISSUE-trust-boundary: `probin` value from old cluster's pg_proc is
SQL-escaped and run as LOAD on the new cluster (maybe-medium)] —
`function.c:204`. Issuing `LOAD` of an attacker-controlled string is
arbitrary code execution by design: any C-language function in
pg_proc can name a `.so` to dlopen. But creating a C-language
function already requires superuser. Same trust boundary as the
running cluster; pg_upgrade documents that it must run as the
cluster owner. The defense is `oid >= FirstNormalObjectId` (line 93)
which excludes system-shipped probins; but a user-installed
superuser-created C function probin still gets re-loaded on the new
cluster.

[ISSUE-correctness: PQescapeStringConn called with NULL error
out-param (line 204) — encoding errors silently produce truncated
output (low)] — Probably fine because probin values are stored as
text in pg_proc with the cluster encoding, but worth noting.

[from-code] **Per-DB de-dup happens implicitly via qsort + adjacent
compare** (line 201): "if (libnum == 0 || strcmp(lib, libraries
[libnum - 1].name) != 0)". The dbnum tiebreaker in
library_name_compare ensures the FIRST occurrence of a name across
DBs determines the probe; subsequent dbnums just attach to the same
load-failure block if any.

[ISSUE-info-disclosure: PQerrorMessage(conn) (line 217) and the
failed library name plus dbname are concatenated into
loadable_libraries.txt — written under log_opts.basedir
(`%s/loadable_libraries.txt` line 181) (low)] —
`function.c:215,227`. Path is `fopen_priv` (mode 0600); only an
attacker with file-system access to log dir sees it.

[from-code] **Logical-replication plugin names** (line 149) come
from `slot_arr->slots[i].plugin` populated by info.c. Output plugins
are typically `pgoutput` (builtin) or extension-supplied; same trust
boundary as probin values.
