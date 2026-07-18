# contrib/bloom/blvalidate.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 216
**Verification depth:** full read

## Role

`amvalidate` implementation for bloom opclasses — used by
`amvalidate_opclass()` (and tested by `make installcheck` via the
`opr_sanity` regress) to assert that every operator + support function in
a bloom opfamily is well-formed.
[verified-by-code] `source/contrib/bloom/blvalidate.c:1-12`

## Public API

- `blvalidate(opclassoid) → bool` — returns true iff the opclass passes
  all checks; emits `INFO`-level ereports for each failure (so the
  caller can collect all problems).
  [verified-by-code] `source/contrib/bloom/blvalidate.c:28-215`

## Invariants checked

- INV-1: Support procedures must have `amproclefttype == amprocrighttype`
  (no cross-type registrations in bloom).
  [verified-by-code] `source/contrib/bloom/blvalidate.c:78-86`
- INV-2: `BLOOM_HASH_PROC` (1) must have signature `(opckeytype) →
  INT4`, single-arg, non-strict allowed.
  [verified-by-code] `source/contrib/bloom/blvalidate.c:98-101`
- INV-3: `BLOOM_OPTIONS_PROC` (2) must match the standard
  `amoptsproc_signature` (used by other AMs too).
  [verified-by-code] `source/contrib/bloom/blvalidate.c:102-103`
- INV-4: Any other proc number in the opfamily is rejected.
  [verified-by-code] `source/contrib/bloom/blvalidate.c:105-113`
- INV-5: Operator strategy number must be in `[1, BLOOM_NSTRATEGIES]` (=
  [1, 1]).
  [verified-by-code] `source/contrib/bloom/blvalidate.c:135-145`
- INV-6: Operator `amoppurpose` must be `AMOP_SEARCH` (no ORDER BY
  ops); `amopsortfamily` must be invalid.
  [verified-by-code] `source/contrib/bloom/blvalidate.c:147-157`
- INV-7: Operator signature must be `(lefttype, righttype) → BOOL`.
  [verified-by-code] `source/contrib/bloom/blvalidate.c:159-170`
- INV-8: The opclass's own group MUST contain the HASH proc (the
  OPTIONS proc is optional and skipped in the missing-proc check).
  [verified-by-code] `source/contrib/bloom/blvalidate.c:195-208`

## Notable internals

- All catalog lookups go through `SearchSysCache1` + `SearchSysCacheList1`;
  release at the bottom.
  [verified-by-code] `source/contrib/bloom/blvalidate.c:48-65, 210-212`
- `identify_opfamily_groups` partitions the catalogs by
  (lefttype, righttype). Bloom expects the opclass's "own" group to
  carry all the procs; other groups exist only when the opclass has
  binary-compatible alternates.
  [verified-by-code] `source/contrib/bloom/blvalidate.c:173-193`

## Trust-boundary / Phase-D surface

- This routine is informational — it ereport(INFO) on every problem
  and only returns false to indicate "some issue found". No DoS,
  no privilege boundary.
- Called from `amvalidate` dispatcher in `src/backend/access/index/amvalidate.c`
  which itself is invoked by `pg_opclass`-style management commands and
  the `amvalidate` regression test.

## Cross-refs

- `source/src/backend/access/index/amvalidate.c`.
- `source/src/include/catalog/pg_amproc.h`, `pg_amop.h`, `pg_opclass.h`.
- Pattern reference: `src/backend/access/{hash,btree,gin,gist}/*validate.c`.

## Issues raised

None — meta-validation routine, no execution path.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-bloom.md](../../../subsystems/contrib-bloom.md)
