# copyto.c

- **Source path:** `source/src/backend/commands/copyto.c`
- **Lines:** 1741
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `copyfrom.c`, `copy.h`, `copyapi.h`, `libpq/pqformat.c` (for binary length-prefixed output and CopyOutResponse), `utils/json.c` (for `FORMAT JSON`).

## Purpose

"COPY <table> TO file/program/client." [from-comment, copyto.c:3-4] Mirror of `copyfrom.c` for the egress direction. Owns formatting (text, CSV, binary, JSON), framing (CopyOutResponse messages on the wire protocol, server-side `WRITE` to file/pipe), and the special `CopyDestReceiver` (so `EXPLAIN (FORMAT TEXT, ANALYZE) COPY (...)` works, and so a `COPY (query) TO ...` can plug the executor output directly into the COPY emitter).

## Public surface

- `BeginCopyTo` (787) — open destination, set up `CopyToState`, look up per-column `typoutput`/`typsend`, write the format-specific header (binary signature, CSV header line if requested).
- `DoCopyTo` (1259) — top-level loop for COPY rel/query TO; calls `CopyRelationTo` for a base relation (delegating to a seq scan) or runs the executor for a query.
- `CopyRelationTo` (1350) — table-am scan emitting one row at a time via `CopyOneRowTo`.
- `CopyOneRowTo` (1414) — serialise a single slot's columns by calling the format's `CopyToOneRow` callback.
- `EndCopyTo` (1238), `EndCopy` (747), `ClosePipeToProgram` (722) — teardown; wait on a `COPY ... TO PROGRAM` child.
- `CopyToGetRoutine` (201) — dispatcher returning text/CSV/binary/JSON `CopyToRoutine`.
- Format implementations: `CopyToTextLikeOneRow` (301) + `CopyToTextOneRow` (282) + `CopyToCSVOneRow` (289); `CopyToBinaryOneRow` (489); `CopyToJsonOneRow` (359).
- Low-level emitters: `CopySendData` (585), `CopySendString` (591), `CopySendChar` (597), `CopySendEndOfRow` (603) — these write to the destination's buffer.

## CopyDestReceiver — the EXPLAIN/COPY (query) plug

`CreateCopyDestReceiver` (1727) returns a `DestReceiver` (the executor's output abstraction; see `tcop/dest.c`) whose `rStartup`/`receiveSlot`/`rShutdown`/`rDestroy` callbacks are `copy_dest_*` here. When you say `COPY (SELECT ...) TO ...`, the executor is started in the usual way with this DestReceiver as its sink, so each tuple flows out through `CopyOneRowTo`. This is also how PG 17+ `EXPLAIN (SERIALIZE)` reports the COPY-serialisation cost without sending bytes.

## Binary format

11-byte signature `PGCOPY\n\377\r\n\0` + 32-bit flag word (only one used: bit 16 = OID column present — long deprecated) + 32-bit length of header-extension area. Each row: 16-bit column count, then per-column 32-bit length (`-1` for NULL) followed by network-byte-order serialised bytes from `typsend`. End-of-data marker: a 16-bit `-1` field count. [verified-by-code]

## JSON format (PG 17+)

`COPY ... TO ... WITH (FORMAT JSON)` emits each row as a JSON object (one per line, NDJSON-style). Implemented in `CopyToJsonOneRow` (359). The companion `FORCE_ARRAY_WRAPPER` option wraps the whole result in a JSON array (`[{...},{...}]`).

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
