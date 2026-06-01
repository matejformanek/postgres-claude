# brin_tuple.c

- **Source path:** `source/src/backend/access/brin/brin_tuple.c` (722 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

On-disk encoding / decoding of BRIN summary tuples. **Outside callers deal only with `BrinMemTuple`** (a Datum/null array in palloc memory); this file converts between the in-memory form and the packed on-disk `BrinTuple`. [from-comment, brin_tuple.c:1-9]

## On-disk shape

- A simplified header (just total length + flag bits), then a **doubled null bitmap**: per indexed column there are two bits, `hasnulls` (any NULL in range) and `allnulls` (every value NULL). When `allnulls[i]`, the column's data area is empty. [from-comment, brin_tuple.c:10-23]
- Per descriptor attribute, the on-disk tuple carries an **opclass-determined number of values** (e.g. minmax = 2, minmax-multi = 1 bytea, inclusion = 1 box plus flags). Therefore the on-disk attribute layout follows `BrinDesc->bd_info[i]->oi_nstored`, **not** the index relation's TupleDesc. [from-comment, brin_tuple.c:13-16]

## Key functions

| Function | Role |
|---|---|
| `brin_form_tuple` | Memtuple → on-disk; computes size, packs null bits, serializes per-attribute Datums via `datumCopy` semantics |
| `brin_form_placeholder_tuple` | Build the "summarization in progress" placeholder (all-null) tuple |
| `brin_deform_tuple` | On-disk → memtuple; rebuilds Datum arrays without copy when possible |
| `brin_memtuple_initialize` | Allocate a `BrinMemTuple` matching a `BrinDesc` |
| `brin_new_memtuple` | Alloc + initial placeholder state |
| `brin_copy_tuple` | Deep-copy an on-disk tuple into caller-supplied buffer (used during evacuation) |
| `brin_tuples_equal` | Byte-wise equality of two on-disk tuples (for the unchanged-detection check in `brin_doupdate`) |

## Notes

- `bt_blkno` (the heap-block-number-of-the-range) is embedded in the on-disk tuple header — this is what `brinGetTupleForHeapBlock` uses to sanity-check that the revmap's TID still points at the right summary. [verified-by-code in brin_revmap.c:296]
- Placeholder tuples are written under exclusive lock on the regular page while the summarizer runs an opclass `addValue` loop over heap rows; they're recognized by a flag and replaced atomically when summarization finishes.

Tags: [from-comment, brin_tuple.c:1-23]; functions enumerated [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
