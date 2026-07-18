# utils/expandeddatum.h — TOAST RW expanded object machinery

Source: `source/src/include/utils/expandeddatum.h` (170 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Defines the in-memory "expanded" representation of complex TOASTable types (arrays, records, jsonb). On-disk is the "flat" representation (a contiguous varlena); in memory, code can work with a more efficient deconstructed form contained in its own MemoryContext, then re-flatten on demand.

## Public API

- `EXPANDED_POINTER_SIZE` (`expandeddatum.h:50`): size of a TOAST pointer to an expanded object.
- `EOM_get_flat_size_method` / `EOM_flatten_into_method` (`expandeddatum.h:69-71`): per-type required methods.
- `ExpandedObjectMethods` (`expandeddatum.h:74-78`).
- `ExpandedObjectHeader` (`expandeddatum.h:100-116`): phony varlena header (always == EOH_HEADER_MAGIC), methods ptr, MemoryContext, and two stored TOAST pointers (RW + RO).
- `EOH_HEADER_MAGIC = -1` (`expandeddatum.h:129`).
- `VARATT_IS_EXPANDED_HEADER(PTR)` (`expandeddatum.h:130-131`).
- `EOHPGetRWDatum` / `EOHPGetRODatum` (`expandeddatum.h:138-148`).
- `DatumIsReadWriteExpandedObject` / `MakeExpandedObjectReadOnly` (`expandeddatum.h:151-157`).
- Functions: `DatumGetEOHP`, `EOH_init_header`, `EOH_get_flat_size`, `EOH_flatten_into`, `MakeExpandedObjectReadOnlyInternal`, `TransferExpandedObject`, `DeleteExpandedObject` (`expandeddatum.h:159-168`).

## Invariants

- **INV-EOH_HEADER_MAGIC=-1** [verified-by-code, `expandeddatum.h:129-131`]: first int32 of any expanded header is -1. No 4-byte-header varlena has this — so flat vs expanded discrimination is reliable, BUT short-header varlena could match (`expandeddatum.h:124-127`). Caller must already know which case they're in.
- **INV-RW-and-RO-pointers-pre-allocated** [from-comment, `expandeddatum.h:91-96`]: both pointers live inside the header so a function can return either without a fresh alloc. They are distinguishable by VARTAG.
- **INV-eoh_context-owns-everything** [from-comment, `expandeddatum.h:85-89`]: all subsidiary data must live in `eoh_context`; deleting the context frees the whole expanded object. Reparenting moves lifetime.
- **INV-flat-must-be-4byte-header** [from-comment, `expandeddatum.h:62-63`]: the flattened form returned by `flatten_into` MUST be inline, non-compressed, 4-byte-header. Not short-header — because `MakeExpandedObjectReadOnlyInternal` and the header magic check rely on that.
- **INV-RW-pointer-modify-in-place-contract** [from-comment, `expandeddatum.h:30-34`]: possession of an RW pointer authorizes in-place modification. Functions modifying in place must NOT corrupt the old value if they fail partway through (the function must be exception-safe before commit).
- **INV-functions-return-RW** [from-comment, `expandeddatum.h:31-32`]: new expanded objects should be returned as RW datums so the caller can keep modifying.

## Notable internals

- `DatumIsReadWriteExpandedObject` (`expandeddatum.h:151-153`) short-circuits on `isnull` or fixed-length type (`typlen != -1` means not varlena, so can't be expanded).
- `TransferExpandedObject(d, new_parent)` (`expandeddatum.h:167`) reparents the object's MemoryContext; cheap.

## Trust-boundary / Phase-D surface

- **Magic header false-positives with short varlena** (`expandeddatum.h:124-127`): the comment explicitly warns. Any code that fetches a Datum from a place that could yield a short-header varlena MUST NOT use `VARATT_IS_EXPANDED_HEADER` without first knowing the source can't be short-header.
- **Exception safety on in-place modify** (`expandeddatum.h:32-34`): "Functions that modify an argument value in-place must take care that they do not corrupt the old value if they fail partway through." This is a non-trivial promise: any palloc failure mid-modification must leave the expanded object internally consistent.
- **RW pointer is shareable** — if caller hands an RW pointer to another function and continues using it, both can modify, leading to action-at-a-distance. Header doesn't warn against double-RW sharing.

## Cross-refs

- `source/src/include/varatt.h` — TOAST pointer machinery (`VARTAG_EXPANDED_RW/RO`).
- `knowledge/files/src/include/utils/expandedrecord.md`, `array.md` — concrete consumers.
- `source/src/backend/utils/adt/expandeddatum.c` — implementation.

## Issues

- `[ISSUE-INVARIANT: in-place-modify exception safety is a hard contract (high)]` — header states it informally; most failing-half-way bugs in expanded objects come from violating this. A defensive copy-on-write pattern documented at header level would help.
- `[ISSUE-DOC: short-header vs EOH_HEADER_MAGIC collision (medium)]` — flag explicit pattern for safe dispatch (e.g. "only call VARATT_IS_EXPANDED_HEADER on already-detoasted 4-byte datums").

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/varatt-varlena.md](../../../../data-structures/varatt-varlena.md)
