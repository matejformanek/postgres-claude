# sinvaladt broadcast — shared cache invalidation

The sinval (shared invalidation) machinery is how a transaction
that changes a catalog notifies every other backend to drop their
relcache / syscache entries for the affected objects. Without it,
backend B could keep using a `Relation *` for a table that backend
A just dropped or repartitioned.

Anchors:
- `source/src/backend/storage/ipc/sinvaladt.c` — the shared
  invalidation array + queue [verified-by-code]
- `source/src/backend/utils/cache/inval.c` — message creation +
  per-backend consumption
- `source/src/include/storage/sinvaladt.h` — public API
- `knowledge/subsystems/utils-cache.md` — surrounding relcache /
  syscache discussion

## Conceptual model

A single shared **circular buffer** of `SharedInvalidationMessage`
records, indexed by monotonically-increasing `MsgNum` values:

- `maxMsgNum` — next subscript to store a submitted message in.
- `minMsgNum` — smallest subscript still pending for some backend.
- Per-backend `nextMsgNum` — the next message that backend needs to
  read.

Invariant: `maxMsgNum >= nextMsgNum[b] >= minMsgNum` for every
backend `b`.

[from-comment `sinvaladt.c:31-39`]

The circular buffer has `MAXNUMMESSAGES` slots
(a power of two for fast modulo). `MsgNum` values are translated to
buffer indexes via `MsgNum % MAXNUMMESSAGES`. As long as `maxMsgNum
- minMsgNum < MAXNUMMESSAGES`, every pending message is still in the
buffer.

[from-comment `sinvaladt.c:46-54`]

## Overflow → reset

If the buffer overflows (some backend fell more than
`MAXNUMMESSAGES` behind), the lagging backend's **`reset` flag** is
set. A backend in reset state must, on its next message-consumption
attempt, **discard all its invalidatable cache state** (relcache,
syscache, plancache) — it doesn't know what it missed.

Reset is the safety net, not the design point. It's correct but
expensive (the affected backend repopulates caches lazily).

## Catchup interrupts

To avoid resets, the sender machinery sends a `SIGUSR1`-class
**catchup interrupt** to any backend that's falling unreasonably
far behind. The lagging backend processes pending messages on the
interrupt (calling `SICleanupQueue` indirectly), and signals the
next-furthest-behind backend if more catchup is needed.

Normal behavior: **at most one catchup interrupt in flight at a
time**. The interrupt propagates from backend to backend until the
queue is drained or every behind-backend is up to date.

[from-comment `sinvaladt.c:58-72`]

The "stuck backend" case — a backend that can't process the
interrupt (e.g. inside a `SIGINT`-blocked critical section) —
eventually gets reset. The sinval machinery is designed to tolerate
this.

## Locking discipline

Two LWLocks protect the shared sinval array:

- **`SInvalReadLock`** — readers take SHARED. Authorizes the
  reader to modify their OWN `ProcState`, but not anyone else's.
  Writers and `SICleanupQueue` take EXCLUSIVE.

- **`SInvalWriteLock`** — writers always take EXCLUSIVE. Serializes
  adding messages to the queue.

The clever bit: **writers can run in parallel with one or more
readers** because the writer only touches the queue, not anyone's
`ProcState`. The only overlap is that the writer wants to bump
`maxMsgNum` while readers want to read it.

That's handled by a **per-array spinlock** that readers and writers
both take for the brief moment they touch `maxMsgNum`.

[from-comment `sinvaladt.c:79-89`]

## MsgNum wraparound

`MsgNum` values would overflow `int` eventually. When `minMsgNum`
exceeds `MSGNUMWRAPAROUND`, the writer subtracts
`MSGNUMWRAPAROUND` from every `MsgNum` variable simultaneously.

`MSGNUMWRAPAROUND` must be a multiple of `MAXNUMMESSAGES` so the
existing circular-buffer slot mapping doesn't change — the
wraparound is purely arithmetic, not data-moving.

## Message kinds

`SharedInvalidationMessage` is a tagged union — the `int id` field
discriminates among:

| Tag | Meaning |
|---|---|
| `id > 0` (syscache id) | Invalidate this syscache entry |
| `SHAREDINVALCATALOG_ID` | Invalidate the whole catalog cache |
| `SHAREDINVALRELCACHE_ID` | Invalidate a relcache entry (rd_id given) |
| `SHAREDINVALSMGR_ID` | smgr-level invalidation (file unlink notify) |
| `SHAREDINVALRELMAP_ID` | relmap update |
| `SHAREDINVALSNAPSHOT_ID` | snapshot management |

(Tag set defined in `source/src/include/utils/inval.h`.)

The receiver dispatches in `LocalExecuteInvalidationMessage` via a
switch on the id.

## When does a backend consume sinval messages?

- At `CommandCounterIncrement` (every SQL command boundary inside a
  transaction).
- At transaction start (`StartTransaction`).
- On a catchup interrupt (per the catchup-propagation chain above).
- On an explicit `AcceptInvalidationMessages()` call inside the
  backend's own code.

The first three cover ~99% of cases. The fourth exists for code
paths that pre-emptively need fresh cache state before catalog
inspection.

## Implications for new backend code

- **Catalog read paths that span CommandCounterIncrement** — be
  aware that a cache entry valid at the start of your code may not
  be valid after a `CCI`. Re-fetch.
- **Any code that publishes a catalog change** must register an
  invalidation via the appropriate `CacheInvalidate*` function in
  `src/backend/utils/cache/inval.c`. Forgetting this is the
  "stale cache" bug.
- **Custom cache implementations** — if you build a backend-side
  cache that mirrors catalog state, you need to register a callback
  via `CacheRegisterSyscacheCallback` /
  `CacheRegisterRelcacheCallback` so the sinval machinery flushes
  your cache too.

## Invariants

- **[INV-1]** Writers and readers can run concurrently. Don't
  add a code path that requires both `SInvalReadLock` and
  `SInvalWriteLock` together.
- **[INV-2]** Reset is correct-but-expensive; aim to avoid it
  via catchup interrupts.
- **[INV-3]** A backend in reset state must discard
  ALL invalidatable cache state on its next message-consumption
  call.
- **[INV-4]** New cache types must register an inval callback or
  forfeit cache coherence across backends.
- **[INV-5]** `MSGNUMWRAPAROUND` is a multiple of
  `MAXNUMMESSAGES` — preserves the circular-buffer slot
  mapping.

## Useful greps

- The inval-message kinds:
  `grep -n 'SHAREDINVAL.*_ID' source/src/include/utils/inval.h`
- Per-message dispatch:
  `grep -n 'LocalExecuteInvalidationMessage' source/src/backend/utils/cache/inval.c`
- Callback registration:
  `grep -RIn 'CacheRegisterSyscacheCallback\|CacheRegisterRelcacheCallback' source/src source/contrib`

## Cross-references

- `.claude/skills/catalog-conventions/SKILL.md` — catalog changes must register sinval invalidations via `CacheInvalidate*`.
- `.claude/skills/locking/SKILL.md` — `SInvalReadLock` / `SInvalWriteLock` partition rules; the per-array spinlock for `maxMsgNum`.
- `.claude/skills/bgworker-and-extensions/SKILL.md` — extensions that maintain caches register callbacks here.
- `knowledge/subsystems/utils-cache.md` — relcache / syscache / plancache architecture; the consumer side of sinval.
- `source/src/backend/storage/ipc/sinvaladt.c` — implementation.
- `source/src/backend/utils/cache/inval.c` — per-backend message creation + dispatch.
- `source/src/include/utils/inval.h` — message-kind constants.
