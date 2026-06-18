---
source_url: https://www.postgresql.org/docs/current/spi-visibility.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Visibility of Data Changes via SPI (internals ch. 47.5)

The leaf chapter that pins down *when a query run through SPI sees changes made
earlier in the same transaction or command.* It is the SPI-level statement of
the general PostgreSQL command-visibility rules, gated by the SPI read/write
flag. Pairs with `idioms/snapshot-acquisition.md`, `idioms/combocid-handling.md`,
and the `fmgr-and-spi` skill.

## Non-obvious claims

- **A command never sees its own changes.** "During the execution of an SQL
  command, any data changes made by the command are invisible to the command
  itself." The canonical example: `INSERT INTO a SELECT * FROM a;` — the rows
  the INSERT is producing are invisible to its own SELECT, so it does not loop
  forever. [from-docs]
- **Later commands see earlier commands' changes — including commands started
  *inside* the earlier one.** "Changes made by a command C are visible to all
  commands that are started after C, no matter whether they are started inside C
  (during the execution of C) or after C is done." This is exactly the
  command-counter (CID) snapshot semantics surfaced at the SPI level. [from-docs]
- **The SPI read/write flag picks which rule a sub-command follows.** A command
  executed via SPI *inside* a function called by an outer SQL command obeys one
  of the two rules above depending on the read/write flag passed to SPI:
  - **read-only mode** → the SPI command **cannot** see the calling command's
    changes (behaves as "started during C", rule 1 territory).
  - **read-write mode** → the SPI command **can** see all changes made so far
    (behaves as a later command, rule 2). [from-docs]
- **PLs derive the flag from function volatility, not from anything you pass.**
  All standard procedural languages set SPI read-write mode from the function's
  volatility attribute: `STABLE` and `IMMUTABLE` functions run their SPI
  commands **read-only**; `VOLATILE` functions run them **read-write**.
  [from-docs]
- **Practical consequence:** marking a PL function `STABLE` when it actually
  needs to observe its own caller's just-made changes is a correctness bug, not
  just a planner hint — the snapshot it runs under will not include those
  changes. Conversely a `VOLATILE` function sees the live, incrementing state.
  [inferred]
- The page does **not** itself mention `CommandCounterIncrement` by name, but the
  two rules are precisely what `CommandCounterIncrement()` between commands
  implements: bumping the command ID so the next command's snapshot includes the
  prior command's writes. [inferred → see corpus]

## Links into corpus

- [[knowledge/docs-distilled/spi.md]] — overview; the read/write flag is set at
  `SPI_connect_ext()` / via the read_only argument to `SPI_execute`.
- [[knowledge/docs-distilled/mvcc.md]] — the chapter-level statement of the same
  visibility rules at the transaction-isolation level.
- [[knowledge/idioms/snapshot-acquisition.md]] / [[knowledge/idioms/snapshot-static-and-current.md]]
  — how the snapshot + command ID that enforce these rules are taken.
- [[knowledge/idioms/combocid-handling.md]] — CID machinery behind "a command
  can't see its own changes".
- [[knowledge/idioms/heap-tuple-visibility-mvcc.md]] — the tuple-level
  HeapTupleSatisfies* logic this visibility ultimately resolves to.
- [[knowledge/files/src/backend/executor/spi.c.md]] — where SPI threads the
  read-only flag into snapshot management.

## Open questions

- Exact `spi.c` path that translates the read-only flag into
  `GetTransactionSnapshot` vs `GetActiveSnapshot` / `PushActiveSnapshot` — verify
  on a future deep read at anchor `ab3023ad1e68`.
