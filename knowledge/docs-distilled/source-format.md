---
source_url: https://www.postgresql.org/docs/current/source-format.html
chapter: "55.1 Formatting (source-format)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Source-code formatting — source-format

The §55.1 formatting rules that the `coding-style` skill operationalizes. This
is the canonical statement of "what `pgindent` enforces"; the skill turns it
into edit-time checks.

## Non-obvious claims

- **4-column tab stops, tabs *preserved* not expanded.** One logical
  indentation level = one tab stop. The 4-wide tab is load-bearing: viewing
  with the wrong width misaligns everything. Use `more -x4` / `less -x4`.
  [from-docs source-format]
- **BSD brace style:** braces of `if`/`while`/`switch`/etc. controlled blocks
  go on their **own lines**. [from-docs]
- **80-column readability target,** with explicit exception for long string
  literals where wrapping hurts more than it helps. [from-docs]
- **No `//` C++ comments** — `pgindent` rewrites them into `/* ... */`.
  [from-docs]
- **Block-comment style is fixed:**

  ```c
  /*
   * comment text begins here
   * and continues here
   */
  ```

  [from-docs]
- **Column-1 comments are preserved verbatim; indented comment blocks get
  re-flowed** by pgindent. To force line breaks inside an indented block, fence
  it with dash separators:

  ```c
  /*----------
   * preserved exactly
   * line by line
   *----------
   */
  ```

  This is the *only* portable way to keep hand-formatted comment layout through
  pgindent. [from-docs]
- **`pgindent` runs before every release,** so matching house style isn't
  optional — non-conforming code gets reflowed and shows up as churn in a later
  diff. Tooling lives in `src/tools/pgindent`; editor configs (Emacs, xemacs,
  vim) in `src/tools/editors`. [from-docs]
- **The overriding rule for a patch: "make the new code look like the existing
  code around it."** Local consistency beats any global preference. [from-docs]

## Links into corpus

- The skill that applies these at edit time (include order, C99 subset, naming
  on top of the formatting here): the `coding-style` skill +
  [[knowledge/conventions/coding-style.md]].
- The companion coding-conventions chapters:
  [[knowledge/docs-distilled/source-conventions.md]] (miscellaneous
  conventions) and [[knowledge/docs-distilled/error-style-guide.md]] (message
  wording).

## Caveats / verification

- All claims `[from-docs source-format]`. The authoritative behavior is
  whatever `src/tools/pgindent/pgindent` + the bundled `pg_bsd_indent` produce
  at anchor `e5f94c4808fe88c170840ac3a24cdfa423b404fc`; the prose is a summary
  of intent, the tool is the enforcer.
