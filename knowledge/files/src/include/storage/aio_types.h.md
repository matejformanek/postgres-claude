---
path: src/include/storage/aio_types.h
anchor_sha: 4b0bf0788b0
loc: 137
depth: deep
---

# aio_types.h

- **Source path:** `source/src/include/storage/aio_types.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 137

## Purpose

The low-`#include`-burden type header for the PG18 AIO subsystem: the
handful of AIO types that callers need to *declare* fields without
pulling in the full `aio.h` interface. Defines the opaque handle
typedef, the cross-process **wait reference**, the per-target data
union, and the compact **result** encoding. [from-comment, aio_types.h:1-13]

## Public symbols

| Symbol | Kind | Line | Notes |
|---|---|---|---|
| `PgAioHandle` | opaque typedef | `aio_types.h:22` | full struct in `aio_internal.h` |
| `PgAioHandleCallbacks` | opaque typedef | `aio_types.h:23` | defined in `aio.h` |
| `PgAioTargetInfo` | opaque typedef | `aio_types.h:24` | defined in `aio.h` |
| `PgAioWaitRef` | struct | `aio_types.h:32` | `{aio_index, generation_upper, generation_lower}` |
| `PgAioTargetData` | union | `aio_types.h:61` | per-target identity; only `smgr` arm today |
| `PgAioResultStatus` | enum | `aio_types.h:78` | UNKNOWN/OK/PARTIAL/WARNING/ERROR |
| `PgAioResult` | struct (8 bytes) | `aio_types.h:99` | bitpacked `id:6 / status:3 / error_data:23` + `int32 result` |
| `PgAioReturn` | struct | `aio_types.h:130` | `PgAioResult` + `PgAioTargetData` |

## Invariants & gotchas

- **`PgAioResult` MUST be exactly 8 bytes** and the three bitfields
  MUST sum to 32 — two `StaticAssertDecl`s enforce both
  (aio_types.h:117-122). It is embedded in every `PgAioHandle` *and*
  every `PgAioReturn`, so its size is load-bearing for shared-memory
  footprint. A new callback that needs >23 bits of `error_data` cannot
  use this path without widening the struct everywhere.
  [verified-by-code, aio_types.h:91-122]
- **`error_data` semantics are defined by the callback's `report`
  function**, not globally (aio_types.h:110). The same 23-bit field
  means different things per `PgAioHandleCallbackID`. Decoding it
  without knowing `id` is meaningless.
- **The generation is split into two `uint32`s** (`generation_upper` /
  `generation_lower`) specifically to avoid requiring int64 alignment
  in the wait reference, so a `PgAioWaitRef` can live in arbitrarily
  aligned local or shared memory and be passed across process
  boundaries (aio_types.h:37-46). Reassemble with
  `(upper << 32) | lower` — see `pgaio_io_from_wref` (aio.c:899).
- **`PgAioTargetData` is a union with one arm today** (`smgr`,
  aio_types.h:63-71). The `forkNum:8` / `is_temp:1` / `skip_fsync:1`
  bitfields are packed to keep the handle small. Adding a WAL target
  (the README anticipates one) adds a second union arm here.
- **`status` of an enum stored in a 3-bit field**: the comment
  (aio_types.h:101-104) warns that `id` can't be a bitfield of the
  `PgAioHandleCallbackID` enum because some compilers treat enums as
  signed — so it's a `uint32` bitfield carrying the enum value.

## Cross-refs

- Full interface: `knowledge/files/src/include/storage/aio.h.md`.
- Internal handle struct: `knowledge/files/src/include/storage/aio_internal.h.md`.
- Result production: `aio_callback.c::pgaio_io_call_complete_shared`.
- Result reporting: `aio_callback.c::pgaio_result_report`.

## Tally

`[verified-by-code]=4 [from-comment]=3 [inferred]=0`
