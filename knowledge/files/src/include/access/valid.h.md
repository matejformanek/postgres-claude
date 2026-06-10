# `src/include/access/valid.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**59 lines.**

## Role

Defines one inline function: **`HeapKeyTest`** — apply an array of
ScanKeys to a heap tuple and return true if all match. This is the
inner-loop predicate evaluator used by heap seqscan and by various
re-check paths.
[verified-by-code] `source/src/include/access/valid.h:1-15`

Despite the name "valid.h" (suggesting `HeapTupleSatisfies*` MVCC
dispatch), this header is actually about **scan-key qualification**,
not MVCC visibility. MVCC dispatch lives in `access/heapam.h` and
`utils/snapmgr.h`. The brief's "HeapTupleSatisfies* dispatch" framing
is historical; the actual MVCC routines moved out long ago.

## Public API

`static inline bool HeapKeyTest(HeapTuple tuple, TupleDesc tupdesc, int nkeys, ScanKey keys)`
(lines 27-56).

Walks `keys[0..nkeys-1]`. For each key:
1. If `sk_flags & SK_ISNULL` → return false.
2. `heap_getattr(tuple, attno, ...)`; if isnull → return false.
3. `FunctionCall2Coll(&sk_func, sk_collation, atp, sk_argument)`;
   if result is false → return false.
4. Otherwise continue.

Implicit AND across all keys.

## Invariants

- **INV-heapkeytest-null-fails:** any NULL on either side (column or
  key) fails the test — strict SQL semantics for indexable
  comparison operators. [verified-by-code] lines 39-45. The
  `SK_SEARCHNULL`/`SK_SEARCHNOTNULL` flags (defined in `skey.h`) are
  index-AM-only; `HeapKeyTest` doesn't handle them, by design (it's
  for heap scans).
- **INV-heapkeytest-binary-strict:** assumes every key is a binary
  operator with the heap column on the left and `sk_argument` on the
  right. Unary, row, and ScalarArrayOp keys are NOT supported here —
  they have to be expanded into proper ExprState evaluation upstream.
- **INV-heapkeytest-leftarg-table:** "The index column is the left
  argument of the operator" (`skey.h` line 25) — same convention
  applies here for heap columns.

## Notable internals

Inlined deliberately to avoid call overhead in the seqscan hot path.
Uses `FunctionCall2Coll` (collation-aware fmgr 2-arg call) — note the
collation comes from `sk_collation`, set by the scan-key initializer.

Used in `heapgettup` (`access/heap/heapam.c`) when the planner pushes
a small number of simple quals down to heapam as `ScanKey`s rather
than as a full ExprState. That happens for index-only-style filters
and for some scans of system catalogs.

## Trust-boundary / Phase D surface

Not directly. But it IS the hot-path that **evaluates user-supplied
expressions inside the heap scan loop**. The `sk_func` FmgrInfo is set
up by `ScanKeyInit` from a `RegProcedure` — if a malicious extension
substitutes a function with an unexpected signature, `FunctionCall2Coll`
will misbehave (read garbage args or longjmp). PG defends against this
by trusting `pg_proc` rows; the ACL is on `CREATE FUNCTION`, not on
ScanKey.

## Cross-refs

- `access/skey.h` — `ScanKey`, `ScanKeyInit`, flag bits.
- `access/htup.h`, `access/htup_details.h` — `HeapTuple`,
  `heap_getattr`.
- `fmgr.h` — `FunctionCall2Coll`.
- `src/backend/access/heap/heapam.c` — primary caller (`heapgettup`).

## Issues

- **ISSUE-misnomer**: "valid.h" predates the move of MVCC dispatch to
  `heapam.h`/`snapmgr.h`. The file would more honestly be
  "scankey_eval.h" now. (Not worth renaming — too much downstream
  churn.)
- **ISSUE-doc**: header comment "tuple qualification validity
  definitions" (line 4) is vague; doesn't say "this is for ScanKey
  evaluation".
