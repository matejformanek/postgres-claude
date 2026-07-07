# Persona: Fujii Masao

- **Last verified:** 2026-06-12
- **Source pin:** e18b0cb7344
- **Method:** `git log` mining of `source/` (read-only clone). Cross-cut against
  `knowledge/personas/committer-map.md`, `contributor-map.md`,
  `domain-ownership.md`. No external network calls.

## Role + email(s)

- **Primary identity:** `Fujii Masao <fujii@postgresql.org>` (committer).
- **Author trailer identity** (seen in his own commit bodies): `Fujii Masao
  <masao.fujii@gmail.com>` — distinct from the committer email; relevant when
  greping for `^Reviewed-by:.*Fujii`.
- **Affiliation hint:** NTT DATA (visible in trailers and `oss.nttdata.com`
  Discussion thread hosts). `[inferred]`.
- **Lifetime commits as committer:** 748.

## Activity profile (last 24mo)

Window: 2024-06-11 .. 2026-06-11.

| Metric | Value |
|---|---:|
| Commits as committer (24mo) | 232 |
| Commits as committer (12mo) | 168 |
| `Reviewed-by:` trailers crediting him (24mo, tree-wide) | 144 |
| `Reported-by:` trailers (24mo) | 7 |
| `Author:` / `Co-authored-by:` trailers crediting him (24mo) | 107 |
| `Discussion:` URL on his commits (24mo) | 231 of 232 — essentially 100% |
| Backpatch references (24mo) | 99 (~43%) |

Reads as: very high backpatch share (~43% vs Andres ~14%, Rowley ~20%) — Fujii
ships a lot of bug fixes that he carries to released branches. Also a heavy
self-author / self-co-author (98 of 232 commits credit himself in `Author:` or
`Co-authored-by:` trailer).

## Domain ownership

Path footprint, 24mo:

```
117 doc/src/sgml             ← #1 by file-touches: huge doc footprint
 89 src/test/regress         ← regression-test churn alongside the bug fixes
 37 src/backend/replication  ← walsender / walreceiver / subscription
 25 src/backend/commands     ← SUBSCRIPTION commands, COPY, REPACK
 22 src/bin/psql             ← tab completion, \d formatting
 19 src/backend/access       ← heap/index touch when fixing replication issues
 17 src/bin/pg_dump          ← pg_dump fixes (often catalog-related)
 17 src/backend/utils
 11 src/interfaces/ecpg      ← ecpg owner-ish
 10 contrib/postgres_fdw/connection.c
```

Subject prefix histogram (24mo) makes the docs lean even clearer:

```
 55 doc        ← over 1 in 4 of his commits is a "doc:" commit
 14 psql       ← tab completion + meta-command tweaks
  9 pgbench
  7 postgres_fdw
  5 pg_dump
  5 file_fdw
  5 ecpg
  4 pg_restore
  4 pg_recvlogical
```

[verified-by-code] His owned-area cluster is:

- **Replication shutdown + walsender lifecycle.** Multiple landmark commits
  (`a8f45dee917` `wal_sender_shutdown_timeout`, `fb80f388f4a` per-subscription
  `wal_receiver_timeout`, `Avoid blocking indefinitely while finishing
  walsender shutdown`). Pattern: GUC- or per-subscription-knob commits that
  bound how long replication waits.
- **psql polish.** Tab completion, `\d+` partition / inheritance listing
  formatting, missing options. ~14 commits in 24mo with the `psql:` prefix.
