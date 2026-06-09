# `src/include/lib/simplehash.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** ~1220

## Role

**The canonical templated open-addressing hash table** in the
backend. Generated per use-site by `#define SH_PREFIX foo; …;
#include "lib/simplehash.h"`. Used by `tidbitmap`, executor
grouping/agg (`execGrouping.c`), JIT compiled hash lookups,
catcache, plan-cache invalidation tracking, and many extensions.
Faster than `dynahash`'s `HTAB` due to no indirect calls, no
separate MemoryContext, and CPU-cache-friendly linear probing
with Robin-Hood placement. [from-comment]
`source/src/include/lib/simplehash.h:11-25`

## Required parameters

[verified-by-code] `source/src/include/lib/simplehash.h:33-53`

- `SH_PREFIX` — symbol prefix (e.g. `foo` → `foo_hash`,
  `foo_insert`)
- `SH_ELEMENT_TYPE` — caller's struct; must contain a `status`
  field of type `SH_STATUS` (enum with `EMPTY` and `IN_USE`)
- `SH_KEY_TYPE` — key type
- `SH_DECLARE` / `SH_DEFINE` / `SH_SCOPE` — generation toggles

When `SH_DEFINE` is set:

- `SH_KEY` — name of the key field in element
- `SH_EQUAL(table, a, b)` — key equality
- `SH_HASH_KEY(table, key)` → uint32

Optional: `SH_STORE_HASH` + `SH_GET_HASH(tb, a)` to stash the
hash in the element to skip rehash on grow / collision check.

Optional: `SH_RAW_ALLOCATOR` to use a custom byte allocator
(e.g. shared memory) rather than MemoryContext.

## Invariants

- INV-1: `status` field reserved in element type; values
  `SH_STATUS_EMPTY` / `SH_STATUS_IN_USE` (lines 105-108).
  Mis-naming the field silently corrupts.
- INV-2: bucket count is power of two; modulo is bit-AND
  (consistent with the Robin-Hood literature).
- INV-3: fill-factor defaults
  ([verified-by-code] lines 267-282):
  - `SH_FILLFACTOR = 0.9` (grow when above)
  - `SH_MAX_FILLFACTOR = 0.98` (hard ceiling)
  - `SH_GROW_MAX_DIB = 25` (max probe distance)
  - `SH_GROW_MAX_MOVE = 150` (max insert displacement)
  - `SH_GROW_MIN_FILLFACTOR = 0.1` (don't grow until at least
    10% full even on probe overflow)
- INV-4: deletion uses **backwards shift** (lines 75-89 of
  doc) rather than tombstones, so tables don't degrade
  asymptotically under heavy churn.

## Notable internals

- Robin-Hood: insert always swaps with any displaced "rich"
  element whose displacement is shorter than the new one
  (`SH_GROW_MAX_DIB` is the abort-and-grow trigger).
- Grow trigger compound: members ≥ grow_threshold OR
  (displacement > DIB/MOVE AND fill ≥ MIN_FILLFACTOR).
  [verified-by-code] lines 638-770.

## Trust boundary (Phase D)

- **Adversarial hash collisions**: simplehash trusts caller's
  `SH_HASH_KEY` to be uniformly distributed. If a consumer
  uses a deterministic hash on attacker-controlled key bytes
  (e.g. `hash_bytes` with no seed), an attacker can craft
  collision chains. Robin-Hood + SH_GROW_MAX_DIB mitigates by
  triggering early grow, but the grow itself is O(n).
- Cluster note: relates to A11/A13/A14 GIN/GiST signature
  collision concerns insofar as both topics are
  "hash-quality-as-defence". For simplehash the hot risk would
  be a tidbitmap or hash-agg memory blow-up from a SELECT that
  produces colliding hashes; ResourceOwner / work_mem bounds
  the damage.

## Cross-refs

- `knowledge/files/src/include/utils/dynahash.h.md` (if exists)
  — the older chained HTAB peer
- `knowledge/files/src/backend/lib/simplehash.c.md` — none;
  this is header-only template
- `knowledge/files/src/backend/nodes/tidbitmap.c.md` — primary
  internal user
- `knowledge/files/contrib/pg_trgm/` (A11/A13) — hash quality
  cluster

## Issues

- ISSUE-DESIGN: silent corruption if `SH_ELEMENT_TYPE` is
  missing the `status` field — only fails at link time and
  the error is opaque. (Low — caught early in dev.)
- ISSUE-TRUST: hash quality is caller-managed; documenting an
  in-house pattern for "use this hash with this seed for
  user-input keys" would harden against collision-DOS. (Low —
  no current exploit, but mentioned for Phase D.)
