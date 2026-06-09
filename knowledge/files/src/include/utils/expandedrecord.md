# utils/expandedrecord.h — composite-type expanded representation

Source: `source/src/include/utils/expandedrecord.h` (241 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Concrete expanded object for composite (record) types. Lets PL/pgSQL and friends manipulate composite values as `Datum[] + bool[]` arrays without re-toasting every field assignment.

## Public API

- `ER_MAGIC = 1384727874` (`expandedrecord.h:40`).
- `ExpandedRecordHeader` (`expandedrecord.h:42-139`): hdr + er_magic + flags + er_decltypeid (could be domain) + er_typeid/er_typmod (composite base) + er_tupdesc + er_tupdesc_id + dvalues/dnulls/nfields + flat_size/data_len/hoff/hasnull + fvalue/fstartptr/fendptr + er_short_term_cxt + domain-check fields + memory-context callback.
- Flag bits (`expandedrecord.h:52-59`): `ER_FLAG_FVALUE_VALID`, `ER_FLAG_FVALUE_ALLOCED`, `ER_FLAG_DVALUES_VALID`, `ER_FLAG_DVALUES_ALLOCED`, `ER_FLAG_HAVE_EXTERNAL`, `ER_FLAG_TUPDESC_ALLOCED`, `ER_FLAG_IS_DOMAIN`, `ER_FLAG_IS_DUMMY`.
- `ER_FLAGS_NON_DATA` mask (`expandedrecord.h:61-62`) — flags preserved across tuple-data replacement.
- `ExpandedRecordIsEmpty` / `ExpandedRecordIsDomain` macros (`expandedrecord.h:158-161`).
- `TransferExpandedRecord(erh, cxt)` (`expandedrecord.h:164-165`).
- `ExpandedRecordFieldInfo` (`expandedrecord.h:168-174`).
- Constructors: `make_expanded_record_from_typeid`, `make_expanded_record_from_tupdesc`, `make_expanded_record_from_exprecord`, `make_expanded_record_from_datum`, `expanded_record_set_tuple` (`expandedrecord.h:179-188`).
- Access: `expanded_record_fetch_tupdesc`, `expanded_record_get_tuple`, `DatumGetExpandedRecord`, `deconstruct_expanded_record`, `expanded_record_lookup_field`, `expanded_record_fetch_field`, `expanded_record_set_field[_internal]`, `expanded_record_set_fields` (`expandedrecord.h:189-209`).
- Inline fast paths: `expanded_record_get_tupdesc`, `expanded_record_get_field` (`expandedrecord.h:217-239`).

## Invariants

- **INV-er_decltypeid-may-be-domain** [from-comment, `expandedrecord.h:64-65`]: top-level declared type can be a domain; `er_typeid`/`er_typmod` are the underlying composite base.
- **INV-er_typeid-not-domain** [from-comment, `expandedrecord.h:68-72`]: `er_typeid` and `er_typmod` ALWAYS identify the composite base, never a domain.
- **INV-dvalues-OR-fvalue-valid** [from-comment, `expandedrecord.h:91-99`]: either the deconstructed `dvalues`/`dnulls` are valid (ER_FLAG_DVALUES_VALID) or the flat `fvalue` is valid (ER_FLAG_FVALUES_VALID) or both. ExpandedRecordIsEmpty ⇔ neither.
- **INV-fstartptr-fendptr-distinguish-shared-vs-private** [from-comment, `expandedrecord.h:97-99`, `expandedrecord.h:120-124`]: for pass-by-ref field types, dvalues[i] may point either inside [fstartptr, fendptr) (sharing the flat tuple's storage) or to private palloc'd memory. Determines whether modification needs a fresh palloc.
- **INV-flat-still-valid-for-syscols** [from-comment, `expandedrecord.h:118-121`]: even after user-field changes invalidate ER_FLAG_FVALUE_VALID, the flat tuple can still be used to fetch system column values.
- **INV-tupdesc-refcount-via-callback** [from-comment, `expandedrecord.h:77-82`]: if `er_tupdesc` is a reference-counted typcache tupdesc, refcount is released via the `er_mcb` memory-context callback. If `ER_FLAG_TUPDESC_ALLOCED`, the tupdesc is locally palloc'd instead.
- **INV-ER_MAGIC** [verified-by-code, `expandedrecord.h:40`]: debug crosscheck.
- **INV-DVALUES_ALLOCED-only-for-private-fields** [from-comment, `expandedrecord.h:55`]: flag is set when ANY pass-by-ref field has been palloc'd separately from the flat tuple.

## Notable internals

- `expanded_record_get_field` inline (`expandedrecord.h:227-239`): fast path when `ER_FLAG_DVALUES_VALID` and field number is in range; falls through to `expanded_record_fetch_field` (which may have to deconstruct first).
- `er_dummy_header` (`expandedrecord.h:134`) is for domain checks — runs constraints against a phantom record.

## Trust-boundary / Phase-D surface

- **`ER_FLAG_IS_DUMMY` dummy headers** (`expandedrecord.h:58-59, 134`): used as a workspace for domain checking. Any code paths that walk a list of expanded records must check IS_DUMMY before using one as a value.
- **Tupdesc lifetime via memory-context callback** (`expandedrecord.h:77-82, 138`): if the callback fires (context reset/delete) while another code path holds a raw tupdesc pointer, that pointer is invalidated. Header doesn't surface this hazard.

## Cross-refs

- `knowledge/files/src/include/utils/expandeddatum.md` — base class.
- `source/src/backend/utils/adt/expandedrecord.c` — implementation.
- `source/src/include/utils/typcache.h` — refcounted tupdesc machinery.

## Issues

- `[ISSUE-INVARIANT: tupdesc-refcount-callback hazard (medium)]` — outside code holding a raw tupdesc ptr while the expanded record's context is reset gets a use-after-free. Worth a header-level NOTE.
- `[ISSUE-DOC: ER_FLAG_IS_DUMMY is easy to miss (low)]` — comment is at flag def only; consumers grepping for "domain" won't find it.
