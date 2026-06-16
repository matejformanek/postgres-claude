# Iteration 2 — answers

Same three prompts. The with_skill answers now reference the
post-edit SKILL.md content (tightened MarkGUCPrefixReserved cite,
guc_malloc README cite 50-62, check_hook per-type signature table,
`GUC_check_errcode` SQLSTATE gloss, `SplitIdentifierString` /
`SplitGUCList`, `guc_realloc`). Baseline is rerun cold.

---

## Eval 1 — Add `extension_foo.log_query = bool` to extension foo

### with_skill

In `foo.c`:

```c
static bool foo_log_query = false;

void
_PG_init(void)
{
    DefineCustomBoolVariable("extension_foo.log_query",
                             "Log every query routed through extension_foo.",
                             NULL,             /* long_desc */
                             &foo_log_query,
                             false,            /* boot_val */
                             PGC_SUSET,        /* or PGC_USERSET / PGC_SIGHUP */
                             0,                /* no flags needed */
                             NULL, NULL, NULL);

    MarkGUCPrefixReserved("extension_foo");    /* AFTER all DefineCustom* */
}
```

Five typed `DefineCustom*Variable` entry points are declared at
`source/src/include/utils/guc.h:358-416`. `DefineCustomBoolVariable` is
the right one for a bool. No hooks are needed for a plain on/off toggle
— pass NULL/NULL/NULL.

To read the value from C, refer to `foo_log_query` directly. guc.c
writes through `valueAddr`, so the variable is always live. From another
TU in `foo`, declare `extern bool foo_log_query;` in a private header.
No getter.

`MarkGUCPrefixReserved("extension_foo")` does two things per
`source/src/backend/utils/misc/guc.c:5185-5228`:

1. Removes any `GUC_CUSTOM_PLACEHOLDER`-flagged variables under the
   `extension_foo.` prefix. These get created when a config file
   mentions a custom variable before the defining extension loads.
   Without removal, future parallel-worker startup trips over them
   (per the comment block at `guc.c:5178-5183`: *"We must actually
   remove invalid placeholders, else future parallel worker startups
   will fail."*).
2. Records the prefix in `reserved_class_prefix` so future placeholders
   under it are refused — typos like `extension_foo.log_qeury` in
   `postgresql.conf` now produce a clear WARNING with
   `ERRCODE_INVALID_NAME` instead of silently being accepted.

Call it exactly once, **after** all `DefineCustom*` calls for the
prefix. The old name `EmitWarningsOnPlaceholders` is still a `#define`
alias (`source/src/include/utils/guc.h:421`) — prefer the new name in
new code.

GucContext: `PGC_SUSET` is the conservative choice. `PGC_USERSET` is
also fine if the log toggle has no security/audit weight. `PGC_SIGHUP`
if you want it cluster-wide and reload-aware. Rule of thumb from §2:
"loosest context that's still safe".

### baseline

Use `DefineCustomBoolVariable` in `_PG_init`:

```c
static bool foo_log_query = false;

void
_PG_init(void)
{
    DefineCustomBoolVariable("extension_foo.log_query",
                             "Log every query.",
                             NULL,
                             &foo_log_query,
                             false,
                             PGC_USERSET,
                             0,
                             NULL, NULL, NULL);
}
```

No hooks needed for a plain bool. Read from C by referring to
`foo_log_query` directly; `extern bool foo_log_query;` in a header if
you need it from another file.

`MarkGUCPrefixReserved` (formerly `EmitWarningsOnPlaceholders`) tells
the GUC machinery that unknown `extension_foo.X` parameter names in
`postgresql.conf` are typos, not custom variables to stub out. Call it
once after defining all your GUCs.

---

## Eval 2 — `foo.cache_dir` string GUC with directory check

### with_skill

```c
static char *foo_cache_dir = NULL;
static bool check_cache_dir(char **newval, void **extra, GucSource source);
static void assign_cache_dir(const char *newval, void *extra);
static const char *show_cache_dir(void);

void
_PG_init(void)
{
    DefineCustomStringVariable("foo.cache_dir",
                               "Directory for foo's on-disk cache.",
                               NULL,
                               &foo_cache_dir,
                               "/var/tmp/foo",
                               PGC_SIGHUP,
                               GUC_SUPERUSER_ONLY,
                               check_cache_dir,
                               assign_cache_dir,
                               show_cache_dir);
    MarkGUCPrefixReserved("foo");
}
```

The signature table in §6 spells out that for a string GUC, the
check_hook's first arg is `char **newval` (so `*newval` is the proposed
`char *`):

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
    return true;
}
```

Conventions (§6):

- Return false to reject. The default rejection SQLSTATE is
  `ERRCODE_INVALID_PARAMETER_VALUE` (22023); `GUC_check_errcode`
  overrides it (e.g. for `ERRCODE_INVALID_NAME` on typo-style
  rejections).
- Use `GUC_check_errdetail` / `errhint` / `errmsg` / `errcode` — never
  `ereport(ERROR)` directly except on OOM.
- If you replace `*newval` (e.g. to canonicalise / strip trailing
  slash), the replacement must be allocated with `guc_malloc` /
  `guc_strdup` — never `palloc` — and the old value must be `guc_free`'d.
  Use `guc_realloc` to grow an existing allocation. All four functions
  live at `source/src/include/utils/guc.h:473-476`.
  ([from-README `source/src/backend/utils/misc/README:50-62`])
- The check_hook may run **outside any transaction** (bootstrap,
  postmaster startup, config reload). Filesystem `stat()` calls are
  fine; catalog lookups must be guarded with `IsTransactionState()`.
- The check_hook may be called purely to validate (no assign to
  follow) — must be side-effect-free apart from `*newval` and `*extra`.

`assign_cache_dir`:

```c
static void
assign_cache_dir(const char *newval, void *extra)
{
    /* swap in. cannot fail. */
}
```

Cannot fail (no return value). May run during transaction rollback →
no catalog lookups. [from-README
`source/src/backend/utils/misc/README:78-109`]

`show_cache_dir`:

```c
static const char *
show_cache_dir(void)
{
    return foo_cache_dir;
}
```

Returns `const char *`. Static buffer is fine; not reentrant.
[from-README `source/src/backend/utils/misc/README:112-117`]

### baseline

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
```

