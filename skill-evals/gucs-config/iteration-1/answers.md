# Iteration 1 — answers

For each eval: a **with_skill** answer that has access to
`.claude/skills/gucs-config/SKILL.md`, and a **baseline** answer that
relies only on general PostgreSQL knowledge (no SKILL.md peek).

---

## Eval 1 — Add `extension_foo.log_query = bool` to extension foo

### with_skill

In `foo--<ver>.sql` nothing changes; this is purely a C-side / shared-library
GUC. In `foo.c` you do four things:

1. Declare a backing variable at file scope:

    ```c
    static bool foo_log_query = false;
    ```

2. In `_PG_init`, call `DefineCustomBoolVariable` from `utils/guc.h`. The
   five typed `DefineCustom*Variable` entry points all live in
   `source/src/include/utils/guc.h:358-416`. For a plain boolean toggle the
   call is:

    ```c
    DefineCustomBoolVariable("extension_foo.log_query",
                             "Log every query routed through extension_foo.",
                             NULL,                /* long_desc */
                             &foo_log_query,      /* bool *valueAddr */
                             false,               /* boot_val */
                             PGC_SUSET,           /* superuser SET, or PGC_USERSET if safe */
                             0,                   /* flags */
                             NULL, NULL, NULL);   /* check/assign/show hooks */
    ```

3. After **all** `DefineCustom*` calls for the `extension_foo` prefix:

    ```c
    MarkGUCPrefixReserved("extension_foo");
    ```

4. Read the value from C anywhere in `foo.c` by referring to the same
   `foo_log_query` static. No getter is needed — guc.c writes through the
   `valueAddr` pointer you passed in, so the variable is always live. If
   another translation unit in `foo` needs to read it, mark the declaration
   `extern bool foo_log_query;` in a private header and define it in exactly
   one `.c` file.

For a plain boolean toggle with no derived state and no validation beyond
"true or false", you do **not** need a `check_hook`, `assign_hook`, or
`show_hook`. Pass `NULL, NULL, NULL` as the trailing trio.

`MarkGUCPrefixReserved("extension_foo")` does two things
[verified-by-code `source/src/backend/utils/misc/guc.c:5185-5228`]:

- It deletes any **placeholder** GUCs (flag `GUC_CUSTOM_PLACEHOLDER`) under
  the `extension_foo.` prefix. Placeholders are created when a config file
  mentions a custom variable name before the defining extension loads. If
  not removed, future parallel-worker startups trip over them.
- It records `extension_foo` in `reserved_class_prefix` so future
  placeholders under that prefix are refused — typos like
  `extension_foo.log_qeury` in `postgresql.conf` now error out instead of
  being silently accepted as new placeholders.

(The old name `EmitWarningsOnPlaceholders` is still a `#define` alias —
prefer the new name in new code, `source/src/include/utils/guc.h:421`.)

Context choice: `PGC_USERSET` is fine if the value is purely a per-session
toggle. `PGC_SUSET` is safer if logging carries any privacy/audit weight.
`PGC_SIGHUP` if you want a postmaster-wide knob refreshable on
`pg_reload_conf()`. The rule of thumb from the skill: pick the loosest
context that's still safe.

### baseline

To add a boolean GUC to an extension, in `_PG_init` call
`DefineCustomBoolVariable`. Roughly:

```c
static bool foo_log_query = false;

void
_PG_init(void)
{
    DefineCustomBoolVariable("extension_foo.log_query",
                             "Whether to log queries.",
                             NULL,
                             &foo_log_query,
                             false,
                             PGC_USERSET,
                             0,
                             NULL, NULL, NULL);
}
```

You don't need hooks for a plain bool. To read it from C, just refer to the
static variable; guc.c updates it through the pointer. No getter required.
If you want to use it from another file, declare `extern bool foo_log_query;`
in a header.

`MarkGUCPrefixReserved` (or the older `EmitWarningsOnPlaceholders`) tells
PostgreSQL that any unrecognized `extension_foo.X` name in postgresql.conf
is a typo, not a custom GUC stub. Call it once after the last
`DefineCustomBoolVariable` for this extension.

---

## Eval 2 — `foo.cache_dir` string GUC with directory-existence validation

### with_skill

A string GUC has three quirks vs. bool/int: (a) `valueAddr` is `char **`,
(b) the underlying storage must be `guc_malloc` / `guc_strdup`, never
`palloc`, and (c) validation logic should live in the check_hook, not in an
assign hook that can't fail.

