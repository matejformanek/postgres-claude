# Adding `myext.cache_size_kb` — registration sequence

## GucContext

Pick **`PGC_POSTMASTER`**. The GUC sizes a shmem allocation made once at
postmaster startup, so the value must be fixed for the lifetime of the
cluster. `PGC_SIGHUP` would let the visible value drift away from the
actual allocation. Rule of thumb from §1.2: if changing the value would
require reallocating shared memory, use `PGC_POSTMASTER`.
[verified-by-code `source/src/include/utils/guc.h:71-80`]

## Entry point

`DefineCustomIntVariable` — int-typed, supports min/max bounds.
[verified-by-code `source/src/include/utils/guc.h:358-416`]

## Flags

- `GUC_UNIT_KB` so the user can write `'128MB'`, `'2GB'`, etc. and
  guc.c converts to KB before storing the int.
- Optionally `GUC_SUPERUSER_ONLY` if the value should be hidden from
  non-superusers in `pg_settings`.

## Skeleton

```c
static int myext_cache_size_kb;

void
_PG_init(void)
{
    if (!process_shared_preload_libraries_in_progress)
        return;

    DefineCustomIntVariable("myext.cache_size_kb",
                            "Size of the myext shared cache.",
                            NULL,
                            &myext_cache_size_kb,
                            16 * 1024,                /* boot 16 MB */
                            64, INT_MAX / 1024,       /* min, max KB */
                            PGC_POSTMASTER,
                            GUC_UNIT_KB,
                            NULL, NULL, NULL);

    /* MUST come after every DefineCustom* for this prefix. */
    MarkGUCPrefixReserved("myext");

    /* PG >= 15: install the request hook, which runs after GUCs are
     * loaded but before main shmem is sized — so it can read the GUC. */
    prev_shmem_request_hook = shmem_request_hook;
    shmem_request_hook = my_shmem_request;
}

static void
my_shmem_request(void)
{
    if (prev_shmem_request_hook)
        prev_shmem_request_hook();
    RequestAddinShmemSpace(myext_cache_size_kb * 1024L);
}
```

## What you MUST call after the DefineCustom* calls

`MarkGUCPrefixReserved("myext")` — exactly once, **after** every
`DefineCustom*Variable` for the prefix. Two effects:

1. **Removes placeholder GUCs** that guc.c creates when a config file
   mentions `myext.foo` before this extension loads. Without removal,
   future parallel-worker startups trip over the stale placeholders
   (comment at `guc.c:5193-5195`: "We must actually remove invalid
   placeholders, else future parallel worker startups will fail.").
2. **Reserves the prefix** so future typos like `myext.cahce_size_kb`
   produce a clear "unrecognized configuration parameter" error
   instead of being silently accepted as a placeholder.

[verified-by-code `source/src/backend/utils/misc/guc.c:5178-5228`;
worked example `source/src/test/modules/worker_spi/worker_spi.c:303-360`]

Old name `EmitWarningsOnPlaceholders` is still a `#define` alias —
prefer `MarkGUCPrefixReserved` in new code.

## Checklist (from §1.8)

- [x] `_PG_init` defines the GUC under `process_shared_preload_libraries_in_progress`.
- [x] `MarkGUCPrefixReserved("myext")` after all DefineCustom* calls.
- [x] `PGC_POSTMASTER` because the value sizes a shmem allocation.
- [x] `GUC_UNIT_KB` so SQL accepts `'128MB'`.
- [x] `shmem_request_hook` reads the GUC and calls `RequestAddinShmemSpace`.
