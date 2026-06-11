# PostgreSQL contributor + reviewer map

- **Last verified:** 2026-06-11
- **Source pin:** e18b0cb7344
- **Method:** mined `git log` commit BODIES on the upstream master branch for
  trailer lines (`Author:`, `Reviewed-by:`, `Reported-by:`, `Diagnosed-by:`,
  `Tested-by:`, `Co-authored-by:`, `Suggested-by:`, `Discussion:`,
  `Backpatch-through:`). No mailing-list archives, no GitHub API.
- **Window:** last 24 months (2024-06-11 .. 2026-06-11; matches the
  `committer-map.md` cohort).
- **Volume:** 5,752 non-merge commits in the window, **857 distinct people**
  recovered across all people-trailers (vs. only 33 distinct committers in the
  same window).

## What this is

Companion to `committer-map.md`. The committer map names who PUSHES commits.
This map names who the committers CREDIT — patch authors, reviewers, bug
reporters, diagnosticians — who never (or rarely) push themselves but shape
the codebase through patches + reviews + bug reports.

Why this matters for Phase B/C/D:

- Any future Phase D submission needs to know who reviews patches in a given
  subsystem, not just who commits there. Email a patch to `pgsql-hackers`
  with `Reviewed-by:` trailers from people who never reviewed it, or fail to
  CC the relevant reviewer — both ways to look like you don't know the
  community.
- Phase C calibration of the review skill should be aware of common reviewer
  voices (their stylistic preferences, what they push back on, who their
  natural pairs are). This map is the data layer under that.
- The committer-map's "only 59 distinct committers ever, 33 active now" number
  is misleading without this companion: the actual sustained contributor
  population in the last 24mo is **857 distinct names** in trailers — over
  25× larger than the committer set.

## Important framing: trailers count "appearances," not "patches"

A single commit can credit many people. Examples:

- A commit with `Reviewed-by: A, B, C` counts as one Reviewed-by appearance for
  each of A, B, C.
- A commit with three separate `Reviewed-by:` lines does the same.
- A person listed twice on the same commit (e.g., once as Author and once as
  Reviewed-by) counts ONCE per trailer type but appears in both Author and
  Reviewed-by columns.

So "Tom Lane has 352 Reviewed-by appearances in 24mo" means his name appears
on the Reviewed-by trailer of 352 distinct commits. Not 352 patches reviewed
end-to-end on `pgsql-hackers` — that count is typically larger (one mailing-list
patch can land as several commits, and some reviews don't survive to the
trailer if the committer rewrote heavily).

## Top contributors (last 24 months) — by total trailer appearances

Counts are distinct-commit counts per trailer type, deduped per commit.
"Other" sums `Reported-by + Diagnosed-by + Tested-by + Co-authored-by +
Suggested-by`. "Total" is the sum across all people-trailer types.

