---
path: src/include/common/blkreftable.h
anchor_sha: 4b0bf0788b0
loc: 116
depth: skim
---

# blkreftable.h

- **Source path:** `source/src/include/common/blkreftable.h`
- **Lines:** 116
- **Last verified commit:** `4b0bf0788b0`
- **Companion file:** `common/blkreftable.c`.

## Purpose

Block-reference-table API consumed by `pg_combinebackup` (and the server-side incremental-backup machinery). For each `RelFileLocator+ForkNumber` covered by a WAL range, tracks: (a) a "limit block" (the truncation watermark — blocks ≥ limit are unconditionally considered modified, because the relation was shorter at that point) and (b) a bitmap/sparse-array of modified blocks below the limit. [from-comment, blkreftable.h:1-22]

## Public surface

- Magic number: `BLOCKREFTABLE_MAGIC 0x652b137b`. [verified-by-code, blkreftable.h:30]
- Opaque structs: `BlockRefTable`, `BlockRefTableEntry`, `BlockRefTableReader`, `BlockRefTableWriter`. [verified-by-code, blkreftable.h:32-35]
- `io_callback_fn (callback_arg, data, length) → int` — must return exactly `length` for writes; short writes are caller's problem. [verified-by-code, blkreftable.h:46]
- `report_error_fn (callback_arg, msg, …)` — must NOT return. Used for malformed-file errors during read. [verified-by-code, blkreftable.h:47]
- In-memory API: `CreateEmptyBlockRefTable`, `BlockRefTableSetLimitBlock`, `BlockRefTableMarkBlockModified`, `WriteBlockRefTable`, `BlockRefTableGetEntry`, `BlockRefTableEntryGetBlocks`. [verified-by-code, blkreftable.h:53-74]
- Incremental reader API: `CreateBlockRefTableReader`, `BlockRefTableReaderNextRelation`, `BlockRefTableReaderGetBlocks`, `DestroyBlockRefTableReader`. [verified-by-code, blkreftable.h:79-91]
- Incremental writer API (entries must arrive sorted by db/tablespace/relfilenumber/fork): `CreateBlockRefTableWriter`, `BlockRefTableWriteEntry`, `DestroyBlockRefTableWriter`. [verified-by-code, blkreftable.h:101-105]
- Per-entry helpers: `CreateBlockRefTableEntry`, `BlockRefTableEntrySetLimitBlock`, `BlockRefTableEntryMarkBlockModified`, `BlockRefTableFreeEntry`. [verified-by-code, blkreftable.h:107-114]

## Phase D notes

See `blkreftable.c.md` — magic+CRC are the only on-disk auth; chunk-count sanity-checked but per-block bitmap is unbounded by design.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=8`
