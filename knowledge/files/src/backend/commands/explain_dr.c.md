# `src/backend/commands/explain_dr.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~311
- **Source:** `source/src/backend/commands/explain_dr.c`

PG18+ addition: a DestReceiver implementation backing
`EXPLAIN (SERIALIZE TEXT|BINARY)`. It runs each output tuple through the
wire-format datatype `out`/`send` functions (mirroring `printtup.c`) but
discards the bytes, capturing total bytes, optional timing, and optional
buffer usage. Lets users measure deTOAST/output-function overhead that's
otherwise only visible when actually hitting the network. [verified-by-code]

## API / entry points

- `CreateExplainSerializeDestReceiver(es)` — public factory; the
  receiver's `mydest` is `DestExplainSerialize`. [verified-by-code]
- `GetSerializationMetrics(dest)` — public; returns a
  `SerializeMetrics` for the receiver, or all-zeroes if `dest` is an
  `IntoRel` receiver (the EXPLAIN target is CTAS). [from-comment]
- Static DestReceiver vtable: `serializeAnalyzeStartup` /
  `serializeAnalyzeReceive` / `serializeAnalyzeShutdown` /
  `serializeAnalyzeDestroy`. [verified-by-code]

## Notable invariants / details

- `SerializeDestReceiver` struct holds: per-row `tmpcontext`,
  StringInfo `buf` reused across rows (matches `printtup`), `finfos`
  array of `FmgrInfo` for typoutput/typsend, and the `metrics` accumulator.
  [verified-by-code]
- `serialize_prepare_info` is a stripped subset of
  `printtup_prepare_info`: format is uniform across all columns
  (`text`=0 / `binary`=1), so the code is simpler. Triggers ERROR on
  any other format code. [from-comment]
- `serializeAnalyzeReceive` (line 105) closely mirrors `printtup`:
  `pq_beginmessage_reuse(buf, PqMsg_DataRow)`, `pq_sendint16`(natts),
  per-attribute output/send call, length prefix. Critically it does
  **NOT** call `pq_endmessage_reuse` — that would actually send data.
  Just counts `buf->len` into `bytesSent`. [from-comment]
- Per-row tmpcontext (line 130-131, 186-188): switch in before output
  function call, reset after. Same pattern as `printtup`. Ensures
  output-function leaks don't grow.
- Timing/buffer instrumentation conditional on `es->timing` /
  `es->buffers` (lines 117-121, 189-200). Avoids cost when not asked.
- Format constant: 0=text, 1=binary, matching pq wire-protocol format
  code. [from-comment]

## Potential issues

- Line 218 `Assert(false)` in `serializeAnalyzeStartup` if `serialize
  == EXPLAIN_SERIALIZE_NONE`. Defensive — if `ParseExplainOptionList`
  set `serialize == NONE` we shouldn't be here. Crash in production
  builds would degrade gracefully (skip switch arms). [unverified]
- `serializeAnalyzeShutdown` carefully nulls `finfos`, `buf.data`,
  `tmpcontext` after free. Looks paranoid; the receiver may be reused
  by a stmt-level rescan? Worth confirming. [unverified]
- Buffer usage accumulation uses `BufferUsageAccumDiff` and a local
  snapshot of `pgBufferUsage` — race-free because it's per-process.

## Synthesized by
<!-- backlinks:auto -->
