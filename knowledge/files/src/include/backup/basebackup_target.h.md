# `src/include/backup/basebackup_target.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~66
- **Source:** `source/src/include/backup/basebackup_target.h`

Extensibility API for adding new `BASE_BACKUP` target backends.
Core ships with `client` and `server`; the `basebackup_to_shell`
contrib module uses this header to register a `shell:cmd` target.
[from-comment]

## API / entry points

- `BaseBackupAddTarget(name, check_detail, get_sink)` — extensions
  call this from `_PG_init` to register. `check_detail(name, detail)`
  parses/validates the user's `TARGET_DETAIL` string (or NULL if
  omitted) and returns an opaque payload; `get_sink(next_sink,
  payload)` produces the bbsink. [from-comment]
- `BaseBackupGetTargetHandle(target, target_detail)` — core entry
  point used by the BASE_BACKUP command processor; ERRORs if no
  such target is registered. [verified-by-code]
- `BaseBackupGetSink(handle, next_sink)` — instantiates the sink
  from the resolved handle. [verified-by-code]

## Notable invariants

- The `check_detail` callback is the place to validate file paths,
  permissions, etc.; throw via `ereport` before the sink chain is
  built so the backup never starts. [from-comment]
- An extension's sink should always forward unhandled callbacks to
  `next_sink` (see basebackup_sink.h §Forwarding helpers); the
  comment "the sink created by this function should always forward
  to this sink" makes that explicit. [from-comment]
