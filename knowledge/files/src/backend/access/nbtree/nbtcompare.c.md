# nbtcompare.c

- **Source path:** `source/src/backend/access/nbtree/nbtcompare.c` (666 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in BTORDER_PROC comparison functions for "trivial" datatypes that nbtree's default opclasses use directly: bool, char, int2/int4/int8 (incl. cross-type pairs), oid, oidvector. Each returns int32 < 0 / 0 / > 0, registered in `pg_amproc` as the BTORDER support function for the corresponding default opclass. Sortsupport (BTSORTSUPPORT_PROC) variants for the same types are also here. Non-trivial datatypes (text, numeric, timestamp, …) keep their btree compare functions next to the type's other code in `utils/adt/*.c`. [from-comment, nbtcompare.c:1-44]

## Rules from the top comment

- **Result must be a total order** on all non-NULL values of the data type. NaN-like values must be given a defined collation position, never "punt". [from-comment, nbtcompare.c:30-36]
- **Wider-than-int32 datatypes cannot return `a - b` directly** because of overflow. The integer comparators here all use explicit `if (a < b) return -1; …`. [from-comment, nbtcompare.c:24-29]
- This file contains only the trivial cases; non-trivial datatypes live with their utils/adt implementations to enable the boolean operators and the btree compare function to share three-way compare logic. [from-comment, nbtcompare.c:37-44]

## Cross-references

- Registered in catalog data: `src/include/catalog/pg_amproc.dat`.
- **Called from**: every `_bt_compare` invocation that lands on a column with a built-in integer/bool/char/oid opclass.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/access-nbtree.md](../../../../../subsystems/access-nbtree.md)
