# Iteration 1 — answers

Each eval answered twice, honestly, from the skill content.

---

## e1-planner-hook-scaffold

### Answer A

Minimum file set for an extension `myplan` at v1.0:

```
myplan.control          # metadata (default_version, module_pathname, ...)
myplan--1.0.sql         # SQL install script (likely tiny — no SQL funcs needed)
myplan.c                # C code with _PG_init that installs planner_hook
Makefile                # PGXS build
```

(Add `meson.build` only if living in-tree under `contrib/`.)

Control file minimally:
```
comment = 'log query plans'
default_version = '1.0'
module_pathname = '$libdir/myplan'
relocatable = true
```

C file needs `PG_MODULE_MAGIC_EXT(.name="myplan", .version=PG_VERSION);` and a
`_PG_init` that saves the previous `planner_hook`, installs yours, and chains
to `prev_planner_hook` (or `standard_planner` if NULL).

**Must be loaded via `shared_preload_libraries`.** Hooks installed in a
lazily-loaded `_PG_init` only take effect after the first SQL call to the
extension, so the first few queries in a backend bypass the hook. This is
common-mistake #4 in the skill.

### Answer B

Files: `myplan.control`, `myplan--1.0.sql`, `myplan.c`, `Makefile` (PGXS).
The SQL script needs the standard header `\echo Use "CREATE EXTENSION
myplan" to load this file. \quit` even if it creates no objects, plus an
optional `CREATE FUNCTION` if you expose anything callable.

In `myplan.c`:
- `PG_MODULE_MAGIC_EXT(.name="myplan", .version=PG_VERSION);` (one per .so).
- `static planner_hook_type prev_planner_hook = NULL;`
- `_PG_init` saves prev, assigns yours.
- Your hook calls `prev_planner_hook ? prev_planner_hook(...) :
  standard_planner(...)`.

Loading: `shared_preload_libraries = 'myplan'` in postgresql.conf. Required
because the hook must be installed in the postmaster before any backend
processes queries — otherwise lazy load means early queries in each new
backend bypass your hook.

---

## e2-create-extension-finds-sql

### Answer A

`CREATE EXTENSION foo` looks up `<sharedir>/extension/foo.control`, reads
`default_version` (or honors the user's `VERSION 'x.y'` clause), then finds
the matching `foo--<version>.sql` script and runs it via SPI. Each object
created during this script is tagged with `creating_extension` so it gets
a `DEPENDENCY_EXTENSION` recorded on the pg_extension row (this is how
`DROP EXTENSION` cascade-drops members).

For upgrades: `ALTER EXTENSION foo UPDATE [TO 'x.y']` triggers
`find_update_path`, which runs a shortest-path search over the available
`foo--A--B.sql` files in `<sharedir>/extension/`. If a user is on 1.0 and
you ship 1.3 with `1.0--1.1.sql`, `1.1--1.2.sql`, `1.2--1.3.sql`, then yes —
PG chains all three steps. If you also ship `1.0--1.3.sql`, PG prefers the
shorter single hop.

Key rule: never edit a released `foo--X.Y.sql`. New work goes in
`foo--X.Y--X.Z.sql` upgrade scripts so users on intermediate versions can
reach the target.

### Answer B

The control file is the entry point — PG reads
`<sharedir>/extension/<name>.control` (path overridable via
`Extension_control_path` GUC since PG 18). It uses the same parser as
postgresql.conf. From the control file it gets `default_version`,
`module_pathname`, `requires`, `schema`, `relocatable`, `superuser`,
`trusted`, and finds the install script `<name>--<default_version>.sql`
(or the version requested by the SQL command).

For upgrades, `find_update_path` does a graph search over available
`<name>--A--B.sql` files. So 1.0 → 1.3 will chain through whichever
shortest sequence of upgrade files exists. Each upgrade file should be a
**delta only** — `CREATE OR REPLACE FUNCTION`, `CREATE FUNCTION` for new
objects, `DROP FUNCTION` for removals.

Bump `default_version` in the control file when releasing 1.3, and add
the new upgrade file to `DATA = …` (PGXS) or `install_data(...)` (meson).
The header in the upgrade file is `\echo Use "ALTER EXTENSION foo UPDATE
TO '1.3'" to load this file. \quit`.

---

## e3-extension-vs-contrib

### Answer A

A PostgreSQL **extension** is a packaging contract: a `.control` file +
SQL install/upgrade scripts + (optionally) a loadable `.so`, installed via
`CREATE EXTENSION`. Extensions are what end users `CREATE EXTENSION foo`
to install.

A **contrib module** is anything under `source/contrib/`. Most contrib
modules *are* extensions (pageinspect, pg_buffercache, auto_explain, ...),
but contrib has historically included other things too. The defining
feature of contrib is "ships in the PG source tree and uses the in-tree
meson build" rather than "is an extension."

**No, you don't need to live in `contrib/` to use a modern build.** Two
build paths:

- **PGXS** (out-of-tree): your `Makefile` includes
  `$(shell pg_config --pgxs)`. Works against any installed PG. This is
  what every third-party extension uses.
- **In-tree meson**: contrib extensions get a `meson.build` and are built
  whenever the PG superbuild runs.

Out-of-tree extensions only use PGXS. The extension code itself (control
file, SQL, C) is identical either way.

### Answer B

Extension = a unit you install with `CREATE EXTENSION`. Defined by a
`.control` file + SQL scripts; may bundle a `.so`. The catalog row lives
in `pg_extension`.

Contrib module = a directory under `source/contrib/`. Practically all
modern contrib modules are extensions, but the *category* is "ships with
PG" not "is an extension." (Counter-example-ish: things like `pg_upgrade`
are contrib-adjacent tools, not extensions.)

You absolutely do not need to be in contrib/ to use meson — but the
in-tree meson superbuild only builds contrib/'s meson.build files. For
out-of-tree extensions, the standard build path is PGXS:

```make
PG_CONFIG = pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
```

If you want to develop your extension inside the PG meson build (e.g.
because you're prototyping in pg-claude's dev/), drop it under
`source/contrib/yourext/` with a small `meson.build` mirroring
`pg_buffercache`'s. Most third-party extensions ship PGXS-only.
