---
source_url: https://www.postgresql.org/docs/current/pgvisibility.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_visibility (visibility-map introspection + corruption check)

`pg_visibility` exposes the visibility map (VM) bits and cross-checks them
against the real heap — the tool for diagnosing the *most dangerous* class of
heap corruption: a VM bit that lies. A wrongly-set all-visible bit makes
index-only scans return rows they shouldn't; a wrongly-set all-frozen bit makes
VACUUM skip pages that still need freezing (wraparound risk). Default access is
**superuser + `pg_stat_scan_tables`**; the one destructive function is
superuser-only. `[from-docs]`

## The two bits, three sources

- **all_visible** (VM bit): every tuple on the page is visible to all current
  and future transactions. **all_frozen** (VM bit): every tuple is frozen.
  **pd_all_visible** (page-header `PD_ALL_VISIBLE` flag): the page's own copy of
  the all-visible claim. These three can legitimately *disagree* after a crash:
  the page-level bit can be set while the VM bit is clear post-recovery.
  `[from-docs]`

## Functions

- `pg_visibility_map(rel, blkno)` → `(all_visible, all_frozen)` — **VM only,
  fast** (reads the tiny VM fork). Set-returning `pg_visibility_map(rel)` adds
  `blkno`. `[from-docs]`
- `pg_visibility(rel, blkno)` → `(all_visible, all_frozen, pd_all_visible)` —
  also reports the page-header bit, so it must **read the heap data blocks**:
  "much more costly" than the VM-only form. Set-returning form adds `blkno`.
  `[from-docs]`
- `pg_visibility_map_summary(rel)` → `(all_visible bigint, all_frozen bigint)`
  aggregate page counts. `[from-docs]`
- `pg_check_frozen(rel)` → setof `tid`: TIDs of **non-frozen tuples on pages
  marked all-frozen** (a corruption indicator). `[from-docs]`
- `pg_check_visible(rel)` → setof `tid`: TIDs of **non-all-visible tuples on
  pages marked all-visible** (a corruption indicator). Both `pg_check_*` do a
  full heap scan — expensive. `[from-docs]`
- `pg_truncate_visibility_map(rel) returns void` — **superuser only**; forces
  the VM to be rebuilt on the next VACUUM. The repair lever when the VM is known
  to be wrong. `[from-docs]`

## Why the lies are dangerous

- The all-visible bit lets **index-only scans skip the heap visibility check** —
  if it's wrongly set, an IOS returns a row that isn't actually visible.
  `[from-docs]`
- The all-frozen bit lets **VACUUM skip the page entirely** — if wrongly set,
  tuples that still need freezing are never processed, a path to wraparound
  trouble. all-frozen formally means "no future vacuum needs to touch this page
  until a tuple is inserted/updated/deleted/locked". `[from-docs]`

## Locking / consistency

- The read functions take no blocking lock; reported values can disagree simply
  because the VM was examined at one instant and the data page at another — a
  benign race, not necessarily corruption. The `pg_check_*` functions are the
  authoritative corruption test. `[from-docs]`

## Links into corpus

- Visibility map fork internals: [docs-distilled/storage-vm.md](./storage-vm.md)
- HOT + heap tuple freezing context: [docs-distilled/storage-hot.md](./storage-hot.md)
- MVCC visibility rules these bits summarize: [docs-distilled/mvcc.md](./mvcc.md)
- Page-level confirmation of `PD_ALL_VISIBLE`: [docs-distilled/pageinspect.md](./pageinspect.md)
- Relevant skills: `debugging`, `access-method-apis`. Index-only-scan
  correctness depends entirely on the all-visible bit being honest.
