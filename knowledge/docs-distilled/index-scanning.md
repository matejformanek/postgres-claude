---
source_url: https://www.postgresql.org/docs/current/index-scanning.html
fetched_at: 2026-06-12T20:50:00Z
anchor_sha: e18b0cb
chapter: "63.3 Index Scanning"
---

# Index Scanning (docs §63.3)

The semantics an AM must honor when returning TIDs: scan keys, recheck,
ordering, marking, and the `amgettuple`-vs-`amgetbitmap` split. `[from-docs]`.

## Non-obvious claims

- **The AM's job is to regurgitate the TIDs of all tuples matching the scan
  keys — nothing more.** It does *not* fetch heap tuples, and does *not* apply
  visibility. `[from-docs]`
- **Scan keys are `index_key operator constant`, implicitly ANDed, zero or
  more.** Returned tuples must satisfy *all* of them. `[from-docs]`
- **Lossy/recheck contract:** the AM may declare it returns a *superset* (all
  matches plus possible extras); core then re-applies the index conditions to
  the heap tuple. If recheck is *not* signalled, the AM must return **exactly**
  the matching set — no more, no less. `[from-docs]`
- **Core hands over WHERE clauses without semantic analysis** — it doesn't prune
  redundant or contradictory quals. The AM must do that itself: e.g. for
  `x > 4 AND x > 14`, btree's `amrescan` must recognize `x > 4` as redundant.
  `[from-docs]`
- **Two distinct ways to produce ordered output:** `amcanorder=true` for AMs that
  always return data in natural order (btree) — these *must* use btree-compatible
  strategy numbers for their equality/ordering operators; `amcanorderbyop=true`
  for AMs that satisfy `ORDER BY index_key operator constant` (KNN), with those
  modifiers passed to `amrescan`. `[from-docs]`
- **Direction rules for `amgettuple`:** `ForwardScanDirection` is normal; a
  *first* call after `amrescan` with `BackwardScanDirection` means scan
  back-to-front and return the *last* match first — only for `amcanorder` AMs.
  After the first call it must advance either direction from the last entry,
  **unless `amcanbackward` is false**, in which case every call keeps the first
  call's direction. `[from-docs]`
- **Marking:** ordered-scan AMs must support marking one position and restoring
  it (possibly repeatedly); a new `ammarkpos` overrides the old mark. Non-ordered
  AMs set the `ammarkpos`/`amrestrpos` slots to NULL. `[from-docs]`
- **Concurrency invariant — the load-bearing rule:** a concurrently *inserted*
  entry may or may not be seen; a concurrent *delete* may or may not be
  reflected — but insertions/deletions **must never cause the scan to miss, or
  doubly return, entries that were not themselves being inserted/deleted.** This
  must hold for both the scan position and any mark position. `[from-docs]`
- **Index-only scans are no concern of the AM beyond returning the data:** even
  when the index can return the value, the heap tuple is still visited unless the
  visibility map shows the TID's page all-visible. The AM just supplies the
  value; the VM check is core's. `[from-docs]`
- **`amgetbitmap` is the bulk alternative** — fetch everything at once, avoiding
  per-tuple lock/unlock cycles. Its five restrictions: (1) no mark/restore; (2)
  unordered bitmap, so **no direction arg**; (3) ordering operators never
  supplied; (4) **no index-only-scan path** (can't return tuple contents); (5)
  **no locking of returned tuples** — which is exactly why §63.4 limits bitmap
  scans to MVCC snapshots. `[from-docs]`
- **An AM may implement only one of `amgettuple` / `amgetbitmap`** if its
  internals suit one API and not the other. `[from-docs]`

## Links into corpus

- [[knowledge/docs-distilled/index-locking.md]] — the §63.4 locking rules this
  page repeatedly defers to (pins, bitmap = MVCC-only).
- [[knowledge/docs-distilled/index-functions.md]] — the callback signatures
  (`amgettuple`/`amgetbitmap`/`amrescan`/mark-restore).
- [[knowledge/subsystems/access-nbtree.md]] — btree's redundant-key elimination
  (`amrescan`) and natural-order scanning.
- [[knowledge/files/src/backend/access/nbtree/nbtsearch.c.md]],
  [[knowledge/files/src/backend/access/nbtree/nbtreadpage.c.md]] — the read path.
- Skill: `access-method-apis`, `executor-and-planner` (IOS, bitmap scans).

## Citations

- All `[from-docs]`. `IndexScanDesc` is in
  `source/src/include/access/relscan.h`; the btree scan path is
  `source/src/backend/access/nbtree/nbtsearch.c`. Verify at anchor e18b0cb.
