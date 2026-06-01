# `storage/ipc/shm_toc.c`

- **Source:** `source/src/backend/storage/ipc/shm_toc.c` (279 lines)
- **Header:** `source/src/include/storage/shm_toc.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

**Table of contents inside a shared-memory segment.** Used to publish
sub-region offsets within a DSM segment so multiple processes
(parallel leader + workers) can find named pieces without each
allocating their own DSMs.

Typical layout of a parallel-query DSM segment:

```
[ shm_toc header + entries ] [ subarea1 ] [ subarea2 ] ...
```

The leader allocates each subarea via `shm_toc_allocate` and registers
it under a `key` (uint64) via `shm_toc_insert`. Workers call
`shm_toc_attach(magic, address)` to read the header, then
`shm_toc_lookup(toc, key, noError)` to find each subarea.

## The struct

```c
struct shm_toc {
    uint64        toc_magic;          /* identifies the TOC */
    slock_t       toc_mutex;          /* serializes allocate + insert */
    Size          toc_total_bytes;
    Size          toc_allocated_bytes;
    uint32        toc_nentry;
    shm_toc_entry toc_entry[FLEXIBLE_ARRAY_MEMBER];
};
struct shm_toc_entry { uint64 key; Size offset; };
```

Allocation grows from the *end* of the segment downward
(`toc_allocated_bytes`), entries grow from the *start* upward
(`toc_nentry`). They must not meet.

## API

- `shm_toc_create(magic, addr, nbytes)` — caller-allocated region;
  must be buffer-aligned.
- `shm_toc_attach(magic, addr)` — returns NULL if magic mismatches
  (caller can verify).
- `shm_toc_allocate(toc, nbytes)` — bump allocator (from the tail);
  spinlock-protected. PG-cache-line aligned.
- `shm_toc_freespace(toc)` — for capacity planning.
- `shm_toc_insert(toc, key, address)` — atomic via spinlock.
- `shm_toc_lookup(toc, key, noError)` — linear scan over entries.
  Workers usually call this after `shm_toc_attach`.
- `shm_toc_estimate(estimator)` / `shm_toc_estimate_chunk` etc. —
  pre-compute the total size needed before creating the segment.

## Cross-references

- `access/parallel.c` — the canonical consumer. Each parallel context
  is one DSM + one TOC with keys for: fixed-data, plan tree state,
  TupleQueue (`shm_mq`) per worker, error queue, instrumentation, etc.
- `dsm.c` — usually creates the underlying segment.

## Open questions

The `shm_toc_lookup` linear scan is O(nentries) per call. For typical
parallel-query TOCs (≤ 20 entries) this is fine, but a hash variant
would be needed for high entry counts. `[inferred]` — no comment in
the file justifies the design choice explicitly.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
