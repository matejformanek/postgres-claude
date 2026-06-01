# `src/backend/utils/fmgr/dfmgr.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~700
- **Source:** `source/src/backend/utils/fmgr/dfmgr.c`

## Purpose

Dynamic loader for `.so` / `.dylib` / `.dll` extension modules. Wraps
`dlopen`/`dlsym` (or `LoadLibrary` on Win32) behind a process-local cache
that survives across function calls and across the `_PG_init` lifetime of
many extensions. Backs `LOAD`, `CREATE EXTENSION` C-language functions,
`shared_preload_libraries`, `session_preload_libraries`,
`local_preload_libraries`. [from-comment]

## Mental model

- **`DynamicFileList`** — singly-linked list of every loaded library
  (`file_list`), keyed on (device, inode, full filename). Stored in
  malloc, not palloc — survives memory-context resets. Re-load is a no-op
  if the same inode is already present. [verified-by-code] (`dfmgr.c:42-67`)
- **Magic block check.** Every PG extension must export a `Pg_magic_struct
  PG_MODULE_MAGIC_DATA` symbol whose `Pg_abi_values` matches the running
  postmaster's `magic_data` (PG version, BLCKSZ, NAMEDATALEN, indexed-by-
  64-bit-int, float-data layout, ABI extra-name). Mismatch →
  `incompatible_module_error` ereport(ERROR) before any code runs.
  (`dfmgr.c:77-78`, `:72-73`)
- **`_PG_init`** — if exported, called exactly once when the library is
  first loaded. After `_PG_init` returns, the library's GUCs and hook
  registrations are live. There is no `_PG_fini` (PG never unloads
  libraries). [from-comment]
- **Rendezvous variables.** A name-keyed hash (`rendezvousHashEntry`)
  letting two independently-loaded libraries find each other's globals
  by string name without symbol-level coupling. `find_rendezvous_variable`.

## API

- `load_external_function(filename, funcname, signalNotFound, **filehandle)`
  — load library if not loaded, return pointer to `funcname`. Used by
  C-language fmgr lookup (`fmgr.c`).
- `load_file(filename, restricted)` — load+`_PG_init` only, no symbol
  lookup. Used by `LOAD` SQL command and preload-libraries machinery.
- `lookup_external_function(handle, funcname)` — cheap follow-up lookup
  on an already-open handle.
- `expand_dynamic_library_name(name)` — searches `dynamic_library_path`
  (default `$libdir`); appends `DLSUFFIX` (`.so`/`.dylib`/`.dll`).
- `check_restricted_library_name(name)` — for `local_preload_libraries`,
  forbids absolute paths and `/` segments (only `$libdir/plugins/<name>`
  is allowed).
- `process_shared_preload_libraries` / `process_session_preload_libraries`
  — postmaster-start and per-backend-start preload drivers.

## Notable invariants

- Once loaded, a library is **never unloaded** — the entry stays in
  `file_list` for the life of the process. Avoids dangling pointers from
  registered hooks, fmgr callbacks, GUCs.
- File inode comparison: a recompiled `.so` at the same pathname but new
  inode is **re-loaded** as a separate entry; `_PG_init` will run again.
  Stale symbol pointers from the previous load become invalid the moment
  they're called.
- Win32 `SAME_INODE` is `false` always — relies on the filename string
  match alone since `st_ino` is meaningless. (`dfmgr.c:62-67`)
- `shared_preload_libraries` runs in the postmaster context, so its
  `_PG_init` can request shmem via `RequestAddinShmemSpace` /
  `RequestNamedLWLockTranche` and register `shmem_request_hook`.

## Tag tally

`[verified-by-code]` 1 / `[from-comment]` 3
