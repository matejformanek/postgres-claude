# Adding `myext.cache_size_kb` — baseline answer

You'll want to register the GUC in your extension's `_PG_init`. The
function to use is `DefineCustomIntVariable` since the value is an
integer.

Since this GUC sizes a shared memory area that's allocated at server
startup, you have to use `PGC_POSTMASTER` as the context — that way the
value can only be changed by restarting the postmaster, which matches
the lifetime of your shared memory allocation. If you used something
like `PGC_SIGHUP` then someone could reload config and change the
value but your shared memory would already be allocated at the old
size.

For flags, you want a unit flag so the user can specify the value with
suffixes like `MB` or `GB`. Something like `GUC_UNIT_KB` would let them
write `128MB` and it would be stored as the right number of KB.

Skeleton:

```c
static int myext_cache_size_kb;

void
_PG_init(void)
{
    DefineCustomIntVariable("myext.cache_size_kb",
                            "Cache size in KB",
                            NULL,
                            &myext_cache_size_kb,
                            16384,            /* default */
                            1, INT_MAX,
                            PGC_POSTMASTER,
                            GUC_UNIT_KB,
                            NULL, NULL, NULL);

    /* request the shmem after the GUC is set */
    RequestAddinShmemSpace(myext_cache_size_kb * 1024L);
}
```

After the DefineCustom calls you should call `EmitWarningsOnPlaceholders`
with your prefix — this catches typos in postgresql.conf where the user
wrote a slightly wrong variable name. It scans the placeholder list and
warns about anything that doesn't match a real defined GUC.

You'd also typically set the `shmem_request_hook` and
`shmem_startup_hook` to allocate and initialize the shared memory once
postmaster has it all sized up.
