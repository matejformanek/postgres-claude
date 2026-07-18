# `src/include/port/win32.h`

## Role

Top-level Windows shim — sets the WIN32 macro from `_WIN32`, pins
`_WIN32_WINNT` to Windows 10 minimum (0x0A00), avoids a header
collision between `<crtdefs.h>` and PG's `errcode()` function, and
defines `PGDLLIMPORT` / `PGDLLEXPORT` for the Windows DLL model
`[verified-by-code]` `source/src/include/port/win32.h:1-59`.

## Public API

- `WIN32` macro guaranteed defined if `_WIN32` is.
- `_WIN32_WINNT = 0x0A00` (Windows 10).
- `PGDLLIMPORT __declspec(dllexport)` if `BUILDING_DLL`, else
  `__declspec(dllimport)`; **frontend code uses no marking**
  `[verified-by-code]` `source/src/include/port/win32.h:43-49`.
- `PGDLLEXPORT __declspec(dllexport)` unconditionally
  `source/src/include/port/win32.h:51-59`.

## Invariants

1. `_WIN32_WINNT` is **forcibly redefined** even if already set —
   intentionally overrides any value lower than 0x0A00. Higher values
   are preserved by the order (`#ifdef ... #undef` then `#define
   0x0A00` `source/src/include/port/win32.h:16-20`). Wait: the
   pattern is `#ifdef _WIN32_WINNT / #undef _WIN32_WINNT / #endif /
   #define _WIN32_WINNT 0x0A00` which unconditionally pins to
   0x0A00. Comment at line 14 says "Leave a higher value in place"
   but the code doesn't — this is a comment/code discrepancy.
   `[verified-by-code]` `source/src/include/port/win32.h:13-20`.
2. The `errcode` collision dodge `#define errcode __msvc_errcode /
   #include <crtdefs.h> / #undef errcode` only triggers on MSVC or
   when `HAVE_CRTDEFS_H` is set; MinGW typically skips it
   `[verified-by-code]` `source/src/include/port/win32.h:23-31`.
3. **MinGW must also use `__declspec(dllexport)`** for PGDLLEXPORT —
   the comment notes that `visibility("default")` works only until
   any other symbol uses `__declspec(dllexport)`, after which all
   exports must be explicit `[from-comment]`
   `source/src/include/port/win32.h:53-58`.

## Trust-boundary / Phase D surface

- **`PGDLLIMPORT` discipline is load-bearing for the entire
  Windows-extension ABI.** Every `extern PGDLLIMPORT` declared
  variable that ships in a release becomes part of the stable ABI
  for that major version. Removing or renaming one breaks
  out-of-tree extensions. This is a known committer concern; this
  header just sets the macro.
- **`_WIN32_WINNT` pinned to 10 means Windows 7/8.1 are no longer
  supported.** This was a deliberate raise; older PG (≤ 15) used
  lower values. Building on Windows < 10 will fail.

## Cross-refs

- `source/src/include/port/cygwin.h` — parallel
  `PGDLLIMPORT`/`BUILDING_DLL` pattern for Cygwin.
- `source/src/include/port/win32_port.h` — the big Windows-port
  header included after this one.

## Issues

- **ISSUE-doc**: comment at line 14 says "Leave a higher value in
  place" but code unconditionally redefines `_WIN32_WINNT` to
  0x0A00, dropping any higher value the caller set. Either the
  comment or the code is wrong; the code looks intentional ("pin to
  10") but the comment implies "raise floor to 10". Mismatch.
  (severity: low, but worth a hf(corpus) ping if a real bug)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
