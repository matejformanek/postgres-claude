# Extension layout — anatomy of a working extension

Reference doc that traces a real contrib extension end-to-end, so a future
session can answer "what file does what" without re-reading the chapter.
The operational checklist lives in `.claude/skills/extension-development/SKILL.md`;
this file is the *why* + worked example.

Last-verified against PG master HEAD as of 2026-06-01.

## 1. The five-or-six file shape

A PG extension is a directory of these files (paths shown as they sit in
`source/contrib/pageinspect/`, but the shape is identical out-of-tree):

```
pageinspect.control                    # metadata
pageinspect--1.5.sql                   # base install script for v1.5
pageinspect--1.5--1.6.sql              # upgrade script: 1.5 -> 1.6
pageinspect--1.6--1.7.sql              # ... one per version step ...
pageinspect--1.12--1.13.sql            # upgrade to the current default_version
rawpage.c                              # the C code (one or many files)
brinfuncs.c btreefuncs.c ...           # additional C files compiled into one .so
pageinspect.h                          # private header shared across .c files
Makefile                               # PGXS build (also works in-tree)
meson.build                            # in-tree meson build (only contrib/)
sql/  expected/                        # regression tests
```

After `make install`, these land at well-known places under the install prefix:

- `<sharedir>/extension/pageinspect.control`
- `<sharedir>/extension/pageinspect--*.sql`
- `<pkglibdir>/pageinspect.so` (one shared lib, named by `MODULE_big`)

`CREATE EXTENSION pageinspect` finds the control file by name in
`<sharedir>/extension/`, reads `default_version`, finds the matching SQL
script, and executes it. SQL `AS 'MODULE_PATHNAME', 'foo'` calls are
dlopen+dlsym into the `.so`.

## 2. Worked example: pageinspect end to end

### 2.1 `pageinspect.control` — what `CREATE EXTENSION` reads first

Full content [verified-by-code, `source/contrib/pageinspect/pageinspect.control`]:

```
# pageinspect extension
comment = 'inspect the contents of database pages at a low level'
default_version = '1.13'
module_pathname = '$libdir/pageinspect'
relocatable = true
```

Each line maps to a column in `pg_extension` once installed:

- `comment` → `pg_description.description` for the extension.
- `default_version` → installed version when `CREATE EXTENSION` doesn't say
  `VERSION '…'`. Bumping this is the act of "releasing" a new version.
- `module_pathname` → `$libdir` is the install's `pkglibdir`; the placeholder
  is substituted for every `MODULE_PATHNAME` token in the SQL script at
  install time. Lets the same SQL work whether the .so lives in the standard
  pkglibdir or in a vendor sub-path.
- `relocatable = true` → the extension's objects can be moved to a different
  schema with `ALTER EXTENSION pageinspect SET SCHEMA …`. Requires that no
  internal SQL hard-codes a schema. Incompatible with a `schema = …` line.

Fields not used by pageinspect but worth knowing about (from
`source/doc/src/sgml/extend.sgml` §"Extension Files" [from-doc]):

- `superuser = true` (default) — only superusers can install/update.
- `trusted = true` (default false) — let non-superusers install a
  `superuser = true` extension, with the install script running as the
  bootstrap superuser. Used by extensions whose objects are safe by
  construction (e.g. citext).
- `schema = 'foo'` — pin objects to schema `foo`. Mutually exclusive with
  `relocatable = true`.
- `requires = 'cube, earthdistance'` — must-install-first list.
- `directory = 'extension/pageinspect'` — relocate SQL scripts under
  `<sharedir>/`. Rarely used.

### 2.2 `pageinspect--1.5.sql` — the install script

Header [verified-by-code, lines 1-4]:

```sql
/* contrib/pageinspect/pageinspect--1.5.sql */

-- complain if script is sourced in psql, rather than via CREATE EXTENSION
\echo Use "CREATE EXTENSION pageinspect" to load this file. \quit
```

The `\quit` is what makes `psql -f pageinspect--1.5.sql` print the message and
stop. `CREATE EXTENSION` reads the file directly with its own loader that
skips backslash commands, so the install proceeds.

Then comes a sequence of `CREATE FUNCTION` declarations, each backed by a C
symbol in the .so [verified-by-code, lines 9-17]:

