---
name: pgsql-hackers archive participants
purpose: Phase B #5 cross-cut — voices visible in pgsql-hackers archives but underrepresented in `contributor-map.md`'s trailer-mined tables.
window: April 2026 – May 2026 (primary sample, ~250 thread entries) + Dec 2025 sample (~50 entries) for long-tail check.
methodology: WebFetch of monthly index pages → name extraction → cross-reference vs `contributor-map.md` and `/usr/bin/git log --grep=<name>` for trailer presence.
---

# Phase B #5 — pgsql-hackers archive participants

This is the deliverable that closes Phase B: **the archive-mining
cross-cut.** Phase B #1-#4 (committer-map, contributor-map,
domain-ownership, deep personas) mined the *git* record. This doc mines
the *mailing list* record and identifies who's missing from the
git-derived picture.

## Methodology + caveats

- **Sample window:** April 1 – May 27 2026 (primary; ~250 thread
  index entries via 4 fetches at 2-week intervals) plus December 1
  2025 (~50 entries) as a deeper-history spot check.
- **Source:** `https://www.postgresql.org/list/pgsql-hackers/since/
  <YYYYMMDD>0000/` — the archive's index pages show one line per
  message, with author shown plain-text. WebFetch returns the
  first ~50 entries per page.
- **Extraction:** name strings from the archive index lines.
  Confidence: high for the first-author-of-thread shape, lower for
  reply-by names (the archive page truncates at 50 lines so
  later-in-thread participants don't appear).
- **Cross-reference 1:** the 60-name set in `committer-map.md` +
  `contributor-map.md` tables (Phase B #1 + #5).
- **Cross-reference 2:** raw `/usr/bin/git log --since='2024-06-12'
  --grep=<name>` on the source tree — catches trailer-data the
  Phase B docs cut off at the top-N display threshold. The `rtk`
  shell filter caps `git log --oneline` at 50 lines per the
  Phase B operational gotcha; this analysis used `/usr/bin/git`
  directly.
- **Out of scope:** thread bodies, subject-line clustering by topic,
  back-then-vs-now activity-rate trend. A deeper Phase B+ pass
  could mine those; this delivers the headline.

## Two distinct findings

### Finding A — `contributor-map.md` top-N cutoff missed ~15 substantial trailer contributors

The contributor-map's tables (top reviewers / authors / reporters)
were built with a display cutoff. Several people who DO have
substantial trailer presence in the underlying git data didn't make
it into the doc's visible tables. Among those visible-in-archive
AND absent-from-doc but PRESENT-in-trailers (mentions = 24mo trailer
count):

| Name | 24mo trailer mentions | Likely doc-cut reason |
|---|---:|---|
| Aleksander Alekseev | **76** | The most egregious omission. Cross-cutting contrib + storage + meson work. Should be a top-25 contributor row. |
| Hayato Kuroda (Fujitsu) | **122** | Already named in `committer-map.md` Amit Kapila row's "Fujitsu/EDB reviewer subteam"; should have his own contributor-map row. |
| Yugo Nagata | 68 | Often Author= or Reported-by= on small fixes (pgstat, vacuum, sequence). Below the contributor-map display threshold. |
| Paul A Jungwirth | 56 | FOR PORTION OF / SQL:2011 Application Time — the temporal-tables author. Sustained 24mo work; not in doc. |
| Zsolt Parragi | 51 | Active on logical replication + COPY ON_CONFLICT. |
| Junwang Zhao | 51 | Multi-area reviewer, RI triggers, tuple deformation. |
| Dilip Kumar | 51 | EDB; logical replication + parallel apply. Major archive presence on Conflict log history thread. |
| Lukas Fittl | 50 | pg_plan_advice author — Robert Haas's collaborator on the planner-advice contrib. |
| Laurenz Albe | 49 | Frequent reporter + reviewer; release-notes commenter; docs. |
| shveta malik | 42 | Mentioned in `committer-map.md` Amit Kapila row's reviewer subteam (45 R-bys) but no contributor-map row. |
| Ayush Tiwari | 37 | EDB/Fujitsu cluster; sequence sync, generated columns. |
| Nisha Moond | 29 | EDB/Fujitsu cluster; conflict log history thread driver. |
| Antonin Houska | 27 | CYBERTEC; REPACK CONCURRENTLY work + REINDEX CONCURRENTLY revisits. |
| Jim Jones | 27 | Documentation + small-fixes presence. |
| Joel Jacobson | 25 | Numeric / type-system + recent fx_exchange money type proposal. |
| Atsushi Torikoshi | 22 | NTT; pg_stat_statements, EXPLAIN. |
| wenhui qiu | 21 | Optimizer / collation work. |
| Pavel Stehule | 20 | plpgsql + auto_explain queryid; long-standing contributor. |
| Maxim Orlov | 20 | 64-bit transaction IDs / mxidoff work. |
| cca5507 | 18 | Tuplesort / heap-build optimization. |
| Bharath Rupireddy | 17 | Logical replication. |
| SATYANARAYANA NARLAPURAM | 16 | Replication-slot-on-error fixes; standby_write/flush. |
| Bryan Green | 15 | Windows / LC_MESSAGES bug-finder. |
| Vitaly Davydov | 11 | Hot-standby deadlock detector. |
| Soumya S Murali | 11 | pg_stat_checkpointer; small-fixes presence. |
| Haibo Yan | 9 | Range-type join selectivity. |

**This is a real Phase B #5 gap.** The contributor-map's "top reviewers"
and "top reporters" tables show an artificial ceiling of activity that
matches the display row count, not the actual activity distribution.
Multiple 50-trailer-mention contributors are invisible in the doc.

The 24mo trailer count for the cutoff names is regularly higher than
several names that DO appear in the doc — see `Andrei Lepikhov` (62
mentions, appears 5×) vs `Aleksander Alekseev` (76 mentions, appears
0×). The cut wasn't done by trailer count.

### Finding B — Genuine archive-only voices (~10 names)

The shorter list: names visible in pgsql-hackers archives but with
**zero `Reviewed-by:` / `Reported-by:` / `Co-authored-by:` / `Author:`
trailer presence in 24mo of git log:**

| Name | Archive activity | Note |
|---|---|---|
| Sehrope Sarkuni | SCRAM iteration parsing thread (May 2026) | Active in pgsql-hackers discussion on libpq SCRAM hardening; patches die or get absorbed into others without trailer attribution. |
| Salma El-Sayed | "[GSoC 2026] B-tree Index Bloat Reduction" intro (May 2026) | GSoC student — introductory thread. Expect their commits to appear in subsequent quarters; track. |
| Aditya Dave | "Seeking guidance on RLS cyclic policy" (May 2026) | One-off question; not yet a contributor. |
| Filip Janus | "Proposal: compression of temporary files" (May 2026) | Driver of own proposal; thread may produce a trailer in the future. |
| Phil Florent | PG 19 release-notes commentary (May 2026) | Commentator, not contributor. Long-time pgsql-general voice. |
| Raghav Mittal | "Track last-used timestamp for index usage" (Dec 2025) | Proposal author; thread ongoing. |
| solai v | Multiple threads (May 2026): WAIT FOR LSN, COPY FROM RLS, pg_get_subscription_ddl | New contributor — multiple proposals in flight, no merged trailer yet. **Track for next cycle.** |
| vellaipandiyan sm | pgbench review + DOCS intro paragraph (May 2026) | Documentation / pgbench area. |
| Peter 'PMc' Much | "Need help debugging SIGBUS" (Dec 2025) | One-off user. |
| Bryan Green | LC_MESSAGES bug report (Dec 2025) | Has 15 trailer mentions — actually moved out of "archive-only" in the cross-reference; left here for visibility. |

These are mostly **proposal authors mid-process** (their patches haven't
landed yet, so they have no trailer) and **one-off voices** (users
asking questions on -hackers, occasional reporters who don't follow
through). The pure-archive set is small.

## Topic clusters surfaced in the May 2026 sample

Threads with 4+ replies in the sample windows (an "activity threshold"
proxy):

- **Logical replication** — Proposal: Conflict log history table (Dilip
  Kumar + shveta malik + Nisha Moond + Peter Smith + vignesh C); also
  Skipping schema changes in publication (Amit Kapila + Peter Smith).
  **The Amit Kapila Fujitsu/EDB cluster's archive footprint is much
  larger than the trailer footprint — and most of it is the same
  ~8 people the `domain-ownership.md` cluster 2 already names.** This
  cluster is well-modeled by Phase B.
- **POC: enable logical decoding when wal_level = 'replica' without a
  server restart** — Masahiko Sawada DRIVES this thread (8+ replies
  in Dec 2025 sample). Phase B persona doc captures him as
  replication/parallel-vacuum; the wal-level liveness work is new
  area, may need a 12mo refresh.
- **First draft of PG 19 release notes** — Bruce Momjian / Peter
  Geoghegan + many commentators including Phil Florent (archive-only)
  and Ashutosh Bapat / Richard Guo / David Rowley / Peter Smith
  (all in Phase B). Pattern: release-notes threads draw a wider
  archive crowd than trailer crowd. Expected.
- **FOR PORTION OF / SQL:2011 Application Time** — Paul A Jungwirth
  drives this multi-thread series. Substantive trailer presence
  (56 mentions) but invisible in `contributor-map.md` tables.
  Should be added.
- **Sequence Access Methods, round two** — Andrei Lepikhov drives;
  he IS in committer-map / contributor-map. Phase B captures him.

## Calibration impact (any Phase C reviewers affected?)

Cross-checking the archive-active set against the 5 Phase C
calibration docs' predicted-reviewer columns:

- **CB1 pgcrypto bomb** — Daniel Gustafsson (top), Tom Lane, Michael
  Paquier, Noah Misch, Peter Eisentraut. **All in Phase B.** The
  archive sample doesn't surface a missed reviewer for CB1.
- **CB7 ltree** — Peter Eisentraut, Tom Lane, Noah Misch, Michael
  Paquier, Jeff Davis, Chao Li. **All in Phase B.** No archive-side
  miss.
- **CB8 hstore** — Peter Eisentraut, Tom Lane, Noah Misch, Michael
  Paquier, Heikki Linnakangas, Chao Li. **All in Phase B.**
- **SP2 pg_str*** — Jeff Davis (LEAD), Peter Eisentraut, Tom Lane,
  Noah Misch, Thomas Munro, Michael Paquier, Chao Li, Heikki.
  **All in Phase B.** But: archive shows
  `Andreas Karlsson` driving the parallel "Speed up ICU case
  conversion by using ucasemap_utf8To*" thread — he's an SP2-adjacent
  voice. Karlsson IS in Phase B (committer-map row + frequent
  reviewer); just verifying he'd be the natural CC.
- **SP6 autoprewarm** — Tom Lane (LEAD), Nathan Bossart, Michael
  Paquier, Melanie Plageman, Andres Freund, Peter Eisentraut, Noah
  Misch, Heikki, Daniel Gustafsson. **All in Phase B.**

**Conclusion:** the Phase B persona set captures all predicted-reviewer
voices for the 5 calibration patches. The archive-only voices (Finding
B) are mostly question-askers and proposal authors with no patches in
the calibration area; they wouldn't change the Phase C catalog.

The Finding A "doc-cutoff" cohort (especially Hayato Kuroda, Aleksander
Alekseev, Lukas Fittl, Paul Jungwirth) would be useful additions to
`contributor-map.md` for completeness, but they wouldn't reshape any
calibration prediction — they're in the same subteam clusters that
`domain-ownership.md` already names.

## Headline finding for STATE.md

**Phase B #5 (contributor-map.md) under-represented ~15 substantive
trailer contributors due to display-row top-N cutoff.** The most
striking case is Aleksander Alekseev (76 trailer mentions in 24mo,
absent from the doc). This is a discoverable Phase B refresh item.

**Genuine pure-archive-only voices total ~8-10** — mostly proposal
authors mid-cycle (solai v, Filip Janus, Raghav Mittal) and one-off
question-askers. Track solai v specifically: 4 in-flight proposal
threads in May 2026 alone suggests they're about to enter the
trailer record.

## Followups (not blocking Phase B close)

1. **`contributor-map.md` refresh**: add the 15 Finding-A names as
   secondary-table rows or remove the artificial display cutoff.
   Low-effort; can be a `hf(corpus)` PR.
2. **Track solai v + Salma El-Sayed**: if either becomes a trailer
   contributor by next quarter, write a short persona. The current
   record is too thin.
3. **Refresh `chao-li.md` and `peter-smith.md`** in 6 months
   (2026-12) per their own persona files' maintenance notes — both
   have archive activity that may have rebalanced by then.

## Cross-references

- `knowledge/personas/contributor-map.md` — Phase B #5 doc this
  cross-cut is against.
- `knowledge/personas/committer-map.md` — names the Fujitsu/EDB
  cluster the Finding-A cohort partially overlaps.
- `knowledge/personas/domain-ownership.md` cluster 2 — Logical
  replication; matches the archive's Conflict-log-history thread
  cluster.
- `knowledge/personas/chao-li.md`, `noah-misch.md` — Phase C
  persona follow-ups; both still apply, archive data doesn't
  invalidate.
- `knowledge/calibration/gap-catalog.md` — Phase C catalog; not
  affected by Finding B (predicted reviewers fully captured).
- `progress/STATE.md` — receives a closing entry in the same PR.

## Phase B status after this doc

| Deliverable | Status |
|---|---|
| #1 committer-map | ✅ landed PR #137 |
| #2 archive participants | ✅ this doc |
| #3 deep personas (top 20 + Noah + Chao) | ✅ landed PR #148 + #152 + #155 |
| #4 domain-ownership | ✅ landed PR #147 |
| #5 contributor+reviewer trailer map | ✅ landed PR #139 (with Finding A refresh follow-up) |

**Phase B is 5/5 complete.**
