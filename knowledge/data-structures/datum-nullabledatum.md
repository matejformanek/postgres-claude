# Datum + NullableDatum — the universal value container

`Datum` is the **single C type** through which PG passes
EVERY value at runtime — int4, text, jsonb, point, oid,
anything. A 64-bit unsigned integer that either IS the value
(pass-by-value types: int4, oid, bool, float8) or POINTS at
the value (pass-by-ref types: text, numeric, arrays).
`NullableDatum` is the (Datum, isnull) pair used when null-
state must be carried alongside.

Anchors:
- `source/src/include/postgres.h:60-103` — typedef +
  conversion functions [verified-by-code]
- `source/src/include/postgres.h:84-91` — `NullableDatum`
  struct [verified-by-code]
- `knowledge/data-structures/fmgrinfo.md` — `FunctionCallInfo`
  carries arrays of NullableDatum
- `.claude/skills/fmgr-and-spi/SKILL.md` — companion skill

## The typedef

```c
typedef uint64_t Datum;
#define SIZEOF_DATUM 8
```

[verified-by-code `postgres.h:70`]

**Always 8 bytes** on every supported platform. Earlier PG
versions had 4-byte Datum on 32-bit platforms; standardized
on 8 in recent versions for cross-platform compatibility
[from-comment `postgres.h:60-65`].

## Pass-by-value vs pass-by-reference

PG types have a `typbyval` flag in `pg_type`:

- **`typbyval = true`**: the value FITS in a Datum.
  Examples: `int4` (32-bit fits in 64), `bool`, `float8`,
  `int8`, `oid`, `Datum` itself.
  - Convert via `Int32GetDatum(42)` / `DatumGetInt32(d)`.
- **`typbyval = false`**: the value LIVES IN MEMORY,
  Datum points at it.
  Examples: `text`, `varchar`, `numeric`, arrays, jsonb.
  - Convert via `PointerGetDatum(p)` /
    `DatumGetPointer(d)`.

Code that handles any type uniformly stores `Datum`; the
type's `typbyval` decides how to interpret.

## The conversion macros

[verified-by-code `postgres.h:198-354`]

A bidirectional macro per type:

```c
int32 i = DatumGetInt32(d);
Datum d = Int32GetDatum(42);

text *t = DatumGetTextPP(d);              /* with detoast */
Datum d = PointerGetDatum(my_text);
```

Type-specific macros + the universal `DatumGetPointer` /
`PointerGetDatum`. The macros are inline functions in
modern PG; older versions used raw casts.

## Why a uint64 and not an actual union?

A union of {int4, int8, float8, void*} would be the
"correct" representation. PG uses uint64 historically
because:

1. **Pre-modern-C portability** — unions of pointers and
   integers had alignment quirks.
2. **Calling convention efficiency** — uint64 fits in a
   register on every 64-bit ABI; unions sometimes don't.
3. **Code clarity** — every code path uses the same type;
   readers know the conversion goes through a macro.

The trade-off: every read needs to know the source type
(via TupleDesc or fcinfo). There's no runtime type
checking on Datum.

## PointerGetDatum and const safety

[from-comment `postgres.h:338-354`]

```c
#define PointerGetDatum(X) \
    ((Datum) (X))
```

`PointerGetDatum` takes a `const void *` but casts to
`Datum`. The cast is intentional — once a value is in a
Datum, the caller may write through it (e.g., if the type
supports in-place mutation under specific protocols).

This is the "const-cast hazard" the comment warns about:
PG functions can't enforce const at the Datum boundary;
the caller's discipline is the only protection.

## NullableDatum

[verified-by-code `postgres.h:84-91`]

```c
typedef struct NullableDatum
{
#define FIELDNO_NULLABLE_DATUM_DATUM 0
    Datum     value;
#define FIELDNO_NULLABLE_DATUM_ISNULL 1
    bool      isnull;
    /* padding bytes available for flags */
} NullableDatum;
```

When code needs to carry both the value AND its null state,
use NullableDatum. The struct packs Datum + bool in 16
bytes (with alignment padding); the padding could be used
for flags.

Used heavily in:
- **`FunctionCallInfo.args[]`** — each function argument is
  a NullableDatum.
