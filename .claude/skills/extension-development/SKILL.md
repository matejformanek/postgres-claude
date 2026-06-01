---
name: extension-development
description: Operational checklist for building a PostgreSQL backend loadable extension (.so / contrib module) — .control file, foo--1.0.sql install + foo--1.0--1.1.sql upgrade scripts, PGXS vs meson build, `_PG_init`, shared_preload_libraries, chained hook installation (ProcessUtility_hook, planner_hook, ExecutorStart_hook), trusted vs untrusted, CREATE EXTENSION. Use whenever the user is writing a Postgres extension, adding a contrib module, exposing a C function as SQL, or installing a backend hook. Do NOT trigger for VS Code / Chrome / Firefox / browser extensions.
---

# Building a PostgreSQL extension

Skill for shipping a loadable extension — what files to create, what each file
declares, the two supported build paths, and the hook/GUC idioms that 90% of
real extensions use.

Reference doc with a worked end-to-end example (pageinspect):
`knowledge/conventions/extension-layout.md`.

## 1. The minimum file set

For an extension named `<ext>` at version `1.0`:

```
<ext>.control          # metadata read by CREATE EXTENSION
<ext>--1.0.sql         # SQL objects installed by CREATE EXTENSION <ext>
<ext>.c                # C code (if there is any)
Makefile               # PGXS build
meson.build            # in-tree meson build (only needed for contrib/)
```

Add upgrade scripts as the version moves: `<ext>--1.0--1.1.sql`,
`<ext>--1.1--1.2.sql`, … `ALTER EXTENSION <ext> UPDATE` chains them.

### `<ext>.control`

Real example, verbatim from `source/contrib/pageinspect/pageinspect.control`
[verified-by-code]:

```
# pageinspect extension
comment = 'inspect the contents of database pages at a low level'
default_version = '1.13'
module_pathname = '$libdir/pageinspect'
relocatable = true
```

Common fields (see `source/doc/src/sgml/extend.sgml` §"Extension Files"
[from-doc]):

- `default_version` — version installed when `CREATE EXTENSION` omits `VERSION`.
- `module_pathname` — substituted for `MODULE_PATHNAME` in the SQL scripts.
- `relocatable = true` — objects can be moved with `ALTER EXTENSION … SET SCHEMA`.
- `schema = 'foo'` — pin the extension's objects to schema `foo`
  (incompatible with `relocatable = true`).
- `requires = 'cube, earthdistance'` — install-time dependency on other
  extensions.
- `superuser = true` (default) — only superusers can install.
- `trusted = true` — relax `superuser = true`: a user with `CREATE` on the
  database can install it, and the install script then runs **as the bootstrap
  superuser**. Use sparingly. See `extend.sgml:779` [from-doc].

### `<ext>--1.0.sql`

Standard header to prevent users from sourcing it directly in psql
[verified-by-code, `pageinspect--1.5.sql:1`]:

```sql
/* contrib/<ext>/<ext>--1.0.sql */

-- complain if script is sourced in psql, rather than via CREATE EXTENSION
\echo Use "CREATE EXTENSION <ext>" to load this file. \quit

CREATE FUNCTION foo(int)
RETURNS int
AS 'MODULE_PATHNAME', 'foo'
LANGUAGE C STRICT PARALLEL SAFE;
```

`MODULE_PATHNAME` is replaced by `module_pathname` from the control file at
install time.

## 2. Two build paths

### PGXS (out-of-tree extensions)

The portable path used by every extension that doesn't live in `contrib/`.

```make
# Makefile
MODULE_big = <ext>
OBJS = <ext>.o
EXTENSION = <ext>
DATA = <ext>--1.0.sql <ext>--1.0--1.1.sql
PGFILEDESC = "<ext> - one-line description"
REGRESS = basic_test         # optional, runs files in sql/ vs expected/

PG_CONFIG = pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
```

Build & install: `make && make install` (uses the `pg_config` on PATH; set
`PG_CONFIG=/path/to/pg_config` to target a specific install).
[from-doc, extend-pgxs.sgml]

### In-tree (meson, the contrib/ path)

`source/contrib/*` use meson via the top-level build. Per-extension
`meson.build` is small [verified-by-code,
`source/contrib/pg_buffercache/meson.build`]:

