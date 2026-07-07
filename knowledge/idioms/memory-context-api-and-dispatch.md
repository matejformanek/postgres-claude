# Memory context API and dispatch

How PG's MemoryContext layer presents one C-level interface (`palloc` /
`pfree` / `repalloc`, plus reset, delete, callbacks, stats) on top of four
different allocators (AllocSet, Slab, Generation, Bump). The dispatch trick
is a 4-bit method-ID packed into the chunk header: any allocator-specific
operation can look at any chunk and know who owns it without a virtual
table on the chunk itself.

This doc is the "frame" around the per-allocator docs:
[[memory-context-allocset-internals]] for AllocSet (the default), and
[[memory-context-slab-generation-bump]] for the three specialized allocators.

## Anchors

All citations resolve at anchor `e18b0cb7344` on `source/...`.

- `source/src/backend/utils/mmgr/README:1` — design overview (528 lines).
- `source/src/include/nodes/memnodes.h:1` — `MemoryContextData`,
  `MemoryContextMethods`, `MemoryContextCounters`.
- `source/src/include/utils/memutils_internal.h:1` —
  `MemoryContextMethodID` enum, `MemoryContextCreate`,
  `MemoryContextAllocationFailure`, `MemoryContextSizeFailure`.
- `source/src/include/utils/memutils_memorychunk.h:1` — the chunk header
  bit-layout (4 bits methodID + 1 external + 30 value + 30 block-offset).
- `source/src/include/utils/palloc.h:1` — public `palloc` / `pfree` /
  `repalloc` declarations, `MemoryContextCallback`.
- `source/src/backend/utils/mmgr/mcxt.c:1` — context-type-independent
  operations: tree traversal, reset, delete, callbacks, stats.

## The abstraction in one struct

`MemoryContextData` is the common header every allocator embeds as its
first field [memnodes.h:117-134]:

```c
typedef struct MemoryContextData
{
    pg_node_attr(abstract)
    NodeTag       type;             /* T_AllocSetContext, T_SlabContext, … */
    bool          isReset;          /* no allocation since last reset */
    bool          allowInCritSection;
    Size          mem_allocated;    /* bytes malloc'd for this context */
    const MemoryContextMethods *methods;  /* vtable */
    MemoryContext parent;
    MemoryContext firstchild;
    MemoryContext prevchild;
    MemoryContext nextchild;
    const char   *name;             /* statically-allocated context name */
    const char   *ident;            /* optional dynamic identifier */
    MemoryContextCallback *reset_cbs;
} MemoryContextData;
```

The vtable [memnodes.h:58-114] is C++-style — one `MemoryContextMethods`
struct per allocator type, holding `alloc`/`free_p`/`realloc`/`reset`/
`delete_context`/`get_chunk_context`/`get_chunk_space`/`is_empty`/`stats`
(plus a `check` slot under `MEMORY_CONTEXT_CHECKING`). The vtable lives in
a static `mcxt_methods[]` array indexed by `MemoryContextMethodID`
[mcxt.c:64-153] — contexts share the table by pointer, they don't copy it.

`MemoryContextIsValid` [memnodes.h:145-150] accepts only the four real
allocator tags: `AllocSetContext`, `SlabContext`, `GenerationContext`,
`BumpContext`. Anything else (including the abstract base) fails the
check.

## How `pfree` finds the right allocator without a chunk-stored vtable

The trick is the `uint64` immediately preceding every chunk
[memutils_memorychunk.h:24-44]. Low 4 bits = `MemoryContextMethodID`,
next bit = "external" flag, next 30 = allocator-defined value (typically
chunk size or freelist index), top 30 = byte offset back to the chunk's
block header. The top bit of (3) overlaps the low bit of (4) — that bit
must always be 0 because chunk-to-block offsets are MAXALIGNed.

The dispatch macro [mcxt.c:205-206]:

```c
#define MCXT_METHOD(pointer, method) \
    mcxt_methods[GetMemoryChunkMethodID(pointer)].method
```

`pfree` is then literally one line of dispatched code
[mcxt.c earlier in file]:

```c
void pfree(void *pointer) { MCXT_METHOD(pointer, free_p)(pointer); }
```

