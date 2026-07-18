# `storage/shm_toc.h`

- **Source:** `source/src/include/storage/shm_toc.h` (58 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Opaque-pointer API for the shared-memory table of contents. See
`shm_toc.c.md`.

The header warns that "this is not intended to scale to a large number
of keys and will perform poorly if used that way" (`:11-13`). Lookups
are linear; typical use is ≤ 20 keys per TOC.

## Estimator

```c
shm_toc_estimator e;
shm_toc_initialize_estimator(&e);
shm_toc_estimate_chunk(&e, sizeof(MyFixed));
shm_toc_estimate_chunk(&e, mq_size);
shm_toc_estimate_keys(&e, 2);
Size total = shm_toc_estimate(&e);
```

Used by `access/parallel.c` to size the DSM segment correctly.

`BUFFERALIGN` is applied to each chunk (cache-line padding for
performance + atomicity of cache-line-sized fields).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)
