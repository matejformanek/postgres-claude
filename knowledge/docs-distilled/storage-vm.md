---
source_url: https://www.postgresql.org/docs/current/storage-vm.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §65.4: Visibility Map

A tiny side-fork that makes index-only scans and anti-wraparound VACUUM cheap.
The corpus already touches the VM in `knowledge/wiki-distilled/Index-only_scans.md`;
this is the canonical docs section, distilled for the **two-bit semantics and the
conservative-direction invariant** that anyone touching `heap_*`/VACUUM must hold.

## What it is

- A per-relation **`_vm` fork** (e.g. heap filenode `12345` → `12345_vm`), in the
  same directory as the main fork. **Indexes have no VM.** [from-docs]
  [verified-by-code, source/src/backend/access/heap/visibilitymap.c]
- **Two bits per heap page:** all-visible and all-frozen
  (`VISIBILITYMAP_ALL_VISIBLE`, `VISIBILITYMAP_ALL_FROZEN`). [from-docs]
  [verified-by-code, source/src/include/access/visibilitymap.h — the flag macros;
  via knowledge/wiki-distilled/Index-only_scans.md]

## What each bit buys

- **all-visible** = every tuple on the page is visible to all current
  transactions and none needs vacuuming. Enables: (a) **index-only scans skip the
  heap visibility check** for tuples on that page; (b) **VACUUM skips the page**.
  [from-docs] [cross: knowledge/docs-distilled/indexes-types.md]
- **all-frozen** = every tuple on the page is frozen. Enables **anti-wraparound
  (aggressive) VACUUM to skip the page** entirely — the key to bounding freeze
  cost on large append-mostly tables. [from-docs]

## The invariant that makes it safe (conservative direction)

- **A set bit is a promise; a clear bit is "don't know".** If all-visible is set,
  the page is *definitely* all-visible. If clear, it *might or might not* be — the
  **heap is the source of truth**, the VM is only a fast-path hint. All
  correctness reasoning must treat a clear bit as the conservative default and
  re-check the heap. [from-docs]
- **Set only by VACUUM; cleared by any modifying operation** on the page
  (insert/update/delete, and row locking that could change visibility). The
  asymmetry (slow to set, eager to clear) is what keeps the promise true.
  [from-docs] [verified-by-code, source/src/backend/access/heap/heapam.c clears
  the VM bit on modification; via knowledge/subsystems/access-heap.md]

## Crash-safety note

- The VM is **WAL-logged** so the all-visible/all-frozen promises survive crash
  recovery; a torn or stale VM bit would otherwise break the index-only-scan
  correctness guarantee. [from-comment] [verified-by-code,
  source/src/backend/access/heap/visibilitymap.c — `visibilitymap_set` takes an
  XLogRecPtr; via knowledge/subsystems/access-heap.md] — re-verify exact WAL
  record type on a future direct read.

## Links into corpus

- [[knowledge/wiki-distilled/Index-only_scans.md]] — the VM bit is what lets an
  index-only scan skip the heap.
- [[knowledge/subsystems/access-heap.md]] — where VM bits are set/cleared.
- [[knowledge/architecture/mvcc.md]] — visibility + freezing, the concepts the VM
  caches.
- [[knowledge/docs-distilled/mvcc.md]] / [[knowledge/docs-distilled/storage.md]].

## Gaps / follow-ups

- No per-file corpus doc yet for `src/backend/access/heap/visibilitymap.c`; the
  WAL-logging and clear-on-modify cites are pointer-level and should be pinned to
  file:line on a direct read (would also confirm the exact set/clear WAL record
  and the `VISIBILITYMAP_VALID_BITS` mask).
