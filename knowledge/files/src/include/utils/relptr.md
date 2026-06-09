# `src/include/utils/relptr.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Macros for *relative pointers* — stored as `Size` offsets from a
base address, suitable for living inside a DSM segment mapped at
different virtual addresses in different backends [from-comment:
lines 17-24].

## Public API

[verified-by-code: lines 29-83]

- `relptr(type)` — declare an inline relative-pointer field.
- `relptr_declare(type, relptrtype)` — preferred typedef form
  (pgindent gets confused by the inline `relptr(...)`)
  [from-comment: lines 31-34].
- `relptr_access(base, rp)` — dereference; uses `__typeof__` for
  type safety when available, falls back to `void *`.
- `relptr_is_null(rp)` — true iff stored offset is 0.
- `relptr_offset(rp)` — extract underlying offset minus 1 (the
  bias).
- `relptr_store(base, rp, val)` — store with type check (when
  `HAVE_TYPEOF`); NULL maps to offset 0.
- `relptr_copy(rp1, rp2)` — copy without dereferencing.

Static asserts: `base` argument must be `char *`
(`StaticAssertVariableIsOfTypeMacro`).

## Invariants

- **INV-BIAS** [verified-by-code: lines 61-69 (`relptr_store_eval`)
  and line 44 (`relptr_access`)] Offsets are stored *plus one* —
  the value 0 is reserved for NULL; the bias is added on store,
  subtracted on access. `val >= base` is asserted.
- **INV-BASE-TYPE** Base must be `char *` so pointer arithmetic is
  well-defined.
- **INV-SAME-SEGMENT** [inferred] Storing a pointer that lies
  outside the segment whose base is later used to access it is a
  silent bug; no runtime check.
- **INV-NO-PADDING** Relptr is a `union { type *; Size }` — the
  pointer arm exists only for type tracking, never read.

## Trust boundary (Phase D)

- Relative pointers are a *unsafe* primitive in the sense that
  there is no runtime check that the offset stays inside the
  segment whose `base` is supplied at dereference time. A corrupt
  shared-memory area or a base-pointer mix-up between segments will
  silently produce a wild pointer.
- Used throughout `freepage.h`, DSA chunks, parallel hash join
  partitions. Any out-of-bounds offset planted by a buggy writer
  can be triggered by *any* reader sharing the segment.

## Cross-refs

- `utils/dsa.h` — primary user via `dsa_pointer`.
- `utils/freepage.h` — uses `relptr_declare` widely.
- `executor/hashjoin.h` — parallel hash join chunk lists use
  `dsa_pointer` (a related but separate scheme).

## Issues

- [ISSUE-DESIGN: no runtime bound check on offset; relies on writer
  discipline. Corrupted offsets are undiagnosable without
  per-segment guards (low — this is by design for speed, but
  worth tagging)] — lines 41-50.
- [ISSUE-PORT: non-`HAVE_TYPEOF` path drops the type check on
  `relptr_store` (line 77-79) — store of mismatched pointer types
  is silently accepted on toolchains without `__typeof__` (low —
  in practice all supported PG toolchains have it)] — lines 76-80.