- **Hash-aggregate buckets** — group key columns + per-group
  state.
- **Sort buffers** — keys with their null states.

The split from "Datum + parallel bool[] array" (used in
TupleTableSlot for `tts_values[]` / `tts_isnull[]`) is a
spatial-locality optimization: when accessing both value and
nullness together, packed pair is faster than two array
indirections.

## The FIELDNO_* macros

[verified-by-code `postgres.h:86-89`]

These define field offsets at compile time:

```c
#define FIELDNO_NULLABLE_DATUM_DATUM  0
#define FIELDNO_NULLABLE_DATUM_ISNULL 1
```

Used by the JIT compiler (LLVM-based) to generate
optimized code that accesses the struct's fields by
offset. The macros allow JIT and C code to agree on
the layout without duplicating offset arithmetic.

## Datum vs Pointer ABI

A subtle ABI rule: a function that returns `Datum` from
`PG_RETURN_TEXT_P` etc. is returning a uint64. The caller
casts the bits to whatever type it expected. Mistakes
here = silent corruption.

This is why `PG_FUNCTION_INFO_V1` exists — the V1 ABI
documents which conversion macros the function uses and
the fmgr layer guarantees the right type is passed.

## Detoasting on the Datum side

For pass-by-reference varlena types, the Datum points to a
varlena. The varlena may be:
- **Plain inline** — direct read.
- **Short-header inline** — `VARATT_IS_SHORT`.
- **Compressed inline** — `VARATT_IS_COMPRESSED`.
- **External TOAST pointer** — `VARATT_IS_EXTERNAL`.

The `_PP` / `_P` suffixes on `PG_GETARG_*` macros choose
the detoast level:
- `_P` — fully detoast (long-header, uncompressed,
  in-memory).
- `_PP` — "preserve packed" — leave short-header / compressed
  alone if possible.

[See `knowledge/idioms/heap-tuple-decompression-pattern.md`
for the full decode pattern.]

## Common review-time concerns

- **Always use the conversion macros** — don't cast Datum
  directly.
- **`DatumGetPointer` returns the raw pointer** — caller
  must know the type and detoast appropriately.
- **`PG_GETARG_*_PP` is the preferred pattern** for varlena
  arguments — leaves them packed when possible.
- **Don't store Datum across MemoryContext resets** without
  copying for pass-by-ref types.
- **`NullableDatum.isnull = true` means `value` is
  unspecified** — readers must check isnull first.

## Invariants

- **[INV-1]** `Datum` is 8 bytes on every platform.
- **[INV-2]** Pass-by-value types fit in Datum; pass-by-ref
  types are pointed at.
- **[INV-3]** Always use the per-type conversion macros.
- **[INV-4]** `NullableDatum.value` is unspecified when
  `isnull = true`.
- **[INV-5]** `PointerGetDatum` doesn't preserve const;
  caller's discipline is the only protection.

## Useful greps

- All DatumGet*/MakeDatum macros:
  `grep -n 'DatumGet\|GetDatum' source/src/include/postgres.h | head -20`
- NullableDatum users:
  `grep -RIn 'NullableDatum' source/src/backend | head -20`
- JIT layout markers:
  `grep -n 'FIELDNO_' source/src/include/postgres.h`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/postgres.h`](../files/src/include/postgres.h.md) | 60 | typedef + conversion functions |
| [`src/include/postgres.h`](../files/src/include/postgres.h.md) | 84 | NullableDatum struct |
| [`src/include/postgres.h`](../files/src/include/postgres.h.md) | — | type + macros |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/data-structures/fmgrinfo.md` — `FunctionCallInfo`
  carries NullableDatum args.
- `knowledge/data-structures/tupletableslot.md` —
  `tts_values[]` is an array of Datum; `tts_isnull[]` the
  parallel bool[].
- `knowledge/data-structures/heap-tuple-layout.md` — Datum
  representation aligns with on-disk attribute format.
- `knowledge/idioms/heap-tuple-decompression-pattern.md` —
  detoasting a Datum-pointed varlena.
- `.claude/skills/fmgr-and-spi/SKILL.md` — `PG_GETARG_*` /
  `PG_RETURN_*` macros work on Datum.
- `source/src/include/postgres.h` — type + macros.
