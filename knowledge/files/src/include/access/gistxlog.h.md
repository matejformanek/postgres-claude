# gistxlog.h

- **Source path:** `source/src/include/access/gistxlog.h` (117 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

WAL record formats for GiST. [from-comment, gistxlog.h:1-9]

## Info bytes

| Bit | Use |
|---|---|
| `XLOG_GIST_PAGE_UPDATE` (0x00) | in-place modify (delete + insert tuples on one page) |
| `XLOG_GIST_DELETE` (0x10) | LP_DEAD tuple cleanup with snapshot conflict |
| `XLOG_GIST_PAGE_REUSE` (0x20) | recycle conflict signal (carries previous `deleteXid`) |
| `XLOG_GIST_PAGE_SPLIT` (0x30) | N-way page split |
| `XLOG_GIST_PAGE_DELETE` (0x60) | VACUUM unlink (target leaf + parent downlink delete) |
| 0x40, 0x50, 0x70 | reserved / retired |

## xlog struct family

- `gistxlogPageUpdate` — `ntodelete`, `ntoinsert`.
- `gistxlogDelete` — `snapshotConflictHorizon`, `isCatalogRel`, `ntodelete`, offsets[].
- `gistxlogPageReuse` — `locator`, `snapshotConflictHorizon`, `isCatalogRel`.
- `gistxlogPageSplit` — `orignsn`, `origrlink`, `origleaf`, `markfollowright`, `npage` + per-page block list.
- `gistxlogPageDelete` — `deleteXid`, `downlinkOffset`.

See `gistxlog.c.md` for replay semantics.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
