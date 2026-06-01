# tupdesc_details.h

- **Source path:** `source/src/include/access/tupdesc_details.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tupdesc.h`, `tupdesc.c`, `heaptuple.c`.

## Purpose

Internal header holding the `AttrMissing` struct definition (used to record "value to substitute when a column added by ALTER TABLE ADD COLUMN ... DEFAULT is not stored in an older row"). Split out from `tupdesc.h` to avoid a wider include footprint. [from-comment, tupdesc_details.h:3-14]

## Top-of-file comment

> "POSTGRES tuple descriptor definitions we can't include everywhere" [from-comment, tupdesc_details.h:3-5]

## Key type

- **`AttrMissing`** (22) — `bool am_present; Datum am_value;` Used inside `TupleConstr->missing[]` (one entry per attribute that has a recorded default-on-add value). [from-comment, tupdesc_details.h:18-27]

## Cross-references

- Populated by `catalog/heap.c::StoreAttrDefault` (when ALTER TABLE ADD COLUMN runs).
- Consumed by `heaptuple.c::getmissingattr` and `heap_deform_tuple` to substitute the recorded value when a tuple was written before the column existed.

## Confidence tag tally
`[verified-by-code]=1 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`
