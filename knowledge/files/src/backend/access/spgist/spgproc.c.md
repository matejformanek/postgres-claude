# spgproc.c

- **Source path:** `source/src/backend/access/spgist/spgproc.c` (88 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Common helper procedures shared across SP-GiST opclasses (point/quad/kd opclasses use them). [from-comment, spgproc.c:1-13]

## What's here

- `point_box_distance` (static) — distance from a point to an axis-aligned box (used by KNN proc in quad/kd opclasses).
- `point_point_distance` macro — wrapper around the built-in `point_distance`.

Tiny file; pulled out of the opclass files to dedup.

Tags: [from-comment].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