```meson
pg_buffercache_sources = files('pg_buffercache_pages.c')

pg_buffercache = shared_module('pg_buffercache',
  pg_buffercache_sources,
  kwargs: contrib_mod_args,
)
contrib_targets += pg_buffercache

install_data(
  'pg_buffercache--1.0--1.1.sql', ...
  'pg_buffercache.control',
  kwargs: contrib_data_args,
)

tests += { 'name': 'pg_buffercache', ..., 'regress': { 'sql': [...] } }
```

The Makefile next to it stays for `USE_PGXS=1` users (`source/contrib/pg_buffercache/Makefile`).

Pg-claude builds happen in `dev/build-debug/`. See `build-and-run` skill.

## 3. C entry points

### `PG_MODULE_MAGIC` is mandatory

Without it, the backend refuses to load the `.so`. Place it once per module,
typically in the file that owns `_PG_init`. The modern form lets you tag the
module name and version [verified-by-code, `fmgr.h:540`]:

```c
PG_MODULE_MAGIC_EXT(
    .name = "<ext>",
    .version = PG_VERSION
);
```

The older `PG_MODULE_MAGIC;` (no args) is still accepted.

### `_PG_init`

Called once per backend on first load of the `.so`. Declaration is in
`fmgr.h:436` — do **not** redeclare it [verified-by-code]:

```c
void
_PG_init(void)
{
    /* Define GUCs, install hooks, RequestAddinShmemSpace, etc. */
}
```