| Person | Author | Rev-by | Rep-by | Other | Total | Top crediting committers | Top subsystems |
|---|---:|---:|---:|---:|---:|---|---|
| Tom Lane | 216 | 352 | 78 | 58 | 704 | Tom Lane (321), Nathan Bossart (59) | utils, optimizer, commands |
| Chao Li | 80 | 340 | 12 | 8 | 440 | Peter Eisentraut (67), Michael Paquier (59) | utils, access, regress |
| Michael Paquier | 70 | 235 | 14 | 36 | 355 | Michael Paquier (200), Nathan Bossart (37) | utils, access, test-modules |
| Andres Freund | 23 | 231 | 50 | 38 | 342 | Andres Freund (53), Melanie Plageman (45) | access, utils, executor |
| Fujii Masao | 90 | 148 | 7 | 17 | 262 | Fujii Masao (213), Nathan Bossart (12) | doc, replication, postgres_fdw |
| Daniel Gustafsson | 69 | 156 | 5 | 14 | 244 | Daniel Gustafsson (143), Nathan Bossart (26) | doc, test-modules, libpq |
| Jian He | 80 | 81 | 53 | 19 | 233 | Peter Eisentraut (46), Amit Langote (29) | regress, doc, commands |
| Peter Eisentraut | 16 | 152 | 29 | 22 | 219 | Peter Eisentraut (47), Jeff Davis (29) | doc, utils, access |
| Bertrand Drouvot | 107 | 102 | 3 | 5 | 217 | Michael Paquier (101), Peter Eisentraut (37) | utils, access, replication |
| Álvaro Herrera | 44 | 129 | 12 | 20 | 205 | Álvaro Herrera (76), Peter Eisentraut (14) | access, utils, commands |
| Amit Kapila | 7 | 179 | 3 | 3 | 192 | Amit Kapila (123), Masahiko Sawada (19) | replication, catalog, subscription |
| David Rowley | 84 | 67 | 19 | 11 | 181 | David Rowley (105), Richard Guo (16) | executor, optimizer, access |
| Melanie Plageman | 88 | 62 | 11 | 7 | 168 | Melanie Plageman (89), Andres Freund (43) | access, storage, executor |
| Alexander Lakhin | 14 | 13 | 115 | 5 | 147 | Michael Paquier (23), Alexander Korotkov (15) | regress, utils, storage |
| Ashutosh Bapat | 40 | 86 | 8 | 8 | 142 | Heikki Linnakangas (28), Peter Eisentraut (27) | regress, doc, storage |
| Richard Guo | 88 | 30 | 12 | 8 | 138 | Richard Guo (98), Alexander Korotkov (8) | optimizer, regress, include/optimizer |
| Heikki Linnakangas | 7 | 113 | 10 | 5 | 135 | Andres Freund (27), Peter Eisentraut (26) | utils, access, regress |
| Peter Smith | 49 | 68 | 12 | 0 | 129 | Amit Kapila (68), Michael Paquier (19) | doc, replication, regress |
| Noah Misch | 4 | 85 | 31 | 8 | 128 | Andres Freund (48), Michael Paquier (14) | storage, utils, regress |
| Tomas Vondra | 16 | 84 | 14 | 8 | 122 | Tomas Vondra (29), Melanie Plageman (15) | access, executor, regress |
| Robert Haas | 9 | 92 | 10 | 10 | 121 | Nathan Bossart (20), Robert Haas (15) | regress, doc, optimizer |
| Hayato Kuroda | 44 | 68 | 3 | 3 | 118 | Amit Kapila (55), Fujii Masao (23) | replication, doc, pg_basebackup |
| Nathan Bossart | 17 | 78 | 8 | 15 | 118 | Nathan Bossart (25), Peter Eisentraut (14) | access, regress, doc |
| Nazir Bilal Yavuz | 41 | 66 | 3 | 7 | 117 | Andres Freund (40), Michael Paquier (29) | storage, test-modules, utils |
| Vignesh C | 50 | 60 | 5 | 1 | 116 | Amit Kapila (72), Fujii Masao (8) | doc, replication, regress |
| Kirill Reshke | 26 | 82 | 6 | 1 | 115 | Melanie Plageman (26), Michael Paquier (18) | regress, access, doc |
| Masahiko Sawada | 3 | 102 | 5 | 3 | 113 | Masahiko Sawada (39), Amit Kapila (19) | doc, replication, regress |
| Sami Imseih | 43 | 53 | 6 | 5 | 107 | Michael Paquier (40), Nathan Bossart (33) | test-modules, utils, pg_stat_statements |
| Jelte Fennema-Nio | 52 | 40 | 7 | 3 | 102 | Peter Eisentraut (32), Heikki Linnakangas (10) | libpq, doc, utils |
| Zhijie Hou | 57 | 28 | 4 | 4 | 93 | Amit Kapila (70), Masahiko Sawada (6) | replication, doc, subscription |
| Corey Huinker | 55 | 30 | 0 | 5 | 90 | Michael Paquier (29), Jeff Davis (22) | regress, pg_dump, statistics |
| Alexander Korotkov | 20 | 56 | 2 | 11 | 89 | Alexander Korotkov (78), Michael Paquier (3) | regress, access, doc |
| Tender Wang | 26 | 42 | 9 | 11 | 88 | Richard Guo (25), Amit Langote (12) | regress, optimizer, utils |
| Jacob Champion | 30 | 41 | 4 | 11 | 86 | Daniel Gustafsson (26), Peter Eisentraut (14) | libpq, doc, pg_plan_advice |
| Peter Geoghegan | 56 | 24 | 6 | 0 | 86 | Peter Geoghegan (58), Melanie Plageman (6) | access (nbtree), regress, include/access |
| Thomas Munro | 16 | 33 | 11 | 21 | 81 | Peter Eisentraut (23), Andres Freund (12) | (cross-cut: storage, jit) |
| Xuneng Zhou | 44 | 29 | 2 | 2 | 77 | Alexander Korotkov (35), Michael Paquier (24) | (cross-cut, new author 2025) |
| Andrei Lepikhov | 24 | 40 | 4 | 0 | 68 | Alexander Korotkov (30), Richard Guo (10) | (optimizer-heavy) |
| Dean Rasheed | 31 | 30 | 3 | 4 | 68 | Dean Rasheed (35), Richard Guo (6) | (parser, optimizer, RETURNING) |
| Matthias van de Meent | 13 | 53 | 1 | 1 | 68 | Heikki Linnakangas (19), Peter Geoghegan (14) | (storage, access) |