The check_hook signature is `bool (*)(char **newval, void **extra,
GucSource source)`. Return false to reject. The assign hook can't fail
(no return). Show hooks return `const char *` and can use a static
buffer.

String storage: I think you have to use `guc_strdup` or similar instead
of `palloc` if you replace `*newval` — but I don't remember the exact
names of all the allocator functions.

Gotcha: check_hooks aren't always inside a transaction (config reload,
bootstrap), so don't unconditionally do catalog lookups — guard with
`IsTransactionState()`.

---

## Eval 3 — PGC_USERSET trap + list flags

### with_skill

**`foo.worker_count` should NOT be `PGC_USERSET`.** The skill's rule of
thumb in §2: "pick the loosest context that's still safe. If changing
the value mid-session would require restarting a worker or reallocating
shared memory, use `PGC_POSTMASTER`." Background workers spawned at
postmaster startup are precisely a postmaster-bound resource — the
count is read once and used to drive `RegisterBackgroundWorker` calls /
`RequestAddinShmemSpace`. A `PGC_USERSET` value that changes
post-startup is silently disconnected from the running pool.

Right context: **`PGC_POSTMASTER`**. (`PGC_SIGHUP` only if your
extension actively re-launches workers on reload, which most don't.)
The GucContext enum is at `source/src/include/utils/guc.h:71-80`.

**`foo.databases` identifier list.** §7 lists the two flags:

- `GUC_LIST_INPUT` (bit `0x000001`) — required to enable list parsing
  at all. Without it the value is one opaque string and the comma
  never gets split.
- `GUC_LIST_QUOTE` (bit `0x000002`) — required for *identifier* lists.
  Each element is double-quoted on serialization, so a name like
  `"My Database"` round-trips through `pg_dump` /
  `ALTER DATABASE ... SET`. Without `GUC_LIST_QUOTE` an embedded space
  or uppercase would re-split the list on re-parse. This is the flag
  combo `search_path` uses.

So:

```c
static char *foo_databases = NULL;

DefineCustomStringVariable("foo.databases",
                           "Databases to monitor.",
                           NULL,
                           &foo_databases,
                           "postgres",
                           PGC_POSTMASTER,
                           GUC_LIST_INPUT | GUC_LIST_QUOTE,
                           check_databases, NULL, NULL);
```

Parse the list inside the check_hook with
`SplitIdentifierString(rawstring, ',', &elemlist)`
(identifier-style lists) or `SplitGUCList(rawstring, ',', &elemlist)`
(general case). Both declared at
`source/src/include/utils/varlena.h:33-37`. Don't roll your own
splitter — these match how the parser handles `search_path`, including
quoted elements.

Any string replacement of `*newval` inside the check_hook must use
`guc_malloc` / `guc_strdup`, with the previous value released via
`guc_free`.

[verified-by-code `source/src/include/utils/guc.h:214-242` for flag bit
values]

### baseline

`PGC_USERSET` is the wrong context for `foo.worker_count` because the
workers are spawned at postmaster startup — a session-level SET can't
re-spawn them. The GUC would lie about reality. Use `PGC_POSTMASTER`
to force a server restart for changes, or `PGC_SIGHUP` if you actually
have reload handling for workers (unusual).

For `foo.databases` you need at least `GUC_LIST_INPUT` to enable
comma-splitting. For identifier lists like `search_path`, there's also
a flag — `GUC_LIST_QUOTE` — that double-quotes elements on output so
the list round-trips through pg_dump. Use both flags together.

Parse the actual list at check_hook time with `SplitIdentifierString`.

---
