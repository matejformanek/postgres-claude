# typecmds.c

- **Source path:** `source/src/backend/commands/typecmds.c`
- **Lines:** 4747
- **Last verified commit:** `031904048aa2`

## Purpose

"Routines for SQL commands that manipulate types (and domains)." [from-comment, typecmds.c:3-4] Owns CREATE/DROP/ALTER TYPE in all its variants: base types, composite types, domains, enums, ranges/multiranges, and the domain-constraint validation machinery. **Heavy dispatch file** — each variant has its own `DefineFoo`/`AlterFoo` chain.

## Top-level entries

- `DefineType` — CREATE TYPE for a base type (input/output/recv/send functions, alignment, storage, category, …). The grammar enforces ordering: "input/output/recv/send functions" must exist before the type itself (per the NOTES comment, typecmds.c:14-25).
- `DefineDomain` — CREATE DOMAIN; produces a type that wraps a base type with NOT NULL + CHECK constraints.
- `DefineEnum` — CREATE TYPE … AS ENUM (…); allocates "OID buckets" in pg_enum so later ADD VALUE can preserve sort order without rewriting.
- `DefineRange` — CREATE TYPE … AS RANGE (…); also creates the implicit multirange type.
- `DefineCompositeType` — CREATE TYPE … AS (col1 type1, …); implemented by making a `RELKIND_COMPOSITE_TYPE` pg_class entry — same row layout as a table but no storage.
- `AlterEnum` — ALTER TYPE … ADD VALUE; reuses OID buckets to keep sort order, splitting if needed.
- `AlterDomainAddConstraint`, `AlterDomainValidateConstraint`, `AlterDomainNotNull`, `AlterDomainDropConstraint`, `AlterDomainDefault` — domain mutations; constraint addition must scan every column of every table that uses this domain (across the whole catalog), via `get_typtype_dependents` walking pg_depend.
- `RemoveTypeById` — DROP TYPE; calls into dependency.c.
- `RenameType` — rename a type with cascade to composite/relation names.
- `AlterTypeRecurse` — propagate composite-type changes to all typed tables.

## Composite types are tables

A composite type's tuple descriptor lives in pg_class/pg_attribute exactly like a real table; the only difference is `relkind = RELKIND_COMPOSITE_TYPE`. That's why `ALTER TYPE ... ADD ATTRIBUTE` can take an `AccessExclusiveLock` on every table that uses the type — see `find_composite_type_dependencies` in tablecmds.c.

## Domain constraint enforcement

Domain constraints are enforced at **CAST time**, not at storage. Every place a value flows into a domain-typed column or expression, the executor inserts a CoerceToDomain node that runs the constraint exprs. `domainAddConstraint` (in this file) records the constraint in pg_constraint with `contypid = domain_oid` and `conrelid = 0`.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