Subsystem path abbreviations: `utils` = `src/backend/utils`, `access` =
`src/backend/access`, `optimizer` = `src/backend/optimizer`, `executor` =
`src/backend/executor`, `storage` = `src/backend/storage`, `replication` =
`src/backend/replication`, `commands` = `src/backend/commands`, `regress` =
`src/test/regress`, `test-modules` = `src/test/modules`, `doc` =
`doc/src/sgml`. Each row's "Top subsystems" is the top 3 paths touched by
commits this person appears in (any trailer). For people whose subsystems
column is `(cross-cut, ...)`, the top-3 paths were dominated by
test/regress + doc, which carry less information about technical focus —
they're called out qualitatively instead.

## Top reviewers (last 24 months) — sorted by Reviewed-by appearances only

The "Other reports/tests/diag" column sums Reported-by + Tested-by +
Diagnosed-by + Suggested-by.

| Person | Rev-by | Author + Co-auth | Other reports/tests/diag | Notable subsystems reviewed |
|---|---:|---:|---:|---|
| Tom Lane | 352 | 242 | 110 | cross-cutting: utils, optimizer, commands, PL/pgSQL |
| Chao Li | 340 | 84 | 16 | broad: utils, access, replication (new heavy reviewer since 2025-08) |
| Michael Paquier | 235 | 103 | 17 | utils, access, test-modules; also tooling/pg_dump |
| Andres Freund | 231 | 28 | 82 | access (AIO), executor, storage |
| Amit Kapila | 179 | 8 | 5 | replication (logical), subscription, catalog |
| Daniel Gustafsson | 156 | 78 | 10 | TLS/OAuth, libpq, postmaster, test-modules |
| Peter Eisentraut | 152 | 29 | 40 | doc, utils, access (broad) |
| Fujii Masao | 148 | 106 | 8 | doc, replication, postgres_fdw |
| Álvaro Herrera | 129 | 60 | 16 | access, commands, regress (constraints) |
| Heikki Linnakangas | 113 | 8 | 14 | utils, access, storage (AIO, shmem) |
| Bertrand Drouvot | 102 | 112 | 8 | utils, access, replication |
| Masahiko Sawada | 102 | 6 | 8 | replication, doc |
| Robert Haas | 92 | 14 | 15 | optimizer (planning advice), commands |
| Ashutosh Bapat | 86 | 44 | 12 | regress, storage, partitioning |
| Noah Misch | 85 | 10 | 33 | storage, utils (durability/correctness) |
| Tomas Vondra | 84 | 18 | 20 | access (GIN), executor |
| Kirill Reshke | 82 | 26 | 7 | regress, access |
| Jian He | 81 | 96 | 56 | regress, doc, commands |
| Nathan Bossart | 78 | 30 | 10 | access, doc, src/port |
| Peter Smith | 68 | 49 | 12 | doc, replication (heavy on logical-rep docs) |
| Hayato Kuroda | 68 | 45 | 5 | replication, pg_basebackup |
| David Rowley | 67 | 87 | 24 | executor, optimizer |
| Nazir Bilal Yavuz | 66 | 47 | 4 | storage, test-modules |
| Vignesh C | 60 | 50 | 6 | doc, replication |
| Alexander Korotkov | 56 | 31 | 13 | regress, access |
| Matthias van de Meent | 53 | 14 | 2 | storage, access |
| Sami Imseih | 53 | 48 | 11 | test-modules, pg_stat_statements |
| Jacob Champion | 41 | 40 | 5 | libpq, oauth |
| John Naylor | 44 | 0 | 9 | (pure reviewer — see "Pure reviewer cohort" below) |
| Andrei Lepikhov | 40 | 24 | 4 | optimizer |

