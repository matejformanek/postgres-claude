# `src/backend/backup/basebackup_target.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~210
- **Source:** `source/src/backend/backup/basebackup_target.c`

## Purpose

Extensible registry of "where the backup goes". Built-in targets are
`blackhole` (discard — used for testing checksum verification) and
`server` (write into a server-side directory). Extensions can add new
ones — e.g. an S3 or HSM target. [from-comment] (`basebackup_target.c:3-7`)

## Mental model

- A target is a `BaseBackupTargetType {name, check_detail, get_sink}`
  registered in `BaseBackupTargetTypeList` (a `TopMemoryContext` list so
  it survives across queries). (`basebackup_target.c:21-25`, `:94-98`)
- The two callbacks separate **option validation** from **sink
  construction**:
  - `check_detail(target, target_detail)` runs early, returns an opaque
    `void *detail_arg` capturing the parsed detail. May ereport on bad
    input.
  - `get_sink(next_sink, detail_arg)` produces the actual `bbsink` that
    will receive bytes from the previous stage. The first sink in the
    chain is whatever this returns; the last is the basebackup driver.
- `BaseBackupTargetHandle` carries `(type, detail_arg)` between the
  parser (which calls `BaseBackupGetTargetHandle`) and the sink-chain
  builder (which calls `BaseBackupGetSink`). (`basebackup_target.c:27-32`)

## API

- `BaseBackupAddTarget(name, check_detail, get_sink)` — registration
  entry point for extensions. Re-registration with the same name **updates
  in place** rather than erroring (comment: "probably not a great idea
  but this seems sanest"). (`basebackup_target.c:60-105`)
- `BaseBackupGetTargetHandle(target, target_detail)` — parser-side
  lookup; ereports `ERRCODE_FEATURE_NOT_SUPPORTED` "unrecognized target"
  if not found. (`basebackup_target.c:116-150`)
- `BaseBackupGetSink(handle, next_sink)` — sink-chain builder side; just
  forwards to `type->get_sink`. (`basebackup_target.c:162-166`)

## Built-in details

- `"blackhole"`: `reject_target_detail` ereports if any detail is given
  (no options allowed). `blackhole_get_sink` returns `bbsink_throwaway`.
- `"server"`: `server_check_detail` requires `target_detail` (the
  pathname), checks the executor role has `pg_write_server_files`
  membership (in `basebackup_server.c`). `server_get_sink` returns
  `bbsink_server`.

## Notable invariants

- All registration memory lives in `TopMemoryContext`. Names are
  `pstrdup`'d into TMC so the caller's storage can vanish.
  (`basebackup_target.c:94-100`)
- The chain order matters: in `basebackup.c:SendBaseBackup` the target
  sink is created **last** (innermost), then compression/throttle/
  progress wrap around it. So a target sink receives uncompressed
  un-throttled bytes if downstream wraps don't intercept — but
  conventionally compression is requested before reaching the target.

## Tag tally

`[verified-by-code]` 5 / `[from-comment]` 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
