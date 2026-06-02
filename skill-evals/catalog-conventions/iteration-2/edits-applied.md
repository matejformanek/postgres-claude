# Edits applied — iteration 2

Source: `iteration-1/proposed-edits.md`. All four proposed edits applied
to `.claude/skills/catalog-conventions/SKILL.md`. Specific values were
verified against `source/...` before writing.

## Verification of factual claims before writing

- **OID ranges 8000-9999 / 10000-11999 / 16384**: confirmed against
  `source/src/include/access/transam.h:160-197`. Comments state:
  "OIDs 8000-9999 are reserved for development purposes (such as
  in-progress patches and forks)"; `FirstGenbkiObjectId = 10000`;
  `FirstUnpinnedObjectId = 12000`; `FirstNormalObjectId = 16384`.
  Adjusted edit #3 wording: proposed-edits.md said "0-7999 reserved for
  already-committed pins", but the header is more careful — pinned
  built-in OIDs are anywhere below FirstGenbkiObjectId, and there is no
  hard "0-7999 = committed only" rule. Reworded to say committer
  renumbers down to a tidy low-OID range without making the false
  "0-7999" claim. The 10000-11999 = genbki auto-assign claim is exact.
- **`renumber_oids.pl`**: confirmed exists at
  `source/src/include/catalog/renumber_oids.pl`, header comment says it
  "shifts a range of OIDs in the Postgres catalog data to a different
  range, skipping any OIDs that are already in use".
- **`unused_oids`**: confirmed at
  `source/src/include/catalog/unused_oids`. Header comment: "The main
  use is for finding available OIDs for new internal functions."
- **`AddDefaultValues` computes `pronargs`**: name used in the worked
  example matches Catalog.pm convention; safe.
- **`SearchSysCacheCopy1` + `heap_freetuple`**: standard PG API, used
  throughout the backend (e.g. `src/backend/catalog/heap.c`).

## Edits applied

### Edit 1 — OID-policy phrasing (§2)

Replaced the short "8000-9999 + renumber_oids.pl" paragraph with an
expanded version that explains *why* 8000-9999 is the right range
(in-progress patches, project convention to minimise collisions),
references `transam.h`, and clarifies 10000-11999 is the genbki
auto-assign range. Removed the unverified "0-7999 reserved for pins"
phrasing from the proposal.

### Edit 2 — Append-at-end-of-fixed-section bullet (§3)

Added a new bullet at the end of §3 ("Edit the header") instructing the
user to append new fixed-length columns at the end of the fixed-length
section, before any `CATALOG_VARLEN` block, to minimise ABI churn for
code reading `Form_pg_X->existing_field`.

### Edit 3 — Worked pg_proc.dat example (§4)

After the two "don't write" bullets, inserted a worked example showing
a minimal immutable strict int4->int4 row (`oid`, `descr`, `proname`,
`prorettype`, `proargtypes`, `prosrc` only) and an explicit list of
which columns NOT to write because `AddDefaultValues` fills them
(`pronargs`, `provolatile`, `proisstrict`, `proparallel`, `prokind`).
Added a "only diverge from defaults" framing and a counter-example
(stable function → `provolatile => 's'`).

### Edit 4 — Using-a-syscache-from-C mini-section (after §6)

Added a new mini-section "Using a syscache from C" right after the §6
declaration bullet, covering:
- `ReleaseSysCache` pairing rule + "cache reference leak" symptom
- Pointer-lifetime rule (tuple data only valid between Search and
  Release) and the `SearchSysCacheCopy1` + `heap_freetuple` escape hatch
- Miss = `HeapTupleIsValid == false`, not an error from the cache;
  caller-side `elog(ERROR, "cache lookup failed for X %u", ...)` vs
  `ereport(ERROR, ERRCODE_UNDEFINED_<thing>, ...)` idioms
- `SearchSysCacheExists1` for existence-only
- `GetSysCacheOid1` for OID-only
- Note that cross-backend coherence is automatic via shared
  invalidation (added beyond the proposal; addresses eval-3 assertion 8)

## Edits NOT applied

None — all four proposed edits applied, with edit-3's specific factual
phrasing tightened to match `transam.h` exactly.
