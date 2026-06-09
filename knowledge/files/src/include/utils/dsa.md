# utils/dsa.h — Dynamic Shared memory Area

Source: `source/src/include/utils/dsa.h` (168 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Cross-backend shared allocator built on top of `dsm` segments. Provides `dsa_pointer` (a relative pointer shareable across processes) plus alloc/free/trim/pin/handle APIs.

## Public API

- `dsa_pointer` type (`dsa.h:52-53` for 32-bit, `61-62` for 64-bit) — uint32 or uint64.
- `dsa_handle` (`dsa.h:136`) = `dsm_handle`.
- `InvalidDsaPointer = 0` (`dsa.h:77-78`); `DSA_HANDLE_INVALID = DSM_HANDLE_INVALID` (`dsa.h:138-139`).
- Allocation flags (`dsa.h:72-75`): `DSA_ALLOC_HUGE` (>1GB), `DSA_ALLOC_NO_OOM` (return InvalidDsaPointer instead of ereport), `DSA_ALLOC_ZERO` (zero memory).
- Segment sizing: `DSA_DEFAULT_INIT_SEGMENT_SIZE = 1MB`, `DSA_MIN_SEGMENT_SIZE = 256KB`, `DSA_MAX_SEGMENT_SIZE = 1 << DSA_OFFSET_WIDTH` (`dsa.h:97-103`).
- Offset width: 27 bits on 32-bit dsa_pointer (32 segments of 128MB), 40 bits on 64-bit (1024 segments of 1TB) (`dsa.h:85-89`).
- Lifecycle: `dsa_create_ext`, `dsa_create_in_place_ext`, `dsa_attach`, `dsa_is_attached`, `dsa_attach_in_place`, `dsa_release_in_place`, `dsa_pin_mapping`, `dsa_detach`, `dsa_pin`, `dsa_unpin`, `dsa_set_size_limit`, `dsa_minimum_size`, `dsa_get_handle` (`dsa.h:141-159`).
- Allocation: `dsa_allocate_extended(area, size, flags)`, convenience `dsa_allocate` / `dsa_allocate0` (`dsa.h:109-114, 160`).
- Free + deref: `dsa_free`, `dsa_get_address` (`dsa.h:161-162`).
- Utilities: `dsa_get_total_size`, `dsa_get_total_size_from_handle`, `dsa_trim`, `dsa_dump` (`dsa.h:163-166`).
- Atomic dsa_pointer ops: `dsa_pointer_atomic_*` (`dsa.h:54-69`) — 32-bit or 64-bit depending on SIZEOF_DSA_POINTER.

## Invariants

- **INV-dsa_pointer-is-relative** [from-comment, `dsa.h:45-49`]: dsa_pointer values are shareable across processes but MUST be converted via `dsa_get_address` before dereferencing in each backend. Cannot be stored as raw pointers.
- **INV-32bit-fallback** [verified-by-code, `dsa.h:37-43`]: if `SIZEOF_SIZE_T == 4 || !PG_HAVE_ATOMIC_U64_SUPPORT || USE_SMALL_DSA_POINTER` → 32-bit dsa_pointer. Imposes ≤4GB total per dsa_area.
- **INV-handle-is-first-segment-dsm-handle** [from-comment, `dsa.h:131-133`]: "currently implemented as the dsm_handle for the first DSM segment ... but client code shouldn't assume that is true." Don't compute handles by hand.
- **INV-segment-growth-doubling** [from-comment, `dsa.h:92-95`]: starts at `init_segment_size`, doubles after each segment until `max_segment_size`. Larger one-shot allocations may bypass doubling.
- **INV-DSA_ALLOC_HUGE-required-for-gt-1GB** [verified-by-code, `dsa.h:73`]: regular `dsa_allocate` fails for size > 1GB unless HUGE flag passed.
- **INV-pin-keeps-mapping-alive** [verified-by-code, `dsa.h:153-155`]: `dsa_pin` ensures the area survives process exit; `dsa_pin_mapping` keeps THIS backend's mapping alive past the surrounding resowner.

## Notable internals

- The atomic ops switch between `pg_atomic_u32` and `pg_atomic_u64` based on `SIZEOF_DSA_POINTER` (`dsa.h:53-69`). Mixing 32-bit dsa_pointer with 64-bit atomic shmem state is a build error.
- `dsa_create` macro (`dsa.h:117-119`) passes default segment sizes — most callers want `dsa_create`, not `dsa_create_ext`.

## Trust-boundary / Phase-D surface

- **A8 handle-prediction hint** [from-corpus]: dsa_handle is exposed (e.g. via `pg_get_shmem_allocations`); a malicious backend that learns the handle of another's dsa could call `dsa_attach` to gain read/write access. The header doesn't surface this as a privilege boundary — it's by convention that handles aren't shared cross-role.
- **A14 autoprewarm dsm_create OOM finding (echo)**: dsa's underlying dsm_create can fail OOM mid-startup; `dsa_create_ext` should be called inside an error-recoverable context.
- **`dsa_get_address` on a foreign dsa_pointer is fatal** — passing a dsa_pointer from area A to `dsa_get_address(area B, dp)` returns a wrong pointer silently. No cross-check.
- **`DSA_ALLOC_NO_OOM` flag is opt-in** — without it, OOM during dsa allocation ereports, which may not be safe in some contexts (e.g. inside a critical section).

## Cross-refs

- `source/src/include/storage/dsm.h` — underlying DSM segment machinery.
- `source/src/backend/utils/mmgr/dsa.c` — implementation.
- `knowledge/files/src/include/utils/freepage.md` — used by DSA internally for span management.

## Issues

- `[ISSUE-SECURITY: handle-prediction privilege boundary undocumented (medium)]` — A8 family. Header should explicitly note that dsa_handles confer access; protect them from cross-role visibility.
- `[ISSUE-INVARIANT: cross-area dsa_pointer dereferences silent (low)]` — `dsa_get_address` has no per-pointer ownership tag; passing dp from area A to area B produces nonsense.