```sql
CREATE FUNCTION get_raw_page(text, int4)
RETURNS bytea
AS 'MODULE_PATHNAME', 'get_raw_page'
LANGUAGE C STRICT PARALLEL SAFE;
```

`'MODULE_PATHNAME'` becomes `'$libdir/pageinspect'` after the control-file
substitution. `'get_raw_page'` is the C symbol name — must match a function
declared `PG_FUNCTION_INFO_V1(get_raw_page);` in the C source.

`STRICT` (null in → null out) and `PARALLEL SAFE` are properties the C
function must actually honor; PG cannot verify them.

### 2.3 `rawpage.c` — the C side

Magic block, once per .so [verified-by-code, `rawpage.c:32-35`]:

```c
PG_MODULE_MAGIC_EXT(
    .name = "pageinspect",
    .version = PG_VERSION
);
```

This generates a function `Pg_magic_func()` that the backend dlsym's on load
to check ABI compatibility (PG major version, FUNC_MAX_ARGS, INDEX_MAX_KEYS,
NAMEDATALEN, FLOAT8PASSBYVAL, FMGR_ABI_EXTRA). Missing it = the .so refuses
to load. The macro definition is at
`source/src/include/fmgr.h:540` [verified-by-code].

V1 SQL-callable function [verified-by-code, `rawpage.c:46-63`]:

```c
PG_FUNCTION_INFO_V1(get_raw_page_1_9);

Datum
get_raw_page_1_9(PG_FUNCTION_ARGS)
{
    text   *relname = PG_GETARG_TEXT_PP(0);
    int64   blkno   = PG_GETARG_INT64(1);
    bytea  *raw_page;

    if (blkno < 0 || blkno > MaxBlockNumber)
        ereport(ERROR,
                (errcode(ERRCODE_INVALID_PARAMETER_VALUE),
                 errmsg("invalid block number")));

    raw_page = get_raw_page_internal(relname, MAIN_FORKNUM, blkno);

    PG_RETURN_BYTEA_P(raw_page);
}
```

Note `PG_FUNCTION_INFO_V1` is required for every symbol named in `'MODULE_PATHNAME',
'symbol'`. No `_PG_init` here — pageinspect is lazily loaded.

### 2.4 The upgrade scripts

`pageinspect--1.12--1.13.sql` is the most recent step
[verified-by-code, lines 1-4]:

```sql
/* contrib/pageinspect/pageinspect--1.12--1.13.sql */

-- complain if script is sourced in psql, rather than via ALTER EXTENSION
\echo Use "ALTER EXTENSION pageinspect UPDATE TO '1.13'" to load this file. \quit
```

The body is the **delta only** — `CREATE OR REPLACE FUNCTION` for redefined
ones, `CREATE FUNCTION` for new ones, `ALTER FUNCTION … OWNER` /
`DROP FUNCTION` as needed. PG records the new installed version in
`pg_extension.extversion`.

To find an upgrade path PG runs a shortest-path search over the available
`<ext>--A--B.sql` files. Pageinspect ships a chain from `1.0--1.1` through
`1.12--1.13`, so anyone on any historical version can `ALTER EXTENSION
pageinspect UPDATE` and arrive at `default_version`.

### 2.5 `Makefile` (PGXS) and `meson.build`

Both are present in contrib/, with the Makefile gated for out-of-tree use:

```make
EXTENSION  = pageinspect
MODULE_big = pageinspect            # name of the .so
OBJS = brinfuncs.o btreefuncs.o ... rawpage.o
DATA = pageinspect--1.5.sql pageinspect--1.5--1.6.sql ...   # SQL scripts to install
REGRESS = page brin btree checksum gin gist hash oldextversions

ifdef USE_PGXS
PG_CONFIG = pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
else
subdir = contrib/pageinspect
top_builddir = ../..
include $(top_builddir)/src/Makefile.global
include $(top_srcdir)/contrib/contrib-global.mk
endif
```

[verified-by-code, `source/contrib/pageinspect/Makefile`]

The meson side is a shared_module + install_data + tests dict
[verified-by-code, `source/contrib/pageinspect/meson.build:20-61`]. In-tree
contrib extensions are built whenever the meson superbuild runs; out-of-tree
extensions only use the PGXS path.

The two paths are not interchangeable from the developer's side — they're the
build system's responsibility. From the **extension code's** side nothing
changes: same control file, same SQL scripts, same C.

