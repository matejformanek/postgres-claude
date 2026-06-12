# Persona: Peter Eisentraut

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (commit bodies parsed for trailers, subjects scanned for prefix patterns, paths bucketed by subsystem) + cross-cut against `committer-map.md`, `contributor-map.md`, `domain-ownership.md`. No mailing-list archives.

## Role + email(s)

- Role: committer (active 24mo), core team member since the early 2000s.
- Primary email: `peter@eisentraut.org` (current). Historical: `peter_e@gmx.net`.
- Lifetime committer rank: **#3 + #6 combined** (4,193 + 2,290 = 6,483 — see `committer-map.md` note: the two emails sum to ~3rd place lifetime).
- Identity rollups: two emails merged in `contributor-map.md`. The old `@gmx.net` shows zero 24mo activity; the cutover predates the window.

## Activity profile (last 24mo: 2024-06-11 .. 2026-06-11)

| Trailer | Count |
|---|---:|
| Commits authored (`%an` as committer) | 719 |
| Commits w/ `Discussion:` URL | 577 (80%) |
| Commits w/ `Backpatch-through:` | **0** |
| Reviewed-by trailer appearances | 152 |
| Reported-by | 29 |
| Author trailer appearances | 16 |
| Co-authored-by | 13 |
| Other (Suggested + Tested + Diagnosed) | 22 |
| **Total trailer appearances** | **219** |

Self-authorship on his pushed commits: only **6 explicit `Author: Peter Eisentraut`**, 506 with no Author trailer (large fraction of all his commits), 207 with someone else as Author. He almost never tags himself as Author — preferring the convention "if I'm the committer and there's no Author trailer, it's me by default."

Cross-verified against `contributor-map.md` row "Peter Eisentraut | 16 | 152 | 29 | 22 | 219" — matches.

## **Striking finding: zero backpatches in 24mo**

Verified via two queries: `--grep='Backpatch-through'` returns 0 and `grep -i 'backpatch'` over his body text returns 0. He committed 719 patches over 2 years and **none of them were back-patched**.

