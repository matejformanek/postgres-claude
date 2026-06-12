# Persona: Jeff Davis

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (read-only clone). Cross-cut against
  `knowledge/personas/committer-map.md`, `contributor-map.md`,
  `domain-ownership.md`. No external network calls.

## Role + email(s)

- **Primary identity:** `Jeff Davis <jdavis@postgresql.org>` (committer).
- **Author-trailer identity** (less commonly visible): `Jeff Davis
  <pgsql@j-davis.com>`. Multiple `Discussion:` URLs in his commits cite
  `j-davis.com` thread hosts.
- **Affiliation hint:** AWS (visible in trailers in nearby work, not asserted
  from log). `[inferred]`.
- **Lifetime commits as committer:** 403.

## Activity profile (last 24mo)

Window: 2024-06-11 .. 2026-06-11.

| Metric | Value |
|---|---:|
| Commits as committer (24mo) | 185 |
| Commits as committer (12mo) | 71 |
| `Reviewed-by:` trailers crediting him (24mo, tree-wide) | 27 |
| `Reported-by:` trailers (24mo) | 2 |
| `Author:` / `Co-authored-by:` trailers crediting him (24mo) | 4 |
| `Discussion:` URL on his commits (24mo) | 185 of 185 (100%) |
| Backpatch references (24mo) | 26 (~14%) |

Reads as: **deepest specialist of the five.** Lowest review-credit count
(27) and lowest author/co-author credit (4) in the bucket — he commits his
own focused work in his own domain, with relatively little cross-area
shepherding of other people's patches. Per-commit footprint is narrow.

## Domain ownership

Path footprint, 24mo:

```
151 src/backend/utils         ← #1 — adt/pg_locale, adt/varlena, adt/regexp
 51 src/test/regress
 48 doc/src/sgml
 46 src/bin/pg_dump
 36 src/include/utils
 32 src/backend/statistics    ← real second domain
 25 src/backend/executor
 24 src/common/unicode        ← Unicode-tables maintainer
 21 src/backend/commands
 15 src/backend/regex
 11 src/bin/pg_upgrade
```

Subject prefixes barely exist:

```
  2 style       (the only repeating prefix)
  2 pg_dump
  1 tsearch
  1 selfuncs.c
  1 pg_upgrade check for Unicode-dependent relations.
  ... [each subject unique]
```

[verified-by-code] **His owned-area cluster is narrow and deep:**

- **ICU + Unicode + collations.** `src/common/unicode/` is essentially his
  module. Multiple landmark commits in 12mo: `27bdec06841d` "Optimization for
  lower(), upper(), casefold() functions" (1194 LOC), `286a365b9c25` "Support
  Unicode full case mapping and conversion" (with full-codepoint mapping for
  e.g. ß→SS), `4e7f62bc386a` "Add support for Unicode case folding",
  `af164f31b9f` "Add `pg_iswalpha()` and related functions", `3853a6956c3`
  "Use C11 `char16_t` and `char32_t` for Unicode code points".
- **`pg_locale.h` / ctype method tables.** `5a38104b364` "Control ctype
  behavior internally with a method table" (1194 LOC) — refactor from
  per-provider branching to method-table dispatch. Stated rationale: "a step
  toward multiple provider versions, which we may want to support in the
  future". Sets up the next round of his collation work.
- **CREATE SUBSCRIPTION ... SERVER.** `8185bb53476` (1320 LOC) — adds the
  ability to specify a foreign server as the connection source for a logical
  subscription. Co-authored with Corey Huinker.
- **pg_dump / pg_dumpall option set.** `6a46089e458` "Simplify options in
  pg_dump and pg_restore" (336 LOC), `6d22c67c3bf` "Don't accept length of -1
  in pg_locale.h APIs" — boundary-tightening commits.
- **Pattern matching prefix extraction.** `9c8de159691` "Use multibyte-aware
  extraction of pattern prefixes" — `src/backend/regex/` touches.

## Style + patterns

- **Imperative-mood title, often punctuated.** "Control ctype behavior
  internally with a method table.", "Optimization for lower(), upper(),
  casefold() functions." — both end with periods. `[verified-by-code]`.
- **Short, dense commit bodies.** Average body ~5-15 lines in his recent
  commits, much shorter than Andres or Daniel. `5a38104b364` body is 6 lines
  total. `4e7f62b` body is one sentence: "Expand case mapping tables to include
  entries for case folding, which are parsed from CaseFolding.txt." This is
  the most compact body style of the five personas.
- **Forward-looking design rationale.** Bodies often justify a refactor by
  pointing at the next step: "This is also a step toward multiple provider
  versions, which we may want to support in the future." (`5a38104b364`). He
  expects to come back. `[verified-by-code]`.
- **Concrete Unicode examples in the body.** `286a365b9c25` body lists three
  examples: "ß" uppercasing to "SS", final sigma conditional, "ǆ" titlecase
  variant. Examples are the spec — the body teaches what the standard requires.
  `[verified-by-code]`.
- **Discussion URL on every commit, often more than one.** 185 of 185
  commits have a `Discussion:`. `286a365b9c25` has *two* Discussion URLs (a
  recurring pattern when prior discussion on a related thread is relevant).
  `[verified-by-code]`.
- **Sparse Reviewed-by trailer blocks.** Most of his commits have 1-3
  reviewers (often Peter Eisentraut + Andreas Karlsson). Compare to Fujii's
  15-reviewer block on `a8f45dee917`. He moves through narrow review.
  `[verified-by-code]`.
