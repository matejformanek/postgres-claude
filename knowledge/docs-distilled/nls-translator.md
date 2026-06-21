---
source_url: https://www.postgresql.org/docs/current/nls-translator.html
fetched_at: 2026-06-21T00:00:00Z
anchor_sha: f25a07b2d94c
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §57.1: Native Language Support — For the Translator

The translator-facing half of NLS. The companion §57.2
([nls-programmer.md](./nls-programmer.md)) covers how a *backend programmer*
makes strings translatable (the `gettext` triggers, `_()` / `errmsg()` marking);
this page covers the **catalog workflow** — gettext PO/POT/MO files, the make
targets, and the format-string rules that matter even to C hackers who never
translate a string (because they constrain how you may write `errmsg()` calls).

## The three file types

- **`.po` (Portable Object)** — plain text, human-editable; one `msgid`
  (original English) → `msgstr` (translation) per entry, with `#`-comments and
  `#,`-flags. `[from-docs]`
- **`.pot` (PO Template)** — a *blank* catalog extracted from the source; the
  `.pot` extension distinguishes the template from production `.po` files. `[from-docs]`
- **`.mo` (Machine Object)** — the binary runtime form; built from `.po`, never
  hand-edited; this is what `libintl`/`gettext` loads at run time. `[from-docs]`

## Naming & layout

- Translation files live in a **`po/`** directory next to an **`nls.mk`** file
  that marks the program as translation-enabled. `[from-docs]`
- **`po/LINGUAS`** lists the available language codes (e.g. `de fr pt_BR`). `[from-docs]`
- File naming: `progname.pot` (template), `language.po` (e.g. `fr.po`, ISO 639-1
  lowercase), or `language_region.po` (e.g. `pt_BR.po`, ISO 3166-1 uppercase
  region). `[from-docs]`

## The make targets

- **`make init-po`** — generate a blank `progname.pot` from the program source;
  copy it to `language.po` to start a new translation. `[from-docs]`
- **`make update-po`** — re-extract from updated source and merge into existing
  `.po` files, emitting `*.po.new`; entries whose source string drifted are
  flagged **`fuzzy`**. `[from-docs]`
- Tooling: end users need `libintl` + `msgfmt`; translators additionally need
  **`xgettext`** and **`msgmerge`**; GNU Gettext **≥ 0.10.36** is recommended;
  the source must be configured with **`--enable-nls`**. `[from-docs]`

## The flags that bite C programmers

- **`c-format`** — marks a `msgid` as a printf-style template; the translation
  *must* remain a valid format string with the **same specifiers in the same
  count and types**. `[from-docs]`
- **`fuzzy`** — the source string changed and the translation may be stale;
  **fuzzy entries are NOT shipped to end users** (the runtime falls back to the
  English `msgid`). `[from-docs]`

## Positional args — the rule that constrains errmsg() authors

- When a target language needs a *different word order*, the translation reorders
  arguments using **`%n$` positional specifiers** (e.g. German
  `"Die Datei %2$s hat %1$u Zeichen."` for English
  `"File %s has %u characters"`). The digit-dollar must come **immediately after
  `%`**, before any other format manipulators. `[from-docs]`
- **Backend-coding implication:** because translators can only *reorder* the
  arguments you gave them — not add, drop, or retype them — an `errmsg()` string
  must keep its substitution arguments stable and self-sufficient. This is the
  deep reason PG style forbids assembling messages from sentence fragments: a
  fragment can't be reordered into another language's grammar. `[inferred]`
  (Pairs with the `error-style-guide` skill / [error-style-guide.md](./error-style-guide.md).)

## Translator discipline (corpus-relevant facts)

- **Partial translations are fine** — missing/empty `msgstr` falls back to
  English; never submit a *wrong* translation to fill a gap. `[from-docs]`
- A translator may only edit text inside `msgstr` quotes, add `#`-comments, and
  toggle the `fuzzy` flag — nothing else in the `.po`. `[from-docs]`
- Preserve newlines/tabs/whitespace and the original's tone (lowercase
  fragments, no trailing period unless the original has one). Report errors in
  the *original* string upstream rather than "fixing" them in translation. `[from-docs]`

## Links into corpus

- §57.2 programmer side (how strings get marked translatable):
  [docs-distilled/nls-programmer.md](./nls-programmer.md)
- §57 parent: [docs-distilled/nls.md](./nls.md) `primary`
- Error-message conventions these rules interlock with:
  [docs-distilled/error-style-guide.md](./error-style-guide.md),
  [docs-distilled/error-message-reporting.md](./error-message-reporting.md)
- Relevant skills: `error-handling` (errmsg/errdetail authoring), `coding-style`.
