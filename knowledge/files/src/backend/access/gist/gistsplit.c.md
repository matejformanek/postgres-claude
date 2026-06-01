# gistsplit.c

- **Source path:** `source/src/backend/access/gist/gistsplit.c` (779 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

**Multi-column page splitting** for GiST: opclass `picksplit` only knows about a single column, but GiST allows multi-column indexes. This file orchestrates picking per-column splits, identifying "don't-care" tuples (tuples that could go either way for column N), and re-splitting them on column N+1. [from-comment, gistsplit.c:1-15]

## `gistSplitByKey` (entry point)

Recursive algorithm:
1. Run `picksplit` on column 0 to get an initial left/right partition.
2. Identify "don't cares" — tuples whose `penalty` is the same on both sides.
3. If don't-cares exist and there are more columns, recurse on column 1 to re-partition them.
4. Repeat until columns exhausted or no don't-cares remain.

Result: a `GistSplitVector` (left/right item arrays + unioned keys for each).

## Variable-length-keys complication

PG GiST allows variable-length keys, so `picksplit`'s halves cannot be guaranteed to fit on a page. The caller (`gistplacetopage`) handles this by recursively splitting any half that overflows, possibly producing >2 result pages. [from-README, README:163-174, 236-256]

## Cross-references

Called from `gist.c::gistplacetopage`. Calls into opclass `picksplit`, `union`, `penalty`, `same` via fmgr.

Tags: [from-comment, gistsplit.c:1-15]; [from-README, README:236-256].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
