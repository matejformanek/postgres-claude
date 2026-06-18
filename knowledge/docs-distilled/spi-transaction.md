---
source_url: https://www.postgresql.org/docs/current/spi-transaction.html
also_fetched:
  - https://www.postgresql.org/docs/current/spi-spi-commit.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# SPI Transaction Management (internals ch. 47.4)

The leaf chapter covering `SPI_commit` / `SPI_rollback` and the nonatomic-mode
contract. This is how a PL implements `COMMIT` / `ROLLBACK` *inside* a
procedure invoked by `CALL`. The §47.4 parent page is mostly a ToC; the
load-bearing prose lives in the constraint statements and the
`SPI_commit` reference page, both folded in here. Pairs with
`idioms/commit-transaction-sequence.md`, `idioms/subtransaction-stack.md`, and
the `fmgr-and-spi` skill.

## Non-obvious claims

- **You cannot run `COMMIT`/`ROLLBACK` as SQL through `SPI_execute`.** "It is not
  possible to run transaction control commands such as `COMMIT` and `ROLLBACK`
  through SPI functions such as `SPI_execute`." You must use the dedicated
  interface functions below. [from-docs]
- **The dedicated functions are:** `SPI_commit`, `SPI_commit_and_chain`,
  `SPI_rollback`, `SPI_rollback_and_chain`, and the (now-obsolete)
  `SPI_start_transaction`. [from-docs]
- **They only work in *nonatomic* SPI mode.** "These functions can only be
  executed if the SPI connection has been set as nonatomic in the call to
  `SPI_connect_ext`" — i.e. you opened with the `SPI_OPT_NONATOMIC` flag.
  Calling them on a default (atomic) connection from plain `SPI_connect()`
  fails. [from-docs]
- **Atomic vs nonatomic tracks the call context.** A procedure invoked at the
  top level by `CALL` (or a DO block, or a background worker driving its own
  transactions) runs in a nonatomic context where committing is meaningful; a
  function called *inside* a larger query runs atomic, where there is no
  separable transaction to commit. The interface "takes the context of the
  `CALL` invocation into account." [from-docs]
- **`SPI_commit` ≈ SQL `COMMIT`, and it immediately starts a fresh
  transaction** with default characteristics. `SPI_commit_and_chain` ≈
  `COMMIT AND CHAIN`: the new transaction inherits the completed transaction's
  characteristics. [from-docs]
- **Commit failure is self-healing into a new transaction.** If the commit
  fails, the current transaction is rolled back *and a new transaction is
  started* before the error is thrown — so the connection is never left without
  an active transaction. [from-docs]
- **The safety warning is explicit:** "It is not generally safe and sensible to
  start and end transactions in arbitrary user-defined SQL-callable functions
  without taking into account the context in which they are called." This is why
  the mode gate exists — to make accidental commit-inside-a-query a hard error
  rather than corruption. [from-docs]
- **`SPI_start_transaction` is obsolete.** It survives for compatibility; the
  commit/rollback functions now auto-start the following transaction, so an
  explicit start is no longer needed. [from-docs]

## Why this matters for PL authors

This is the mechanism behind PL/pgSQL `COMMIT`/`ROLLBACK` statements being legal
in a `CALL`-invoked procedure but illegal in a function called mid-query: the PL
opens SPI with `SPI_OPT_NONATOMIC` only when its caller is itself nonatomic, and
otherwise the transaction-control statements raise. [inferred]

## Links into corpus

- [[knowledge/docs-distilled/spi.md]] — overview; `SPI_connect_ext` + flags.
- [[knowledge/docs-distilled/spi-memory.md]] — sibling leaf; note a commit ends
  the transaction, so anything not promoted appropriately is at risk across it.
- [[knowledge/docs-distilled/plhandler.md]] — the PL handler that decides
  atomic vs nonatomic.
- [[knowledge/idioms/commit-transaction-sequence.md]] — the CommitTransaction
  path `SPI_commit` ultimately drives.
- [[knowledge/idioms/subtransaction-stack.md]] — why an open subtransaction /
  explicit transaction block blocks these calls.
- [[knowledge/files/src/backend/executor/spi.c.md]] — implementation of
  `SPI_commit`/`SPI_rollback` and the nonatomic flag checks.
- [[knowledge/files/src/pl/plpgsql/src/pl_exec.md]] — PL/pgSQL's
  `exec_stmt_commit` / `exec_stmt_rollback` callers.

## Open questions

- The §47.4 parent renders ToC-only via WebFetch (same failure class as
  `planner-stats-details`); the per-function `SPI_rollback` /
  `SPI_commit_and_chain` reference pages were not separately mined. Cursor /
  savepoint behavior across a commit (the doc hints but the excerpt did not
  enumerate) — revisit via `source/src/backend/executor/spi.c` at anchor
  `ab3023ad1e68`.