`GetMemoryChunkMethodID` [mcxt.c:213-234] reads the header byte under a
Valgrind `MAKE_MEM_DEFINED`/`MAKE_MEM_NOACCESS` envelope, masks off the
low 4 bits, and returns the ID. The Valgrind dance matters because chunk
headers are otherwise marked NOACCESS so that any client-code read of
them shows up as an error. `[verified-by-code]`

## The 16-entry methodID enum, with three poisoned slots

`MemoryContextMethodID` [memutils_internal.h:121-139]:

| ID | Name                            | Notes |
|----|---------------------------------|-------|
| 0  | `MCTX_0_RESERVED_UNUSEDMEM_ID`  | never-used memory pattern catches `pfree` on freshly-malloc'd region |
| 1  | `MCTX_1_RESERVED_GLIBC_ID`      | glibc small malloc chunks tend to match this pattern |
| 2  | `MCTX_2_RESERVED_GLIBC_ID`      | glibc large (>128KB) malloc chunks |
| 3  | `MCTX_ASET_ID`                  | AllocSet (default) |
| 4  | `MCTX_GENERATION_ID`            | Generation |
| 5  | `MCTX_SLAB_ID`                  | Slab |
| 6  | `MCTX_ALIGNED_REDIRECT_ID`      | `palloc_aligned` indirection chunk |
| 7  | `MCTX_BUMP_ID`                  | Bump |
| 8–14 | `MCTX_*_UNUSED_ID`            | reserved for future allocators |
| 15 | `MCTX_15_RESERVED_WIPEDMEM_ID`  | `0xFF`-wiped memory (e.g. after `wipe_mem`) |

The 0/1/2 and 15 reservations are about **bogus-pointer detection**, not
allocator dispatch [memutils_internal.h:118-120]: glibc's malloc happens
to leave its flag bits where PG puts the method ID, so chunks that came
from raw `malloc()` (not `palloc`) look like `MCTX_1_RESERVED_GLIBC_ID` or
`MCTX_2_RESERVED_GLIBC_ID`. Those slots in `mcxt_methods[]` route to
`BogusFree`/`BogusRealloc`/`BogusGetChunkContext`/`BogusGetChunkSpace`
[mcxt.c:142-152, 308-337] which `elog(ERROR)` with the header word.

## What `MemoryContextCreate` actually does

`MemoryContextCreate` [mcxt.c:1151-1192] is the **type-independent**
half of context creation. Each allocator has its own `XxxContextCreate`
(public API, e.g. `AllocSetContextCreateInternal`,
`SlabContextCreate`, `GenerationContextCreate`, `BumpContextCreate`)
that does the type-specific allocation, then calls this. Sequence:

1. **Critical-section guard** — `Assert(CritSectionCount == 0)`.
   Creating contexts under a critical section is forbidden because the
   underlying `malloc()` could fail and an OOM during a critical section
   escalates to PANIC.

2. **Initialize the common header** — `type`, `methods` (from the static
   table), parent linkage, NULL children/reset_cbs.

3. **Link into parent's child list** — push at the head of
   `parent->firstchild`. This makes context creation O(1) and child
   ordering LIFO, which is exactly what you want for transient contexts:
   `MemoryContextDelete(parent)` walks first-child first
   [mcxt.c:489-509] so the most-recently-created child dies first.

4. **Inherit `allowInCritSection`** from parent. Children of
   `ErrorContext` (the one context that permits critical-section
   allocation) get the same permission [mcxt.c:392-397].

The vtable pointer is fixed at create time and never changes for the
lifetime of the context. `[verified-by-code]`

## Tree traversal without recursion

`MemoryContextTraverseNext` [mcxt.c:279-300] is the workhorse for
walking a context's descendants. Pre-order, sibling-then-up. The
non-recursive walk is intentional — the comment at mcxt.c:262-265
warns that recursion could blow the C stack during error cleanup with
deep context hierarchies. The pattern is documented at mcxt.c:266-278:

```c
<process context>
for (MemoryContext curr = context->firstchild;
     curr != NULL;
     curr = MemoryContextTraverseNext(curr, context))
{
    <process curr>
}
```

