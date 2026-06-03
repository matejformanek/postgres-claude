---
path: src/common/config_info.c
anchor_sha: 4b0bf0788b0
loc: 201
depth: read
---

# config_info.c

- **Source path:** `source/src/common/config_info.c`
- **Lines:** 201
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `common/config_info.h`, `port/path.c` (the `get_*_path` family).

## Purpose

Backs the `pg_config` CLI. Given `my_exec_path` (the absolute pg_config binary path obtained from `find_my_exec`), build a 23-entry `ConfigData[]` of (name, setting) pairs: `BINDIR`, `DOCDIR`, …, `PGXS`, plus build-time `CONFIGURE`, `CC`, `CFLAGS`, `LDFLAGS`, `LIBS`, `VERSION`. Each path-flavored entry calls a `get_*_path()` helper out of `src/port/path.c` that derives the installed-tree location from the binary's own location, then runs the path through `cleanup_path()`. [verified-by-code, config_info.c:32-200]

## Role in PG

Frontend-only utility. Used by `src/bin/pg_config/pg_config.c`. Not used at backend runtime.

## Key function

- `get_configdata(my_exec_path, *configdata_len)` — palloc the array, fill 13 path entries plus 9 VAL_* build constants plus VERSION; `Assert(i == *configdata_len)` at the end (line 198). [verified-by-code, config_info.c:32-201]

## State / globals

None. All output is freshly palloc'd; caller frees.

## Phase D notes

- **VAL_\* constants** (`VAL_CC`, `VAL_CFLAGS`, `VAL_LDFLAGS`, `VAL_LIBS`, …) are baked into the binary at configure time. A `pg_config` shipped through a hostile build pipeline could carry attacker-chosen flags and the operator would see them — but this is "garbage in, garbage out" for the build, not a PG bug.
- **No trust input.** `my_exec_path` is supplied by `find_my_exec` (resolved via `realpath`), so the path-derivation is rooted in a trusted absolute path. [verified-by-code, config_info.c:33]
- **`Assert(i == *configdata_len)` at line 198** — if a future patch adds a key without updating the literal `23`, production NDEBUG builds will write past the palloc'd buffer. [verified-by-code, config_info.c:41,198] [maybe — Phase D]

## Confidence tag tally
`[verified-by-code]=5 [maybe]=1`
