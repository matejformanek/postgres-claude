# `contrib/pg_logicalinspect/pg_logicalinspect.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~207
- **Source:** `source/contrib/pg_logicalinspect/pg_logicalinspect.c`

PG17-era extension that **opens serialized logical-decoding snapshot
files on disk** and surfaces their contents as SQL row sets. Two
SQL-callable functions: `pg_get_logical_snapshot_meta(text)` returns
the on-disk header (magic / checksum / version);
`pg_get_logical_snapshot_info(text)` returns the full `SnapBuild`
internal state (state enum, xmin/xmax, two_phase_at,
in_slot_creation, the `committed.xip[]` and `catchange.xip[]` xid
arrays, …). Access is restricted to `pg_read_server_files` via the
`.sql` install script. [verified-by-code] [from-comment]

## API / entry points

- `pg_get_logical_snapshot_meta(filename text) RETURNS RECORD`
  (pg_logicalinspect.c:98-131) — parses the filename
  (`%X-%X.snap`) into an LSN, calls
  `SnapBuildRestoreSnapshot(&ondisk, lsn, CurrentMemoryContext,
  false)`, then returns three columns: magic, checksum (cast to
  int64), version. [verified-by-code]
- `pg_get_logical_snapshot_info(filename text) RETURNS RECORD`
  (pg_logicalinspect.c:133-207) — same restore path, returns 14
  columns describing the SnapBuild internal state plus the two
  committed/catchange xid arrays as `xid[]`. The arrays are built
  via `construct_array_builtin(arrayelems, xcnt, XIDOID)`.
  [verified-by-code]
- `parse_snapshot_filename` (pg_logicalinspect.c:57-93) — strict
  parser: sscanf must yield 2 fields AND `sprintf("%X-%X.snap", hi,
  lo)` must round-trip exactly equal to the input. This guards
  against shenanigans like `0-0.snap.foo` or zero-padded variants.
  [verified-by-code] [from-comment]
- `get_snapbuild_state_desc` (pg_logicalinspect.c:30-52) — switch
  over `SnapBuildState` → string ("start", "building", "full",
  "consistent"). [verified-by-code]

## Notable invariants / details

- **Access control is via the install SQL**, not C-level
  `superuser()` checks. `pg_logicalinspect--1.0.sql` runs
  `REVOKE EXECUTE … FROM PUBLIC; GRANT EXECUTE … TO
  pg_read_server_files;` for both functions. So a non-superuser
  granted membership in `pg_read_server_files` can read every
  serialized snapshot in `pg_logical/snapshots/`. [verified-by-code]
- The C functions themselves have **no permission check**. A
  superuser who creates a SECURITY DEFINER wrapper exposes the
  primitive to any caller — same pattern as the pageinspect family.
  [verified-by-code] [ISSUE-security: no in-function check; relies
  entirely on SQL-level GRANT (likely)]
- `SnapBuildRestoreSnapshot` is **not normally called from regular
  backends** — it's the snap-build code path used by walsender during
  decoding initialization. Calling it from a SQL function relies on
  the implementation being safe to re-enter outside of a logical
  decoding session. The `false` last argument is the "missing_ok"
  flag — false means "ERROR on missing file". [verified-by-code]
  [from-comment]
- Filename parse uses `%X-%X.snap` matching the on-disk format from
  `snapbuild.c`. The strict round-trip check (lines 80-82) ensures
  the caller can't pass `0-0.snap` (parses, but
  `sprintf("0-0.snap")` would have leading zeros stripped — actually
  matches because %X has no width). The real protection is against
  trailing/embedded garbage that sscanf would skip. [verified-by-code]
- The filename is **directly used to compute an LSN** but the actual
  file path resolution is internal to `SnapBuildRestoreSnapshot` —
  the caller doesn't supply a path, just the LSN-bearing filename.
  Hard-coded location: `pg_logical/snapshots/`. So traversal
  attacks via `../etc/passwd.snap` are blocked at the format-parse
  level. [verified-by-code] [inferred]
