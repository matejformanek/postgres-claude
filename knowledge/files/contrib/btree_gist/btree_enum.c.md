# btree_enum.c

## One-line summary

GiST opclass for `enum` types. 8-byte key `[Oid|Oid]` — enum values are
identified by their `pg_enum.oid`. Comparators use `enum_cmp` (which
consults `pg_enum.enumsortorder`) via `CallerFInfoFunctionCall2` so the
flinfo cache stays warm.

## Public API

Standard 8 + sortsupport: `gbt_enum_{compress,fetch,union,picksplit,
consistent,penalty,same,sortsupport}`
`source/contrib/btree_gist/btree_enum.c:23-30`. No KNN.

## Key invariants

- Key: `[lower:Oid|upper:Oid]`, size 8 (`gbtreekey8`).
- **`gbt_enumeq` uses raw `Oid ==`** `source/contrib/btree_gist/btree_enum.c:48`
  — bypasses `enum_eq` because OID equality IS enum-value equality.
  All other comparators go through `enum_gt/ge/le/lt/cmp` which look up
  `enumsortorder`.
- `gbt_enum_sortsupport` allocates an `FmgrInfo` in `ssup_cxt` and stashes
  it in `ssup->ssup_extra` so `gbt_enum_ssup_cmp` can call `enum_cmp` via
  `CallerFInfoFunctionCall2` `:202-222`.

## Trust boundary / Phase D surface

- **pg_dump round-trip:** enum OIDs are *NOT* stable across dump/restore.
  When you dump and restore a database, the new enum values get fresh OIDs.
  The GiST index built on the old OIDs is unusable — but `REINDEX` rebuilds
  with the new OIDs and queries via `enum_cmp` (which uses `enumsortorder`,
  not raw OID) will find the right values.
  **The risk:** if anyone changes `enum_cmp` to compare OIDs directly (a
  perfectly reasonable optimisation), the index becomes silently wrong for
  any enum where the sortorder doesn't match OID order. The current
  implementation depends on `enum_cmp` being sortorder-based.
- **EXCLUDE on enum:** `gbt_enum_same` uses `gbt_num_same` → `gbt_enumeq` →
  raw OID equality. Sound because enum identity IS OID identity.
- **Cross-type comparison:** an enum opclass is parameterised by the enum
  type's OID. If a foreign enum type's OID happened to match, the
  comparator would crash inside `enum_cmp`'s catalog lookup. Not a
  user-reachable code path — opclass binding prevents cross-type use.

## Issues spotted

- [ISSUE-OID-STABILITY: After pg_dump round-trip, enum values get new OIDs.
  Pre-existing GiST indexes on enum columns must be REINDEXed — otherwise
  the stored OIDs are stale and queries find nothing. pg_dump emits
  `CREATE INDEX` in the schema dump, so the index is rebuilt; but a
  pg_upgrade with `--link` and no index rebuild could miss this. (MED —
  operational footgun, worth documenting)]
- [ISSUE-DESIGN-COUPLING: `gbt_enumeq` bypasses `enum_eq` for performance.
  If anyone ever introduces a notion of "enum aliases" (multiple OIDs for
  the same logical value), this opclass becomes wrong. Defensive only.
  (LOW)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-btree_gist.md](../../../subsystems/contrib-btree_gist.md)
