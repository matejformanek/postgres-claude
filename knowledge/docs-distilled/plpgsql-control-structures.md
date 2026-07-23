---
source_url: https://www.postgresql.org/docs/current/plpgsql-control-structures.html
chapter: "43.6 PL/pgSQL Control Structures (plpgsql-control-structures)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# PL/pgSQL control structures — plpgsql-control-structures

The §43.6 control-flow chapter, read for backend mechanics rather than syntax:
the two claims that actually cost you — **`BEGIN…EXCEPTION` is a real
subtransaction** and **`RETURN NEXT`/`RETURN QUERY` materialize into a
tuplestore** — plus the local-variable-survives-rollback asymmetry and the
`GET [STACKED] DIAGNOSTICS` item set. The engine is `pl_exec.c`; see the
`plpgsql-internals` skill and `[[knowledge/docs-distilled/plpgsql-implementation.md]]`.

## Non-obvious claims

- **An `EXCEPTION` block IS a subtransaction — the docs only imply it, code
  confirms it.** The docs say only: "A block containing an `EXCEPTION` clause is
  significantly more expensive to enter and exit than a block without one.
  Therefore, don't use `EXCEPTION` without need." [from-docs] The mechanism is
  explicit in the executor: `exec_stmt_block` calls
  `BeginInternalSubTransaction(NULL)` on entry when the block has an exception
  section [verified-by-code pl_exec.c:1820], then on normal exit
  `ReleaseCurrentSubTransaction()` [:1859] and on a caught error
  `RollbackAndReleaseCurrentSubTransaction()` [:1885]. So each entry/exit is a
  savepoint push/pop — that is the "significantly more expensive" the docs warn
  about, quantified.
- **Local PL/pgSQL variables survive the rollback; database changes do not.**
  "When an error is caught by an `EXCEPTION` clause, the local variables of the
  PL/pgSQL function remain as they were when the error occurred, but all changes
  to persistent database state within the block are rolled back." [from-docs]
  This asymmetry falls straight out of the subtransaction model: the subxact
  rolls back *table* changes, but the PL/pgSQL variable memory (in the function's
  estate, not the transaction) is untouched. The canonical example — `x := x+1`
  then `y := x/0` — returns the **incremented** `x` from the handler even though
  a sibling `UPDATE` in the same block is undone.
- **`RETURN NEXT` and `RETURN QUERY` build the whole result set in a tuplestore
  before the function returns — no streaming.** "The current implementation of
  `RETURN NEXT` and `RETURN QUERY` stores the entire result set before returning
  from the function… if a PL/pgSQL function produces a very large result set,
  performance might be poor: data will be written to disk to avoid memory
  exhaustion, but the function itself will not return until the entire result
  set has been generated." [from-docs] Verified: `exec_stmt_return_next`
  [pl_exec.c:3357] appends via `tuplestore_puttuple(estate->tuple_store, …)`
  [:3452/:3470/:3515], and `exec_stmt_return_query` [:3577] fills the same
  `estate->tuple_store` [:3604]. The tuplestore spills to disk past `work_mem`;
  the SRF is materialize-mode, not value-per-call.
- **`SQLSTATE` / `SQLERRM` are only defined inside an exception handler.** "These
  variables are undefined outside exception handlers." [from-docs]
- **A raise inside a handler escapes that handler.** "If a new error occurs
  within the selected `handler_statements`, it cannot be caught by this
  `EXCEPTION` clause, but is propagated out. A surrounding `EXCEPTION` clause
  could catch it." [from-docs] (Each nested handler that catches is its own
  subtransaction level.)
- **`GET STACKED DIAGNOSTICS` (past error) vs `GET DIAGNOSTICS` (current
  state).** Stacked items: `RETURNED_SQLSTATE`, `MESSAGE_TEXT`,
  `PG_EXCEPTION_DETAIL`, `PG_EXCEPTION_HINT`, `PG_EXCEPTION_CONTEXT`,
  `COLUMN_NAME`, `CONSTRAINT_NAME`, `TABLE_NAME`, `SCHEMA_NAME`,
  `PG_DATATYPE_NAME`. Current-state `GET DIAGNOSTICS` exposes `ROW_COUNT` and
  `PG_CONTEXT` (the live call stack). "GET DIAGNOSTICS … retrieves information
  about current execution state (whereas … GET STACKED DIAGNOSTICS … reports
  information about the execution state as of a previous error)." [from-docs]

## Practical corollary

The subtransaction cost is why the idiom "wrap every statement in its own
`BEGIN…EXCEPTION`" is an anti-pattern — each wrap is a savepoint round-trip. And
because `RETURN NEXT`/`QUERY` never stream, a set-returning PL/pgSQL function
that yields millions of rows blocks its caller until the last row is generated,
spilling to disk in between — prefer a plain SQL function or a cursor when the
consumer wants row-at-a-time behavior.

## Links into corpus

- `[[knowledge/docs-distilled/plpgsql-implementation.md]]` — §43.11, plan
  caching + the estate the tuplestore hangs off.
- `[[knowledge/docs-distilled/plpgsql-transactions.md]]` — §43.8, the
  `COMMIT`/`ROLLBACK`-inside-a-procedure rules that interact with these
  subtransaction blocks.
- `[[knowledge/docs-distilled/subxacts.md]]` — §67.3, the subtransaction
  machinery `BeginInternalSubTransaction` drives.
- `[[knowledge/docs-distilled/spi-transaction.md]]` — SPI-level subxact
  control, the layer below `BeginInternalSubTransaction`.
- Skill `plpgsql-internals` (pl_exec.c exec_stmt_* dispatch);
  `snapshot-management` / `multixact` for the isolation seen inside a subxact.

## Verification note

Subtransaction entry/exit verified against
`src/pl/plpgsql/src/pl_exec.c:1820/1859/1885` @ `d774576f6f0`; tuplestore
accumulation against `exec_stmt_return_next` :3357 (puttuple :3452/:3470/:3515)
and `exec_stmt_return_query` :3577/:3604. Diagnostics item lists, variable-
survives-rollback, and the streaming caveat are [from-docs].