`MemoryContextDelete` itself [mcxt.c:474-509] is even more careful: it
descends to the leftmost leaf, deletes that leaf via
`MemoryContextDeleteOnly`, then walks back up — without
`MemoryContextTraverseNext`, because the tree is being modified as the
walk proceeds. The comment at mcxt.c:482-487 calls this out
explicitly.

## Reset vs ResetOnly vs ResetChildren vs Delete vs DeleteChildren

Five operations, three orthogonal axes:

| Op                              | Self | Children                     | Delete or just reset? |
|---------------------------------|------|------------------------------|------------------------|
| `MemoryContextReset`            | reset | **delete** all descendants  | mixed: reset self, delete children |
| `MemoryContextResetOnly`        | reset | leaves children alone        | reset self only |
| `MemoryContextResetChildren`    | leave self alone | reset all descendants | reset descendants only |
| `MemoryContextDelete`           | **delete** | delete all descendants | delete everything |
| `MemoryContextDeleteChildren`   | leave self alone | delete all descendants | delete descendants only |

`MemoryContextReset` [mcxt.c:405-417] is the common case:
"give me back a clean context but keep the context object itself". It
deletes children (because the README explains at line 119-123 that you
almost always want children gone too — reset-with-empty-children is
rarely useful) and then resets self via `MemoryContextResetOnly` if
`!isReset`.

`MemoryContextResetOnly` [mcxt.c:424-445] fires reset callbacks first
(see below) and **then** delegates to the allocator's `reset` method.
The order matters: a callback might still need access to memory that
the reset is about to wipe.

`MemoryContextDeleteOnly` [mcxt.c:517-550] is the single-node leaf
deletion. The order is: callbacks → `SetParent(NULL)` to delink → clear
`ident` → `methods->delete_context(context)`. Delinking before the
type-specific delete is deliberate: if `delete_context` were to throw,
leaving the context in the parent's child list would be a hard-to-debug
dangling pointer [mcxt.c:535-539].

## Reset/delete callbacks — the 9.5 escape hatch

Sometimes memory contexts own resources that aren't just palloc'd memory:
- an open file descriptor associated with a tuplesort
- a refcount on a long-lived cache object
- a malloc'd buffer from a non-PG library (the README explicitly calls
  this out at mmgr/README:148-156 as the only sane use of
  callback-managed malloc)

`MemoryContextRegisterResetCallback` [mcxt.c:584-595] pushes a
caller-provided `MemoryContextCallback` struct onto a linked list. The
caller provides the struct — usually allocated **inside** the same
context as the resource it tracks, so the struct itself goes away when
the context is reset/deleted. The struct holds `func` (function ptr to
call), `arg` (one void* of state), and `next`.

Three rules from `mmgr/README:158-161` and the source:

1. **Push at the head, call in reverse order of registration** —
   `cb->next = context->reset_cbs; context->reset_cbs = cb`. So the
   most-recently-registered callback fires first.
2. **Child callbacks fire before parent callbacks** during a tree
   reset/delete, because the walk is bottom-up.
3. **Pop before call** [mcxt.c:637-651] — `while (cb = context->reset_cbs) { context->reset_cbs = cb->next; cb->func(cb->arg); }`. If the
   callback throws, we won't try to call it a second time on the next
   reset.

`MemoryContextUnregisterResetCallback` [mcxt.c:609-630] is the
"actually I don't need this anymore" path. It walks the list and unlinks
the matching struct. Hitting a callback that isn't there asserts —
the comment explains the design choice at mcxt.c:601-608: a silent
no-op would mask the common bug of passing the wrong context. `[from-comment]`

## Globally-known contexts and the lifespan hierarchy

`mmgr/README:177-258` lays out the seven globals that every backend
starts with. They form a tree by intended lifespan:

```
TopMemoryContext              # process-lifetime, malloc-equivalent
├── ErrorContext              # reserved 8KB, allowed in critical sections
├── PostmasterContext         # postmaster only; backends delete after fork
├── CacheMemoryContext        # relcache/catcache; lives forever
├── MessageContext            # one frontend message, reset per outer loop
├── TopTransactionContext     # top-level xact lifetime, survives error
│   └── CurTransactionContext # subxact-scoped; aliases parent at top level
└── PortalContext             # active portal's per-portal context (alias only)
```

