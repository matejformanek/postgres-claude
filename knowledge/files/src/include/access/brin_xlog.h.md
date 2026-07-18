# brin_xlog.h

- **Source path:** `source/src/include/access/brin_xlog.h` (151 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

WAL record format definitions for BRIN. Each `XLOG_BRIN_*` info bit is paired with an `xl_brin_*` struct. [from-comment, brin_xlog.h:1-12]

## Info bytes

| Bit | Meaning |
|---|---|
| `XLOG_BRIN_CREATE_INDEX` (0x00) | metapage init |
| `XLOG_BRIN_INSERT` (0x10) | first summary for a range |
| `XLOG_BRIN_UPDATE` (0x20) | cross-page summary replacement |
| `XLOG_BRIN_SAMEPAGE_UPDATE` (0x30) | overwrite in place |
| `XLOG_BRIN_REVMAP_EXTEND` (0x40) | one more revmap page |
| `XLOG_BRIN_DESUMMARIZE` (0x50) | manual desummarize |
| `XLOG_BRIN_INIT_PAGE` (0x80, OR-bit) | page in block 0 is logged as `WILL_INIT` and re-initialized at replay |
| `XLOG_BRIN_OPMASK` (0x70) | strip the `INIT_PAGE` bit to get the op code |

## xl_brin_* structs

- `xl_brin_createidx` — `pagesPerRange`, `version`.
- `xl_brin_insert` — `heapBlk`, `pagesPerRange`, `offnum`.
- `xl_brin_update` — embeds `xl_brin_insert` + `oldOffnum`.
- `xl_brin_samepage_update` — `offnum` only.
- `xl_brin_revmap_extend` — `targetBlk`.
- `xl_brin_desummarize` — `pagesPerRange`, `heapBlk`, `regOffset`.

Sizeof macros (`SizeOfBrinInsert` etc.) use `offsetof` to avoid padding.

See `brin_xlog.c.md`.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/brin-revmap.md](../../../../idioms/brin-revmap.md)

- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)