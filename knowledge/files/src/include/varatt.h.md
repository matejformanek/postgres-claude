# `src/include/varatt.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~542
- **Source:** `source/src/include/varatt.h`

The variable-length-datatype (varlena + TOAST) header machinery. Defines
the three TOAST-pointer flavors (on-disk / in-memory-indirect /
expanded-object), the bit layouts for 1-byte / 4-byte / external
varlena headers (endian-dependent!), and the VARSIZE / VARDATA /
VARATT_IS_* macro family. This file is **load-bearing**: every code
path that touches a `text`/`bytea`/`numeric`/`jsonb`/array goes through
these macros. [verified-by-code]

## Concept

A varlena Datum on a backend is one of five physical forms:
1. **4-byte header, uncompressed** (`VARATT_IS_4B_U`) — first 2 bits
   `00xx` (BE) or `xx00` (LE). Length stored in low 30 bits. Up to
   1 GB.
2. **4-byte header, compressed-in-line** (`VARATT_IS_4B_C`) — first 2
   bits `01xx` (BE) or `xx10` (LE). Compressed payload with
   `va_tcinfo` header field (raw size + compression method bits).
3. **1-byte header, uncompressed-short** (`VARATT_IS_1B` &&
   `!VARATT_IS_1B_E`) — first bit `1xxx` (BE) or `xxx1` (LE). Length
   in 7 bits (max 126 bytes). Saves 3 bytes per small varlena. Always
   unaligned in tuples.
4. **TOAST pointer** (`VARATT_IS_1B_E`) — header byte exactly `0x80`
   (BE) or `0x01` (LE), followed by `va_tag` discriminator. Three
   sub-types:
   - `VARTAG_ONDISK=18` — references `pg_toast.toast_NNNN` row
     (`varatt_external`).
   - `VARTAG_INDIRECT=1` — pointer to in-memory varlena
     (`varatt_indirect`).
   - `VARTAG_EXPANDED_RO=2` / `VARTAG_EXPANDED_RW=3` — pointer to an
     `ExpandedObjectHeader` (`varatt_expanded`).

The first byte's high/low bit (BE/LE) is the universal discriminator;
once a TOAST pointer is recognized, the `va_tag` field carries the
type. The peculiar `VARTAG_ONDISK = 18` value preserves on-disk
compatibility with an older notion where `va_tag` was the pointer
datum's length (`varatt.h:80-82`). [from-comment]

## API / declarations

### Structs

- `varatt_external` (`varatt.h:32-39`) — `va_rawsize` (orig size incl
  header), `va_extinfo` (saved size + compression method bits),
  `va_valueid`, `va_toastrelid`. **MUST contain no padding** (compared
  via memcmp).
- `varatt_indirect { varlena *pointer; }` (`varatt.h:57-60`) — the
  creator owns lifetime of the pointed-to data.
- `varatt_expanded { ExpandedObjectHeader *eohptr; }` (`varatt.h:74-77`).
- `varattrib_4b` union (`varatt.h:126-140`) — `va_4byte { uint32
  va_header; char va_data[]; }` or `va_compressed { uint32 va_header;
  uint32 va_tcinfo; char va_data[]; }`. Union form prevents the
  compiler from generating aligned-access code on 1-byte-header
  paths.
- `varattrib_1b { uint8 va_header; char va_data[]; }` (`varatt.h:142-146`).
- `varattrib_1b_e { uint8 va_header; uint8 va_tag; char va_data[]; }`
  (`varatt.h:149-154`) — TOAST pointer.

### Tag machinery (`varatt.h:84-115`)

- `vartag_external { VARTAG_INDIRECT=1, VARTAG_EXPANDED_RO=2,
  VARTAG_EXPANDED_RW=3, VARTAG_ONDISK=18 }`.
- `VARTAG_IS_EXPANDED(tag)` — `(tag & ~1) == VARTAG_EXPANDED_RO`,
  exploits the specific values 2 and 3 (`varatt.h:94-98`).
- `VARTAG_SIZE(tag)` — dispatches on tag to size of the appropriate
  varatt_* struct; Assert/0 in default case.

