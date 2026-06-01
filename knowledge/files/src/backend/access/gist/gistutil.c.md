# gistutil.c

- **Source path:** `source/src/backend/access/gist/gistutil.c` (1061 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Grab-bag of utilities: page init (`GISTInitBuffer`), `gistfillbuffer`, NSN/follow-right macros, `gistMakeUnionItVec` / `gistMakeUnionKey`, `gistgetadjusted`, `gistKeyIsEQ`, `gistpenalty`, the new-buffer allocator with recycle check, opclass-state caching. [from-comment, gistutil.c:1-13]

## Key entry points

- `gistfillbuffer` — `PageAddItem` a batch of tuples; the workhorse used by build, redo, and split.
- `gistMakeUnionItVec` / `gistMakeUnionKey` — call opclass `union` to combine N key arrays.
- `gistgetadjusted` — given old downlink + new key, compute the adjusted downlink that covers both (used by the single-pass insert's on-the-way adjustment).
- `gistpenalty` — call opclass `penalty` proc.
- `gistNewBuffer` — get a buffer from FSM; checks `gistPageRecyclable(page)` which compares `deleteXid` against `GlobalVisCheckRemovableFullXid`. If FSM gave a non-recyclable page, the function loops or extends the relation.
- `gistPageRecyclable` — the recycle gate; mirrors nbtree's `BTPageIsRecyclable` semantics.
- `gistcheckpage` — sanity-check a page on read; panic on bogus opaque area.
- `GistPageGetNSN` / `GistPageSetNSN` — the NSN field accessors. NSN is stored in the GIST opaque area, distinct from `pd_lsn`.
- `GistMarkFollowRight` / `GistClearFollowRight` / `GistFollowRight` — flag accessors.

## Tags

[from-comment, gistutil.c:1-15]; behavior [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
