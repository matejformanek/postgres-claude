# `src/fe_utils/version.c`

- **File:** `source/src/fe_utils/version.c` (86 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-04)

## Purpose

A single helper, `get_pg_version`, that reads the `PG_VERSION` file from a data
directory and returns the major version encoded the same way as `PG_VERSION_NUM`
(e.g. `"18\n"` → `180000`). It understands both the pre-v10 dotted scheme
(`9.6.1`) and the post-v10 single-number scheme (`18`). Used by tools that must
sanity-check a cluster's on-disk catalog version (e.g. `pg_combinebackup`,
`pg_resetwal`-adjacent tooling) before touching it. `[from-comment]` (version.c:29-42)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `get_pg_version` | :43 | Read `<datadir>/PG_VERSION`, return packed major version (`vN0000`); optionally return the raw string. |

## Internal landmarks

- `PG_VERSION_MAX_SIZE` `version.c:27` — `64`; "more than enough for any version
  numbers", used both for the read buffer and the size cap. `[from-comment]` (:24-26)
- Filename build `version.c:53-54` — `snprintf` of `"%s/PG_VERSION"` into a
  `MAXPGPATH` buffer. `[verified-by-code]`
- Open + fail-fast `version.c:56-57` — `fopen("r")`; `pg_fatal` with `%m` on
  failure. `[verified-by-code]`
- Size guard `version.c:59-62` — `fstat` the open fd; `pg_fatal` if
  `st.st_size > PG_VERSION_MAX_SIZE`. Bounds the later `memcpy`. `[verified-by-code]`
- Parse `version.c:64-66` — `fscanf("%63s")` then `sscanf("%d.%d")`; requires at
  least the major field (`< 1` fields → `pg_fatal`). `v2` defaults to 0 and stays
  0 for the post-v10 form. `[verified-by-code]`
- Optional raw string `version.c:70-74` — when `version_str != NULL`, allocates
  `PG_VERSION_MAX_SIZE` via `pg_malloc` and `memcpy`s `st.st_size` bytes from
  `buf`. Caller `pg_free`s it. `[verified-by-code]`
- Version packing `version.c:76-85` — `v1 < 10` → `v1*10000 + v2*100` (pre-v10);
  else `v1*10000` (post-v10, minor ignored). `[verified-by-code]`

## Invariants & gotchas

- **Frontend conventions:** allocation is `pg_malloc`; all error exits are
  `pg_fatal` (`%m`/`%s`). The returned `version_str` is caller-owned and must be
  `pg_free`d. `[verified-by-code]` / `[from-comment]` (:39-41)
- The size cap (`:61`) is enforced against `PG_VERSION_MAX_SIZE` (64) and the same
  constant is the `memcpy` source/dest budget, so the copy at `:73` cannot
  overrun the destination. `[verified-by-code]`
- `buf` is filled by `fscanf("%63s")` (a NUL-terminated token, no whitespace),
  but the `memcpy` at `:73` copies `st.st_size` bytes from `buf` — the on-disk
  file *size*, which includes the trailing newline that `%63s` stopped before and
  did not store into `buf`. See Potential issues. `[verified-by-code]`
- This file touches no secrets; it is included in this connection/recovery sweep
  only as a sibling fe_utils file. `[inferred]`

## Cross-references

- `source/src/include/fe_utils/version.h` — prototype.
- `source/src/include/common/relpath.h` / catalog version machinery — `PG_VERSION`
  is written by `initdb` / `bootstrap`.
- `source/src/common/logging.c` — `pg_fatal`.

## Potential issues

- **[ISSUE-correctness: memcpy of st.st_size bytes from a `%63s`-filled buffer]**
  `version.c:64,73` — `buf` is populated by `fscanf(version_fd, "%63s", buf)`,
  which reads a single whitespace-delimited token and NUL-terminates it, leaving
  the bytes after the token (including the file's trailing `\n`) **uninitialized**
  in `buf`. The optional-return path then does `memcpy(*version_str, buf,
  st.st_size)`, copying `st.st_size` bytes — the full on-disk file length, e.g. 3
  for `"18\n"`. So `version_str` ends up holding the token plus whatever garbage
  occupied `buf` at the newline/trailing positions, and is **not guaranteed
  NUL-terminated** (the copy length is the file size, not `strlen(buf)+1`). A
  caller that treats `version_str` as a C string could read uninitialized bytes.
  In practice `PG_VERSION` is tool-written and well-formed, and the dest buffer is
  64 bytes so there is no overflow, which is likely why this has gone unnoticed;
  but `strlen(buf)+1` (or copying into a zero-filled buffer) would be the robust
  form. (maybe)

## Confidence tag tally

- `[verified-by-code]` × 9
- `[from-comment]` × 4
- `[inferred]` × 1
