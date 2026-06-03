# fe_memutils.c

Frontend palloc-shim: provides `pg_malloc`/`pg_realloc`/`pg_strdup`
and the backend-compatible `palloc`/`palloc0`/`pfree`/`pstrdup`
names so that source files shared between backend and frontend
compile unchanged. OOM is fatal: the helpers print
`"out of memory\n"` to stderr and `exit(EXIT_FAILURE)`, rather than
returning NULL. [verified-by-code]

Guarded by `#ifndef FRONTEND #error` at the top — never linked into
the backend. [verified-by-code]
(`source/src/common/fe_memutils.c:16-18`)

## Purpose

Make frontend tools (psql, pg_dump, initdb, pg_basebackup, …) able
to share C with backend code that calls `palloc`/`pstrdup`. Also
gives frontend code a simple "exit on OOM" allocator family so
every caller doesn't repeat the NULL check.

## Key functions

- `pg_malloc_internal(size, flags)` — static workhorse. `size == 0`
  is rewritten to `1` to dodge unportable `malloc(0)`. Honours
  `MCXT_ALLOC_NO_OOM` (return NULL instead of exiting) and
  `MCXT_ALLOC_ZERO` (memset the buffer).
  (`source/src/common/fe_memutils.c:28-50`) [verified-by-code]
- `pg_malloc`, `pg_malloc0`, `pg_malloc_extended` — public wrappers
  passing the corresponding flags.
  (`source/src/common/fe_memutils.c:52-68`)
- `pg_realloc` — `realloc(NULL, 0)` rewritten to `size = 1` for
  the same portability reason. OOM exits.
  (`source/src/common/fe_memutils.c:70-85`)
- `pg_strdup` — NULL input is a fatal internal error
  (`"cannot duplicate null pointer"`); OOM exits.
  (`source/src/common/fe_memutils.c:90-108`)
- `pg_free` — plain `free()`. **No zeroing.**
  (`source/src/common/fe_memutils.c:110-114`)
- `palloc` / `palloc0` / `palloc_extended` / `pfree` / `pstrdup` /
  `pnstrdup` / `repalloc` — backend-name shims forwarding to the
  `pg_*` family. `pnstrdup` uses `strnlen(in, size)` to cap and then
  `malloc(len+1)`. (`source/src/common/fe_memutils.c:120-181`)
- `add_size` / `mul_size` — overflow-checked size arithmetic, with
  `pg_noreturn` error helpers. Reject results above `SIZE_MAX/2` to
  match the backend's allocation-size convention.
  (`source/src/common/fe_memutils.c:195-231`)
- `pg_malloc_mul`, `pg_malloc0_mul`, `pg_malloc_mul_extended`,
  `pg_realloc_mul`, `palloc_mul`, `palloc0_mul`,
  `palloc_mul_extended`, `repalloc_mul` — `mul_size()` inlined for
  perf, then call the matching allocator.
  (`source/src/common/fe_memutils.c:237-363`)

## State / globals

None — the module is pure wrappers around libc malloc/free.

## Phase D notes

[ISSUE-secret-scrub: pg_free()/pfree() do NOT zero memory before
release; no helper exists for secret-bearing buffers (maybe)]
`pg_free` is `free(ptr)` verbatim
(`source/src/common/fe_memutils.c:110-114`) [verified-by-code].
Frontend tools that allocate password/secret strings (via
`simple_prompt`, `pg_strdup` of a connection-string fragment, etc.)
have no in-tree helper that does `explicit_bzero(ptr, len)` before
freeing — every caller must remember and many don't. Compare with
`src/common/string.c:explicit_bzero` and the
`src/include/utils/memutils.h` backend helpers. This compounds the
A4 finding around `simple_prompt`: the caller of `pg_strdup`'d
secret strings has no library-level scrub path.

[ISSUE-secret-scrub: pg_strdup of a secret leaves the source copy
untouched (maybe)] By design (it's `strdup`), but worth flagging:
when a tool does `password = pg_strdup(parsed_field);`, both
buffers now hold the secret and both need scrubbing.

[ISSUE-stale-todo: `MCXT_ALLOC_HUGE` flag defined but "not actually
used for frontends" per `fe_memutils.h:28-29` (low)]
`pg_malloc_internal` accepts the flag and silently ignores it. If a
shared backend file passes it through, no allocation cap is
enforced — `MaxAllocSize` is documented but not enforced
(`fe_memutils.h:14-22`) [verified-by-code].

## Potential issues

- `pnstrdup` on NULL is a fatal internal error
  (`fe_memutils.c:156-161`); backend `pnstrdup` has the same
  contract, so callers shared across FE/BE are safe.
- `add_size_error`/`mul_size_error` echo the requested sizes to
  stderr, which is fine in a tool but would be a small info leak in
  a server context (not applicable here — file is frontend-only).
