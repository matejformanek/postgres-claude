# `src/include/access/cmptype.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**45 lines.**

## Role

The `CompareType` enum — a small set of named comparison semantics
(`<`, `<=`, `=`, `>=`, `>`, `<>`, overlap, contained-by) that the
core system can reason about without needing to know which strategy
number each index AM uses. Bridges "core wants to know if this is
the equals operator" and "btree calls it strategy 3, gist calls it
strategy 6".
[verified-by-code] `source/src/include/access/cmptype.h:1-30`

## Public API

`enum CompareType` (lines 31-42):
- `COMPARE_INVALID = 0`
- `COMPARE_LT = 1` (matches `BTLessStrategyNumber`)
- `COMPARE_LE = 2` (matches `BTLessEqualStrategyNumber`)
- `COMPARE_EQ = 3` (matches `BTEqualStrategyNumber`)
- `COMPARE_GE = 4` (matches `BTGreaterEqualStrategyNumber`)
- `COMPARE_GT = 5` (matches `BTGreaterStrategyNumber`)
- `COMPARE_NE = 6` — no btree strategy
- `COMPARE_OVERLAP` (auto-numbered)
- `COMPARE_CONTAINED_BY` (auto-numbered)

## Invariants

- **INV-cmptype-aligned-with-btree:** the first six numeric values are
  **deliberately equal to the btree strategy numbers** (lines 34-39).
  This is a transition convenience: where btree strategies were
  previously hardcoded, the new `CompareType` slots in 1:1.
- **INV-cmptype-incomplete:** the header itself flags it: "Currently,
  this mapping is not fully developed and most values are chosen to
  match btree strategy numbers, which is not going to work very well
  for other access methods." [verified-by-code] lines 27-29. So:
  treat `CompareType` as a **work-in-progress abstraction**, not a
  final API.
- `COMPARE_OVERLAP` and `COMPARE_CONTAINED_BY` carry no numeric
  contract — they're new slots for range/array operators that btree
  has no analog for.

## Notable internals

Each index AM's amapi exposes a mapping function (`amtranslatestrategy`
in `IndexAmRoutine`) that takes the AM's native strategy number and
returns a `CompareType`. The core system uses this to:
- Identify "is this a `=` operator?" for `RowCompareExpr` planning
  (header comment, lines 19-23).
- Generalize EquivalenceClass and outer-join planning across AMs.
- Avoid hardcoding btree-specific strategy numbers in higher layers.

## Trust-boundary / Phase D surface

Not a data-leak surface in itself. But the `CompareType` framework is
the **abstraction layer that custom index AMs plug into**. A custom AM
that mis-implements `amtranslatestrategy` (returns `COMPARE_EQ` for an
operator that isn't actually equals) can mislead the planner into
generating a plan that returns wrong results — a **correctness**
surface, not a security one.

PG18 (new in roughly that era based on the work-in-progress comment)
expanded this framework as part of the broader "make opclass-strategy
mapping less btree-centric" effort.

## Cross-refs

- `access/stratnum.h` — the historical strategy-number constants
  (`BTLessStrategyNumber` etc.).
- `access/amapi.h` — `IndexAmRoutine.amtranslatestrategy`.
- `nodes/primnodes.h` — `RowCompareExpr` uses `CompareType` to
  represent its operator semantics.
- `optimizer/restrictinfo.c` — planner consumer.

## Issues

- **ISSUE-incomplete**: the header itself flags the design as
  unfinished. Future opclass-framework work will likely extend this
  enum; downstream code should NOT switch-with-default-error on
  `CompareType` without expecting new cases.
- **ISSUE-doc**: no mention of `amtranslatestrategy` here as the
  consumer hook; reader has to find it in `amapi.h`.
