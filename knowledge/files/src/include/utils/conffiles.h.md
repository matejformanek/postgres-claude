# `utils/conffiles.h` — postgresql.conf include-file support

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/conffiles.h`)

## Role

Tiny (27-line) header for the two helpers backing `include`,
`include_if_exists`, and `include_dir` directives in postgresql.conf:
`AbsoluteConfigLocation` (resolves a relative include path against the
calling file) and `GetConfFilesInDir` (reads a directory listing for
`include_dir`).

## Public API

- `CONF_FILE_START_DEPTH = 0` — `source/src/include/utils/conffiles.h:17`.
- `CONF_FILE_MAX_DEPTH = 10` — `:18`. Max recursion depth for nested
  `include` directives.
- `char *AbsoluteConfigLocation(location, calling_file)` — `:20`.
- `char **GetConfFilesInDir(includedir, calling_file, elevel,
   *num_filenames, **err_msg)` — `:22-25`.

## Invariants

- Include nesting depth is hard-capped at 10. Files at depth ≥ 10 with
  further includes are rejected. [from-define, `:17-18`]
- `AbsoluteConfigLocation` resolves a relative `location` by prepending
  the directory of `calling_file`. An absolute `location` is returned as-is.
  [inferred from name; matches standard "include relative to me" semantics]
- `GetConfFilesInDir` returns an alphabetically sorted array of file
  paths and sets `*num_filenames`. Errors set `*err_msg` (caller's
  responsibility). [inferred from signature]

## Notable internals

10 is small enough to prevent stack blowup but large enough for realistic
sysadmin setups (`postgresql.conf` → `conf.d/01-base.conf` → etc.).

## Trust-boundary / Phase D surface

- **Symlink trust**: `GetConfFilesInDir` reads the directory and stat()s
  entries; nothing here prevents symlinks pointing outside `includedir`
  from being followed. Standard PG threat model assumes the postgres OS
  user controls the data/config directories, but admins who mount a
  shared `conf.d/` from elsewhere should know. [ISSUE-security: includedir
  follows symlinks; no header-documented anti-symlink stance (maybe)]
- **Relative vs absolute path resolution**: `AbsoluteConfigLocation` is
  the only normaliser. A `..` in the include path is preserved (not
  rejected), so `include '../../../etc/passwd'` would be a parse error
  later but the path resolution itself doesn't sandbox. Likely safe in
  practice because the GUC config parser will fail on the actual content.
  [ISSUE-defense-in-depth: no path-traversal check in include resolution;
  relies on later parse failure (nit)]
- `CONF_FILE_MAX_DEPTH = 10` is a stack guard, not a fanout guard. An
  `include_dir` pointing at a directory with 100k files will produce
  100k file opens; no per-directory cap. [ISSUE-resource:
  `GetConfFilesInDir` has no per-directory file count cap (maybe)]
- `*err_msg` is a heap string the caller must free; header doesn't say
  so. [ISSUE-documentation: err_msg ownership undocumented (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/guc.h.md` — `ParseConfigFile` /
  `ParseConfigDirectory` use these helpers.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-security: `GetConfFilesInDir` follows symlinks without
   header-documented stance (maybe)] —
   `source/src/include/utils/conffiles.h:22`.
2. [ISSUE-defense-in-depth: no path-traversal sandboxing in
   `AbsoluteConfigLocation` (nit)] —
   `source/src/include/utils/conffiles.h:20`.
3. [ISSUE-resource: `GetConfFilesInDir` has no per-directory file-count
   cap (maybe)] — `source/src/include/utils/conffiles.h:22`.
4. [ISSUE-documentation: `err_msg` ownership undocumented (nit)] —
   `source/src/include/utils/conffiles.h:25`.
