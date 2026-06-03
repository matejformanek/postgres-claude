# `src/backend/utils/adt/rowtypes.c`

- **File:** `source/src/backend/utils/adt/rowtypes.c` (2052 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O and comparison entry points for **generic composite types**
(`RECORD` and named row types). Backs `record_in`/`record_out`,
`record_recv`/`record_send`, the comparison operators
`record_eq`/`ne`/`lt`/`le`/`gt`/`ge`/`cmp`, the bytewise
`record_image_eq`/`ne`/`lt`/`le`/`gt`/`ge`/`cmp` family, and the
hash functions.

The crucial property: composite values are stored as
`HeapTupleHeader` Datums with embedded type-id/typmod so the
generic functions can re-discover the schema at runtime.

## Key functions

### Text I/O

- `record_in(string, tupType, tupTypmod)` (`:73-323`) — accepts the
  `( v1 , v2 , ... )` syntax. Calls **`check_stack_depth()` at `:92`**
  to bound recursion through record-typed columns. Refuses anonymous
  `RECORD` when typmod is -1 (`:102-105`). Caches per-call `RecordIOData`
  + per-column `ColumnIOData` in `fn_extra` so the input proc is
  fmgr-resolved once per fn-call series (`:119-141`). The parser
  loop (`:165-279`) handles quoted strings, backslash escapes, and
  doubled `""` inside quotes, then feeds the de-quoted column data to
  `InputFunctionCallSafe` (`:267-273`, soft-error-aware via
  `escontext`). [verified-by-code]
- `record_out(rec)` (`:328-477`) — same caching pattern, uses
  `nq` quote-needed detection to decide if the per-column text needs
  quoting + backslash-escaping. `check_stack_depth()` at `:344`.
  [verified-by-code]

### Binary I/O

- `record_recv(buf, tupType, tupTypmod)` (`:480-684`) — reads natts +
  per-column `(oid, len, bytes)` tuples. Validates that received OIDs
  match the schema (`:560-585`), rejects unknown types. Per-column
  bytes go through `ReceiveFunctionCallSafe`. [verified-by-code]
- `record_send(rec)` (`:687-820`) — symmetric: writes natts, then per
  column `(typid, VARSIZE-VARHDRSZ, bytes)`. [verified-by-code]

### Comparison

- `record_cmp(fcinfo)` (`:823-1064`) — workhorse for ordered
  comparison. Pulls `TypeCacheEntry` for each column, looks up
  `cmp_proc_finfo`, walks both deformed tuples in parallel. Per-column
  comparisons go through `FunctionCall2Coll` with appropriate collation.
  Caches `RecordCompareData` in `fn_extra` (`:60-66` struct).
  [verified-by-code]
- `record_eq` (`:1067+`) — equality-only, uses `eq_opr_finfo` for
  efficiency.
- `record_image_eq`/`record_image_cmp` family (`:1595+`) — **bytewise**
  comparison ignoring user-defined equality semantics; used by
  things like REPLICA IDENTITY change detection. Compares raw Datum
  bytes after detoasting; respects only typlen/typalign.
- Hash variants further down (`:1770+`).

## Phase D notes

- **Recursion depth on nested composite**: `check_stack_depth()` is
  called at `record_in:92` and `record_out:344`. Both `record_recv`
  and `record_send` lack an explicit `check_stack_depth()` in the
  header (verified by grep — only the two text I/O sites have it).
  Recursion through binary I/O still calls back into `record_recv`
  via `ReceiveFunctionCall`, which goes through fmgr; the per-call
  `check_stack_depth()` in `record_in`/`record_out` covers text
  recursion. For deeply-nested record-of-record inputs over the
  binary protocol, depth is bounded only by the implicit fmgr-stack
  growth and the per-column `InputFunctionCallSafe` paths that may
  recurse into `record_in`. [verified-by-code]
- **Quote parsing**: `record_in` reads until `,` or `)` at top level,
  but inside `"..."` continues through `,`/`)`. A malformed input
  with unclosed quote eventually hits `ch == '\0'` and errsaves a
  clean "Unexpected end of input" error (`:212-219`). [verified-by-code]
- **Field-count validation**: too-few columns caught by `*ptr` != `,`
  branch (`:181-193`); too-many by `*ptr != ')'` after loop
  (`:281-288`). Dropped columns are skipped (`:172-178`), preserving
  NULL placement. [verified-by-code]
- **Type-id round-trip**: `record_recv` validates each column's typid
  against the expected schema, preventing a spoofed binary value
  from injecting an unexpected column type. [verified-by-code]

## Potential issues

- [ISSUE-dos: `record_recv` does NOT call `check_stack_depth()` (only
  `record_in`/`record_out` do). For deeply-nested record-of-record
  values over the binary protocol, recursion via
  `ReceiveFunctionCallSafe` → `record_recv` relies on the C stack
  guard catching it indirectly; under copy-binary protocol an
  attacker controlling the bytes could try to nest deeply (maybe)]
- [ISSUE-undocumented-invariant: `RecordIOData` cache invalidation
  triggers on `record_type`/`record_typmod` change, but ALTER TYPE
  on a domain-of-composite is not covered explicitly — relies on
  fn_mcxt reset elsewhere (maybe)]
- [ISSUE-wire-protocol: `record_recv` per-column-len is uint32 from
  wire; `pq_getmsgbytes` checks against remaining buffer, so a
  truncated message errors cleanly via `pq_getmsgend` (info)]

## Cross-references

- `source/src/backend/utils/cache/typcache.c` — `lookup_rowtype_tupdesc`,
  `TypeCacheEntry.cmp_proc_finfo`.
- `source/src/backend/access/common/heaptuple.c` — `heap_form_tuple`,
  `heap_deform_tuple`.
- `source/src/backend/utils/adt/jsonfuncs.c` — `populate_record*` is the
  json→record companion (separate path).

## Confidence tag tally
- `[verified-by-code]` × 8
- `[from-comment]` × 1
