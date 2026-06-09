# `utils/injection_point.h` — INJECTION_POINT() macro for in-tree testability

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/injection_point.h`)

## Role

Build-flag-gated mechanism for placing labelled "hooks" in core backend
code that tests can attach callback functions to (e.g. "stall here",
"wait for signal", "inject an error"). Compiled to a NO-OP unless
`--enable-injection-points` is configured. Used heavily by isolation
tests for replication, recovery, and concurrency races.

## Public API

- `InjectionPointData { name, library, function }` —
  `source/src/include/utils/injection_point.h:20-25`.
- Macros gated on `USE_INJECTION_POINTS`:
  - `INJECTION_POINT_LOAD(name)` — `:31, 36`.
  - `INJECTION_POINT(name, arg)` — `:32, 37`.
  - `INJECTION_POINT_CACHED(name, arg)` — `:33, 38`.
  - `IS_INJECTION_POINT_ATTACHED(name)` — `:34, 39`.
  When `USE_INJECTION_POINTS` is undefined, all become `((void) name)`.
- `InjectionPointCallback (name, private_data, arg)` typedef — `:45-47`.
- `InjectionPointAttach(name, library, function, private_data,
  private_data_size)` — `:49-53`. Loads a callback via dlopen of `library`.
- `InjectionPointLoad / Run / Cached / IsAttached / Detach / List` —
  `:54-61`.
- `EXEC_BACKEND` only: `extern PGDLLIMPORT struct InjectionPointsCtl
  *ActiveInjectionPoints` — `:63-65`.

## Invariants

- All injection-point machinery is compiled out unless
  `USE_INJECTION_POINTS` is defined at build time.
  [verified-by-code, `:30-40`]
- The no-op fallback is `((void) name)` — a cast of the literal name
  string to void, which suppresses unused-variable warnings without
  emitting code. [verified-by-code, `:36-39`]
- `InjectionPointAttach` takes a `library` and `function` name pair —
  the library is `dlopen`'d (or equivalent), the function is looked up,
  and that pointer becomes the callback. [inferred from signature, `:49-53`]
- `private_data` is copied (size given) into shmem so any backend that
  triggers the named point can find it. [inferred from API + EXEC_BACKEND
  shmem variable]

## Notable internals

The macro form `INJECTION_POINT(name, arg)` is designed for sprinkling
through hot code with negligible cost when disabled — the literal name
string is just a token cast away.

## Trust-boundary / Phase D surface

- **Critical**: build flag `USE_INJECTION_POINTS` enables the entire
  machinery. A production build with the flag accidentally on becomes
  a **dlopen-anything backdoor**: `InjectionPointAttach("foo",
  "/path/to/anything.so", "anyfunc", ...)` will dlopen and call into an
  arbitrary library. This is by design for test builds and explicitly
  meant to be off in production. [ISSUE-dlopen: USE_INJECTION_POINTS=on
  in a production binary is effectively an arbitrary-dlopen surface
  (confirmed; release-builds intentionally compile this out)]
- `InjectionPointAttach` permission model — header doesn't show a
  privilege check. The .c file restricts to superuser; the header gives
  no hint of that contract. [ISSUE-documentation: superuser requirement
  for InjectionPointAttach not visible at header level (likely)]
- Even within a test build, an attached injection point persists in
  shmem across sessions (per `ActiveInjectionPoints`). A test that
  attaches and doesn't detach leaves the point active for any later
  backend hitting that path. [ISSUE-correctness: attached points
  outlive the test that attached them; cleanup is caller's
  responsibility (maybe)]
- `library` and `function` names are stored as bare strings in shmem.
  The dlopen happens lazily on first hit, in the target backend.
  [ISSUE-api-shape: deferred-dlopen makes failures appear far from
  the attach call (nit)]
- The macro hides whether a given source-line is "instrumented for
  testing" vs production. A code reviewer scanning for "what runs on
  master" must know to grep for `INJECTION_POINT(`. [ISSUE-audit-gap:
  injection points are invisible to non-grep code review (nit)]

## Cross-refs

- `source/src/backend/utils/misc/injection_point.c` — implementation.
- `source/src/test/modules/injection_points/` — test module that
  registers callbacks.
- `knowledge/idioms/debugging.md` — operational use of injection points
  during backend debugging.

## Issues

1. [ISSUE-dlopen: a production build with `USE_INJECTION_POINTS` on is
   an arbitrary-dlopen + arbitrary-symbol-execute surface (confirmed)]
   — `source/src/include/utils/injection_point.h:30,49`.
2. [ISSUE-documentation: superuser requirement for `InjectionPointAttach`
   not declared at header level (likely)] —
   `source/src/include/utils/injection_point.h:49`.
3. [ISSUE-correctness: attached injection points outlive the test that
   attached them; cleanup is caller-only (maybe)] —
   `source/src/include/utils/injection_point.h:49`.
4. [ISSUE-api-shape: deferred dlopen at first hit hides attach-time
   failures (nit)] —
   `source/src/include/utils/injection_point.h:49`.
5. [ISSUE-audit-gap: injection points are silent to code review unless
   grepped (nit)] —
   `source/src/include/utils/injection_point.h:32`.
