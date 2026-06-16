# `contrib/pg_stash_advice/pg_stash_advice.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 111
- **Source:** `source/contrib/pg_stash_advice/pg_stash_advice.h`

Module header for `pg_stash_advice`, a **new-in-PG18+** contrib module that
parks plan-advice strings (the kind `pg_plan_advice` produces) in dynamic
shared memory keyed by `(stash_id, queryId)` and applies them automatically
as queries get planned. This header declares the shared-memory layout,
the simplehash-generated lookup table for stash-id → name, and the public
function prototypes consumed by `pg_stash_advice.c`, `stashfuncs.c`, and
`stashpersist.c`. [verified-by-code]

## API / entry points

- `pgsa_entry_key { uint64 pgsa_stash_id; int64 queryId; }` — the lookup
  key used by the entry dshash. [verified-by-code] `:30-34`
- `pgsa_entry { pgsa_entry_key key; dsa_pointer advice_string; }` — the
  payload entry. Advice string is a NUL-terminated C string in DSA.
  [verified-by-code] `:39-43`
- `pgsa_stash { char name[NAMEDATALEN]; uint64 pgsa_stash_id; }` —
  the stash directory entry. Named by string, addressed by integer ID
  internally. [verified-by-code] `:48-52`
- `pgsa_shared_state` (the top-level fixed-size shmem object) holds the
  module-wide `LWLock`, three tranche IDs (`dsa_tranche`,
  `stash_tranche`, `entry_tranche`), `next_stash_id` counter, the
  `dsa_handle` for the DSA area, two `dshash_table_handle` (for stash
  + entry hashes), the persistence-worker `bgworker_pid`, an
  `pg_atomic_flag stashes_ready` (set once on-disk dump has been
  loaded), and an `pg_atomic_uint64 change_count` driving incremental
  disk writes. [verified-by-code] `:57-70`
- `pgsa_stash_name` — simplehash element type, declared via
  `SH_DECLARE` for the `pgsa_stash_name_table` (extern-scoped so
  multiple `.c` files share one definition). [verified-by-code] `:73-86`
- GUC externs: `pg_stash_advice_persist`, `pg_stash_advice_persist_interval`. [verified-by-code] `:94-96`
- Function prototypes: `pgsa_attach`, `pgsa_check_lockout`,
  `pgsa_check_stash_name`, `pgsa_clear_advice_string`,
  `pgsa_create_stash`, `pgsa_drop_stash`, `pgsa_lookup_stash_id`,
  `pgsa_reset_all_stashes`, `pgsa_set_advice_string`,
  `pgsa_start_worker`. [verified-by-code] `:99-109`
- `PGSA_DUMP_FILE` = `"pg_stash_advice.tsv"` — on-disk persistence file. [verified-by-code] `:25`

## Notable invariants / details

- The `pgsa_stash_name_table` simplehash is declared with `SH_SCOPE
  extern`. The corresponding `SH_DEFINE` lives in
  `pg_stash_advice.c:72-80`, with extra macros (`SH_KEY`,
  `SH_HASH_KEY`, `SH_EQUAL`) supplied only at definition site —
  legal because the declared SH_SCOPE matches in both translation
  units. [verified-by-code]
- `LWLock` is embedded inline in `pgsa_shared_state` (not a pointer
  into MainLWLockArray). The lock protects: stash directory mutation,
  entry insertion/deletion, and the bgworker PID slot. Read-side
  attach uses LW_SHARED only. See `INV-locking` below.
  [verified-by-code] `:59` plus call sites in `pg_stash_advice.c`.
- `dsa_handle` and `dshash_table_handle` slots in `pgsa_shared_state`
  start as `*_HANDLE_INVALID` and the first attacher creates the
  underlying object under `LWLockAcquire(...EXCLUSIVE)`; later
  attachers see a valid handle and just attach. [verified-by-code]
  `pg_stash_advice.c:244-315`
- `stashes_ready` is a `pg_atomic_flag` (one-bit). `unlocked_test`
  works because once set it stays set for the postmaster's lifetime;
  no concurrent clear ever races. [from-comment + verified-by-code]
  `pg_stash_advice.c:170-171`, `stashpersist.c:144-148`.

## Potential issues

- `:25` `PGSA_DUMP_FILE` is a bare filename without a directory
  qualifier — `AllocateFile()` will open it relative to the data
  directory cwd. Not a bug; matches PG convention for `pg_stat.stat`
  etc. [from-comment via `stashpersist.c:264-272`] [ISSUE-style:
  hardcoded file basename, no GUC to redirect (nit)]
- The `pgsa_shared_state` struct mixes 64-bit atomics
  (`change_count`), single-bit atomics (`stashes_ready`), an inline
  LWLock, and tranche IDs without explicit cacheline padding —
  fine for a low-contention path (advice modification is rare) but
  worth noting. [inferred] [ISSUE-style: no padding hints, fine here
  (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_stash_advice`](../../../issues/pg_stash_advice.md)
<!-- issues:auto:end -->
