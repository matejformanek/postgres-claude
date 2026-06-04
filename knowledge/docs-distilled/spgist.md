---
source_url: https://www.postgresql.org/docs/current/spgist.html
fetched_at: 2026-06-04T18:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 69: SP-GiST Indexes

SP-GiST = **space-partitioned GiST**. It maps in-memory partitioned search trees
(quad-trees, k-d trees, radix tries) onto disk pages with high fanout. Unlike
GiST it is **not balanced** and explicitly partitions the search space into
*non-equal* regions per node. Same division of labor as GiST: the core owns the
disk layout, concurrency, and WAL; the opclass supplies the partitioning logic.

## Inner tuples vs leaf tuples — the structural distinction

- **Inner tuples** are branch points holding **nodes** (groups of similar
  values). Each node has an optional **label** (NULL if the node set is fixed,
  e.g. a quad-tree's 4 quadrants) and an optional **prefix** common to all
  descendants (a shared string prefix in a radix tree, the centroid in a
  quad-tree). [from-docs]
- **Leaf tuples** store the indexed value (of `leafType`), possibly partial — a
  radix tree stores only the suffix; the opclass reconstructs the original value
  by accumulating prefixes/labels down the search path. [from-docs]
- **`allTheSame` inner tuples** are SP-GiST's recovery mechanism when `picksplit`
  fails to split values into ≥2 nodes: the core builds several identically
  labeled nodes and spreads values randomly. `choose` returning `spgMatchNode`
  then has its `nodeN` ignored (random descent for balance); `inner_consistent`
  must return all-or-none of the equivalent nodes; `spgAddNode` is illegal on
  such tuples. [from-docs]

## Support functions

**Five mandatory** (each is a C function over a paired in/out struct): [from-docs]

- `config` (`spgConfigIn` → `spgConfigOut`) — static metadata: `prefixType`,
  `labelType`, `leafType`, `canReturnData`, `longValuesOK`. **`leafType` must
  match the opclass `opckeytype`** (or be left for auto-derivation); **if
  `attType ≠ leafType`, a `compress` method becomes mandatory.**
- `choose` (`spgChooseIn` → `spgChooseOut`) — decide how to insert a value into
  an inner tuple: return `spgMatchNode` (descend), `spgAddNode` (add a child —
  **illegal on fixed/unlabeled or `allTheSame` tuples**), or `spgSplitTuple`
  (restructure the inner tuple).
- `picksplit` (`spgPickSplitIn` → `spgPickSplitOut`) — partition a set of leaf
  values into nodes; must produce ≥2 nodes or the core forces an `allTheSame`
  tuple. Allocates the `nodeLabels` / `mapTuplesToNodes` / `leafTupleDatums`
  output arrays.
- `inner_consistent` (`spgInnerConsistentIn` → `spgInnerConsistentOut`) — tree
  search: return the child `nodeNumbers` worth visiting (with `levelAdds`).
  Supports KNN via a per-node `distances` array (smaller first) and may pass
  opaque state down via `traversalValues`.
- `leaf_consistent` (`spgLeafConsistentIn` → `spgLeafConsistentOut`) — final
  predicate test on a leaf; returns bool, sets `recheck` (heap re-test) and
  `recheckDistances`, and on a match with `returnData` populates `leafValue` of
  `attType`.

**Optional:** `compress(Datum) → leafType` (applied only at insertion, **never
to query scankeys**) and `options(internal)` (opclass params via the standard
`PG_HAS_OPCLASS_OPTIONS()` / `PG_GET_OPCLASS_OPTIONS()`). [from-docs]

## Long values, nulls, KNN

- **`longValuesOK = true`** is required to index values bigger than a page;
  `picksplit`/`choose` iteratively strip prefixes until the leaf datum fits. The
  core enforces a **10-cycle limit on consecutive `choose` calls** to catch
  opclasses that fail to shrink the value (infinite-loop guard). [from-docs]
- **Null handling is automatic** — the core filters null entries and null search
  conditions before calling the opclass, so opclass code never sees nulls and may
  assume STRICT operators. [from-docs]
- **KNN/ordered search**: `inner_consistent`/`leaf_consistent` fill `distances[]`
  per `orderbys` scankey; nodes are visited in ascending distance;
  `recheckDistances` forces the executor to recompute from the heap tuple. Only
  `quad_point_ops`, `kd_point_ops`, and `poly_ops` ship `<->` KNN support.
  [from-docs]
- **`traversalValues`** are opaque pointers passed down the tree, allocated in
  `traversalMemoryContext` (not the per-tuple context) so they survive the reset
  between tuples. [from-docs]

## Built-in operator classes

| Opclass | Type | Shape |
|---|---|---|
| `quad_point_ops` (default) | point | quad-tree, KNN |
| `kd_point_ops` | point | k-d tree, KNN (different I/O profile) |
| `range_ops` | anyrange | range containment/overlap |
| `text_ops` | text | radix tree (trie), prefix search |
| `box_ops`, `poly_ops` | box/polygon | spatial partitioning, KNN |
| `inet_ops` | inet | IP-network hierarchy |

[from-docs]

## Memory + concurrency contract

Same as GiST: support methods run in a short-lived per-tuple context that is
reset after each tuple (minimal `pfree` burden; `config` should still avoid
leaks by assigning constants). The SP-GiST core owns WAL and concurrency.
[from-docs] [verified-by-code, via
knowledge/files/src/backend/access/spgist/spgxlog.c.md]

## Links into corpus

- [[knowledge/files/src/backend/access/spgist/spgist.c.md]] — AM entry points.
- [[knowledge/files/src/backend/access/spgist/spgdoinsert.c.md]] — the
  `choose`/`picksplit`/`spgSplitTuple` insertion machinery + 10-cycle guard.
- [[knowledge/files/src/backend/access/spgist/spgscan.c.md]] — `inner_consistent`
  / `leaf_consistent` driving the scan + KNN ordering.
- [[knowledge/files/src/backend/access/spgist/spgtextproc.c.md]] — the radix-tree
  `text_ops` worked example (prefix stripping, `longValuesOK`).
- [[knowledge/files/src/backend/access/spgist/spgquadtreeproc.c.md]],
  [[knowledge/files/src/backend/access/spgist/spgkdtreeproc.c.md]] — point opclasses.
- [[knowledge/files/src/backend/access/spgist/spgxlog.c.md]] — WAL/redo.
- [[knowledge/files/src/backend/access/spgist/README.md]] — canonical structure note.
- [[knowledge/docs-distilled/gist.md]] — the balanced sibling.
- Skill: `access-method-apis` — implementing an SP-GiST opclass in C.

## Confidence note

All claims `[from-docs]` (Chapter 69, fetched 2026-06-04); file cross-links
`[verified-by-code]` against the per-file corpus at the STATE.md anchor.
</content>
