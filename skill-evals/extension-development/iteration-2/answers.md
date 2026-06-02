# Iteration 2 — answers

Same 3 prompts as iter-1. Each answered twice: **A = with_skill** (using
current SKILL.md), **B = baseline** (no SKILL.md, training knowledge only).
Assertion list reused from iter-1 grading.

---

## e1 — planner_hook scaffold

### A (with_skill)

Minimum file scaffold for an extension named `myext`:

```
myext.control          # metadata read by CREATE EXTENSION
myext--1.0.sql         # SQL objects (near-empty for a pure-hook extension —
                       # just the `\echo Use "CREATE EXTENSION myext"...\quit`
                       # header is fine if you have no SQL functions)
myext.c                # planner_hook installation + _PG_init
Makefile               # PGXS (out-of-tree) — `meson.build` only if you live
                       # under source/contrib/
```

Control file (concrete values):

```
comment = 'log query plans'
default_version = '1.0'
module_pathname = '$libdir/myext'
relocatable = true
```

`myext.c` skeleton:

```c
#include "postgres.h"
#include "fmgr.h"
#include "optimizer/planner.h"

PG_MODULE_MAGIC_EXT(.name = "myext", .version = PG_VERSION);

static planner_hook_type prev_planner_hook = NULL;

static PlannedStmt *
myext_planner(Query *parse, const char *query_string, int cursorOptions,
              ParamListInfo boundParams)
{
    PlannedStmt *result;

    if (prev_planner_hook)
        result = prev_planner_hook(parse, query_string, cursorOptions, boundParams);
    else
        result = standard_planner(parse, query_string, cursorOptions, boundParams);

    /* log result->planTree here */
    return result;
}

void
_PG_init(void)
{
    prev_planner_hook = planner_hook;
    planner_hook = myext_planner;
}
```

