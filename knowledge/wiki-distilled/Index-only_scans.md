---
source_url: https://wiki.postgresql.org/wiki/Index-only_scans
fetched_at: 2026-06-03T19:50:00Z
wiki_last_edited: 2016-07-06
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: page is from 2016 (PG 9.2-era framing) but the core mechanism — the
  visibility-map gate — is unchanged through PG18. Supplemented below with
  [verified-by-code] facts from the corpus (visibilitymap.c, access-nbtree).
---

# Wiki distilled — Index-only scans

Why an index scan can sometimes skip the heap entirely, and the one thing that
makes it *correct*: the visibility map. Companion: the page-format and VM detail
in `knowledge/docs-distilled/storage.md`.

## What the wiki page says

- **Index-only scans landed in PostgreSQL 9.2.** They let a query satisfy its
  output from the index alone, avoiding the heap fetch and its random I/O.
  [from-wiki]
- **The hard problem was MVCC visibility.** An index entry carries no
  xmin/xmax — "it is not directly possible to ascertain if any given tuple is
  visible to the current transaction." That is *why* index-only scans took so
  long to implement: the index knows the value but not whether the row version is
  visible. [from-wiki]
- **The visibility map (VM) is the answer.** The planner/executor may skip the
  heap for a given page *only* when that page's VM `ALL_VISIBLE` bit is set —
  meaning every tuple on the page is visible to all transactions, so visibility
  needn't be re-checked per tuple. If the bit is clear, the executor falls back to
  a heap fetch for that tuple. [from-wiki]
- **AM support is uneven:** B-tree fully supports it (advertised via the
  `btcanreturn` flag in `pg_am`); SP-GiST supports it for some opclasses only;
  GiST and GIN do not. [from-wiki]
- **EXPLAIN tells you the cost you didn't avoid:** an `Index Only Scan` node
  reports a **`Heap Fetches`** counter — the number of times the VM bit was *not*
  set and a heap visit was needed anyway. High `Heap Fetches` means the table is
  under-vacuumed for this access pattern. [from-wiki]
- **Covering indexes** exist expressly to feed index-only scans: extra columns
  carried in the index (today via `INCLUDE`) so the SELECT list is fully
  satisfied without the heap. [from-wiki]
- **HOT tension:** updating only non-indexed columns keeps a row HOT-eligible
  (no new index tuple). Adding columns to an index to make it "covering" can
  *reduce* HOT opportunities, because more columns are now indexed. [from-wiki]
- **The planner estimates the payoff from `pg_class.relallvisible`** — the
  fraction of pages marked all-visible, which **VACUUM** maintains. A table that
  is never vacuumed gets few index-only scans even with a perfect covering index.
  [from-wiki]

## Corpus supplement — the load-bearing mechanism

- **The VM is a separate relation fork, 2 bits per heap page:**
  `VISIBILITYMAP_ALL_VISIBLE = 0x01` and `VISIBILITYMAP_ALL_FROZEN = 0x02` (the
  latter for vacuum freeze-skipping, added 9.6). `ALL_FROZEN` may be set only if
  `ALL_VISIBLE` is also set. [verified-by-code,
  source/src/backend/access/heap/visibilitymap.c — bit constants live in
  `visibilitymapdefs.h`; ALL_FROZEN⇒ALL_VISIBLE rule at visibilitymap.c header,
  via knowledge/files/src/backend/access/heap/visibilitymap.c.md]
- **The set bit is authoritative; the cleared bit is "unknown".** The VM is a
  conservative hint in one direction only: a set `ALL_VISIBLE` is a hard
  guarantee, but a clear bit means "maybe not all-visible — go check the heap."
  This asymmetry is exactly what makes the index-only fast path safe. [from-comment,
  visibilitymap.c:1-95 header block]
- **PD_ALL_VISIBLE ↔ VM bit must stay in lockstep.** There is an implicit
  dependency between the heap page's `PD_ALL_VISIBLE` flag and the VM bit; the
  crash-recovery rules (a *clear* must replay before the heap page reaches disk;
  a *set* must replay if the VM page reached disk first) are what keep an
  index-only scan from ever reading a stale "all-visible". [from-comment,
  visibilitymap.c:1-95]
- **B-tree's `amcanreturn`** is what the planner consults to know the index can
  reconstruct the indexed columns for an index-only scan. [verified-by-code, via
  knowledge/subsystems/access-nbtree.md]

## Why it matters operationally

- The lever for index-only-scan performance is **VACUUM frequency**, not index
  design: the VM bits go stale on every update/delete, and only VACUUM (or
  autovacuum) re-sets them. A read-mostly table that is rarely vacuumed shows
  high `Heap Fetches` and loses most of the benefit. [inferred, from-wiki]
- A bulk load → first scan leaves VM bits unset (same root cause as the hint-bit
  "second query writes everything" story); an explicit `VACUUM` after load
  front-loads both the hint bits and the VM. [inferred — cross-link
  `knowledge/wiki-distilled/Hint_Bits.md`]

## Links into corpus

- [[knowledge/files/src/backend/access/heap/visibilitymap.c.md]] — VM fork
  implementation: bit semantics, the unlock-pin-relock race window (797-812), the
  crash-safety rules in the 95-line header.
- [[knowledge/files/src/include/access/visibilitymap.h.md]] — VM API surface.
- [[knowledge/subsystems/access-nbtree.md]] — `btcanreturn`/`amcanreturn` and how
  B-tree reconstructs indexed columns for the scan.
- [[knowledge/subsystems/access-heap.md]] — VACUUM sets the VM bits this fast path
  depends on.
- [[knowledge/docs-distilled/storage.md]] — `PD_ALL_VISIBLE` page-header flag that
  must agree with the VM bit.
- [[knowledge/wiki-distilled/Hint_Bits.md]] — the sibling "VACUUM-maintained
  metadata that read paths depend on" story.

## Confidence note

Wiki claims tagged `[from-wiki]`; every symbol/invariant supplement is
`[verified-by-code]` or `[from-comment]` against the per-file corpus (last
verified `ef6a95c7c64`; treated current per STATE.md anchor delta). The
"VACUUM-frequency is the real lever" framing is `[inferred]` from the
relallvisible + VM-maintenance facts.
</content>
