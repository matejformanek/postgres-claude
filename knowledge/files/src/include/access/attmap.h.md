# attmap.h

- **Source path:** `source/src/include/access/attmap.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `attmap.c`, `tupconvert.h`.

## Purpose

Defines `AttrMap` (output-attnum → input-attnum mapping) and declares the constructors / destructor implemented in `attmap.c`. [from-comment, attmap.h:1-15]

## Key type

- **`AttrMap`** — `AttrNumber *attnums; int maplen;`. Entry `attnums[i]` is the 1-based input attnum that maps to output column `i+1` (zero ⇒ "produce NULL", used for dropped columns and inheritance children). [from-comment, attmap.h:18-30]

## Public surface

- `make_attrmap(int maplen)`, `free_attrmap(AttrMap *)`.
- `build_attrmap_by_position(TupleDesc indesc, TupleDesc outdesc, const char *msg)`.
- `build_attrmap_by_name(TupleDesc indesc, TupleDesc outdesc, bool missing_ok)`.
- `build_attrmap_by_name_if_req(TupleDesc indesc, TupleDesc outdesc, bool missing_ok)`.

## Cross-references

- See `knowledge/files/src/backend/access/common/attmap.c.md`.

## Confidence tag tally
`[verified-by-code]=1 [from-comment]=1 [from-readme]=0 [inferred]=0 [unverified]=0`