## Top patch authors (last 24 months) — sorted by Author + Co-authored-by

The "Author + Co-auth" column sums the two; Author and Co-auth are also
shown separately. Reviewers credited on the same commits as this author are
informative for "who reviews this person's patches"; that breakdown is in
the per-committer pairings section, NOT in this author-side table.

| Person | Author | Co-auth | Rev-by | Notable subsystems authored |
|---|---:|---:|---:|---|
| Tom Lane | 216 | 26 | 352 | cross-cutting: utils, optimizer, commands, PL |
| Bertrand Drouvot | 107 | 5 | 102 | utils, access, replication |
| Fujii Masao | 90 | 16 | 148 | doc, replication, postgres_fdw |
| Richard Guo | 88 | 4 | 30 | optimizer (planner internals) |
| Melanie Plageman | 88 | 4 | 62 | access (heap+vacuum), storage |
| David Rowley | 84 | 3 | 67 | executor, optimizer (performance) |
| Chao Li | 80 | 4 | 340 | broad: utils, access |
| Jian He | 80 | 16 | 81 | regress, commands |
| Michael Paquier | 70 | 33 | 235 | utils, access, test-modules |
| Daniel Gustafsson | 69 | 9 | 156 | doc, test-modules, libpq |
| Zhijie Hou | 57 | 0 | 28 | replication (logical), subscription |
| Peter Geoghegan | 56 | 0 | 24 | access (nbtree, skip scan) |
| Corey Huinker | 55 | 5 | 30 | pg_dump, statistics |
| Jelte Fennema-Nio | 52 | 3 | 40 | libpq |
| Vignesh C | 50 | 0 | 60 | doc, replication |
| Peter Smith | 49 | 0 | 68 | doc, replication |
| Álvaro Herrera | 44 | 16 | 129 | access, commands, regress |
| Hayato Kuroda | 44 | 1 | 68 | replication, pg_basebackup |
| Xuneng Zhou | 44 | 2 | 29 | new heavy author since 2025 |
| Sami Imseih | 43 | 5 | 53 | test-modules, pg_stat_statements |
| Nazir Bilal Yavuz | 41 | 6 | 66 | storage, test-modules |
| Ashutosh Bapat | 40 | 4 | 86 | regress, storage |
| Dean Rasheed | 31 | 3 | 30 | parser, optimizer (RETURNING) |
| Jacob Champion | 30 | 10 | 41 | libpq, oauth |
| Andres Freund | 23 | 5 | 231 | access (AIO infra) |
| Alexander Korotkov | 20 | 11 | 56 | regress, access |
| Tender Wang | 26 | 5 | 42 | regress, optimizer |
| Kirill Reshke | 26 | 0 | 82 | regress, access |
| Tomas Vondra | 16 | 2 | 84 | access (GIN), executor |
| Thomas Munro | 16 | 17 | 33 | storage, jit |
| Andrei Lepikhov | 24 | 0 | 40 | optimizer |
| Nathan Bossart | 17 | 13 | 78 | access |
| Peter Eisentraut | 16 | 13 | 152 | utils, doc |

## Trailer-type frequency summary

