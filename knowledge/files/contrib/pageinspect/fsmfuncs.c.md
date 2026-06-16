# fsmfuncs.c

Covers `source/contrib/pageinspect/fsmfuncs.c` (66 lines): the
FSM-page dumper. Smallest file in pageinspect.

## One-line summary

`fsm_page_contents(bytea)` walks a Free Space Map page and emits a
text blob "node_idx: value\nnode_idx: value\n…fp_next_slot: N" for
every non-zero node and the next-slot pointer.

## Public API / entry points

- `fsm_page_contents(bytea raw_page)` —
  `source/contrib/pageinspect/fsmfuncs.c:35`.

## Key invariants

- INV-1: `superuser()` gate at `:43` [verified-by-code]. Same error
  wording as the rest of pageinspect.
- INV-2: New pages → NULL (`:50`).
- INV-3: No special-space-size check — FSM pages don't have a
  special area in the way AM pages do. The function reads
  `PageGetContents(page)` (`:53`) which is the area after
  `PageHeader` up to `pd_special`.
- INV-4: Iteration is bounded by `NodesPerPage` (`:57`), a compile-
  time constant from `storage/fsm_internals.h`.

## Notable internals

**No type checks at all.** Unlike every per-AM file, fsmfuncs does
NOT validate that the bytea actually came from an FSM fork. The
file-level comment (`:6-11`) acknowledges this: "These functions
are restricted to superusers for the fear of introducing security
holes if the input checking isn't as water-tight as it should."

A bytea from a heap or btree page passed in here will:
- Cast `PageGetContents(page)` to `FSMPage` (`:53`).
- Iterate `NodesPerPage` (a constant ~4080) entries, reading uint8
  bytes that happen to live at those offsets.
- Print non-zero ones with no validation that they make semantic
  sense.

This is intentional dump-mode behavior. No crash because the read is
bounded by `PageGetContents(page) + NodesPerPage * sizeof(uint8)`,
which is `< BLCKSZ`.

**`fp_next_slot` print at the end.** `:62`: prints the slot pointer
unconditionally. Same out-of-page-context guarantee.

## Trust boundary / Phase D surface

**Lowest-impact pageinspect function.** FSM contents are aggregate
free-space estimates, not row data. There's no RLS data here — FSM
nodes are uint8 estimates of free bytes per page in the
corresponding heap range. No bypass surface.

**Mis-identification produces noise, not crashes.** Feeding a heap
bytea: you get a screenful of "node_idx: value" lines computed from
heap-payload bytes interpreted as FSM nodes. Confusing, not
dangerous.

**Buffer-overflow surface.** Zero — the iteration is bounded by a
compile-time constant smaller than BLCKSZ and the page is exactly
BLCKSZ from `get_page_from_raw`. No on-page bytes are used as
lengths or offsets.

**CONCURRENTLY index inspection.** FSM is per-relation (or per-fork);
the bytea is detached; concurrent VACUUM that updates the FSM tree
doesn't affect the snapshot.

## Cross-references

- `source/src/include/storage/fsm_internals.h` — `FSMPage`,
  `NodesPerPage`, `fp_nodes`, `fp_next_slot`.
- `source/src/backend/storage/freespace/freespace.c` — the FSM
  writer side; this file's reader complements it.
- `source/src/backend/storage/freespace/README` — the data
  structure (a max-aggregating binary tree of free-space estimates).
- `knowledge/files/contrib/pageinspect/pageinspect.md` — bytea
  source; users typically obtain FSM pages via
  `get_raw_page_fork('tbl', 'fsm', N)`.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-defense-in-depth: no "is this actually an FSM page"
  check; mis-identified input produces confusing-but-harmless
  output (nit; documented design choice)]** —
  `source/contrib/pageinspect/fsmfuncs.c:53`.
