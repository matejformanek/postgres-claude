# Adding a new built-in LWLock 'FooBarLock'

To add a built-in (predefined) LWLock you need to touch a couple of files in the source tree. Here's the list.

## 1. `src/include/storage/lwlocklist.h`

This file contains a list of `PG_LWLOCK(id, name)` macro invocations that the build system processes to generate `lwlocknames.h`. Add an entry at the end:

```c
PG_LWLOCK(NN, FooBar)
```

where NN is the next unused number (just one higher than the current last entry). Don't reuse retired numbers and don't renumber existing entries — external tools (DTrace probes, debugging scripts) key on these IDs. The name in the macro omits the `Lock` suffix; the suffix is added by the generator so the symbol you reference from C will be `FooBarLock`.

## 2. `src/backend/utils/activity/wait_event_names.txt`

Add an entry for FooBar in the LWLock section so that `pg_stat_activity.wait_event` displays correctly. The name has to match exactly.

## 3. Optionally, a subsystem README

If your code lives under a subsystem with its own README (buffer manager, lock manager, etc.), document the new lock there.

## 4. The struct it protects

Add a header comment to the shared struct saying "protected by FooBarLock" and explain the invariant.

After editing those, rebuild — `MainLWLockArray` is sized at build time from the count of `PG_LWLOCK` entries and `CreateLWLocks` in `src/backend/storage/lmgr/lwlock.c` initializes them. You can then use `LWLockAcquire(FooBarLock, LW_EXCLUSIVE)` directly.

## Built-in vs `RequestNamedLWLockTranche`

`RequestNamedLWLockTranche()` is for extensions and other code that can't edit `lwlocklist.h`. The extension calls it from `_PG_init` (when preloaded via `shared_preload_libraries`); Postgres reserves a tranche of N locks in shared memory at startup, and the extension retrieves them later with `GetNamedLWLockTranche()`.

Choose the built-in `PG_LWLOCK` route if:
- You're patching core (not writing an extension).
- You want a single named lock referenced by a symbol.

Choose `RequestNamedLWLockTranche` if:
- You're writing an extension.
- You need an array of locks rather than a single one.
- The number of locks depends on a configuration value.

There's also a third pattern, `LWLockNewTrancheId()` + `LWLockInitialize()` + `LWLockRegisterTranche()`, for locks allocated inside DSM segments rather than the static shmem area.

## References

- `src/include/storage/lwlocklist.h`
- `src/backend/utils/activity/wait_event_names.txt`
- `src/include/storage/lwlock.h` — declarations of `RequestNamedLWLockTranche`, `GetNamedLWLockTranche`, `LWLockNewTrancheId`.
- `src/backend/storage/lmgr/lwlock.c` — implementation.