| Trailer | Raw lines (24mo) | Person-appearances (post-split, dedup-per-commit-per-type) |
|---|---:|---:|
| `Discussion:` (URL, not a person) | 5,352 | — |
| `Reviewed-by:` | 5,121 | 5,518 |
| `Author:` | 3,124 | 3,192 |
| `Reported-by:` | 1,215 | 1,229 |
| `Backpatch-through:` (version tag) | 1,062 | — |
| `Co-authored-by:` | 371 | 373 |
| `Suggested-by:` | 121 | 121 |
| `Tested-by:` | 63 | 64 |
| `Diagnosed-by:` | 48 | 50 |

Notes:

- 5,352 `Discussion:` lines vs. 5,752 commits → about **93% of recent commits
  cite a mailing-list URL**. PG's "every change has a thread" norm is
  enforced almost universally.
- `Reviewed-by:` (5,121 raw lines) is the most common people-trailer — more
  than 1.6× `Author:` (3,124). This is consistent with PG's culture of
  multi-reviewer patches: the median patch credits more reviewers than authors.
- `Tested-by:` and `Diagnosed-by:` are rare (<70 each over 24mo). They're
  reserved for substantive testing or root-cause attribution; routine "I ran
  the regression tests" is implicit and not credited.
- `Backpatch-through:` (1,062 raw lines) means roughly **18% of recent
  master-tree commits were backpatched**.
- Person-appearance counts slightly exceed raw line counts for `Reviewed-by`
  because multi-name trailers (`Reviewed-by: A, B, C`) and continuation
  lines get split into three appearances.

## Committer ↔ reviewer pairings

For each of the top-15 committers (by 24mo commit count), the top 5 people
credited as `Reviewed-by` on commits THIS committer pushed.

Quirk to flag: **committers frequently list themselves as Reviewed-by**.
This is the PG convention when the committer did substantive review (not just
applied the patch). Example: 114 of Amit Kapila's 185 commits in 24mo
contain `Reviewed-by: Amit Kapila`. Lines in the table marked `(self)` are
this case; you can read them as "the committer also reviewed before
pushing."

| Committer | 24mo commits | With Rev-by | Top 5 reviewers credited |
|---|---:|---:|---|
| Michael Paquier | 723 | 326 | Michael Paquier (self, 101), Chao Li (39), Bertrand Drouvot (37), Tom Lane (17), Nazir Bilal Yavuz (14) |
| Peter Eisentraut | 719 | 357 | Chao Li (58), Tom Lane (46), Andres Freund (27), Peter Eisentraut (self, 26), Heikki Linnakangas (26) |
| Tom Lane | 661 | 208 | Tom Lane (self, 86), Chao Li (12), Andres Freund (12), David Rowley (8), Andrey Borodin (7) |
| Nathan Bossart | 315 | 227 | Tom Lane (49), Michael Paquier (35), Daniel Gustafsson (23), Sami Imseih (19), John Naylor (18) |
| Heikki Linnakangas | 292 | 158 | Ashutosh Bapat (22), Andres Freund (20), Chao Li (19), Matthias van de Meent (17), Daniel Gustafsson (15) |
| Álvaro Herrera | 270 | 117 | Álvaro Herrera (self, 24), Tom Lane (14), Michael Paquier (12), Chao Li (11), Tender Wang (8) |
| Fujii Masao | 232 | 212 | Fujii Masao (self, 113), Chao Li (43), Hayato Kuroda (12), Amit Kapila (12), Michael Paquier (11) |
| Andres Freund | 227 | 150 | Noah Misch (42), Melanie Plageman (34), Andres Freund (self, 25), Nazir Bilal Yavuz (23), Heikki Linnakangas (23) |
| Daniel Gustafsson | 192 | 135 | Daniel Gustafsson (self, 66), Peter Eisentraut (18), Jacob Champion (13), Michael Paquier (13), Tom Lane (13) |
| David Rowley | 187 | 97 | David Rowley (self, 23), Tom Lane (16), Chao Li (10), Michael Paquier (10), Andres Freund (9) |
| Jeff Davis | 185 | 78 | Peter Eisentraut (28), Chao Li (13), Andreas Karlsson (11), Corey Huinker (5), Tom Lane (4) |
| Amit Kapila | 185 | 149 | Amit Kapila (self, 114), Peter Smith (46), shveta malik (45), Hayato Kuroda (34), Vignesh C (32) |
| Alexander Korotkov | 141 | — | Alexander Korotkov (self, dominant), Pavel Borisov, Andrei Lepikhov (specialist reviewers) |
| Melanie Plageman | 121 | — | Melanie Plageman (self), Andres Freund, Tomas Vondra |
| Richard Guo | 111 | — | Richard Guo (self), Tom Lane, Alexander Korotkov |

