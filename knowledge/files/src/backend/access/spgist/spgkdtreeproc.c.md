# spgkdtreeproc.c

- **Source path:** `source/src/backend/access/spgist/spgkdtreeproc.c` (351 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in **k-d tree** opclass over `point` for SP-GiST: `kd_point_ops`. [from-comment, spgkdtreeproc.c:1-13]

## Procs

- `spg_kd_config` — declares prefix type = float8 (one coordinate), node label = void (no labels). nNodes=2 per inner tuple.
- `spg_kd_choose` — descend by comparing the relevant coordinate (alternating X/Y by level).
- `spg_kd_picksplit` — median split on the relevant coordinate at this level → 2 children.
- `spg_kd_inner_consistent` — for scan: prune children whose half-plane misses the query rectangle/box.
- `spg_kd_leaf_consistent` — exact point-in-box / etc.

## Key idea

K-d trees alternate the dimension by tree level: even-level nodes split by X, odd-level by Y. The prefix stores the split coordinate; the level (parity) is implicit in the descent depth. [from-comment + verified-by-code]

Tags: [from-comment].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
