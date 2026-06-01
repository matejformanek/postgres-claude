# opclasscmds.c

- **Source path:** `source/src/backend/commands/opclasscmds.c`
- **Lines:** 1885
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines for opclass (and opfamily) manipulation commands." [from-comment, opclasscmds.c:3-5] CREATE OPERATOR CLASS, CREATE OPERATOR FAMILY, ALTER OPERATOR FAMILY ADD/DROP, DROP OPERATOR CLASS/FAMILY.

## Public surface

- `DefineOpClass`, `DefineOpFamily` — create rows in pg_opclass / pg_opfamily; for opclass, also populate the strategy- and support-function tables (pg_amop, pg_amproc).
- `AlterOpFamily` — ADD/DROP operators and support functions in an existing family. Used by extensions that ship new types but want them to play nicely with existing AMs (e.g. an extension defines a new geometric type and adds it to the GIST opfamily for `point`).
- `RemoveOpClassById`, `RemoveOpFamilyById` — cascaded drops.
- `IsThereOpClassInNamespace`, `IsThereOpFamilyInNamespace` — collision checks.
- `OpClassCacheLookup`, `OpFamilyCacheLookup` — internal cache lookups used during DDL.

## Strategy and support numbers

Each AM defines (in its `IndexAmRoutine`) a set of "strategy numbers" (e.g. btree: 1=`<`, 2=`≤`, 3=`=`, 4=`≥`, 5=`>`) and "support function numbers" (e.g. btree: 1=`comparator`, 2=`sortsupport`, 3=`in_range`, …). An opclass populates these for a specific data type. This file validates that the user-supplied operators have the right signatures and strategy numbers.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
