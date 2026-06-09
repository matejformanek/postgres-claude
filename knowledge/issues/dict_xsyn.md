# Issues — `contrib/dict_xsyn`

Text-search synonym dictionary template. 1 source file / ~264 LOC.

**Parent docs:** `knowledge/files/contrib/dict_xsyn/dict_xsyn.c.md`.

**Source:** 3 entries surfaced 2026-06-09 by A14-3.

## Entries — `dict_xsyn.c`

- [ISSUE-resource: per-key full-line copy bloats memory `K*L*S` (nit)] — `:118-122`
- [ISSUE-correctness: `str_tolower` uses `DEFAULT_COLLATION_OID`; semantics shift on server collation change (nit)] — `:101,218`
- [ISSUE-resource: no upper bound on `d->len`; admin file fills heap before error (nit)] — `:108-115`

## Cross-sweep references

- A14 unaccent — sister dictionary template.
- A13 citext — same `DEFAULT_COLLATION_OID` family hazard.
