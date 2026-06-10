# fe_memutils.h

Public header for the frontend palloc-shim implemented in
`src/common/fe_memutils.c` and the `psprintf.c` siblings.
(`source/src/include/common/fe_memutils.h`) [verified-by-code]

## Purpose

Declares the `pg_malloc`/`pg_strdup`/`pg_realloc` family and the
backend-named `palloc`/`palloc0`/`pstrdup`/`pfree`/`repalloc`
shims, plus the type-safe `pg_malloc_array`,
`pg_malloc_object` etc. macros. Lets shared FE/BE source compile
unchanged.

## Key declarations

- `MaxAllocSize = 0x3fffffff` (1 GB - 1) — defined for symmetry
  with the backend; **not enforced** in frontend allocators.
  (`fe_memutils.h:22`)
- `MCXT_ALLOC_HUGE` / `MCXT_ALLOC_NO_OOM` / `MCXT_ALLOC_ZERO`
  flag bits, named identically to the backend equivalents.
  `MCXT_ALLOC_HUGE` carries a "not actually used for frontends"
  comment. (`fe_memutils.h:28-31`)
- `pg_strdup`, `pg_malloc`, `pg_malloc0`, `pg_malloc_extended`,
  `pg_realloc`, `pg_free` — exit-on-OOM (except with
  `MCXT_ALLOC_NO_OOM`).
- `add_size`, `mul_size`, `pg_malloc_mul`, `pg_malloc0_mul`,
  `pg_malloc_mul_extended`, `pg_realloc_mul` — overflow-checked
  size arithmetic + allocator combos.
- `pg_malloc_object(type)`, `pg_malloc0_object(type)`,
  `pg_malloc_array(type, count)`, `pg_malloc0_array(type, count)`,
  `pg_malloc_array_extended(type, count, flags)`,
  `pg_realloc_array(p, type, count)` — type-safe casting macros.
  (`fe_memutils.h:61-75`)
- `pstrdup`, `pnstrdup`, `palloc`, `palloc0`, `palloc_extended`,
  `repalloc`, `pfree`, `palloc_mul`, `palloc0_mul`,
  `palloc_mul_extended`, `repalloc_mul` plus the matching
  `palloc_object` / `palloc_array` macros — backend-named.
- `psprintf`, `pvsnprintf` — `pg_attribute_printf` declarations for
  the helpers in `psprintf.c`. (`fe_memutils.h:98-99`)

## Phase D notes

## Issues

[ISSUE-secret-scrub: header advertises `pg_free` (`fe_memutils.h:42`)
but no `pg_free_secure` / `pg_explicit_bzero` equivalent (medium)]
A5's `common.md` SecretBuf-hosting-site cluster: every
secret-bearing buffer (passwords, SCRAM intermediates, GSSAPI
tokens) freed through this path uses raw `free()` semantics — the
heap retains the secret until reuse. Adding `pg_free_secure(ptr, len)`
here would make a callsite-by-callsite audit feasible.

[ISSUE-stale-todo: `MaxAllocSize` defined but not enforced
(`fe_memutils.h:14-22`) (low)] Backend enforces this in
`MemoryContextAlloc`; frontend silently allows arbitrary sizes up
to `SIZE_MAX/2` (the `add_size`/`mul_size` cap). The header comment
acknowledges this divergence but the macro looks authoritative.

[ISSUE-trust-boundary: `add_size` / `mul_size` (`fe_memutils.h:47-48`)
exit on overflow; this is good. BUT plain `pg_malloc(size)`
(`fe_memutils.h:38`) takes `size_t` and does NOT overflow-check —
callers computing `n * sizeof(T)` themselves can wrap (low)] The
type-safe `_array` macros mitigate this, but the raw signatures
remain.

[ISSUE-undocumented-invariant: every `pg_malloc*` exit(1)s on OOM
EXCEPT with `MCXT_ALLOC_NO_OOM`; the header documents this in a
comment block but the function signatures look normal-C-API (low)]

## Cross-refs

- A5 `common.md` — SecretBuf hosting-site cluster (free does not
  scrub).
- A6 `pg_upgrade` / `pg_rewind` — heavy frontend allocators.
- Companion: `src/common/fe_memutils.c.md`, `src/common/psprintf.c`.