A few subtleties that bite if you misuse them:

- **`CurrentMemoryContext` should point somewhere short-lived.**
  The README explicitly warns at line 91-96: only "very circumscribed
  code" should ever switch into a long-lived context. The default during
  query execution is a per-tuple context that gets reset each tuple.

- **`TopTransactionContext` is NOT cleared on error** — only at
  COMMIT/ROLLBACK [README:223-230]. Anything you allocate there
  survives a thrown error within the transaction block. Useful for
  cross-statement state, dangerous if you mean "wipe on error".

- **`CurTransactionContext` aliases `TopTransactionContext` at the top
  level**; in subxacts it points to a child. A failed subxact's
  `CurTransactionContext` is thrown away during abort, but a
  *committed* subxact's stays until top-level commit. The example
  given is `NOTIFY` messages [README:240-246].

- **`ErrorContext` is special-cased twice**: created at
  `MemoryContextInit` with slow growth and 8K reserved
  [mcxt.c:392-396], then immediately marked
  `allowInCritSection = true` [mcxt.c:397]. This is what makes OOM
  an `ERROR` instead of a `FATAL` — `errstart` has somewhere to allocate.

`MemoryContextInit` [mcxt.c:361-398] runs in every backend (well,
once per process tree in non-EXEC_BACKEND builds, once per backend in
EXEC_BACKEND builds, because there `TopMemoryContext` doesn't survive
fork). It's the very first thing — `elog.c` assumes `ErrorContext` is
non-NULL.

## `MemoryContextAlloc`, `palloc`, and the OOM path

`MemoryContextAlloc` [mcxt.c:1234-1259]:

```c
void *
MemoryContextAlloc(MemoryContext context, Size size)
{
    void *ret;
    Assert(MemoryContextIsValid(context));
    AssertNotInCriticalSection(context);
    context->isReset = false;
    ret = context->methods->alloc(context, size, 0);
    VALGRIND_MEMPOOL_ALLOC(context, ret, size);
    return ret;
}
```

Two design decisions worth highlighting:

1. **OOM is handled inside the allocator's `alloc` callback, not here.**
   The comment at mcxt.c:1244-1253 is explicit: this lets the compiler
   apply tail-call optimization on the common (allocation succeeds)
   path. Allocation is a hot enough spot that one avoided stack frame
   matters. The `MemoryContextAllocationFailure` helper [mcxt.c:1200-1214]
   is what allocators call on `malloc() == NULL`. Its behavior depends
   on flags: `MCXT_ALLOC_NO_OOM` returns NULL, otherwise it prints
   `MemoryContextStats(TopMemoryContext)` to the log and ereports
   `ERRCODE_OUT_OF_MEMORY`. The "dump every context" diagnostic in the
   log is precious — it tells you which context bloated.

2. **`isReset = false` happens unconditionally**, even if the alloc
   eventually fails. This is fine because we'd be about to error out
   anyway; the `isReset` flag exists to skip `methods->reset()` in the
   common no-allocation case [mcxt.c:430].

`palloc(size)` is a one-liner in `mcxt.c` that forwards to
`MemoryContextAlloc(CurrentMemoryContext, size)`. `palloc0` is the
zeroed variant via `MemoryContextAllocZero` [mcxt.c:1268-1285] (uses
`MemSetAligned` to clear the chunk after alloc — the helper does an
aligned bulk store that's faster than `memset` for our typical
chunk sizes). `palloc_extended` [mcxt.c:1291-1315] is the
flag-aware version — handles `MCXT_ALLOC_HUGE` for >1GB allocations
(otherwise `AllocSizeIsValid` would reject the size).

## `repalloc` doesn't use `CurrentMemoryContext`

This is documented at `mmgr/README:99-104` and is a subtle correctness
property: `pfree(p)` and `repalloc(p, n)` look at the chunk to find its
**owning** context, regardless of what `CurrentMemoryContext` currently
points at. This is what makes patterns like "switch into a temp context
to do work, then `repalloc` the result back into the caller's context"
unnecessary — `repalloc` operates on the chunk's home, not the active
context.

