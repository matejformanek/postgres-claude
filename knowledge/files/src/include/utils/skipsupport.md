# `src/include/utils/skipsupport.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Optional B-tree opclass support function for *skip scans* (PG18+).
A btree opclass over a discrete type (int, date) may register a
`BTSKIPSUPPORT_PROC` that lets the executor enumerate "next value"
in the type's domain — enabling skip arrays to advance without an
extra index probe [from-comment: lines 4-29].

## Public API

[verified-by-code: lines 49-96]

```c
typedef Datum (*SkipSupportIncDec)(Relation rel,
                                   Datum existing,
                                   bool *overflow);

typedef struct SkipSupportData {
    Datum low_elem;          /* lowest possible value */
    Datum high_elem;         /* highest possible value */
    SkipSupportIncDec decrement;
    SkipSupportIncDec increment;
} SkipSupportData;

extern SkipSupport PrepareSkipSupportFromOpclass(Oid opfamily,
                                                  Oid opcintype,
                                                  bool reverse);
```

## Invariants

- **INV-FULL-INIT** [from-comment: lines 56-58] All four fields must
  be set; no optional members.
- **INV-OVERFLOW** [from-comment: lines 74-80] When increment is
  called on `high_elem` (or decrement on `low_elem`), `*overflow`
  must be set; the returned Datum is then undefined.
- **INV-NO-LEAK** [from-comment: lines 71-73] Inc/Dec functions
  must not leak memory across calls (skip scans call them in a hot
  loop).
- **INV-NON-NULL** [from-comment: lines 87-89] `existing` is never
  NULL on call.
- **INV-VARIATION-TOLERANCE** [from-comment: lines 80-86] Opclass
  must accept every representational variation of the underlying
  type; need NOT preserve display-only info (e.g. numeric scale).

## Trust boundary (Phase D)

- Skip-support functions are *opclass-internal* C code. An opclass
  shipped by an untrusted extension can register an inc/dec that
  silently mis-counts and produces incorrect query results — same
  trust posture as any opclass operator function.
- Continuous-type opclasses (float, numeric) intentionally do NOT
  ship skip support; the fallback "next-key sentinel" path is
  taken. A buggy opclass that wrongly claims skip support for a
  continuous type would degrade scans, not crash.

## Cross-refs

- `access/nbtree.h` — skip scan internals.
- `utils/relcache.h` — Relation arg.
- B-tree opclass docs.

## Issues

- [ISSUE-API: `low_elem`/`high_elem` are stored as Datums with no
  type tag — caller must remember the column's pass-by-value /
  pass-by-ref convention (low)] — lines 66-68.
