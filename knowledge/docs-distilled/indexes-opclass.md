---
source_url: https://www.postgresql.org/docs/current/indexes-opclass.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.10 Operator Classes and Operator Families"
maps_to_skills: [catalog-conventions, access-method-apis]
---

# 11.10 Operator Classes and Operator Families

Distilled from §11.10. The user-facing framing ("pick `text_pattern_ops` for
LIKE") sits on top of the `pg_opclass` / `pg_opfamily` / `pg_amop` /
`pg_amproc` catalog machinery that `xindex.md` and `catalog-conventions`
describe from the definition side; this page is the *why-two-opclasses* view.

## Non-obvious claims

- **An operator class names the operators an index uses for one column.** A
  B-tree index on `int4` uses `int4_ops`, which bundles the comparison
  functions for `int4`. The opclass is a per-(AM, type) object. [from-docs §11.10]
- **Multiple opclasses exist because some types have >1 meaningful index
  behavior.** Doc example: a complex-number type could be ordered by absolute
  value *or* by real part → two opclasses, selected at `CREATE INDEX` time.
  [from-docs §11.10]
- **`text_pattern_ops` / `varchar_pattern_ops` / `bpchar_pattern_ops` compare
  strictly byte-by-byte**, bypassing locale collation. This is what makes an
  index usable for `LIKE` / POSIX-regex anchored prefix matching **when the
  DB is not in the C locale** — the default `text_ops` index cannot serve
  `LIKE` in a non-C locale. [from-docs §11.10]
- **You may need BOTH indexes on one column:** one with
  `varchar_pattern_ops` (for `LIKE`) and one with the default opclass (for
  ordinary `<`/`>`/`ORDER BY`), because a single index carries one opclass.
  [from-docs §11.10]
- **An operator class is a subset of an operator FAMILY.** A family groups
  related opclasses across types so **cross-data-type operators** (e.g.
  compare `int4` to `int8`) can be index-usable. Cross-type operators are
  members of the *family*, not of any single class. [from-docs §11.10]
- **Introspection catalogs:** `pg_opclass` (classes, `opcdefault`,
  `opcintype`, `opcmethod`, `opcfamily`), `pg_opfamily` (families,
  `opfmethod`), `pg_amop` (operators in a family, `amopopr`/`amopfamily`),
  `pg_amproc` (support functions). psql shortcuts: `\dAc`, `\dAf`, `\dAo`.
  [from-docs §11.10]
- **The default opclass is chosen automatically** by the column's data type
  and is "usually sufficient"; a non-default opclass is an explicit opt-in at
  index-creation. [from-docs §11.10]

## Links into corpus

- Opclass/opfamily definition side (`CREATE OPERATOR CLASS`, support
  functions, strategy numbers): [[knowledge/docs-distilled/xindex.md]],
  [[knowledge/subsystems/access-nbtree.md]].
- Catalog `.dat`/`.h` conventions for pg_opclass/pg_amop/pg_amproc:
  [[knowledge/docs-distilled/system-catalog-declarations.md]],
  [[knowledge/docs-distilled/catalogs-overview.md]].
- Why `text_pattern_ops` matters — collation vs byte comparison:
  [[knowledge/docs-distilled/collation.md]],
  [[knowledge/docs-distilled/indexes-collations.md]].
- AM support-function protocol behind an opclass:
  [[knowledge/docs-distilled/index-functions.md]],
  [[knowledge/docs-distilled/index-api.md]].

## Citations

- All bullets: source-URL §11.10 (including the four introspection SQL
  queries and the `\dAc`/`\dAf`/`\dAo` shortcuts quoted there).
