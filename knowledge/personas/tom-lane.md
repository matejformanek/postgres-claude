# Persona: Tom Lane

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (commit bodies parsed for trailers, subjects scanned for prefix patterns, paths bucketed by subsystem) + cross-cut against `committer-map.md`, `contributor-map.md`, `domain-ownership.md`. No mailing-list archives.

## Role + email(s)

- Role: committer (active 24mo), core team member since the late 1990s.
- Primary email: `tgl@sss.pgh.pa.us` — single identity, never changed.
- Lifetime committer rank: **#1** (16,794 lifetime commits — see `committer-map.md`).
- Identity rollups: none. Only one `<name, email>` pair in the log.

## Activity profile (last 24mo: 2024-06-11 .. 2026-06-11)

| Trailer | Count |
|---|---:|
| Commits authored (`%an` as committer) | 661 |
| Commits w/ `Discussion:` URL | 576 (87%) |
| Commits w/ `Backpatch-through:` | 151 (23%) |
| Reviewed-by appearances (across all commits) | 352 |
| Reported-by appearances | 78 |
| Author trailer appearances | 216 |
| Co-authored-by appearances | 26 |
| Other (Suggested + Tested + Diagnosed) | 58 |
| **Total trailer appearances** | **704** (12% of all 5,752 24mo commits) |

Self-authorship on his pushed commits: 208 with `Author: Tom Lane`, 325 with no Author trailer (implicit self), 128 with someone else as Author. So roughly **80% of what he pushes is his own work**; 20% is committing others' patches.

Numbers cross-verified against `contributor-map.md` row "Tom Lane | 216 | 352 | 78 | 58 | 704" — matches exactly.

## Domain ownership

From `domain-ownership.md` per-subsystem leadership (24mo):

- `src/backend/utils/` — co-lead (137 commits, behind Michael Paquier 168 and Peter Eisentraut 164).
- `src/backend/snowball/` — **sole maintainer**. The recurring "Update to latest Snowball sources" commits are his (`7dc95cc3b94`, 63k lines changed Jan 2026).
- `src/backend/executor/` — **top committer** (39 commits), narrowly ahead of David Rowley (37).
- `src/backend/optimizer/` — co-lead (41 commits, second to Richard Guo at 85).
- `src/backend/commands/` — top-3 (65 commits, behind Peter Eisentraut 82 and Álvaro Herrera 74).
- `src/pl/` — **top committer** (43 commits across plpgsql/plperl/plpython/pltcl).
- `src/interfaces/ecpg/` — heavy maintenance (115 file-touches; he is the de-facto ecpg maintainer).
- `src/test/regress/` — second-highest churn (184 commits, behind Michael Paquier 249).
- `doc/src/sgml/` — top-4 (101 commits).

**Read:** Tom is the closest thing PG has to a generalist "anywhere is my domain" committer. The path histogram is unusually flat — no single subsystem dominates >15% of his work. He is also the sole long-term steward of two niche corners (Snowball, ecpg) that nobody else touches systematically.

## Style + patterns

### Commit message style

Run: `rtk proxy git -C source/ log --since='2024-06-11' --author='tgl@sss.pgh.pa.us' --pretty='%s'`.

Subject prefix histogram (top 20):

| Prefix | Count |
|---|---:|
| `Fix ...` | 113 |
| `Doc:` / `doc:` | 47 |
| `Avoid ...` | 35 |
| `Remove ...` | 30 |
| `Add ...` | 29 |
| `Improve ...` | 26 |
| `Make ...` | 25 |
| `ecpg:` | 16 |
| `Use ...` | 16 |
| `Don't ...` | 16 |
| `Allow ...` | 14 |
| `Update ...` | 12 |

- **Imperative mood**, always. Never "Fixed", never "Fixing".
- **Average subject length: 56 chars** — well under the 72-char informal limit.
- Uses subsystem-tag colon prefix sparingly (`Doc:`, `ecpg:`, `pgindent:`) — only when the change is wholly inside that area. Most patches land with bare imperative title (`Fix missed checks for hashability of container-type equality.`).
- Almost every subject ends with a period. Example sample: 47/50 of recent subjects checked end with `.`.