Note that the `_PG_init` prototype is already in `fmgr.h` — don't redeclare
it (e.g. don't write `static void _PG_init(void)`); that silently creates a
different symbol that's never called.

**Loading:** `shared_preload_libraries = 'myext'` is **REQUIRED**, not lazy.
The decision table from the skill applies: any extension that installs an
executor/planner/utility/auth hook must be preloaded. Reason: with lazy
loading, `_PG_init` only runs on the first SQL call to a function in the
extension, so the first N queries in every backend bypass your hook
entirely. For a planner instrumentation tool that's a correctness bug —
you'll silently miss queries.

### B (baseline)

You'll need:

- `myext.control` — extension metadata
- `myext--1.0.sql` — install script (probably empty for a hook-only ext)
- `myext.c` — your C code with `_PG_init` and the hook
- `Makefile` using PGXS

The C file needs `PG_MODULE_MAGIC` and a `_PG_init` that does the
save-previous + assign pattern:

```c
static planner_hook_type prev_planner_hook = NULL;

void _PG_init(void) {
    prev_planner_hook = planner_hook;
    planner_hook = my_planner;
}
```

In `my_planner`, call the saved previous hook if non-NULL, else
`standard_planner`, so other extensions and core still work.

**Loading:** must go in `shared_preload_libraries`. Hooks installed in a
lazily-loaded `_PG_init` won't catch queries that run before any function
from the extension is called.

---

## e2 — CREATE EXTENSION finds SQL upgrade scripts

### A (with_skill)

`CREATE EXTENSION foo` looks for `foo.control` in `<sharedir>/extension/`
(typically `/usr/local/pgsql/share/extension/`). Since PG 18, the GUC
`extension_control_path` (C symbol `Extension_control_path`, see
`source/src/backend/commands/extension.c:77`) can override the lookup
directory list — useful for installing extensions in non-standard locations
without rebuilding PG.

From `foo.control` it reads `default_version` (the version used when
`CREATE EXTENSION foo` is called without `VERSION`). It then runs the
matching SQL file `foo--<version>.sql`. The script must start with
`\echo Use "CREATE EXTENSION foo" to load this file. \quit` so users can't
source it directly in psql.

For upgrades: `ALTER EXTENSION foo UPDATE [TO '1.3']`. PG searches the
extension directory for files matching `foo--A--B.sql` (one upgrade step
per file). If a user is on 1.0 and you ship 1.3, PG runs a **shortest-path
graph search** over the available step files:

- If you ship only `1.0--1.1.sql`, `1.1--1.2.sql`, `1.2--1.3.sql`, PG
  chains all three.
- If you also ship `1.0--1.3.sql`, the single hop wins (1 edge < 3).
- The search is the `find_update_path` function in `extension.c`. Each
  upgrade file needs the matching header:
  `\echo Use "ALTER EXTENSION foo UPDATE TO '1.1'" to load this file. \quit`.

When shipping a new version:

1. Add `foo--1.0--1.1.sql` with only the **diff** (new functions,
   `CREATE OR REPLACE` for changed sigs, `DROP` for removals).
2. Bump `default_version` in `foo.control`.
3. Add the new file to `DATA = …` in the PGXS Makefile (or to the
   `install_data(...)` call in meson).

**Never edit the released `foo--1.0.sql`.** That file is the install
script for fresh installs that pin to 1.0; mutating it breaks
reproducibility and the `ALTER EXTENSION UPDATE` chain.

While the upgrade script runs, PG sets the internal `creating_extension`
flag and tags every object created with `DEPENDENCY_EXTENSION` against the
extension — that's how `DROP EXTENSION` knows what to remove.

### B (baseline)

PG looks for `foo.control` under `$(pg_config --sharedir)/extension/`.
`default_version` in the control file picks the version when not
specified. The matching `foo--1.0.sql` is run.

For upgrades, you ship per-step files like `foo--1.0--1.1.sql`. When
`ALTER EXTENSION foo UPDATE TO '1.3'` is called, PG finds the shortest
chain of upgrade files from the current installed version to the target. If
you only ship single-step files (1.0→1.1, 1.1→1.2, 1.2→1.3), all three run
in sequence. If you ship a direct 1.0→1.3, that runs alone.

When shipping a new version:

- add the new upgrade script,
- bump `default_version`,
- add the new file to `DATA = …` in the Makefile (and to the `install_data`
  call if you use meson),
- include the upgrade-script header:
  `\echo Use "ALTER EXTENSION foo UPDATE TO '1.1'" to load this file. \quit`

Never edit a released SQL file in place — that's the install script for
users still on that version. Always add a new step file.

---

## e3 — extension vs contrib module

### A (with_skill)

- An **extension** is a packaging unit defined by a `.control` file + at
  least one SQL script (`<ext>--<ver>.sql`) + optionally a shared library
  (`.so`). It's installed via `CREATE EXTENSION` and dropped with
  `DROP EXTENSION`, which uses `pg_depend` to find all the objects to
  remove.
- A **contrib module** is anything that lives under `source/contrib/`.
  It's a *source-tree location*, not a packaging concept. Most contrib
  modules are extensions (pageinspect, pg_buffercache, auto_explain,
  pg_stat_statements, …), but a few aren't — e.g. command-line utilities
  like `oid2name` or `vacuumlo` ship as standalone binaries with no
  `.control` file.

**Not all contrib modules are extensions, and most extensions live
out-of-tree.** PGIS, TimescaleDB, pgvector, pg_partman — none in
`contrib/`.

**You do NOT need to put your extension in `contrib/` to use meson.** The
two build paths are:

- **PGXS** — the portable, out-of-tree path. Set `PG_CONFIG`, write a
  small Makefile, `make && make install`. This is what every third-party
  extension ships:

  ```make
  MODULE_big = myext
  OBJS = myext.o
  EXTENSION = myext
  DATA = myext--1.0.sql
  PGFILEDESC = "myext - log query plans"

  PG_CONFIG = pg_config
  PGXS := $(shell $(PG_CONFIG) --pgxs)
  include $(PGXS)
  ```

- **In-tree meson** — only for `source/contrib/*`. Out-of-tree extensions
  targeting meson directly are rare and not supported by the official
  extension docs.

The C code is identical regardless of build path — same `PG_MODULE_MAGIC`,
same `_PG_init`, same hooks, same `PG_FUNCTION_INFO_V1` macros. Only the
build glue (Makefile vs `meson.build`) differs.

### B (baseline)

Extension and contrib module aren't the same thing:

- **Extension** = the runtime concept: a `.control` file + SQL script
  (+ optional `.so`) installed and uninstalled atomically via
  `CREATE EXTENSION` / `DROP EXTENSION`.
- **Contrib module** = anything shipped in the source tree under
  `contrib/`. Most are extensions, a few (oid2name, vacuumlo) are
  standalone utilities.

Most extensions in the wild (PostGIS, pgvector, TimescaleDB) are *not*
contrib modules — they live in their own repos.

For meson: no, you don't have to put your extension in `contrib/`. Two
options:

1. **PGXS** (out-of-tree, by far the most common):
   ```make
   MODULE_big = myext
   OBJS = myext.o
   EXTENSION = myext
   DATA = myext--1.0.sql
   PG_CONFIG = pg_config
   PGXS := $(shell $(PG_CONFIG) --pgxs)
   include $(PGXS)
   ```
   Build with `make && make install`. Works against any installed PG.

2. **In-tree meson** — only relevant if your code lives under
   `source/contrib/`. The top-level PG meson build picks it up via
   per-extension `meson.build`.