```c
/* In foo.c */
static char *foo_cache_dir = NULL;

static bool check_cache_dir(char **newval, void **extra, GucSource source);
static void assign_cache_dir(const char *newval, void *extra);
static const char *show_cache_dir(void);

void
_PG_init(void)
{
    DefineCustomStringVariable("foo.cache_dir",
                               "Directory for foo's on-disk cache.",
                               NULL,                       /* long_desc */
                               &foo_cache_dir,             /* char **valueAddr */
                               "/var/tmp/foo",             /* boot_val */
                               PGC_SIGHUP,                 /* not USERSET — shared resource */
                               GUC_SUPERUSER_ONLY,         /* path → hide from regular users */
                               check_cache_dir,
                               assign_cache_dir,
                               show_cache_dir);
    MarkGUCPrefixReserved("foo");
}
```

[Skeleton form mirrors `source/src/test/modules/worker_spi/worker_spi.c:303-360`]

### `check_cache_dir`

Signature per the skill / `source/src/backend/utils/misc/README` per-variable
hooks section:

```c
static bool
check_cache_dir(char **newval, void **extra, GucSource source)
{
    struct stat st;

    if (*newval == NULL || (*newval)[0] == '\0')
    {
        GUC_check_errdetail("foo.cache_dir may not be empty.");
        return false;
    }

    if (stat(*newval, &st) != 0)
    {
        GUC_check_errcode(ERRCODE_INVALID_PARAMETER_VALUE);
        GUC_check_errmsg("foo.cache_dir \"%s\" does not exist", *newval);
        GUC_check_errhint("Create the directory before setting the parameter.");
        return false;
    }
    if (!S_ISDIR(st.st_mode))
    {
        GUC_check_errdetail("\"%s\" is not a directory.", *newval);
        return false;
    }
    if (access(*newval, W_OK) != 0)
    {
        GUC_check_errdetail("\"%s\" is not writable by the postgres user.",
                            *newval);
        return false;
    }

    /* Canonicalise: strip trailing slash. If we modify, we must guc_malloc
     * the replacement and guc_free the caller's copy. */
    /* (omitted: simple in-place edit on *newval is also legal as long as
     *  we don't reallocate.) */

    return true;
}
```

Important conventions from the skill:

- Return `false` to reject.
- Use `GUC_check_errdetail` / `GUC_check_errhint` / `GUC_check_errcode` /
  `GUC_check_errmsg` for the error message — **do not call `ereport(ERROR)`**
  except on out-of-memory.
- If you replace `*newval` with a different string, the replacement must be
  `guc_malloc`'d (or `guc_strdup`'d) and you must `guc_free` the previous
  value — never `palloc`.
- The check_hook may run **outside any transaction** (postmaster startup,
  bootstrap, config reload). Therefore if you ever do catalog lookups —
  here we don't, but generally — guard them with `IsTransactionState()`.
  Filesystem `stat()` calls are fine outside a transaction.
- The check_hook can also be called just to validate without assigning, so
  it must be side-effect-free apart from setting `*newval` and `*extra`.

### `assign_cache_dir`

Signature: `void assign_hook(const char *newval, void *extra)`. Cannot
fail (no return value). Do all fallible work in the check_hook above. May
run during transaction rollback, so no catalog lookups.

```c
static void
assign_cache_dir(const char *newval, void *extra)
{
    /* Close any open cache files keyed off the old dir, swap in the new one.
     * If we need to remember more than the new string, the check_hook would
     * have passed it through *extra (guc_malloc'd). */
}
```

### `show_cache_dir`

Signature: `const char *show_hook(void)`. Static buffer is fine (not
reentrant). Often used to hide secrets or rewrite paths.

```c
static const char *
show_cache_dir(void)
{
    /* Could rewrite e.g. expand $PGDATA prefix. Here just return raw. */
    return foo_cache_dir;
}
```

### baseline

For a string GUC `foo.cache_dir` with directory validation:

```c
static char *foo_cache_dir = NULL;

static bool
check_cache_dir(char **newval, void **extra, GucSource source)
{
    struct stat st;
    if (stat(*newval, &st) != 0 || !S_ISDIR(st.st_mode))
        return false;
    return true;
}

static void
assign_cache_dir(const char *newval, void *extra)
{
    /* swap state */
}

void
_PG_init(void)
{
    DefineCustomStringVariable("foo.cache_dir",
                               "Cache dir.",
                               NULL,
                               &foo_cache_dir,
                               "/tmp/foo",
                               PGC_SIGHUP,
                               0,
                               check_cache_dir,
                               assign_cache_dir,
                               NULL);
}
```