This is unique among the top-5 committers. Tom (23%), Michael (25%), Nathan (20%), Heikki (17%) all routinely back-patch correctness fixes. Peter's commits skew toward:
- **Feature work** that lands only on master (e.g. SQL/PGQ in March 2026).
- **Mechanical cleanup** (unused #includes, meson refactoring, GUC table regeneration) — not back-patch-eligible by convention.
- **Translations** and **doc updates** — also master-only.

What this means in practice: Peter does not handle stable-branch maintenance. Bug fixes that need back-patching reach the back branches via other committers (most commonly Michael Paquier or Tom Lane).

## Domain ownership

From `domain-ownership.md` per-subsystem leadership (24mo):

- `src/backend/commands/` — **top committer** (82 commits, ahead of Álvaro Herrera 74 and Tom Lane 65).
- `src/backend/parser/` — **top committer** (37 commits, ahead of Tom Lane 33).
- `src/backend/catalog/` — **top committer** (37 commits, ahead of Tom Lane 31 and Michael Paquier 28).
- `src/backend/nodes/` — **top committer** (17 commits).
- `src/include/` — **top committer** (196 commits, ahead of Michael Paquier 163).
- `src/bin/` — **top committer** (111 commits, ahead of Michael Paquier 96 and Tom Lane 92).
- `src/common/` — **top committer** (34 commits).
- `contrib/` — **top committer** (90 commits, narrowly ahead of Michael Paquier 87).
- `src/interfaces/` — **top committer** (51 commits, ahead of Tom Lane 46).
- `src/backend/replication/` — co-lead (38 commits, second to Amit Kapila 86).
- `src/pl/` — co-lead (39 commits, second to Tom Lane 43).

**Read:** Peter is the single most cross-cutting committer in PG. He is top committer in **9 subsystems** (more than any other person). His specialty is "the front-end" of the system: parser, catalog, commands, headers, the SQL surface, plus the build system (meson) and the SQL/PGQ feature. He is also the SQL standards expert — features tagged as SQL-standards-driven (`UPDATE/DELETE FOR PORTION OF`, `SQL Property Graph Queries`) reliably land via him.

## Style + patterns

### Commit message style

Subject prefix histogram (top 10):

| Prefix | Count |
|---|---:|
| `Fix ...` | 102 |
| `Remove ...` | 74 |
| `Add ...` | 59 |
| `doc:` | 38 |
| `Make ...` | 23 |
| `Use ...` | 19 |
| `Update ...` | 18 |
| `Improve ...` | 17 |
| `meson:` | 15 |
| `pg_createsubscriber:` | 14 |

- **Shortest average subject length of any persona in this set: 42.6 chars.** Reflects his preference for terse subjects.
- Uses module-tag colon prefix (`doc:`, `meson:`, `pg_createsubscriber:`, `ecpg:`, `pgcrypto:`).
- Frequently runs "Remove unused #include's from ..." batch cleanups — multiple subjects with this prefix appear across the 24mo window.

### Body conventions

`%B` mean ≈ 10.6 lines / commit, **median = 9 lines**. **Shortest typical body length of any persona in this set.** Compare: Tom Lane median 17, Michael Paquier median 15. Peter writes terse, declarative bodies — typically a paragraph of context + trailer block.

Many of his commits are mechanical (translation updates, `meson:` tweaks, `Remove unused #include's`) where the body is one line plus the trailers, pulling the median down. But even his feature commits tend toward terseness.

### Discussion: URL discipline

**80% of his commits cite a `Discussion:` URL** (577/719). Lower than Michael (98%) and Tom (87%). The non-Discussion commits are predominantly **mechanical** — translation imports, meson tweaks, copyright bumps, `pgindent` artifacts. For non-mechanical commits the rate is much higher.

### Backpatch behavior

**Zero backpatches** — see standout finding above. This is the single most distinctive characteristic of Peter's commit profile.

### Author-trailer pattern

Only 6 of 719 commits carry `Author: Peter Eisentraut`. He almost never self-tags. This is the strongest "if I'm committer and no Author trailer, it's me" convention in PG.

506 commits without ANY Author trailer = roughly 70% of his work is implicit-self. The remaining ~30% (213 commits) credit someone else as Author. So he is mostly an own-work pusher, similar to Tom Lane in self-vs-other ratio (~70/30) but with much more aggressive trailer-omission for himself.

### Build-system + tooling ownership

The `meson:` prefix appears 15 times in 24mo subjects and many more times implicitly. Peter is the **de facto meson build-system maintainer**: top-churn commits include "meson: Differentiate top-level and custom targets", "meson: Add headerscheck and cpluspluscheck targets", "meson: Increase minimum version to 0.57.2". Build-system patches that touch `meson.build` files will typically reach him.

The "Remove unused #include's" batch commits (multiple visible in subject sample) are a Peter-signature project-wide cleanup.

## Common reviewer/collaborator partners

Top reviewers credited on commits Peter pushed (24mo):

| Reviewer | Count |
|---|---:|
| Chao Li | 58 |
| Tom Lane | 46 |
| Andres Freund | 27 |
| Peter Eisentraut (self) | 26 |
| Heikki Linnakangas | 26 |
| Bertrand Drouvot | 21 |
| Jelte Fennema-Nio | 13 |
| Nathan Bossart | 13 |
| Dagfinn Ilmari Mannsåker | 13 |
| Ashutosh Bapat | 11 |

**Notable:** Chao Li (58) is the #1 reviewer on Peter's commits. Per `contributor-map.md`, this is consistent with Chao's 340 total R-by appearances (second only to Tom Lane) and his concentration on broad-coverage code review since 2025-08.

Self-credit: 26/719 = 4% — lower than Tom (13%), Michael (14%), Fujii (49%). Peter rarely self-credits as reviewer, possibly because his own-work commits often have no other reviewers tagged either.

**Cross-pairings of note:**
- `Andres Freund` (27 reviews on Peter's commits) — heavy AIO/storage cross-review collaboration.
- `Heikki Linnakangas` (26 reviews on Peter's) — shared interest in storage + access internals.
- `Dagfinn Ilmari Mannsåker` (13 reviews) — Perl + Unicode + meson cross-checking partner.

## What to expect on a patch he would review

1. **He will demand SQL-standards compliance for SQL-surface changes.** Confidence: high. Patches changing user-visible SQL (DML / DDL / new statements) get scrutinized against the standard. Recent SQL/PGQ work and `UPDATE/DELETE FOR PORTION OF` both came through him; his review is the SQL conformance review.

2. **He will run pgindent and meson-warnings checks.** Confidence: very high (he commits the project's mechanical `meson: Fix meson warning` and `pgindent`-fixup work). Patches that trip new meson warnings or that haven't been pgindented will be flagged.

3. **He will NOT backpatch your fix.** Confidence: very high (0/719). If your patch needs to reach a stable branch, expect Peter to commit only to master and rely on another committer to handle the back-branch. Submit with the expectation that backpatch coordination is your job, not his.

4. **He prefers terse commit messages.** Confidence: medium. Median body 9 lines (shortest in this set). If you submit a 50-line body, expect compression. Avoid prose padding.

5. **He may rewrite to drop your Author trailer for himself.** Confidence: low-medium. Peter has only 6 self-Author trailers in 24mo, and 506 no-Author commits. If you submit a patch that's mostly his own design suggestion adapted by you, expect the Author trailer to be ambiguous.

6. **He will accept patches that clean up `#include`s, dead code, or unused headers.** Confidence: high. Multiple "Remove unused #include's" batches in 24mo — he is receptive to project-wide hygiene work that others might consider noise.

## Landmark commits (last 12mo)

- `2f094e7ac69` (Mar 2026): SQL Property Graph Queries (SQL/PGQ) — major feature, 14,960-line diff. The headline SQL-surface feature of the PG18/19 cycle landed by Peter.
- `8e72d914c52` (Apr 2026): Add UPDATE/DELETE FOR PORTION OF — system-versioned-tables-adjacent feature (5,816-line diff). Followed by isolation tests `4824` lines (`b6ccd30d8ff`).
- `63599896545` (Sep 2025): Generate GUC tables from .dat file — restructuring how GUCs are declared (8,425-line diff). Reorganized in `a13833c35f9` (Oct 2025) "Reorganize GUC structs".
- `57ee397953` (Mar 2026): Update Unicode data to Unicode 17.0.0 — recurring but substantial (7,708-line diff).
- `847336ba53a` (Apr 2026): pg_createsubscriber: Use logging.c log file callback — representative tool maintenance.
- `8354b9d6b60` (Feb 2026): Use fallthrough attribute instead of comment — project-wide C cleanup.

## Notes / hedges

- **The "zero backpatches" finding is the single most surprising data point across all 5 personas in this batch.** It does not mean Peter ignores stable branches — it means he does not personally push the back-branch commits. Cross-committer back-patching does happen via Tom Lane and Michael Paquier.
- **Subject length 42.6 chars + median body 9 lines** = the most compressed commit-message profile in the top-5 committer pool. The opposite of Tom Lane's narrative style.
- **SQL/PGQ + UPDATE/DELETE FOR PORTION OF** as landmark features confirm `committer-map.md`'s tag "SQL/PGQ owner."
- **Cross-references:**
  - `michael-paquier.md` — Peter is one of Michael's regular cross-reviewers (11 reviews on Michael's commits).
  - `tom-lane.md` — opposite styles (terse vs narrative); they overlap heavily in `src/backend/parser/`, `src/backend/commands/`, `src/include/catalog/`.
  - `heikki-linnakangas.md` — 26 reviews on Peter's commits; shared storage + access territory.
- **Pure committer or also reviewer?** Peter's 152 R-by appearances (across all commits) is moderate. He reviews broadly but not on the Chao-Li-or-Tom-Lane scale.
