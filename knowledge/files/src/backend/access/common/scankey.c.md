# scankey.c

- **Source path:** `source/src/backend/access/common/scankey.c`
- **Lines:** 117
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `skey.h` (the struct + flag definitions; this file's header is `skey.h`, not `scankey.h`).

## Purpose

Three tiny initializers for `ScanKeyData`: filling out the struct with the right operator/function lookup info, attribute number, strategy, collation and argument. ScanKeys are used for both heap and index scans; the index AM determines how they're interpreted via `sk_strategy` + `sk_subtype` + opclass. [from-comment, scankey.c:1-14; from-comment, skey.h:22-63]

## Top-of-file comment

> "scan key support code" — the substantive documentation lives in `skey.h`. [from-comment, scankey.c:1-14]

## Public surface

- `ScanKeyEntryInitialize` (32) — Full form: caller supplies `flags`, attnum, strategy, subtype, collation, RegProcedure (proc OID), and argument Datum. Internally calls `fmgr_info(procedure, &entry->sk_func)` to cache the lookup. The fmgr context must outlive the ScanKey.
- `ScanKeyInit` (76) — Convenience for the common case: zero flags, no subtype, no collation. Used by most heap-scan callers.
- `ScanKeyEntryInitializeWithInfo` (101) — Same as the full form but caller supplies a pre-built `FmgrInfo` (used when initializing many ScanKeys with the same proc — e.g. one comparator per index column).

## Key invariants

- `sk_strategy` and `sk_subtype` MUST be set correctly for index scans; for heap scans they're ignored (`InvalidStrategy`, `InvalidOid`). [from-comment, skey.h:30-33]
- `sk_collation` MUST be set when the operator is collation-sensitive — otherwise sort/compare results are undefined. [from-comment, skey.h:34-36]
- `sk_flags` bits 0-15 are system-defined (`SK_ISNULL`, `SK_ROW_HEADER`, `SK_SEARCHARRAY`, `SK_SEARCHNULL`, `SK_SEARCHNOTNULL`, `SK_ORDER_BY` etc.); bits 16-31 are AM-private. [from-comment, skey.h:110-113]
- `CurrentMemoryContext` at the call site is where `FmgrInfo` subsidiary allocations land — that context must outlive the ScanKey. [from-comment, scankey.c:27-30]

## Cross-references

- Used everywhere a heap or index scan is set up: `genam.c::systable_beginscan`, every index AM's `amrescan` callback, `heapam.c::heap_beginscan` (in the unkeyed case it builds a 0-key array).

## Confidence tag tally
`[verified-by-code]=3 [from-comment]=5 [from-readme]=0 [inferred]=0 [unverified]=0`
