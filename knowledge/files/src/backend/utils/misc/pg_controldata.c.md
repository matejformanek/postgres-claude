# `src/backend/utils/misc/pg_controldata.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~250
- **Source:** `source/src/backend/utils/misc/pg_controldata.c`

SQL surface for inspecting `$PGDATA/global/pg_control`:
`pg_control_checkpoint()`, `pg_control_system()`, `pg_control_init()`,
`pg_control_recovery()`. Each function reads the file via
`get_controlfile()` (under `ControlFileLock`) and returns a row-shaped
record. Used by monitoring tools to read DB system identifier,
last-checkpoint LSN, oldest xid, WAL block size, etc. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
