---
source_url: https://www.postgresql.org/docs/current/nls.html
fetched_at: 2026-06-08T20:54:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Native Language Support (for the programmer)

How translatable strings are marked and extracted in the backend. Relevant to
any patch that adds user-facing `ereport`/`elog` text: get the marking right
and the message becomes translatable for free; get it wrong (assembled
fragments) and you create an untranslatable string.

## Mechanism

- PG uses **GNU `gettext`**: `gettext("string")` looks up a translation at
  runtime, and the **`_()` macro** is the in-tree shorthand that marks a string
  literal as translatable *and* performs the lookup. [from-docs]
- Catalogs use the standard gettext file trio: **`.pot`** (template, extracted
  from source), per-language **`.po`** (translations), compiled **`.mo`**
  (binary, loaded at runtime). Backend catalogs live under **`src/backend/po/`**
  (each binary/library has its own `po/`). [from-docs]
- NLS must be turned on at build time with **`--enable-nls`** (meson:
  `-Dnls=enabled`); without it the `_()` calls compile to plain pass-through. [from-docs]

## Per-program `nls.mk`

- Each translatable program/library carries an **`nls.mk`** declaring:
  - **`CATALOG_NAME`** — the catalog's base name.
  - **`GETTEXT_FILES`** — source files to scan for marked strings.
  - **`GETTEXT_TRIGGERS`** — the function names whose string argument should be
    extracted (e.g. `errmsg`, `errdetail`, `errhint`, `errmsg_plural`), plus
    **`GETTEXT_FLAGS`** for printf-style format checking. [from-docs]

## ereport / message marking

- **`errmsg()` argument is auto-extracted** for translation (it's a default
  trigger); **`errmsg_internal()` is NOT translated** — use it for
  "can't-happen" internal errors so translators don't waste effort. [from-docs]
  [verified-by-code, via [[knowledge/idioms/error-handling.md]]]
- **`gettext_noop("...")`** marks a string for extraction *without* translating
  at that point — for strings stored in a table/array and translated later
  (e.g. GUC descriptions, error-context arrays). [from-docs]
- **Plurals use `ngettext()`** (or `errmsg_plural()` in ereport) so languages
  with multiple plural forms translate correctly — never branch on `n == 1`
  yourself. [from-docs]

## Message-writing rules (so strings stay translatable)

- **Never assemble a sentence from fragments.** Concatenated pieces give
  translators no grammatical context and can't reorder for other languages —
  write each message as a complete sentence with parameters. [from-docs]
- Provide enough standalone context in each message; rely on `errdetail`/
  `errhint` rather than gluing clauses. (Pairs with the capitalization/period
  rules in the corpus error-handling idiom.) [from-docs]

## Links into corpus
- [[knowledge/idioms/error-handling.md]] — ereport/errmsg vs errmsg_internal, SQLSTATE, message style.
- Skill: `error-handling` — the backend rules these NLS conventions reinforce.

## Gaps / follow-ups
- The default `GETTEXT_TRIGGERS` set (which ereport helpers are scanned by
  default vs. must be listed per-`nls.mk`) is given by example only on the docs
  page; `src/nls-global.mk` holds the authoritative default list — worth a
  per-file doc if a future patch touches translation extraction.
