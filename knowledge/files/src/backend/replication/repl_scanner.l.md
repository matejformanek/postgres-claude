# `src/backend/replication/repl_scanner.l`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~280 (7.6K source)
- **Source:** `source/src/backend/replication/repl_scanner.l`
- **Depth:** skim

## Purpose

Flex lexer for the replication-command language. Pairs with
`repl_gram.y`. Exposes `replication_scanner_init/finish` and
`replication_scanner_is_replication_command(scanner)` — the latter is
called by `exec_replication_command` *before* parsing, so if the input
isn't recognizable as a replication command, walsender falls through to
SQL execution path. (`walsender.c:2133`) [verified-by-code]

## Notable

`fprintf` is redefined to call `fprintf_to_ereport` (`:30-39`) so flex's
fatal-error path doesn't actually `exit()` the backend.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
