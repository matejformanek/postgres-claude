# decoderbufs — a logical-decoding output plugin that emits Protocol Buffers, not JSON or text

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `xstevens/decoderbufs` @ branch `master`, fetched 2026-07-01. All
> `file:line` cites below point into that repo (not `source/`), since this doc
> characterizes an *external* module's relationship to core idioms.
> **Status: INACTIVE** — the author's own README opens with a WARNING that this
> was "a PoC 4 years ago ... not actively maintained" and redirects to
> Debezium's fork (`README.md:1-2`) `[from-README]`.
> Files fetched: `README.md` (200), `decoderbufs.control` (200), `Makefile`
> (200), `src/decoderbufs.c` (200, 645 lines), `proto/pg_logicaldec.proto`
> (200). The GitHub tree API 403'd through the proxy; the generated
> `src/proto/pg_logicaldec.pb-c.{c,h}` (protobuf-c output) and `LICENSE` were
> NOT fetched — all `Decoderbufs__*` symbols below are inferred from the `.proto`
> + their use in `decoderbufs.c`.

## Domain & purpose

decoderbufs is "a PostgreSQL logical decoder output plugin to deliver data as
Protocol Buffers" (`README.md:8`) `[from-README]`. Like wal2json it is a
change-data-capture (CDC) feed consumed over a logical replication slot or the
SQL slot API (`pg_logical_slot_get_changes(..., 'decoderbufs')`,
`README.md:76-83`) `[from-README]`. The distinguishing choice is the wire
format: instead of JSON text (wal2json) or the ad-hoc human-readable text of
core `test_decoding`, it packs each row change into a binary protobuf
`RowMessage` (`decoderbufs.c:631-634`) `[verified-by-code]`. It targets
PostgreSQL 9.4+, Protocol Buffers 3.x, protobuf-c 1.2.x, and — unusually —
hard-links PostGIS/liblwgeom so it can emit geometry/geography points
(`README.md:29-33`) `[from-README]`.

## How it hooks into PG

Same output-plugin contract as wal2json (see `[[output-plugin-callbacks]]`).
`_PG_init` is an empty no-op (`decoderbufs.c:96`) `[verified-by-code]` — no
GUCs, no executor/planner hooks, no shmem. The whole integration is
`_PG_output_plugin_init(OutputPluginCallbacks *cb)`, which fills the callback
table (`decoderbufs.c:99-106`) `[verified-by-code]`:

- `startup_cb = pg_decode_startup` (`:101`)
- `begin_cb = pg_decode_begin_txn` (`:102`)
- `change_cb = pg_decode_change` (`:103`)
- `commit_cb = pg_decode_commit_txn` (`:104`)
- `shutdown_cb = pg_decode_shutdown` (`:105`)

It registers only the five mandatory callbacks — no `truncate_cb`,
`message_cb`, or `filter_by_origin_cb` (`decoderbufs.c:99-106`)
`[verified-by-code]`; this is a 9.4-era plugin predating those hooks. It opens
with `AssertVariableIsOfType(&_PG_output_plugin_init, LogicalOutputPluginInit)`
(`:100`) `[verified-by-code]`, the standard type-safety guard. The
output-format decision is made per-slot in startup: default is
`OUTPUT_PLUGIN_BINARY_OUTPUT` (`:121`), flipped to
`OUTPUT_PLUGIN_TEXTUAL_OUTPUT` only when the `debug-mode` option is passed
(`:139`) `[verified-by-code]` — the one plugin option it accepts, parsed by
walking `ctx->output_plugin_options` with `parse_bool` (`:123-148`)
`[verified-by-code]`.

Unlike wal2json, decoderbufs **does ship a `.control` file** — it is
installable both as a bare `.so` output plugin AND as a `CREATE EXTENSION`
object: `comment = 'Logical decoding plugin ... Protocol Buffer format'`,
`default_version = '0.1.0'`, `relocatable = true` (`decoderbufs.control:1-3`)
`[verified-by-code]`. (Note the version drift: control says 0.1.0, README says
0.2.0 — `README.md:14`.)

## Where it diverges from core idioms

