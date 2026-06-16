# relpath.h

Declarations for `GetRelationPath` and the `relpath*`/`relpathperm`
wrapper macros, plus the `RelFileNumber`, `ForkNumber`, and
`RelPathStr` types. Companion to `src/common/relpath.c`.
(`source/src/include/common/relpath.h`) [verified-by-code]

## Purpose

The single header that defines how PG names on-disk relation files
and forks. Backend storage code (`smgr`, `md`, `bufmgr`), WAL redo,
and frontend tools all include this.

## Key declarations

- `RelFileNumber` = typedef of `Oid` — distinct logical type so
  `relfilenode` arithmetic doesn't accidentally mix with table
  OIDs. `InvalidRelFileNumber = InvalidOid`,
  `RelFileNumberIsValid()`. (`relpath.h:25-28`)
- `TABLESPACE_VERSION_DIRECTORY` — `"PG_<major>_<catversion>"`
  built from `PG_MAJORVERSION` and `CATALOG_VERSION_NO` via
  `CppAsString2`. Defines the per-major-version subdirectory under
  every `pg_tblspc/<oid>/`. (`relpath.h:33-34`)
- `PG_TBLSPC_DIR` = `"pg_tblspc"`, `PG_TBLSPC_DIR_SLASH` =
  `"pg_tblspc/"`. (`relpath.h:41-43`)
- `OIDCHARS` = 10 (max chars `%u` prints).
- `enum ForkNumber` — `InvalidForkNumber = -1`,
  `MAIN_FORKNUM = 0`, `FSM_FORKNUM`, `VISIBILITYMAP_FORKNUM`,
  `INIT_FORKNUM`. `MAX_FORKNUM = INIT_FORKNUM`. Comment at lines
  64-68 reminds editors to also bump `MAX_FORKNUM`,
  `FORKNAMECHARS`, and `forkNames[]`. (`relpath.h:56-73`)
- `FORKNAMECHARS = 4` — max fork name length (`"init"`).
- `forkNames[]` declared `PGDLLIMPORT extern const char *const`.
- `forkname_to_number`, `forkname_chars` prototypes.
- `PROCNUMBER_CHARS = 6` — comment notes `MAX_BACKENDS = 2^18-1`.
  (`relpath.h:82-85`)
- `REL_PATH_STR_MAXLEN` — preprocessor expression summing every
  fixed component of the longest possible relation path.
  (`relpath.h:97-113`)
- `struct RelPathStr { char str[REL_PATH_STR_MAXLEN + 1]; }` —
  returned by-value to keep `GetRelationPath` allocation-free in
  critical sections, and to prevent the array from decaying to a
  `char *`. (`relpath.h:122-125`)
- `GetDatabasePath`, `GetRelationPath` prototypes.
- `relpathbackend(rlocator, backend, forknum)`,
  `relpathperm(rlocator, forknum)`,
  `relpath(rlocator, forknum)` — convenience wrappers. **Warning
  comment about multiple evaluation of the RelFileLocator
  argument.** (`relpath.h:140-152`)

## Phase D notes

[ISSUE-undocumented-invariant: REL_PATH_STR_MAXLEN encodes
FORKNAMECHARS=4; any new fork name >4 chars overflows the in-place
struct buffer (lines 97-113) (low)] The comment at lines 65-67
reminds the editor to bump FORKNAMECHARS — but it's a manual
coupling and `GetRelationPath` ends with `Assert`, not a runtime
check.

## Issues

[ISSUE-undocumented-invariant: REL_PATH_STR_MAXLEN encodes
FORKNAMECHARS=4; any new fork name >4 chars overflows the in-place
struct buffer (lines 97-113) (low)] The comment at lines 65-67
reminds the editor to bump FORKNAMECHARS — but it's a manual
coupling and `GetRelationPath` ends with `Assert`, not a runtime
check.

[ISSUE-undocumented-invariant: wrapper macros (`relpath.h:140-152`)
carry "beware of multiple evaluation" warning — `relpathbackend`
evaluates `rlocator` three times. A caller that passes a
side-effectful expression (e.g. a function call) silently invokes it
three times (medium)]

[ISSUE-trust-boundary: `GetRelationPath` (`relpath.h:133`) accepts
any (`dbOid`, `spcOid`, `RelFileNumber`) tuple and composes a
filesystem path under PGDATA. A6 + A14 cross-link: code paths that
pass attacker-influenced relation numbers (e.g. logical-replication
worker, replication slot, etc.) could be steered toward unexpected
filesystem locations. Header has no validation contract (low)]

## Cross-refs

- A6 `pg_upgrade` — path composition + symlink interaction.
- A14 path-traversal cluster — relation-path echo.
- Companion: `src/common/relpath.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `include-common`](../../../../issues/include-common.md)
<!-- issues:auto:end -->

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Bump CATALOG_VERSION_NO](../../../../scenarios/bump-catversion.md)

<!-- scenarios:auto:end -->
