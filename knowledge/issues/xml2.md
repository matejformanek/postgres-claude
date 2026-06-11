# Issues — `contrib/xml2`

DEPRECATED contrib module providing the legacy `xpath_*` and
`xslt_process` SQL functions backed by libxml2 (DOM parser) and
libxslt. Whole module is documented as deprecated in favor of the
in-core `xml` type's XPath/XMLTABLE support. 2 source files covered
in this sweep / ~1 229 LOC.

**Parent docs:** `knowledge/files/contrib/xml2/*` (2 docs:
`xpath.c.md`, `xslt_proc.c.md`).

**Source:** ~12 entries surfaced 2026-06-11 by A21-B.

## Headlines

1. **Whole module is deprecated, still shipped.** Comments
   reference "needs tidying", self-flagged `XXX` markers persist;
   ongoing maintenance happens but new code should use the in-core
   `xml` type (PG 8.4+).
2. **XSLT uses `xsltSetSecurityPrefs` to forbid file + network I/O
   (read/write file, create dir, read/write network).** Good
   defence in depth. But `XML_PARSE_NOENT` is set on both
   `xmlReadMemory` calls in `xslt_proc.c` and `xpath.c`, so entity
   expansion happens at the libxml2 layer — billion-laughs DoS still
   possible against either the doc or the stylesheet.
3. **`xslt_process` returns SQL NULL on `xsltSaveResultToString
   < 0`.** Self-flagged "XXX this is pretty dubious, really ought to
   throw error instead". Errors masked as NULL.
4. **Several silent-fallback paths in `xpath.c`**: NaN xpath_number
   → SQL NULL, unsupported XPath result type → `NOTICE` plus
   `<unsupported/>` literal string instead of ereport.

## Entries — `xpath.c`

- [ISSUE-stale-todo: whole module flagged deprecated; still shipped (confirmed)] — module-wide
- [ISSUE-stale-todo: `xpath_table` flagged "needs tidying" (XXX comment) (nit)] — `:625-628`
- [ISSUE-doc-drift: NULL xmldoc treated as "not well-formed" → all-NULL tuple, not pass-through NULL (nit)] — `:781-790`
- [ISSUE-style: `xmlNodeDump(buf, doc, node, 1, 0)` uses magic level/format numbers (nit)] — `:201`
- [ISSUE-correctness: silent "<unsupported/>" placeholder for non-string XPath results (likely confusing)] — `:594-600, 856-862`
- [ISSUE-security: `XML_PARSE_NOENT` enables entity expansion; XXE / billion-laughs surface (maybe)] — `:88, 511, 778`
- [ISSUE-undocumented-invariant: `PG_XML_STRICTNESS_LEGACY` is more permissive than core `xml` type's strictness (nit)] — `:277, 322, 377, 419, 464`

## Entries — `xslt_proc.c`

- [ISSUE-stale-todo: whole module deprecated; still shipped (confirmed)] — module-wide
- [ISSUE-stale-todo: XXX comment on "dubious" NULL-return for `resstat < 0` (likely)] — `:201-203`
- [ISSUE-correctness: malformed XSLT parameter strings silently drop entries (no equal sign → ignore) (likely)] — `:251-256`
- [ISSUE-style: missing `errcode()` on security-prefs error (nit)] — `:140-141`
- [ISSUE-style: `max_params = 20; /* must be even! */` constraint encoded in comment (nit)] — `:230`
- [ISSUE-security: billion-laughs / entity-expansion DoS possible via `XML_PARSE_NOENT` (maybe)] — `:88, 95`
