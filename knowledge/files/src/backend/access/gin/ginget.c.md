# ginget.c

- **Source path:** `source/src/backend/access/gin/ginget.c` (1982 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The scan iteration engine: drives entry-tree lookups, posting-list/tree traversal, fastupdate-pending-list scanning, and the AM-level callback `gingetbitmap` (which produces a `TIDBitmap`). GIN is bitmap-only; there is no `amgettuple`. [from-comment, ginget.c:1-13]

## GUC

- `gin_fuzzy_search_limit` — soft upper bound on returned set size; when set, the scan stochastically drops items past the limit. README §"Gin Fuzzy Limit" discusses rationale (very-frequent-lexeme queries). [from-README, README:57-82]

## Key entry points

- `gingetbitmap` — the AM slot. Iterates all scan keys' entry sets, performs the "advance to next candidate TID" loop, evaluates the ternary `consistent` (via `ginlogic.c`), and adds matches to a `TIDBitmap`. Also scans the fastupdate pending list and ORs those matches in.
- `scanGetItem` — the multi-way merge over per-key entry streams.
- `startScanEntry` — open one entry's data stream: either the inline posting list (decode) or pin/lock the posting-tree root and prepare a cursor.
- `entryGetItem` — advance one entry stream to the next TID.
- `collectMatchBitmap` — accumulate matching TIDs.
- `scanPendingList` — linear pass over fastupdate pages, gated by metapage share-lock.

## State

`pendingPosition` (line ~30) — cursor state for the pending-list scan. Tracks current buffer, offset range, and a `hasMatchKey[]` array per scan-key to detect when a heap tuple has matched every required key.

## Locking

- Entry-tree descent: pin+share lock per page during descent; release pin on parent at each step (search mode, per README §"Locating the leaf page").
- Posting-tree descent: same pattern, but the leaf may be held pinned across `gettuple`-style advances (to interlock against VACUUM TID recycling).
- Pending-list scan: holds metapage share lock for the duration of one scan pass.
- SSI: each entry leaf page or posting-tree-root scanned receives a `PredicateLockPage`; the metapage receives one as the fastupdate-interlock. [from-README, README:476-509]

Tags: [from-comment, ginget.c:1-13]; [from-README] for locking pattern.
