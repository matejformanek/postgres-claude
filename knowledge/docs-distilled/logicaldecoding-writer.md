---
source_url: https://www.postgresql.org/docs/current/logicaldecoding-writer.html
fetched_at: 2026-06-19T18:50:00Z
anchor_sha: bdae2c20e88d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Logical Decoding Output Writers (logical-decoding ch. 49.6)

The "where does decoded output *go*" leaf of §49 — the writer side, distinct
from the *output plugin* (which decides what the output *looks like*). **This is
a genuinely short page** (~one paragraph); it is captured here for completeness
of the logical-decoding family rather than for volume.

## What the page states (in full)

- Logical decoding output can be consumed via the SQL interface
  (`logicaldecoding-sql.md`) or the walsender streaming interface
  (`logicaldecoding-walsender.md`); it is **also possible to add more output
  methods.** [from-docs]
- To add an output method, **three functions must be provided: one to read WAL,
  one to prepare writing output, and one to write the output.** [from-docs]
- The page points implementers at the source — `src/backend/replication/logical/logicalfuncs.c`
  (the SQL-interface writer is the worked reference) — and cross-references the
  output-plugin "Functions for Producing Output" section (the `OutputPluginPrepareWrite`
  / `OutputPluginWrite` pair the plugin calls). [from-docs]

## The plugin-vs-writer distinction (why two concepts)

- **Output plugin** = *what* the change stream looks like (callbacks like
  `change_cb`, emitting via `OutputPluginWrite`). See `output-plugin-callbacks.md`.
- **Output writer** = *where/how* those bytes are delivered (SQL result rows vs.
  walsender CopyData vs. a custom sink). The plugin is writer-agnostic; the
  writer supplies the read-WAL / prepare-write / write trio the decoding loop
  drives. [inferred from the three-function contract]

## Links into corpus

- [[knowledge/idioms/output-plugin-callbacks.md]] — the plugin side
  (`OutputPluginPrepareWrite`/`OutputPluginWrite`) this writer trio pairs with.
- [[knowledge/docs-distilled/logicaldecoding-sql.md]] — the SQL writer
  (logicalfuncs.c) the page names as reference.
- [[knowledge/docs-distilled/logicaldecoding-walsender.md]] — the walsender
  writer.
- [[knowledge/docs-distilled/logicaldecoding-output-plugin.md]] — the
  producing-output functions cross-referenced here.
- [[knowledge/subsystems/replication.md]] — owning subsystem.

## Open questions

- Pin the actual signatures of the read-WAL / prepare-write / write trio in
  `logicalfuncs.c` (and whether any out-of-core writer exists) at anchor
  `bdae2c20e88d` on a logical-decoding deep read.
