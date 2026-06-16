# plpython_system.h

Covers `source/src/pl/plpython/plpython_system.h` (55 LOC). Sibling: `plpython.h.md`.

Source pin: `4b0bf0788b0`.

## One-line summary

The narrow wrapper that actually does `#include <Python.h>`, isolated so the `system_header` pragma's scope is precisely controlled. Also hosts the MSVC `_DEBUG` and `errcode` collision shims.

## Public API / entry points

None — pure preprocessor. Side effects:

- `#define HAVE_SNPRINTF 1` before `Python.h` — prevents Python ≤ 3.8 from providing its own snprintf replacement, which would cause macro redefinition warnings [verified-by-code: `source/src/pl/plpython/plpython_system.h:30-34`].
- `#pragma GCC system_header` (if `HAVE_PRAGMA_GCC_SYSTEM_HEADER`) — suppresses warnings from Python headers under PG's strict flags (notably `-Wdeclaration-after-statement`) [verified-by-code: `source/src/pl/plpython/plpython_system.h:26-28`, from-comment :20-25].
- On MSVC: temporarily `#undef _DEBUG` around `Python.h` so Python doesn't pull in a debug-only `python3X_d.lib` we don't ship [verified-by-code: `source/src/pl/plpython/plpython_system.h:36-46`].
- On MSVC: `#define errcode __msvc_errcode` around `Python.h` so Python's `errcode` symbol doesn't collide with PG's `errcode()` macro from `elog.h` [verified-by-code: `source/src/pl/plpython/plpython_system.h:42-50`].

## Key invariants

- **No PG-specific declarations may be added here** — explicit in the file-level comment: "No Postgres-specific declarations should be put here" [from-comment: `source/src/pl/plpython/plpython_system.h:7-8`]. The whole point is to scope `#pragma GCC system_header` tightly to Python's headers only.

## Notable internals

- The `errcode` macro dance is one of the oldest cross-language friction points in the plpython source: PG's `elog.h` defines `errcode(ERRCODE_FOO)` as a macro that builds ereport components, and Python.h has a function/macro named `errcode` (Windows error code). Because plpython.h forces `postgres.h` before `Python.h`, PG's `errcode` macro is already defined when Python.h tries to declare its own — without the rename trick, Python.h's tokens would expand using PG's macro and break the build [inferred from comment `source/src/pl/plpython/plpython_system.h:42-43` and the surrounding `#define errcode __msvc_errcode`].

- `_DEBUG` is unset on MSVC debug builds because Python's MSVC build uses `#pragma comment(lib, ...)` to auto-link `python3X_d.lib` when `_DEBUG` is defined, and that debug library isn't normally installed alongside the release library [from-comment: `source/src/pl/plpython/plpython_system.h:37-40`].

## Trust posture

N/A — see `plpython.h.md` for the language-wide trust posture.

## Cross-references

- `plpython.h.md` — the canonical entry header that includes this one.
- `source/src/include/utils/elog.h` — defines the colliding `errcode()` macro on the PG side.

<!-- issues:auto:begin -->
- [Issue register — `plpython`](../../../../issues/plpython.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-documentation: `system_header` pragma only fires on GCC/clang, not MSVC (nit)] — `#pragma GCC system_header` is guarded by `HAVE_PRAGMA_GCC_SYSTEM_HEADER`; on MSVC, Python header warnings are not suppressed [verified-by-code: `source/src/pl/plpython/plpython_system.h:26-28`]. Not a bug, but a portability quirk: MSVC plpython builds may emit warnings other compilers suppress. PG's MSVC support is in maintenance mode, so this is unlikely to matter in practice.
