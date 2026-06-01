# 2026-06-01 — build-and-run slash commands + verification

## Goal

Author six slash commands (`setup-pg`, `pg-start`, `pg-stop`, `pg-restart`,
`pg-test`, `pg-psql`) and verify each underlying command actually executes
against the upstream PG clone at `source/` (symlink to `../postgresql`).

## What I ran (order + outcome)

1. `meson setup source/build-debug source --buildtype=debug -Dcassert=true -Ddebug=true -Dprefix=$PWD/source/install-debug`
   - Succeeded. clang 21, icu4c 78.3 via Homebrew, bison 3.8.2 from `/opt/homebrew/opt/bison/bin/bison`.
   - Optional deps absent (configure still happy): dtrace, gss, libnuma, liburing, llvm, selinux, systemd, uuid.
2. `ninja -C source/build-debug` — **15s wall** on M-series (91s user, 50s sys, 9.4x parallelism). 1913 targets.
3. `ninja -C source/build-debug install` — fine, installed under `source/install-debug/`.
4. `initdb -D source/data-debug --locale=C --encoding=UTF8` — fine. Default tz picked Europe/Prague (host setting). trust auth warning, expected.
5. `pg_ctl -D source/data-debug -l server.log start` — fine.
6. `psql -h /tmp -d postgres -c 'SELECT version();'` →
   `PostgreSQL 19devel on aarch64-darwin, compiled by clang-21.0.0, 64-bit`.
7. `SHOW unix_socket_directories;` → `/tmp` (confirms `psql -h /tmp` is the correct dev invocation on macOS).
8. `pg_ctl stop -m fast` — fine.
9. `meson test --suite regress --num-processes 4` → **FAILED** in 1.56s with
   `# copying of initdb template failed` / `tmp_install/initdb-template: No such file`.
   Root cause: PG's meson layout has a separate `setup` suite (`tmp_install`,
   `install_test_files`, `initdb_cache`) that the regress test depends on but
   isn't auto-pulled when you filter by `--suite`. Fix:
   `meson test --suite setup --suite regress --num-processes 4` →
   **OK, 245 subtests passed in 33.92s** (plus ~7s of setup).

## What I had to fix

- **`postgresql/.git/info/exclude`**: appended `/data-debug/`, `/build-debug/`,
  `/install-debug/` so upstream's `git status` stays clean. Upstream's tracked
  `.gitignore` only covers `build*/` `install*/` patterns implicitly via
  `tmp_install/` style — verified via grep, the `build*/` `install*/` patterns
  ARE there (`*.so` etc are global; root-level dirs need explicit entries which
  I added locally).
- **`build-and-run/SKILL.md`** — fixed the "Running the regression tests"
  section: the previous `meson test -C source/build-debug regress` invocation
  is broken without `--suite setup`. Updated to
  `meson test -C source/build-debug --suite setup --suite regress --num-processes 4`
  with a Gotcha block explaining why.

## Files written

- `.claude/commands/setup-pg.md`
- `.claude/commands/pg-start.md`
- `.claude/commands/pg-stop.md`
- `.claude/commands/pg-restart.md`
- `.claude/commands/pg-test.md`
- `.claude/commands/pg-psql.md`

## Gotchas worth surfacing

1. **macOS bison is too old**; Homebrew bison is on a non-default PATH
   (`/opt/homebrew/opt/bison/bin`). meson found it via pkg search this time
   but a fresh shell might miss it.
2. **Socket dir is `/tmp` on macOS** but Linux libpq defaults differ — always
   pass `-h /tmp` explicitly when scripting.
3. **The symlink trick** means meson writes the build dir into the upstream
   clone. Upstream tracked `.gitignore` doesn't list `/data-debug/`, so I
   added it to `.git/info/exclude` (not the tracked file).
