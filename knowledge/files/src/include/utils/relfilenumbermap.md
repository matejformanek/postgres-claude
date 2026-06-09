# `src/include/utils/relfilenumbermap.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Tiny header for the reverse map: `(reltablespace, RelFileNumber) →
Oid`. Backed by an in-backend hash cache that's populated on demand
from `pg_class` / `pg_filenode.map` [from-comment: lines 3-4].

## Public API

[verified-by-code: lines 18-19]
```c
extern Oid RelidByRelfilenumber(Oid reltablespace,
                                RelFileNumber relfilenumber);
```

Returns `InvalidOid` if not found.

## Invariants

- **INV** [inferred] Cache is per-backend; invalidated on relcache
  inval (same broadcast path as `rel.h` entries).

## Trust boundary

- Used by `pg_buffercache` and similar extraction tools to translate
  a buffer's filenumber back to an OID. Inherits the buffer-cache
  cross-database visibility issues documented in A14 — a backend can
  resolve filenumbers for relations in *other* databases (though it
  cannot necessarily open them).

## Cross-refs

- `storage/relfilelocator.h` — `RelFileNumber` type.
- `utils/relmapper.h` — forward map for nailed catalogs.
- A14 `pg_buffercache` finding.

## Issues

None at header level.
