# tidstore.c

- **Source path:** `source/src/backend/access/common/tidstore.c`
- **Lines:** 609
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tidstore.h`, `lib/radixtree.h` (template the backing store is instantiated from), `commands/vacuumlazy.c` (the primary consumer — keeps the set of dead TIDs to remove from indexes).

## Purpose

An in-memory set of `ItemPointerData` (block + offset), organised as a radix tree keyed by `BlockNumber` with bitmap-of-offsets values. Replaces the historical `dead_tuples` array used by VACUUM (a flat sorted array bounded by `maintenance_work_mem`) with a compact tree that supports parallel sharing through DSA. [from-comment, tidstore.c:3-19]

## Top-of-file comment

> "TID (ItemPointerData) storage implementation. TidStore is a in-memory data structure to store TIDs (ItemPointerData). Internally it uses a radix tree as the storage for TIDs. The key is the BlockNumber and the value is a bitmap of offsets, BlocktableEntry. TidStore can be shared among parallel worker processes by using TidStoreCreateShared(). Other backends can attach to the shared TidStore by TidStoreAttach()." [from-comment, tidstore.c:3-13]

## Public surface

- **Construction:** `TidStoreCreateLocal` (162, backend-private), `TidStoreCreateShared` (208, DSA-backed; takes a tranche id for the LWLock), `TidStoreAttach` (244, worker side), `TidStoreDetach` (269), `TidStoreDestroy` (317).
- **Locking:** `TidStoreLockExclusive` (287), `TidStoreLockShare` (294), `TidStoreUnlock` (301). For shared TidStores, callers MUST hold the appropriate lock around mutating / iterating operations.
- **Mutation:** `TidStoreSetBlockOffsets` (345) — sets the bitmap for one block; replaces any existing entry (VACUUM-style: collect all offsets per block, then set once).
- **Lookup:** `TidStoreIsMember` (421).
- **Iteration:** `TidStoreBeginIterate` (471), `TidStoreIterateNext` (493), `TidStoreEndIterate` (518), `TidStoreGetBlockOffsets` (566).
- **Sizing / handles:** `TidStoreMemoryUsage` (532), `TidStoreGetDSA` (544), `TidStoreGetHandle` (552).

## Key types

- **`BlocktableEntry`** (44) — Per-block value. Either an inline list of up to `NUM_FULL_OFFSETS` offsets (the common case for sparsely-dead pages) OR a bitmap of `nwords * BITS_PER_BITMAPWORD` bits indexed by offset. Layout includes a `flags` byte whose low bit is reserved for radix-tree pointer tagging. [verified-by-code]
- The backing radix tree is instantiated from `lib/radixtree.h` with key = `uint64` (block number, zero-extended) and value = `BlocktableEntry`. [verified-by-code]

## Key invariants and locking

- The TidStore-level LWLock (used only for shared TidStores) is held by callers via `TidStoreLockExclusive` / `TidStoreLockShare`. Local TidStores have no internal locking. [from-comment, tidstore.h; verified-by-code]
- `TidStoreSetBlockOffsets` REPLACES the existing entry for that block — incremental "add one offset" is not supported. Callers (VACUUM) collect all dead offsets per page in a local array first. [verified-by-code, tidstore.c:345-420]
- For shared TidStores, the DSA area is owned by the creator; attaching backends get a `dsa_handle` + `dsa_pointer` that they `TidStoreAttach` to. The DSA itself outlives all attachers until the creator destroys it. [verified-by-code, tidstore.c:208-318]
- `TidStoreMemoryUsage` returns the bytes used by the radix tree (DSA or local memory context). [verified-by-code]
- Iteration order is by ascending BlockNumber (radix-tree property). [from-comment, tidstore.c — iteration uses the underlying radix tree's ordered iterator]

## Functions of note

1. **`TidStoreSetBlockOffsets`** (345) — Build a fresh `BlocktableEntry` from the offsets array. If `noffsets <= NUM_FULL_OFFSETS` use the inline list form (cache-friendly for VACUUM, which most often sees 1-2 dead TIDs per page). Otherwise build a bitmap sized to the highest offset. Insert into the radix tree (`shared_rt_set` or `local_rt_set`). [verified-by-code]
2. **`TidStoreIsMember`** (421) — Radix-tree lookup, then inline-list or bitmap check. [verified-by-code]
3. **`TidStoreIterateNext`** (493) — Walks the radix tree in key order; per entry, returns the block + the entry. The caller then uses `TidStoreGetBlockOffsets` to expand back to offsets. [verified-by-code]

## Cross-references

- `vacuumlazy.c` is the primary consumer (the parallel-vacuum dead-TID set).
- `lib/radixtree.h` is included via templated instantiation; both `local_*` and `shared_*` variants are created via macros.

## Open questions

- Whether the inline `NUM_FULL_OFFSETS` form is byte-identical between local and shared TidStores (it should be, but I didn't trace the macro instantiations side-by-side). [unverified]

## Confidence tag tally
`[verified-by-code]=8 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