The same property is why `pfree(NULL)` is **not** valid
[README:69-75]: for `repalloc(NULL, n)`, there's no chunk to read the
context from. For `pfree(NULL)`, it's mostly historical + a perf
microopt (avoid the extra NULL check per pfree). If you want NULL-safe,
you write the check yourself.

`palloc(0)` IS valid [README:64-67] — returns a non-NULL pointer to a
zero-byte chunk you cannot read or write but can later `repalloc` or
`pfree`.

## Stats and the memory-accounting design

`MemoryContextStats(context)` and `MemoryContextStatsDetail`
[mcxt.c:866-880, 881+] walk the tree and aggregate `mem_allocated`
counters. Each context tracks its own bytes consumed at the **block**
level [README:511-527] — `mem_allocated` updates only when a block is
malloc'd or freed, not on every chunk operation. This is the lazy-but-
fast accounting design noted in the README at line 523-527.

`MemoryContextMemAllocated(context, recurse)` [mcxt.c:814+]:
- `recurse=false` → just `context->mem_allocated`, O(1).
- `recurse=true` → walks descendants via `MemoryContextTraverseNext`,
  summing `mem_allocated`. O(descendants).

The recursive walk is **not** intended for high-frequency calls — the
README warns at line 525-527 that contexts-with-many-children make this
slow.

`MemoryContextMemConsumed` [mcxt.c:838+] is the more detailed sibling
that fills in a `MemoryContextCounters` (totalspace, freespace,
nblocks, freechunks) by dispatching to the allocator's `stats` method.
The counter set is intentionally AllocSet-shaped [memnodes.h:23-28];
Slab/Generation/Bump map their own metrics into the same fields.

`HandleLogMemoryContextInterrupt` [mcxt.c:1325-1331] is the signal
hook for `pg_log_backend_memory_contexts(pid)` — sets pending flags,
the actual work happens in `ProcessLogMemoryContextInterrupt` from
`CHECK_FOR_INTERRUPTS()`.

## `palloc_aligned` and the redirect chunk

PG normally MAXALIGNs allocations (8-byte alignment on most platforms).
For larger alignment (e.g. 64-byte cache line, page boundary), there's
`palloc_aligned` [mcxt.c:1485+] and the `MCTX_ALIGNED_REDIRECT_ID`
method. The trick: allocate `size + alignto + sizeof(MemoryChunk)`,
place a "redirect" `MemoryChunk` at the aligned pointer that points
back to the real chunk header below. `pfree` on the aligned pointer
hits the `MCTX_ALIGNED_REDIRECT_ID` slot in `mcxt_methods[]`, which
chases the redirect to the real chunk and forwards
[memutils_internal.h:76-80, mcxt.c:107-119].

This is the one allocator-ID that doesn't have a context type behind it
— it's a chunk-level indirection only. The `alloc`/`reset`/`delete`
slots in `mcxt_methods[MCTX_ALIGNED_REDIRECT_ID]` are NULL because
nothing creates a "context of aligned redirects". `[verified-by-code]`

## Critical-section discipline

`AssertNotInCriticalSection(context)` [mcxt.c:198-199]:

```c
#define AssertNotInCriticalSection(context) \
    Assert(CritSectionCount == 0 || (context)->allowInCritSection)
```

It's asserted at every `MemoryContextAlloc` entry. Why: inside a
critical section (`START_CRIT_SECTION()` / `END_CRIT_SECTION()`), any
ERROR is escalated to PANIC. An OOM from `malloc()` is an ERROR, so
allocating in a critical section is allowing ANY allocation to take
down the server. The standard escape: pre-allocate before the critical
section starts.

`MemoryContextAllowInCriticalSection` [mcxt.c:746+] is the explicit
opt-in. The only callers in the tree:
- `ErrorContext` itself [mcxt.c:397]
- Some `bufmgr` paths that need to allocate scratch in `LockBuffer`-
  protected code; check the README in `storage/buffer` for the exact
  invariants

Inheritance: any child of a context with `allowInCritSection=true` gets
the flag for free [mcxt.c:1184-1185]. So children of `ErrorContext`
also allocate-in-crit-section.

