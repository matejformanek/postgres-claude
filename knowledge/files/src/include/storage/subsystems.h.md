# `src/include/storage/subsystems.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~31
- **Source:** `source/src/include/storage/subsystems.h`

Two-line trick header that turns `subsystemlist.h` into
`extern const ShmemCallbacks ...;` forward declarations for every
built-in subsystem callback symbol. Pair this with
`subsystemlist.h` to drive the actual `RegisterShmemCallbacks` calls
in `ipci.c:RegisterBuiltinShmemCallbacks`. PG18-era addition.
[verified-by-code] [from-comment]

## API / declarations

The entire body is:

```c
#define PG_SHMEM_SUBSYSTEM(callbacks) \
    extern const ShmemCallbacks callbacks;
#include "storage/subsystemlist.h"
#undef PG_SHMEM_SUBSYSTEM
```

Each line of `subsystemlist.h` expands to an `extern const
ShmemCallbacks <name>;` declaration. The actual definitions live in
the implementing subsystem's `.c` file (e.g. `LWLockCallbacks` in
`src/backend/storage/lmgr/lwlock.c`, `BufferManagerShmemCallbacks` in
`src/backend/storage/buffer/buf_init.c`, etc.). [verified-by-code]
[inferred]

## Notable invariants / details

- Including this header is how `RegisterBuiltinShmemCallbacks` in
  `ipci.c` knows the callback symbol exists at link time. Without
  this declarations file, every subsystem would either need its own
  individual `extern` in `ipci.c` (the pre-PG18 pattern) or every
  subsystem's main header would have to be pulled in. [from-comment]
- The `#undef` at the end is critical — `subsystemlist.h` is included
  multiple times in one TU (e.g. in `ipci.c` it's used once for
  declarations via this header and once for registration), so the
  macro must be re-definable. [verified-by-code]
- The header includes only `storage/shmem.h` (for `ShmemCallbacks`),
  keeping it cheap to pull in. [verified-by-code]

## Potential issues

- The header has zero error-checking — a typo in `subsystemlist.h`
  (`PG_SHMEM_SUBSYSTEM(BugferManagerShmemCallbacks)`) becomes an
  unresolved extern at link time, with no friendlier message.
  [verified-by-code]
  [ISSUE-api-shape: registration-vs-declaration name mismatches
  surface only as link errors; a `StaticAssertDecl` per symbol could
  give a clearer error (nit) — same root cause as the corresponding
  issue tagged on `subsystemlist.h`]
- The header is so trivial that future "cleanup" PRs might be
  tempted to inline it into `ipci.c`. That would be a regression:
  the split exists explicitly so the same list (in
  `subsystemlist.h`) is reusable by "automatic tools" per the head
  comment of `subsystemlist.h`. [inferred]
  [ISSUE-style: header is intentionally minimal; future cleanup
  pressure may be a footgun (nit)]
