# multibitmapset.c

- **Source:** `source/src/backend/nodes/multibitmapset.c` (162 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Two-dimensional bitset: a `List` of `Bitmapset *`, where the
zero-based list index is the outer "key" and the zero-based bit index
inside each bitmapset is the inner "key". Used when set members are
naturally `(int outer, int inner)` pairs — the canonical example is
`(varno, varattno)` over a query's range table. `:1-19`
`[from-comment]`

## Representation

- `NIL` = empty.
- A list entry of `NULL` = empty bitmapset at that outer index.
- Inner bitmapsets are independent in size; no expectation they all be
  the same length.
- Like `Bitmapset`, the representation is not unique — there are
  multiple valid encodings of the same set (e.g. trailing NULL entries
  are allowed but redundant). `:8-10` `[from-comment]`

## API

| Line | Function | Purpose |
|---|---|---|
| 43 | `mbms_add_member(a, listidx, bitidx)` | add one (outer, inner) pair; grows list with NULLs as needed; recycles `a`'s cells |
| 70 | `mbms_add_members(a, b)` | UNION; `a` modified in-place |
| 99 | `mbms_int_members(a, b)` | INTERSECT; truncates `a` to `length(b)` first |
| 125 | `mbms_is_member(listidx, bitidx, a)` | bool test |
| 145 | `mbms_overlap_sets(a, b)` | returns a `Bitmapset *` of list indexes where a[i] and b[i] overlap |

Negative `listidx` or `bitidx` is an `elog(ERROR)` — the type is for
small nonnegatives, mirroring Bitmapset. `:49-50, 131-132`
`[verified-by-code]`

## Implementation notes

- Add/union grow `a` via `lappend(a, NULL)` until `list_length(a) >
  listidx`. Use `lfirst_node(Bitmapset, lc) = bms_add_member(...)` to
  update in place.
- Intersect uses `list_truncate(a, list_length(b))` to drop tail
  bitmapsets that have no counterpart, then `forboth` walks the
  common prefix. `:106-116` `[verified-by-code]`
- `mbms_overlap_sets` uses `foreach_current_index(lca)` to recover the
  list position inside the loop. `:159` `[verified-by-code]`

## Status

The header file (`multibitmapset.h`) notes this is a young API — only
the few operations actually needed by callers have been built; more
will be added on demand. `:16-19` `[from-comment]`

## Cross-references

- Header: `source/src/include/nodes/multibitmapset.h`
- Built on: `bitmapset.c`, `list.c`.
- Callers: planner code dealing with `(varno, attno)` sets, e.g.
  `optimizer/util/var.c`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
