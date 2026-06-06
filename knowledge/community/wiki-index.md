# PostgreSQL Wiki — developer-relevant index

Annotated map of the PG wiki for future Claude sessions. Each entry: URL,
1–2 line description, when to read.

All claims here are derived from a hub crawl performed on 2026-06-01. Wiki
pages drift; re-verify before quoting in code commentary.

Crawled ~24 pages. Pages that came back **404** (don't link to them):
`Backend_flowchart`, `Hacking_on_PostgreSQL`, `Glossary`, `Working_with_GDB`,
`Developer_Mentoring`. See §Open questions.

---

## Hubs (start here)

- **Main_Page** — https://wiki.postgresql.org/wiki/Main_Page
  Top-level wiki landing. Surprisingly thin on developer links; the only
  contributor-facing entry it actually exposes is "Development_information".
  Don't expect to discover developer pages by browsing from Main_Page
  [from-wiki](https://wiki.postgresql.org/wiki/Main_Page).

- **Development_information** — https://wiki.postgresql.org/wiki/Development_information
  The *real* developer hub. Groups: Development Process, Developer Resources,
  CommitFests, Roadmaps, Past Developer Meeting Notes. Use this as the
  canonical "where do I find the dev page on X" jump-table
  [from-wiki](https://wiki.postgresql.org/wiki/Development_information).

- **Developer_FAQ** — https://wiki.postgresql.org/wiki/Developer_FAQ
  Long-form Q&A. Covers source tree layout, debugging (gdb, perf, rr,
  valgrind), parser internals, palloc/pfree, ereport, system catalog
  access, OID assignment, patch flow. Read once end-to-end then keep as
  reference [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

- **So,_you_want_to_be_a_developer?** — https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F
  Onboarding checklist: tooling, repo clone, regression tests, mailing
  list etiquette, code style, CommitFest timing
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).

---

## Getting started

- **HowToBetaTest** — https://wiki.postgresql.org/wiki/HowToBetaTest
  How non-coders can help by testing beta releases. The version-specific
  content is dated (focuses on PG 9.6 features) but the testing-method
  taxonomy is still useful [from-wiki](https://wiki.postgresql.org/wiki/HowToBetaTest).

- **Mailing_Lists** — https://wiki.postgresql.org/wiki/Mailing_Lists
  Which list to use for what. `pgsql-hackers` = patches + internals,
  `pgsql-bugs` = bug reports, `pgsql-docs` = docs, `pgsql-committers` =
  commit announcements. Etiquette: reply-all, no top-posting, no HTML,
  strip confidentiality notices
  [from-wiki](https://wiki.postgresql.org/wiki/Mailing_Lists).

- **Todo** — https://wiki.postgresql.org/wiki/Todo
  Catalogue of bugs/features/wishlist items. 28 sections. **Warning
  quoted on the page**: "Do not assume that you can select one, code it
  and then expect it to be committed" — workflow is
  Desirability→Design→Implement→Test→Review→Commit
  [from-wiki](https://wiki.postgresql.org/wiki/Todo).

## Coding & conventions

- **Coding_Conventions** — https://wiki.postgresql.org/wiki/Coding_Conventions
  *Note*: page exists per references in Developer_FAQ; primary source for
  PG style is actually the official docs at
  https://www.postgresql.org/docs/current/source.html
  [from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch). Inline
  highlights from Developer_FAQ: BSD style, 4-column tab stops, run
  `pgindent` at least once per dev cycle, block comments starting with
  `/*------` are exempt [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

- **Creating_Clean_Patches** — https://wiki.postgresql.org/wiki/Creating_Clean_Patches
  *(distilled 2026-06-05 → `knowledge/wiki-distilled/Creating_Clean_Patches.md`)*
  Treat the diff itself as a product. Use `git diff --color` to spot
  whitespace, `git rebase -i origin/master` to squash, and
  `git diff --patience` when default diff produces ugly alignment
  [from-wiki](https://wiki.postgresql.org/wiki/Creating_Clean_Patches).

- **Regression_test_authoring** — https://wiki.postgresql.org/wiki/Regression_test_authoring
  *(distilled 2026-06-05 → `knowledge/wiki-distilled/Regression_test_authoring.md`)*
  Tests live in `src/test/regress/`. Add new tests to both
  `parallel_schedule` AND `serial_schedule`. `.source` files get
  preprocessed (`@abs_srcdir@` substitutions)
  [from-wiki](https://wiki.postgresql.org/wiki/Regression_test_authoring).

## Patch workflow

- **Submitting_a_Patch** — https://wiki.postgresql.org/wiki/Submitting_a_Patch
  *(distilled 2026-06-04 → `knowledge/wiki-distilled/Submitting_a_Patch.md`)*
  Use `git format-patch`. Email must include: description, target branch
  (usually master), compile+test status, regression tests, docs.
  "Any patch without these two items is automatically considered a WIP one"
  (regression tests + documentation)
  [from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch).

- **Reviewing_a_Patch** — https://wiki.postgresql.org/wiki/Reviewing_a_Patch
  *(distilled 2026-06-04 → `knowledge/wiki-distilled/Reviewing_a_Patch.md`)*
  Six-phase checklist: Submission review, Usability review, Feature test,
  Performance review, Coding review, Architecture review. Use as the
  template when reviewing
  [from-wiki](https://wiki.postgresql.org/wiki/Reviewing_a_Patch).

- **CommitFest** — https://wiki.postgresql.org/wiki/CommitFest
  > "A Commitfest (CF) is a periodic break to PostgreSQL development
  > that focuses on patch review and commit rather than new development."
  ~1 month long, 1-month gaps between cycles
  [from-wiki](https://wiki.postgresql.org/wiki/CommitFest). Live app at
  https://commitfest.postgresql.org.

- **CommitFest_Checklist** — https://wiki.postgresql.org/wiki/CommitFest_Checklist
  Timeline + email templates for the Commitfest Manager (CFM). Audience
  is the CFM, not the average contributor
  [from-wiki](https://wiki.postgresql.org/wiki/CommitFest_Checklist).

- **Running_a_Commitfest** — https://wiki.postgresql.org/wiki/Running_a_Commitfest
  Sister page to CommitFest_Checklist for the CFM. Wiki crawler
  flagged it as a redirect/stale stub; prefer CommitFest_Checklist
  [from-wiki](https://wiki.postgresql.org/wiki/Running_a_Commitfest).

- **RRReviewers** — https://wiki.postgresql.org/wiki/RRReviewers
  Round-Robin Reviewers program. Volunteers get randomly assigned
  patches during a commitfest. **Active as of Aug 2025**
  [from-wiki](https://wiki.postgresql.org/wiki/RRReviewers). Subscribe
  to `pgsql-rrreviewers` to participate.

- **Committing_with_Git** — https://wiki.postgresql.org/wiki/Committing_with_Git
  Committers-only. Sets `branch.autosetuprebase=always`, always use
  `git push --dry-run` first. Refers out to Commit_Message_Guidance
  [from-wiki](https://wiki.postgresql.org/wiki/Committing_with_Git).

- **Commit_Message_Guidance** — https://wiki.postgresql.org/wiki/Commit_Message_Guidance
  *(distilled 2026-06-05 → `knowledge/wiki-distilled/Commit_Message_Guidance.md`)*
  Summary < 64 chars. Tags: `Reported-by`, `Suggested-by`, `Diagnosed-by`,
  `Author`, `Co-authored-by`, `Reviewed-by`, `Tested-by`, `Discussion`
  (postgr.es/m/MESSAGE_ID), `Backpatch-through`
  [from-wiki](https://wiki.postgresql.org/wiki/Commit_Message_Guidance).

## Tooling

- **Working_with_Git** — https://wiki.postgresql.org/wiki/Working_with_Git
  *(distilled 2026-06-05 → `knowledge/wiki-distilled/Working_with_Git.md`)*
  Standard clone is `https://git.postgresql.org/git/postgresql.git`.
  Stable branches use `REL_<N>_STABLE` convention. Run
  `make maintainer-clean` when switching between major versions
  [from-wiki](https://wiki.postgresql.org/wiki/Working_with_Git).

- **Continuous_Integration** — https://wiki.postgresql.org/wiki/Continuous_Integration
  *(distilled 2026-06-04 → `knowledge/wiki-distilled/Continuous_Integration.md`)*
  Cfbot (unofficial) auto-runs CI on patches posted to -hackers.
  Cirrus CI is the widest-OS path (Linux/Windows/FreeBSD/macOS).
  Control files live in the feature branch
  [from-wiki](https://wiki.postgresql.org/wiki/Continuous_Integration).

- **Valgrind** — https://wiki.postgresql.org/wiki/Valgrind
  *(distilled 2026-06-04 → `knowledge/wiki-distilled/Valgrind.md`)*
  Build with `CPPFLAGS="-DUSE_VALGRIND"`. Combine with
  `MEMORY_CONTEXT_CHECKING` for `repalloc()` instrumentation. Suppressions
  file is `src/tools/valgrind.supp`
  [from-wiki](https://wiki.postgresql.org/wiki/Valgrind).

- **gdb / debugging tips** — see Developer_FAQ §"What debugging features
  are available?". Recommended configure flags: `--enable-cassert
  --enable-debug CFLAGS="-ggdb -Og -g3 -fno-omit-frame-pointer"`. Set
  breakpoint at `errfinish` to trap all `elog/ereport`
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ). Note:
  there is **no** standalone `Working_with_GDB` page (404).

## Subsystem notes

- **Hint_Bits** — https://wiki.postgresql.org/wiki/Hint_Bits
  *(distilled 2026-06-02 → `knowledge/wiki-distilled/Hint_Bits.md`)*
  Tight, useful page on `XMIN_COMMITTED/ABORTED` and `XMAX_COMMITTED/ABORTED`.
  Explains why "just reading" can issue writes (hint bits get set on
  visibility check) [from-wiki](https://wiki.postgresql.org/wiki/Hint_Bits).
  Note: page is from 2015 — the distilled doc supplements the missing
  `SetHintBits`/`MarkBufferDirtyHint`/WAL-flush machinery from the corpus.

- **Hot_Standby** — https://wiki.postgresql.org/wiki/Hot_Standby
  *(distilled 2026-06-02 → `knowledge/wiki-distilled/Hot_Standby.md`)*
  PG 9.0/9.1-era quick-start for running read-only queries on a replaying
  standby [from-wiki](https://wiki.postgresql.org/wiki/Hot_Standby).
  Note: page is dated (2016) — uses retired `recovery.conf`/`standby_mode`
  spellings and barely covers the replay-vs-query conflict knobs
  (`max_standby_*_delay`, `hot_standby_feedback`); the distilled doc
  supplements those plus the lock-manager recovery clamp from the corpus.

- **MVCC** — https://wiki.postgresql.org/wiki/MVCC
  **Stale stub** (last meaningful update May 2012). Just a pointer to
  the official docs and Bruce Momjian talks. Don't use as a learning
  resource [from-wiki](https://wiki.postgresql.org/wiki/MVCC).

- **Index-only_scans** — https://wiki.postgresql.org/wiki/Index-only_scans
  *(distilled 2026-06-03 → `knowledge/wiki-distilled/Index-only_scans.md`)*
  2016 page; the core visibility-map gate is unchanged through PG18. The
  distilled doc supplements the VM bit semantics (`visibilitymap.c`) and the
  `btcanreturn`/`amcanreturn` path the wiki only gestures at
  [from-wiki](https://wiki.postgresql.org/wiki/Index-only_scans).

- **Free_Space_Map_Problems** — https://wiki.postgresql.org/wiki/Free_Space_Map_Problems
  *(distilled 2026-06-03 → `knowledge/wiki-distilled/Free_Space_Map_Problems.md`)*
  Narrower than its title: a detect-and-repair guide for corrupt `_fsm` forks
  around 2016 WAL-logging bugs (all in unsupported majors). Lasting value is the
  `pg_freespacemap` detection recipe; the distilled doc adds the actual FSM
  architecture (`FSM_CATEGORIES=256`, the `_fsm` fork) from the corpus
  [from-wiki](https://wiki.postgresql.org/wiki/Free_Space_Map_Problems).

- **Group_commit** — https://wiki.postgresql.org/wiki/Group_commit
  *(distilled 2026-06-03 → `knowledge/wiki-distilled/Group_commit.md`)*
  A stale 2012-era **design proposal** (Riggs/Geoghegan, targeted 9.2), not
  shipped behavior. The distilled doc records the history and then documents what
  PG actually does today — the implicit ganged `XLogFlush` plus the
  `commit_delay`/`commit_siblings` knob — from the corpus + docs
  [from-wiki](https://wiki.postgresql.org/wiki/Group_commit).

- **Dead wiki URLs (404 as of 2026-06-03 crawl):** `Logical_Decoding`,
  `MultiXacts`, `WAL_Internals`, `Generic_WAL` all return 404 — there is no
  such wiki page; these topics live in the official docs / source READMEs, and
  the corpus already documents `generic_xlog.c` and `multixact.c` per-file.
  `Parallel_Query_Execution` exists but is a stale 2017 design stub (superseded
  by `knowledge/docs-distilled/parallel-query.md`). All marked
  `[skipped:...]` in `progress/_queues/wiki.md` so they are not re-queued.

- **Backend_flowchart** — referenced everywhere but the wiki page URL
  returns 404 in our crawl. The actual flowchart asset lives in the
  source tree / on the main website, not the wiki [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## History / roadmaps (mostly archival)

- **Development_projects** — https://wiki.postgresql.org/wiki/Development_projects
  **Severely stale** — last modified May 2018, lists "Hot Standby" and
  "Streaming Replication" as Active despite being shipped a decade ago.
  Treat as historical catalogue only
  [from-wiki](https://wiki.postgresql.org/wiki/Development_projects).

- **PostgreSQL11_Roadmap**, **PostgreSQL10_Roadmap**, older 9.x pages —
  archival. Useful for "when was X added" archaeology only
  [from-wiki](https://wiki.postgresql.org/wiki/Development_information).

- **Past Developer Meeting Notes** (PgCon / FOSDEM, 2008–2024) — linked
  from Development_information. Genuinely useful for understanding *why*
  certain decisions were made
  [from-wiki](https://wiki.postgresql.org/wiki/Development_information).

---

## Open questions

- `Hacking_on_PostgreSQL` is referenced by other agents' notes but the URL
  returns **404**. Either the page was renamed/deleted or the link is
  apocryphal. Don't cite it.
- `Glossary` returned 404. The PG project does maintain a glossary inside
  the official documentation (https://www.postgresql.org/docs/current/glossary.html)
  — use that instead.
- `Working_with_GDB` returned 404; gdb guidance lives inside Developer_FAQ
  instead.
- `Developer_Mentoring` returned 404. There is an active **RRReviewers**
  program but no formal mentoring page found via this crawl. If a session
  needs a "find me a mentor" workflow, point to pgsql-hackers + RRR.
- `Backend_flowchart` wiki URL 404'd in our crawl despite frequent
  references; the canonical asset is in source tree / main site.
- `Coding_Conventions` is referenced but we did not successfully fetch it
  in this crawl — the authoritative coding style document is the
  official docs page at
  https://www.postgresql.org/docs/current/source.html. Treat that as
  primary.
