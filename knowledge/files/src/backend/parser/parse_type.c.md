# parse_type.c

- **Source:** `source/src/backend/parser/parse_type.c` (821 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Resolve `TypeName` parse nodes into `(Oid type, int32 typmod, Oid collation)`
triples. Used for column declarations, `CAST(x AS T)`, function argument /
return types, etc.

## Key entries

- `typenameTypeId` / `typenameTypeIdAndMod` / `typenameTypeMod` — resolve a
  `TypeName` to its components.
- `LookupTypeName` / `LookupTypeNameOid` — same but allow not-found
  reporting (returns InvalidOid instead of erroring).
- `typeStringToTypeName` — the inverse: parse a SQL type string (used by
  `regtype` IO).
- `typeOrDomainTypeRelid` — relation Oid behind a row type / domain over
  row type, used for `%ROWTYPE`.

## What `TypeName` carries

The raw node mixes:
- `names` — possibly schema-qualified type name list.
- `typmods` — the `(N,M)` modifier list for `numeric(10,2)` etc.
- `setof` — `SETOF` flag for return-types in function declarations.
- `arrayBounds` — non-empty for `int[]`, `int[3]`, etc.
- `pct_type` — true if the source was `tab.col%TYPE` (PL/pgSQL syntax).

The resolver expands `%TYPE` to the underlying column's type and pushes
`arrayBounds` into an array-type Oid lookup (`get_array_type`).

## Caveats

- Domain types are *not* unwrapped here; the returned Oid is the domain
  Oid. Unwrapping happens during coercion in `parse_coerce.c`.
- Typmod processing goes via the type's `typmodin` function (e.g.
  `numerictypmodin`) — that's where `numeric(10,2)` becomes a packed
  int32 typmod.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