- **pgbench knobs.** `--continue-on-error` (`0ab208fa505`), multi-line headers
  for COPY FROM (`bc2f348e87c`), and several bug fixes (e.g. "fix verbose error
  message corruption with multiple threads").
- **postgres_fdw / dblink / ecpg.** He is the de-facto fielder of bug reports
  against these utility components. SCRAM passthrough fixes,
  use_scram_passthrough validation, dblink user-mapping precedence — a
  multi-commit cluster all from him.
- **Documentation.** "doc:" is his single biggest prefix (55 of 232 commits).
  Many are translations of operational decisions ("Use 'integer' for some I/O
  worker GUC type descriptions") rather than tutorial-style prose.

## Style + patterns

- **Title-case imperative subject; punctuation varies.** Unlike Andres's
  lowercase `area:` prefix, Fujii's subjects are mixed-case sentences with a
  trailing period sometimes (`Add per-subscription wal_receiver_timeout
  setting.`, `pgbench: Add --continue-on-error option.`). Both punctuated and
  unpunctuated occur. `[verified-by-code]`.
- **Long reviewer-trailer lists.** `a8f45dee917` (`wal_sender_shutdown_timeout`)
  carries 15 `Reviewed-by:` trailers. He pulls in essentially the whole
  replication review pool when committing replication GUCs.
  `[verified-by-code]`.
- **Self-review credit.** He appears as `Reviewed-by: Fujii Masao
  <masao.fujii@gmail.com>` on 96 of his own 232 commits (~41%). This is the
  "committer-also-reviewed" convention, where the gmail address records the
  review identity and the @postgresql.org address records the commit.
  `[verified-by-code]`.
- **Self-author too.** 98 of 232 commits list him as `Author:` /
  `Co-authored-by:` — he is patch-driver as well as committer on roughly 42%
  of his commits.
- **Backpatch-heavy.** ~43% of his commits in 24mo reference a back-branch.
  Bug-fix and small-omission commits (e.g. `Fix COPY FROM ON_ERROR SET_NULL
  with selective column list`) frequently carry `Backpatch-through:`.
  `[verified-by-code]`.
- **Operational rationale in body.** Bodies typically open with the user-visible
  problem ("Previously, during shutdown, walsenders always waited until all
  pending data was replicated to receivers...") and end with a single paragraph
  on the trade-off ("However, if the timeout is reached, the sender and
  receiver may be left out of sync, which can be problematic..."). Less
  theoretical / more operational than Andres's commits.
- **"Bump catalog version." line on catalog-touching commits.** Visible in
  `fb80f388f4a` (`Add per-subscription wal_receiver_timeout setting.`) — a small
  but consistent flag he leaves in the commit body. `[verified-by-code]`.


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

Reviewers of his commits (24mo):

```
 96 Fujii Masao             — self (committer-also-reviewed convention)
 43 Chao Li                 — frequent collaborator on small fixes
 12 Amit Kapila             — logical-replication overlap
 11 Hayato Kuroda           — same employer (Fujitsu/NTT-area circle)
 10 David G. Johnston       — docs + user-visible-behavior reviews
  9 Michael Paquier
  7 Daniel Gustafsson
  7 Japin Li
  7 Robert Treat
```

Co-authors on his commits:

```
 98 Fujii Masao             — self-driven patches
 14 Chao Li
 13 Yugo Nagata             — NTT colleague; pgbench / COPY work
 10 Hayato Kuroda
  9 Atsushi Torikoshi
```

The pairings cluster:

1. **NTT / Fujitsu inner circle:** Hayato Kuroda, Atsushi Torikoshi, Yugo Nagata,
   Shinya Kato — these names appear as both authors and reviewers around
   replication and pgbench work.
2. **Chao Li recurs on bug-fix triage.** 43 reviews + 14 co-authorships in 24mo
   — high-volume small-fix collaborator.
3. **Amit Kapila is the logical-replication second pair of eyes.**

## What to expect on a patch he would review

- **Backpatch discipline.** If your patch is a bug fix, expect a `Backpatch-
  through:` decision conversation. He often asks "should this go back to N?"
  and answers it in the body. Pre-empt by stating your backpatch position.
- **Operational consequence stated up front.** He will ask for a "what happens
  to existing deployments?" sentence on user-visible changes, especially in
  replication. See `a8f45dee917` body for the model: ".. may be left out of
  sync, which can be problematic for physical replication switchovers".
- **psql tab completion expected for any new SQL keyword/option.** Multiple
  of his own commits are "Fix tab completion for X" follow-ups. If your patch
  adds a SQL clause, add the matching `tab-complete.in.c` entry or expect a
  follow-up commit.
- **Docs expected in the same patch.** `doc/src/sgml/` shows up in 117 of 232
  of his commits — half his work touches docs. Patches that change user-visible
  behavior without docs will draw a request.
- **`Bump catalog version.` reminder.** If your patch touches `pg_*` catalog
  layout or new catalog columns, expect this reminder if you forget it.

## Landmark commits (last 12mo)

1. **`aecc558666a` psql: Show comments in `\dRp+`, `\dRs+`, and `\dX+`** (742
   LOC). Adds `obj_description()` columns to publication, subscription, and
   extension psql meta-commands. Mid-sized refactor of `describe.c`. Shows his
   psql-polish focus.
2. **`a8f45dee917` Add `wal_sender_shutdown_timeout` GUC to limit shutdown wait
   for replication** (401 LOC). 15 reviewers, multi-author with two NTT
   contributors. Cleanly states the user pain (apply workers blocked on locks
   prevent shutdown) and the trade-off (sender/receiver can be out of sync at
   the timeout). Representative of his replication-GUC pattern.
3. **`fb80f388f4a` Add per-subscription `wal_receiver_timeout` setting** (343
   LOC). New `subwalrcvtimeout` column on `pg_subscription`. Body explicitly
   includes "Bump catalog version." line. Author = Fujii Masao himself.
4. **`bc2f348e87c` Support multi-line headers in COPY FROM command** (180 LOC).
   New COPY FROM option `HEADER N`. Carries `Backpatch-through:` consideration
   visible in body.
5. **`0ab208fa505` pgbench: Add --continue-on-error option** (204 LOC). 7
   reviewers, three Authors. Body opens with the user use case ("benchmarks
   using custom scripts that may raise errors, such as unique constraint
   violations").

## Notes / hedges

- **Two email identities for grep matching.** When mining for review credit,
  match both `fujii@postgresql.org` (committer) and `masao.fujii@gmail.com`
  (author/reviewer). The 96 "self-review" credits are all via the gmail
  address. `[verified-by-code]`.
- **Backpatch share is the headline number.** ~43% is the highest of the five
  bucket-B personas. He is a heavy maintenance committer, not just a feature
  committer. Don't assume his work is master-only. `[verified-by-code]`.
- **Replication scope is broader than walsender.** Despite being clustered in
  `src/backend/replication`, his actual touch reaches into `src/bin/psql` (for
  tab completion), `src/bin/pg_dump` (for publication/subscription dump),
  `contrib/postgres_fdw`, `contrib/dblink`, and `src/interfaces/ecpg`. Treat
  him as an FE-tooling owner too. `[verified-by-code]`.
- **The Reviewed-by trailer block is sometimes very long.** Don't read 15
  reviewers as "I solicited 15 reviews"; it's the accumulated reviewer list
  across many versions of a thread. He preserves prior version reviewers
  rather than dropping them. `[verified-by-code]`.
