# utils/multirangetypes.h — MultirangeType varlena

Source: `source/src/include/utils/multirangetypes.h` (150 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

On-disk MultirangeType varlena and the full set of multirange/range op internal functions. Multiranges are sequences of (sorted, disjoint, non-empty) ranges.

## Public API / on-disk format

```
<vl_len_>           varlena header
<multirangetypid>   Oid
<rangeCount>        uint32 (number of contained ranges)
<ShortRangeType>[]  rangeCount ranges, variable-length, NOT indexable
```

`multirangetypes.h:21-38` [from-comment]. Key remark: "we can't really index into this list" — must iterate via `multirange_deserialize`.

## Invariants

- **INV-multirange-disjoint-sorted** [inferred from comments + `make_multirange`]: contained ranges are sorted by lower bound, disjoint, non-empty, and non-adjacent. The header doesn't restate it but every internal op (`multirange_*_internal`) assumes it.
- **INV-multirange-not-indexable** [verified-by-code/comment, `multirangetypes.h:34-37`]: ranges inside are variable-length (their bound values + flags), so `multirange[i]` requires walking from the start. The struct is just the prefix.
- **INV-multirange-empty-rangeCount=0** [verified-by-code, `multirangetypes.h:42`]: `MultirangeIsEmpty(mr) ⇔ rangeCount == 0`.
- **INV-multirange-ShortRangeType** [from-comment, `multirangetypes.h:34-37`]: stored sub-ranges use a "short" form (no rangetypid OID — that's implicit in the multirange's own typid).

## Notable internals

- `multirange_deserialize(rangetyp, mr, &count, &ranges)` (`multirangetypes.h:132-135`) is the only safe accessor — allocates an array of full RangeType pointers.
- `make_multirange` (`multirangetypes.h:136-138`) is the canonical constructor; it asserts/normalizes the disjoint+sorted invariant.

## Trust-boundary / Phase-D surface

- **multirange_recv** [inferred — header silent]: must validate (a) `rangeCount` against varlena length, (b) that the contained ranges are sorted/disjoint/non-empty (otherwise downstream ops misbehave silently). Header surfaces neither.
- **Integer overflow on `rangeCount * sizeof(RangeType *)`** — header allows up to UINT32_MAX ranges; downstream `multirange_deserialize` palloc must guard against that.

## Cross-refs

- `knowledge/files/src/include/utils/rangetypes.md` — sub-range format.
- `source/src/backend/utils/adt/multirangetypes.c` — implementation including recv/validation.

## Issues

- `[ISSUE-DOC: ShortRangeType is undocumented at header level (low)]` — `multirangetypes.h:34-37` mentions "ShortRangeType structs" but no struct definition or pointer to where it lives.
- `[ISSUE-INVARIANT: sorted/disjoint contract is implicit (medium)]` — header should state this clearly; downstream code crashes/loops if a recv path accepts a malformed multirange with overlapping or unsorted ranges.
