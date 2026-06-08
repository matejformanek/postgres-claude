---
source_url: https://www.postgresql.org/docs/current/source.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 56: PostgreSQL Coding Conventions

The *official* style chapter (the wiki `Coding_Conventions` page points here as
the source of truth). Four sections: Formatting, Reporting Errors Within the
Server, Error Message Style Guide, Miscellaneous Coding Conventions. This doc
captures the rules that are easy to get wrong in a patch and that reviewers flag
— it is the docs-side companion to the `coding-style` and `error-handling`
skills.

## §56.1 Formatting

- **4-column tab stops; indent with tabs, not spaces.** Layout is **BSD style**.
  [from-docs] [cross: knowledge/conventions/coding-style.md]
- **`pgindent` is authoritative** — code is reindented with it; don't hand-fight
  the formatter. Block comments use the `/* ... */` star-aligned form; the
  decorative `/*------` block-comment headers are **exempt** from pgindent
  reflowing. [from-docs] [from-wiki — Developer_FAQ echo]
- Code must compile **clean under the project warning flags** (effectively
  `-Werror`-grade for the buildfarm). [from-docs]

## §56.2 Reporting Errors Within the Server

- Use **`ereport()`** (not bare `elog`) for user-facing errors; `elog` is for
  internal "can't happen" errors. The mechanics (SQLSTATE selection, errmsg /
  errdetail / errhint) are the `error-handling` skill's domain. [from-docs]
  [cross: knowledge/idioms/error-handling.md]

## §56.3 Error Message Style Guide (the high-flag-rate rules)

- **Primary message: not capitalized, NO trailing period.** [from-docs]
- **Detail and hint messages: complete sentences — capitalized, WITH trailing
  period.** This asymmetry (primary vs detail/hint punctuation) is the single
  most common reviewer nit. [from-docs]
- **Prefer active voice; avoid the passive.** "could not open file" not "file
  could not be opened" where avoidable. [from-docs]
- **Quote object names with the conventional double-quote style** used across the
  tree; don't invent quoting. [from-docs]
- **Don't leak implementation detail / file-internal jargon** into user-facing
  text; keep messages translatable — avoid sentence assembly by string
  concatenation, which breaks for other languages' word order. [from-docs]

## §56.4 Miscellaneous Coding Conventions

- **C standard = C99 subset** (the tree restricts to a portable subset; e.g. no
  `//` comments, no VLAs, no mid-block declarations in the house style). [from-docs]
  [cross: knowledge/conventions/coding-style.md — the concrete C99-subset list]
- **Function-like macros:** parenthesize every argument and the whole expansion;
  beware double-evaluation of arguments with side effects. [from-docs]
- **Multi-statement macros MUST be wrapped in `do { ... } while(0)`** so they
  behave as a single statement under `if (x) MACRO(); else ...`. This is the
  canonical PG macro idiom. [from-docs] [verified-by-code — pervasive across
  source/src/include/, e.g. the `*_VALID`/list macros]
- Be explicit about **signed vs unsigned**; avoid implicit narrowing/conversion.
  [from-docs]

## Links into corpus

- [[knowledge/conventions/coding-style.md]] — the corpus's working style doc;
  this chapter is its upstream source.
- [[knowledge/idioms/error-handling.md]] — ereport/elog mechanics §56.2 defers to.
- [[knowledge/wiki-distilled/Creating_Clean_Patches.md]] — diff hygiene that
  pairs with pgindent discipline.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — where "run pgindent,
  compile clean" become submission gates.
- coding-style + error-handling skills (the operational rulebooks).

## Caveats

- This chapter is prose; the *enforced* version is `src/tools/pgindent` +
  `typedefs.list` + the buildfarm warning flags. When a rule here and the
  `coding-style` skill seem to disagree, the skill carries the concrete,
  code-verified list (C99-subset specifics, include order) and wins. [inferred]
