---
source_url: https://www.postgresql.org/docs/current/extend-pgxs.html
chapter: "38.18 Extension Building Infrastructure / PGXS (extend-pgxs)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# PGXS — building extensions against an installed server

PGXS is the make-based build glue that lets a contrib-style module compile
against an *installed* PG (no source tree needed). The meta-repo builds in
`dev/` with meson, but every third-party extension ships a PGXS Makefile.

## Non-obvious claims

- **The required boilerplate is three lines, always last in the Makefile:**

  ```make
  PG_CONFIG = pg_config
  PGXS := $(shell $(PG_CONFIG) --pgxs)
  include $(PGXS)
  ```

  `pg_config --pgxs` returns the absolute path to the global PGXS makefile;
  `PG_CONFIG` defaults to the first `pg_config` on `PATH` and is overridable on
  the command line to target a specific server. [from-docs extend-pgxs]
- **Exactly one of three "what to build" variables:** `MODULES` (multiple
  single-source `.so`s, list stems without suffix), `MODULE_big` (one `.so`
  from many sources listed in `OBJS`), or `PROGRAM` (an executable, objects in
  `OBJS`). [from-docs]
- **`MODULEDIR` decides the install subdir under `share/`:** defaults to
  `extension` when `EXTENSION` is set, else `contrib`. `DATA`/`DOCS` install to
  `share/$MODULEDIR` and `doc/$MODULEDIR`. [from-docs]
- **`EXTENSION` requires a matching `<name>.control` file** and installs it to
  `share/extension`. This is the bridge to
  [[knowledge/docs-distilled/extend-extensions.md]]. [from-docs]
- **`DATA_built` vs `HEADERS_built` differ on clean:** `DATA_built` IS removed
  by `make clean`; `HEADERS_built` is NOT (add it to `EXTRA_CLEAN` if you want
  it gone). A subtle, easy-to-miss asymmetry. [from-docs]
- **Test-input layout is fixed:** `REGRESS` scripts live in `sql/` (`.sql`),
  expected output in `expected/` (`.out`); `ISOLATION` specs in `specs/`
  (`.spec`), expected in `expected/`. `make installcheck` runs both and writes
  `regression.diffs` / `output_iso/regression.diffs`. `TAP_TESTS=1` enables
  TAP, results under `tmp_check/`. A missing expected file → test reported as
  "trouble". [from-docs]
- **Flag-injection direction matters:** `PG_CPPFLAGS` is *prepended* to
  `CPPFLAGS`; `PG_CFLAGS` is *appended* to `CFLAGS`; `PG_LDFLAGS` is
  *prepended* to `LDFLAGS`. `SHLIB_LINK` adds libs to a `MODULE_big` link line;
  `PG_LIBS` adds them to a `PROGRAM` link line. [from-docs]
- **Suppression knobs:** `NO_INSTALL` drops the `install` target (test-only
  modules); `NO_INSTALLCHECK` drops `installcheck` (tests needing special
  setup). [from-docs]
- **VPATH builds work** via `make -f /path/to/src/Makefile` or `make
  VPATH=/path/to/src`. [from-docs]
- **Custom `prefix=` is fixed up:** `make install prefix=/x` works, and if the
  prefix path lacks `postgres`/`pgsql`, `postgresql` is appended to the
  generated dir names — and the *server* then needs `extension_control_path` +
  `dynamic_library_path` GUCs pointed at the custom location to find the files.
  [from-docs]

## Links into corpus

- The control-file / version-script contract these installed files satisfy:
  [[knowledge/docs-distilled/extend-extensions.md]].
- The C entry points a `MODULE_big`/`MODULES` `.so` exposes:
  [[knowledge/docs-distilled/xfunc-c.md]].
- Test-flavor selection (regress vs isolation vs TAP) is the `testing` skill's
  domain; PGXS just wires the runners.

## Caveats / verification

- All claims `[from-docs extend-pgxs]`. The authoritative variable list lives
  in `src/makefiles/pgxs.mk` in the source tree (anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc`); the doc page is a curated
  subset. meson-based contrib builds in `dev/` use `meson.build` instead and
  don't exercise this path — PGXS matters for *external* extensions.
