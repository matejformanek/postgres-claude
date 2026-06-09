# `src/include/access/skey.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**152 lines.**

## Role

Defines `ScanKeyData` — the workhorse struct representing one
"column op constant" condition for index and heap scans. Plus the
nine `SK_*` flag bits that overload `ScanKeyData` to express
ScalarArrayOp, IS NULL / IS NOT NULL, ORDER BY operators, and row
comparisons.
[verified-by-code] `source/src/include/access/skey.h:1-13`

## Public API

`struct ScanKeyData` (lines 64-73):
- `sk_flags` (int) — bitfield, see SK_* below.
- `sk_attno` (AttrNumber) — table or index column.
- `sk_strategy` (StrategyNumber) — operator strategy in the column's
  opclass (only meaningful for index scans).
- `sk_subtype` (Oid) — strategy subtype.
- `sk_collation` (Oid) — collation to use, if any.
- `sk_func` (FmgrInfo) — lookup info for the operator function.
- `sk_argument` (Datum) — the right-hand value.

`typedef ScanKeyData *ScanKey;` (line 75).

Nine flag bits (lines 115-123):
- `SK_ISNULL` (0x0001) — `sk_argument` is NULL (test always fails for
  heap; index AM may treat specially).
- `SK_UNARY` (0x0002) — declared but "not supported!" (line 116).
- `SK_ROW_HEADER` / `SK_ROW_MEMBER` / `SK_ROW_END` (0x0004 / 0x0008 /
  0x0010) — row comparison subtree.
- `SK_SEARCHARRAY` (0x0020) — ScalarArrayOpExpr (`col op ANY(arr)`),
  index-only.
- `SK_SEARCHNULL` (0x0040), `SK_SEARCHNOTNULL` (0x0080) — IS NULL /
  IS NOT NULL, index-only.
- `SK_ORDER_BY` (0x0100) — distance/order operator for kNN-style
  ORDER BY scans.

Three init functions (lines 129-149):
- `ScanKeyInit` — minimal (no flags, no subtype, no collation).
- `ScanKeyEntryInitialize` — full.
- `ScanKeyEntryInitializeWithInfo` — full + pre-built FmgrInfo.

## Invariants

- **INV-skey-flags-half-reserved:** bits 0-15 system-wide, bits 16-31
  per-index-AM-private [verified-by-code] lines 111-113. AMs MUST NOT
  squat in 0-15.
- **INV-skey-leftarg-index:** "The index column is the left argument
  of the operator" [verified-by-code] line 25. Operator commutators
  may need to be swapped at plan time to enforce this.
- **INV-skey-heap-vs-index:** in heap scans `sk_strategy`/`sk_subtype`
  are unused; in index scans they MUST be set [verified-by-code]
  lines 30-33.
- **INV-skey-array-index-only:** `SK_SEARCHARRAY`, `SK_SEARCHNULL`,
  `SK_SEARCHNOTNULL` work only for index scans and only on AMs that
  set `amsearcharray`/`amsearchnulls` [verified-by-code] lines 49-51.
- **INV-skey-row-header-attno:** for row comparison, the header's
  `sk_attno` is the leading column number [verified-by-code]
  lines 87-89. Sort discipline depends on it.
- **INV-skey-row-subsidiary-uses-support-fn:** in row comparison
  members, `sk_func` points to the btree **comparison support
  function** (returns -1/0/+1), NOT the operator function
  [verified-by-code] lines 101-102. Easy to get wrong.
- **INV-skey-orderby-non-boolean:** `SK_ORDER_BY` operators don't
  yield boolean [verified-by-code] line 55-56. Caller treats result
  as a distance.

## Notable internals

The flag-overloaded design is historical: ScanKey started as a simple
"col op const" struct, then accrued ScalarArrayOp, IS NULL, row
comparisons, and ORDER BY as bit flags rather than separate node
types. A cleaner design would have a union or a sumtype, but
ScanKey is on the hot path and bit-flag dispatch is fast.

Row comparisons (lines 77-105) are btree-only: only btree's
`_bt_first` knows how to walk the subsidiary `ScanKey` array. Other
index AMs would either reject the scan or fall back to filtering.

## Trust-boundary / Phase D surface

`sk_func` is an FmgrInfo cached by the executor; the underlying
`RegProcedure` came from `pg_amop` / `pg_amproc` for that opclass.
A malicious extension defining its own opclass could install a
function with wrong arg types — but at that point the attacker is a
catalog writer, which is already a high-trust role.

ScanKey is the **only path by which planner-known predicates reach
index-AM internals**. For Phase-D-style "limit which rows an index
returns" filtering, this would be the chokepoint to instrument.

## Cross-refs

- `access/valid.h` — `HeapKeyTest` consumes ScanKeys in heap scans.
- `access/stratnum.h` — `StrategyNumber`, `InvalidStrategy`.
- `access/genam.h` — `IndexScanDescData.keyData` ScanKey array.
- `nodes/execnodes.h` — `IndexScanState` carries runtime ScanKeys.
- `subsystems/executor-and-planner.md` — index-qual lowering.

## Issues

- **ISSUE-historical**: `SK_UNARY` declared but unsupported
  (line 116). Could be removed if no extension is known to set it.
- **ISSUE-flag-overload**: nine subtly-different semantic modes
  multiplexed onto one struct. Adding a tenth (e.g. range overlap)
  would push the design.
