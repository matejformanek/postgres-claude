# 2026-06-01 — wave 2 consolidation

## What I did

- Read prior `progress/STATE.md`, `progress/coverage.md`, `progress/files-examined.md`,
  and the `memory-keeping` skill.
- Rewrote `progress/STATE.md` to reflect the post-wave-2 reality: new phase label
  ("deep file-by-file corpus building"), per-wave-2-agent Done bullets, full
  wave-3 In-progress list, refreshed Next steps.
- Extended `progress/coverage.md` with a new "Per-file coverage" section that
  points at `progress/files-examined.md` and records current counts.
- Counted artifacts: 273 registry rows in `files-examined.md`, 414 docs under
  `knowledge/files/`.

## What I learned

- `knowledge/files/` already has more docs (414) than registry rows (273). Either
  some agents skipped the registry append step, or the docs include header-only
  and dir-overview files that no one registered. Worth a reconciliation pass.
- Top-covered dirs so far: `access/nbtree` (13), `utils/cache` (12),
  `utils/mmgr` (11), `storage/lmgr` (10).
- `rtk grep` rewrites `grep` output for token compaction and mangles raw lines —
  had to use `rtk proxy grep` to get faithful counts.

## What I'm unsure about

- Whether the 414-vs-273 gap is "missing registry rows" or "docs that legitimately
  don't map 1:1 to a single examined file". A follow-up agent should diff
  `knowledge/files/` paths against the registry.
- Whether any wave-2 agents produced subsystem-level docs beyond `storage-buffer`
  that should get rows in `coverage.md`'s subsystems table.

## Pointers left for next time

1. Reconcile `knowledge/files/` ↔ `progress/files-examined.md` and backfill any
   missing rows.
2. After wave 3 lands `smgr` + `md` + `fd`, write
   `knowledge/architecture/storage-layer.md`.
3. Cross-reference pass linking `knowledge/files/` back from
   `knowledge/architecture/` and `knowledge/idioms/`.
