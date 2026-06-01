# `src/backend/utils/misc/conffiles.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~150
- **Source:** `source/src/backend/utils/misc/conffiles.c`

Shared helpers for parsing `include_dir`/`include_if_exists`/`include`
across all PG conf files (`postgresql.conf`, `pg_hba.conf`,
`pg_ident.conf`). Recursion-safe (tracks current include depth against
`CONF_FILE_MAX_DEPTH = 10`).

- `AbsoluteConfigLocation(location, calling_file)` — resolve relative to
  the including file's directory.
- `ParseConfigDirectory(dir, ..., head_p, tail_p)` — read all `*.conf` in
  a directory in sorted order, recursing through nested includes.
  Skips dotfiles. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
