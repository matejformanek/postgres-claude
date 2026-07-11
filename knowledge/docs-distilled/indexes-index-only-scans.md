---
source_url: https://www.postgresql.org/docs/current/indexes-index-only-scans.html
fetched_at: 2026-07-10
anchor_sha: c1702cb51363
chapter: "11.9 Index-Only Scans and Covering Indexes"
maps_to_skills: [buffer-manager, executor-and-planner, access-method-apis]
---

# 11.9 Index-Only Scans and Covering Indexes

Distilled from §11.9. The load-bearing fact is that an index-only scan (IOS)
is gated at runtime on the **visibility map** bit, not merely on "are all
columns in the index" — this is where the subsystem coupling
(executor ↔ heap VM ↔ VACUUM) lives.

## Non-obvious claims

- **Two hard requirements:** (1) the AM must support IOS, (2) the query must
  reference *only* columns stored in the index. [from-docs §11.9]
- **AM support is uneven:** B-tree always supports IOS; GiST and SP-GiST
  support it for *some operator classes but not others*; GIN *cannot* —
  "each index entry typically holds only part of the original data value."
  [from-docs §11.9]
- **The MVCC problem:** visibility (xmin/xmax) lives only in heap tuples, not
  in index entries, "so at first glance every row retrieval would require a
  heap access anyway." IOS would be impossible without a side channel.
  [from-docs §11.9]
- **The visibility map is that side channel.** After finding a candidate
  index entry, IOS checks the VM bit for the corresponding heap page. Bit
  set → row is known all-visible, return straight from the index. Bit clear
  → the heap tuple *must* be visited to test visibility, giving **no win
  over a plain index scan**. [from-docs §11.9] — code: the VM check is
  `VM_ALL_VISIBLE(scandesc->heapRelation, …)` in the IOS executor node.
  [verified-by-code `source/src/backend/executor/nodeIndexonlyscan.c:164` @c1702cb51363]
- **Why it still pays:** the VM is ~4 orders of magnitude smaller than the
  heap, so even when only *some* pages are all-visible the physical I/O
  saved is large. But: "it will be a win only if a significant fraction of
  the table's heap pages have their all-visible map bits set." [from-docs §11.9]
- **Heavily-updated tables defeat IOS.** Frequent writes keep VM bits
  cleared, so IOS degrades to ordinary index scans. VACUUM is what sets the
  bits back. [inferred from §11.9 + VM semantics]
- **`INCLUDE` payload columns** are stored but never interpreted by the index
  machinery: they need not be of an indexable type, and on a unique index
  the uniqueness constraint applies to the *key* columns only, not the
  payload. [from-docs §11.9]
- **Payload width is a footgun:** if an index tuple (key + INCLUDE) exceeds
  the index type's max tuple size, the *insertion fails* — be conservative
  with wide INCLUDE columns. [from-docs §11.9]
- **B-tree suffix truncation** always drops non-key (INCLUDE) columns from
  upper tree levels, and can also drop trailing *key* columns when the
  remaining prefix already uniquely describes leaf tuples — so `INCLUDE`
  reliably keeps internal pages small vs the legacy "just add the column to
  the key" pattern. [from-docs §11.9]
- **Expression-index blind spot:** the planner only considers IOS when every
  *column* the query needs is in the index. For `SELECT f(x) … WHERE f(x) <
  1` with `INDEX (f(x)) INCLUDE (x)`, it fails to notice `x` is only needed
  inside `f(x)`, and won't pick IOS. Workaround (add the base column) is
  itself imperfect. [from-docs §11.9]
- **Partial-index predicates need not be rechecked:** a partial unique index
  `… WHERE success` lets `SELECT target … WHERE subject=… AND success` run
  index-only even though `success` isn't a result column — every index entry
  necessarily has `success=true`, so no runtime recheck (PG 9.6+). [from-docs §11.9]

## Links into corpus

- Visibility map mechanics + who sets the bits:
  [[knowledge/docs-distilled/storage-vm.md]],
  [[knowledge/files/src/backend/access/heap/visibilitymap.c.md]].
- HOT updates keep tuples off the index but interact with all-visible:
  [[knowledge/docs-distilled/storage-hot.md]].
- The executor node that does the VM check:
  [[knowledge/subsystems/executor.md]].
- B-tree suffix truncation / dedup home:
  [[knowledge/subsystems/access-nbtree.md]],
  [[knowledge/files/src/backend/access/nbtree/nbtdedup.c.md]].
- AM capability flags (`amcanreturn`) that gate IOS support:
  [[knowledge/docs-distilled/index-api.md]],
  [[knowledge/docs-distilled/indexam.md]].
- VACUUM as the VM-bit setter: [[knowledge/docs-distilled/routine-vacuuming.md]].

## Citations

- Behavioral claims: source-URL §11.9.
- Runtime VM check: `source/src/backend/executor/nodeIndexonlyscan.c:164`
  (`VM_ALL_VISIBLE(scandesc->heapRelation, …)`), [verified-by-code @c1702cb51363].
