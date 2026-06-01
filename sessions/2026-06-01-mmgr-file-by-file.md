# 2026-06-01 — utils/mmgr file-by-file deep read

Spec: produce per-file docs at mirrored paths under
`knowledge/files/src/backend/utils/mmgr/` for the 10 .c files + the
README + the principal headers. File-level detail, not subsystem
overview (the latter already exists at `knowledge/idioms/memory-contexts.md`).

## What I read

- README (deep), mcxt.c (deep), aset.c (deep), dsa.c (deep).
- generation.c (read), slab.c (read), bump.c (read), alignedalloc.c
  (read), freepage.c (read — entry points + design comment),
  portalmem.c (read), memdebug.c (read).
- Headers cross-checked: memnodes.h, palloc.h, memutils.h,
  memutils_memorychunk.h, memutils_internal.h, dsa.h.

## What I produced

- `knowledge/files/src/backend/utils/mmgr/README.md` (section-map of
  the canonical design doc, load-bearing facts list).
- `mcxt.c.md` — type-independent API, vtable dispatch invariants,
  iterative `MemoryContextDelete`, `MemoryContextAllocAligned`
  redirection-chunk trick, `ProcessLogMemoryContextInterrupt`
  re-entry guard.
- `aset.c.md` — power-of-two freelists 8 B…8 KB, keeper block,
  process-wide `context_freelists[2]` recycle cache (100 each),
  double-pfree detection via `requested_size==InvalidAllocSize`.
- `generation.c.md`, `slab.c.md`, `bump.c.md`, `alignedalloc.c.md` —
  per-allocator specialty notes.
- `dsa.c.md` — segment/page/superblock/span/pool model, two-tier
  locking (area lock + per-pool LWLock), FATAL-on-FPM-mismatch
  policy, active-block hysteresis.
- `freepage.c.md` — parasitic in-page bookkeeping, btree coalescing.
- `portalmem.c.md` — portal lifecycle, `TopPortalContext`,
  holdContext-is-sibling, transaction-abort handoff.
- `memdebug.c.md` — debug-build helpers (0x7E sentinel, 0x7F clobber,
  randomize_mem).
- Appended 17 rows to `progress/files-examined.md`.

## Flagged as uncertain / future passes

- `mcxt.c`: multi-level-loop detection in `MemoryContextSetParent` is
  *not* done; could silently corrupt the tree.
- `aset.c`: write-past-end of an *exact-fit* power-of-two chunk is
  undetected even under `MEMORY_CONTEXT_CHECKING` (no sentinel).
- `dsa.c`: lock-order audit of the recursive
  `dsa_free(area, span_pointer)` on the large-object free path is
  worth a separate pass; the comments don't state the invariant
  positively.
- `freepage.c`: ~1400 lines of btree split/merge code only skimmed
  in this pass.
- `bump.c`: production builds have *no* chunk header, so any code path
  that lets a bump-allocated pointer reach generic `pfree` will
  dispatch on whatever 4 bits precede the chunk — needs auditing per
  caller, not enforceable centrally.

## Four most surprising facts

1. **`MemoryChunk` is 65 logical bits packed into 64**: the 30-bit
   chunk-size value and the 30-bit block-offset *share* a bit, made
   safe by MAXALIGN forcing the offset's low bit to zero
   (`memutils_memorychunk.h:24-43`, `README:421-435`).
2. **AllocSet caches up to 100 empty contexts per shape**
   (`ALLOCSET_DEFAULT_SIZES` and `ALLOCSET_SMALL_SIZES`) in
   process-wide `context_freelists[2]`. On overflow the *entire*
   freelist is dropped at once on a "recently-allocated are
   probably longer-lived" heuristic (`aset.c:219-241, 648-691`).
3. **Bump contexts have no chunk header in production builds**
   (`Bump_CHUNKHDRSZ = 0`). The chunk header *is* generated under
   `MEMORY_CONTEXT_CHECKING` purely to make stray `pfree` calls
   route to `BumpFree` which `elog(ERROR)`s — that's the whole
   misuse-detection story (`bump.c:52-57, 645-660`).
4. **DSA has two special size classes** (`DSA_SCLASS_BLOCK_OF_SPANS`,
   `DSA_SCLASS_SPAN_LARGE`) to break the chicken-and-egg of "you
   need a span to make a superblock, you need a superblock to make
   a span" — the "block of spans" superblock is itself allocated
   *via* the same machinery, but in a class whose objects are spans
   and which is bootstrapped at area creation (`dsa.c:178-181,
   238-240`).

## Confidence-tag totals across the 11 docs

- `[verified-by-code]` ≈ 116
- `[from-comment]` ≈ 65
- `[from-readme]` ≈ 16
- `[inferred]` ≈ 3
- `[unverified]` ≈ 20

(`unverified` markers concentrated on: cross-file caller behavior
not chased, DSA's deep lock-order audit, freepage's btree internals,
portal/snapshot lifetime edge cases.)
