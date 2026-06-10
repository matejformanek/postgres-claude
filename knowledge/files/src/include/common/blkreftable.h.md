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

## Issues

[ISSUE-trust-boundary: `BlockRefTableSetLimitBlock` accepts arbitrary
`limit_block` from caller-controlled data; no header-level contract
that a malicious BRT cannot silently drop blocks from a combined
backup (high)] `blkreftable.h:54-57` declares the setter with no
bounds-validation hint. A5's `common.md` headline: a hostile BRT can
set `limit_block` to a value smaller than the relation's true length,
and `pg_combinebackup` will treat the dropped tail as
"covered-by-bitmap" → blocks vanish from the reconstructed backup.
The .h does not even comment that the limit is security-sensitive on
read. Cross-link: backup chain trust model.

[ISSUE-undocumented-invariant: `report_error_fn` is documented to
"not return" (`blkreftable.h:44`) but the typedef is a normal C
function pointer — there is no compiler-enforced `noreturn`. A
buggy callback that DOES return leaves the reader in an undefined
state (medium)] The contract is comment-only.

[ISSUE-trust-boundary: `io_callback_fn` (`blkreftable.h:46`) takes
attacker-controlled `data`/`length` on read; the header punts all
length validation to callers. The opaque `BlockRefTableReader`
implementation in `.c` is the actual integrity-checker (low)]

## Cross-refs

- A5 `common.md` — limit_block attack (high).
- A6 `pg_combinebackup` — primary consumer.
- Companion: `src/common/blkreftable.c.md`.

## Confidence tag tally
`[from-comment]=1 [verified-by-code]=8`