- Output xid arrays (committed.xip, catchange.xip) can be very
  large; the `palloc` at lines 171, 188 allocates `xcnt *
  sizeof(Datum)` directly in the calling context. For a long-running
  decoder under heavy DDL, `catchange.xcnt` can be in the thousands.
  [verified-by-code]

## Potential issues

- pg_logicalinspect.c:118, 153. **Calls `SnapBuildRestoreSnapshot`
  from a SQL function context.** This API was historically called
  only from logical decoding setup (walsender path). It allocates
  in `CurrentMemoryContext` (passed explicitly) but its internal
  invariants assume the SnapBuild module isn't being driven
  concurrently from elsewhere. Re-entrancy story is undocumented.
  [ISSUE-question: re-entrancy of SnapBuildRestoreSnapshot from
  user SQL (maybe)]
- pg_logicalinspect.c:155-198. **Exposes internals of an active
  snap-build state** — `xmin`, `xmax`, `start_decoding_at`,
  `committed.xip[]`. A `pg_read_server_files` member who can also
  see other databases via this surface can correlate decoding
  progress with active txids on the cluster. Mostly informational,
  but combined with `pg_stat_replication` and decoded slot state
  gives a near-complete picture of which writes are currently in
  the pipeline. [ISSUE-security: read amplifier for replication
  internals (maybe)]
- pg_logicalinspect.c:72-82. The format-check uses `sscanf` with
  `%X` (case-insensitive hex). The round-trip uses `sprintf` with
  `%X` (uppercase). A lower-case filename like `aabb-ccdd.snap`
  parses successfully but the regenerated `tmpfname` becomes
  `AABB-CCDD.snap`, which `strcmp` fails. So lower-case hex is
  rejected. PG itself only writes upper-case, so this is fine, but
  a manually copied file from a tool that lower-cased the name
  will be rejected with a confusing "invalid snapshot file name"
  error. [ISSUE-style: case-sensitive filename match (nit)]
- pg_logicalinspect.c:166-198. The xid array construction palloc's
  the whole thing in the function-result memory context. For a
  cluster with `catchange.xcnt` in millions, this is one giant
  allocation. No limit is applied. [ISSUE-style: unbounded array
  size (nit)]
- pg_logicalinspect.c:104-105. `values[…] = {0}` and `nulls[…] =
  {0}` are zero-initialized; the assigned columns sequentially fill
  via `i++`. If a future patch reorders the assignments, the
  `Assert(i == COLS)` at line 124, 200 catches it only in assert
  builds. [ISSUE-style: index counter fragile to reorder (nit)]
- pg_logicalinspect.c:88-92. `parse_error` path goto from two
  separate sscanf-failure / mismatch checks. Both lead to the same
  ereport. Style-wise the two branches could be inlined for
  clarity. [ISSUE-style: minor (nit)]

## Cross-references

- `knowledge/issues/pg_logicalinspect.md` — per-extension issue
  register (create from template if absent).
- `source/src/backend/replication/logical/snapbuild.c` — the
  source of `SnapBuildRestoreSnapshot` and the `SnapBuildOnDisk`
  layout this extension surfaces.
- `source/src/include/replication/snapbuild_internal.h` — the
  internal header included here; signals this is a *peek-at-
  internals* extension by design.
- Companion: `contrib/pg_walinspect` (same pattern — restricted to
  `pg_read_server_files`, no in-function superuser check).
- A14-era finding-class: "contrib extensions that REVOKE+GRANT to
  a default role but have no C-level permission check are
  trivially exposed via SECURITY DEFINER wrappers."

<!-- issues:auto:begin -->
- [Issue register — `pg_logicalinspect`](../../../issues/pg_logicalinspect.md)
<!-- issues:auto:end -->
