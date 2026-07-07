# varatt / varlena — the on-disk varlena header zoo

TOAST is built on a four-way classification of varlena headers
encoded in the first 1-2 bytes of every variable-length datum. The
header tells the reader: am I a plain 4-byte-length value, an
inline-compressed 4-byte value, a 1-byte-length short value (for
small strings), or a 1-byte "TOAST pointer" referencing external
storage / indirect memory / an expanded object? The tag byte
discriminates further: `VARTAG_ONDISK` for the canonical
toast-table reference, `VARTAG_INDIRECT` for in-memory aliasing,
`VARTAG_EXPANDED_RO` / `_RW` for the writable expanded-object
machinery (arrays, ranges). All TOAST behavior — compression,
out-of-line storage, slicing — keys off this taxonomy.

Anchors:
- `source/src/include/varatt.h:32-39` — varatt_external struct
  [verified-by-code]
- `source/src/include/varatt.h:57-60` — varatt_indirect
  [verified-by-code]
- `source/src/include/varatt.h:74-77` — varatt_expanded
  [verified-by-code]
- `source/src/include/varatt.h:84-90` — vartag_external enum
  [verified-by-code]
- `source/src/include/varatt.h:126-154` — varattrib_4b / 1b / 1b_e
  [verified-by-code]
- `source/src/include/varatt.h:228-258` — little-endian header
  bit-layout macros [verified-by-code]
- `knowledge/idioms/toast-chunk-write.md` — companion
- `knowledge/idioms/detoast-stream-consumption.md` — companion
- `.claude/skills/catalog-conventions.md` — companion

## The four header shapes

| Shape | First-byte signature (LE) | Meaning |
|---|---|---|
| 4-byte uncompressed | `xxxxxx00` | Plain large datum; up to 1 GB |
| 4-byte compressed | `xxxxxx10` | Inline-compressed; up to 1 GB |
| 1-byte short | `xxxxxxx1` (x not all 0) | Up to 126-byte datum, unaligned |
| 1-byte TOAST pointer | `00000001` | Tag-byte follows; references external storage |

(big-endian flips the sign bits — see lines 193-225 of varatt.h.)

The bit layout matters because the **first byte alone** is enough
to decide which struct to interpret the rest as. `VARATT_IS_*`
helpers test these signatures.

## varattrib_4b — the workhorse

[verified-by-code `varatt.h:126-140`]

```c
typedef union
{
    struct {                /* Normal varlena (4-byte length) */
        uint32   va_header;
        char     va_data[FLEXIBLE_ARRAY_MEMBER];
    } va_4byte;
    struct {                /* Compressed-in-line format */
        uint32   va_header;
        uint32   va_tcinfo;  /* raw size + compression method */
        char     va_data[FLEXIBLE_ARRAY_MEMBER];  /* compressed payload */
    } va_compressed;
} varattrib_4b;
```

The high two bits of `va_tcinfo` encode the compression method
(`TOAST_PGLZ_COMPRESSION_ID` / `TOAST_LZ4_COMPRESSION_ID`); the
low 30 bits are the uncompressed size. This is why max raw size
of a compressed datum is 1 GB minus a small constant.

## varattrib_1b_e — the TOAST pointer

[verified-by-code `varatt.h:148-154`]

```c
typedef struct {
    uint8    va_header;     /* Always 0x80 (BE) or 0x01 (LE) */
    uint8    va_tag;        /* vartag_external value */
    char     va_data[FLEXIBLE_ARRAY_MEMBER];  /* tag-specific data */
} varattrib_1b_e;
```

`va_data` holds one of three structures based on `va_tag`. The
`SET_VARTAG_EXTERNAL` macro stamps the header (0x01) and the tag
in one go.

## varatt_external — the on-disk TOAST pointer payload

[verified-by-code `varatt.h:32-39`]

```c
typedef struct varatt_external
{
    int32    va_rawsize;     /* Original data size (includes header) */
    uint32   va_extinfo;     /* (external size) | (compression method << 30) */
    Oid      va_valueid;     /* Unique ID of value within TOAST table */
    Oid      va_toastrelid;  /* RelID of TOAST table containing it */
} varatt_external;
```

Critical: this struct is stored **unaligned within the heap
tuple**, so reading it requires `VARATT_EXTERNAL_GET_POINTER` to
memcpy into a local. The struct also "must not contain any
padding" because `memcmp` is used for equality.

`va_extinfo` packs two meanings:
- Low 30 bits: external (post-compression) size of the data
  payload, excluding header.
- High 2 bits: compression method (PGLZ / LZ4 — only two
  legal values today, per the SET macro Assert).

`VARATT_EXTERNAL_IS_COMPRESSED` returns true when external size
< (raw size - header), which is the "compression actually saved
space" condition.

## varatt_indirect — in-memory aliasing

[verified-by-code `varatt.h:57-60`]

```c
typedef struct varatt_indirect
{
    varlena   *pointer;     /* Pointer to in-memory varlena */
} varatt_indirect;
```

An indirect TOAST pointer says "the real Datum lives at this
in-memory address — don't fetch from a relation". Used to avoid
copying when passing TOASTed values through executor stages. The
caller is responsible for ensuring lifetime: the pointed-to
storage must outlive every pointer to it.

Indirect pointers cannot nest (asserted in `detoast.c:144`).

## varatt_expanded — writable expanded-object pointer

[verified-by-code `varatt.h:74-77`]

```c
typedef struct varatt_expanded
{
    ExpandedObjectHeader *eohptr;
} varatt_expanded;
```

