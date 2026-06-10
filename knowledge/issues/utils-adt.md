# Issues — `utils-adt` (scalar & basic types)

Per-subsystem issue register for `src/backend/utils/adt/` — the
SQL-callable abstract-data-type implementations (type I/O, comparison,
hashing, codecs). See `knowledge/issues/README.md` for the tag
convention, severity scale, and workflow.

**Parent subsystem doc:** (none yet — `src/backend/utils/adt/` is
documented per-file under `knowledge/files/src/backend/utils/adt/`;
this register backs that file-by-file pass.)

**Seeded:** 2026-06-03 by the `pg-file-backfiller` cloud run that
documented the scalar-type cluster (bool, char, name, xid, tid, oid8,
arrayutils, pg_lsn, uuid, mac, mac8, enum, cash, numutils, encode,
quote, ascii). All anchor `4b0bf0788b0`.

**Tenor of the batch:** this cluster is mature, well-defended code.
Nothing in it rises above `maybe`; most rows are `nit`. The recurring
theme is *undocumented invariants* — lookup-table range guards, fixed
buffer sizings, and overflow checks that are correct today but rely on
caller discipline or an off-file dependency that isn't flagged at the
call site. Those are corpus-fix candidates (add a comment / an
accessor), not bugs.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | bool.c:44-92 | undocumented-invariant | nit | `parse_bool_with_len` does not reject trailing chars after a complete keyword; relies on caller passing a tight `len` (only single-char `1`/`0` cases check `len==1`). `boolin` is safe via whitespace-trim, but other callers must pass a tight `len`. | open | knowledge/files/src/backend/utils/adt/bool.c.md §Potential issues |
| 2026-06-03 | name.c:338-342 | undocumented-invariant | nit | `nameconcatoid` uses a fixed `char suffix[20]` for `_%u`; safe for 32-bit Oid (max 12 bytes) and `snprintf`-bounded, but the sizing assumption is undocumented. | open | knowledge/files/src/backend/utils/adt/name.c.md §Potential issues |
| 2026-06-03 | enum.c:135-141 | undocumented-invariant | nit | `enum_in` advertises soft errors via `escontext`, but the `check_safe_enum_use` path always hard-`ereport(ERROR)`s on an uncommitted value (acknowledged in-code as a known shortcoming). | open | knowledge/files/src/backend/utils/adt/enum.c.md §Potential issues |
| 2026-06-03 | cash.c:191,407 | undocumented-invariant | nit | money round-trip is not locale-stable: `cash_in`/`cash_out` re-read `lc_monetary` per call, so a value output under one locale can fail to re-parse under another. | open | knowledge/files/src/backend/utils/adt/cash.c.md §Potential issues |
| 2026-06-03 | cash.c:226,240-241 | stale-todo | nit | long-standing `XXX` / "better heuristics needed" / "doesn't properly check for balanced parens" comments in `cash_in` describing known input-parser looseness. | open | knowledge/files/src/backend/utils/adt/cash.c.md §Potential issues |
| 2026-06-03 | pg_lsn.c:272 | undocumented-invariant | maybe | `pg_lsn_pli`/`pg_lsn_mii` delegate all range enforcement to off-file `numeric_pg_lsn` (numeric.c); no local comment flags the dependency, so a future in-place "optimization" could drop the overflow check. | open | knowledge/files/src/backend/utils/adt/pg_lsn.c.md §Potential issues |
| 2026-06-03 | uuid.c:550 | question | nit | UUIDv7 monotonicity is backend-local only (`static int64 previous_ns`); cross-connection v7 ordering is not guaranteed. Likely intentional; worth noting for consumers who assume global monotonicity. | open | knowledge/files/src/backend/utils/adt/uuid.c.md §Potential issues |
| 2026-06-03 | mac8.c:116,186 | correctness | nit | `<ctype.h>` / `hexlookup` access is currently safe (`ptr` is `unsigned char *` plus a `>127` guard); flagged only as a latent pitfall if `ptr`'s type ever changes — not a present defect. | open | knowledge/files/src/backend/utils/adt/mac8.c.md §Potential issues |
| 2026-06-03 | encode.c:644-658 | question | nit | `pg_base64url_dec_len` deliberately overestimates (rounds srclen up to a multiple of 4); harmless under the len-estimate-must-overestimate contract, flagged so it isn't "tightened" into an underestimate (which would be a buffer overflow). | open | knowledge/files/src/backend/utils/adt/encode.c.md §Potential issues |
| 2026-06-03 | encode.c:174,412,834 | undocumented-invariant | maybe | the 128-entry codec lookup tables (`hexlookup`/`b64lookup`/`b32hexlookup`) rely on per-call-site `<127`/`<128` range guards scattered across the codecs rather than a single bounds-checked accessor; correct today, fragile for a new codec added without the guard. | open | knowledge/files/src/backend/utils/adt/encode.c.md §Potential issues |
| 2026-06-03 | ascii.c:92 | undocumented-invariant | maybe | `ascii[*x - range]` is an unchecked OOB-read shape; correctness depends on each inline translation string being exactly `256 - range` bytes, and the string literals are not length-annotated or asserted. | open | knowledge/files/src/backend/utils/adt/ascii.c.md §Potential issues |
| 2026-06-03 | ascii.c:187 | question | nit | `ascii_safe_strlcpy` admits byte `0x7F` (DEL) via `ch <= 127` while the comment calls the accepted set "printable ASCII"; likely intentional but inconsistent with the comment. | open | knowledge/files/src/backend/utils/adt/ascii.c.md §Potential issues |
| 2026-06-09 | pg_locale_builtin.c:293-295 | info-disclosure | nit | error message echoes the user-supplied locale name (`invalid locale name "%s" for builtin provider`); acceptable since it comes from DBA-controlled SQL. | open | knowledge/files/src/backend/utils/adt/pg_locale_builtin.c.md §Potential issues |
| 2026-06-09 | pg_locale_builtin.c:285-290 | correctness | nit | builtin-provider collation version is hardcoded "1" for all three locales; if the build's Unicode tables change ctype semantics the collversion does not bump (comment notes collversion only tracks sort order). | open | knowledge/files/src/backend/utils/adt/pg_locale_builtin.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- **numutils.c is the reference for "this is how overflow detection
  should look."** Its unsigned-accumulation + pre-store
  `tmp > -(PG_INTnn_MIN/base)` guards and the hard-vs-soft error
  contract (`pg_strtointNN` ereports; `pg_strtointNN_safe` fills an
  `escontext`) are correct and self-documented. No issue row — listed
  here so a future reader doesn't re-flag the gotchas as defects.
- **uuid.c randomness is correct:** both v4 and v7 generators use
  `pg_strong_random` (CSPRNG), not the weak `pg_prng_*`
  (`uuid.c:528,625`). Flagging here because "UUID uses a weak RNG" is
  a common false-positive worth pre-empting.
- **The lookup-table guard pattern recurs** (encode.c codecs, mac8.c
  hex parse, ascii.c translate). A single `[ISSUE-undocumented-invariant]`
  theme: 128/256-entry tables indexed by a byte that *must* be
  range-checked at the call site. Candidate for one small corpus/idiom
  note rather than N separate upstream patches.
- **encode.c output-length contract is sound:** both SQL entry points
  guard `res <= resultlen` → `elog(FATAL)` and pre-`palloc` against
  `MaxAllocSize` (`encode.c:76-91,126-141`); every decode `_len`
  estimator overestimates. The buffer-overflow class is closed here.
