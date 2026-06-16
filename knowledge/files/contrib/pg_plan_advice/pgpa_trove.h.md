# `contrib/pg_plan_advice/pgpa_trove.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~84
- **Source:** `source/contrib/pg_plan_advice/pgpa_trove.h`

Trove-public types: `pgpa_trove_entry`, the SCAN/JOIN/REL lookup-type enum,
and `pgpa_trove_result` (entries pointer + indexes bitmapset). [verified-by-code]

## API / entry points

- `pgpa_trove_entry` struct (line 26): `tag`, `target`, `flags`. The `flags`
  field accumulates `PGPA_FB_*` bits during planning. [verified-by-code]
- `pgpa_trove_lookup_type` enum (line 51): three values — JOIN, REL, SCAN.
  Comment block explains why partitionwise advice is REL not JOIN: it's
  also relevant at the scan level (for partitionwise scans, not joins),
  and other join advice affects `join_path_setup_hook` whereas
  partitionwise affects `joinrel_setup_hook`. [from-comment]
- `pgpa_trove_result` struct (line 63): `entries` pointer + `indexes`
  Bitmapset. Indexes are offsets into entries. [verified-by-code]

## Notable invariants / details

- The three-slice taxonomy is locked: SCAN advice is per-baserel,
  JOIN advice is per-joinrel (and considers inner/outer split), REL advice
  applies at *either* level. PARTITIONWISE is the canonical REL case.
  [from-comment]
- `pgpa_trove_entry.flags` is shared mutable state: planner code OR's bits in
  via `pgpa_trove_set_flags` while iterating the same entries. Single-backend
  query-planning context makes this safe. [verified-by-code]

## Potential issues

- `pgpa_trove.h:26-31` — `flags` is `int`, not `unsigned` or a typedef like
  `pgpa_fb_flags_t`. Mixed int/bit-field usage is conventional in PG. [ISSUE-style:
  bitfield-as-int convention (nit)]
- `pgpa_trove.h:53-56` — enum values not given explicit numbers; reordering
  the declaration order in the source switches behaviors (currently used
  as indexed lookups in pgpa_trove.c slice selection). [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_plan_advice`](../../../issues/pg_plan_advice.md)
<!-- issues:auto:end -->
