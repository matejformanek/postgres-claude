# `src/include/storage/buf.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 46

## Role

Basic buffer identifier types. `Buffer` is a signed `int`:

- `0` = `InvalidBuffer`
- `> 0` = index 1..NBuffers into shared buffer pool
- `< 0` = index -1..-NLocBuffer into the backend's local
  (temp-table) buffer pool

[verified-by-code] `source/src/include/storage/buf.h:17-37`

Also forward-declares `BufferAccessStrategy` (impl is in
freelist.c).

## Invariants

- INV-1: sign of `Buffer` discriminates shared vs local —
  `BufferIsLocal(b) := b < 0`. Cannot be changed without touching
  every buffer consumer.
- INV-2: 0 is reserved invalid — also propagated by `bufmgr.h`'s
  `BufferIsValid`, which additionally asserts in-range.

## Trust boundary (Phase D)

None — opaque integer.

## Cross-refs

- `knowledge/files/src/include/storage/bufmgr.h.md` — the API on
  top
- `knowledge/files/src/include/storage/buf_internals.h.md`
  (existing) — descriptor layout

## Issues

None.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-buffer.md](../../../../subsystems/storage-buffer.md)
