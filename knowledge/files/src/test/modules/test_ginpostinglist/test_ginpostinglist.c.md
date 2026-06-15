---
path: src/test/modules/test_ginpostinglist/test_ginpostinglist.c
anchor_sha: e18b0cb7344
loc: 96
depth: read
---

# src/test/modules/test_ginpostinglist/test_ginpostinglist.c

## Purpose

Round-trip test for the **varbyte-encoded posting list** compression in
`src/backend/access/gin/ginpostinglist.c` — the on-disk representation of a
sequence of TIDs stored against a single GIN key. Encodes two TIDs, decodes
them back, and verifies the result matches the input exactly. The first TID is
always `(0, 1)` and only the second varies, because the first TID is stored
uncompressed; varbyte encoding only kicks in on the *delta* to subsequent TIDs
(`:31-33` from-comment).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_ginpostinglist()` | `:88` | SQL-callable entry; runs four hard-coded cases via `test_itemptr_pair` |

No `_PG_init`; no hooks; no static state.

## Internal landmarks

- `test_itemptr_pair(blk, off, maxsize)` (`:41`) — encode-decode core. Calls
  `ginCompressPostingList(orig, 2, maxsize, &nwritten)` then
  `ginPostingListDecode(pl, &ndecoded)`; emits NOTICEs with the result size and
  decoded count, and ERRORs on mismatch or `SizeOfGinPostingList(pl) > maxsize`
  (`:59-61`).
- Four canned cases in `test_ginpostinglist` (`:90-93`):
  1. `(0, 2)` at `maxsize=14` — minimum delta.
  2. `(0, MaxHeapTuplesPerPage)` at `maxsize=14` — max offset same block.
  3. `(MaxBlockNumber, MaxHeapTuplesPerPage)` at `maxsize=14` — overflow probe
     (delta cannot fit in 14 bytes; expects `ndecoded != nwritten`).
  4. Same TID at `maxsize=16` — verifies the larger budget accommodates the
     full delta.

## Invariants & gotchas

- **TEST MODULE — never load in production.** Pure correctness oracle.
- The encoded size must satisfy `SizeOfGinPostingList(pl) <= maxsize` — this is
  the contract `ginCompressPostingList` is documented to enforce, and case 3
  exists specifically to verify the overflow path returns a truncated list
  (`nwritten < 2`) rather than blowing past the budget.
- Single-TID encoding does NOT exercise varbyte at all (first TID is stored
  verbatim) — the comment at `:31-33` calls this out explicitly. Two-TID is the
  minimum that touches the delta encoder.
- `ginCompressPostingList` and `ginPostingListDecode` live in
  `access/gin_private.h` + `access/ginblock.h` — non-stable internals; the
  module is part of the regression check that bumps when those signatures move.
- Failure modes caught: encode-decode asymmetry, off-by-one on the size limit,
  silent truncation that drops a TID without signalling.

## Cross-refs

- `knowledge/files/src/backend/access/gin/ginpostinglist.c.md` — the
  implementation under test.
- `knowledge/files/src/include/access/ginblock.h.md` —
  `GinPostingList`, `SizeOfGinPostingList`.
- `knowledge/subsystems/access-gin.md` — broader GIN posting-list lifecycle
  (how varbyte fits into leaf-tuple compression).
