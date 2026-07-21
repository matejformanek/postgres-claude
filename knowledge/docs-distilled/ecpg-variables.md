---
source_url: https://www.postgresql.org/docs/current/ecpg-variables.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Using Host Variables (§36 leaf): the C↔SQL type map, VARCHAR/bytea struct expansion, NULL/truncation indicators, pgtypes pseudo-types"
maps_to_skill: wire-protocol
---

# ECPG — Using Host Variables (the C↔SQL marshaling layer)

The type-mapping contract between C variables and SQL columns: which C type
carries which SQL type, how `VARCHAR`/`bytea` get rewritten into structs at
preprocessing, how NULL and truncation are signalled, and where the pgtypes
pseudo-types (`numeric`/`date`/`timestamp`/`interval`) require heap allocation.

## Non-obvious claims

- **The base type map is mostly the obvious C scalars — with three sharp
  edges.** `smallint→short`, `integer→int`, **`bigint→long long int`** (not
  `long`), `real→float`, `double precision→double`, `oid→unsigned int`,
  `boolean→bool` (from `ecpglib.h` if the platform lacks a native `bool`),
  `name→char[NAMEDATALEN]`. The pseudo-types `decimal`/`numeric`/`timestamp`/
  `interval`/`date` map to library-managed types, *not* plain C scalars.
  [from-docs]

- **`VARCHAR var[180]` is rewritten into a named struct by the preprocessor.**
  It expands to `struct varchar_var { int len; char arr[180]; } var;`. `arr`
  holds the string *including* a terminating zero; `len` holds the length
  *excluding* it. On input, if `strlen(arr) != len`, the **shorter** of the two
  wins — a real footgun if you set one but not the other. `VARCHAR` may be all
  upper or all lower case but **not mixed**. [from-docs]

- **`bytea var[180]` expands the same way but is binary-clean.** `struct
  bytea_var { int len; char arr[180]; }` — but `arr` may contain embedded
  `'\0'` as data (unlike VARCHAR), and `len` is the true binary length. The
  data is hex-encoded on the wire, so it **only works when the server's
  `bytea_output` GUC is `hex`** (the default) — an `escape` setting breaks the
  round-trip. [from-docs]

- **The indicator variable is a *three-way* signal, not a boolean.** For a
  target `:val :val_ind`: `val_ind == 0` → not NULL; `< 0` → NULL (the real
  host variable is left untouched/ignored); `> 0` → not NULL **but truncated**
  when copied into the host variable, with the positive value being the
  original length. Omitting an indicator on a column that returns NULL raises
  `ECPG_MISSING_INDICATOR` (-213). [from-docs]

- **The pgtypes pseudo-types require explicit heap allocation and free.**
  `numeric`/`decimal`/`interval` targets are pointers you must
  `PGTYPESnumeric_new()` / `PGTYPESdecimal_new()` / `PGTYPESinterval_new()`
  before the `INTO`, and free afterward; `timestamp`/`date` are value types you
  can declare inline but still convert via `PGTYPES*_to_asc`. There is no
  dedicated `decimal`-specific arithmetic — convert to `numeric` first
  (`PGTYPESnumeric_from_decimal`). [from-docs]

- **Arrays let you fetch multiple rows with no cursor.** `int dbid[8]; char
  dbname[8][16];` as `INTO` targets pull up to 8 rows in one `SELECT` — the
  array dimension is the row cap. This is the "elements 4 & 5" (count + stride)
  of the 10-arg `ECPGdo` block doing real work (see `ecpg-develop`). [from-docs]

- **Struct targets bind by column *name*, and `EXEC SQL TYPE` registers a C
  typedef with ECPG.** A `struct { int oid; char datname[65]; … }` matches
  columns to members by name. Typedefs work two ways: an ordinary C `typedef`
  inside the declare section, or the ECPG-specific `EXEC SQL TYPE serial_t IS
  long;`. Caveat: a typedef name that collides with a SQL keyword causes
  preprocessor syntax errors. [from-docs]

## Links into corpus

- The 10-arg-per-variable convention these types feed:
  `knowledge/docs-distilled/ecpg-develop.md`.
- The pgtypes C API for the pseudo-types:
  `knowledge/docs-distilled/ecpg-pgtypes.md`.
- The `ECPG_MISSING_INDICATOR` and other codes:
  `knowledge/docs-distilled/ecpg-errors.md`.
- Server-side `bytea_output=hex` format: `knowledge/docs-distilled/storage-toast.md`
  (varlena) and the `jsonpath-and-jsonb`/type-adt corpus for hex encoding.
- Skill: `wire-protocol`.
