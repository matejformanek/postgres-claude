# `src/backend/replication/syncrep_gram.y`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~110 (2.9K source)
- **Source:** `source/src/backend/replication/syncrep_gram.y`
- **Depth:** skim

## Purpose

Bison grammar parsing the `synchronous_standby_names` GUC string into a
flat `SyncRepConfigData` (`syncrep.h:63-72`). Supports `FIRST n (a,b,c)`
and `ANY n (a,b,c)` plus bare `n (...)` (FIRST by default) and a plain
name list. Output is a single `palloc`'d blob suitable as GUC `extra`
data. [from-comment] (`syncrep_gram.y:25-32`)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