Expanded objects let datatypes maintain a **flat-but-modifiable**
in-memory representation that's faster than re-flattening on every
update (the canonical user is arrays — see
`expandeddatum.h`). Two tags discriminate the safety of the
reference:
- `VARTAG_EXPANDED_RO` — read-only; the caller MUST NOT modify.
- `VARTAG_EXPANDED_RW` — read-write; the caller owns the object.

`VARTAG_IS_EXPANDED` strips the RO/RW distinction
[verified-by-code `varatt.h:94-98`].

## Endian-dependent macros

[verified-by-code `varatt.h:193-258`]

Two parallel sets of macros for big-endian / little-endian. The
public API (`VARSIZE`, `VARDATA`, `VARSIZE_ANY` etc.) hides this:
each compiles to one or the other.

Reading the bit-pattern table at the top of varatt.h is more
useful than tracing the macros — the macros are mechanical
shifts/masks of those patterns.

## Short-header conversion

[verified-by-code `varatt.h:415-428`]

A 4-byte-uncompressed datum that's ≤ 126 bytes can be re-encoded
as 1-byte-header (saves 3 bytes). The `VARATT_CAN_MAKE_SHORT`
test:

```c
static inline bool
VARATT_CAN_MAKE_SHORT(const void *PTR)
{
    return VARATT_IS_4B_U(PTR) &&
        (VARSIZE(PTR) - VARHDRSZ + VARHDRSZ_SHORT) <= VARATT_SHORT_MAX;
}
```

The TOAST insert path (`heap_toast_insert_or_update`) does this
conversion as part of "shrink down to TOAST_TUPLE_TARGET"
optimization passes.

## Padding-byte vs short-header disambiguation

The `VARATT_NOT_PAD_BYTE` macro tests the first byte against zero.
Pad bytes (alignment fill) are required to be zero; a 1-byte
header is never zero (the length itself is non-zero); a 4-byte
header's first byte includes the length high bits which are
non-zero for any non-empty datum. So zero in the first byte means
"this is alignment padding, skip me".

## Common review-time concerns

- **Always check IS_EXTERNAL before IS_1B** — VARSIZE_1B returns
  0 for external pointers, which is meaningless.
- **`varatt_external` must be memcpy'd to a local** before
  field access — it's stored unaligned in the tuple.
- **`va_extinfo` is dual-purpose** — use the GET_EXTSIZE /
  GET_COMPRESS_METHOD accessors, never bit-twiddle directly.
- **Indirect pointers cannot nest** — assertion in detoast paths.
- **Expanded RO vs RW matters** — modifying through an RO
  pointer is a programmer bug.
- **Bit layout changes require initdb** — `TOAST_MAX_CHUNK_SIZE`
  derivation in heaptoast.h:78 says so explicitly; varatt header
  layouts are even more on-disk-committed.

## Invariants

- **[INV-1]** The first byte fully discriminates header shape:
  4B-U / 4B-C / 1B / 1B-E.
- **[INV-2]** TOAST pointer tags: ONDISK=18 (chosen for legacy
  on-disk compat), INDIRECT=1, EXPANDED_RO=2, EXPANDED_RW=3.
- **[INV-3]** `varatt_external` is unaligned in tuples; access
  via VARATT_EXTERNAL_GET_POINTER memcpy.
- **[INV-4]** Compression method is encoded in the top 2 bits of
  `va_extinfo` (external) or `va_tcinfo` (inline).
- **[INV-5]** Pad bytes are zero; 1-byte headers are never zero;
  this disambiguates alignment fill from datum start.

## Useful greps

- The struct family:
  `grep -n 'varatt_external\|varatt_indirect\|varatt_expanded' source/src/include/varatt.h | head -10`
- Tag enum + macros:
  `grep -n 'vartag_external\|VARTAG_ONDISK\|VARTAG_INDIRECT' source/src/include/varatt.h | head -10`
- TOAST pointer construction:
  `grep -n 'SET_VARTAG_EXTERNAL\|VARATT_EXTERNAL_SET' source/src/include/varatt.h | head -10`
- VARATT_IS_* tests:
  `grep -n 'VARATT_IS_EXTERNAL\|VARATT_IS_COMPRESSED\|VARATT_IS_SHORT' source/src/include/varatt.h | head -15`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/utils/expandeddatum.h`](../files/src/include/utils/expandeddatum.md) | — | ExpandedObjectHeader API |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | 32 | varatt_external struct |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | 57 | varatt_indirect |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | 74 | varatt_expanded |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | 84 | vartag_external enum |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | 126 | varattrib_4b / 1b / 1b_e |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | 228 | little-endian header bit-layout macros |
| [`src/include/varatt.h`](../files/src/include/varatt.h.md) | — | full header |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/idioms/toast-chunk-write.md` — how
  varatt_external is filled at write time.
- `knowledge/idioms/detoast-stream-consumption.md` — how
  detoast_attr branches on the four header shapes.
- `knowledge/idioms/expanded-objects.md` — varatt_expanded
  consumers (arrays, ranges).
- `knowledge/data-structures/datum-nullabledatum.md` — Datum is
  a `uintptr_t` that may hold a varlena pointer.
- `knowledge/subsystems/access-common.md` — TOAST module
  overview.
- `.claude/skills/catalog-conventions.md` — pg_attribute
  storage class drives TOAST decisions.
- `source/src/include/varatt.h` — full header.
- `source/src/include/utils/expandeddatum.h` —
  ExpandedObjectHeader API.
