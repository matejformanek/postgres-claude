# printtup.c

- **Source path:** `source/src/backend/access/common/printtup.c`
- **Lines:** 489
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `printtup.h`, `libpq/pqformat.c`, `tcop/pquery.c` (consumer), `tcop/dest.c`.

## Purpose

The DestReceiver implementation that converts query result tuples into the PostgreSQL frontend/backend wire protocol (`RowDescription` + `DataRow` messages). Both the network backend and `--single` standalone backend funnel through here. Also provides `debugtup` (text dump to stderr for `--single`-mode debugging). [from-comment, printtup.c:1-15]

## Top-of-file comment

> "Routines to print out tuples to the destination (both frontend clients and standalone backends are supported here)." [from-comment, printtup.c:1-12]

## Public surface (non-static functions)

- `printtup_create_DR` (72) — Allocate a `DR_printtup` and set its `pub.{rStartup, receiveSlot, rShutdown, rDestroy}` callbacks. Default `receiveSlot = printtup`; may be replaced.
- `SetRemoteDestReceiverParams` (101) — attach the receiver to a Portal (needed because Bind chooses output formats per column at portal creation time).
- `SendRowDescriptionMessage` (167) — emit a single `RowDescription` ('T') message from a TupleDesc + targetlist + per-column format codes. Used both internally and by `pquery.c` when describing portals.
- `debugStartup` (445), `debugtup` (463) — alternate receivers for printing tuples in standalone mode (text-only, sent via `printatt`).

## Key static state

`DR_printtup` (55) extends `DestReceiver` with: portal, sendDescrip flag, cached TupleDesc, per-attribute `PrinttupAttrInfo[]` (precomputed `typoutput`/`typsend` OID + `FmgrInfo`), shared `StringInfoData buf`, and a per-row `tmpcontext` (reset between rows to bound text-output allocations). [verified-by-code, printtup.c:46-65]

## Functions of note

1. **`printtup_startup`** (112) — Send `RowDescription` (unless suppressed when reusing a portal). Lazy: format codes come from the portal binding; calls `SendRowDescriptionMessage`. [verified-by-code]
2. **`SendRowDescriptionMessage`** (167) — For each column: name, table OID, attnum, type OID, attlen, atttypmod, format code. Looks up `typoutput`/`typsend` on demand via `getTypeOutputInfo`/`getTypeBinaryOutputInfo` (so junk columns still get a row description). [verified-by-code]
3. **`printtup_prepare_info`** (251) — Lazy-init per-attribute info on the first row, or when the TupleDesc changes. Picks `typsend` vs `typoutput` based on the per-column format code from the portal. Caches `FmgrInfo` so output-fn lookups happen once per query. [verified-by-code]
4. **`printtup`** (305) — The hot path. Switch to `tmpcontext`, `slot_getallattrs(slot)`, build a `DataRow` ('D') message: int16 natts, then for each attr: int32 len + bytes (or `-1` for NULL). Reset `tmpcontext` at end. Then `pq_endmessage` (which performs the actual send). [verified-by-code]
5. **`debugtup`** (463) — Standalone-mode dumper used when `IsUnderPostmaster` is false; calls `printatt` (424) which prints `attname = "value"` per column. Strictly text-only. [verified-by-code]

## Key invariants

- The receiver MUST allocate all per-row output workspace in `tmpcontext`, then reset that context — otherwise per-row output-function allocations leak for the duration of the query. [from-comment, printtup.c:62-65; verified-by-code, printtup.c:305-389]
- Format codes (0=text, 1=binary) are decided per-column at Bind time and live in the Portal; the receiver does NOT renegotiate them. [verified-by-code]
- For binary output we call `typsend` (returns `bytea`); for text we call `typoutput` (returns `cstring`) and emit it with a length prefix. NULL is encoded as length = `-1`. [verified-by-code, printtup.c:305-389]
- `attrinfo` is captured by pointer-identity, so a Portal that changes its result TupleDesc mid-stream (e.g. after replan) triggers `printtup_prepare_info` to rebuild the cache. [verified-by-code, printtup.c:259-273]

## Cross-references

- Called from `tcop/pquery.c::PortalRunSelect` (executor → DestReceiver) on every row.
- Bind/Describe in `tcop/postgres.c` set up the portal and indirectly drive `SendRowDescriptionMessage`.
- `spi_dest_startup` / `spi_printtup` (declared in printtup.h) implement an in-memory variant used by SPI; they live in `executor/spi.c` not here.

## Open questions

- The exact ordering rules for sending RowDescription when a Portal is re-used with `Execute(P, n)` followed by another `Execute(P, m)`: the `sendDescrip` flag is set false on the second startup, but I did not trace the Execute/Describe interplay in detail. [unverified]

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`
