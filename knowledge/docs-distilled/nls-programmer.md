---
source_url: https://www.postgresql.org/docs/current/nls-programmer.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §57.2: Native Language Support — For the Programmer

How translatable strings work in the backend: the gettext wiring, `nls.mk`, and —
the part that bites patch authors — the **rules against concatenating or inline-
pluralizing** message text. Direct companion to the `error-handling` skill: every
`errmsg()` is implicitly a translatable string.

## The gettext wiring [from-docs]

- A program enables NLS by, at startup (guarded by `ENABLE_NLS`):
  `setlocale(LC_ALL, "")`, `bindtextdomain("<progname>", LOCALEDIR)`,
  `textdomain("<progname>")`. [from-docs]
- Strings are marked for translation with **`gettext()`**, conventionally aliased
  to the **`_()`** macro: `#define _(x) gettext(x)`. [from-docs]
- **The backend's `ereport()`/`errmsg()` call `gettext` internally** — so backend
  message strings do **not** need individual `_()` marking; they're translated by
  virtue of going through the error machinery. [from-docs]
  [verified-by-code, source/src/backend/utils/error/elog.c — `errmsg` runs the
  format string through `gettext`; via knowledge/idioms/error-handling.md]

## `nls.mk` — what makes a string get extracted [from-docs]

Each translatable program has an `nls.mk` declaring:
- **`CATALOG_NAME`** — the textdomain (matches `textdomain()`).
- **`GETTEXT_FILES`** — source files to scan for translatable strings.
- **`GETTEXT_TRIGGERS`** — function names whose arguments are translatable, beyond
  the default `gettext`. Syntax: `_`, `func:2` (2nd arg is the string),
  `func:1,2` (plural singular/plural args).
- **`po/LINGUAS`** — the list of provided translations. [from-docs]

A string is translatable iff it is `_()`/`gettext()`-marked **or** passed to a
`GETTEXT_TRIGGERS` function (which is why `errmsg` strings qualify automatically).
[from-docs]

## The two rules patch authors break [from-docs]

1. **No runtime concatenation of message fragments.** Word order differs by
   language, so fragments don't translate independently:
   ```c
   /* WRONG */ printf("Files were %s.\n", flag ? "copied" : "removed");
   /* RIGHT */ if (flag) printf("Files were copied.\n");
               else      printf("Files were removed.\n");
   ```
2. **No inline pluralization** (`"%d file%s", n, n!=1?"s":""`): English plural
   rules don't generalize; many languages have several plural forms. Use
   **`errmsg_plural(singular, plural, n, ...)`** in `ereport`, or the underlying
   **`ngettext()`** elsewhere. The translator receives both English forms and
   supplies the per-language set; runtime picks by the control value `n`. [from-docs]
   [verified-by-code, source/src/include/utils/elog.h — `errmsg_plural`]

## Translator comments [from-docs]

- A `/* translator: ... */` comment immediately before a marked string is **copied
  into the `.po` catalog** to disambiguate for translators. Use it when a string
  is non-obvious. [from-docs]

## Links into corpus

- [[knowledge/idioms/error-handling.md]] — `errmsg`/`errdetail`/`errmsg_plural`;
  the strings this chapter governs.
- [[knowledge/docs-distilled/error-style-guide.md]] — wording rules that compound
  with translatability (e.g. complete sentences translate; fragments don't).
- [[knowledge/docs-distilled/nls.md]] — the parent NLS chapter (end-user /
  installation side).

## Gaps / follow-ups

- The `.po`/`.pot` catalog build mechanics (msgfmt, `make update-po`) are only
  sketched here; they live in the build system, not a corpus doc yet.
