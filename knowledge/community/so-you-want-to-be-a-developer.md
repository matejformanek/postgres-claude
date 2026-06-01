# "So, you want to be a developer?" — distilled

Source: https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F
Crawled: 2026-06-01.

This is the "where do I even start" page. Reorganized as a checklist for a
new (or new-to-this-project) Claude session.

---

## Phase 0 — environment

- [ ] Install **git**, a working **C toolchain**, and **perl**
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).
- [ ] Clone the official repo:
  `https://git.postgresql.org/git/postgresql.git`
  [from-wiki](https://wiki.postgresql.org/wiki/Working_with_Git).
- [ ] Compile from source and run the regression test suite green
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).
- [ ] Set up your pager: `pager = less -x4` (tabs are 4 spaces in PG)
  [from-wiki](https://wiki.postgresql.org/wiki/Working_with_Git).

## Phase 1 — orientation

- [ ] Read **Developer_FAQ** end-to-end once; bookmark for reference
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).
- [ ] Skim the **TODO** list to get a feel for what's open
  [from-wiki](https://wiki.postgresql.org/wiki/Todo). Heed:
  > "Do not assume that you can select one, code it and then expect it
  > to be committed."
  > [from-wiki](https://wiki.postgresql.org/wiki/Todo)
- [ ] Search the pgsql-hackers archive **before** proposing anything:
  > "starting a project should always begin with a search of our
  > PostgreSQL mailing list archives"
  > [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)
- [ ] Read **Submitting_a_Patch** and **Reviewing_a_Patch** so you
  know what the finish line looks like
  [from-wiki](https://wiki.postgresql.org/wiki/Development_information).

## Phase 2 — community participation

- [ ] Subscribe to **pgsql-hackers** (and skim, don't just lurk)
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).
- [ ] Mailing-list etiquette is enforced socially. Quoting verbatim:
  > "Be conservative in what you send; be liberal in what you accept"
  > [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).
- [ ] Use "reply all", no HTML email, no top-posting, strip
  confidentiality notices, ask for clarification when confused
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).
- [ ] First post to -hackers about a feature should include:
  problem description, relevant standards/docs links, affected source
  areas, timeline, links to prior discussion, and a wiki status page
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).

## Phase 3 — coding

- [ ] Match the surrounding code's naming convention rather than
  imposing your own. Quoting:
  > "Readability and consistency within a section of code is of
  > greater importance than universal consistency"
  > [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)
- [ ] 4-space tabbed indenting, strict ANSI C comment formatting
  [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).
- [ ] Use `palloc`/`pfree`, `ereport`/`elog`, `SearchSysCache` —
  the canon idioms (see developer-faq-distilled.md in this repo).
- [ ] Run `pgindent` before sending the patch
  [from-wiki](https://wiki.postgresql.org/wiki/Developer_FAQ).

## Phase 4 — submitting

- [ ] Generate the patch with `git format-patch`
  [from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch).
- [ ] **Required for non-WIP**: regression tests + documentation.
  > "Any patch without these two items is automatically considered a
  > WIP one."
  > [from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch)
- [ ] Email pgsql-hackers with project name, file name (v1, v2…),
  short description, target branch, compile/test status, perf impact,
  design rationale, related TODO items
  [from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch).
- [ ] After it's archived, add it to the open **CommitFest** at
  https://commitfest.postgresql.org [from-wiki](https://wiki.postgresql.org/wiki/CommitFest).

## Phase 5 — timing & reciprocity

- [ ] Major features need to land in the review queue **July–December**
  to make the next major release:
  > "Getting a major feature into a major release generally requires
  > getting the patch into the review queue sometime between
  > July-December"
  > [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)
- [ ] Avoid submitting during an *active* CommitFest; tag for the next
  one if you'd otherwise clash
  [from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch).
- [ ] **Reciprocity expected**: each submitter should review another
  similar-scope patch ("Mutual Review Offset Obligations")
  [from-wiki](https://wiki.postgresql.org/wiki/Submitting_a_Patch).
- [ ] Consider joining **RRReviewers** (Round-Robin) to get assigned
  patches and learn by reviewing — confirmed active as of Aug 2025
  [from-wiki](https://wiki.postgresql.org/wiki/RRReviewers).

---

## Quoted core values

> "Be conservative in what you send; be liberal in what you accept"
> [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)

> "Readability and consistency within a section of code is of greater
> importance than universal consistency"
> [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F)

> "Our philosophy about conversations/code in public" — section title
> on the page. PG is radically public-by-default; closed channels are
> discouraged for design discussion
> [from-wiki](https://wiki.postgresql.org/wiki/So,_you_want_to_be_a_developer%3F).

---

## Open questions

- The page links out to a "TODO" list and to "Mailing Lists" but does
  *not* link Developer_FAQ, Submitting_a_Patch, or CommitFest directly
  in its body text (those have to be discovered via
  Development_information). A new dev landing here cold gets only
  partial pointers — the wiki's IA is genuinely confusing
  [inferred from crawl].
- The page does not mention **meson** (the current default build
  system as of PG ≥ 16) — its build instructions implicitly assume
  the older autoconf path. Cross-check this repo's
  `.claude/skills/build-and-run/SKILL.md` for the current canon.
- No explicit pointer to a mentorship program. RRReviewers is the
  closest active analogue and is recommended as the "learn by doing"
  on-ramp.
