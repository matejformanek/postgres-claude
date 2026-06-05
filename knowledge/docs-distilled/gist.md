---
source_url: https://www.postgresql.org/docs/current/gist.html
fetched_at: 2026-06-04T18:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 68: GiST Indexes

The GiST (Generalized Search Tree) chapter — the opclass-author view. GiST is a
*template* for tree-structured AMs (R-tree, B-tree-like, RD-tree, …); the core
owns concurrency, WAL, and tree shape, and the opclass supplies only the
domain semantics through a fixed set of support functions.

## What GiST is

- **GiST is a base template, not a fixed index.** The implementer of an operator
  class defines the query semantics (which operators the index answers and how);
  the framework supplies the tree, concurrency control, and WAL. This is the key
  contrast with extensible B-tree/hash, which support *any data type* but only a
  fixed predicate set (`<,=,>` / `=`). [from-docs]
- **Internal-node storage type may differ from the indexed type.** Leaf entries
  are the indexed type; internal (and optionally leaf) entries can be any C
  struct following varlena rules. The `STORAGE` clause of `CREATE OPERATOR CLASS`
  declares the internal type; `compress`/`decompress` convert between them.
  [from-docs]

## Support functions — required vs optional

**Five mandatory:** [from-docs]

- `consistent(internal, data_type, smallint, oid, internal) → bool` — does this
  entry match the query? Sets a `bool *recheck` out-param: `false` = exact (index
  answer definitive), `true` = candidate (re-test against the heap tuple). This
  one out-param is what lets GiST be **lossy or lossless**.
- `union(internal, internal) → storage_type` — consolidate a set of entries into
  one covering entry. **Must return freshly `palloc`'d memory** of the storage
  type — cannot return an input as-is even when the type is unchanged.
- `same(storage_type, storage_type, internal) → internal` — equality of two
  storage-type keys.
- `penalty(internal, internal, internal) → internal` — cost of inserting under a
  given subtree; drives branch choice at insert. **Crucial to index quality.**
  Negative penalties are treated as zero.
- `picksplit(internal, internal) → internal` — partition entries between the old
  page and a new page on split. Together with `penalty`, governs tree balance.

**Optional (each unlocks a capability):** [from-docs]

- `compress` / `decompress` — leaf transform to/from storage type. **If
  `compress` is lossy for leaf entries, the opclass cannot support index-only
  scans and must not define `fetch`.** Omitting `compress` means no compression.
- `fetch(internal) → internal` — reconstruct the exact original value; **required
  for index-only scans** (and only valid when `compress` is non-lossy).
- `distance(internal, data_type, smallint, oid, internal) → float8` —
  **required if the opclass contains ordering (KNN) operators.** For internal
  nodes it must return a *lower bound* (smallest distance any child could have);
  the returned distance **must never exceed** the true distance; if approximate,
  set `*recheck` and the executor reorders after a heap fetch.
- `sortsupport` — a comparator enabling the sorted build method; **if present it
  becomes the default build path** (faster than buffering).
- `options(internal)` — opclass parameters into a `local_relopts`; read in other
  methods via `PG_HAS_OPCLASS_OPTIONS()` / `PG_GET_OPCLASS_OPTIONS()`.
- `translate_cmptype(integer) → smallint` — maps a `CompareType`
  (`src/include/access/cmptype.h`) to a strategy number so the opclass can back
  the non-`WITHOUT OVERLAPS` part of temporal `PRIMARY KEY`/`UNIQUE`. Two
  ready-made translators: `gist_translate_cmptype_common` (RT* strategies) and
  `gist_translate_cmptype_btree` (BT*, in `btree_gist`). [from-docs]

## Build methods

- **Three strategies:** sorted (default *if* `sortsupport` exists — fastest),
  buffered, and simple one-tuple-at-a-time. [from-docs]
- **Without `sortsupport`, build switches to the buffering method once the index
  reaches `effective_cache_size`** — buffering defers insertions to cut random
  I/O for unordered data, at the cost of more `penalty` calls and temp disk.
  Force/forbid via the `buffering` `CREATE INDEX` parameter. [from-docs]
  [verified-by-code, via knowledge/files/src/backend/access/gist/gistbuildbuffers.c.md]

## Memory + concurrency contract

- **Support methods run in a short-lived context** that `CurrentMemoryContext`
  resets after each tuple — don't bother `pfree`'ing locals. For cross-tuple
  caching, allocate in `fcinfo->flinfo->fn_mcxt` and stash the pointer in
  `fn_extra` (free the old one first). [from-docs]
- **The GiST core owns concurrency and WAL**; the opclass never touches locking
  or recovery. [from-docs]
  [verified-by-code, via knowledge/files/src/backend/access/gist/gistxlog.c.md]

## Built-in operator classes

Geometric (`box_ops`, `circle_ops`, `point_ops`, `poly_ops`), network
(`inet_ops` — not default, must be named in `CREATE INDEX`), range
(`range_ops`, `multirange_ops`), full-text (`tsvector_ops`, `tsquery_ops`).
Domain-specific opclasses ship in contrib (`btree_gist`, `cube`, `hstore`,
`intarray`, `ltree`, `pg_trgm`, `seg`). [from-docs]

## Links into corpus

- [[knowledge/files/src/backend/access/gist/gist.c.md]] — the AM entry points.
- [[knowledge/files/src/backend/access/gist/gistproc.c.md]] — R-tree geometric
  support functions (the worked example the chapter points to).
- [[knowledge/files/src/backend/access/gist/gistget.c.md]] — scan-side
  `consistent`/`distance` evaluation + recheck + KNN reordering.
- [[knowledge/files/src/backend/access/gist/gistbuildbuffers.c.md]] — the
  buffering build method described under "GiST build".
- [[knowledge/files/src/backend/access/gist/gistxlog.c.md]] — WAL/redo the core
  supplies so opclasses don't.
- [[knowledge/files/src/backend/access/gist/README.md]] — canonical tree/NSN
  description.
- [[knowledge/docs-distilled/spgist.md]] — the space-partitioned sibling.
- [[knowledge/docs-distilled/indexes-types.md]] — where GiST sits among the AMs.
- [[knowledge/wiki-distilled/Index-only_scans.md]] — why a lossy `compress`
  forecloses index-only scans for GiST.
- Skill: `access-method-apis` — implementing a GiST opclass/AM in C.

## Confidence note

All API/semantics claims are `[from-docs]` (Chapter 68, fetched 2026-06-04);
file cross-links are `[verified-by-code]` against the per-file corpus at the
STATE.md anchor. Not re-verified line-by-line this run — the per-file gist docs
carry the source cites.
</content>
