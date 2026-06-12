# Persona: Daniel Gustafsson

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (read-only clone). Cross-cut against
  `knowledge/personas/committer-map.md`, `contributor-map.md`,
  `domain-ownership.md`. No external network calls.

## Role + email(s)

- **Primary identity:** `Daniel Gustafsson <dgustafsson@postgresql.org>`
  (committer).
- **Author-trailer identity** (in his own commit bodies): `Daniel Gustafsson
  <daniel@yesql.se>`. Both addresses appear; grep accordingly when mining.
- **Lifetime commits as committer:** 466.

## Activity profile (last 24mo)

Window: 2024-06-11 .. 2026-06-11.

| Metric | Value |
|---|---:|
| Commits as committer (24mo) | 192 |
| Commits as committer (12mo) | 88 |
| `Reviewed-by:` trailers crediting him (24mo, tree-wide) | 156 |
| `Reported-by:` trailers (24mo) | 6 |
| `Author:` / `Co-authored-by:` trailers crediting him (24mo) | 79 |
| `Discussion:` URL on his commits (24mo) | 194 of 192 (most have one, some have multiple) |
| Backpatch references (24mo) | 42 (~22%) |

Reads as: about half the commit rate of Andres/Fujii, but the per-commit
weight is among the largest in 24mo (his single biggest, `f19c0eccae9` "Online
enabling and disabling of data checksums", is 5190 LOC — bigger than anything
in Andres, Rowley, Davis or Fujii's 12mo windows).

## Domain ownership

Path footprint, 24mo:

```
119 doc/src/sgml             ← matches Fujii's docs-heavy profile
 69 src/test/modules         ← test_oauth_validator, test_radius, test_checksums
 58 src/backend/utils
 44 src/interfaces/libpq     ← libpq TLS + auth client
 36 src/backend/postmaster   ← online-checksums background worker launcher
 27 src/backend/libpq        ← server-side auth + TLS
 22 src/test/ssl             ← TLS regression tests
 16 src/bin/psql
 16 src/bin/pg_dump
 12 src/include/libpq
```

Subject prefix histogram:

```
 44 doc        ← #1 prefix
  7 psql
  5 pgcrypto
  5 oauth
  4 ssl
  3 libpq
  2 ci         (he also chips at CI infra)
```

[verified-by-code] His owned-area cluster is the security / auth / transport
column of PG:

- **TLS / SSL / SNI.** `4f433025f66` "ssl: Serverside SNI support for libpq"
  (1926 LOC) introduces a new `pg_hosts.conf` for per-hostname cert selection.
  Also various OpenSSL compatibility fixes (`Fix compilation with OpenSSL 4`,
  `Remove incorrect OpenSSL feature guards`).
- **OAuth.** `b3f0be788afc` "Add support for OAUTHBEARER SASL mechanism" is
  upstream's OAuth landing. Daniel is a co-author and `Reviewed-by:` while
  Jacob Champion is principal author; subsequent oauth fixes ride through
  Daniel's committer bit.
- **Online checksum enable/disable.** The 5190-LOC `f19c0eccae9` is the
  highest-LOC single commit in the bucket-B set. Adds a background worker
  framework that marks all buffers dirty in all databases concurrently, with
  procsignalbarrier coordination to handle the cluster-wide state transition.
  Subsequent stabilization commits ride through him too.
- **pgcrypto + base64url.** `e1d917182c1` "Add support for base64url encoding
  and decoding" (380 LOC); OAuth ecosystem needs this.
- **pg_dump compression API.** `e686010c5b4` "pg_dump: Fix compression API
  errorhandling" (373 LOC) — a structural cleanup of the zstd/lz4/gzip
  compression abstraction, citing four predecessor commits by SHA.

## Style + patterns

- **Title-case imperative subjects, mixed prefixes.** Like Fujii, he uses
  `doc:` heavily but also bare imperative ("Reword activity message to avoid
  truncation", "Improve database detection logic in datachecksumsworker"). No
  fixed prefix scheme. `[verified-by-code]`.
- **Long history-aware commit bodies.** `e686010c5b4` opens with "The API and
  its implementations have evolved over time, notable commits include
  bf9aa490db, e9960732a9, 84adc8e20, and 0da243fed." — naming the
  predecessor SHAs and explaining the lineage before listing the changes. This
  multi-commit-SHA-citation pattern is distinctively his. `[verified-by-code]`.
- **Bulleted enumeration of fix list.** `e686010c5b4`'s body lays out a
  bullet-tree per affected function (`write_func:`, `open_func:`, etc.) — when
  a single commit touches many functions, he writes a structured changelog
  inline. `[verified-by-code]`.
- **Heavy `Reviewed-by:` lists especially on TLS/auth.** `4f433025f66` (SNI)
  has 6 reviewers. The OAuth landing (`b3f0be788afc`) explicitly names "a
  multi-year project with many contributors" — Daniel writes out a paragraph
  of historical contributors in the body, then a structured trailer block.
- **Self-author + self-review combination.** 66 of his 192 commits credit him
  as `Reviewed-by: Daniel Gustafsson` and 76 credit him as `Author:` /
  `Co-authored-by:` — the same author-also-committer pattern as Fujii.
- **`Discussion:` close to 100%.** 194 lines across 192 commits — one
  `Discussion:` URL per commit, sometimes two. `[verified-by-code]`.
- **Backpatch rate ~22%.** Lower than Fujii's 43% but higher than Andres's
  14%. Reflects the mix of long-lived infrastructure (online checksums, SNI)
  vs ongoing bug fixes (OpenSSL 4 compat, pg_dump compression errors).

## Common reviewer / collaborator partners

Reviewers of his commits (24mo):

```
 66 Daniel Gustafsson      — self (committer-also-reviewed convention)
 18 Peter Eisentraut       — TLS, build system
 13 Jacob Champion         — OAuth co-driver
 13 Michael Paquier        — broad code-quality reviewer
 13 Tom Lane               — design / API review
 11 Ayush Tiwari           — repeated co-author + reviewer
  8 Tomas Vondra           — online-checksums coding + review
  7 Heikki Linnakangas     — TLS + checksums lineage
  7 Chao Li
```

Co-authors on his commits:

```
 76 Daniel Gustafsson      — self
 12 Jacob Champion         — OAuth pairing
  6 Chao Li
  5 Tomas Vondra           — online checksums co-driver
  3 Nazir Bilal Yavuz
```

Pairings cluster:

1. **OAuth circle:** Jacob Champion is the main author of OAUTHBEARER and the
   downstream `oauth:` fixes; Daniel committed/co-authored. Together with Peter
   Eisentraut and Antonin Houska they form the OAuth review pool.
2. **Online checksums circle:** Tomas Vondra is the close coding partner; the
   `f19c0eccae9` body explicitly thanks "Tomas Vondra has given invaluable
   assistance with not only coding and reviewing but very in-depth testing."
3. **TLS / OpenSSL circle:** Peter Eisentraut + Heikki Linnakangas for design
   review; Cary Huang, Zsolt Parragi for implementation review.

## What to expect on a patch he would review

- **Multi-version OpenSSL/LibreSSL conditionals checked carefully.** TLS
  patches must compile against OpenSSL 3, 4 (when current), and LibreSSL.
  `4f433025f66` explicitly notes "currently LibreSSL does not support the
  required infrastructure" and `Remove incorrect OpenSSL feature guards` was a
  whole commit. Expect a feature-guard / version-check review on TLS patches.
- **History of the API spelled out.** If your patch touches an abstraction
  with prior commits (pg_dump compression API, libpq SSL handling), he will
  ask the commit body to cite predecessor SHAs. Pre-empt by including them.
- **Test module expected for new infra.** test_checksums, test_oauth_validator,
  test_radius — when he adds infrastructure, he adds a test module under
  `src/test/modules/`. Expect the same demand on infra patches.
- **PG_TEST_EXTRA gating for expensive tests.** Online-checksums tests are
  explicitly gated behind `PG_TEST_EXTRA` because they run pgbench
  concurrently. If your patch adds slow tests, follow this convention.
- **errorhandling discipline on compression / IO paths.** `e686010c5b4`'s
  bullet list is the template: every IO function in an API should be reviewed
  for "what does fclose() failure do?", "is the file descriptor closed on
  error?", "is the compressor cleanup state allocation leaked?"

## Landmark commits (last 12mo)

1. **`f19c0eccae9` Online enabling and disabling of data checksums** (5190
   LOC, the biggest single commit in the 12mo window across all 5 personas).
   Background-worker launcher + procsignalbarrier coordination for cluster-wide
   state transition. Multi-author with Magnus Hagander + Tomas Vondra; long
   list of historical reviewers named in prose. Subsequent commits like
   `bf25e5571b3` (`Improve handling of concurrent checksum requests`),
   `25b922ec582` (`Fix invalid checksum state transition in checkpoints`) are
   his stabilization tail.
2. **`4f433025f66` ssl: Serverside SNI support for libpq** (1926 LOC). New
   `pg_hosts.conf` mechanism, new `ssl_sni` GUC, interaction with TLS init
   hook spelled out (`If the init hook and ssl_sni are both enabled, a WARNING
   will be issued`).
3. **`b3f0be788afc` Add support for OAUTHBEARER SASL mechanism** (multi-year
   project, ~committed via Daniel). Adds `oauth` HBA method, OAuth
   Device-Authorization-Grants client flow, new `validator` plugin framework
   under `contrib/oauth_validator`.
4. **`e686010c5b4` pg_dump: Fix compression API errorhandling** (373 LOC).
   Structural cleanup with bulleted changelog body — the template for "single
   commit touches many functions" commits.
5. **`e1d917182c1` Add support for base64url encoding and decoding** (380
   LOC). Smaller but shows the security-tooling chain: OAuth needs base64url,
   so add it to pgcrypto.

## Notes / hedges

- **Two email identities.** Match both `dgustafsson@postgresql.org` (committer)
  and `daniel@yesql.se` (author/reviewer in trailers). The "self-review" count
  comes via the yesql.se address. `[verified-by-code]`.
- **OAuth is not solo work.** Jacob Champion is the principal author; Daniel
  is the committer + co-author + reviewer. Treat OAuth-touching patches as
  Jacob's review territory primarily, with Daniel as the gatekeeper.
- **Online-checksums work is recent and ongoing.** The pattern of follow-up
  commits (state-transition fixes, throttling param fixes, GUC show_hook
  fixes) suggests this is still stabilizing. New related patches will draw
  scrutiny on cluster-wide barrier semantics.
- **Multi-author OAuth landing pattern.** When a long-thread feature lands
  through him, expect the commit body to include a *prose* paragraph of
  historical contributors as well as the structured trailer block. This is
  not a stylistic preference but a tradition for multi-year features.
  `[verified-by-code]`.
