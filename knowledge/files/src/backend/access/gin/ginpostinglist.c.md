# ginpostinglist.c

- **Source path:** `source/src/backend/access/gin/ginpostinglist.c` (434 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Varbyte codec for posting lists. Encodes a sorted ItemPointer array into a compact byte stream; decodes back. Used both for inline leaf posting lists and posting-tree leaf segments. [from-comment, ginpostinglist.c:1-13]

## Encoding

- Each item pointer is packed into a 64-bit integer: low 11 bits = offset (since `MaxHeapTuplesPerPage < 2^11`), next 32 bits = block number; 43 bits used in total. [from-comment, lines 25-35]
- **First item** is stored uncompressed as an `ItemPointerData` (gives a random-skip seed when scanning into the middle of a page's segment list).
- Subsequent items are **deltas from the previous** item, varbyte-encoded. Each byte carries 7 data bits + 1 continuation bit; 43 bits fit in at most 7 bytes per delta.
- `GinPostingList` on-disk: `{ first: ItemPointerData, nbytes: uint16, bytes[FLEX] }`.

## Why deltas + varbyte

Small deltas (consecutive heap blocks) encode in 1-2 bytes; large jumps in 4-6 bytes. Average rate for real FTS workloads is ~1-2 bytes per item, often beating the 6 bytes of an uncompressed TID by 3-6x. [from-README, README:277-305]

## Key entry points

- `ginCompressPostingList(items, nitems, maxsize, &npacked)` — encode as many items as fit in maxsize bytes; sets `npacked` to how many made it.
- `ginPostingListDecode(plist, &ndecoded)` — decode the whole list.
- `ginPostingListDecodeAllSegmentsToTbm(plist, len, tbm)` — decode multiple consecutive segments straight into a TIDBitmap (used by `gingetbitmap` fast path).
- `ginMergeItemPointers(a, na, b, nb, &nout)` — sorted-merge two TID arrays (for ADDITEMS replay and bulk insert).

## Roundtrip assertions

Under `USE_ASSERT_CHECKING`, `CHECK_ENCODING_ROUNDTRIP` is defined and the compress→decode roundtrip is asserted to recover the original.

Tags: [from-comment, ginpostinglist.c:1-44]; structure [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/gin-tree-structure.md](../../../../../idioms/gin-tree-structure.md)