Notable patterns:

- **Tom Lane has the lowest "with Rev-by" ratio** of any top committer (208 /
  661 = 31%). His commits are disproportionately small fixes / doc tweaks
  that he doesn't bother to credit reviewers for, or solo work where he was
  the only reviewer needed.
- **Fujii Masao has the highest ratio** (212 / 232 = 91%) and 113 of those
  cite himself — i.e., he almost always tags himself when pushing someone
  else's patch.
- **Amit Kapila's review pool is the tightest** of the active committers:
  Amit Kapila (self), Peter Smith, shveta malik, Hayato Kuroda, Vignesh C —
  these five people review most of the logical-replication patches he
  commits. Logical replication is a tight-knit subteam, mostly Fujitsu /
  EnterpriseDB people.
- **Andres Freund's reviewers cluster on AIO + storage**: Noah Misch (42),
  Melanie Plageman (34), Nazir Bilal Yavuz (23), Heikki Linnakangas (23) —
  exactly the people who've also been credited as Author on AIO patches.
- **Heikki Linnakangas does NOT self-review** (his self-line is absent from
  his top-5). He's the cleanest "I commit only others' patches with their
  reviewers" pattern.
- **Chao Li reviews across SIX different committers** in the top 12. That's
  a remarkable breadth for someone who only became active in 2025-08 (see
  "Rising new reviewers" below).

## Pure-reviewer cohort (Reviewed-by ≥ 10, never authored)

People who appear on Reviewed-by lines ≥10 times in the 24mo window but ZERO
times as Author (or Co-authored-by). High-value cohort for Phase D submission
planning: these are people who can substantively review without being patch
authors themselves.

| Person | Rev-by | Reported-by | Tested-by | Diagnosed-by | Suggested-by |
|---|---:|---:|---:|---:|---:|
| John Naylor | 44 | 2 | 0 | 0 | 7 |
| wenhui qiu | 21 | 0 | 0 | 0 | 0 |
| Ilya Gladyshev | 11 | 0 | 0 | 0 | 0 |

Important caveat: this list is SHORT (only 3 names). Looks too small. The
reason: many "reviewer-only" people DO occasionally land a patch via
Author/Co-authored-by, so the strict "Author + Co-authored-by == 0" filter
excludes them. The PG community has very few people who review for years
without ever shipping a patch — review and authorship are intertwined.

Also note: **John Naylor IS a committer** (per `committer-map.md`, with 63
commits in 24mo). He pushes his OWN work but in this 24mo window apparently
never had someone else commit a patch where he was the Author. So the
"pure-reviewer" label here means "no Author-trailer credits," not "doesn't
write code." The label captures only what's visible from trailers.

A looser definition (Reviewed-by ≥ 20, Author + Co-auth ≤ 5) catches more
genuine reviewer-leaning people. From the top reviewers table the candidates
fitting that are: Masahiko Sawada (Rev 102, Au+CoA 6), Heikki Linnakangas
(Rev 113, Au+CoA 8), Amit Kapila (Rev 179, Au+CoA 8), Robert Haas (Rev 92,
Au+CoA 14), Matthias van de Meent (Rev 53, Au+CoA 14). These are committers
or near-committers who in the last 24mo have shifted toward reviewing rather
than authoring — useful for Phase D's "who would actually read my patch."

## Notable patterns + surprises

### Rising new reviewers (2025+)