### Body conventions

`%B` mean = 19.6 lines / commit, **median = 17 lines**. This is the **longest typical body length of any active committer** (Bruce Momjian's release-notes commits aside).

Bodies follow a recurring 4-part structure (verified by reading ~15 random bodies):

1. **Symptom paragraph.** What user-visible thing was wrong. ("...we could attempt to use hashing for a `ScalarArrayOpExpr` on a container type when it won't actually work, leading to 'could not identify a hash function ...' runtime failures.")
2. **Root-cause paragraph.** Why. Often references prior commits by SHA-prefix.
3. **Fix paragraph.** What this commit does, with discussion of API/back-compat tradeoffs. He **explicitly calls out when he chose NOT to change something** ("We mustn't change the API of that exported function in a back-patched fix...").
4. **Trailer block.** `Reported-by:`, `Author:`, `Reviewed-by:`, `Discussion:`, `Backpatch-through:`.

Cited example: `06e94eccfd9` (Sep 2025, "Fix missed checks for hashability of container-type equality") — textbook 4-part structure, 30+ lines of body, ends with `Backpatch-through: 14`.

### Discussion: URL discipline

**87%** of his 24mo commits carry a `Discussion:` URL (576/661). The remaining 13% are mechanical (`Pre-beta mechanical code beautification, step 1: run pgindent.`, tzdata bumps, `.gitignore` adds, copyright bumps). For non-mechanical commits the `Discussion:` rate approaches 100%.

### Backpatch behavior

**23% of his commits are backpatched** (151/661) — the highest absolute count of any committer and roughly 30% above the project-wide 18% backpatch rate. This reflects his focus on correctness fixes that must propagate to stable branches.

Backpatch range varies: he routinely backpatches as far as 13 or 14 (the oldest supported branch in the window). Example: `06e94eccfd9` `Backpatch-through: 14`.

### Author-trailer pattern (his own commits)

Of 661 commits he pushed in 24mo:
- 208 carry `Author: Tom Lane` (he self-tags when there was a separate Reported-by/Reviewed-by).
- 325 carry no `Author:` trailer (implicit self — usually small/obvious fixes).
- 128 carry `Author: <someone else>` (he committed their patch).

So he's roughly 80% his-own-work / 20% committing-others. Compare e.g. Michael Paquier whose ratio is reversed: most of MP's commits are credited to other Authors.

### Self-review

He self-credits as `Reviewed-by: Tom Lane` on **86 of his own 661 commits = 13%**. This is the convention "I was the only/lead reviewer here" — see `contributor-map.md` notes on self-review prevalence. Note that the 352 total Reviewed-by appearances mostly fall on **other** committers' commits (he reviews ~265 patches/year that he doesn't push).

### Revert/fixup pattern

Searched subjects for `^Revert ` / `^Re-` / `oops`-style: found in 24mo only ~10 revert subjects, several of which are reverting OTHER people's commits (e.g. revert of a problematic patch he caught in beta). Self-fixup pattern is rare; he tends to get it right the first time or land follow-ups under non-fixup-styled subjects.

## Common reviewer/collaborator partners

From his commits (top reviewers credited on commits **he pushed**, 24mo):

| Reviewer | Count |
|---|---:|
| Tom Lane (self) | 86 |
| Chao Li | 12 |
| Andres Freund | 12 |
| David Rowley | 8 |
| Andrey Borodin | 7 |
| Pavel Stehule | 7 |
| Jim Jones | 6 |
| Matheus Alcantara | 6 |
| Heikki Linnakangas | 5 |
| Peter Eisentraut | 5 |
| Nathan Bossart | 5 |

From `contributor-map.md`'s "Top crediting committers" for Tom Lane: he gets credited on his own commits 321 times (as expected since he pushes 661), and on Nathan Bossart's commits 59 times. He cross-reviews Nathan's work heavily.

Notable absences: he is **not** in Amit Kapila's logical-rep reviewer cluster, **not** in the AIO reviewer cluster (Andres / Noah / Melanie / Bilal / Matthias). His review territory is everywhere EXCEPT those tight subteams.

