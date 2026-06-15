---
path: src/test/modules/test_dsm_registry/test_dsm_registry.c
anchor_sha: e18b0cb7344
loc: 149
depth: read
---

# src/test/modules/test_dsm_registry/test_dsm_registry.c

## Purpose

Exercises the DSM registry — the named-shmem service that lets
extensions obtain DSM segments, DSAs, and DSHash tables by name without
having to register them at `shared_preload_libraries` time. Demonstrates
each of `GetNamedDSMSegment`, `GetNamedDSA`, and `GetNamedDSHash` from
SQL-callable functions. `[verified-by-code]` `test_dsm_registry.c:34-44,58-73`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `set_val_in_shmem(int4)` | `:77` | Write the int value into the named DSM segment under `LW_EXCLUSIVE` |
| `get_val_in_shmem() returns int4` | `:89` | Read the int value under `LW_SHARED` |
| `set_val_in_hash(text key, text val)` | `:104` | Insert/replace an entry in the named DSHash, allocating the value string in the named DSA |
| `get_val_in_hash(text key) returns text` | `:131` | Look up a key in the named DSHash |

## Internal landmarks

- `init_tdr_dsm` (`:46`) — DSM initializer callback; asserts that the
  `arg` cookie equals `5432`, then allocates a fresh LWLock tranche via
  `LWLockNewTrancheId("test_dsm_registry")` and `LWLockInitialize`s the
  in-segment lock.
- `tdr_attach_shmem` (`:58`) — lazy attach helper; three named lookups
  use stable string keys (`"test_dsm_registry_dsm"`, `..._dsa`,
  `..._hash`). The DSM call passes `(void *) (intptr_t) 5432` as the
  init cookie.
- `dsh_params` (`:38`) — uses `dshash_strcmp` / `dshash_strhash` /
  `dshash_strcpy`; key buffer is 64 bytes inline in the entry struct.
- `set_val_in_hash` (`:104`) — on key collision, frees the existing DSA
  pointer with `dsa_free`, then `dsa_allocate` + `strcpy` for the new
  value; releases the dshash bucket lock via `dshash_release_lock`.

## Invariants & gotchas

- TEST MODULE — exists to exercise an API; not for production use.
- Lazy attach pattern: every SQL-callable starts with
  `tdr_attach_shmem()` — first call materializes the shmem state, later
  calls just check the static pointers. This is the recommended pattern
  for extensions that do not require shmem at preload time
  `[verified-by-code]` `:79,94,116,138`.
- Key length must fit inside the inline 64-byte `key[]` buffer
  (`:112-114`).
- `init_shmem` callback runs **exactly once** across the cluster, so the
  cookie check is a one-shot assertion that the caller correctly threaded
  its argument through.

## Cross-refs

- `source/src/backend/storage/ipc/dsm_registry.c` — the registry impl.
- `source/src/include/storage/dsm_registry.h` — `GetNamedDSMSegment`,
  `GetNamedDSA`, `GetNamedDSHash`.
- `source/src/backend/lib/dshash.c` — `dshash_strcmp` etc.
- `knowledge/files/src/test/modules/test_dsa/test_dsa.c.md` — DSA-only
  variant.
