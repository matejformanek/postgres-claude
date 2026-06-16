# `src/include/pg_trace.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~17
- **Source:** `source/src/include/pg_trace.h`

The DTrace probe-macro trampoline. This entire file is one
`#include "utils/probes.h"` — the real probe macros (and the
`TRACE_POSTGRESQL_*` family) live in that header, which is
generated from `src/backend/utils/probes.d` at build time when PG
is configured with `--enable-dtrace`. [verified-by-code]

## API / declarations

```c
#include "utils/probes.h"		/* IWYU pragma: export */
```

That's the entire file body. The IWYU `export` pragma ensures that
including `pg_trace.h` transitively makes the probes.h symbols
visible without IWYU stripping the include.

## Notable invariants / details

- `utils/probes.h` is **generated** — if not built with
  `--enable-dtrace`, it's a stub that expands every probe to a no-op
  macro. So source files can sprinkle
  `TRACE_POSTGRESQL_LWLOCK_ACQUIRE(...)` unconditionally without
  worrying about `#ifdef ENABLE_DTRACE`. [inferred from build
  conventions]
- The actual probe-points are defined in `src/backend/utils/probes.d`.
  Adding a probe means editing that .d file and bumping the build
  to regenerate `probes.h`. There is no in-tree process to
  audit the active set of probes.
- DTrace is supported on Solaris and on macOS (in older versions);
  on Linux, the dtrace-compatibility shim uses SystemTap markers.

## Potential issues

- `pg_trace.h:15` — single-include indirection layer; if a future
  cleanup eliminates `utils/probes.h` (or renames the generator),
  every `#include "pg_trace.h"` user breaks. [ISSUE-stale-todo:
  pg_trace.h is a one-line stub; consider direct include of
  probes.h or merging (nit)]
- The probe set is unaudited at the header level — extensions
  using probes can collide with future PG probes. [ISSUE-api-shape:
  no probe-name namespace allocation (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->
