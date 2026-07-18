# parse_type.h

- **Source:** `source/src/include/parser/parse_type.h` (~60 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Prototypes for type-name resolution. Wrappers around syscache lookups in
`pg_type`.

## Key entries

- `LookupTypeName` / `LookupTypeNameOid` — TypeName → Oid (missing_ok
  variants).
- `typenameType` / `typenameTypeId` / `typenameTypeIdAndMod` /
  `typenameTypeMod` — resolved tuple / Oid / typmod.
- `typeStringToTypeName` — parse a SQL type string (used by `regtype`).
- `typeOrDomainTypeRelid` — composite/domain → underlying relation Oid.
- A handful of pgtype helpers: `format_type_be`, `format_type_with_typemod_qualified`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
