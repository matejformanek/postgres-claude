---
source_url: https://wiki.postgresql.org/wiki/Free_Space_Map_Problems
fetched_at: 2026-06-03T19:50:00Z
wiki_last_edited: 2016-10-31
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: page documents specific FSM-corruption *bugs* fixed in 9.3.15 /
  9.4.10 / 9.5.5 / 9.6.1 (all long out of support). The detection/repair
  *procedure* it describes is still valid; the pre-8.4 in-memory FSM history I
  expected is NOT on this page (supplemented from the corpus below).
---

# Wiki distilled — Free Space Map problems

This page is narrower than its title: it is a **how-to-detect-and-repair a
corrupt `_fsm` fork** guide, written around a cluster of 2016 WAL-logging bugs.
The general FSM architecture is supplemented from the corpus.

## What the wiki page actually covers

- **The bug class:** several point releases fixed a "failure to make adequate WAL
  log entries when an FSM is truncated" — affected anything before **9.3.15,
  9.4.10, 9.5.5, 9.6.1**. A standby (or a crash-recovered primary) could end up
  with an `_fsm` fork pointing at heap blocks that no longer exist. [from-wiki]
- **The symptom:** `ERROR: could not read block NNN ... read only 0 of 8192
  bytes` — the FSM claims free space on a page past the real end of the relation.
  [from-wiki]
- **Detection uses the `pg_freespacemap` contrib extension:** `CREATE EXTENSION
  pg_freespacemap;` then compare `pg_freespace()` reports against
  `pg_relation_size()` / `pg_relation_filepath()` to find FSM entries beyond the
  heap's real block count. [from-wiki]
- **Repair = delete the fork and rebuild it:** shut the server down *cleanly*
  (NOT `pg_ctl stop -m immediate`), manually delete the relation's `_fsm`
  file(s), then run `VACUUM` to regenerate the FSM from scratch. The FSM is
  pure derived state, so deleting it is safe — only free-space *hints* are lost,
  and VACUUM recomputes them. [from-wiki]

## Corpus supplement — what the FSM actually is

The wiki page omits the architecture; the corpus has it:

- **The FSM is a per-relation on-disk fork (`_fsm`), since 8.4.** It is a binary
  tree of one-byte slots, one leaf per heap page, stored as a separate fork
  alongside the main and `_vm` forks. (The pre-8.4 fixed-size *in-memory* FSM —
  with the retired `max_fsm_pages` / `max_fsm_relations` GUCs that needed a
  restart to resize — is what the 8.4 rewrite replaced; that history is not on
  this wiki page.) [verified-by-code,
  source/src/backend/storage/freespace/freespace.c, via
  knowledge/files/src/backend/storage/freespace/freespace.c.md]
- **Free space is bucketed into 256 categories (one byte/page):**
  `FSM_CATEGORIES = 256`, `FSM_CAT_STEP = BLCKSZ / 256` (= 32 bytes per step at
  8 kB), and `MaxFSMRequestSize = MaxHeapTupleSize` caps a request at category
  255. So the FSM tracks free space at ~32-byte resolution — it is a hint, never
  exact. [verified-by-code, freespace.c:17-21, via the per-file doc]
- **It is lossy and self-healing by design:** because the category is coarse and
  the whole fork is reconstructible by VACUUM, a stale or deleted FSM costs only
  bloat/placement-efficiency, never correctness — which is exactly why the
  wiki's "delete the file and VACUUM" repair is safe. [inferred, from-comment]
- **Index FSM is a separate, simpler user:** `indexfsm.c` uses the same machinery
  to track whole free *pages* (not partial space) for index AMs. [verified-by-code,
  via knowledge/files/src/backend/storage/freespace/indexfsm.c.md]

## Why it matters operationally

- Treat the `_fsm` fork as a disposable cache: corruption is annoying but never
  data-loss, and the fix (clean stop → delete `_fsm` → VACUUM) is mechanical.
  [inferred, from-wiki]
- The bugs that motivated the page are all in unsupported majors; the page's
  lasting value is the **detection recipe** (`pg_freespacemap` +
  `pg_relation_size` comparison), reusable for any "FSM points past EOF" symptom.
  [from-wiki]

## Links into corpus

- [[knowledge/files/src/backend/storage/freespace/freespace.c.md]] — the FSM
  implementation: `FSM_CATEGORIES`/`FSM_CAT_STEP` (17-21), `fsm_search`, the
  binary-tree slot layout.
- [[knowledge/files/src/backend/storage/freespace/fsmpage.c.md]] — per-page FSM
  node operations.
- [[knowledge/files/src/backend/storage/freespace/indexfsm.c.md]] — the
  whole-page index variant.
- [[knowledge/files/src/include/storage/freespace.h.md]] — public FSM API
  (`RecordPageWithFreeSpace`, `GetPageWithFreeSpace`, `FreeSpaceMapVacuum`).
- [[knowledge/subsystems/access-heap.md]] — heap inserts consult the FSM to place
  new tuples (`RelationGetBufferForTuple`).
- [[knowledge/docs-distilled/storage.md]] — the `_fsm` fork in the on-disk file
  layout (§66.3).

## Confidence note

Wiki claims `[from-wiki]`; the FSM-architecture supplement is `[verified-by-code]`
against the per-file corpus (last verified `ef6a95c7c64`; treated current per
STATE.md anchor delta). The pre-8.4 `max_fsm_pages` history is `[verified-by-code]`
from the freespace.c README/comment context, NOT from this wiki page.
</content>