## What to expect on a patch he would review

Inferred from his commit-message bodies + the patches he amended/rewrote (see "Author=other: 128" above — most carry a paragraph explaining what he changed about the submitted patch):

1. **He will rewrite your commit message.** Confidence: high. His own subjects are precisely 56 chars on average, his bodies follow a 4-part structure, and the commits he pushes with `Author: <other>` virtually always have his style fingerprint on the message. If you submit a patch with a terse subject like "fix bug in X", expect it to land with a 25-line body explaining the symptom, root cause, and fix.

2. **He will probe API/ABI back-compatibility carefully.** Example: `06e94eccfd9` explicitly discusses "We mustn't change the API of that exported function in a back-patched fix" and invents `_ext` wrapper rather than break callers. Expect pushback on a patch that changes a signature in `src/include/` headers without justifying.

3. **He will ask for `Discussion:` URL.** 87% of his commits cite one; the others are mechanical. If your patch landed in his queue without a mailing-list thread, expect him to either find the thread himself or push back asking for one.

4. **He will push back on hashability/typecache/cache-invalidation hand-waving.** Several recent commits (`06e94eccfd9`, `4b1e18b057`, others on container-type equality and casting) show he tracks the interaction between operator strategy, type-cache lookup, and planner assumptions very carefully. Patches in this area should anticipate questions like "what about ranges?", "what about composite types?", "is this safe under domain wrappers?".

5. **Backpatch implications will be part of the review.** Roughly a quarter of what he commits gets backpatched. Expect him to ask "should this go to 14?" on any correctness fix. A patch framed as "for master only" without explaining why it's not back-patch-safe will get questioned.

6. **He does NOT typically push back on coding style nits.** Verification: the project runs `pgindent` mechanically; he commits the "Pre-beta mechanical code beautification" step himself (`020794ee42a3`). Style is a tooling concern, not a review concern.

## Landmark commits (last 12mo)

Selected by lines-changed AND/OR design significance (not just churn — the Snowball update is huge but uninteresting).

- `0dca5d6f6dd` (Aug 2025): Change SQL-language functions to use the plan cache. — Long-pending SQL-function-execution rework; cited in `committer-map.md` as his 24mo landmark.
- `282b1cde9de` (Jan 2026): Optimize LISTEN/NOTIFY via shared channel map and direct advancement. — Substantive performance work in a notoriously tricky subsystem (1,345-line diff).
- `bc6374cd76a` (Dec 2025): Change IndexAmRoutines to be statically-allocated structs. — Internal API rework, follow-up to broader index-AM refactors (1,017-line diff).
- `83a56419457` (Sep 2025): Provide more-specific error details/hints for function lookup failures. — Quality-of-error-message work that touches parser+catalog+errors (724-line diff).
- `45762084545` (Jan 2026): Force standard_conforming_strings to always be ON. — Long-deferred compatibility decision finally landed (816-line diff).
- `4eda42e8bdf` (Dec 2025): ecpg: refactor to eliminate cast-away-const in find_variable(). — Representative ecpg maintenance, an area only he works on.

## Notes / hedges

- **The Snowball commits are noise for persona purposes.** `7dc95cc3b94` (63k lines) is mostly auto-generated stemmer data. Don't read it as a code-design landmark.
- **No employer/affiliation claim.** This doc does not infer or assert affiliation. Visible only: `@sss.pgh.pa.us` is a personal domain.
- **Review "voice" not characterized.** This doc reads commit messages, not mailing-list responses. Patterns like "tone of pushback" or "asks for benchmark numbers" would require mining pgsql-hackers archives, which is out-of-scope per Phase B rules. Calibration in Phase C should fold in actual review-thread reading.
- **Cross-references:**
  - Heavy collaborator with `nathan-bossart.md` (cross-review on src/port + arch-specific code).
  - Co-reviews optimizer work with `peter-eisentraut.md` and Richard Guo (not yet a deep persona).
  - Does NOT collaborate closely with `heikki-linnakangas.md` on AIO/storage rework — different territories.