- **Author lineage credited via prose, not always trailer.** `27bdec06841d`
  body: "Other approaches were considered ... a radix tree, or perfect hashing.
  The author implemented and tested these alternatives and settled on the
  generated branches." This narrates the design history without naming the
  alternatives in trailers.
- **Backpatch rate (~14%) is the lowest in the bucket.** Most of his work is
  master-only feature/refactor. `[verified-by-code]`.

## Common reviewer / collaborator partners

Reviewers of his commits (24mo):

```
 22 Peter Eisentraut        — primary collation/locale reviewer
 13 Chao Li
  6 Andreas Karlsson        — locale / Unicode reviewer
  5 Corey Huinker           — pg_dump / subscription work
  4 Tom Lane
  3 David Rowley            — perf overlap on regexp prefix work
  3 Heikki Linnakangas
  3 Nathan Bossart
  3 Noah Misch
```

Co-authors on his commits:

```
 16 Corey Huinker            — CREATE SUBSCRIPTION ... SERVER co-driver
 11 Andreas Karlsson         — Unicode tables, ICU work
  3 Yugo Nagata
  3 Jeff Davis               — self (only 3 — very low self-co-author count)
  1 Fujii Masao
  1 Álvaro Herrera
```

Pairings cluster:

1. **Peter Eisentraut is the collation/locale reviewer of record.** 22 of his
   27 review credits in 24mo. If your patch touches `src/backend/utils/adt/`
   collation or `src/common/unicode/`, expect Peter Eisentraut in the trailer
   block.
2. **Corey Huinker is the close partner on subscription work** (16 co-authors).
   `8185bb53476` (CREATE SUBSCRIPTION ... SERVER) is the recent example.
3. **Andreas Karlsson is the Unicode co-driver.** When the work is collation
   tables / `pg_locale.c` provider plumbing, Andreas appears as both reviewer
   and co-author.
4. **Very small circle overall.** This is the narrowest collaboration profile
   in the bucket — Davis works in tight loops with 2-3 partners.

## What to expect on a patch he would review

- **Unicode standard fidelity.** If your patch touches case mapping, casing,
  or collation tables, expect Unicode-version-aware review. He has just
  added full SpecialCasing.txt + CaseFolding.txt support; expect a request to
  cite the Unicode TR / RFC behind any behavior decision.
- **Method-table dispatch preferred to provider branching.** `5a38104b364`
  refactored away "branched based on the provider" code. New code that adds
  `if (locale->provider == COLLPROVIDER_LIBC) ... else if ICU ...` will draw a
  "use the method table" review.
- **`length=-1` and "magic" API values rejected.** `6d22c67c3bf` removed `-1`
  as a valid length in `pg_locale.h`. Sentinel ints in APIs draw scrutiny.
- **C11 `char16_t` / `char32_t` typedefs for code points.** `3853a6956c3`
  moved Unicode code-point types to C11 standard types. Patches still using
  `pg_wchar` or `uint32` for codepoints may draw a typedef-update request.
- **Concrete failure example expected.** When a patch claims to "fix Unicode
  handling", he asks for the specific codepoint that breaks. See his own
  bodies for the model (ß, ǆ, final sigma).
- **Short bodies are fine.** Don't pad. His own bodies show that a clear
  one-sentence rationale is acceptable.

## Landmark commits (last 12mo)

1. **`8185bb53476` CREATE SUBSCRIPTION ... SERVER** (1320 LOC). Adds the ability
   to source a logical subscription from a foreign-server connection rather
   than a literal connection string. Co-authored with Corey Huinker.
   Cross-cuts subscription, foreign-server, and pg_dump support.
2. **`5a38104b364` Control ctype behavior internally with a method table**
   (1194 LOC). Refactor from per-provider branching to a method table.
   Explicitly framed as enabling "multiple provider versions" future work.
3. **`286a365b9c25` Support Unicode full case mapping and conversion** (165
   LOC, but high-impact). Adds SpecialCasing.txt processing — ß→SS,
   conditional final sigma, titlecase variants.
4. **`27bdec06841d` Optimization for lower(), upper(), casefold() functions**
   (1194 LOC). Compact case-mapping tables using 16-bit offsets + a
   generated nested-branches function. Body narrates the design exploration
   (radix tree, perfect hashing) before settling on generated branches.
5. **`3853a6956c3` Use C11 char16_t and char32_t for Unicode code points**
   (528 LOC). Codebase-wide typedef migration for Unicode code-point types.
6. **`af164f31b9f` Add pg_iswalpha() and related functions** (446 LOC).
   Adds wide-character classification functions internal to PG (rather than
   relying on libc `iswalpha()`).

## Notes / hedges

- **Lowest review-credit count in the bucket (27).** Combined with the
  highest specialization (151 of 185 commits touch `src/backend/utils/`), this
  is the clearest "deep specialist" profile of the five. Don't expect him as
  a generalist gatekeeper outside his domain.
- **Lowest co-author count (4) too.** He drives most of his own patches. The
  exceptions are subscription / pg_dump work where Corey Huinker is the
  driver and Davis the committer.
- **Method table refactor is recent and ongoing.** The ctype method-table
  refactor (`5a38104b364`, 2025-07) is recent enough that follow-up commits
  fitting locale work into the new dispatch are still landing. Expect this to
  drive review feedback on new locale code.
- **Affiliation is inferred only.** Several other AWS PG hackers (Mark Dilger,
  Mike Stonebraker historically) overlap in the corpus, and `j-davis.com` is
  his personal domain. Don't state affiliation as fact in a review.
  `[unverified]`.
- **Discussion URL on 100% of his commits — the cleanest of the five.**
  Including his shortest one-sentence bodies. The Discussion: trailer is
  evidently non-negotiable for him. `[verified-by-code]`.
