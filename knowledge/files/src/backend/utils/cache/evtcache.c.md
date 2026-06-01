# evtcache.c

- **Source path:** `source/src/backend/utils/cache/evtcache.c`
- **Lines:** 274
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `evtcache.h`, `catalog/pg_event_trigger.h`, `commands/event_trigger.c` (the consumer).

## Purpose

Special-purpose cache mapping `EventTriggerEvent` (`ddl_command_start`, `ddl_command_end`, `sql_drop`, `table_rewrite`, `login`) to the ordered list of enabled event-trigger functions to fire for it. Rebuilt by full scan of `pg_event_trigger` in name order; invalidated on any pg_event_trigger change. [from-comment, evtcache.c:3-4]

## Top-of-file comment

> "Special-purpose cache for event trigger data." [evtcache.c:3-4]

## Public surface

- `EventCacheLookup(EventTriggerEvent event) → List *` (64).
- Static: `BuildEventTriggerCache` (78), `InvalidateEventCacheCallback` (258), `DecodeTextArrayToBitmapset` (223).

## Key types / structs

- `EventTriggerCacheStateType` (33) — `{ETCS_NEEDS_REBUILD, ETCS_REBUILD_STARTED, ETCS_VALID}`.
- `EventTriggerCacheEntry` (40) — `{EventTriggerEvent event; List *triggerlist;}`.
- `EventTriggerCacheItem` (in evtcache.h) — per-trigger record with fnoid, enabled, tagset bitmap.
- Global `EventTriggerCache` (HTAB), `EventTriggerCacheContext` (MemoryContext), `EventTriggerCacheState` tri-state.

## Key invariants and locking

- **Tri-state rebuild guard.** `BuildEventTriggerCache` flips state to `ETCS_REBUILD_STARTED` before touching catalogs. If an inval arrives mid-build, `InvalidateEventCacheCallback` notices we're not VALID, leaves the in-progress memory alone, and sets `ETCS_NEEDS_REBUILD`. The builder still installs its result but leaves the state at `ETCS_NEEDS_REBUILD` so the *next* lookup rebuilds again. This avoids both infinite recursion and stale-after-inval. [verified-by-code, evtcache.c:114, 205-213, 261-273; from-comment, 205-209]
- **Name-order scan.** `systable_beginscan_ordered` on `EventTriggerNameIndexId` to fire triggers in name order — this defines the runtime firing order. [verified-by-code, evtcache.c:124-128]
- **Disabled triggers skipped at build time** (`evtenabled == TRIGGER_DISABLED`).
- **Single shared callback** registered on `EVENTTRIGGEROID` — coarse invalidation (full rebuild on any pg_event_trigger change). Rarely modified, so OK. [verified-by-code, evtcache.c:108-110]
- **Pointer-stability caveat for callers.** "Note that the caller had better copy any data it wants to keep around across any operation that might touch a system catalog into some other memory context, since a cache reset could blow the return value away." [from-comment, evtcache.c:59-62]
- **Event tag arrays decoded into Bitmapset** via `DecodeTextArrayToBitmapset` calling `GetCommandTagEnum`.

## Functions of note

1. **`EventCacheLookup`** (64) — single entry point; rebuilds if needed; returns the trigger list (or NIL).
2. **`BuildEventTriggerCache`** (78) — see invariants. The "rebuild started" → "valid" transition only happens if nobody invalidated during the rebuild.
3. **`DecodeTextArrayToBitmapset`** (223) — text[] of CommandTag names → Bitmapset of `CommandTag` enum values.

## Cross-references

- **Called by**: `commands/event_trigger.c` (`EventTriggerCommonSetup`, `EventTriggerCollectSimpleCommand`, login-trigger machinery).
- **Calls into**: relation/genam (`systable_beginscan_ordered`), inval (`CacheRegisterSyscacheCallback`), cmdtag (`GetCommandTagEnum`).

## Open questions

None of note.

## Confidence tag tally

verified-by-code: 4 — from-comment: 4 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