## 3. The hook-based variant: auto_explain

`source/contrib/auto_explain/` has no SQL functions at all — it has a control
file, a `.so`, and that's it. It does its work by installing executor hooks
during `_PG_init`. So:

- No `pageinspect--X.Y.sql` analog with `CREATE FUNCTION` statements; the
  default install script (`auto_explain--1.0.sql`) is tiny.
- The control file still drives `CREATE EXTENSION`, but the user usually adds
  the module to `shared_preload_libraries` in postgresql.conf so `_PG_init`
  runs in the postmaster — this is what gets the executor hooks installed
  before any backend processes a query.

The hook-installation block lives at `auto_explain.c:312-321`
[verified-by-code]:

```c
prev_ExecutorStart = ExecutorStart_hook;
ExecutorStart_hook = explain_ExecutorStart;
prev_ExecutorRun = ExecutorRun_hook;
ExecutorRun_hook = explain_ExecutorRun;
prev_ExecutorFinish = ExecutorFinish_hook;
ExecutorFinish_hook = explain_ExecutorFinish;
prev_ExecutorEnd = ExecutorEnd_hook;
ExecutorEnd_hook = explain_ExecutorEnd;
```

And the chained call at `auto_explain.c:368-372`:

```c
if (prev_ExecutorStart)
    prev_ExecutorStart(queryDesc, eflags);
else
    standard_ExecutorStart(queryDesc, eflags);
```

This is the chain-of-responsibility convention every multi-extension PG
install depends on. Skipping it silently disables every extension that loaded
after yours.

GUC definitions are also in `_PG_init`, one `DefineCustomXxxVariable` per
parameter, ending with [verified-by-code, `auto_explain.c:310`]:

```c
MarkGUCPrefixReserved("auto_explain");
```

without which `auto_explain.*` settings written into postgresql.conf would
log "unrecognized configuration parameter" until the module is loaded.

## 4. Invariants worth carving in stone

- One `PG_MODULE_MAGIC[_EXT]` per `.so`, never more, never zero. Without it
  the dlopen call in `internal_load_library` fails ABI check
  [verified-by-code, `fmgr.h:443-446`].
- Every C symbol referenced by `CREATE FUNCTION ... AS 'MODULE_PATHNAME',
  'sym'` needs a `PG_FUNCTION_INFO_V1(sym);` declaration in the same .so.
- Once `<ext>--X.Y.sql` has shipped, it's frozen. New work goes in
  `<ext>--X.Y--X.Z.sql`. This is the only way `ALTER EXTENSION UPDATE` works
  for users who skipped versions.
- Anything installing executor/planner/utility/auth hooks belongs in
  `shared_preload_libraries`. Lazy loading after the first SQL call means
  the first few statements bypass the hook.
- If you define GUCs from `_PG_init`, finish with
  `MarkGUCPrefixReserved("<ext>")`. Otherwise a stray reference to a real
  parameter logs noise until the module loads.
- `relocatable = true` and `schema = 'foo'` cannot both be set; PG rejects
  the control file.
- `trusted = true` runs the install script as the bootstrap superuser even
  when invoked by a non-superuser. Every object created has to be safe under
  that elevated identity.

## 5. Pointers

- `source/doc/src/sgml/extend.sgml` — full chapter; `extend-extensions-files-*`
  sections list every control-file field with semantics.
- `source/doc/src/sgml/extend.sgml` §"Extension Building Infrastructure" →
  PGXS reference (the `extend-pgxs` chapter when rendered).
- `source/contrib/pg_buffercache/` — smallest clean contrib example.
- `source/contrib/pageinspect/` — multi-file, multi-upgrade reference.
- `source/contrib/auto_explain/` — hook + GUC reference.
- `source/src/include/fmgr.h:430-549` — `_PG_init`, `PG_MODULE_MAGIC[_EXT]`,
  ABI struct.
- `source/src/include/utils/guc.h:358-421` — `DefineCustomXxxVariable` family
  + `MarkGUCPrefixReserved`.
- `.claude/skills/extension-development/SKILL.md` — operational checklist.
- `.claude/skills/error-handling/SKILL.md`,
  `.claude/skills/memory-contexts/SKILL.md`,
  `.claude/skills/gucs-bgworker-parallel/SKILL.md` — sibling skills extensions
  almost always touch.
