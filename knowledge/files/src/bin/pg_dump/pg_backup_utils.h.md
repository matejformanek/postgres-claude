---
path: src/bin/pg_dump/pg_backup_utils.h
anchor_sha: 4b0bf0788b0
loc: 41
depth: read
---

# pg_backup_utils.h

- **Source path:** `source/src/bin/pg_dump/pg_backup_utils.h`
- **Lines:** 41
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `pg_backup_utils.c` (implementation of `on_exit_nicely`, `exit_nicely`, `set_dump_section`), `common/logging.h` (`pg_log_generic`, `PG_LOG_ERROR`, `PG_LOG_PRIMARY`).

## Purpose

Smallest header in the pg_dump family. Two responsibilities:

1. Define the `DUMP_PRE_DATA`/`DUMP_DATA`/`DUMP_POST_DATA`/`DUMP_UNSECTIONED` bit flags returned by `set_dump_section` (the `--section=` parser).
2. **Override `pg_fatal` to call `exit_nicely` instead of plain `exit`.** This is the load-bearing reason every pg_dump-family source file `#include`s this header.

[verified-by-code, pg_backup_utils.h:15-41]

## Public surface

- Bit flags (21-24) — `DUMP_PRE_DATA=0x01`, `DUMP_DATA=0x02`, `DUMP_POST_DATA=0x04`, `DUMP_UNSECTIONED=0xff`. The `0xff` value is a clever "match anything" mask.
- `on_exit_nicely_callback` (26) — typedef for `void(*)(int code, void *arg)`.
- `extern const char *progname` (28).
- `set_dump_section(arg, *dumpSections)` (30) — parses `pre-data` / `data` / `post-data` and ORs into `*dumpSections`.
- `on_exit_nicely(function, arg)` (31) — register cleanup callback.
- `exit_nicely(code)` (32) — declared `pg_noreturn`; runs every registered callback in reverse order then exits.

## The `pg_fatal` override

```c
#undef pg_fatal
#define pg_fatal(...) do { \
        pg_log_generic(PG_LOG_ERROR, PG_LOG_PRIMARY, __VA_ARGS__); \
        exit_nicely(1); \
    } while(0)
```

(pg_backup_utils.h:35-39). The base `pg_fatal` in `common/logging.h` calls plain `exit(1)`; the override routes through `exit_nicely` so registered cleanups (DB disconnect, worker shutdown via `archive_close_connection`) actually run. [verified-by-code, pg_backup_utils.h:34-39]

## Phase D — surfaces of concern

- **Any TU that wants the cleanup behaviour must `#include "pg_backup_utils.h"`** AFTER `common/logging.h`. If a future caller forgets the include, `pg_fatal` falls back to plain `exit(1)` and the worker pool is left orphaned. [verified-by-code, pg_backup_utils.h:34-35] [maybe — invariant maintained by include discipline]
- **`exit_nicely` runs callbacks in reverse-registration order** — the parallel.c `archive_close_connection` is the most important. If that callback itself calls `pg_fatal`, it would re-enter `exit_nicely` recursively. [inferred — depends on pg_backup_utils.c implementation, not audited here]
- **`DUMP_UNSECTIONED = 0xff`** as a max-mask is a clever choice but means adding a new section bit beyond `0x80` would require widening the type. Currently a non-issue. [verified-by-code, pg_backup_utils.h:21-24] [no concern]
- **`progname` is global extern** — written once in `main`, read everywhere. Non-atomic but written before any thread/fork. [verified-by-code, pg_backup_utils.h:28] [no concern]

## Cross-references

- Every file in `src/bin/pg_dump/` that calls `pg_fatal` includes this header (transitively via `pg_backup.h` for archive-format files, directly for the helpers documented in this batch).
- Implementation: `pg_backup_utils.c` (not in this batch).

## Confidence tag tally
`[verified-by-code]=6 [maybe]=1 [no concern]=2 [inferred]=1`
