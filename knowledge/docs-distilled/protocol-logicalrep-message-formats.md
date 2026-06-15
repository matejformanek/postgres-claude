---
source_url: https://www.postgresql.org/docs/current/protocol-logicalrep-message-formats.html
fetched_at: 2026-06-14T19:36:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Logical Replication Message Formats (§54.9)

The wire-format reference for the messages a logical-replication output plugin
(`pgoutput`) streams to a subscriber. The byte tags below are what you match on
when writing or debugging a custom output plugin / decoder. Code companion:
the `protocol-logical-replication` distilled doc (the higher-level flow) and the
logicaldecoding-* family.

## The message-tag table (tag → meaning → protocol version)

- Transaction framing: **`B`** Begin, **`C`** Commit, **`O`** Origin, **`M`**
  logical-decoding Message — all **v1** (base). [from-docs]
- Schema: **`R`** Relation (namespace, relname, replica identity, columns), **`Y`**
  Type — **v1**, with an **Int32 Xid prefix added in v2**. [from-docs]
- Row events: **`I`** Insert, **`U`** Update, **`D`** Delete, **`T`** Truncate —
  **v1**, Xid-prefixed since **v2**. [from-docs]
- **Streaming (v2)**: **`S`** Stream Start, **`E`** Stream Stop, **`c`** Stream
  Commit, **`A`** Stream Abort. Stream Abort gained **LSN + timestamp fields in
  v4** (for parallel apply). [from-docs]
- **Two-phase (v3)**: **`b`** Begin Prepare, **`P`** Prepare, **`K`** Commit
  Prepared, **`r`** Rollback Prepared, **`p`** Stream Prepare. [from-docs]
  [cross: knowledge/docs-distilled/two-phase.md]

## Relation (`R`) message — the schema descriptor

- Layout: `Byte1('R')`, `Int32 Xid` (v2+), `Int32 relid`, `String namespace`
  (**empty string means `pg_catalog`**), `String relname`, `Int8 relreplident`
  (replica-identity setting), `Int16 ncolumns`; then per column: `Int8 flags`
  (**bit 1 = part of the key**), `String colname`, `Int32 atttypid`, `Int32
  atttypmod`. [from-docs]
- A subscriber caches the Relation message and applies subsequent row events
  against that cached schema — which is why a `R` precedes the first row event
  for each relation in a stream. [inferred]

## TupleData submessage — shared by Insert/Update/Delete

- `Int16 ncolumns`, then per published column **one kind byte** + payload:
  - **`n`** = NULL (no length/value follows), **`u`** = unchanged TOASTed value
    (**not sent** — subscriber keeps its existing value), **`t`** = text format,
    **`b`** = binary format. For `t`/`b`: `Int32 length` + `Byte_n` value. [from-docs]
- The **`u` (unchanged-TOAST) byte is the subtle one**: an UPDATE that doesn't
  touch a large out-of-line TOAST column ships `u` instead of re-sending the
  value — the apply side must preserve the old value, not write NULL. [inferred]

## Update / Delete old-tuple variants

- **Update** carries the new tuple, optionally preceded by **either** a **`K`**
  (key) **or** an **`O`** (old whole tuple) submessage — never both; which one
  depends on the table's replica identity. **Delete** likewise carries **either
  `K` or `O`**. [from-docs]
  [cross: knowledge/docs-distilled/xact-locking.md]

## Links into corpus
- [[knowledge/docs-distilled/protocol-logical-replication.md]] — the higher-level streaming-replication-protocol flow that carries these.
- [[knowledge/docs-distilled/logicaldecoding-output-plugin.md]] — the output-plugin callbacks that emit these messages.
- [[knowledge/docs-distilled/logicaldecoding-streaming.md]] — the in-progress streaming variants (`S`/`E`/`c`/`A`).
- [[knowledge/docs-distilled/two-phase.md]] — the 2PC events these v3 tags carry.

## Gaps / follow-ups
- The per-field byte offsets above are transcribed from the docs table; for
  exact struct emission see `src/backend/replication/logical/proto.c` (not yet a
  per-file corpus doc — candidate for pg-file-backfiller).
