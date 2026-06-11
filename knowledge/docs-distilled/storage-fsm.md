---
source_url: https://www.postgresql.org/docs/current/storage-fsm.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §66.3: Free Space Map (FSM)

The `_fsm` fork that lets an inserter find a page with room without scanning the
heap. Short chapter; the real mechanics live in
`src/backend/storage/freespace/README`, which the corpus already mirrors.

## What the fork is [from-docs]

- Each heap and each index has an associated **Free Space Map**, stored in a
  separate fork named `<filenode>_fsm` in the same directory as the main fork.
  [verified-by-code, source/src/common/relpath.c — `forkNames[]` maps
  `FSM_FORKNUM` → "fsm"; via knowledge/files/src/common/relpath.c.md]
- **Hash indexes are the exception** — they do not maintain an FSM. [from-docs]
- It tracks, per main-fork page, *approximately* how much free space remains, so a
  tuple insert can locate a target page cheaply. "Approximate" matters: the FSM is
  a hint and is allowed to be stale (out of date / over-optimistic). [from-docs]

## Tree structure [from-docs]

- The FSM is a **tree of FSM pages**. The bottom level stores **one byte per
  main-fork page** — a quantized free-space *category*, not an exact byte count.
- Within each FSM page is a binary tree stored as an array (one byte per node).
  Each **leaf** corresponds to one heap/index page (bottom level) or to a
  lower-level FSM page (upper levels).
- Each **non-leaf node holds the maximum of its children**, so the page's root
  byte is the max free space reachable through that FSM page. A search for "a page
  with ≥ N free space" walks down from the root following children whose value
  ≥ N — O(height), not O(npages). [from-docs]
  [verified-by-code, source/src/backend/storage/freespace/README; via
  knowledge/files/src/backend/storage/freespace/README.md and fsmpage.c.md]

## How it's maintained [from-docs, inferred]

- The category byte is a quantization of free space (the README/`fsm_internals.h`
  define the category granularity), so small free-space changes don't churn the
  FSM. [verified-by-code, source/src/include/storage/fsm_internals.h; via
  knowledge/files/src/include/storage/fsm_internals.h.md]
- **VACUUM** rebuilds/updates FSM leaf values for the pages it processes and runs
  an `fsm_vacuum` pass to propagate corrected maxima up the tree; **inserts**
  update the leaf for the page they extend/fill. The FSM is *not* WAL-logged in
  full and can be rebuilt — a torn/stale FSM costs efficiency, never correctness.
  [inferred from README; the not-fully-WAL-logged property is the reason a stale
  FSM is tolerable]

## Inspection [from-docs]

- The `pg_freespacemap` contrib module exposes the per-page free-space bytes and
  the FSM tree, for debugging bloat / fill-factor questions. [from-docs]

## Links into corpus

- [[knowledge/files/src/backend/storage/freespace/README.md]] — the authoritative
  algorithm (category encoding, search, fsm_vacuum).
- [[knowledge/files/src/backend/storage/freespace/freespace.c.md]] — the public
  API (`GetPageWithFreeSpace`, `RecordPageWithFreeSpace`, `FreeSpaceMapVacuum`).
- [[knowledge/files/src/backend/storage/freespace/fsmpage.c.md]] — the in-page
  binary-tree search/update.
- [[knowledge/files/src/include/storage/fsm_internals.h.md]] — category constants.
- [[knowledge/docs-distilled/storage-file-layout.md]] — where the `_fsm` fork sits
  on disk.
- [[knowledge/wiki-distilled/Free_Space_Map_Problems.md]] — historical pre-8.4
  FSM-as-shared-memory design and why the per-relation fork replaced it.

## Gaps / follow-ups

- The chapter is deliberately thin; exact category boundaries and the
  `MaxFSMRequestSize` clamp are only in the README + `fsm_internals.h`. The "stale
  FSM is correctness-safe" claim is inferred from the not-WAL-logged design — a
  direct read of `freespace.c`'s redo/extend paths would pin it `[verified-by-code]`.
