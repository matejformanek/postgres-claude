---
scenario: add-new-test-module
when_to_use: Add an in-tree test module under `src/test/modules/<name>/` for backend behavior that can't be exercised from SQL alone — TAP harness scenarios, isolation specs that need C support funcs, or hook-coverage tests.
companion_skills: ["testing"]
related_scenarios: ["add-new-extension","add-new-bgworker"]
canonical_commit: 49cd2b93d7d
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new `src/test/modules/<name>`

## Scope — what's in / out

**In scope:**
- A new self-contained `src/test/modules/<name>/` directory shaped like a
  contrib extension but **never shipped to users** — `make install` /
  `make installcheck-world` at top level deliberately skip this tree
  [from-README](source/src/test/modules/README:11-14).
- The triple-fixture: regression SQL (`sql/` + `expected/`), isolation
  specs (`specs/` + `expected/`), and Cluster.pm TAP (`t/*.pl`) — pick
  one or more.
- Registering the module in both `src/test/modules/Makefile` and
  `src/test/modules/meson.build`.
- The `pg_test_mod_args` / `test_install_libs` / `test_install_data` /
  `tests += {...}` meson plumbing that wires the module into
  `meson test --suite test-modules`.
- The conditional-build patterns for modules gated on a configure flag
  (`enable_injection_points`, `with_ssl=openssl`, `have_cxx`,
  `PG_TEST_EXTRA=ldap`).

**Out of scope:**
- A user-facing `contrib/<name>/` extension — same skeleton, different
  install target. See `scenarios/add-new-extension.md`.
- The C-side _content_ of a bgworker / hook / WAL rmgr the test module
  exercises. See `scenarios/add-new-bgworker.md` and friends; this
  scenario is about the test-module *shell* around them.
- The PostgreSQL::Test::Cluster.pm Perl API itself — load the `testing`
  skill for that surface.

## Pre-flight

- **Companion skill:** load `testing` — covers `pg_regress` invocation,
  isolationtester spec format, and the `PostgreSQL::Test::Cluster`
  Perl API used by every `t/*.pl` file.
- **Canonical commit:** `49cd2b93d7d` — *Add test module
  injection_points.* A clean, end-to-end "add a new test-modules
  subdir" patch: Makefile, meson.build, `.c` + `.control` + `--1.0.sql`
  extension shell, a regression `sql/` + `expected/` pair, an isolation
  `specs/` + `expected/` pair, the parent-dir Makefile + meson.build
  edits, and the `.gitignore`. Read it before starting.
- **Common pitfalls (one-line each):**
  - Edited `src/test/modules/Makefile` but forgot `meson.build`
    (or vice versa). The autoconf build and meson build silently
    diverge — one tree's `installcheck` runs the module, the other
    doesn't. [verified-by-code](source/src/test/modules/Makefile:7-58) /
    [verified-by-code](source/src/test/modules/meson.build:3-60).
  - Forgot the `.gitignore` for `tmp_check/` (TAP) or `results/` +
    `output_iso/` (regress/iso) — generated dirs end up tracked. See
    [verified-by-code](source/src/test/modules/worker_spi/.gitignore:1-2).
  - Put the module in `SUBDIRS` unconditionally when it depends on a
    configure flag — break the build on platforms missing the dep.
    The pattern is `SUBDIRS += foo` if-enabled, `ALWAYS_SUBDIRS += foo`
    otherwise [verified-by-code](source/src/test/modules/Makefile:61-88).
  - Wrote `meson test --suite=<name>` but didn't add the `tests += {...}`
    dict — module compiles but no test ever runs. Meson's
    `pg_test_mod_args` only handles install/build; the `tests` global is
    what drives `meson test`.
  - Module C code calls `RegisterBackgroundWorker` / installs hooks but
    isn't in `shared_preload_libraries` — Cluster.pm's
    `->append_conf('postgresql.conf', "shared_preload_libraries = '<name>'")`
    or an `extra.conf` snippet is required. See
    [verified-by-code](source/src/test/modules/injection_points/extra.conf).
  - TAP test wants a second module already built (e.g. `worker_spi`
    needs `injection_points`). The Makefile needs `EXTRA_INSTALL = src/test/modules/<dep>`
    [verified-by-code](source/src/test/modules/worker_spi/Makefile:9). Meson
    handles this implicitly via `test_install_libs`.
  - Naming collision with a contrib extension — the `.control` file's
    `module_pathname = '$libdir/<name>'` resolves to the same shared
    library directory at install time. Pick a name not used in `contrib/`.

