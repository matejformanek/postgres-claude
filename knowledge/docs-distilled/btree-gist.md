---
source_url: https://www.postgresql.org/docs/current/btree-gist.html
fetched_at: 2026-07-13T20:48:00Z
anchor_sha: d92e98340fcb
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.6 btree_gist — GiST operator classes for B-tree behavior"
maps_to_skill: access-method-apis
---

# Docs distilled — btree_gist (B-tree semantics inside a GiST index)

Ships GiST opclasses for the scalar types a B-tree already handles, so those
types can participate in the two things a plain B-tree *cannot* do: **exclusion
constraints** (`EXCLUDE USING gist`) and **KNN distance ordering**
(`ORDER BY col <-> const`). The reference implementation for "add a scalar type
to GiST" — squarely `access-method-apis`.

## Non-obvious claims

- **Broad type coverage.** Opclasses exist for `int2/int4/int8`,
  `float4/float8`, `numeric`, all the temporal types
  (`timestamp[tz]`, `time[tz]`, `date`, `interval`), `oid`, `money`,
  `char/varchar/text`, `bytea`, `bit/varbit`, `macaddr/macaddr8`,
  `inet/cidr`, `uuid`, `bool`, and **all enum types**. [from-docs]
- **The whole point is `<>` support for exclusion constraints.** A native
  B-tree opclass has no "not equals" strategy, so `EXCLUDE USING gist (cage
  WITH =, animal WITH <>)` is impossible with B-tree. btree_gist adds the
  `<>` operator so the "same cage ⇒ different animal" style constraint works.
  [from-docs] The cross-type strategy translation is realized by
  `gist_translate_cmptype_btree` [[btree_gist.c:18]] — the function that maps
  a compare-type to the AM's strategy number. [verified-by-code @ d92e98340fcb]
- **KNN `<->` only for types with a natural metric.** The distance operator is
  provided for the numeric + temporal + `oid`/`money` types (not for text,
  bytea, network, uuid, bool). `SELECT * FROM t ORDER BY a <-> 42 LIMIT 10`
  becomes an index-ordered scan. [from-docs]
- **It will not beat a real B-tree, and it cannot enforce uniqueness.** The
  docs are explicit: btree_gist "will normally not outperform" the equivalent
  B-tree and "lacks" a uniqueness capability. Use it for the three cases a
  B-tree can't cover: exclusion constraints, mixing a scalar column into a
  *multicolumn* GiST index alongside a genuinely GiST-only column (e.g. a
  geometry or range), and GiST testing. [from-docs]
- **Builds default to sorted mode via GiST sortsupport.** Each type ships a
  `sortsupport` support function (e.g. `gbt_int4_sortsupport`
  [[btree_int4.c:26]], which includes `utils/sortsupport.h` at :9), so
  `CREATE INDEX` uses the fast presorted GiST build; you can fall back to the
  older buffered build with the `buffering` index storage parameter.
  [from-docs] + [verified-by-code @ d92e98340fcb]
- **Trusted extension.** Installable by a non-superuser holding `CREATE` on the
  database. [from-docs]

## Links into corpus

- [[knowledge/subsystems/contrib-btree_gist.md]] — the source-side companion
  walking the per-type opclass C.
- [[knowledge/docs-distilled/gist.md]] — the GiST support-function contract
  (consistent/union/compress/penalty/picksplit/…) these opclasses satisfy.
- [[knowledge/docs-distilled/btree-gin.md]] — the sibling module doing the same
  trick for GIN (this run).
- [[knowledge/docs-distilled/xindex.md]] — opclass/strategy/support registration.

## Confidence

Type list, the `<>`/exclusion-constraint rationale, KNN type restriction, and
the "won't beat B-tree / no uniqueness" caveats are [from-docs].
`gist_translate_cmptype_btree` and the per-type `sortsupport` functions are
[verified-by-code @ d92e98340fcb] against `contrib/btree_gist/{btree_gist.c,
btree_int4.c}`.
