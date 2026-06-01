# evtcache.h

- **Source path:** `source/src/include/utils/evtcache.h`
- **Lines:** 38
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `evtcache.c` (impl), `commands/event_trigger.c` (consumer).

## Purpose

Public surface for the event-trigger cache. Declares the `EventTriggerEvent` enum (`EVT_DDLCommandStart`, `EVT_DDLCommandEnd`, `EVT_SQLDrop`, `EVT_TableRewrite`, `EVT_Login`) and the `EventTriggerCacheItem` struct (one per enabled trigger: fnoid, enabled, tagset bitmap).

## Public surface

- **Enum**: `EventTriggerEvent` (20).
- **Struct**: `EventTriggerCacheItem` (29) — `{Oid fnoid; char enabled; Bitmapset *tagset;}`.
- **Function**: `EventCacheLookup(EventTriggerEvent event) → List *` (36) — returns `List *` of `EventTriggerCacheItem *`.

## Confidence tag tally

verified-by-code: 1 — from-comment: 0 — from-readme: 0 — inferred: 0 — unverified: 0
