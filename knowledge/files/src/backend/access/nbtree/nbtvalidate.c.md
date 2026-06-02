# nbtvalidate.c

- **Source path:** `source/src/backend/access/nbtree/nbtvalidate.c` (375 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Opclass validator for btree (`amvalidate` implementation). Called from `commands/opclasscmds.c` when `CREATE OPERATOR CLASS … USING btree` or `pg_amop`/`pg_amproc` is touched. Also implements `btadjustmembers` (called when adding members to an existing opfamily) to fix up dependency types so members aren't dropped along with the originating opclass. [from-comment, nbtvalidate.c:1-13]

## Functions

- `btvalidate(opclassoid)` (40) — sweep all `pg_amop` entries for the family, check operators are present in exactly the expected strategies (1..5: `<`, `<=`, `=`, `>=`, `>`), check support function signatures (BTORDER_PROC mandatory, others optional), check the cross-type pairs are sensibly closed. Emits warnings via `ereport(INFO/WARNING)` and returns `false` on outright violations.
- `btadjustmembers(opfamilyoid, opclassoid, operators, functions)` — for each new member, recompute the right dependency type so opclass-internal members are auto-dropped with the opclass and family-external members aren't.

## Required support functions (from nbtree.h:717-723)

| Slot | Macro | Required? |
|---|---|---|
| 1 | `BTORDER_PROC` | yes — 3-way compare returning int4 |
| 2 | `BTSORTSUPPORT_PROC` | optional — accelerated sort |
| 3 | `BTINRANGE_PROC` | optional — for RANGE window frames |
| 4 | `BTEQUALIMAGE_PROC` | optional — enables deduplication for the index |
| 5 | `BTOPTIONS_PROC` | optional — per-attribute opclass options |
| 6 | `BTSKIPSUPPORT_PROC` | optional — efficient skip scan |

## Cross-references

- **Called by:** `catalog/opclasscmds.c` via the `IndexAmRoutine.amvalidate`/`amadjustmembers` slots.
- **Calls into:** `access/amvalidate.c` (`check_amproc_signature`, `check_amop_signature`, opfamily-completeness helpers).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/access-nbtree.md](../../../../../subsystems/access-nbtree.md)
