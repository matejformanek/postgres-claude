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

Since `a75bd485b5ea` the `<xd>` (double-quoted identifier) start condition
gained a `<xd>{xddouble}` rule (`:200`) that collapses an embedded `""` to a
single `"` via `addlitchar('"')`, mirroring how the main `scan.l` handles
quoted identifiers. Before this, an embedded quote inside a replication-command
identifier was not un-doubled — the companion fix to the
`appendQuotedIdentifier` quoting rewrite in `libpqwalreceiver.c`, so that a
slot/publication name round-trips correctly through quote-then-parse.
[verified-by-code, repl_scanner.l:200-206 @ a75bd485b5ea]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../subsystems/replication.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->
