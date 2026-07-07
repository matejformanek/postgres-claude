# Cache-invalidation callback registration

Code that maintains a backend-local cache of catalog state needs
to be notified when the underlying catalog changes — otherwise the
cache silently goes stale and the backend returns wrong answers
until restart. The `CacheRegister*Callback` family is how a
subsystem hooks into the existing sinval (shared invalidation)
machinery so its cache stays coherent without re-implementing
broadcast.

Anchors:
- `source/src/backend/utils/cache/inval.c` — registration +
  dispatch [verified-by-code]
- `source/src/include/utils/inval.h` — public API
- `knowledge/idioms/sinvaladt-broadcast.md` — the underlying
  broadcast machinery this hook plugs into
- `knowledge/subsystems/utils-cache.md` — the syscache /
  relcache the built-in callbacks maintain

## The three callback flavors

| Function | When fired | Argument passed |
|---|---|---|
| `CacheRegisterSyscacheCallback(cacheid, fn, arg)` | Specific syscache entry invalidated | hash value of invalidated tuple (or `0` for full reset) |
| `CacheRegisterRelcacheCallback(fn, arg)` | Any relcache entry invalidated | OID of invalidated relation (or `InvalidOid` for full reset) |
| `CacheRegisterRelSyncCallback(fn, arg)` | Pgoutput / logical decoding state invalidated | (logical-replication specific) |

[verified-by-code `inval.c:1813,1855` for the first two]

The relsync flavor exists for the logical-replication output
plugin's row-filter cache; rarely relevant outside that subsystem.

## The "full reset" convention

Each callback **must handle a reset signal** indicated by a
distinguished argument value:

- Syscache callbacks: `hashvalue == 0` → flush ALL cached state
  the callback owns.
- Relcache callbacks: `relid == InvalidOid` → flush ALL.

[from-comment `inval.c:1800-1812, 1846-1855`]

Reset happens after a sinval-queue overflow (see
`knowledge/idioms/sinvaladt-broadcast.md` § "Overflow → reset")
or on initial setup. The reset signal is the only way to convey
"you missed messages; don't trust your state."

Forgetting to handle reset is a classic bug: cache works most of
the time, then on a high-volume DDL workload one backend's cache
goes silently stale. Symptoms: backend returns wrong answers,
restart fixes it, can't reproduce.

## Where the callbacks fire from

The dispatch hub is `LocalExecuteInvalidationMessage()` in
`inval.c`. It runs at:

- `CommandCounterIncrement()` — every SQL command boundary.
- `StartTransaction()` — transaction start.
- Catchup interrupts — when this backend falls behind.
- Explicit `AcceptInvalidationMessages()` — pre-emptive consumption.

For each pending `SharedInvalidationMessage`, dispatch is by the
message's `id` field. Syscache messages walk
`syscache_callback_list`; relcache messages walk
`relcache_callback_list`.

## Implementation: linked-list-of-callbacks per cacheid

For syscache callbacks, the registry uses a clever
linked-list layout to amortize dispatch:

```c
syscache_callback_links[cacheid] = head of chain for this cacheid
syscache_callback_list[]         = pool of {id, link, function, arg} records
```

[verified-by-code `inval.c:1819-1842`]

When a syscache entry is invalidated, dispatch walks just the
chain for that cacheid — not every registered callback. The cost
is per-cacheid-with-callbacks, not per-callback-across-all-caches.

For relcache callbacks the dispatch is simpler — every callback
fires for every relcache invalidation, indiscriminately. The
callbacks themselves must filter by OID if they only care about a
subset of relations.

## Slot budget

The pools are sized at compile time:

- `MAX_SYSCACHE_CALLBACKS` — exhausting it raises `FATAL: out of
  syscache_callback_list slots`
  [verified-by-code `inval.c:1820`].
- `MAX_RELCACHE_CALLBACKS` — similar
  [verified-by-code `inval.c:1859`].

Both are large enough for built-in callees + a few dozen
extension callbacks. If you blow past it from an extension, your
extension is doing something wrong (probably registering per-call
instead of per-load).

## Callback-order semantics

- **First-registered fires first.** Both pools chain in
  registration order
  [from-comment `inval.c:1828-1834` "add to end of chain, so that
  older callbacks are called first"].
- **Core callbacks register at `InitPostgres` time**, before any
  extension can. So built-in cache eviction is always observable
  before extension callbacks fire.
- **Extensions register at module load** (`_PG_init`) by convention
  — not on first call. This guarantees the callback is in place
  before any data could be cached.

## Common review-time concerns

- **Always register at `_PG_init` time, never lazily.** A callback
  installed after the first cache fill misses the invalidations
  for entries cached pre-registration.
- **Filter callbacks by the argument** rather than registering
  many callbacks. One callback that dispatches internally is
  cheaper than 50 cacheid-specific callbacks.
- **Never block in a callback.** They run inside sinval dispatch
  paths that may hold the per-backend `ProcState`. Blocking
  stalls the catchup chain.
- **Handle the reset argument.** Untested code paths here account
  for ~half the cache-invalidation bugs I've seen.

## Standard sites in the tree

- `RelationCacheInvalidateEntry` — built-in relcache eviction.
- `SysCacheInvalidate` — built-in syscache eviction.
- `pgstat_drop_*` — pgstats maintenance.
- `plancache_invalidate` — prepared-statement plan cache.
- `LogicalRepCacheInvalidate` — logical-replication subscriber.

Each of these is registered in its subsystem's init code (NOT in
inval.c itself).

## Invariants

- **[INV-1]** Callbacks MUST handle the reset signal (hashvalue=0
  or relid=InvalidOid).
- **[INV-2]** Callbacks fire in registration order; the first
  registered runs first.
- **[INV-3]** Registration is per-postmaster-fork (i.e. per
  backend, since callbacks live in process-local memory).
- **[INV-4]** Pool slots are fixed at compile time; running out
  is FATAL.
- **[INV-5]** Callbacks must be non-blocking; they run inside
  sinval dispatch.

## Useful greps

- All registration sites:
  `grep -RIn 'CacheRegisterSyscacheCallback\|CacheRegisterRelcacheCallback\|CacheRegisterRelSyncCallback' source/src source/contrib`
- The dispatch hub:
  `grep -n 'LocalExecuteInvalidationMessage' source/src/backend/utils/cache/inval.c`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/cache/inval.c`](../files/src/backend/utils/cache/inval.c.md) | — | registration + dispatch |
| [`src/include/utils/inval.h`](../files/src/include/utils/inval.h.md) | — | public API |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/idioms/sinvaladt-broadcast.md` — the underlying
  broadcast machinery; the registration here is the consumer side.
- `knowledge/subsystems/utils-cache.md` — relcache + syscache
  architecture; the canonical callers.
- `.claude/skills/catalog-conventions/SKILL.md` — DDL that
  modifies catalogs publishes the inval messages these callbacks
  consume.
- `.claude/skills/extension-development/SKILL.md` — extensions
  that maintain caches register here in `_PG_init`.
- `.claude/skills/bgworker-and-extensions/SKILL.md` — extensions
  with shared-state caches need callback hooks too.
- `source/src/backend/utils/cache/inval.c` — implementation.
- `source/src/include/utils/inval.h` — public API.
