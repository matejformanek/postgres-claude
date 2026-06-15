# src/test/modules/test_dsm_registry/test_dsm_registry.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 149
**Verification depth:** full read

## Role

Test module for the dynamic shared memory (DSM) registry. It exercises all three registry entry points — `GetNamedDSMSegment` (a plain fixed-size segment with an init callback), `GetNamedDSA` (a registered DSA area), and `GetNamedDSHash` (a registered dshash table) — and demonstrates storing variable-length values in the DSA-backed hash. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:63-72`. The registry lets independent backends look up the same named shared structures by string key without a static shmem reservation. [inferred]

## Public API

- `set_val_in_shmem(int4)` / `get_val_in_shmem()` — store/read an int in the named DSM segment under an LWLock. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:75-101`
- `set_val_in_hash(text key, text val)` / `get_val_in_hash(text key)` — store/read a string in the DSA-backed dshash table keyed by `key`. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:103-149`
- `init_tdr_dsm(void *ptr, void *arg)` — init callback for the named segment; validates `arg == 5432` and initializes the LWLock + val. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:46-56`
- `dsh_params` — static `dshash_parameters` using `dshash_strcmp`/`dshash_strhash`/`dshash_strcpy` with the entry's `val` offset as the key-size boundary. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:38-44`

## Invariants

- INV-1: `tdr_attach_shmem()` is idempotent per backend — the DSA and dshash are fetched only if their cached pointers are still NULL; the DSM segment is fetched every call. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:58-73`
- INV-2: The named segment's init callback runs once at creation and receives `arg = (void *)(intptr_t)5432`; any other value is an error. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:51-52,66`
- INV-3: Hash keys must fit in the `key[64]` field — enforced as `strlen(key) >= offsetof(...,val)` → error "key too long". [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:22-26,112-114`
- INV-4: On overwrite, the previous DSA allocation is freed before a new one is assigned, preventing a DSA leak. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:118-122`
- INV-5: The segment's `LWLock` guards `val`: writers take `LW_EXCLUSIVE`, readers `LW_SHARED`. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:81-83,96-98`

## Notable internals

- The segment's LWLock uses a dynamically assigned tranche via `LWLockNewTrancheId("test_dsm_registry")`. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:54`
- dshash insert path: `dshash_find_or_insert` → free old `entry->val` if found → `dsa_allocate` + `strcpy` into `dsa_get_address` → `dshash_release_lock`. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:118-125`
- dshash read path: `dshash_find(..., false)` (shared lock, no insert) → NULL→PG_RETURN_NULL → `cstring_to_text(dsa_get_address(...))` → `dshash_release_lock`. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:140-148`
- `TestDSMRegistryHashEntry.key[64]` defines both the key buffer and (via offsetof to `val`) the strcpy key-size for `dsh_params`. [verified-by-code] `source/src/test/modules/test_dsm_registry/test_dsm_registry.c:28-32,39`

## Cross-refs

- `source/src/backend/storage/ipc/dsm_registry.c` — GetNamedDSMSegment, GetNamedDSA, GetNamedDSHash.
- `source/src/include/storage/dsm_registry.h` — registry API declarations.
- `source/src/backend/utils/mmgr/dsa.c` — dsa_allocate/dsa_free/dsa_get_address.
- `source/src/backend/lib/dshash.c` — dshash_find/dshash_find_or_insert/dshash_release_lock, dshash_str* helpers.
- `source/src/backend/storage/lmgr/lwlock.c` — LWLockNewTrancheId, LWLockInitialize.

## Potential issues

None.
