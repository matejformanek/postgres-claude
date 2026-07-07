---
scenario: add-new-extension
when_to_use: I want to add a brand-new contrib/ extension — .control + foo--1.0.sql + a .c with _PG_init + Makefile + meson.build + tests + docs — packaged as an installable `CREATE EXTENSION foo` module.
companion_skills: ["extension-development"]
related_scenarios: ["add-new-bgworker", "add-new-hook", "add-new-test-module"]
canonical_commit: 5ef1eefd76f
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new contrib/ extension

## Scope — what's in / out

**In scope:**
- A new top-level `contrib/<name>/` directory shipping a single
  loadable shared module + a `CREATE EXTENSION <name>` package.
- The four mandatory pieces: `<name>.control`, `<name>--1.0.sql`,
  `<name>.c` (with `PG_MODULE_MAGIC_EXT` and optionally `_PG_init`),
  `Makefile` + `meson.build`.
- Wiring into the two parent build systems (`contrib/Makefile`'s
  `SUBDIRS` and `contrib/meson.build`'s `subdir()` list).
- Regression tests via `REGRESS` / `tests += { regress: ... }`.
- The `doc/src/sgml/<name>.sgml` appendix entry + entity declaration
  in `filelist.sgml` + reference from `contrib.sgml`.

**Out of scope:**
- New `src/test/modules/<name>/` purely-test extensions (no install,
  no doc, no SQL) → see `add-new-test-module`.
- The extension introduces a brand-new hook in core → see
  `add-new-hook` (then this scenario wraps the demo extension around
  it).
- The extension defines a background worker → see `add-new-bgworker`
  (compose: this scenario for the package, that one for
  `RegisterBackgroundWorker` plumbing).
- Upgrade scripts (`<name>--1.0--1.1.sql`) for a *later* version bump:
  the v1.0 path is the focus here. Upgrade-script discipline is
  covered in `extension-development` skill.
- PGXS-only out-of-tree extensions (Makefile pattern is similar but
  there's no in-tree wiring).

## Pre-flight

- **Companion skill:** load `extension-development`. Covers
  `PG_MODULE_MAGIC_EXT`, `_PG_init`, `DefineCustomXxxVariable`,
  `MarkGUCPrefixReserved`, install-script vs upgrade-script discipline,
  and the `module_pathname` indirection [verified-by-code](source/src/include/fmgr.h:540).
- **Canonical commit:** `5ef1eefd76f` — *Allow archiving via loadable
  modules.* (Robert Haas, 2022-11-26). Introduced the
  `contrib/basic_archive/` extension end-to-end: control, SQL,
  `basic_archive.c` with `_PG_init` + GUC registration, Makefile,
  meson.build, regression tests, SGML docs, parent-Makefile and
  `meson.build` wiring. Tight, complete, modern shape.
- **Common pitfalls (one-line each):**
  - Forgot to add the directory to **both** `contrib/Makefile` SUBDIRS
    and `contrib/meson.build` `subdir()` — autoconf build sees it,
    meson build skips it (or vice versa); pgsql-hackers will flag.
  - `default_version` in `.control` doesn't match the script filename
    (`foo--1.0.sql` vs `default_version = '1.1'`) → `CREATE EXTENSION`
    fails with "extension … has no installation script for version".
  - `module_pathname = '$libdir/foo'` mismatched with `MODULE_big = bar`
    in Makefile → loader can't find the .so.
  - GUC defined in `_PG_init` without `MarkGUCPrefixReserved` — anyone
    can set bogus `foo.unknown_setting` and pollute the namespace
    (commit 88103567cb8 hardened this; see `knowledge/issues/extensions.md`).
  - SQL functions declared `LANGUAGE C` without `PARALLEL SAFE` /
    `PARALLEL RESTRICTED` — silently parallel-unsafe by default, kills
    plans.

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `contrib/<name>/<name>.control` | (NEW) META file read by `CREATE EXTENSION`. Required keys: `comment`, `default_version`, `module_pathname = '$libdir/<name>'`, `relocatable` (true/false). Optional: `schema`, `requires`, `superuser`, `trusted`, `encoding`. Convention: `default_version = '1.0'` for the initial release [verified-by-code](source/contrib/pg_prewarm/pg_prewarm.control). | — | extension-development |
| 2 | `contrib/<name>/<name>--1.0.sql` | (NEW) Install script for v1.0. First line: `\echo Use "CREATE EXTENSION <name>" to load this file. \quit` (refuses sourcing via psql). Declares all SQL objects: `CREATE FUNCTION … AS 'MODULE_PATHNAME', 'C_symbol' LANGUAGE C [PARALLEL SAFE]`, types, opclasses, views. Filename **must** match `default_version`. [verified-by-code](source/contrib/pg_prewarm/pg_prewarm--1.1.sql:1-14) | — | extension-development |
| 3 | `contrib/<name>/<name>.c` | (NEW) Module source. Mandatory: `#include "postgres.h"`, `#include "fmgr.h"`, and `PG_MODULE_MAGIC_EXT(.name = "<name>", .version = PG_VERSION);` at file scope [verified-by-code](source/contrib/pg_prewarm/pg_prewarm.c:31-34),[verified-by-code](source/src/include/fmgr.h:540). Define `void _PG_init(void)` only if the extension needs to register GUCs, hooks, bgworkers, or shmem requests at LOAD time [verified-by-code](source/contrib/pg_prewarm/autoprewarm.c:127). Each SQL-callable C function needs `PG_FUNCTION_INFO_V1(name);` + `Datum name(PG_FUNCTION_ARGS) { … }`. | — | extension-development |
| 4 | `contrib/<name>/Makefile` | (NEW) `MODULE_big = <name>` (one .so) **or** `MODULES = a b` (separate .so per file). `OBJS = $(WIN32RES) <name>.o …`. `EXTENSION = <name>`. `DATA = <name>--1.0.sql` (and any upgrade scripts). `PGFILEDESC = "<name> - one-liner"`. `REGRESS = <name>` to enable `make check`. `TAP_TESTS = 1` if you ship `t/*.pl`. End with the in-tree vs PGXS guard block [verified-by-code](source/contrib/pg_prewarm/Makefile). | — | extension-development |
| 5 | `contrib/<name>/meson.build` | (NEW) Declare `<name>_sources = files('<name>.c', …)`. Append `rc_lib_gen.process(win32ver_rc, …)` for Windows. `shared_module('<name>', <sources>, kwargs: contrib_mod_args)`. Append target to `contrib_targets`. `install_data('<name>--1.0.sql', '<name>.control', kwargs: contrib_data_args)`. Append a `tests += { 'name': '<name>', 'sd': …, 'bd': …, 'regress': { 'sql': […] }, 'tap': { 'tests': […] } }` block when there are tests. Pattern lifted verbatim from `contrib/pg_prewarm/meson.build` [verified-by-code](source/contrib/pg_prewarm/meson.build). | — | extension-development |
| 6 | `contrib/Makefile` | Add `<name>` to the `SUBDIRS` list, kept alphabetical. Conditional placement only if the module needs OpenSSL/libxml/Perl/Python/SELinux/uuid — see existing `ifeq (with_…)` blocks [verified-by-code](source/contrib/Makefile). | — | extension-development |
| 7 | `contrib/meson.build` | Add `subdir('<name>')` to the alphabetized list (lines 15-74) [verified-by-code](source/contrib/meson.build:15-74). Without this the meson build silently skips your directory. | — | extension-development |
| 8 | `contrib/<name>/sql/<name>.sql` | (NEW) Regression test input. First statement is `CREATE EXTENSION <name>;` (or with `SCHEMA` clause if not relocatable). Last is `DROP EXTENSION <name>;` to keep the test self-contained [verified-by-code](source/contrib/pg_prewarm/sql/pg_prewarm.sql). Referenced from `REGRESS =` in Makefile / `tests += { regress: { sql: [...] } }` in meson. | — | testing |
| 9 | `contrib/<name>/expected/<name>.out` | (NEW) Expected output for #8. Generate by running `pg_regress --temp-instance=… --inputdir=. <name>` once and copying `results/<name>.out` over after a manual review. | — | testing |
| 10 | `contrib/<name>/t/001_basic.pl` | (NEW, optional) TAP test in Perl using `PostgreSQL::Test::Cluster`. Only needed if the regression-test harness can't exercise the feature (e.g. needs restart, crash, or wire-protocol interaction). Enable via `TAP_TESTS = 1` in Makefile + `tap: { tests: [...] }` in meson. | — | testing |
| 11 | `doc/src/sgml/<name>.sgml` | (NEW) Appendix chapter. Top-level `<sect1 id="<name>">` with `<title>`, an overview `<para>`, then sub-`<sect2>`s for functions / configuration / examples. Each public SQL function gets a `<variablelist>` entry. Built and validated by `meson test --suite docs`. | — | — |
| 12 | `doc/src/sgml/filelist.sgml` | Add `<!ENTITY <name> SYSTEM "<name>.sgml">` to the alphabetized contrib entity list [verified-by-code](source/doc/src/sgml/filelist.sgml:154). Skip and docs won't link. | — | — |
| 13 | `doc/src/sgml/contrib.sgml` | Add `&<name>;` to the appendix include list (lines 130-180) [verified-by-code](source/doc/src/sgml/contrib.sgml:130-180). If the extension fits the "trusted, ships SQL-callable funcs" category, also add `<member><xref linkend="<name>"/></member>` to the `<simplelist>` near line 100 [verified-by-code](source/doc/src/sgml/contrib.sgml:100-111). | — | — |
| 14 | `contrib/<name>/.gitignore` | (NEW, optional) Standard contrib pattern: ignore `log/`, `results/`, `tmp_check/`, `tmp_check_iso/` — `pg_regress` and TAP harness scratch dirs [verified-by-code](source/contrib/pg_prewarm/.gitignore). | — | — |
| 15 | `src/tools/pgindent/exclude_file_patterns` | Add an entry only if the extension ships generated `.c` or `.h` files that pgindent should skip. Unusual; most contribs don't need it. | — | coding-style |

(Use `—` in the per-file doc column for genuinely-new files. Almost
every row here is NEW because the change-class is "create a new
directory".)

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Skeleton + build wiring.** Files: [1, 3, 4, 5, 6, 7,
   14]. Create the directory with the `.control`, a minimal
   `<name>.c` containing only `PG_MODULE_MAGIC_EXT(...)` and one
   placeholder `PG_FUNCTION_INFO_V1` if you have any SQL surface
   already designed, Makefile, meson.build. Add to
   `contrib/Makefile` SUBDIRS and `contrib/meson.build` subdir().
   Phase-end check: `meson compile -C dev/build-debug` builds
   `<name>.so` and `make -C contrib/<name>` succeeds. `make install`
   places `<name>.so` and `<name>.control` under
   `dev/install-debug/`.

2. **Phase 2 — SQL surface + smoke test.** Files: [2, 8, 9]. Author
   `<name>--1.0.sql` with real `CREATE FUNCTION` entries pointing at
   the symbols in `<name>.c`. Implement the C bodies (return-value
   shapes, `PG_GETARG_*` / `PG_RETURN_*` per `fmgr-and-spi`). Write
   `sql/<name>.sql` covering create-extension → call-each-function →
   drop-extension. Capture expected output. Phase-end check: `meson
   test -C dev/build-debug --suite regress --test <name>` passes
   (test name from `tests += { 'name': '<name>', ... }` in step 5).

3. **Phase 3 — _PG_init / hooks / GUCs (optional).** Files: [3
   again]. Only if the extension needs LOAD-time registration: add
   `void _PG_init(void)`, register GUCs via
   `DefineCustomXxxVariable`, immediately call
   `MarkGUCPrefixReserved("<name>")` to lock the namespace [verified-by-code](source/contrib/auto_explain/auto_explain.c). Install
   hooks (save the prev pointer, chain to it). For shmem / bgworker
   needs, compose with `add-new-shared-memory-region` /
   `add-new-bgworker`. Phase-end check: `shared_preload_libraries =
   '<name>'` boots cleanly; logs show your init prints if any; GUCs
   appear in `SHOW <name>.*`.

4. **Phase 4 — Docs + final hygiene.** Files: [11, 12, 13, 10
   (TAP if any)]. Write `doc/src/sgml/<name>.sgml`, declare the
   entity, include in `contrib.sgml`. Add TAP tests if behaviour
   demands restart / multi-cluster scenarios. Phase-end check: `meson
   test -C dev/build-debug --suite docs` passes and `meson test -C
   dev/build-debug --suite contrib` runs every test you wired up.

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`extension-loading`](../idioms/extension-loading.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | direct reference |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Forgot `contrib/meson.build` `subdir()` entry** — `meson
  compile` is silent and your extension never builds under meson
  (autoconf may still work via `contrib/Makefile`'s `SUBDIRS`). Both
  parent files must change together; this is the most common
  reviewer comment on new-extension patches [verified-by-code](source/contrib/meson.build:15-74).
- **`module_pathname` ↔ `MODULE_big` mismatch** — `.control` says
  `$libdir/foo`, Makefile says `MODULE_big = bar`. `CREATE
  EXTENSION` succeeds, every C-language function call fails with
  "could not access file 'foo': No such file". Always set both to
  the extension's canonical short name.
- **`default_version` doesn't match install-script filename** —
  `.control` declares `default_version = '1.1'` but only
  `<name>--1.0.sql` exists. `CREATE EXTENSION <name>` fails with
  "extension … has no installation script nor update path". Fix: add
  the matching `--1.1.sql`, or downgrade `default_version`.
- **GUC namespace pollution** — registering `foo.timeout` via
  `DefineCustomIntVariable` without a follow-up
  `MarkGUCPrefixReserved("foo")` lets users set arbitrary
  `foo.anything = '...'` lines in `postgresql.conf` with no error.
  Commit `88103567cb8` (*Disallow setting bogus GUCs within an
  extension's reserved namespace*) made the reserve call the
  standard discipline. See `knowledge/issues/extensions.md`.
- **`PG_MODULE_MAGIC` vs `PG_MODULE_MAGIC_EXT`** — older extensions
  use the bare `PG_MODULE_MAGIC;` macro. New code should prefer
  `PG_MODULE_MAGIC_EXT(.name = …, .version = PG_VERSION)` so the
  loader can surface name/version mismatches in `pg_loaded_extensions`
  [verified-by-code](source/src/include/fmgr.h:535-540).
- **Forgetting `PARALLEL SAFE` on pure C functions** — defaults to
  parallel-unsafe; queries that call your function never go parallel.
  If the C body has no transactional side-effects and reads no
  session state, annotate `PARALLEL SAFE` on the
  `CREATE FUNCTION` line.
- **Regress test depends on cluster-wide settings** — `pg_regress`
  starts a temp instance with mostly default GUCs. If your test
  needs `wal_level >= replica`, `shared_preload_libraries = …`, or
  `max_wal_senders`, request it via `EXTRA_INSTALL` and
  `EXTRA_REGRESS_OPTS` in the Makefile (and `regress_args` in
  meson). Symptom: works locally, fails in CI. The basic_archive
  patch hit this exactly; see commit `00c360a89c1`.

- **Synchronization traps** (sibling files that must change
  together):
  - `contrib/Makefile` SUBDIRS ↔ `contrib/meson.build` subdir()
    (always pair).
  - `.control` `default_version` ↔ `<name>--<ver>.sql` filename.
  - `.control` `module_pathname` ↔ Makefile `MODULE_big` ↔ meson
    `shared_module(<name>, …)`.
  - `Makefile` `DATA = …` ↔ `meson.build` `install_data(…)` — both
    must list every script (install + every upgrade).
  - `doc/src/sgml/filelist.sgml` `<!ENTITY>` ↔ `contrib.sgml`
    `&<name>;` include (skip either and docs build fails or omits
    the chapter).

## Verification (exact test invocations)

```bash
# Clean build picks up the new subdir entries
meson compile -C dev/build-debug

# Install so the .control + .sql are visible to initdb-time extension
# discovery
meson install -C dev/build-debug

# Smoke test: server boots, CREATE EXTENSION works
dev/install-debug/bin/initdb -D dev/data-debug
dev/install-debug/bin/pg_ctl -D dev/data-debug -l /tmp/pg.log start
psql -h /tmp -d postgres -c "CREATE EXTENSION <name>; \dx"

# Regression suite for the new extension (test name = the 'name' key in
# tests += { ... } in contrib/<name>/meson.build)
meson test -C dev/build-debug --suite contrib --test <name>

# Or via the in-tree Makefile path
make -C dev/build-debug/../postgresql-dev/contrib/<name> check

# TAP tests, if any
meson test -C dev/build-debug --suite contrib --test <name>

# Docs SGML validation
meson test -C dev/build-debug --suite docs

# Full contrib suite (catch cross-extension breakage)
meson test -C dev/build-debug --suite contrib
```

If you created a brand-new TAP test, the test name is the basename
without `.pl`, e.g. `001_basic`. List runnable tests with `meson test
-C dev/build-debug --list | grep <name>`.

## Cross-refs

- Companion skills: `.claude/skills/extension-development/SKILL.md`
  (the procedural rules for `.control` / `_PG_init` / GUCs /
  upgrade scripts), `.claude/skills/fmgr-and-spi/SKILL.md` (for the
  C function bodies), `.claude/skills/testing/SKILL.md` (regress +
  TAP harness for contribs).
- Related scenarios: `scenarios/add-new-bgworker.md` (compose when
  the extension ships a bgworker), `scenarios/add-new-hook.md`
  (compose when the extension's *raison d'être* is a new hook),
  `scenarios/add-new-test-module.md` (sibling: pure-test extension
  under `src/test/modules/`), `scenarios/add-new-guc.md` (compose
  when the extension registers GUCs).
- Idioms: `knowledge/idioms/extension-loading.md`,
  `knowledge/idioms/catalog-conventions.md` (only marginally:
  extensions don't go through BKI, but `pg_extension` rows obey the
  same OID rules at runtime), `knowledge/idioms/fmgr.md`.
- Subsystems: `knowledge/subsystems/extension-infra.md`,
  `knowledge/subsystems/utils-fmgr.md`,
  `knowledge/subsystems/build-system.md` (Makefile + meson dual
  wiring).
- Issues: `knowledge/issues/extensions.md` (GUC namespace
  hardening, `module_pathname` traps, parallel-safety defaults).
- Reference patch (canonical_commit): `git -C source show
  5ef1eefd76f` (basic_archive end-to-end; the cleanest modern
  template).
