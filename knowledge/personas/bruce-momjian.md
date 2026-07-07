# Persona: Bruce Momjian

- Last verified: 2026-06-12
- Source pin: e18b0cb7344
- Method: `git log` mining of `source/` (committer-filtered, 24 months) + cross-cut against `knowledge/personas/committer-map.md`, `contributor-map.md`, `domain-ownership.md`.

## Role + email(s)

- Committer email: `bruce@momjian.us`
- One of the project's two oldest active committers (Tom Lane, Bruce Momjian dominate all-time commit volume — together ~48% of master per `contributor-map.md`'s lifetime-commits table).
- Effective role today is **release-process owner** and **documentation/markup gardener** rather than feature committer. He writes and curates the release notes for each major version, runs the copyright-year bumps, and does many small SGML/cosmetic doc fixes.
- Affiliation: long-time contributor under EDB.

## Activity profile (last 24mo) — trailer counts

| Metric | Count | Source |
|---|---:|---|
| Commits as committer (24mo) | 168 | `committer-map.md`; verified by `/usr/bin/git -C source/ log --since='2024-06-12' --committer='Bruce Momjian'` |
| Of which subject matches `doc:` / `relnotes` / `copyright` | 144 (≈86%) | `git log ... --pretty='%s' | grep -ciE 'doc:|relnotes|copyright'` |
| Commits with Reviewed-by trailer | 2 | `git log ... --pretty='%B' | grep -ci '^Reviewed-by:'` — only 2 over 24mo |
| Distinct external reviewers credited (24mo) | 2 (Laurenz Albe, Erik Wienhold; one credit each) | same query |
| Total reviews credited by him on others' work (lifetime, per `committer-map.md`) | 72 | `committer-map.md` |

The Reviewed-by number is the most distinctive: **2 out of 168 commits carry any Reviewed-by trailer**. He is not reviewing community patches at any scale; his workstream is process-side.

**Subsystem footprint (24mo, his commits only — top dirs):**

| Path | Touched files-count | Why |
|---|---:|---|
| `src/backend/utils/` | 533 | Almost all from copyright-year bumps; `Update copyright for 2025`, `Update copyright for 2026` |
| `src/backend/access/` | 337 | Same — copyright sweep |
| `src/test/modules/` | 253 | Same — copyright sweep |
| `doc/src/sgml/` | 236 | Release-notes work + markup gardening |
| `src/include/catalog/` | 220 | Copyright sweep |
| `src/include/utils/` | 186 | Copyright sweep |
| `src/include/access/` | 182 | Copyright sweep |
| `src/backend/storage/` | 132 | Copyright sweep |

**Important caveat for committer-map readers:** the "src/backend/utils, src/backend/access, src/backend/storage" footprint in `committer-map.md` looks like a substantive backend committer at a glance. It is not — it is the wake of 1-2 copyright-bump commits per year that touch ~thousands of files apiece. His actual hands-on subsystem is `doc/src/sgml/release-NN.sgml` (note: this file is hand-edited release-notes prose; the rest is bulk-mechanical).

## Domain ownership

- **Release notes (`doc/src/sgml/release-19.sgml`, previously release-17/18).** Owner. He drafts the initial release-notes file for each major release (`a724c78` first PG 18 draft; `f0577816865` first PG 19 draft) and then accepts dozens of small "various corrections", "add missing X", "remove author Y", "fix typo" follow-ups from community email. Sample subjects from the 24mo log:
  - "doc PG 19 relnotes: first phase of markup additions"
  - "doc PG 19 relnotes: various fixes reported via email"
  - "doc PG 19 relnotes: corrections reported to me privately"
  - "doc PG 19 relnotes: remove 'Lakshmi N' as author of checksums"
- **Copyright-year stamping** (annually, January 1st). Owner. `451c439` (Update copyright for 2026), `2025-Jan` (Update copyright for 2025). These two commits alone account for >2,000 file touches each.
- **Doc / SGML markup gardening.** Owner of small cleanup pass commits: "doc: add missing xreflabel", "doc: add comma to UPDATE docs, for consistency", "docs: fix text by adding/removing parentheses". These commits average 1-3 files each.
- **Release-note tooling (Perl scripts).** Owns `src/tools/codelines` (recently removed) and `add_commit_links.pl`. Sample: `0c6d572c117` ("add_commit_links.pl: error out if missing major version number"), `f0577816865` ("Improve Perl script which adds commit links to release notes").
- **`pg_upgrade` (historical).** Not visible in the 24mo window's *committer* data, but he is the long-running maintainer/architect — `[from-comment, not verified-by-code in this window]`.

## Style + patterns

