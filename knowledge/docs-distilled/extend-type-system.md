---
source_url: https://www.postgresql.org/docs/current/extend-type-system.html
chapter: "38.2 The PostgreSQL Type System (extend-type-system)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# The PostgreSQL type system — extend-type-system

The taxonomy (base / container / domain / pseudo) and the **polymorphic type
resolution** rules that the parser's `parse_coerce.c` enforces. This is the
conceptual spine behind every `anyelement`/`anycompatible` function signature.

## Non-obvious claims

- **Four top-level categories:** base types (implemented in C below SQL,
  manipulated only via user functions — enums are a SQL-creatable
  subcategory), container types (arrays, composites, ranges/multiranges),
  domains (an underlying type + constraints, interchangeable with it almost
  everywhere), and pseudo-types. [from-docs extend-type-system]
- **Arrays are auto-created per type but cannot nest:** every base, composite,
  range, and domain type gets an array type automatically, but there are **no
  arrays of arrays**. Composite types appear whenever a table is created (and
  via `CREATE TYPE`). [from-docs]
- **Pseudo-types can't be table columns or container members** — they exist
  only to declare function argument/result types and thereby tag special
  function classes (`language_handler`, `fdw_handler`, `table_am_handler`,
  `index_am_handler`, `tsm_handler`, `trigger`, `event_trigger`, `internal`,
  `cstring`, `void`, `record`, ...). [from-docs]
- **Two independent polymorphic families.** "Simple": `anyelement`,
  `anyarray`, `anynonarray`, `anyenum`, `anyrange`, `anymultirange`. "Common":
  `anycompatible`, `anycompatiblearray`, `anycompatiblenonarray`,
  `anycompatiblerange`, `anycompatiblemultirange`. They are **separate type
  variable sets** — in `f(a anyelement, b anyelement, c anycompatible, d
  anycompatible)`, the first pair and the second pair resolve independently.
  [from-docs]
- **Simple family demands exact identity, no coercion.** All `anyelement`
  positions in one call must be the *same* actual type; PG will not reconcile
  `make_array(1, 2.5)`. `anyarray` positions must share one array type;
  `anyrange` one range type. [from-docs]
- **Common family promotes via UNION rules.** `anycompatible` positions may
  differ as long as all are implicitly castable to one common type (same rule
  as `UNION`/`CASE` result typing). There is **no `anycompatibleenum`** —
  implicit casts to enum types don't normally exist. [from-docs]
- **Cross-constraints between array/element/range:** if both `anyarray` and
  `anyelement` appear, the array's element type must equal the `anyelement`
  type; `anyrange`'s subtype must match the companion `anyelement`/array
  element. `anynonarray` = `anyelement` that must not be an array; `anyenum` =
  `anyelement` that must be an enum. [from-docs]
- **Result polymorphism needs argument polymorphism.** A polymorphic *result*
  type is legal only if at least one *argument* is polymorphic — the actual
  argument types determine the actual result type (`subscript(anyarray,
  integer) RETURNS anyelement`). The converse (fixed args, polymorphic result)
  is forbidden. [from-docs]
- **Variadic polymorphism:** `VARIADIC anyarray` / `VARIADIC
  anycompatiblearray` behaves as if N `anynonarray` / `anycompatiblenonarray`
  parameters were declared. [from-docs]

## Links into corpus

- Where the rules are enforced (polymorphic resolution, common-type
  selection): [[knowledge/files/src/backend/parser/parse_coerce.c.md]].
- The catalog machinery for registering a base type:
  [[knowledge/docs-distilled/xtypes.md]] +
  [[knowledge/files/src/backend/catalog/pg_type.c.md]].
- SQL-function signatures that consume these polymorphic types:
  [[knowledge/docs-distilled/xfunc-sql.md]].

## Caveats / verification

- All claims `[from-docs extend-type-system]`. The resolution algorithm lives
  in `source/src/backend/parser/parse_coerce.c`
  (`check_generic_type_consistency`, `enforce_generic_type_consistency`,
  `resolve_polymorphic_argtypes`) at anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
