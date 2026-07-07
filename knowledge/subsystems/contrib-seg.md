# contrib-seg (line segments / float intervals)

- **Source path:** `source/contrib/seg/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.4` (per `seg.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

The **1-dimensional cousin of cube**. Represents a closed
interval `[lower, upper]` on the real line, with optional
sentinel values for `<lower` (any value less than) and
`>upper` (any value greater than). Originally designed for
chemical-laboratory data where measurements have uncertainty
ranges.

The historical motivation: chemists report values like
`< 0.5` (below detection limit) or `5.5 ± 0.3` — neither fits
the standard `numeric` type. `seg` was the contrib answer.

## 2. The single 1106-LOC file

```
source/contrib/seg/seg.c    1106 LOC
```

[verified-by-code `wc -l`]

All in one file: parser, operators, GiST opclass.

## 3. The text representation

| Form | Meaning |
|---|---|
| `5.0` | Single-value (zero-width interval) |
| `5.0..10.0` | Closed interval [5.0, 10.0] |
| `<5.0` | Open lower (any value < 5.0) |
| `>5.0` | Open upper (any value > 5.0) |
| `~5.0` | Approximate (preserves the tilde in output) |

The `~` prefix doesn't change the value or any operator —
it's just a textual marker preserved for chemistry-data
compatibility. So `seg_in('~5.0')` and `seg_in('5.0')`
behave identically except in `seg_out`.

## 4. SQL surface — accessors

| Function | Returns |
|---|---|
| `seg_lower(seg)` | Lower bound (float) |
| `seg_upper(seg)` | Upper bound (float) |
| `seg_center(seg)` | (lower + upper) / 2 |
| `seg_size(seg)` | upper - lower |

[verified-by-code `seg.c:49-54`]

## 5. SQL surface — operators

| Op | Meaning |
|---|---|
| `s1 @> s2` | s1 contains s2 |
| `s1 <@ s2` | s2 contains s1 |
| `s1 && s2` | overlap |
| `s1 = s2` | equal |
| `s1 < s2` | s1 entirely to the left |
| `s1 > s2` | s1 entirely to the right |
| `s1 << s2` | strictly left (no overlap) |
| `s1 >> s2` | strictly right (no overlap) |
| `s1 &< s2` | doesn't extend right of s2 |
| `s1 &> s2` | doesn't extend left of s2 |

The richer comparison set (vs core `int4range` / `numrange`)
includes the "extends" operators — useful for queries like
"find rows whose interval doesn't extend past 100."

## 6. The GiST opclass

`gist_seg_ops` provides:

- `gseg_consistent` — does this internal node's bounding
  segment overlap the query?
- `gseg_compress` / `gseg_decompress` — internal-node
  bounding-segment representation.
- `gseg_picksplit` — split heuristic.
- `gseg_penalty` — insert cost estimate.
- `gseg_union` — union of segments at an internal node.
- `gseg_same` — equality check for index dedup.

[verified-by-code `seg.c:59-65`]

The picksplit heuristic: sort by lower-bound, pick the median
as the split point. Simple but works well for typical
chemistry data (clustered measurements).

## 7. Why not int4range / numrange?

PG's core `int4range`, `int8range`, `numrange`, `tsrange`,
`tstzrange`, `daterange` types cover most general-purpose
range needs and have GiST support too. `seg` predates these
(it was contrib before the core range types were added).

Differences:
- `seg` only handles `float`-typed bounds.
- `seg`'s `~5.0` syntax is unique.
- `seg`'s `<5.0` / `>5.0` open-on-one-side form differs from
  range's `(,5.0]` / `[5.0,)` syntax.

For new code, use `numrange` instead. `seg` lives on for the
chemistry-data legacy.

## 8. Production-use guidance

- **For new schemas, use `numrange`** (or another core range
  type).
- **For existing chemistry data**, `seg` is correct +
  performant.
- **GiST indexing** — covers all the range queries; no
  performance penalty vs `numrange`.

## 9. Invariants

- **[INV-1]** float bounds only; not parameterizable.
- **[INV-2]** Closed by default; `<5.0` / `>5.0` are open
  via sentinel values, not via flags.
- **[INV-3]** `~5.0` is text-preserved but semantically
  equivalent to `5.0`.
- **[INV-4]** Trusted extension.

## 10. Useful greps

- The entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/seg/seg.c | head -20`
- The text representation parser:
  `grep -n 'seg_in\|seg_yyparse' source/contrib/seg/seg.c | head -5`

## 11. Cross-references

- `knowledge/subsystems/contrib-cube.md` — companion N-D
  cousin; same operator philosophy.
- `knowledge/subsystems/access-method-apis.md` — GiST AM
  contracts.
- `knowledge/subsystems/contrib-btree_gist.md` — sibling
  contrib; GiST opclasses for scalar types.
- `.claude/skills/access-method-apis.md` — index-AM
  contracts.
- `source/contrib/seg/seg.c` — implementation (1106 LOC).

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**2 files.**

| File |
|---|
| [`contrib/seg/seg.c`](../files/contrib/seg/seg.c.md) |
| [`contrib/seg/segdata.h`](../files/contrib/seg/segdata.h.md) |

<!-- /files-owned:auto -->