- **Binary protobuf, not text.** The load-bearing divergence: the change
  callback calls `decoderbufs__row_message__get_packed_size` + `__pack` into a
  freshly `palloc`'d buffer, then `appendBinaryStringInfo(ctx->out, ...)`
  (`decoderbufs.c:631-634`) `[verified-by-code]`. `test_decoding`/wal2json only
  ever `appendStringInfo` textual bytes. The consumer must link the same
  `.proto`; there is no self-describing envelope.
- **Type mapping is a hand-written OID switch, not a generic output function.**
  `set_datum_value()` switches on `typid` to pick a protobuf `oneof` arm
  (`decoderbufs.c:392-488`) `[verified-by-code]`: `BOOLOID→datum_bool`,
  `INT2/INT4OID→datum_int32`, `INT8/OIDOID→datum_int64`,
  `FLOAT4→datum_float`, `FLOAT8→datum_double`,
  `NUMERICOID→datum_double` via a private `numeric_to_double_no_overflow`
  helper (lossy!), text-family OIDs (`CHAR/VARCHAR/BPCHAR/TEXT/JSON/XML/UUID`)
  → `datum_string`, `BYTEAOID→datum_bytes`, `POINTOID→datum_point`
  (`:399-468`) `[verified-by-code]`. The README itself stresses **"NOT ALL OID
  TYPES ARE SUPPORTED"** (`README.md:129`) `[from-README]` — the `default:`
  arm falls back to the type's output function stuffed into `datum_bytes` with
  an `elog(WARNING, "Encountered unknown typid...")` (`:477-484`)
  `[verified-by-code]`. Contrast core, which never enumerates OIDs: it calls
  the registered type output function generically.
- **NUMERIC precision is silently sacrificed for a protobuf primitive.**
  Rather than pass numeric as a string, it routes through
  `numeric_out`→`strtod` (`numeric_to_double_no_overflow`, `:338-358`) —
  admitting "this doesn't seem to be available in the public api" (`:337`) —
  and NaN numerics are dropped entirely (no `datum_case` set, `:427-430`)
  `[verified-by-code]`.
- **Hard PostGIS/liblwgeom dependency baked into the plugin.** Core output
  plugins don't link geometry libraries. decoderbufs `#include "liblwgeom.h"`
  (`:58`), resolves `geometry`/`geography` type OIDs *dynamically* in the
  BEGIN callback via `TypenameGetTypid` (`:168-179`), and converts a POINT
  geography to a protobuf `Point` through `GSERIALIZED`/`LWGEOM` detoasting
  (`geography_point_as_decoderbufs_point`, `:360-389`) `[verified-by-code]`.
  The `Makefile` unconditionally links `-llwgeom` (`Makefile:8`)
  `[verified-by-code]` — so the plugin will not load without PostGIS present.
- **Timestamps as formatted strings, assuming UTC.** `TIMESTAMP`/`TIMESTAMPTZ`
  go through `timestamptz_to_str` into `datum_string` with a code comment
  admitting "THIS FALLTHROUGH IS MAKING THE ASSUMPTION WE ARE ON UTC"
  (`:443-451`) `[from-comment]` — despite the `commit_time` field being
  encoded as microseconds-since-epoch via a `HAVE_INT64_TIMESTAMP` macro
  (`:65-71`, `:567`) `[verified-by-code]`.

## Notable design decisions

- **Whole-tuple emit, not just changed columns.** Every callback path sets
  `n_new_tuple/n_old_tuple = tupdesc->natts` and allocates one
  `DatumMessage*` per attribute (`decoderbufs.c:579-580`, `:591-593`,
  `:613-615`) `[verified-by-code]`; there is no column-diffing.
- **REPLICA IDENTITY drives old-tuple inclusion.** It computes
  `is_rel_non_selective` from `relreplident` (`NOTHING`, or `DEFAULT` with no
  valid replica-index) and skips old/new tuples for UPDATE/DELETE accordingly
  (`:560-562`, `:588`, `:611`) `[verified-by-code]` — mirroring core CDC
  semantics the README calls out (`README.md:87`) `[from-README]`.