The check_hook signature is `bool (*)(char **newval, void **extra,
GucSource source)`. Return false to reject. The assign hook can't fail
because it has no return value. String GUCs use `char **` for the address
parameter. I think you have to use special malloc functions but I'm not
100% sure on the exact name — `guc_strdup` maybe? — don't allocate with
`palloc`.

Show hooks return `const char *`. Storage can be static.

Gotcha: not all check_hooks happen inside a transaction (e.g. config file
reload), so don't do catalog lookups unconditionally.

---

## Eval 3 — PGC_USERSET trap + GUC_LIST_INPUT for `foo.databases`

### with_skill

**`foo.worker_count` should NOT be `PGC_USERSET`.** Two reasons:

1. The skill's rule of thumb in §2: *"pick the loosest context that's still
   safe. If changing the value mid-session would require restarting a
   worker or reallocating shared memory, use `PGC_POSTMASTER`."* Background
   workers launched at postmaster startup are precisely a postmaster-bound
   resource — they're started before client backends exist, and the count
   may even drive a `RequestAddinShmemSpace` allocation.
2. Even setting aside shared memory, `PGC_USERSET` means *"any user can
   change it any time"* — but the workers have already been spawned. The
   GUC would be silently disconnected from the running worker pool. Every
   user session would see a `foo.worker_count` value that doesn't reflect
   reality. Confusing at best, security-relevant if the value is used in
   later authorization decisions.

The right context is **`PGC_POSTMASTER`** (the strictest one for
"effective only at postmaster startup, via `postgresql.conf` or command
line"). If you specifically want SIGHUP to take effect (without a worker
restart, accepting that already-running workers won't notice), then
`PGC_SIGHUP`. Both are listed in the GucContext table at
`source/src/include/utils/guc.h:71-80`.

**`foo.databases` comma-separated identifier list.** From §7 useful flags:

- `GUC_LIST_INPUT` — required to enable list parsing at all. Without this
  flag the value is treated as a single opaque string and the comma never
  gets split.
- `GUC_LIST_QUOTE` — each element is double-quoted on serialization, so a
  list of *identifiers* (like `search_path`) round-trips correctly even
  when an element needs quoting. **Required for identifier lists**; if you
  skipped it, `pg_dump` of `ALTER DATABASE ... SET foo.databases = ...`
  could re-parse the value incorrectly.

So:

```c
static char *foo_databases = NULL;

DefineCustomStringVariable("foo.databases",
                           "Databases to monitor.",
                           NULL,
                           &foo_databases,
                           "postgres",
                           PGC_POSTMASTER,           /* read once at startup */
                           GUC_LIST_INPUT | GUC_LIST_QUOTE,
                           check_databases, NULL, NULL);
```

Parse the list with `SplitIdentifierString(rawstring, ',', &elemlist)` in
the check_hook (it lowercases / strips quotes the same way the parser does
for `search_path`). The check_hook should `pfree(rawstring)` and
`list_free(elemlist)` on its own copy — but remember: any **replacement**
of `*newval` must use `guc_malloc` / `guc_strdup`, never `palloc`.

(`GUC_LIST_QUOTE` is the flag that lets `search_path = "Foo Bar", public`
survive a round-trip through `pg_dumpall`. Without it the embedded space
would re-split the list. Same logic applies here for any identifier list.)

[verified-by-code `source/src/include/utils/guc.h:214-242` for flag bit
values]

### baseline

`PGC_USERSET` is wrong if changing the GUC at session time can't actually
take effect — and that's exactly the case for `foo.worker_count` when the
workers are spawned at postmaster startup. You'd be lying to the user: the
GUC value can drift away from the real number of running workers, and any
new SET would do nothing. Use `PGC_POSTMASTER` so the only way to change
it is a server restart. (`PGC_SIGHUP` would let it pick up
`pg_reload_conf()` but only if your code actually restarts workers on
reload, which most extensions don't.)

For `foo.databases` as a comma-separated identifier list, you need at
least `GUC_LIST_INPUT` to enable list parsing. For identifier-style lists
like `search_path`, there's also a flag — I think `GUC_LIST_QUOTE` — that
makes the elements get double-quoted on output so the list round-trips
through `pg_dump`. Use both together.

Parse the actual list at check_hook time with `SplitIdentifierString` or
`SplitGUCList`.

---
