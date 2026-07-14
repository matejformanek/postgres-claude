---
source_url: https://www.postgresql.org/docs/current/isn.html
fetched_at: 2026-07-14T20:56:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.21 isn — data types for international standard numbers (ISBN, EAN, UPC, etc.)"
maps_to_skill: [type-cache, catalog-conventions]
---

# Docs distilled — isn (ISBN/EAN13/… — eight types over one int64)

Eight product-number types (`EAN13`, `ISBN13`, `ISMN13`, `ISSN13`, `ISBN`,
`ISMN`, `ISSN`, `UPC`) that **all share one physical representation** and
differ only in display + validation. A clean worked example of **many
SQL-visible types multiplexed onto a single pass-by-value storage form**, plus
a GUC-controlled input-validation mode.

## Non-obvious claims

- **All eight types are physically one `uint64`.** `typedef uint64 ean13;`
  [[isn.h:24]] with the header comment "uint64 is the internal storage format
  for ISNs" [[isn.h:21]]; the docs confirm "internally, all these types use the
  same representation (a 64-bit integer), and all are interchangeable."
  [verified-by-code @ 1863452a4bfe] + [from-docs]
- **The `…13` types always display in EAN13 form; the short types (`ISBN`,
  `ISMN`, `ISSN`) display in the legacy 10-digit form when possible.** `UPC` is
  the EAN13 subset without the leading 0. The distinction is *presentation +
  validation only* — the stored bits are identical. [from-docs]
- **A one-bit "invalid check digit" flag rides in the value.** Numbers with a
  bad check digit are accepted only in **weak mode** and print with a trailing
  `!` (e.g. `0-11-000322-5!`). `is_valid(isn)` tests the flag; `make_valid(isn)`
  clears it. [from-docs]
- **Weak mode is a GUC, `isn.weak` (default false).** `SET isn.weak TO true`
  lets bad-check-digit values in for bulk loads; find them later with
  `WHERE NOT is_valid(id)`. Legacy `isn_weak(bool)` / `isn_weak()` shims
  set/read the same state. [from-docs]
- **`?` as the check digit is auto-computed on input** (`'220500896?'` →
  correct digit filled in). [from-docs]
- **Casts to/from `EAN13` are validated; sideways casts are relabelings.**
  Casting *from* `EAN13` into a narrower type does a run-time domain check and
  errors if out of range; the other casts "always succeed." [from-docs]
- **Indexing**: standard comparison operators with **B-tree and hash** support
  (no GiST/GIN — these are scalar identifier types, not set/range types).
  [from-docs]
- **Prefix/hyphenation tables are hard-coded in the source and can go stale.**
  Validity + hyphenation come from a compiled-in prefix list; updating it
  currently requires editing source and recompiling (the docs flag this as a
  known limitation). [from-docs]

## Links into corpus

- `catalog-conventions` skill — isn is the reference for registering **many
  `pg_type` entries + a mesh of `pg_cast` rows** over a single underlying
  representation; contrast the single-type contribs
  `[[docs-distilled/hstore.md]]` / `[[docs-distilled/cube.md]]`.
- `type-cache` — a pass-by-value fixed-width (`int8`-shaped) type family; the
  in-band validity flag is an interesting use of otherwise-spare bits.
- `[[docs-distilled/runtime-config-custom.md]]` — `isn.weak` is a
  contrib-defined custom GUC (`gucs-config` skill), toggling input strictness
  at session scope.
