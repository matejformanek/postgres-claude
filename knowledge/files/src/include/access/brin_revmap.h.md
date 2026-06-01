# brin_revmap.h

- **Source path:** `source/src/include/access/brin_revmap.h` (41 lines)
- **Last verified commit:** `ef6a95c7c64`

Prototype header for the revmap API. `BrinRevmap` is an opaque typedef; the struct lives in `brin_revmap.c`. Exposed entry points: `brinRevmapInitialize`/`brinRevmapTerminate`, `brinRevmapExtend`, `brinLockRevmapPageForUpdate`, `brinSetHeapBlockItemptr`, `brinGetTupleForHeapBlock`, `brinRevmapDesummarizeRange`. See `brin_revmap.c.md`.