## Invariants

- **Every chunk has a 4-bit method ID in its preceding `uint64`.** This
  is the contract every allocator must satisfy. Bump's no-header design
  cheats by storing the header only under `MEMORY_CONTEXT_CHECKING`;
  outside that flag, you simply cannot `pfree` a Bump chunk — and the
  allocator wires its `free_p` to an `elog(ERROR)`.
- **Methods pointer is fixed at create.** Don't try to change an
  allocator type on an existing context.
- **`reset_cbs` are LIFO and bottom-up across the tree.** Most-recently-
  registered fires first; child callbacks fire before parent callbacks
  during a tree reset.
- **`pfree(NULL)` and `repalloc(NULL, n)` are both forbidden** —
  documented, intentional.
- **`palloc(0)` is fine** — returns a valid no-read no-write pointer.
- **`isReset` is a fast-path optimization**, not a state machine.
  Cleared on first allocation, set back to true on reset. Doesn't reflect
  "logically empty"; an AllocSet with all chunks pfree'd is logically
  empty but `isReset` is still false (no detection of the last pfree).
- **No allocation in a critical section** unless `allowInCritSection`,
  which is inherited from parent.
- **Context creation can't fail** beyond the initial `malloc` — there
  must be no failure points between the `malloc` and `MemoryContextCreate`
  call [README:163-170, aset.c:456-459].

## Useful greps

```bash
# Where's a given global context set up?
grep -nE "MemoryContextInit\b|TopMemoryContext = |ErrorContext = " \
    source/src/backend/utils/mmgr/mcxt.c

# Find every concrete context type:
grep -RnE 'AllocSetContextCreate|SlabContextCreate|GenerationContextCreate|BumpContextCreate' source/src

# Spot reset-callback users (interesting integration points):
grep -RnE 'MemoryContextRegisterResetCallback' source/src

# Trace pfree dispatch:
grep -n "MCXT_METHOD\b" source/src/backend/utils/mmgr/mcxt.c

# Look at the chunk header bit layout:
sed -n '20,60p' source/src/include/utils/memutils_memorychunk.h

# Inspect a backend's contexts at a point in time (gdb session):
#   (gdb) call MemoryContextStats(TopMemoryContext)
# Or via SQL, after pg_log_backend_memory_contexts(pid):
#   tail -f $PGDATA/log/postgresql-*.log
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/mmgr/mcxt.c`](../files/src/backend/utils/mmgr/mcxt.c.md) | 1 | context-type-independent operations: tree traversal, reset, delete, callbacks, stats |
| [`src/include/nodes/memnodes.h`](../files/src/include/nodes/memnodes.h.md) | 1 | MemoryContextData, MemoryContextMethods, MemoryContextCounters |
| [`src/include/utils/memutils_internal.h`](../files/src/include/utils/memutils_internal.h.md) | 1 | MemoryContextMethodID enum, MemoryContextCreate, MemoryContextAllocationFailure, MemoryContextSizeFailure |
| [`src/include/utils/memutils_memorychunk.h`](../files/src/include/utils/memutils_memorychunk.h.md) | 1 | chunk header bit-layout (4 bits methodID + 1 external + 30 value + 30 block-offset) |
| [`src/include/utils/palloc.h`](../files/src/include/utils/palloc.h.md) | 1 | public palloc / pfree / repalloc declarations, MemoryContextCallback |

<!-- /callsites:auto -->

## Cross-references

- [[memory-context-allocset-internals]] — AllocSet (`MCTX_ASET_ID`),
  the default workhorse: 11 freelists, keeper blocks, context recycle.
- [[memory-context-slab-generation-bump]] — the three specialized
  allocators and where they're worth using.
- [[expression-evaluator-flow]] — the per-tuple context reset rhythm
  during expression evaluation.
- [[apply-worker-loop-and-dispatch]] — `ApplyContext` vs
  `ApplyMessageContext` lifespan split.
- [[cost-units-gucs]] — the planner's per-plan-node memory context
  pattern.
- [[heap-tuple-visibility-mvcc]] — how relcache lives in
  `CacheMemoryContext` children with subsidiary lifetimes.