**Chao Li** — most striking single finding in this map. First appeared as a
PG reviewer August 2025; in the 10 months since has accumulated **340
Reviewed-by appearances**, second only to Tom Lane (352, who has been doing
this for 26 years). His reviews span at least 8 different committers'
commits, with strong concentration on Michael Paquier (39) and Peter
Eisentraut (58). Monthly cadence has held 40-75 commits credited per month
since 2025-10. By the time this doc is verified again he will likely have
overtaken Tom Lane on this metric.

**Xuneng Zhou** — another new (2025+) high-volume author/reviewer cluster;
44 authored commits, 29 reviews. Credited heavily by Alexander Korotkov and
Michael Paquier.

**Kirill Reshke** — established 2024+ reviewer-leaning contributor, 82
Rev-by and 26 Author in 24mo; tightly clustered on access + regress work.

### Subsystem-specific reviewer dominance

- **Logical replication** (`src/backend/replication`): the reviewer pool is
  dominated by Amit Kapila (179 R-by total, almost all rep-related), Peter
  Smith (68), Masahiko Sawada (102), Vignesh C (60), Zhijie Hou (28),
  Hayato Kuroda (68). Six names cover nearly all the reviewing in this
  subsystem; the Phase D submitter on a logical-rep patch should expect
  these names to weigh in.
- **AIO / storage**: Noah Misch, Melanie Plageman, Nazir Bilal Yavuz,
  Matthias van de Meent. Tighter group, mostly people who also authored
  parts of the AIO infrastructure.
- **Optimizer**: Richard Guo (30 R-by, but 88 Author — he's
  author-dominated), Andrei Lepikhov (40 R-by), Tender Wang (42 R-by) —
  alongside Tom Lane (the universal reviewer) and David Rowley.
- **libpq / oauth / TLS**: Daniel Gustafsson (156 R-by total) and Jacob
  Champion (41) — both committers in this area; they cross-review each
  other heavily (Daniel credits Jacob 13× on his pushed commits).

### Alexander Lakhin — the bug-hunter persona

Alexander Lakhin is the clearest example of "non-author, non-reviewer but
huge contributor": **115 Reported-by appearances** in 24mo (the highest of
anyone in the entire dataset), plus 13 Reviewed-by, only 14 Author. He
finds and reports bugs across the codebase (utils, storage, access, regress
all show up in his subsystem distribution). The credit pattern shows him
distributed across many committers (Michael Paquier 23, Alexander Korotkov
15, others) — he's a project-wide asset, not anyone's specific reporter.

### Self-review prevalence

Six of the top-15 committers self-credit on Reviewed-by ≥20 times in 24mo:
Tom Lane (86 self), Fujii Masao (113), Daniel Gustafsson (66), Amit Kapila
(114), Álvaro Herrera (24), David Rowley (23), Michael Paquier (101).
Heikki Linnakangas and Andres Freund mostly do NOT self-credit. Two
plausible reasons for this stylistic split: (1) some committers see
themselves as "the committer applied a thoroughly-reviewed patch" vs. "the
committer was also the lead reviewer"; (2) some maintain the trailer block
purely as a record of who else looked, since "the committer reviewed it"
is implicit. Worth noting but not strongly load-bearing.

### Tom Lane's dominance

Tom Lane appears in some role on **704 of 5,752 commits = ~12%** of all
commits in the window. His Reviewed-by count (352) means he reviews on
average one patch every other day. He's also the single biggest
self-credit (86 of his 661 committed commits include himself on R-by,
again ~13%) — which actually understates his review work, since most of his
review is on his OWN PUSHED patches and never gets a separate trailer.

## Methodology + caveats

- **Trailer parsing.** Lines matching `^(Author|Reviewed-by|Reported-by|
  Diagnosed-by|Tested-by|Discussion|Co-authored-by|Suggested-by|Acked-by|
  Backpatch-through):\s+...` in the commit body. Case-insensitive. PG's
  `commit-message-style` discourages `Acked-by` and `Suggested-by` somewhat,
  but they appear sporadically (121 Suggested-by in 24mo). Continuation
  lines (indented, containing `@` or starting with `,`) are appended to the
  preceding trailer's value.