`_PG_fini` exists but is effectively never called (modules aren't unloaded);
don't rely on it.

### Lazy load vs `shared_preload_libraries`

- **Lazy load**: `_PG_init` runs the first time a SQL function from the
  extension is called in a backend. Sufficient for extensions that only expose
  functions (pageinspect, pg_buffercache).
- **`shared_preload_libraries = '<ext>'`** in postgresql.conf: `_PG_init` runs
  in the postmaster, before forking backends. **Required** if the extension:
  - installs executor/planner/utility hooks (otherwise the first few queries
    in a backend bypass them),
  - calls `RequestAddinShmemSpace` / `RequestNamedLWLockTranche` (these only
    work from postmaster start),
  - registers a background worker via `RegisterBackgroundWorker`.

`auto_explain` is a textbook preload module — it installs executor hooks in
`_PG_init` [verified-by-code, `auto_explain.c:312-321`].

### `PG_FUNCTION_INFO_V1` for each SQL-callable function

Every C function referenced from `CREATE FUNCTION ... AS 'MODULE_PATHNAME',
'foo'` needs `PG_FUNCTION_INFO_V1(foo);` plus `Datum foo(PG_FUNCTION_ARGS)`.
[verified-by-code, `rawpage.c:46-49`]

## 4. Custom GUCs

`DefineCustomXxxVariable` lives in `source/src/include/utils/guc.h:358-416`
[verified-by-code]. Five flavors:

| Macro | Bound type |
|---|---|
| `DefineCustomBoolVariable` | `bool *` |
| `DefineCustomIntVariable` | `int *` (with `min`, `max`, optional `GUC_UNIT_MS`/`_KB`/`_BYTE`) |
| `DefineCustomRealVariable` | `double *` (with `min`, `max`) |
| `DefineCustomStringVariable` | `char **` (PG owns/frees the string) |
| `DefineCustomEnumVariable` | `int *` + `const struct config_enum_entry options[]` |

Call them from `_PG_init`. Real example from `auto_explain.c:139-308`
[verified-by-code]:

```c
DefineCustomIntVariable("auto_explain.log_min_duration",
    "Sets the minimum execution time above which plans will be logged.",
    "-1 disables logging plans. 0 means log all plans.",
    &auto_explain_log_min_duration,
    -1,                  /* boot value */
    -1, INT_MAX,         /* min, max */
    PGC_SUSET,           /* who can SET it */
    GUC_UNIT_MS,         /* flags */
    NULL, NULL, NULL);   /* check/assign/show hooks */

DefineCustomEnumVariable("auto_explain.log_format",
    "EXPLAIN format to be used for plan logging.", NULL,
    &auto_explain_log_format,
    EXPLAIN_FORMAT_TEXT,
    format_options,      /* {"text", EXPLAIN_FORMAT_TEXT, false}, ... */
    PGC_SUSET, 0, NULL, NULL, NULL);
```

**Always end the GUC block with `MarkGUCPrefixReserved("<ext>");`**
[verified-by-code, `auto_explain.c:310`]. This tells the GUC machinery that
`<ext>.*` names belong to a real (now-loaded) extension, suppressing
"unrecognized configuration parameter" warnings for forward references in
postgresql.conf.

## 5. Hooks (chain-of-responsibility)

PG exposes function-pointer hooks (declared as `extern Foo_hook_type Foo_hook;`
in their owning header). Multiple extensions can stack on the same hook, so
the convention is **save previous, call your code, then chain**.

Canonical pattern from `auto_explain.c:110-113, 313-321, 326-372`
[verified-by-code]:

```c
static ExecutorStart_hook_type prev_ExecutorStart = NULL;

void
_PG_init(void)
{
    prev_ExecutorStart = ExecutorStart_hook;
    ExecutorStart_hook = explain_ExecutorStart;
    /* ...install the rest... */
}

static void
explain_ExecutorStart(QueryDesc *queryDesc, int eflags)
{
    /* my work */

    if (prev_ExecutorStart)
        prev_ExecutorStart(queryDesc, eflags);
    else
        standard_ExecutorStart(queryDesc, eflags);   /* default impl */
}
```

For executor hooks the "default" lives behind `standard_ExecutorStart` /
`standard_ExecutorRun` / `standard_ExecutorFinish` / `standard_ExecutorEnd`.
For the planner: `standard_planner`. For utility: `standard_ProcessUtility`.

Commonly-installed hooks:

- `planner_hook` — wrap/replace planner.
- `ExecutorStart_hook` / `Run` / `Finish` / `End` — instrument execution.
- `ProcessUtility_hook` — observe/replace utility (DDL) execution.
- `ClientAuthentication_hook` — auth-decision callback.
- `shmem_request_hook` / `shmem_startup_hook` — reserve & init shared memory.
- `emit_log_hook` — intercept log lines (pgaudit-style).

Always use `PG_TRY` / `PG_FINALLY` if you mutate any global state across the
inner call — see the nesting-depth pattern in `auto_explain.c:382-393`
[verified-by-code]. The `error-handling` skill covers the longjmp rules.

## 6. Upgrade scripts and `ALTER EXTENSION UPDATE`

To ship version `1.1`, add:

1. `<ext>--1.0--1.1.sql` containing only the **diff** vs 1.0 (new functions,
   `CREATE OR REPLACE FUNCTION` for changed signatures, `DROP FUNCTION` for
   removals).
2. Bump `default_version = '1.1'` in `<ext>.control`.
3. Add the new file to `DATA = …` (PGXS) and to `install_data(...)` (meson).
4. Header in the upgrade file [verified-by-code,
   `pageinspect--1.12--1.13.sql:1-4`]:
   ```sql
   /* contrib/<ext>/<ext>--1.0--1.1.sql */
   \echo Use "ALTER EXTENSION <ext> UPDATE TO '1.1'" to load this file. \quit
   ```

Existing installs upgrade via `ALTER EXTENSION <ext> UPDATE [TO '1.1']`. PG
finds the shortest chain of upgrade scripts from the installed version to the
target. **Never edit `<ext>--1.0.sql` after release** — it's the fresh-install
script for users on 1.0; mutate via upgrade scripts instead.

## 7. Trusted vs untrusted

| | superuser=true (default) | superuser=true, trusted=true | superuser=false |
|---|---|---|---|
| Who can `CREATE EXTENSION` | superuser only | superuser OR user with CREATE on db | anyone with CREATE on db |
| Script runs as | calling superuser | bootstrap superuser | calling user |

Use `trusted = true` only if every object the script creates is safe to expose
under elevated privilege — no `LANGUAGE C` shells over privileged operations,
no untrusted PL functions running as superuser. See `extend.sgml:779-795`
[from-doc].

## 8. `pg_proc.dat` vs `CREATE FUNCTION` in the SQL script

- **In-tree builtin functions** (the ones shipped in core, not in a contrib
  extension) are declared in `src/include/catalog/pg_proc.dat`. The
  `catalog-conventions` skill covers that path.
- **Extension functions** live in the SQL install script as
  `CREATE FUNCTION ... AS 'MODULE_PATHNAME', 'symbol'`. They get a regular OID
  at install time, are owned by the extension, and dropped by
  `DROP EXTENSION`. Never put extension functions in `pg_proc.dat`.

## 9. Common mistakes

1. **Missing `PG_MODULE_MAGIC`.** Backend refuses to dlopen the module with a
   confusing "incompatible module" error.
2. **Forgetting `MarkGUCPrefixReserved("<ext>")`** after defining GUCs.
   Users see "unrecognized configuration parameter" warnings the moment
   anyone sets `<ext>.foo` before the extension has loaded.
3. **Not chaining a hook.** If you do `ExecutorStart_hook = mine;` without
   first saving the previous value and then calling it (or
   `standard_ExecutorStart`), every other extension stacked above you stops
   working — and core's default path stops running too.
4. **Installing hooks from a lazily-loaded module.** Hooks set inside a
   per-backend `_PG_init` only take effect after the first SQL call to the
   extension, so the first few statements bypass them. Anything that hooks
   the executor/planner/utility/auth path must be in
   `shared_preload_libraries`.
5. **Allocating into `CurrentMemoryContext` in `_PG_init`.** That context is
   the postmaster context (for preload) or a per-backend startup context
   (for lazy). Use `TopMemoryContext` for state that has to outlive everything
   in the backend; see `memory-contexts` skill.
6. **Editing the released `<ext>--X.Y.sql`** instead of adding
   `<ext>--X.Y--X.Z.sql`. Breaks reproducible installs and `ALTER EXTENSION
   UPDATE` paths.
7. **`relocatable = true` together with `schema = '…'`.** Mutually exclusive;
   `CREATE EXTENSION` will reject the control file.

## 10. Where to look in source

- `source/contrib/pg_buffercache/` — smallest clean contrib example (one
  `.c`, one meson.build, one SQL + upgrades).
- `source/contrib/pageinspect/` — multi-file C extension with many upgrade
  scripts; good for upgrade-flow reference.
- `source/contrib/auto_explain/` — hook-based preload module with custom
  GUCs of every flavor; the canonical hook pattern.
- `source/src/include/fmgr.h:430-549` — `_PG_init` + `PG_MODULE_MAGIC[_EXT]`.
- `source/src/include/utils/guc.h:358-421` — `DefineCustomXxxVariable` and
  `MarkGUCPrefixReserved`.
- `source/doc/src/sgml/extend.sgml` — full chapter on extension files and
  semantics.
- https://www.postgresql.org/docs/current/extend-extensions.html — the same
  chapter, rendered.
- https://www.postgresql.org/docs/current/extend-pgxs.html — PGXS reference.

## files-examined rows

Add the following rows to `progress/files-examined.md` (the memory-keeping
skill writes; don't edit the registry directly here):

```
| contrib/pageinspect/pageinspect.control | 2026-06-01 | (current master) | read | extension-development skill | .claude/skills/extension-development/SKILL.md, knowledge/conventions/extension-layout.md | Control-file field set |
| contrib/pageinspect/Makefile | 2026-06-01 | (current master) | read | extension-development skill | same | PGXS in-tree pattern with USE_PGXS fallback |
| contrib/pageinspect/meson.build | 2026-06-01 | (current master) | read | extension-development skill | same | shared_module + install_data + tests block |
| contrib/pageinspect/rawpage.c | 2026-06-01 | (current master) | read | extension-development skill | same | PG_MODULE_MAGIC_EXT + PG_FUNCTION_INFO_V1 patterns |
| contrib/pageinspect/pageinspect--1.5.sql | 2026-06-01 | (current master) | skim | extension-development skill | same | Install-script header + MODULE_PATHNAME |
| contrib/pageinspect/pageinspect--1.12--1.13.sql | 2026-06-01 | (current master) | skim | extension-development skill | same | Upgrade-script header |
| contrib/pg_buffercache/pg_buffercache.control | 2026-06-01 | (current master) | read | extension-development skill | same | Minimal control file |
| contrib/pg_buffercache/Makefile | 2026-06-01 | (current master) | skim | extension-development skill | same | Sibling of pageinspect Makefile |
| contrib/pg_buffercache/meson.build | 2026-06-01 | (current master) | read | extension-development skill | same | Minimal contrib meson.build |
| contrib/auto_explain/auto_explain.c | 2026-06-01 | (current master) | deep-read | extension-development skill | same | Canonical hook-chaining + DefineCustomXxx patterns |
| contrib/auto_explain/Makefile | 2026-06-01 | (current master) | skim | extension-development skill | same | Preload-module Makefile |
| contrib/auto_explain/meson.build | 2026-06-01 | (current master) | skim | extension-development skill | same | Preload-module meson.build |
| src/include/fmgr.h | 2026-06-01 | (current master) | read | extension-development skill | same | _PG_init decl + PG_MODULE_MAGIC[_EXT] macros |
| src/include/utils/guc.h | 2026-06-01 | (current master) | read | extension-development skill | same | DefineCustomXxxVariable + MarkGUCPrefixReserved signatures |
```
