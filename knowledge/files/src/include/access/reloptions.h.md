# reloptions.h

- **Source path:** `source/src/include/access/reloptions.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `reloptions.c`, `amapi.h`.

## Purpose

Public typedefs and prototypes for the reloptions framework. Defines the option type/kind enums, the `relopt_gen` / `relopt_value` / `relopt_bool` / `relopt_int` / etc. struct family, the `StdRdOptions` shared struct for heap/toast, and the kind bitmaps used by each per-AM `amoptions` implementation. [from-comment, reloptions.h:1-17]

## Top-of-file comment

> "Core support for relation and tablespace options (pg_class.reloptions and pg_tablespace.spcoptions). Note: the functions dealing with text-array reloptions values declare them as Datum, not ArrayType *, to avoid needing to include array.h into a lot of low-level code." [from-comment, reloptions.h:3-10]

## Key types

- **`relopt_type`** (28) — `BOOL` / `TERNARY` / `INT` / `REAL` / `ENUM` / `STRING`.
- **`relopt_kind`** (39) — Bitmask: which relation kinds each option applies to (`HEAP`, `TOAST`, `BTREE`, `HASH`, `GIN`, `GIST`, `ATTRIBUTE`, `TABLESPACE`, `SPGIST`, `VIEW`, `BRIN`, `PARTITIONED`). `RELOPT_KIND_LAST_DEFAULT` is the last entry covered by default reloption parsing.
- **`relopt_gen`** (64) — Common header (name, desc, kinds bitmask, lockmode, namelen, type).
- **`relopt_value`** (76) — Parsed value tagged by the type discriminator inside `gen`.
- **`relopt_bool` / `relopt_int` / `relopt_real` / `relopt_string` / `relopt_enum`** (further down) — Typed registration records.
- **`local_relopts`**, **`relopts_validator`**, **`relopt_parse_elt`** — Local-options framework used by opclass options (GIN, BRIN, …).
- **`StdRdOptions`**, **`HEAP_DEFAULT_FILLFACTOR`**, **`HEAP_MIN_FILLFACTOR`** — Standard heap/toast options struct + bounds.

## Public surface (prototypes)

- All the registration helpers (`add_bool_reloption`, `add_int_reloption`, …, plus `add_local_*` variants) and the parsing pipeline (`transformRelOptions`, `untransformRelOptions`, `extractRelOptions`, `parseRelOptions`, `build_reloptions`, `default_reloptions`, `view_reloptions`, `partitioned_table_reloptions`, `index_reloptions`, `heap_reloptions`, etc.) are declared here.

## Key invariants

- The `RELOPT_KIND_*` bitmask is signed-int-safe: the maximum is `1 << 30` (not 31). Future kinds need to respect this. [from-comment, reloptions.h:54-57]
- Reloption text-array Datums are passed as `Datum`, not `ArrayType *`, to keep include footprints small. [from-comment, reloptions.h:7-9]

## Cross-references

- Behaviour: `knowledge/files/src/backend/access/common/reloptions.c.md`.

## Confidence tag tally
`[verified-by-code]=3 [from-comment]=4 [from-readme]=0 [inferred]=0 [unverified]=0`
