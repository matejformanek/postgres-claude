# `src/include/utils/palloc.h`

- **File:** `source/src/include/utils/palloc.h` (168 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The minimal universal memory-allocation API. Pulled in directly by
`postgres.h`, so its declarations are visible in **every** backend TU
(and a few frontend programs like `pg_controldata` that include
`postgres.h`). Header comment is explicit: "Keep it lean!"
(`palloc.h:1-9` [from-comment]). Everything that doesn't need to be
ubiquitous lives in `memutils.h` instead.

Provides:
- The opaque `MemoryContext` typedef + `MemoryContextCallback` struct.
- `CurrentMemoryContext` extern + the `MemoryContextSwitchTo` inline.
- The `palloc*` / `MemoryContextAlloc*` / `pfree` / `repalloc*` family.
- Reset-callback registration.
- `MemoryContextStrdup` / `pstrdup` / `pnstrdup` / `pchomp` / `psprintf`.

## Public surface

### Types (`palloc.h:31-52`)

- `MemoryContext = struct MemoryContextData *` (`:36`). Full struct lives
  in `nodes/memnodes.h`; this header keeps it abstract intentionally
  (`palloc.h:31-35` [from-comment]).
- `MemoryContextCallbackFunction = void (*)(void *arg)` (`:45`).
- `MemoryContextCallback { func, arg, next }` (`:47-52`) — linked-list
  node. Comment recommends allocating the callback **inside the context
  it's registered on**, so reset/delete frees it implicitly
  (`palloc.h:38-44` [from-comment]).

### Globals (`palloc.h:54-59`)

- `CurrentMemoryContext` — default sink for `palloc()`. Comment: "Avoid
  accessing it directly! Use `MemoryContextSwitchTo()` to change the
  setting" (`palloc.h:54-58` [from-comment]).

### Flags for `MemoryContextAllocExtended` (`palloc.h:61-66`)

- `MCXT_ALLOC_HUGE` (`0x01`) — allow > `MaxAllocSize`.
- `MCXT_ALLOC_NO_OOM` (`0x02`) — return NULL instead of `ereport(ERROR)`
  on failure.
- `MCXT_ALLOC_ZERO` (`0x04`) — zero the result.

Consumed by `MemoryContextAllocationFailure` (`mcxt.c:1200-1214`) to
decide between `ereport(ERROR)` and silent-NULL.

### Core allocators (`palloc.h:68-86`)

- `MemoryContextAlloc(context, size)` — no flags, fail with ERROR.
- `MemoryContextAllocZero(context, size)` — zeroed.
- `MemoryContextAllocExtended(context, size, flags)` — flag-driven.
- `MemoryContextAllocAligned(context, size, alignto, flags)` — uses the
  redirection-chunk mechanism (`MCTX_ALIGNED_REDIRECT_ID`) implemented
  in `mcxt.c:1485-1591`.
- `palloc`, `palloc0`, `palloc_extended`, `palloc_aligned` — same four
  variants but targeting `CurrentMemoryContext` (`:78-81`).
- `repalloc`, `repalloc_extended`, `repalloc0`, `pfree` (`:82-86`).
  All `repalloc*` are `pg_nodiscard` so the compiler warns if the
  caller drops the new pointer (`palloc.h:82-85` [verified-by-code]).
- `repalloc0(p, oldsize, size)` is grow-and-zero; not safe for shrink
  (`mcxt.c:1707-1719` [from-comment, in mcxt.c]).

### Size-safe arithmetic (`palloc.h:88-98`)

- `add_size(s1, s2)` / `mul_size(s1, s2)` — `ereport(ERROR)` on overflow.
- `palloc_mul`, `palloc0_mul`, `palloc_mul_extended`, `repalloc_mul`,
  `repalloc_mul_extended` — combine the multiplication with the
  allocation, so the typical `palloc(n * sizeof(T))` overflow trap is
  closed at the API level.

### Typed-allocation macros (`palloc.h:100-123`)

- `palloc_object(type)` / `palloc0_object(type)` — `(type *)
  palloc(sizeof(type))` shape, both type-cast and zero-fill variants.
- `palloc_array(type, count)` / `palloc0_array(type, count)` /
  `palloc_array_extended(type, count, flags)` — use `palloc_mul`
  internally so overflow can't sneak through.
- `repalloc_array`, `repalloc0_array`, `repalloc_array_extended` —
  same idiom for resize. `repalloc0_array(p, T, oldcount, count)`
  resizes and zero-fills the *added* portion.

### Huge allocators (`palloc.h:125-127`)

- `MemoryContextAllocHuge(context, size)` — bypasses `MaxAllocSize`,
  bounded only by `MaxAllocHugeSize = SIZE_MAX / 2`
  (`memutils.h:44-45`).
- `repalloc_huge(p, size)` — `pg_nodiscard`.

### `MemoryContextSwitchTo` inline (`palloc.h:129-145`)

```c
#ifndef FRONTEND
static inline MemoryContext
MemoryContextSwitchTo(MemoryContext context)
{
    MemoryContext old = CurrentMemoryContext;
    CurrentMemoryContext = context;
    return old;
}
#endif
```

Hidden behind `#ifndef FRONTEND` because some compilers can't elide
unused inlines in frontend builds that include `postgres.h`
(`palloc.h:129-134` [from-comment]).

Idiomatic usage: save `old = MemoryContextSwitchTo(target)`, do work,
`MemoryContextSwitchTo(old)`. See `knowledge/idioms/memory-contexts.md`.

### Reset/delete callbacks (`palloc.h:147-151`)

- `MemoryContextRegisterResetCallback(context, cb)` — push.
- `MemoryContextUnregisterResetCallback(context, cb)` — early-remove.

Callbacks fire in **reverse-registration order** at reset or delete,
are popped before invocation (so a throwing callback won't re-fire),
and child callbacks run before parent callbacks (`mcxt.c:636-651, 533`
[verified-by-code]).

### String helpers (`palloc.h:153-165`)

- `MemoryContextStrdup(context, string)` — strdup into specific context.
- `pstrdup(in)` — strdup into `CurrentMemoryContext`.
- `pnstrdup(in, len)` — at-most-len bytes + NUL.
- `pchomp(in)` — strip one trailing newline if present.
- `psprintf(fmt, ...)` — sprintf into a freshly-allocated palloc'd
  buffer; implemented in `psprintf.c` (`:163-165` [from-comment]).
- `pvsnprintf(buf, len, fmt, args)` — return-true-if-fit variant.

## Key invariants

- **palloc never returns NULL** unless `MCXT_ALLOC_NO_OOM` is set.
  Failure goes through `MemoryContextAllocationFailure` →
  `ereport(ERROR)`. Asserted in `palloc`/`palloc0` post-conditions
  (`mcxt.c:1413, 1433` [verified-by-code]).
- **`pfree(p)` and `repalloc(p, …)` are context-independent**: dispatch
  reads the `MemoryContextMethodID` out of the chunk header, not from
  `CurrentMemoryContext` (`mcxt.c:1619-1659` [verified-by-code]). So
  you can free in a different context than the one that allocated.
- **palloc is forbidden in a critical section** unless the destination
  context has `allowInCritSection = true`. `ErrorContext` is the only
  default opt-in (`mcxt.c:198-199, 397` [verified-by-code]).
- **`repalloc*` return values must not be discarded** — enforced by
  `pg_nodiscard` on every `repalloc*` and `repalloc_huge` declaration
  (`palloc.h:82-85, 96-98, 127` [verified-by-code]).
- **`MemoryContextSwitchTo` is invisible in frontend builds** —
  protected by `#ifndef FRONTEND` so frontend code that includes
  `postgres.h` (e.g. `pg_controldata`) compiles without dragging in
  the inline (`palloc.h:129-134` [from-comment]).
- **Callbacks should be allocated in the context they hook** so the
  reset/delete pass frees them automatically (`palloc.h:38-44`
  [from-comment]).

## Cross-references

- `memutils.h` — sibling header with the larger context-management API
  (creators, top-level pointers, `MaxAllocSize`).
- `nodes/memnodes.h` — concrete `MemoryContextData` and
  `MemoryContextMethods` struct shapes.
- `mcxt.c` — implements every prototype here.
- `memutils_internal.h` — `MemoryContextMethodID` + per-impl callback
  prototypes; `MCXT_ALLOC_*` flags are consumed by
  `MemoryContextAllocationFailure`/`MemoryContextSizeFailure` declared
  there.
- `knowledge/idioms/memory-contexts.md` — idiom-level usage patterns
  (Switch/Try/Catch, callback hygiene, OOM model).
- `knowledge/files/src/backend/utils/mmgr/mcxt.c.md` — implementation
  notes for everything here.

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 9

## Synthesized by
<!-- backlinks:auto -->
- [idioms/memory-contexts.md](../../../../idioms/memory-contexts.md)
- [subsystems/utils-mmgr.md](../../../../subsystems/utils-mmgr.md)