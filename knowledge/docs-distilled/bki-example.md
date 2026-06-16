---
source_url: https://www.postgresql.org/docs/current/bki-example.html
chapter: "68.4 Example"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# BKI example — §68.4

A minimal worked BKI sequence; the page is mostly a code listing with little
prose. Completes the BKI trio with §68.2
([[knowledge/docs-distilled/bki-structure.md]]) and §68.3
([[knowledge/docs-distilled/bki-commands.md]]).

## The example (paraphrased)

```
create test_table 420 (oid = oid, cola = int4, colb = text)
open test_table
insert ( 421 1 'value 1' )
insert ( 422 2 _null_ )
close test_table
```

## Non-obvious claims

- The example confirms the §68.3 shapes in miniature: `create <name> <oid>
  (col = type, ...)` with an **explicit table OID (420)**, then the
  open → insert(s) → close cycle. [from-docs §68.4]
- **Inserts are positional with explicit per-row OIDs** (`421`, `422` are the
  row OIDs preceding the column values), and `_null_` supplies a NULL —
  exactly the `insert ([oid_value] value1 ...)` form from §68.3.
  [from-docs §68.4]
- The example is *deliberately minimal*: it shows **no `declare index` /
  `build indices`** and none of the `bootstrap` / `shared_relation`
  modifiers — for those, §68.3 is the reference, and the real generated
  `postgres.bki` is the exhaustive example. [from-docs §68.4]
- Take-away for corpus use: when reasoning about a catalog-bootstrap change,
  the *authoritative* example is the build-generated
  `src/backend/catalog/postgres.bki`, not this toy — this page is a syntax
  primer, the generated file is ground truth. [inferred]

## Links into corpus

- Command reference: [[knowledge/docs-distilled/bki-commands.md]] (§68.3).
- File structure: [[knowledge/docs-distilled/bki-structure.md]] (§68.2).
- Generation + the real `.dat` sources:
  [[knowledge/docs-distilled/bki.md]] +
  [[knowledge/docs-distilled/system-catalog-initial-data.md]].
- Executing backend:
  [[knowledge/files/src/backend/bootstrap/bootstrap.c.md]].

## Caveats / verification

- All claims `[from-docs §68.4]`. The actual generated artifact to inspect is
  `dev/build-debug/src/backend/catalog/postgres.bki` after a build (or
  `source/src/backend/catalog/` `.dat` inputs) at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
