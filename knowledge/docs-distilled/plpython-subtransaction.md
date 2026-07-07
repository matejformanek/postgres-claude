---
source_url: https://www.postgresql.org/docs/current/plpython-subtransaction.html
fetched_at: 2026-07-07T20:54:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Python explicit subtransactions (§46.7) — plpy.subtransaction()

Why a context manager is needed to recover from SPI errors, and how the
`__enter__`/`__exit__` protocol maps onto the backend subtransaction API. This
is the load-bearing internals leaf for the whole non-plpgsql-PL family: the same
`BeginInternalSubTransaction` / `Release` / `RollbackAndRelease` triple appears
in all three PL handlers.

## Non-obvious claims

- **The problem it solves is atomicity across multiple `plpy.execute` calls.**
  Without a subtransaction, if the second of two `UPDATE`s raises, the first has
  already taken effect within the surrounding statement's implicit
  subtransaction context — money leaves Joe but never reaches Mary. [from-docs]
- **`plpy.subtransaction()` returns a context-manager object** (`with
  plpy.subtransaction(): ...`, or the pre-2.6 explicit `__enter__`/`__exit__`).
  It guarantees every DB op in its scope is **atomically committed or rolled
  back**. [from-docs]
- **Rollback fires on ANY exception exit, not just DB errors.** "A rollback of
  the subtransaction block occurs on any kind of exception exit … A regular
  Python exception raised inside … would also cause the subtransaction to be
  rolled back." The manager does **not** trap the exception — you still need
  `try`/`except` around the `with`, or the error propagates to the top of the
  Python stack and aborts the whole function. [from-docs]
- **Backend mapping is code-verified.** The context manager's methods call, in
  `source/src/pl/plpython/plpy_subxactobject.c`:
  - `__enter__` → `BeginInternalSubTransaction(NULL)` (`plpy_subxactobject.c:122`)
  - exception exit → `RollbackAndReleaseCurrentSubTransaction()`
    (`plpy_subxactobject.c:181`)
  - normal exit → `ReleaseCurrentSubTransaction()` (`plpy_subxactobject.c:185`)
  [verified-by-code @9d1188f29865] — identical triple to PL/Tcl's
  `subtransaction` command (`pltcl.c:2366/:2376/:2393`), confirming all PLs share
  the same internal-subxact primitive.

## Links into corpus

- [[knowledge/docs-distilled/pltcl-dbaccess.md]] — PL/Tcl's `subtransaction`
  command, same backend primitive.
- [[knowledge/docs-distilled/plperl-builtins.md]] — PL/Perl's `spi_commit`/
  `spi_rollback` (top-level txn control, distinct from inner subxacts).
- [[knowledge/docs-distilled/subxacts.md]] / [[knowledge/docs-distilled/spi-transaction.md]]
  — the subtransaction semantics these wrap.
- `resource-owners` skill (`.claude/skills/resource-owners/`) — internal
  subtransactions own a ResourceOwner released on commit/abort.