## File checklist (the FULL sweep)

Every row mandatory unless marked optional. `<name>` is your module
slug; pick e.g. `test_myhook`. Test fixtures (regress / iso / TAP) are
all optional individually but the module must have ≥1.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/test/modules/<name>/Makefile` | (NEW) Autoconf build. `MODULE_big = <name>`, `OBJS = $(WIN32RES) <name>.o`, optional `EXTENSION` / `DATA` / `REGRESS` / `ISOLATION` / `TAP_TESTS = 1`, optional `EXTRA_INSTALL = src/test/modules/<dep>`. Tail `include $(top_srcdir)/contrib/contrib-global.mk` is the magic that gives you `installcheck` for free. Model on [verified-by-code](source/src/test/modules/worker_spi/Makefile:1-24). | — | testing |
| 2 | `src/test/modules/<name>/meson.build` | (NEW) Meson build. Declare `<name>_sources = files('<name>.c')`, build with `shared_module(<name>, ..., kwargs: pg_test_mod_args)` and append to `test_install_libs`. If you ship a `.control` + `.sql`, append to `test_install_data`. Add a `tests += { 'name': '<name>', 'sd': ..., 'bd': ..., 'regress': {...}, 'isolation': {...}, 'tap': {...} }` dict — this is what `meson test` reads. Model on [verified-by-code](source/src/test/modules/worker_spi/meson.build:1-37). | — | testing |
| 3 | `src/test/modules/<name>/<name>.c` | (NEW) The test module backend code. `PG_MODULE_MAGIC;` at top, optional `_PG_init` for hook install / bgworker register, `PG_FUNCTION_INFO_V1(...)` + bodies for any SQL-callable C helpers. | — | testing |
| 4 | `src/test/modules/<name>/<name>.control` | (NEW, if exposing SQL) Extension control file: `comment`, `default_version = '1.0'`, `module_pathname = '$libdir/<name>'`, `relocatable = true`. Required iff you `CREATE EXTENSION <name>` from any test. Model on [verified-by-code](source/src/test/modules/worker_spi/worker_spi.control:1-5). | — | extension-development |
| 5 | `src/test/modules/<name>/<name>--1.0.sql` | (NEW, if exposing SQL) Extension script. `\echo Use "CREATE EXTENSION <name>" to load this file. \quit` guard at top, then `CREATE FUNCTION ... AS 'MODULE_PATHNAME', '<c_symbol>' LANGUAGE C ...` per SQL-visible helper. | — | extension-development |
| 6 | `src/test/modules/<name>/.gitignore` | (NEW) Ignore generated dirs. Minimum `/tmp_check/` for TAP; add `/results/`, `/output_iso/`, `/log/` if you also have regress/iso. Mirror [verified-by-code](source/src/test/modules/worker_spi/.gitignore:1-2). | — | testing |
| 7 | `src/test/modules/<name>/sql/<test>.sql` | (NEW, optional) `pg_regress` input. One file per test in `REGRESS = ...`. | — | testing |
| 8 | `src/test/modules/<name>/expected/<test>.out` | (NEW, optional) `pg_regress` expected output. Regenerate via `cp results/<test>.out expected/<test>.out` after manual verification. | — | testing |
| 9 | `src/test/modules/<name>/specs/<test>.spec` | (NEW, optional) `isolationtester` spec. `setup` / `teardown` / `session "s1" { ... } step "s1a" { ... }` / `permutation` blocks. Listed in `ISOLATION = ...` (Makefile) and `'isolation': { 'specs': [...] }` (meson). Model on [verified-by-code](source/src/test/modules/delay_execution/specs/partition-addition.spec). | — | testing |
| 10 | `src/test/modules/<name>/expected/<test>.out` | (NEW, optional) Isolation expected output. Same dir as regress expected; isolationtester writes one `.out` per spec. | — | testing |
| 11 | `src/test/modules/<name>/t/NNN_<topic>.pl` | (NEW, optional) Cluster.pm TAP test. `use PostgreSQL::Test::Cluster;` + `use PostgreSQL::Test::Utils;` + `use Test::More;`. Number sequentially from `001_`. Model on [verified-by-code](source/src/test/modules/worker_spi/t/001_worker_spi.pl). | — | testing |
| 12 | `src/test/modules/<name>/extra.conf` | (NEW, optional) Conf snippet to splice into a Cluster's `postgresql.conf` (`shared_preload_libraries = '<name>'` etc.). Loaded via `$node->append_conf('postgresql.conf', slurp_file('.../extra.conf'))` from the `t/*.pl`. See [verified-by-code](source/src/test/modules/injection_points/extra.conf). | — | testing |
| 13 | `src/test/modules/Makefile` | Add `<name>` to `SUBDIRS` (unconditional) or guard with `ifeq ($(<flag>),yes) SUBDIRS += <name>` + `else ALWAYS_SUBDIRS += <name>` (conditional). Keep alphabetical [verified-by-code](source/src/test/modules/Makefile:7-58). | — | testing |
| 14 | `src/test/modules/meson.build` | Add `subdir('<name>')` in alphabetical position. Conditional modules use `if get_option('<flag>') subdir('<name>') endif` — see how `injection_points` is unconditional in the meson tree because meson handles the flag inside the subdir's own `meson.build` [verified-by-code](source/src/test/modules/meson.build:3-60). | — | testing |
| 15 | `src/tools/pgindent/typedefs.list` | (Optional) If your `<name>.c` defines new public typedefs (structs, function-pointer types), `pgindent` needs them listed or it will misformat the declarations. The buildfarm regenerates this; locally `cd src/tools/pgindent && perl pgindent ...` will warn. | — | coding-style |

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Module skeleton + registration.** Files: [1, 2, 3, 6,
   13, 14]. Edits: minimal `<name>.c` with `PG_MODULE_MAGIC` and a
   trivial `_PG_init` (or stub); Makefile + meson.build wired; parent
   dir Makefile + meson.build updated. Phase-end check: `meson compile
   -C dev/build-debug` succeeds, `ls dev/install-debug/lib/<name>.so`
   exists, `meson test -C dev/build-debug --list | grep <name>`
   resolves (even with zero tests so far).
2. **Phase 2 — Extension shell (if SQL-callable).** Files: [4, 5].
   Edits: `.control` + `--1.0.sql`; SQL-callable `PG_FUNCTION_INFO_V1`
   bodies in `<name>.c`. Phase-end check: `make -C
   src/test/modules/<name> install && psql -c 'CREATE EXTENSION
   <name>'` works against a fresh cluster.
3. **Phase 3 — Test fixtures.** Files: [7, 8] for regress, [9, 10] for
   isolation, [11, 12] for TAP (any subset). Edits: write the `.sql` /
   `.spec` / `.pl` content; regenerate `expected/` once by manual
   review. Phase-end check: `meson test -C dev/build-debug --suite
   test-modules --test <name>` is green from a clean tree.
4. **Phase 4 — Polish + conditional gating (only if your module
   depends on a configure flag).** Files: [13, 14] revisited. Edits:
   wrap with `ifeq`/`else`/`ALWAYS_SUBDIRS` in Makefile; mirror the
   `get_option(...)` guard in `meson.build`. Verify the tree builds
   with the flag both on and off.

## Pitfalls

- **Build-system divergence.** Forgetting one of `src/test/modules/Makefile`
  *or* `src/test/modules/meson.build` is the #1 trap — the module
  compiles and links from one build system but is invisible to the
  other. CI catches it; local devs sometimes don't. Always grep both
  files at the same time when adding/removing a module
  [verified-by-code](source/src/test/modules/Makefile:7-58)
  [verified-by-code](source/src/test/modules/meson.build:3-60).
- **`installcheck-world` does not recurse.** The top-level
  `make installcheck-world` deliberately skips `src/test/modules/`
  [from-README](source/src/test/modules/README:11-14). Your test runs
  only via `make check` inside the module dir, or `meson test --suite
  test-modules`. Don't rely on `installcheck-world` for coverage.
- **`shared_preload_libraries` is the gate.** A test module that
  installs hooks in `_PG_init` runs nothing if the cluster started
  without it preloaded. From a `t/*.pl` use
  `$node->append_conf('postgresql.conf', "shared_preload_libraries =
  '<name>'")` *before* `$node->start`. From `sql/` set
  `shared_preload_libraries` via an `extra_install_extensions` /
  `extra.conf` pattern — see [verified-by-code](source/src/test/modules/injection_points/extra.conf).
- **EXTRA_INSTALL for cross-module deps.** If your TAP test installs
  `CREATE EXTENSION injection_points` alongside your own extension,
  the Makefile needs `EXTRA_INSTALL = src/test/modules/injection_points`
  [verified-by-code](source/src/test/modules/worker_spi/Makefile:9).
  Without it, `make check` builds your module but not the dep, and the
  TAP test fails on `CREATE EXTENSION`. Meson resolves this implicitly
  via the `test_install_libs` collector.
- **Conditional modules need BOTH branches.** A module gated on
  `enable_injection_points` must appear in `ALWAYS_SUBDIRS` for the
  *disabled* path so that `make distclean` / `make distprep` still
  recurses [verified-by-code](source/src/test/modules/Makefile:61-65).
  Forgetting `ALWAYS_SUBDIRS` leaves orphan build artifacts after a
  reconfigure.
- **Synchronization traps:**
  - `src/test/modules/Makefile` ↔ `src/test/modules/meson.build` —
    every add/remove touches both.
  - `<name>.control` `default_version` ↔ `<name>--<version>.sql`
    filename — must match exactly or `CREATE EXTENSION` fails with
    "extension <name> has no installation script for version".
  - `Makefile` `REGRESS = a b c` order ↔ files in `sql/` and
    `expected/` — `pg_regress` runs them in the listed order; missing
    a `.sql` aborts the suite, missing an `.out` reports
    "expected file not found".

## Verification (exact test invocations)

```bash
# Build everything (the new module compiles into dev/install-debug/lib/)
meson compile -C dev/build-debug

# Run just your new test module's full suite (regress + iso + TAP)
meson test -C dev/build-debug --suite test-modules --test <name>

# Run the entire test-modules suite to verify you didn't break siblings
meson test -C dev/build-debug --suite test-modules

# Autoconf equivalents (from the module dir)
cd dev/src/test/modules/<name>
make check                          # builds + runs regress + iso + TAP
make installcheck                   # against a running cluster

# Inspect output on failure
ls dev/build-debug/testrun/<name>/
cat dev/build-debug/testrun/<name>/<test>/log/regress_log_*
```

If your module is conditional, also verify the *disabled* path builds
cleanly:

```bash
meson configure -D injection_points=false dev/build-debug
meson compile -C dev/build-debug && meson test -C dev/build-debug --suite test-modules
```

## Cross-refs

- Companion skills: `.claude/skills/testing/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md` (for the `.control` /
  `--1.0.sql` shell).
- Related scenarios: `scenarios/add-new-extension.md` (the user-facing
  cousin — same skeleton, different install target),
  `scenarios/add-new-bgworker.md` (the most common *reason* to grow a
  new test module — `worker_spi` is the reference),
  `scenarios/add-new-hook.md` (a new core hook usually needs a
  test-module to demo + cover it).
- Idioms: `knowledge/idioms/process-utility-hook-chain.md` (the
  prev-hook chaining pattern test modules use),
  `knowledge/idioms/background-worker-startup.md` (lifecycle of the
  bgworker `worker_spi` exercises).
- Subsystems: per-file docs in `knowledge/files/src/test/modules/`
  (worker_spi, injection_points, delay_execution, test_parser) — read
  these to see the shape concretely.
- Reference patch (canonical_commit):
  `git -C source show 49cd2b93d7d` — *Add test module
  injection_points.* Also worth reading:
  `git -C source show 22dfd116a12` — *Move test modules from contrib
  to `src/test/modules`*, the historical split that gave this
  directory its identity.
