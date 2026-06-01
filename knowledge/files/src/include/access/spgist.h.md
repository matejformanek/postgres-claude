# spgist.h

- **Source path:** `source/src/include/access/spgist.h` (229 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Public SP-GiST API: procnum constants + opclass-callback struct definitions. Exposed to opclass implementors. [from-comment, spgist.h:1-9]

## Procnum constants

```c
SPGIST_CONFIG_PROC              1   /* mandatory */
SPGIST_CHOOSE_PROC              2   /* mandatory */
SPGIST_PICKSPLIT_PROC           3   /* mandatory */
SPGIST_INNER_CONSISTENT_PROC    4   /* mandatory */
SPGIST_LEAF_CONSISTENT_PROC     5   /* mandatory */
SPGIST_COMPRESS_PROC            6   /* optional */
SPGIST_OPTIONS_PROC             7   /* optional */
SPGISTNRequiredProc             5
```

## Public structs (opclass callback IO)

- `spgConfigIn` / `spgConfigOut` — prefix type, label type, leaf type, INCLUDE-column support flags.
- `spgChooseIn` / `spgChooseOut` — input value + current inner tuple; output is one of `spgMatchNode` / `spgAddNode` / `spgSplitTuple`.
- `spgPickSplitIn` / `spgPickSplitOut` — input set of leaf tuples; output is new inner-tuple shape + leaf distribution.
- `spgInnerConsistentIn` / `spgInnerConsistentOut` — scan: which node indexes match.
- `spgLeafConsistentIn` / `spgLeafConsistentOut` — scan: does this leaf match.

## SPGIST_MAX_PREFIX_LENGTH

Bounds prefix-tuple size to fit on a page (radix opclasses).