- **Per-change private memory context, reset every call.** startup creates an
  `AllocSetContextCreate` child of `ctx->context` stored in
  `DecoderData` (`:117-119`); `pg_decode_change` switches into it, does all
  its work, then `MemoryContextReset(data->context)` on exit (`:557`, `:643-644`)
  `[verified-by-code]`. shutdown does `MemoryContextDelete` (`:160`). This is
  the idiomatic leak-scoping pattern (`[[memory-contexts]]`) — but note it
  *also* hand-writes `row_message_destroy()` to `pfree` each sub-message's
  string/bytes/point payloads (`:187-255`) even though the context reset would
  reclaim them anyway `[verified-by-code]` — belt-and-suspenders, arguably
  redundant.
- **Column names quoted; dropped/system columns skipped.** `tuple_to_tuple_msg`
  uses `quote_identifier(NameStr(attr->attname))` and skips
  `attisdropped || attnum < 0` (`:504-512`) `[verified-by-code]`.
- **TOAST handled by detoast, external-on-disk skipped.** varlena values are
  `PG_DETOAST_DATUM`'d (`:532`), but external-on-disk varlena is dropped with
  `elog(WARNING, "Not handling external on disk varlena")` (`:526-528`)
  `[verified-by-code]` — a known gap (`[[detoast-stream-consumption]]`).
- **fmgr used directly for output functions.** It resolves per-attribute
  `getTypeOutputInfo` and calls `OidOutputFunctionCall` (`:524`, `:439`,
  `:478`) and `DirectFunctionCall1(numeric_out, ...)` (`:343`)
  `[verified-by-code]` (`[[fmgr]]`).
- **`debug-mode` prints a bespoke text dump, not protobuf-text.** The
  `protobuf_c_text_to_string` call is commented out; instead `print_row_msg`
  hand-formats the message (`:627-629`, `:307-335`) `[verified-by-code]`.
- **Empty commit callback.** All work happens in `change_cb`; `commit_cb` is a
  no-op (`:183-185`) — it does not buffer per-transaction like wal2json format
  v1, so each row change is an independent framed protobuf message
  `[verified-by-code]`.

## The proto schema shape

`pg_logicaldec.proto` is proto3, package `decoderbufs`, `optimize_for = SPEED`
(`pg_logicaldec.proto:1-7`) `[verified-by-code]`. Three messages + one enum:
`enum Op { INSERT=0; UPDATE=1; DELETE=2 }` (`:9-13`), `Point{double x,y}`
(`:15-18`), `DatumMessage` with `column_name`, `int64 column_type`, and a
`oneof datum` over the eight scalar arms (`:20-33`), and `RowMessage` carrying
`uint32 transaction_id`, `uint64 commit_time`, `string table`, `Op op`, and
`repeated DatumMessage new_tuple/old_tuple` (`:35-42`) `[verified-by-code]`.
The `column_type` field carries the raw PG type OID as an int64
(`decoderbufs.c:518`) `[verified-by-code]`, pushing final type interpretation
onto the consumer.

## Links into corpus

- `[[wal2json]]` — sibling output plugin; JSON-text where this is binary
  protobuf, and (unlike this one) ships no `.control` file.
- `[[output-plugin-callbacks]]` — the `OutputPluginCallbacks` contract both
  implement.
- `[[logical-decoding-snapshot]]` — the ReorderBuffer/snapshot machinery that
  drives these callbacks.
- `[[memory-contexts]]` — the per-change AllocSet reset pattern used here.
- `[[fmgr]]` — `OidOutputFunctionCall` / `DirectFunctionCall1` usage.
- `[[detoast-stream-consumption]]` — TOAST detoast + the external-on-disk gap.

## Sources

- `https://raw.githubusercontent.com/xstevens/decoderbufs/master/README.md` — HTTP 200
- `https://raw.githubusercontent.com/xstevens/decoderbufs/master/decoderbufs.control` — HTTP 200
- `https://raw.githubusercontent.com/xstevens/decoderbufs/master/Makefile` — HTTP 200
- `https://raw.githubusercontent.com/xstevens/decoderbufs/master/src/decoderbufs.c` — HTTP 200
- `https://raw.githubusercontent.com/xstevens/decoderbufs/master/proto/pg_logicaldec.proto` — HTTP 200
- `https://api.github.com/repos/xstevens/decoderbufs/git/trees/master?recursive=1` — HTTP 403 (proxy; tree listing unavailable, files discovered from README/Makefile)
- NOT fetched: generated `src/proto/pg_logicaldec.pb-c.{c,h}`, `LICENSE`
