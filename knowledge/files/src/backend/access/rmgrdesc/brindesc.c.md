---
path: src/backend/access/rmgrdesc/brindesc.c
anchor_sha: 4b0bf0788b0
loc: 107
depth: deep
---

# brindesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/brindesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 107

## Purpose

rmgr descriptor routines for the BRIN resource manager (`RM_BRIN_ID`,
records from `access/brin/brin_xlog.c` / `access/brin_xlog.h`). Renders
the BRIN WAL opcodes — index create, summary insert/update, samepage
update, revmap extend, desummarize — for `pg_waldump`.
[from-comment, brindesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `brin_desc(buf, record)` | `brindesc.c:19` | render one BRIN record |
| `brin_identify(info)` | `brindesc.c:73` | opcode → short name |

## Internal landmarks

- `brin_desc` is an `if/else if` chain keyed on the opcode after
  masking with `XLOG_BRIN_OPMASK` (brindesc.c:25). Each branch prints
  `heapBlk` / `pagesPerRange` / `offnum`-family fields. `XLOG_BRIN_UPDATE`
  (brindesc.c:42) reaches through the embedded `xlrec->insert.*`
  sub-struct for the new offset.

## Invariants & gotchas

- **`brin_desc` strips the init-page bit; `brin_identify` keeps it.**
  `brin_desc` does `info &= XLOG_BRIN_OPMASK` (brindesc.c:25) so
  `INSERT` and `INSERT+INIT` share one rendering branch, whereas
  `brin_identify` (brindesc.c:73) has *distinct* cases
  `XLOG_BRIN_INSERT` vs `XLOG_BRIN_INSERT | XLOG_BRIN_INIT_PAGE`
  → `"INSERT"` vs `"INSERT+INIT"`. This is the same init-page-as-a-bit
  pattern as heap (`heapdesc.c`) and is correct; the asymmetry is by
  design (the page contents differ, the rendered fields don't).
- **No `default:` / no `else`** — unknown opcode → empty string;
  `brin_identify` returns `NULL` for unknowns.

## Cross-refs

- Record structs + `XLOG_BRIN_*` opcodes + `XLOG_BRIN_OPMASK` /
  `XLOG_BRIN_INIT_PAGE`: `[[src/include/access/brin_xlog.h]]`.
- Init-page-bit precedent: `[[src/backend/access/rmgrdesc/heapdesc.c]]`
  (`heap_identify` keys on opcode + `XLOG_HEAP_INIT_PAGE`).
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
