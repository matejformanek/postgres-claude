# ginscan.c

- **Source path:** `source/src/backend/access/gin/ginscan.c` (514 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Scan setup and rescan housekeeping. Maintains `GinScanOpaque` (search state) and breaks the query into per-key entries via the opclass `extractQuery` proc. [from-comment, ginscan.c:1-13]

## Key entry points

- `ginbeginscan` — alloc `GinScanOpaque`, init `tempCtx` (per-tuple work memory).
- `ginrescan` — re-apply scan keys: for each key, call opclass `extractQuery` (proc 2) to break into match-keys, then `ginNewScanKey`/`ginFillScanEntry` to allocate per-key state.
- `ginendscan` — free `tempCtx`, release any pinned buffers.
- `ginrestrpos` / `ginmarkpos` — stubs; GIN doesn't support mark/restore.

## State

`GinScanOpaque` carries:
- `keys[]` — one per scan-key; each has an array of `entries[]` derived from `extractQuery`.
- `pendingPosition` — cursor into the fastupdate pending list.
- `isVoidRes` — pre-computed "no rows can match" flag (e.g. all extractQuery returned empty).

Predicate-locking for SSI: scan keys' entry-locating reads call `CheckForSerializableConflictIn` against the leaf page or posting-tree root, per the README §"Predicate Locking" rules. [from-README, README:476-509]

Tags: [from-comment]; specifics [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/gin-scan-and-consistent.md](../../../../../idioms/gin-scan-and-consistent.md)

