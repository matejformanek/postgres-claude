# `src/include/access/visibilitymapdefs.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**26 lines.**

## Role

Definitions only — no functions. Pulls out the bit-layout constants
of a visibility map page so they can be included by both `vm.c`
implementation and external readers (e.g. `pg_visibility` contrib) without
dragging in `visibilitymap.h`'s full API.
[verified-by-code] `source/src/include/access/visibilitymapdefs.h:1-12`

## Public API

Four constants (lines 17-23):
- `BITS_PER_HEAPBLOCK = 2` — two VM bits encode the state of one
  heap block.
- `VISIBILITYMAP_ALL_VISIBLE = 0x01` — bit 0 of the pair: "all tuples
  on this heap block are visible to all active snapshots".
- `VISIBILITYMAP_ALL_FROZEN = 0x02` — bit 1 of the pair: "all tuples
  on this heap block are frozen (no xid older than the freeze
  cutoff)".
- `VISIBILITYMAP_VALID_BITS = 0x03` — mask of both valid bits.

## Invariants

- **INV-vm-bits-per-block:** exactly 2 bits per heap block. Header
  comment: "Number of bits for one heap page" (line 16). [verified-by-code]
- **INV-vm-bit-pair-semantics:**
  - `ALL_VISIBLE` set ⇒ index-only scans can skip heap lookups for
    this block, and `xmin`/`xmax` of tuples on the block are committed.
  - `ALL_FROZEN` set ⇒ vacuum can skip this block in
    aggressive/freeze passes.
  - `ALL_FROZEN` set REQUIRES `ALL_VISIBLE` set (frozen implies
    visible). [inferred from semantics, code-cited in visibilitymap.c]
- A heap block's two VM bits live in the VM page at bit offset
  `(blockno % HEAPBLOCKS_PER_PAGE) * 2`, where `HEAPBLOCKS_PER_PAGE`
  is computed elsewhere (in `visibilitymap.c`) as
  `(BLCKSZ - SizeOfPageHeaderData) * 8 / BITS_PER_HEAPBLOCK`.
  [verified-by-code, in visibilitymap.c not this header]

## Notable internals

The header is deliberately split out (note the 2021 copyright) from the
full `visibilitymap.h` to allow header-only consumers — most notably the
`pg_visibility` contrib module, which renders the bit pairs to SQL.

## Trust-boundary / Phase D surface

**A14 finding anchor:** `pg_truncate_visibility_map(regclass)` accepts
system-catalog OIDs without restriction. A SUPERUSER (or holder of the
`pg_write_server_files` role) can truncate the VM of `pg_class`,
`pg_attribute`, etc., causing subsequent index-only scans to revert to
heap fetches — performance pothole, but also forces the next vacuum
into a full visibility resweep. Header-level: the VM bit semantics
documented here are the **invariants pg_truncate_visibility_map
destroys** — every cleared bit means "ALL_VISIBLE not known", which
forces heap re-inspection.

Header-level Phase-D claim: **the VM is advisory cache, not source of
truth**. The source of truth is per-tuple `xmin/xmax/infomask`. A
corrupt or zeroed VM never causes incorrect SQL results, only
performance loss. (The exception: index-only scans trust ALL_VISIBLE
without re-checking heap, but they still respect snapshot
visibility — they just skip the heap fetch.)

Cross-link to A8/A14 SLRU wraparound: `ALL_FROZEN` is the *only* state
that prevents an aggressive freeze pass from re-reading the block. If
freezing is broken (e.g. multixact wraparound, `vacuum_freeze_min_age`
misconfig), `ALL_FROZEN` bits going stale is the visible symptom.

## Cross-refs

- `access/visibilitymap.h` — full API (`visibilitymap_set`,
  `visibilitymap_get_status`, etc.).
- `contrib/pg_visibility/pg_visibility.c` — header consumer.
- `subsystems/access-heap.md` (if/when written) — heap+VM interaction.
- `subsystems/vacuum.md` (if/when written) — freeze cutoffs.

## Issues

- **ISSUE-A14**: this is the header anchor for the A14
  `pg_truncate_visibility_map` no-restriction finding. The header
  itself doesn't describe the trust model; the policy lives in
  `pg_visibility.c`.
- **ISSUE-doc**: no formula here for "heap blocks per VM page" —
  has to be reconstructed from `visibilitymap.c`.
