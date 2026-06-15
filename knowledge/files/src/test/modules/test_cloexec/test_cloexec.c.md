---
path: src/test/modules/test_cloexec/test_cloexec.c
anchor_sha: e18b0cb7344
loc: 240
depth: read
---

# src/test/modules/test_cloexec/test_cloexec.c

## Purpose

Standalone test program (not a backend extension) that verifies the
`O_CLOEXEC` flag on `open()` actually prevents handle inheritance on Windows.
The Unix kernel handles `FD_CLOEXEC` natively; on Windows PG synthesizes the
behavior in its `port/open.c` shim, so this test pins that down. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `main` | `test_cloexec.c:33` | Self-respawning test harness; on non-Windows it just prints "only runs on Windows" and exits 0 |
| `run_parent_tests` (static) | `:76` | Opens two test files, one with `O_CLOEXEC` and one without, spawns child |
| `run_child_tests` (static) | `:175` | Parses HANDLE values from argv and tries `WriteFile()` on each |
| `try_write_to_handle` (static) | `:219` | Returns true if the write succeeded |

## Internal landmarks

- The test is parent/child: parent opens `O_CLOEXEC` + non-`O_CLOEXEC` files
  and `CreateProcess(.. bInheritHandles=TRUE)` so all inheritable handles
  flow into the child via `_get_osfhandle()`.
- Child receives the two HANDLE values as `%p` hex strings (`:128`, `:184`)
  and tries to write to each; success on the `O_CLOEXEC` one is a test failure.
- Pass criterion: `!h1_worked && h2_worked` (`:207`).

## Invariants & gotchas

- **Windows-only.** The body is `#ifdef WIN32`; on Unix the test is a no-op.
- The handle is passed as a literal `%p` pointer in the command line — this
  only works because parent + child share the same address space rules for
  HANDLEs (Windows kernel objects, not pointers into the process).
- Test files are unlinked at the end (`:62-63`) but a crash mid-test leaves
  `test_cloexec_*_<pid>.tmp` in cwd.

## Cross-refs

- `source/src/port/open.c` — the Windows `open()` shim that implements
  `O_CLOEXEC` via `SetHandleInformation(.. HANDLE_FLAG_INHERIT=0)`.
- `source/src/include/port.h` — declares the portable `O_CLOEXEC` macro.
