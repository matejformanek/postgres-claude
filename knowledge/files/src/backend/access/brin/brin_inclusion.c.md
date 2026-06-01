# brin_inclusion.c

- **Source path:** `source/src/backend/access/brin/brin_inclusion.c` (661 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Generic **inclusion** opclass framework for BRIN — useful for types that support R-Tree style operations (geometric types, range types, INET/CIDR). The summary is a bounding box / hull; consistency answers "does the page-range bounding-box overlap the scan key". [from-comment, brin_inclusion.c:1-23]

## Two PG-special handlings

1. **Empty elements** — for range types, an "empty" range cannot be summarized by a bounding box; the summary must track "has any empty value in this range" separately. [from-comment, brin_inclusion.c:11-13]
2. **Unmergeable elements** — INET IPv4 vs IPv6 cannot be unioned into a single bounding box. The summary tracks an `unmergeable` flag; once set, the range becomes effectively "match anything". [from-comment, brin_inclusion.c:13-17]

## Required + extra procs

| Procnum | Function/role |
|---|---|
| 1 opcInfo | one stored column: the union/bounding-box type (`oi_typcache[0]`) plus internal flags as additional storage cells (`hasnulls`+`empty`+`unmergeable` tracked outside the box) |
| 2 addValue | extend bounding box via type-specific union (procnum 13) |
| 3 consistent | dispatch on strategy (overlap, contains, contained-by, left/right/etc.); routes through the underlying R-Tree operator |
| 4 union | union of two bounding boxes; sets `unmergeable` if the type-specific merge fails |
| 11 mergeable | "are these two values mergeable" (true except cross-family INET) |
| 12 contains-strict | true if the bounding box strictly contains x |
| 13 union proc | type-specific union of two values into a bounding box |

## Notes

- The opclass needs only stub support functions for box/range/inet/cidr types — the actual operator implementations come from the type's own operator class (`geo_ops.c`, `rangetypes.c`, `network.c`).
- Strategy lookup goes through `pg_amop` to find the per-strategy proc.

Tags: [from-comment, brin_inclusion.c:1-23]; procnum semantics [inferred from BRIN README's required-procs table].

## Open questions

- The exact storage layout for "empty seen" / "unmergeable" flags inside the BrinTuple null bitmap was not traced. [unverified]
