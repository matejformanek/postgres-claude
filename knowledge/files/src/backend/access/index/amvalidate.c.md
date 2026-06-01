# amvalidate.c

- **Source path:** `source/src/backend/access/index/amvalidate.c`
- **Lines:** 276
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `amvalidate.h`, each AM's `*_validate` (`btvalidate`, `hashvalidate`, `gistvalidate`, `gin_validate`, `spgvalidate`, `brinvalidate`), `catalog/pg_amop.h`, `catalog/pg_amproc.h`.

## Purpose

Catalog-traversal helpers shared by all index AMs' `amvalidate` and `amadjustmembers` implementations. The per-AM validator is responsible for the AM-specific opclass rules (e.g. "btree opfamily must have a strategy 1-5 for each datatype"); this file does the generic work — walking the family's `pg_amop` + `pg_amproc` rows, checking proc signatures, finding opclasses for a datatype, asking "is opfamily X usable for sorting type Y?". [from-comment, amvalidate.c:1-13]

## Top-of-file comment

> "Support routines for index access methods' amvalidate and amadjustmembers functions." [from-comment, amvalidate.c:1-7]

## Public surface

- `identify_opfamily_groups` (43) — Given ordered `pg_amop` and `pg_amproc` CatCLists, produce a List of `OpFamilyOpFuncGroup` structs, one per (lefttype, righttype) combination. Each group's `operatorset` and `functionset` are bitmaps of which strategy / proc numbers are present (up to 63). Used by validators to spot incomplete operator families. [verified-by-code, amvalidate.c:30-150]
- `check_amproc_signature` (152) — Verify that a support proc's return type and arg types match what the AM expects. `exact=true` requires an exact type match; `exact=false` allows binary-compatible-via-`IsBinaryCoercible`.
- `check_amoptsproc_signature` (192) — Specialised check for the AM-options proc (signature: `internal -> void`).
- `check_amop_signature` (206) — Verify an operator's lefttype/righttype/restype against expected.
- `opclass_for_family_datatype` (236) — Return the default opclass in `opfamilyoid` for `datatypeoid` (or InvalidOid if none / multiple).
- `opfamily_can_sort_type` (271) — Boolean: does this opfamily contain a btree opclass for this datatype? Used by the planner when picking a sort opclass.

## Key invariants

- The CatCLists passed to `identify_opfamily_groups` MUST be ordered by their secondary keys (datatypes); the function relies on contiguous grouping. Throws `ERROR` if `!ordered`. [verified-by-code, amvalidate.c:51-54]
- Strategy/proc numbers above 63 cannot be represented in the `operatorset` / `functionset` bitmaps. AMs that need more would have to widen this. [from-comment, amvalidate.c:33-36]
- `check_amproc_signature` with `exact=false` permits binary-coercible substitutions — this is how btree allows a `text` comparator to apply to `varchar`. [verified-by-code, amvalidate.c:152-191]
- `opclass_for_family_datatype` returns InvalidOid when ambiguous (more than one default opclass) — callers must handle this. [verified-by-code, amvalidate.c:236-270]

## Cross-references

- All six core index AMs call these from their `*validate` functions.
- Planner usage: `optimizer/util/pathnode.c`, `optimizer/path/equivclass.c` call `opfamily_can_sort_type` and `opclass_for_family_datatype`.

## Confidence tag tally
`[verified-by-code]=6 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`
