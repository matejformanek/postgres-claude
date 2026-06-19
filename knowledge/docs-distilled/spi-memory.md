---
source_url: https://www.postgresql.org/docs/current/spi-memory.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# SPI Memory Management (internals ch. 47.3)

The leaf chapter under §47 SPI that the overview (`spi.md`) only gestures at.
This is the single most footgun-prone part of the SPI ABI: **where a `palloc`
lands while you are connected to SPI, and what survives `SPI_finish()`.** Pairs
with the `fmgr-and-spi` skill, `idioms/spi.md`, and `idioms/memory-contexts.md`.

## Non-obvious claims

- **`SPI_connect()` switches the current context out from under you.** It
  creates a *new private SPI procedure context* and makes it current, so every
  `palloc` / `repalloc` / SPI utility allocation you do *after* connecting lands
  in that transient context — **not** in the caller's context. [from-docs]
- **`SPI_finish()` destroys that whole context.** It restores the *upper
  executor context* (whatever was current at `SPI_connect()` time) and frees
  everything allocated in the SPI procedure context. Any pointer you got from a
  plain `palloc` between connect and finish is **dangling** after finish.
  [from-docs]
- **Therefore: you cannot return a pass-by-reference Datum allocated with plain
  `palloc` while connected.** The doc states it flatly — "you cannot allocate
  that memory using `palloc`, at least not while you are connected to SPI."
  [from-docs]
- **`SPI_palloc` / `SPI_repalloc` / `SPI_pfree` allocate in the *upper executor
  context*, not the SPI context.** That is the whole point: memory from these
  survives `SPI_finish()` and is the correct home for return values. [from-docs]
- **The tuple-copying helpers also target the upper executor context**, so their
  results survive finish: `SPI_copytuple` (copy a row), `SPI_returntuple`
  (package a row as a `Datum`), `SPI_modifytuple` (build a row by replacing
  selected columns of an existing one). [from-docs]
- **`SPI_freetuple` frees a row that lives in the upper executor context** — the
  counterpart to the copy helpers, for when you allocated a survivor you no
  longer need. [from-docs]
- **`SPI_freetuptable` frees a result set** (`SPI_tuptable`) produced by
  `SPI_execute` and friends. Result tuptables otherwise accumulate until the SPI
  context is torn down — in a long loop that re-executes, free each one or you
  leak within the procedure context. [from-docs]
- **`SPI_freeplan` frees a *saved* prepared statement.** Saved plans (via
  `SPI_prepare` + `SPI_keepplan`/`SPI_saveplan`) live outside the per-call SPI
  context on purpose, so `SPI_finish()` does *not* reclaim them — they must be
  freed explicitly or they persist for the session. [from-docs/inferred]
- **Survivor checklist** (lives past `SPI_finish`): anything from `SPI_palloc`,
  `SPI_copytuple`, `SPI_returntuple`, `SPI_modifytuple`, and saved plans.
  **Casualty checklist** (gone at `SPI_finish`): plain `palloc`/`repalloc` done
  while connected, and any tuptable you didn't explicitly free. [from-docs]
- **Idiomatic pattern:** `SPI_connect()` → use plain `palloc` freely for scratch
  → use `SPI_palloc`/copy-helpers only for the value you will return →
  `SPI_finish()` → `return` the survivor. The scratch is auto-reclaimed; the
  survivor rode out on the upper executor context. [from-docs]

## Why this design

The transient SPI procedure context is a leak-containment device: a PL function
that runs hundreds of SPI queries can `palloc` scratch with abandon, and one
`SPI_finish()` reclaims all of it at once (the memory-context "free the whole
arena" idiom). The cost is the discipline above — survivors must be explicitly
promoted to the upper context. This is the same upper/lower split that
`ExecutorState` vs per-tuple contexts use in the executor. [inferred]

## Links into corpus

- [[knowledge/docs-distilled/spi.md]] — the §47 overview (lifecycle bracket,
  read-only flag); this page is its memory-management leaf.
- [[knowledge/docs-distilled/spi-transaction.md]] — sibling leaf §47.4;
  `SPI_commit` interacts with which context survives.
- [[knowledge/idioms/spi.md]] — the SPI usage idiom.
- [[knowledge/idioms/memory-contexts.md]] / [[knowledge/idioms/memory-context-api-and-dispatch.md]]
  — the upper/lower context model SPI builds on.
- [[knowledge/files/src/backend/executor/spi.c.md]] — the implementation of all
  the functions named here (`_SPI_procmem` vs upper-context switching).
- [[knowledge/files/src/pl/plpython/plpy_spi.md]] — a real SPI client showing
  the connect/finish bracket in practice.

## Open questions

- Exact line where `spi.c` performs the upper-vs-SPI context switch for
  `SPI_palloc` — verify against `source/src/backend/executor/spi.c` at anchor
  `ab3023ad1e68` on a future deep read.