### Compression-method bits

- `VARLENA_EXTSIZE_BITS = 30` (`varatt.h:45`).
- `VARLENA_EXTSIZE_MASK = (1U << 30) - 1` — low 30 bits store size.
- High 2 bits identify compression method (`TOAST_PGLZ_COMPRESSION_ID`
  / `TOAST_LZ4_COMPRESSION_ID`).
- `VARATT_EXTERNAL_SET_SIZE_AND_COMPRESS_METHOD(toast_pointer, len,
  cm)` (`varatt.h:520-526`) — macro (NOT static inline; "must remain
  a macro; beware multiple evaluations") with Assert that `cm` is
  pglz or lz4.

### Endian-dependent inner macros (`varatt.h:193-259`)

Two parallel #ifdef WORDS_BIGENDIAN blocks. The pattern: the flag
bits sit in the physically-first byte either way, but BE uses
`& 0xC0` masks while LE uses `& 0x03` masks. Same family on both
sides:

- `VARATT_IS_4B`, `VARATT_IS_4B_U`, `VARATT_IS_4B_C` (4-byte
  uncompressed/compressed),
- `VARATT_IS_1B`, `VARATT_IS_1B_E` (1-byte short / 1-byte external),
- `VARATT_NOT_PAD_BYTE` — non-zero header byte (the 1-byte-zero
  reservation that disambiguates alignment padding from start of
  data, `varatt.h:171-176`),
- `VARSIZE_4B(PTR)`, `VARSIZE_1B(PTR)`, `VARTAG_1B_E(PTR)`,
- `SET_VARSIZE_4B(PTR, len)`, `SET_VARSIZE_4B_C(PTR, len)`,
  `SET_VARSIZE_1B(PTR, len)`, `SET_VARTAG_1B_E(PTR, tag)`.

### VARDATA_* (`varatt.h:261-264`)

`VARDATA_4B`, `VARDATA_4B_C`, `VARDATA_1B`, `VARDATA_1B_E` — return
pointers into the appropriate header struct.

### External-API VAR* family (`varatt.h:276-540`)

The named constants:
- `VARHDRSZ_EXTERNAL = offsetof(varattrib_1b_e, va_data)` — 2 bytes.
- `VARHDRSZ_COMPRESSED = offsetof(varattrib_4b, va_compressed.va_data)`
  — 8 bytes.
- `VARHDRSZ_SHORT = offsetof(varattrib_1b, va_data)` — 1 byte.
- `VARATT_SHORT_MAX = 0x7F` (`varatt.h:279`).
- `VARHDRSZ` is in `c.h:781` = `sizeof(int32) = 4`.

The query macros (all `static inline`, take `const void *PTR`):
- `VARSIZE(PTR)` — known-not-toasted, size incl. 4-byte header.
- `VARDATA(PTR)` — known-not-toasted data start.
- `VARSIZE_SHORT(PTR)`, `VARDATA_SHORT(PTR)` — known-short.
- `VARTAG_EXTERNAL(PTR)` — read the tag byte.
- `VARSIZE_EXTERNAL(PTR)` = `VARHDRSZ_EXTERNAL +
  VARTAG_SIZE(VARTAG_EXTERNAL(PTR))`.
- `VARDATA_EXTERNAL(PTR)`.
- `VARATT_IS_COMPRESSED(PTR)`, `VARATT_IS_EXTERNAL(PTR)`,
  `VARATT_IS_EXTERNAL_ONDISK(PTR)`,
  `VARATT_IS_EXTERNAL_INDIRECT(PTR)`,
  `VARATT_IS_EXTERNAL_EXPANDED_RO/RW/_NON_EXPANDED(PTR)`,
  `VARATT_IS_SHORT(PTR)`, `VARATT_IS_EXTENDED(PTR)`.
- `VARATT_CAN_MAKE_SHORT(PTR)` — true if 4-byte-uncompressed datum
  fits within `VARATT_SHORT_MAX` after re-headering.
- `VARATT_CONVERTED_SHORT_SIZE(PTR)` — that converted size.
- `SET_VARSIZE(PTR, len)`, `SET_VARSIZE_SHORT(PTR, len)`,
  `SET_VARSIZE_COMPRESSED(PTR, len)`, `SET_VARTAG_EXTERNAL(PTR, tag)`.
- `VARSIZE_ANY(PTR)`, `VARSIZE_ANY_EXHDR(PTR)`, `VARDATA_ANY(PTR)` —
  the three "any" macros that dispatch on header type. **Caution**:
  `VARDATA_ANY` returns a possibly-unaligned pointer and won't work
  on external/compressed datums.
- `VARDATA_COMPRESSED_GET_EXTSIZE(PTR)`,
  `VARDATA_COMPRESSED_GET_COMPRESS_METHOD(PTR)` — for in-line
  compressed datums.
- `VARATT_EXTERNAL_GET_EXTSIZE(toast_pointer)`,
  `VARATT_EXTERNAL_GET_COMPRESS_METHOD(toast_pointer)` — for
  on-disk TOAST pointers (note: take a `varatt_external` value,
  not a pointer).
- `VARATT_EXTERNAL_IS_COMPRESSED(toast_pointer)` (`varatt.h:535-540`)
  — extsize < rawsize-VARHDRSZ. "We never use compression unless it
  actually saves space, so we expect either equality or less-than."

## Notable invariants / details

- **Pad bytes MUST be zero** (`varatt.h:176`). The 1-byte-length-word
  encoding "cannot be zero", which is how disambiguation against
  MAXALIGN-padding works. Any code that writes raw bytes into a
  heap tuple must zero the alignment pad. [from-comment]
- **`varatt_external` is stored UNALIGNED in tuples** (`varatt.h:27-29`).
  Code must `memcpy` into a local `varatt_external` variable before
  accessing fields. Direct dereference will SIGBUS on alignment-strict
  platforms (sparc64, some ARM). The reason `memcmp` is used for
  equality: "to avoid having to do that just to detect equality of two
  TOAST pointers" (`varatt.h:29-30`). [from-comment]
- **`varatt_external` MUST have zero padding** so `memcmp` equality
  works. The current layout (int32 + uint32 + Oid + Oid = 16 bytes)
  packs cleanly on every PG-supported platform, but this is brittle.
  [from-comment]
  [ISSUE-undocumented-invariant: no `StaticAssert(sizeof(varatt_external)
  == 16)` to catch accidental padding (likely)]
- **The TOAST-pointer header byte is exactly 0x80 (BE) or 0x01 (LE)**
  — `VARATT_IS_1B_E` tests for the *exact* value, not a masked one.
  This means any varatt_1b with payload starting with that byte is
  AMBIGUOUS — disambiguation relies on the second byte being a
  recognized `va_tag` value (`varatt.h:148`).
- **`VARATT_IS_1B_E` is true for external; VARSIZE_1B returns 0** —
  the warning at `varatt.h:188-190`: "you should usually check for
  IS_EXTERNAL before checking for IS_1B." Confusing this order silently
  zeroes external pointers. [from-comment]
- **`VARTAG_IS_EXPANDED` relies on specific tag values** —
  `VARTAG_EXPANDED_RO=2`, `VARTAG_EXPANDED_RW=3`, so `tag & ~1 == 2`.
  Adding a new tag value of 0 or 1 would break this. [from-comment]
  [ISSUE-undocumented-invariant: vartag_external numbering scheme is
  load-bearing for `VARTAG_IS_EXPANDED` macro (nit)]
- **`SET_VARSIZE_4B_C` does not clear the existing header** — caller
  must construct from scratch or zero first. The macros are
  write-once. [inferred]
- **The compression-method bits in `va_extinfo` are 2 bits** — only
  pglz (0) and lz4 (1) are defined. The Assert in
  `VARATT_EXTERNAL_SET_SIZE_AND_COMPRESS_METHOD` enforces this
  (`varatt.h:521-523`). Adding a third method (zstd was discussed)
  uses bit pattern `10`; a fourth (`11`) would exhaust the space.
  [ISSUE-correctness: only 2 compression-method bits available; zstd +
  pglz + lz4 + 1 more would need an on-disk-format break (maybe)]
- **The two BE vs LE blocks have identical structure but differ in
  shift vs mask** — and the LE shift-by-2 (`varatt.h:243`) means a
  varlena's 4-byte header is endian-dependent on disk. This is *fine*
  because PG datafiles are not portable across endiannesses anyway.
- **`VARATT_NOT_PAD_BYTE` is identical on BE and LE** (`varatt.h:205,
  238`) — just `*(PTR) != 0`. The pad-byte reservation is the only
  cross-endian invariant. [from-comment]
- The macro `VARATT_EXTERNAL_SET_SIZE_AND_COMPRESS_METHOD` is the only
  non-static-inline in the external-API block. Comment at `varatt.h:519`
  says "This has to remain a macro; beware multiple evaluations!" —
  because it needs to compute on `toast_pointer.va_extinfo` as an
  lvalue, which a function-taking-by-value couldn't. [from-comment]

## Potential issues

- `varatt.h:27-29` — unaligned `varatt_external` is the #1 portability
  hazard. New code that adds a TOAST-pointer field MUST memcpy
  through a local. No header-level helper enforces this.
  [ISSUE-correctness: unaligned `varatt_external` access (read or
  write) silently SIGBUS on alignment-strict platforms (confirmed)]
- `varatt.h:175-176` — the "pad bytes are zero" requirement is
  enforced at write-time (`heap_form_tuple` zero-fills) but not at
  read-time. Corrupt tuples with non-zero pad bytes will be
  misparsed as 1-byte-header varlena. [ISSUE-correctness:
  pad-byte-zero invariant has no validity check (maybe)]
- `varatt.h:84-90` — adding new `vartag_external` values requires
  preserving the `VARTAG_IS_EXPANDED` `& ~1 == 2` algebra and
  avoiding collision with `VARTAG_ONDISK = 18`. Header doesn't
  call out a "next available tag" comment. [ISSUE-style:
  vartag_external numbering scheme is undocumented for future
  additions (nit)]
- `varatt.h:519-526` — `VARATT_EXTERNAL_SET_SIZE_AND_COMPRESS_METHOD`
  multi-evaluation hazard is comment-only. A caller passing
  `(*x).va_extinfo` will evaluate `x` twice if the macro is
  ever rewritten.
- `varatt.h:486-489` — `VARDATA_ANY` for external or compressed-in-line
  datums returns garbage. Comment warns ("caution: this will not work
  on an external or compressed-in-line Datum") but provides no Assert.
  [ISSUE-correctness: `VARDATA_ANY` on external/compressed silently
  garbage (likely)]
- `varatt.h:520-526` — Assert on compression method is cassert-only;
  a release build silently encodes invalid `cm` bits. [ISSUE-correctness:
  compression-method bits not validated in release builds (nit)]
- `varatt.h:34` — `va_rawsize` is `int32`, so max raw varlena size is
  ~2 GB. The 30-bit `va_extinfo` external size is 1 GB. Mixing the
  two without checking is a silent error. [ISSUE-doc-drift: 2 GB
  vs 1 GB limit mismatch not flagged (nit)]
- `varatt.h:45-46` — `VARLENA_EXTSIZE_BITS=30` is fixed. The 2-bit
  compression-method field is tight; adding zstd consumed bit `10`.
  Any 5th compression method = on-disk-format break. [ISSUE-stale-todo:
  compression-method bit budget tight (likely)]
- `varatt.h:148-154` — `varattrib_1b_e` is a struct embedding a flexible
  array `va_data[]`. The Assert and offsetof gymnastics in macros are
  all there is; a `sizeof(varattrib_1b_e)` includes only the 2 fixed
  bytes plus alignment padding (compiler-dependent on `char` arrays
  but usually 2). [ISSUE-style: `sizeof(varattrib_1b_e)` semantics not
  documented (nit)]
