# unicode_version.h

One-line define of the Unicode version the in-tree generated
tables target. (`source/src/include/common/unicode_version.h:14`)
[verified-by-code]

## Purpose

Single source of truth for `PG_UNICODE_VERSION` (currently
`"17.0"`), referenced by docs and by Unicode-aware code paths that
want to advertise their compliance level.

## Key declarations

- `#define PG_UNICODE_VERSION "17.0"`

The file is itself written by hand (not generated) but is updated
in lockstep with the regeneration scripts under
`src/common/unicode/`, driven by
`src/common/unicode/generate-unicode_version.pl`.
[from-comment]

## Phase D notes

- **Version pinning across major releases.** `PG_UNICODE_VERSION`
  is bumped per major PG release (PG 17 → Unicode 15.1, PG 18 →
  Unicode 16.0, PG 19/master → Unicode 17.0). Any persistent on-disk
  artefact whose hash/sort key depends on Unicode tables can become
  invalid across a pg_upgrade if normalization or category output
  changes for in-use codepoints.
- **A13 ltree CRC32 locale-change echo.** ltree's `_ltree_consistent`
  hashes label strings; a Unicode-version-driven case-fold change
  could in principle perturb hashes of mixed-case labels. The risk
  is largely theoretical because ltree label syntax is ASCII-only
  (`A-Za-z0-9_-`), so the Unicode version is moot for ltree. But
  the *general* invariant — "regenerating Unicode tables can
  invalidate on-disk hash/sort keys" — applies to citext indexes,
  pg_trgm GIN indexes built before a major upgrade, and to the
  builtin collation provider.
- **SCRAM-side concern** (also covered in `unicode_norm.h.md`): a
  libpq from PG N talking to a server from PG N+M with a different
  embedded Unicode version could disagree on NFKC of a password
  containing exotic codepoints. In practice libpq is normally
  matched to server major version, but the asymmetry exists.

## Cross-refs

- `source/src/common/unicode/generate-unicode_version.pl` — the
  generator that bumps this define.
- A13 corpus finding: `knowledge/files/contrib/ltree/...` —
  label-hash stability across upgrades.
- A13/A14 finding: `citext` + `pg_trgm` with
  `DEFAULT_COLLATION_OID` — also affected by collation/Unicode
  drift across upgrades.

## Potential issues

None at the header level — single `#define`.
