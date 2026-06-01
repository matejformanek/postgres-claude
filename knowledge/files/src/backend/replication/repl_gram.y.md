# `src/backend/replication/repl_gram.y`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~330 (10K source)
- **Source:** `source/src/backend/replication/repl_gram.y`
- **Depth:** skim

## Purpose

Bison grammar for the replication-protocol mini-language used by
walsender. Produces a `Node *` AST consumed by `exec_replication_command`
in `walsender.c`. [from-comment]

## Grammar surface (replication commands)

- `IDENTIFY_SYSTEM`
- `READ_REPLICATION_SLOT slotname`
- `BASE_BACKUP [...options]`
- `CREATE_REPLICATION_SLOT slot {PHYSICAL|LOGICAL [plugin]} [...]`
- `DROP_REPLICATION_SLOT slot [WAIT]`
- `ALTER_REPLICATION_SLOT slot (option ...)`
- `START_REPLICATION [SLOT slot] [PHYSICAL] X/X [TIMELINE n]` or
  `START_REPLICATION SLOT slot LOGICAL X/X (options...)`
- `TIMELINE_HISTORY tli`
- `UPLOAD_MANIFEST`
- `SHOW name` — limited GUC inspection

`%name-prefix="replication_yy"`; parser uses palloc so a parse error leaks
no memory. (`:33-43`) [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
