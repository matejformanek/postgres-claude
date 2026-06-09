# `src/include/access/gin_tuple.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**47 lines.**

## Role

Defines the **transient `GinTuple` format** used during parallel GIN
index build — specifically the tuplesort stage where worker processes
serialize per-key TID lists for the leader to merge. Header comment:
"This is not the permanent in-index representation, but just a
convenient format to use during the tuplesort stage of building a new
GIN index."
[verified-by-code] `source/src/include/access/gin_tuple.h:1-21`

## Public API

`struct GinTuple` (lines 22-32):
- `tuplen` (int) — length of whole tuple, for the tuplesort framework.
- `attrnum` (OffsetNumber) — which index column.
- `keylen` (uint16) — bytes of key data.
- `typlen` (int16), `typbyval` (bool) — type metadata for the key,
  carried so the merge stage doesn't need a syscache lookup.
- `category` (signed char) — normal / NULL / placeholder.
- `nitems` (int) — number of TIDs in `data`.
- `data[FLEXIBLE_ARRAY_MEMBER]` — packed: `keydata` followed by a
  `GinPostingList` (SHORTALIGN'd).

One inline + one extern:
- `GinTupleGetFirst(tup)` — extract first ItemPointer from the embedded
  posting list (lines 34-42).
- `_gin_compare_tuples(a, b, ssup)` — sort comparator (line 44).

## Invariants

- **INV-gintuple-transient:** "not the permanent in-index representation"
  [verified-by-code] line 19. Don't confuse with `IndexTuple`-shaped
  on-disk leaf entries; that's `ginblock.h`.
- **INV-gintuple-alignment:** the embedded posting list starts at
  `SHORTALIGN(data + keylen)` [verified-by-code] line 39. Misalign
  and `GinPostingList->first` reads are UB.
- `nitems` corresponds to entries in the embedded posting list, NOT
  to a raw ItemPointer array — the posting list is compressed
  variable-length deltas.
- Carrying `typlen`/`typbyval` in-tuple means the tuplesort doesn't
  cross-reference the relation cache — important because parallel
  workers may have different reloid binding states during build.

## Notable internals

The "posting-tree vs posting-list pivot" referenced in the brief:
- **Posting list** = a small inline list of TIDs (compressed deltas),
  stored alongside the key in a GIN leaf entry. Compact for sparse
  keys.
- **Posting tree** = when a key has too many TIDs to fit inline, GIN
  spawns a separate B-tree (rooted in `ginblock.h`'s `GinPostingItem`)
  to hold them. Pivot happens at `GinItemPointerSetMax`-ish thresholds
  during insert.

The transient `GinTuple` here is always in posting-LIST form; the
posting-tree spillover happens at final-merge time in the leader.

## Trust-boundary / Phase D surface

Not directly a Phase-D surface — this is build-time-only state. But:
the `tuplen` field is consumed by the tuplesort framework with no
internal bounds check; a corrupted-on-disk spill file (from a crash
mid-build, then a restart that picks up the tmp file?) could in
principle cause an over-read. In practice spill files are removed on
crash and rebuild restarts from scratch, so the surface is small.

## Cross-refs

- `access/ginblock.h` — permanent on-disk GIN page formats, including
  `GinPostingList` and posting-tree pages.
- `access/gin.h` — public GIN API.
- `access/gin_private.h` — internal GIN structures (build state).
- `utils/sortsupport.h` — `SortSupport` consumed by `_gin_compare_tuples`.
- `src/backend/access/gin/gintuplesort.c` — actual consumer.

## Issues

- **ISSUE-doc**: header doesn't cross-reference the posting-list /
  posting-tree pivot, leaving a new contributor unsure which on-disk
  shape this maps into.
