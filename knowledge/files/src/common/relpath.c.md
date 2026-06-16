# relpath.c

Shared FE/BE code that maps `(dbOid, spcOid, RelFileNumber,
procNumber, ForkNumber)` to the on-disk filesystem path of the
relation's segment-zero file. Also holds the fork-name lookup
table and helpers used by tools that need to recognise filenames.
(`source/src/common/relpath.c:1-13`) [verified-by-code]

## Purpose

The single source of truth for the layout of `PGDATA/base/`,
`PGDATA/global/`, and `PGDATA/pg_tblspc/.../PG_<ver>_<catver>/...`.
Every backend storage layer and every frontend tool (pg_basebackup,
pg_resetwal, pg_rewind, pg_checksums, …) that needs to compute a
relation file path goes through here so the format stays in lockstep.

## Key functions

- `forkNames[]` — designated-initialized array indexed by
  `ForkNumber` (`MAIN_FORKNUM=0` → `"main"`, `FSM_FORKNUM`, vm,
  init). `StaticAssertDecl` guards `MAX_FORKNUM+1` alignment.
  (`source/src/common/relpath.c:33-41`) [verified-by-code]
- `forkname_to_number(forkName)` — linear scan; backend throws
  `ERRCODE_INVALID_PARAMETER_VALUE` on miss, frontend returns
  `InvalidForkNumber`. (`source/src/common/relpath.c:49-67`)
- `forkname_chars(str, fork)` — used by tools to test whether a
  directory entry's tail (`"_fsm"`, `"_vm"`, …) names a fork; skips
  index 0 (`"main"`) by design so unsuffixed names stay "main".
  Returns the matched length; assumes no fork name is a prefix of
  another. (`source/src/common/relpath.c:80-99`)
- `GetDatabasePath(dbOid, spcOid)` — returns a `pstrdup`'d/psprintf
  path: `"global"` for `GLOBALTABLESPACE_OID`, `"base/<dbOid>"` for
  `DEFAULTTABLESPACE_OID`, else
  `"pg_tblspc/<spc>/PG_<ver>_<catver>/<db>"`. Comment flags "XXX
  must agree with GetRelationPath()".
  (`source/src/common/relpath.c:109-130`)
- `GetRelationPath(dbOid, spcOid, relNumber, procNumber,
  forkNumber)` — returns a stack-`RelPathStr` (a fixed-size struct
  by-value, so it's safe in critical sections — no palloc). 8-way
  branch on (tablespace × procNumber × fork). The temp-table form
  prefixes `t<procNumber>_` to the relfilenode. Concludes with an
  `Assert` that the formatted string fits `REL_PATH_STR_MAXLEN`.
  (`source/src/common/relpath.c:142-222`)

## State / globals

- `forkNames[]` — read-only PGDLLIMPORT array declared in
  `relpath.h:75`. Anything that touches it for write would be an
  ABI break.

## Phase D notes

[ISSUE-trust-boundary: GetRelationPath formats user-influenceable
OIDs into a filesystem path (low)] All five inputs are nominally
backend-internal: `dbOid`/`spcOid` come from catalog rows,
`relNumber` from `pg_class.relfilenode`, `procNumber` from
`PGPROC`, `forkNumber` is enum-bounded. None comes directly from a
client wire field. However, *frontend* callers (e.g. pg_rewind
walking a manifest, pg_basebackup parsing a tar entry, pg_amcheck
reading user CLI args) may take a relnode-from-string and pass it
in — `forkname_chars` itself runs over a parsed filename. The
result is written into `rp.str[REL_PATH_STR_MAXLEN+1]` and bounded
by the final `Assert` (relpath.c:219), so even a maliciously huge
OID would only push the assertion in a debug build. In a release
build the `sprintf` would overrun if the caller bypassed the OID
range. **Worth a hard length check in release builds** —
relpath.c:219 is `Assert`, not `if`.

[ISSUE-undocumented-invariant: forkname_chars assumes no fork is a
prefix of another (line 78 comment) — not enforced (low)] If a
future fork is named `"vmap"` or `"main2"`, the scan from index 1
would shadow `"vm"`/`"main"`. Add a static check.

## Potential issues

- `REL_PATH_STR_MAXLEN` (relpath.h:97-113) is computed at
  preprocessor time from `PG_MAJORVERSION`, `CATALOG_VERSION_NO`,
  `OIDCHARS=10`, `PROCNUMBER_CHARS=6`, `FORKNAMECHARS=4`. If a fork
  longer than 4 chars (e.g. `"summary"`) is added, the buffer
  overflows silently in release builds. The comment in
  `relpath.h:65-67` reminds the editor to bump these, but it's a
  manual coupling.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
