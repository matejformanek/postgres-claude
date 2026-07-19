# utils/hsearch.h — dynahash public API

Source: `source/src/include/utils/hsearch.h` (151 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

PostgreSQL's workhorse in-memory hash table (`dynahash.c`). Used by syscache, relcache, plancache, lock table, buffer mapping, GUC, plus many extensions. Supports MemoryContext-backed, shared-memory, and partitioned variants.

## Public API

- Callback types: `HashValueFunc`, `HashCompareFunc`, `HashCopyFunc`, `HashAllocFunc` (`hsearch.h:21-43`).
- `HASHELEMENT` (`hsearch.h:50-54`): private prefix with link + cached hashvalue. Caller's struct follows, starting with the hash key.
- `HASHHDR` / `HTAB` opaque (`hsearch.h:57-60`).
- `HASHCTL` (`hsearch.h:64-84`): num_partitions, keysize, entrysize, hash/match/keycopy/alloc/alloc_arg/hcxt/hctl.
- Flag bits (`hsearch.h:87-100`): `HASH_PARTITION` (partitioned locking), `HASH_ELEM` (keysize+entrysize, REQUIRED), `HASH_STRINGS`, `HASH_BLOBS`, `HASH_FUNCTION`, `HASH_COMPARE`, `HASH_KEYCOPY`, `HASH_ALLOC`, `HASH_CONTEXT`, `HASH_SHARED_MEM`, `HASH_ATTACH`, `HASH_FIXED_SIZE`.
- `NO_MAX_DSIZE = -1` (`hsearch.h:103`) — expansible directory marker.
- `HASHACTION` enum (`hsearch.h:106-112`): `HASH_FIND`, `HASH_ENTER`, `HASH_REMOVE`, `HASH_ENTER_NULL` (returns NULL on OOM instead of ereport).
- `HASH_SEQ_STATUS` (`hsearch.h:114-122`): seq-scan cursor.
- API: `hash_create`, `hash_destroy`, `hash_stats`, `hash_search`, `get_hash_value`, `hash_search_with_hash_value`, `hash_update_hash_key`, `hash_get_num_entries`, `hash_seq_init[_with_hash_value]`, `hash_seq_search`, `hash_seq_term`, `hash_freeze`, `hash_estimate_size`, `AtEOXact_HashTables`, `AtEOSubXact_HashTables` (`hsearch.h:127-149`).

## Invariants

- **INV-key-at-start-of-entry** [from-comment, `hsearch.h:46-49`]: "The hash key is expected to be at the start of the caller's hash entry data structure." Entries are placed after HASHELEMENT on a MAXALIGN'd boundary, so key offset is fixed.
- **INV-HASH_ELEM-required** [verified-by-code, `hsearch.h:90`]: comment says "now required!" — every caller must set keysize and entrysize.
- **INV-HASH_STRINGS-vs-HASH_BLOBS** [verified-by-code, `hsearch.h:91-92`]: pick exactly one (or set HASH_FUNCTION/HASH_COMPARE manually). Strings use string hash + strncmp; blobs use tag_hash + memcmp.
- **INV-no-free-function** [from-comment, `hsearch.h:40-42`]: "there is no free function API; can't destroy a hashtable unless you use the default allocator." `hash_destroy` only works on context-backed tables.
- **INV-shared-mem-no-resize** [implicit]: HASH_SHARED_MEM ⇒ size fixed at creation (HASH_FIXED_SIZE typically also set). Hash tables in shared memory cannot grow.
- **INV-HASH_PARTITION-power-of-2** [verified-by-code, `hsearch.h:67`]: num_partitions must be a power of 2 — required for the partition lock indexing.
- **INV-hash-seq-must-terminate** [verified-by-code, `hsearch.h:144-145, 148-149`]: dropping a `HASH_SEQ_STATUS` without `hash_seq_term` leaves a "scan in progress" marker; `AtEOXact_HashTables` mops these up at xact end.
- **INV-HASH_ENTER_NULL-vs-HASH_ENTER** [verified-by-code, `hsearch.h:108-111`]: HASH_ENTER ereports on OOM; HASH_ENTER_NULL returns NULL. Use the latter inside spinlock/critical sections.

## Notable internals

- `HASH_ATTACH` (`hsearch.h:99`): attach to an already-initialized header in shmem (do not re-init).
- `hash_update_hash_key` (`hsearch.h:137-138`): in-place key change without delete+insert — preserves entry pointer for callers holding it.
- `get_hash_value` (`hsearch.h:133`) + `hash_search_with_hash_value` (`hsearch.h:134-136`): split lookup, useful when the hash is computed under a lock and the table walk happens later.

## Trust-boundary / Phase-D surface

- **`hash_seq_init` without `hash_seq_term`** is xact-cleanup-only — long-running seq scans across xact boundaries leak the "scan in progress" flag. Header notes the cleanup hooks but doesn't warn callers.
- **`HASH_ENTER` inside critical section** ereports on OOM → PANIC. Use `HASH_ENTER_NULL` in such sites.
- **Custom `HashValueFunc` must be deterministic + side-effect-free** — otherwise lookups misbehave. Header silent.

## Cross-refs

- `source/src/backend/utils/hash/dynahash.c` — implementation.
- `knowledge/files/src/include/utils/funccache.md` — one of many consumers.

## Issues

- `[ISSUE-INVARIANT: hash_seq_term required (medium)]` — easy to forget; an `__attribute__((cleanup))` wrapper macro would help.
- `[ISSUE-DOC: HASH_FIXED_SIZE in shared-mem context implicit (low)]` — shmem tables effectively need it; not enforced.

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/dynahash-hashctl.md](../../../../data-structures/dynahash-hashctl.md)
