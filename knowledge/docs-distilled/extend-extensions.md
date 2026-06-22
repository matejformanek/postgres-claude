---
source_url: https://www.postgresql.org/docs/current/extend-extensions.html
chapter: "38.17 Packaging Related Objects into an Extension (extend-extensions)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Packaging objects into an extension — extend-extensions

The control-file + versioned-SQL-script mechanism behind `CREATE EXTENSION`.
This is the user-facing contract; the backend that enforces it lives in
`commands/extension.c`. Pairs with the `extension-development` skill.

## Non-obvious claims

- **`default_version` is effectively required.** Omit it and `CREATE
  EXTENSION foo` fails unless the caller passes an explicit `VERSION`.
  Version strings are **arbitrary tokens matched by string equality** — PG
  assumes no semantic-versioning ordering. [from-docs extend-extensions]
- **Two script-name shapes drive everything:** install script
  `extension--version.sql` (e.g. `foo--1.0.sql`) and update script
  `extension--old--new.sql` (e.g. `foo--1.0--1.1.sql`). Downgrade scripts
  (`foo--1.1--1.0.sql`) are equally legal. [from-docs]
- **`ALTER EXTENSION UPDATE` chains scripts along the shortest path** through
  the available `old--new` edges, treating them as a graph. A stray downgrade
  script can create a shorter-but-wrong path — a real footgun. Inspect with
  `SELECT * FROM pg_extension_update_paths('foo')` (NULL path = unreachable).
  [from-docs]
- **Direct multi-hop install needs no redundant full scripts** (post-PG 10):
  with `foo--1.0.sql` + `1.0--1.1` + `1.1--1.2`, `CREATE EXTENSION foo VERSION
  '1.2'` auto-chains; you don't ship `foo--1.2.sql`. [from-docs]
- **`MODULE_PATHNAME` in a script is textually replaced by the control file's
  `module_pathname`** before execution — the standard way to avoid hard-coding
  the `.so` path in every `CREATE FUNCTION ... LANGUAGE C`. [from-docs]
- **Three relocatability levels, not two:**
  1. `relocatable = true` → movable anytime via `ALTER EXTENSION ... SET
     SCHEMA`; the extension's objects must make **no** internal schema
     assumptions.
  2. `relocatable = false` + no `schema` → install-time relocatable: scripts
     use `@extschema@`, target chosen by `CREATE EXTENSION ... SCHEMA`.
  3. `relocatable = false` + `schema = 'x'` → hard-wired; `SCHEMA` option must
     match or is rejected. [from-docs]
- **Substitution tokens** (replaced, suitably quoted, before script run):
  `@extschema@` (target schema), `@extschema:reqext@` (a *required*
  extension's schema — but using it bakes that schema name into your objects),
  `@extowner@` (calling user, used by trusted extensions to assign ownership).
  [from-docs]
- **During script execution PG sets `search_path` to `@extschema@, pg_temp`**
  plus required-extension schemas appended, then restores it afterward. Don't
  rely on the caller's search_path inside scripts. [from-docs]
- **Membership is tracked in `pg_extension` + `pg_depend`;** member objects
  can't be dropped individually (only `DROP EXTENSION`). `pg_dump` emits just
  `CREATE EXTENSION` + privilege deltas (from `pg_init_privs`), **not** the
  member DDL. [from-docs]
- **Cluster-wide objects (roles, databases, tablespaces) can't be members** —
  an extension is single-database scoped. Temp objects created in a script are
  session-only members. [from-docs]
- **Configuration tables: mark with `pg_extension_config_dump(regclass,
  text)`** so `pg_dump` ships the *contents* (not the definition). Empty 2nd
  arg = whole table; non-empty = a `WHERE` filter selecting user-modifiable
  rows. Sequences (incl. serial-owned) must be marked directly; the filter has
  no effect on them. Re-call to change the filter; only `ALTER EXTENSION ...
  DROP TABLE` unmarks. [from-docs]
- **Security: trusted extensions are maximally exposed.** Scripts run as the
  bootstrap superuser but the installing user picks the (possibly hostile)
  schema. Qualify every name, set `search_path = pg_catalog, pg_temp`, use
  `OPERATOR(pg_catalog.=)` / `CASE WHEN expr` (not `CASE expr WHEN`), and
  exact-type-match function/operator calls to dodge overload capture.
  [from-docs]

## Links into corpus

- The backend that parses control files, resolves update paths, and runs
  scripts: [[knowledge/files/src/backend/commands/extension.c.md]].
- The C-function side of an extension's objects:
  [[knowledge/docs-distilled/xfunc-c.md]] (and `MODULE_PATHNAME` substitution
  there).
- The build-side companion that produces the installed control + SQL files:
  [[knowledge/docs-distilled/extend-pgxs.md]].
- Adding catalog rows for the functions an extension exposes:
  [[knowledge/idioms/catalog-conventions.md]].

## Caveats / verification

- All claims `[from-docs extend-extensions]`. The update-path graph search,
  `@extschema@` substitution, and `pg_extension_config_dump` are implemented
  in `source/src/backend/commands/extension.c` (`identify_update_path`,
  `execute_extension_script`, `extension_config_dump`) at anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc` — verify there before quoting
  exact behavior.