- **Lower-case subject lines starting with the scope** ("doc:", "doc PG 19 relnotes:", "tools:", "scripts:") — distinct from the canonical PG imperative-capitalized style. This is his personal convention and is stable across the 24mo window.
- **Short bodies, often a single sentence or none.** Release-notes follow-ups frequently have empty bodies — the subject IS the change.
- **No `Discussion:` trailer on most commits.** Spot-check across his last 30 commits: 0 had `Discussion:` (vs. Amit Kapila's 100% rate). Process work doesn't go through a hackers thread.
- **Almost no `Reviewed-by:`, `Author:`, or `Co-authored-by:` trailers.** Because the changes are his own process work, attribution machinery is unused.
- **High-fan-out single commits.** The annual copyright bump (`Update copyright for 2026` = `451c439`) is the single highest-fan-out commit in the repo — thousands of file touches in one go. This skews any "top directories" analysis if you don't filter it out.
- **Self-correcting follow-up pattern on release notes.** Notes get a first draft (mid-Q2 of a release cycle), then 50-100 small "various corrections", "update to current", "merge items", "add missing X" commits over the following weeks as the community reads the draft and emails him fixes. He commits these batched into 1-5-line edits.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none — persona has no owned paths that overlap any scenario's files)_

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none)_

<!-- /persona-subsystems:auto -->

## Common reviewer / collaborator partners

- Effectively **none**. Across 168 24mo commits there are 2 Reviewed-by trailers (Laurenz Albe, Erik Wienhold; one each, both on doc-substance commits). No `Author:` or `Co-authored-by:` trailers in the substantive set.
- Implicit collaboration is **"the community emailing him privately about release notes"** — visible in subjects like "various corrections reported to me privately" (`f3ae1ec` — wait, that's Kapila; Bruce's analogous one is "doc PG 19 relnotes: corrections reported to me privately"). These email-fix loops do not surface as git trailers, so the contributor-graph cross-cut from `contributor-map.md` does not capture his collaboration network.
- He is not part of any subsystem subteam (contrast Amit Kapila's tight Fujitsu logical-rep pool, or Andres Freund's AIO cluster).

## What to expect on a patch he would review

This is the section where the template strains for Bruce. **He does not review feature patches.** Per `committer-map.md`'s reviewer table, his lifetime Reviewed-by count is 72 — small for a top-2 lifetime committer. The 24mo number of *commits he applied that credit a reviewer* is 2.

Concrete expectations if a patch lands in his lane:

1. **If it touches `doc/src/sgml/release-NN.sgml`,** he is the right person to email. He merges release-notes fixes himself, often within hours of receiving the email, and does not usually push the change back to a hackers thread.
2. **If it touches a Perl helper under `src/tools/`** related to release-notes (`add_commit_links.pl`, `codelines`), same.
3. **For feature patches** (executor, storage, AM, replication) — do not expect Bruce to review. Route to the relevant subsystem committer.
4. **If the patch is a "consistency / typo" doc fix,** he is one of the most responsive committers and will likely apply it as a one-line commit with no review trailer.
5. **If the patch is the annual copyright bump,** he runs it himself.

## Landmark commits (last 12mo)

1. **`451c4392ce6` — Update copyright for 2026** (Jan 2026). Annual ritual. Touches thousands of files. This is the canonical example of a "high-mechanical-volume" commit that distorts subsystem-touch counts.
2. **`a724c78dc69` — doc: first draft of PG 18 release notes** (mid-2025). The initial release-notes drop that anchored all the subsequent PG 18 doc work. The pattern: first draft → ~80 follow-up "doc PG 18 relnotes: ..." commits over the next month.
3. **`f0577816865` — doc: first draft of PG 19 release notes** (Q2 2026). Same pattern repeating for the next cycle.
4. **`46b4ba533ce` — Fix PG 17 [NOT] NULL optimization bug for domains** (one of his rare non-doc commits in the window). Demonstrates he still does the occasional substantive fix when it's in a corner he historically owned.
5. **`257210455257` — scripts: add Perl script to add links to release notes** (recent). Process-tooling improvement that he wrote and uses for his own workflow.

## Notes / hedges

- **Do NOT over-claim review patterns.** The brief flagged this explicitly; the data confirms it. Bruce's lane is publication + process, not feature review.
- The 86% `doc:` / `relnotes` / `copyright` subject-line rate is computed only from his 24mo subjects; the remaining 14% is the doc-tooling Perl-script work plus a handful of small fixes. This is consistent with `committer-map.md`'s "release notes + copyright-year bumps; docs" characterization.
- His "top subsystems" in `committer-map.md` (`src/backend/utils`, `src/backend/access`, `src/backend/storage`) are an artifact of the annual copyright sweep. Any future tool that ranks committer-subsystem affinity should exclude pure copyright/relnotes commits when computing affinity.
- `[from-comment]` for the EDB affiliation; not directly visible in his commit-email but well-known from public PG community history.
- His all-time #2 committer rank (per `contributor-map.md` lifetime table) does not translate into a current-day feature lane; the rank reflects 25+ years of small process commits at high frequency.