- **Multi-name trailers.** `Reviewed-by: X <e1>, Y <e2>, Z` is split into
  three appearances by walking the value with `<>`-depth tracking (so
  commas inside angle brackets don't trigger a split).
- **Per-commit dedup.** A person who appears on multiple Reviewed-by lines
  of the same commit (e.g., separate lines for two distinct reviewing
  rounds) is counted ONCE per trailer type per commit. A person who appears
  as both Author and Reviewed-by on the same commit is counted in BOTH
  columns.
- **Identity merging.** Same person under multiple `<name, email>` pairs is
  merged via:
  1. Email-based union: same effective email → same identity (after
     `EMAIL_ROLLUPS` table fold-ins: e.g. Peter Eisentraut's two emails,
     Álvaro's three, Chao Li's three, Fujii Masao's two NTT vs. gmail).
  2. Name-based union: same ASCII-folded lowercased name → same identity.
     This catches "Fujii Masao" / "Masao Fujii" (Japanese name-order swap)
     and accent variants ("Álvaro Herrera" vs "Alvaro Herrera").
  3. Manual rollup table for known special cases (Chao Li (Evan) → Chao Li,
     "何建 (Jian He)" → Jian He, etc.). All applied rollups are listed in
     `/tmp/parse_trailers.py` in the `MANUAL_NAME_ROLLUPS` and
     `EMAIL_ROLLUPS` dicts.
- **Display-name picker.** When multiple display forms exist for the same
  canonical identity (e.g. "Michael Paquier" vs "Michaël Paquier"), the
  most-frequent form across the 24mo window wins.
- **Discussion trailer.** `Discussion:` is a URL (almost always a
  `postgr.es/m/<msgid>` shortener). Counted in the trailer-frequency
  summary but excluded from person tables.
- **Backpatch-through trailer.** Version tag (e.g., `Backpatch-through: 13`).
  Counted in the frequency summary but not a person.
- **"Author" semantics.** PG's `Author:` does not distinguish "wrote 100%
  of the patch" from "wrote 10% of a heavily-rewritten patch." Author
  counts everyone listed. `Co-authored-by:` is used inconsistently — some
  committers use it for multi-author work, others fold everyone into a
  comma-separated `Author:` list.
- **Subsystem inference.** For each top-30 contributor, the SHAs of all
  commits where they appear in ANY people-trailer are walked through
  `git log --name-only`, and touched paths are bucketed into coarse
  subsystem labels (`src/backend/<X>`, `src/<X>/<Y>`, `contrib/<X>`, `doc`,
  `build`). The "Top subsystems" column shows the top 3 buckets BY FILE
  TOUCH count, not by patch count — a single big patch that touches many
  files in a subsystem skews this. For some people the top buckets are
  always `src/test/regress` + `doc` (because most patches touch a test +
  doc), so the column lists only meaningful technical buckets.
- **What this map does NOT capture:**
  - Review SUBSTANCE — a one-line "LGTM" review and a 50-comment deep
    review both produce one `Reviewed-by:` appearance.
  - Mailing-list activity outside committed patches — people who reviewed
    a patch that never landed are invisible here.
  - Per-patch authorship breakdown — three Authors on one commit each get
    one credit; no "primary vs. secondary" distinction.
  - Pre-2024-06 work — this is strictly a 24mo window. Long-running
    contributors who tapered off before then aren't in the tables.
  - Anything social, stylistic, or employer-affiliated. Those are
    Phase B follow-up deliverables.
- **Source command (reproducibility):**
  ```bash
  git -C source/ log --since="24 months ago" --no-merges \
      --pretty='%H%n%B%n==COMMIT-END==' > pg_commits_24mo.txt
  git -C source/ log --since="24 months ago" --no-merges \
      --pretty='%H|%an' > pg_commits_24mo_committers.txt
  ```
  Parser in `/tmp/parse_trailers.py` (this session); subsystem walker in
  `/tmp/get_subsystems.py`.
