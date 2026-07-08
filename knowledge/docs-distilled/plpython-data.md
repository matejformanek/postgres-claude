---
source_url: https://www.postgresql.org/docs/current/plpython-data.html
fetched_at: 2026-07-07T20:52:00Z
anchor_sha: 9d1188f29865
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/Python data values (§46.3) — the PG↔Python type mapping

The exact conversion table between PostgreSQL datums and Python objects, plus
the composite/array/set-returning shapes. PL/Python is **untrusted-only**
(`plpython3u`, `superuser = true` in `plpython3u.control` @9d1188f29865 —
there is no trusted `plpython`), so this maps to `fmgr-and-spi` +
`extension-development` rather than a sandboxing story.

## Input mapping (PostgreSQL → Python)

- `boolean` → `bool`; `smallint`/`int`/`bigint`/`oid` → `int`; `real`/`double`
  → `float`; `numeric` → `Decimal` (`cdecimal` if present, else
  `decimal.Decimal`); `bytea` → `bytes`; **everything else, including all
  character types → `str` (Unicode).** [from-docs]
- **SQL `NULL` → Python `None`** for every type; test with `x is None`.
  [from-docs]
- **SQL array → Python `list`**; multidimensional arrays → nested lists.
  Composite-type argument → a Python **mapping (dict-like)** keyed by attribute
  name, with `None` for NULL attributes. [from-docs]

## Return mapping (Python → PostgreSQL)

- `boolean` return uses Python truthiness — so the string `'f'` returns **true**
  (non-empty string), a classic footgun. `bytea` return goes through Python
  `bytes`. Everything else is stringified with `str()` (or `repr()` for `float`
  to keep precision) and fed to the target type's input function; strings are
  auto-encoded to the server encoding. [from-docs]
- **Return `None` → SQL `NULL`, even for a `STRICT` function.** [from-docs]
- **Type mismatches are NOT flagged:** "logical mismatches between the declared
  PostgreSQL return type and the Python data type of the actual return object
  are not flagged; the value will be converted in any case." [from-docs] — the
  conversion is representation-driven, so a wrong-shaped object fails only at the
  input-function boundary.

## Arrays / composites / sets (the shape gotchas)

- **Array return requires uniform inner lists** ("inner lists at each level must
  all be of the same size") for multidimensional results. A Python **string** is
  a sequence, so returning `"hello"` for `varchar[]` yields `{h,e,l,l,o}` — a
  silent trap. Tuples are accepted for 1-D only (they're ambiguous with
  composites). [from-docs]
- **Composite return has three forms:** a sequence (tuple/list, positional,
  `None` for NULL columns); a mapping (dict keyed by column name — extra keys
  ignored, **missing keys are an error**); or an object read via attribute
  access (`__getattr__`). Works for `OUT` parameters too. [from-docs]
- **`RETURNS SETOF` return forms:** a sequence (tuple/list/set of rows), an
  iterator object (`__iter__`/`__next__`, ends on `StopIteration`), or a
  generator (`yield`). Combines with `OUT` params. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/plpython-database.md]] — the SPI wrappers that
  consume/produce these shapes.
- [[knowledge/docs-distilled/plperl-builtins.md]] — Perl's parallel
  hashref/arrayref mapping (contrast: Perl passes args as text, Python maps
  datums to native objects).
- [[knowledge/idioms/fmgr.md]] — the datum boundary these conversions cross.
