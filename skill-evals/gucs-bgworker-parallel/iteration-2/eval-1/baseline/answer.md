# `myext.cache_size_kb` — registration in `_PG_init`

For a value that sizes a shared-memory area, you want the GUC to be
fixed at postmaster start. So:

- **Entry point**: `DefineCustomIntVariable` (int-typed).
- **GucContext**: `PGC_POSTMASTER` — the only context that guarantees
  the value can't drift after the shmem allocation is made.
- **Flags**: `GUC_UNIT_KB` so the user can write `'128MB'`, `'2GB'`,
  etc. and have the parser convert to KB.

```c
static int myext_cache_size_kb;

void
_PG_init(void)
{
    DefineCustomIntVariable("myext.cache_size_kb",
                            "Size of the myext shared cache.",
                            NULL,
                            &myext_cache_size_kb,
                            16384,          /* 16 MB default */
                            64, INT_MAX/1024,
                            PGC_POSTMASTER,
                            GUC_UNIT_KB,
                            NULL, NULL, NULL);

    /* Detect typos in postgresql.conf. */
    EmitWarningsOnPlaceholders("myext");

    /* Then register shmem need. */
    RequestAddinShmemSpace(myext_cache_size_kb * 1024L);
}
```

## After the DefineCustom* calls

Call `EmitWarningsOnPlaceholders("myext")` so a misspelled GUC in
`postgresql.conf` produces a warning instead of being silently
ignored.
