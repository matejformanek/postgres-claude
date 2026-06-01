# `src/backend/storage/freespace/fsmpage.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~340
- **Source:** `source/src/backend/storage/freespace/fsmpage.c`

## Purpose

Operates on a single FSM page as a black box of `SlotsPerPage` slots,
hiding the binary-heap layout used internally. Lets freespace.c treat
each FSM page uniformly whether it's a leaf or an internal-level
page. [from-comment] (`fsmpage.c:13-21`)

## Top of file

The in-page binary tree is stored as an array; helpers
`leftchild(x)=2x+1`, `rightchild(x)=2x+2`, `parentof(x)=(x-1)/2`
encode the addressing. `rightneighbor` handles wrap-around at the
right edge of a level (lines 36–55).

## Public surface (fsm_internals.h)

- `fsm_search_avail(buf, minvalue, advancenext, exclusive_lock_held)
  → int` — slot index with value ≥ minvalue, or -1.
- `fsm_get_avail(page, slot) → uint8`
- `fsm_get_max_avail(page) → uint8` — root of in-page tree.
- `fsm_set_avail(page, slot, value) → bool` — returns whether page
  was modified; bubbles up.
- `fsm_truncate_avail(page, nslots) → bool` — drop trailing slots
  (FSM-truncate support).
- `fsm_rebuild_page(page) → bool` — rebuild internal nodes from
  leaves (corruption-repair path called by freespace.c).

## Invariants

- Internal nodes always equal max of children. `fsm_rebuild_page`
  restores this when freespace.c detects violation.
- Caller responsible for buffer locking — shared for read functions
  (`fsm_get_avail`, `fsm_search_avail` without update), exclusive for
  `fsm_set_avail`. The `fp_next_slot` field can be updated under
  shared lock (intentional race, README justifies).

## Cross-refs

- Called by freespace.c only.

## Tag tally

`[from-comment]` 3 / `[from-README]` 2 / `[verified-by-code]` 1.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
