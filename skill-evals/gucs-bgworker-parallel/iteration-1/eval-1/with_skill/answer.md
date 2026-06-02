# Adding `myext.cache_size_kb` — registration sequence

## GucContext

Because the GUC sizes a shared-memory area allocated once at postmaster
start, the only safe context is **`PGC_POSTMASTER`**. Anything looser
(e.g. `PGC_SIGHUP`) means a SIGHUP could "change" the value while the
backing allocation stays the original size — breaking everything
silently downstream. Rule of thumb from the skill: if changing the value
mid-session would require reallocating shared memory, use
`PGC_POSTMASTER`.

[verified-by-code `source/src/include/utils/guc.h:71-80`]

## Picker — which `DefineCustom*Variable`

Integer-typed → `DefineCustomIntVariable`, signature in `utils/guc.h`.
[verified-by-code `source/src/include/utils/guc.h:358-416`]

## Flags

- `GUC_UNIT_KB` so the user can write `'128MB'` / `'2GB'` and guc.c
  converts to KB.
- Optional `GUC_SUPERUSER_ONLY` if the size is sensitive.

## Skeleton

```c
static int myext_cache_size_kb;

void
_PG_init(void)
{
    DefineCustomIntVariable("myext.cache_size_kb",
                            "Size of the myext shared cache.",
                            NULL,                         /* long_desc */
                            &myext_cache_size_kb,         /* valueAddr */
                            16 * 1024,                    /* boot_val: 16 MB */
                            64, INT_MAX / 1024,           /* min, max in KB */
                            PGC_POSTMASTER,
                            GUC_UNIT_KB,
                            NULL, NULL, NULL);            /* check/assign/show */

    /* MUST be the last GUC-related call for this prefix. */
    MarkGUCPrefixReserved("myext");

    /* Request the shmem area sized from the (now-set) GUC. */
    RequestAddinShmemSpace(myext_cache_size_kb * 1024L);
    shmem_request_hook = my_shmem_request;        /* PG16+ */
}
```

## After the DefineCustom* calls: `MarkGUCPrefixReserved`

You must call `MarkGUCPrefixReserved("myext")` **after** every
`DefineCustom*Variable` for the prefix. It does two things:

1. Removes any *placeholder* GUCs that guc.c stashed when
   `postgresql.conf` mentioned `myext.*` before the extension loaded —
   otherwise parallel-worker startup later trips over them.
2. Refuses future placeholders under the prefix, so a typo
   (`myext.cahce_size_kb = 64MB`) errors out with "unrecognized
   configuration parameter" instead of being silently accepted.

[verified-by-code `source/src/backend/utils/misc/guc.c:5178-5228`;
worked example in `source/src/test/modules/worker_spi/worker_spi.c:303-360`]

Note: the old name `EmitWarningsOnPlaceholders` is still a `#define`
alias but `MarkGUCPrefixReserved` is preferred for new code.

## Checklist (from SKILL.md §1.8)

- [x] `_PG_init` defines every custom GUC for the prefix.
- [x] `MarkGUCPrefixReserved("myext")` after all defs.
- [x] `PGC_POSTMASTER` because the value sizes a shmem allocation.
- [x] `GUC_UNIT_KB` so SQL accepts `'128MB'`.
- [x] No `check_hook` needed — guc.c enforces min/max already.
