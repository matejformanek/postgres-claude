# `src/include/storage/fsm_internals.h`

- **Last verified commit:** `ef6a95c7c64`

## Purpose

Internal interface between freespace.c (cross-page logic) and
fsmpage.c (intra-page tree). Not exposed to AMs.

## Surface

- `SlotsPerFSMPage`, `NonLeafNodesPerPage`, `LeafNodesPerPage`
  constants derived from BLCKSZ.
- `FSMPageData` struct with `fp_next_slot` + `fp_nodes[]`.
- `fsm_search_avail`, `fsm_get_avail`, `fsm_get_max_avail`,
  `fsm_set_avail`, `fsm_truncate_avail`, `fsm_rebuild_page`.

## Tag tally

`[verified-by-code]` 1.
