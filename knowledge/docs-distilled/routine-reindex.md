---
source_url: https://www.postgresql.org/docs/current/routine-reindex.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Routine Reindexing

Short chapter; the non-obvious index-bloat + locking facts. Companion:
`knowledge/subsystems/access-nbtree.md` (if present), skill `access-method-apis`.

## Why indexes bloat even though VACUUM runs

- **Fully empty B-tree pages ARE reclaimed, but a page with even a few surviving
  keys stays allocated.** So a workload that eventually deletes *most but not
  all* keys in each key-range leaves sparsely-populated pages that never get
  merged — the canonical B-tree bloat pattern. REINDEX is the only fix.
  [from-docs]
- **Even without bloat, a freshly-built index is slightly faster**: logically
  adjacent pages tend to be *physically* adjacent right after a build, and drift
  apart under churn. This locality benefit is **B-tree-specific**. [from-docs]
- **Non-B-tree bloat is explicitly under-researched** — the docs tell you to
  *monitor physical index size manually* for GIN/GiST/SP-GiST/BRIN/hash rather
  than giving a schedule. [from-docs]

## Locking: REINDEX vs REINDEX CONCURRENTLY

- **`REINDEX` takes `ACCESS EXCLUSIVE`** on the index's table — blocks all reads
  and writes for the whole rebuild. **`REINDEX CONCURRENTLY` takes only `SHARE
  UPDATE EXCLUSIVE`**, allowing concurrent writes, at the cost of building a
  second copy (transient duplicate storage) and passing through invalid
  intermediate index states — slower and heavier, but online. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/routine-vacuuming.md]] — the maintenance sibling.
- [[knowledge/docs-distilled/btree.md]] — B-tree page structure / splits.
- [[knowledge/docs-distilled/index-locking.md]] — AM-level locking rules.
- Skill: `access-method-apis` — ambuild / amvacuumcleanup.

## Confidence note

All claims `[from-docs]` (Routine Reindexing chapter, fetched 2026-07-01). The
CONCURRENTLY invalid-index state machine lives in `index.c` /
`ReindexRelationConcurrently`; `[from-docs]`-only here.
