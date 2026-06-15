---
path: src/test/modules/spgist_name_ops/spgist_name_ops.c
anchor_sha: e18b0cb7344
loc: 504
depth: read
---

# src/test/modules/spgist_name_ops/spgist_name_ops.c

## Purpose

A worked example of writing an SP-GiST operator class. Indexes values of type
`name` using `text` storage — basically a stripped-down clone of
`src/backend/access/spgist/spgtextproc.c` with collation-aware logic removed,
to keep the example minimal. Demonstrates all five SP-GiST support functions:
`config`, `choose`, `picksplit` (reused from core), `inner_consistent`,
`leaf_consistent`, plus a `compress` function for the type-conversion edge
case. `[verified-by-code]`

This file is the canonical "show me how to write a non-trivial SP-GiST
opclass" example for extension authors.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `spgist_name_config` | `spgist_name_ops.c:33` | Declares prefix=TEXTOID, label=INT2OID, leaf=TEXTOID; canReturnData + longValuesOK |
| `spgist_name_choose` | `:124` | Descent decision: descend to existing child, add a new child, or split the tuple |
| `spgist_name_inner_consistent` | `:266` | Inner-node query filter — reconstruct prefix+label, eliminate non-matching child branches |
| `spgist_name_leaf_consistent` | `:399` | Leaf comparator — reconstruct full Name from path + leaf, apply BT* strategy |
| `spgist_name_compress` | `:496` | name → text-datum conversion for storage |
| `formTextDatum` (static) | `:53` | Build a text Datum with short header when possible |
| `commonPrefix` (static) | `:79` | Length of common byte prefix between two strings |
| `searchChar` (static) | `:98` | Binary search of int16 label array |

## Internal landmarks

- The opclass uses the "different leaf type" feature of SP-GiST: input
  values are `name` (fixed 64 byte) but stored leaves are `text`, so the
  `compress` function converts name → text. Reconstruction at search time
  rebuilds `name` from text path + leaf (`:425-441`).
- Node labels are `int16` representing one byte of the key (range 0..255)
  plus the sentinels `-1` (end of key) and `-2` (used in the
  `allTheSame` split branch, `:249`).
- `spgChooseOut` is a tagged union — the three result types are
  `spgMatchNode` (descend), `spgSplitTuple` (split this inner tuple), and
  `spgAddNode` (insert a new child). Each gets a distinct branch of the
  function (`:206-258`).
- The picksplit function is intentionally reused from core
  `spgtextproc.c` — there's no `spgist_name_picksplit` here; the
  `.control` file maps `picksplit` to the core text version.

## Invariants & gotchas

- **Test module — never load in production** (though it's harmless beyond
  taking up oid space). Use core's `name_ops` instead.
- Comparison is **byte-wise**, not collation-aware (`memcmp` at `:356`,
  `:455`). For a real opclass on natural-language strings this would be a
  bug; for `name` (which is C-locale by definition) it's correct.
- `Assert(fullLen < NAMEDATALEN)` (`:428`) is the invariant that keeps the
  whole indexing scheme sound — every reconstructed value must fit in a
  `Name`. A bug in `choose` or `picksplit` that lets a longer-than-name
  string into the index would trip here.
- The `allTheSame` flag means a node where every child has the same label;
  it's a degenerate case the algorithm has to handle without infinite
  recursion (`:231-251`).
- Short-header text datums (`SET_VARSIZE_SHORT`) save 3 bytes per stored
  value when the value is small — important for index density.

## Cross-refs

- `source/src/backend/access/spgist/spgtextproc.c` — the collation-aware
  parent this code is based on.
- `source/src/backend/access/spgist/spgist.c` — SP-GiST AM implementation.
- `source/src/include/access/spgist.h` — `spgConfigIn`/`Out`,
  `spgChooseIn`/`Out`, `spgInnerConsistentIn`/`Out`, etc.
