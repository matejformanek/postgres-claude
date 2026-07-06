---
source_url: https://www.postgresql.org/docs/current/plpgsql-transactions.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL transaction management (internals §43.8 — page body says §41.8)

The COMMIT/ROLLBACK-inside-PL leaf. The docs describe the *rule* (only in
procedures / DO blocks, only from a top-level or nested-CALL/DO context); the
*mechanism* is the SPI **atomic vs non-atomic** execution context, which the page
does not name but which is the real gate. This is the page behind every "cannot
commit while a subtransaction is active" and "cannot begin/end transactions in
SQL functions" error. Pairs with `spi-transaction.md` and the `fmgr-and-spi`
skill.

## Non-obvious claims

- **Transaction control is only in `CALL` procedures and `DO` blocks.** *"In
  procedures invoked by the `CALL` command as well as in anonymous code blocks
  (`DO` command), it is possible to end transactions using the commands `COMMIT`
  and `ROLLBACK`."* A plain `LANGUAGE plpgsql` **function** called inside a query
  can never do this. [from-docs]
- **Only from a top-level or purely-nested CALL/DO chain.** *"Transaction control
  is only possible in `CALL` or `DO` invocations from the top level or nested
  `CALL` or `DO` invocations without any other intervening command."* If a
  `SELECT func()` sits anywhere in the call stack between the top and your
  procedure (`CALL p1()` → `SELECT f2()` → `CALL p3()`), `p3` **cannot** commit.
  [from-docs]
- **The real gate is the SPI non-atomic flag** (page doesn't say "atomic", but
  this is the mechanism). The executor runs a procedure in a **non-atomic** SPI
  context so it may commit/rollback; a function invoked mid-query runs
  **atomic** and cannot. [from-comment / inferred] Verified: PL/pgSQL threads an
  `atomic` bool through the execstate (`estate.atomic = atomic`,
  `source/src/pl/plpgsql/src/pl_exec.c:511`) and only a `CALL`'s target enables
  non-atomic SPI (`options.allow_nonatomic = true`, `pl_exec.c:2270`); everywhere
  a value is stored the code passes `!estate->atomic` to decide whether a detoast
  is safe across a possible commit (e.g. `pl_exec.c:5959` guards prefetch "in a
  non-atomic context, we dare not prefetch"). [verified-by-code @e0ff7fd9aa2e]
- **No COMMIT/ROLLBACK inside an EXCEPTION block (subtransaction).** *"transactions
  cannot be ended inside such a block"* — a block with an `EXCEPTION` clause is a
  subtransaction (savepoint), and you can't commit the outer transaction from
  under an open savepoint. [from-docs]
- **A new transaction starts automatically after COMMIT/ROLLBACK.** *"A new
  transaction is started automatically after a transaction is ended using these
  commands, so there is no separate `START TRANSACTION` command."* `COMMIT AND
  CHAIN` / `ROLLBACK AND CHAIN` carry the transaction characteristics forward.
  [from-docs]
- **Non-read-only cursor loops forbid transaction commands.** *"Transaction
  commands are not allowed in cursor loops driven by commands that are not
  read-only (for example `UPDATE ... RETURNING`)."* A COMMIT mid-loop would
  invalidate the writing cursor's snapshot/portal. [from-docs]

## Why this design

The atomic/non-atomic split is a safety interlock: transaction boundaries can
only move when the backend knows nothing above you on the stack is holding
partial state that a commit would corrupt — no half-finished SQL statement (an
intervening `SELECT func()`), no open subtransaction (`EXCEPTION` block), no
writing cursor mid-scan. Procedures called by `CALL` are the one entry point with
a clean enough stack to allow it, so they get the non-atomic SPI context; SQL
functions never do. [inferred]

## Links into corpus

- [[knowledge/docs-distilled/spi-transaction.md]] — §47.4: `SPI_commit` /
  `SPI_rollback` and the `SPI_connect_ext(SPI_OPT_NONATOMIC)` this rides on.
- [[knowledge/docs-distilled/plpgsql-structure.md]] — §43.2: block-BEGIN ≠
  transaction-BEGIN, the confusion this page resolves.
- [[knowledge/docs-distilled/plpgsql-cursors.md]] — §43.7: the cursor-loop
  restriction above.
- [[knowledge/docs-distilled/subxacts.md]] / [[knowledge/docs-distilled/two-phase.md]]
  — the subtransaction machinery an EXCEPTION block uses.

## Open questions

- The `_SPI_current->atomic` / `SPI_connect_ext` path in `spi.c` reached from the
  `CALL` executor (`ExecuteCallStmt`) — pin the exact non-atomic entry at anchor
  `e0ff7fd9aa2e`.
