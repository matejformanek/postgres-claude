---
source_url: https://www.postgresql.org/docs/current/xtypes.html
fetched_at: 2026-06-08T21:05:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — User-Defined Types (defining a base type)

How a C extension adds a genuine base type (not a composite/domain). The
non-obvious parts are the **shell-type two-step**, the storage/alignment
options, and the **varlena header alignment landmine** that core-dumps on
strict-alignment CPUs if you declare the length field wrong.

## I/O functions — the type's parser

- A base type needs an **input function** (`cstring → type`) and **output
  function** (`type → cstring`); PG generates neither. Input must be a complete,
  robust parser of the external text; output must be the exact inverse so
  dump/reload round-trips (matters most for float). [from-docs]
  [verified-by-code, via [[knowledge/idioms/fmgr.md]]]
- Optional **binary `recv` (`internal` StringInfo → type)** and **`send` (type →
  `bytea`)** functions make COPY BINARY / wire transfer faster and more portable
  than text I/O. [from-docs]

## The shell-type chicken-and-egg

- The I/O functions must `RETURNS thetype`, but the type can't exist until its
  I/O functions do. **Break it with a shell type:** `CREATE TYPE complex;`
  (placeholder), then create the I/O functions, then the full
  `CREATE TYPE complex (...)`. [from-docs]

## Storage declaration

- **`INTERNALLENGTH`** = fixed `N` bytes, or **`VARIABLE`** for variable-length
  (varlena) types. [from-docs]
- **`PASSEDBYVALUE`** only for small fixed-size types whose internal length fits
  in a `Datum` (≤8 bytes on 64-bit); the declared length must equal the real
  struct size. Anything larger must be pass-by-reference. [from-docs]
- **`ALIGNMENT`** = `char`/`short`/`int`/`double`. [from-docs]
- **`STORAGE`** (varlena only) = `PLAIN` (no TOAST) / `EXTENDED` (default;
  compress + out-of-line) / `EXTERNAL` (out-of-line, no compress) / `MAIN`
  (compress, prefer in-line). [from-docs]
  [cross: knowledge/docs-distilled/storage-toast.md]
- An **array type is auto-created** for every base type, named with a leading
  underscore (`_complex`). [from-docs]

## C-level varlena rules (the alignment landmine)

- A varlena type's first field **must be `char vl_len_[4]`**, never accessed
  directly. Declaring it as `int32` lets the compiler assume 4-byte alignment
  and **core-dumps on strict-alignment architectures** when handed an unaligned
  (e.g. packed/short-header) datum. [from-docs]
- Use **`SET_VARSIZE()`** to write and **`VARSIZE()`** to read the total size
  (length field encoding is platform-dependent — no raw access). [from-docs]
- A C function must **detoast first** with **`PG_DETOAST_DATUM`** (usually hidden
  in a `GETARG_*_P` macro). The lighter **`PG_DETOAST_DATUM_PACKED`** +
  `VARSIZE_ANY_EXHDR` / `VARDATA_ANY` avoids a copy but yields **unaligned**
  data. [from-docs]
  [verified-by-code, via [[knowledge/docs-distilled/xfunc-c.md]]]

## Expanded (in-memory) representation — advanced

- TOAST-able types may offer an **expanded** read/write in-memory form distinct
  from the flat on-disk varlena, detected via **`VARATT_IS_EXPANDED_HEADER()`**,
  with read-write vs read-only pointer semantics for in-place mutation. Reference
  implementation: `src/backend/utils/adt/array_expanded.c`. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/utils/adt/array_expanded.c.md]]]

## Links into corpus
- [[knowledge/idioms/fmgr.md]] — PG_FUNCTION_ARGS, PG_GETARG/PG_RETURN, the I/O-function calling convention.
- [[knowledge/docs-distilled/xfunc-c.md]] — V1 C functions, detoasting, varlena macros.
- [[knowledge/docs-distilled/storage-toast.md]] — what the STORAGE options actually do on disk.
- [[knowledge/files/src/backend/utils/adt/array_expanded.c.md]] — the canonical expanded-datum example.
- Skill: `fmgr-and-spi` — writing the C I/O functions; `catalog-conventions` — pg_type.dat for built-in types.

## Gaps / follow-ups
- The `CREATE TYPE` TOAST/typmod/collation interplay and `LIKE` shortcut are
  summarized only; the SQL-command reference page carries the full grammar.
