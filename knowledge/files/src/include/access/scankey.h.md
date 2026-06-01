# scankey.h (actually: skey.h)

> **Note on the filename:** The task lists `scankey.h`, but the actual header in the source tree is `source/src/include/access/skey.h`. The C file is `scankey.c`; the header was named `skey.h` for historical brevity. This doc covers `skey.h`.

- **Source path:** `source/src/include/access/skey.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `scankey.c`, `stratnum.h`, every index AM.

## Purpose

Defines `ScanKeyData` / `ScanKey` and the `SK_*` flag bits. The struct is the AM-neutral encoding of one search predicate `column OP constant` (optionally `IS NULL`, `IS NOT NULL`, `ScalarArrayOp`, row comparison, or ORDER BY). Every index scan and many heap scans build a `ScanKey[]` array; how the AM interprets it depends on `sk_strategy` + opclass. [from-comment, skey.h:22-106]

## Top-of-file comment

> "A ScanKey represents the application of a comparison operator between a table or index column and a constant. When it's part of an array of ScanKeys, the comparison conditions are implicitly ANDed. … A ScanKey can also represent a ScalarArrayOpExpr … 'column IS NULL' or 'column IS NOT NULL' … ordering operator invocation 'ORDER BY indexedcol op constant'." [from-comment, skey.h:22-106]

## Key type

- **`ScanKeyData`** (64) — `sk_flags`, `sk_attno`, `sk_strategy`, `sk_subtype`, `sk_collation`, `sk_func` (FmgrInfo), `sk_argument` (Datum).

## Flag bits

- `SK_ISNULL = 0x0001` — sk_argument is NULL.
- `SK_UNARY = 0x0002` — unary operator (NOT IMPLEMENTED, kept for the data model).
- `SK_ROW_HEADER = 0x0004` / `SK_ROW_MEMBER = 0x0008` / `SK_ROW_END = 0x0010` — row comparison support (btree only).
- `SK_SEARCHARRAY = 0x0020` — ScalarArrayOpExpr; sk_argument is an array, OR per element.
- `SK_SEARCHNULL = 0x0040` / `SK_SEARCHNOTNULL = 0x0080` — IS NULL / IS NOT NULL (only AMs with `amsearchnulls` support).
- `SK_ORDER_BY = 0x0100` — ORDER BY operator (KNN-style).
- Bits 16-31 are reserved for AM-private use.

## Key invariants

- For an INDEX scan: `sk_strategy` and `sk_subtype` MUST be correct; for a HEAP scan they're unused. [from-comment, skey.h:30-33]
- For a collation-sensitive operator: `sk_collation` MUST be set. [from-comment, skey.h:34-36]
- `SK_SEARCHARRAY` / `SK_SEARCHNULL` / `SK_SEARCHNOTNULL` are index-scan only; heap scans don't support them. [from-comment, skey.h:49-51]
- Row comparison (`SK_ROW_HEADER` + subsidiary array) is **btree-only**. [from-comment, skey.h:78-106]

## Public surface

- `ScanKeyInit`, `ScanKeyEntryInitialize`, `ScanKeyEntryInitializeWithInfo` (implemented in `scankey.c`).

## Cross-references

- Behaviour: `knowledge/files/src/backend/access/common/scankey.c.md`.

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=7 [from-readme]=0 [inferred]=0 [unverified]=0`
