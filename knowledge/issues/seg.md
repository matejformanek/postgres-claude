# Issues — `contrib/seg`

Floating-point segment (interval) datatype + GiST opclass. 2 source files / ~1136 LOC.

**Parent docs:** `knowledge/files/contrib/seg/seg.c.md`, `knowledge/files/contrib/seg/segdata.h.md`.

**Source:** 4 entries surfaced 2026-06-09 by A14-3.

## Headlines

1. **NaN endpoints make `seg_cmp` let duplicate NaN segs satisfy `EXCLUDE USING gist (val WITH =)`** — same family as A13 btree_gist float NaN divergence.
2. **NaN in `gseg_picksplit` center → unstable qsort comparator → degenerate GiST tree** — silent index pathology.
3. **`HUGE_VAL` "regular" boundary collides with `-` sentinel** — input edge case.
4. `seg_out` builds output with sprintf into fixed 40-byte buffer — safe only because `restore()` caps digits at `FLT_DIG`.

## Entries — `seg.c`

- [ISSUE-correctness: NaN endpoints make `seg_cmp` let duplicate NaN segs satisfy `EXCLUDE USING gist (val WITH =)` (likely)] — `:744-855`
- [ISSUE-correctness: NaN in `gseg_picksplit` center → unstable qsort comparator → degenerate GiST tree (likely)] — `:354,303-314`
- [ISSUE-correctness: `HUGE_VAL` "regular" boundary collides with `-` sentinel (maybe)] — `:751-755`
- [ISSUE-defense-in-depth: `seg_out` builds output with sprintf into fixed 40-byte buffer, safe only because `restore()` caps digits at `FLT_DIG` (nit)] — `:130-159`

## Cross-sweep references

- A13 btree_gist float4/float8 NaN divergence — same root cause.
- A14 cube — sister geometric module with same NaN/Inf hazards.
