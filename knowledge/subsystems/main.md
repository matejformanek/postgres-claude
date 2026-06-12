# main (process startup dispatch)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Bruce Momjian (2), Tom Lane (2), Peter Eisentraut (2), Jeff Davis (1)
- **Top reviewers (last 24mo):** Peter Eisentraut (3), Heikki Linnakangas (1), Greg Sabino Mullane (1), Álvaro Herrera (1)
- **Recent landmark commits (12mo):**
  - `5e6e42e44fe (Jeff Davis, 2025-07-16): Force LC_COLLATE to C in postmaster.`
  - `d4baa327a1c (Tom Lane, 2025-11-05): Avoid possible crash within libsanitizer.`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/main/`
- **Header path:** none of its own (uses miscadmin.h, postmaster.h, etc.)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **README anchor:** none

## 1. Purpose

Just `main.c` — the C `main()` for *every* incarnation of the postgres
binary (postmaster, single-user backend, bootstrap, fork-exec child,
`--check`, `--describe-config`). Does the common startup hacks
(platform init, locale, root check) and then dispatches by first
argv to one of the `FooMain()` routines that own the real lifecycle
([from-comment] `main.c:1-19`).

## 2. Mental model

- **One binary, six modes.** Dispatch is by `argv[1]` matching
  `DispatchOptionNames[]` ([verified-by-code] `main.c:48-56`):
  - `--check` → `BootstrapModeMain(argc, argv, true)`
  - `--boot` → `BootstrapModeMain(argc, argv, false)`
  - `--forkchild` → `SubPostmasterMain` (only under `EXEC_BACKEND`)
  - `--describe-config` → `GucInfoMain`
  - `--single` → `PostgresSingleUserMain`
  - anything else / no arg → `PostmasterMain` (the normal server)
- **None of these return.** `main()` ends with `abort()` after the
  switch — every `FooMain` either `exit()`s or `proc_exit()`s
  ([verified-by-code] `main.c:236`).
- **Order of startup is rigid.** Stack-base set → locale → root check
  → dispatch. Comments at each step explain *why* each thing must
  happen before the next ([from-comment] `main.c:78-159`).

## 3. Key files

- `main.c` (~17 KB) — only file in the subdir. Top comment is
  `main.c:1-19`; dispatch switch `main.c:208-233`; help text
  `main.c:386-442`.

## 4. Key data structures

- **`DispatchOption` enum** (in `miscadmin.h`, used here) — indices
  into `DispatchOptionNames[]`.
- **`progname`** (`main.c:44`) — globally-visible `const char *`
  for ps display + error messages.

## 5. Control flow — `main()` step by step

1. `reached_main = true` (used by `__ubsan_default_options` at the
   bottom — sanitizer-init paranoia, `main.c:486-520`).
2. `pgwin32_install_crashdump_handler()` (Windows only).
3. `progname = get_progname(argv[0])`.
4. `startup_hacks(progname)` — Win32-only stuff: `WSAStartup`,
   `_set_abort_behavior`, `SetErrorMode` so abort() makes a dump and
   errors go to stderr instead of popups ([from-comment]
   `main.c:272-358`).
5. `argv = save_ps_display_args(argc, argv)` — must be early because
   some platforms need argv-overwrite to set the process title
   ([from-comment] `main.c:94-103`).
6. `MyProcPid = getpid(); MemoryContextInit();` — first point where
   `elog/ereport` becomes legal ([from-comment] `main.c:106-114`).
7. `set_stack_base()` — for `check_stack_depth()`.
8. Locale: `LC_COLLATE=C` always; `LC_CTYPE` from env; `LC_MESSAGES`
   from env; `LC_MONETARY/NUMERIC/TIME=C` always ([verified-by-code]
   `main.c:125-152`). Then `unsetenv("LC_ALL")`.
9. Handle `--help` / `--version` early (before root check)
   ([verified-by-code] `main.c:165-176`).
10. `do_check_root` exempted for `--describe-config` and `-C var`
    (used by `pg_ctl` on Windows where it may still be admin)
    ([from-comment] `main.c:178-192`).
11. `check_root(progname)` — refuses to run as `root` (Unix) or
    Administrator (Windows). Also enforces real-uid == effective-uid
    ([verified-by-code] `main.c:446-484`).
12. `parse_dispatch_option(&argv[1][2])` if `argv[1]` begins with
    `--`. `--forkchild` matches by prefix (it carries an argument);
    others by exact strcmp ([verified-by-code] `main.c:243-270`).
13. Dispatch switch (§2 above). `abort()` after.

## 6. Locking and invariants

- `MemoryContextInit()` must precede any allocation or
  `ereport`. The comment is explicit ([from-comment] `main.c:106-114`).
- `save_ps_display_args` must precede any `getenv()` you intend to
  hold a pointer from ([from-comment] `main.c:94-103`).
- Locale setup is *partially* finalized here — `LC_MESSAGES` is set
  again later from GUCs ([from-comment] `main.c:141-147`). Don't
  rely on backend-style localization in this file.
- Refusing to run as root is policy, not a bug; intentionally never
  optional except for the read-only `--describe-config` and `-C`
  modes ([from-comment] `main.c:178-192`).
- `__ubsan_default_options` is built with
  `disable_sanitizer_instrumentation` attribute to avoid recursive
  re-entry from the sanitizer's own getenv probe
  ([from-comment] `main.c:486-512`).

## 7. Interactions with other subsystems

- **postmaster/** — `PostmasterMain` is the normal path.
- **bootstrap/** — `BootstrapModeMain` (initdb's worker).
- **tcop/** — `PostgresSingleUserMain` (`--single` mode), `GucInfoMain`.
- **utils/misc/ps_status.c** — `save_ps_display_args`.
- **utils/mmgr/mcxt.c** — `MemoryContextInit`.
- **utils/pg_locale.c** — `pg_perm_setlocale`,
  `set_pglocale_pgservice`.

## 8. Tests

None directly; every regression run exercises `main.c` implicitly.
`--check` and `--single` are exercised by `initdb` and PostgresNode
TAP infra.

## 9. Open questions / unverified claims

- The `_CrtSetReportMode` paragraph for DEBUG MSVC builds is from a
  comment; not validated against current MSVC behavior
  ([from-comment] `main.c:343-355`).

## 10. Glossary

- **DISPATCH_*** — enum values mapping argv strings to the right
  `FooMain` routine.
- **Single-user mode** — `--single`, a backend that owns its own
  stdin/stdout; used by `initdb` and emergency repair.
- **`EXEC_BACKEND`** — opt-in compile flag that re-`exec()`s instead
  of relying on fork-inheritance; required on Windows.
- **fork/exec child** — under `EXEC_BACKEND`, the child runs
  `main()` again with `--forkchild …`, which dispatches to
  `SubPostmasterMain`.
