# `contrib/xml2/xpath.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 953
- **Source:** `source/contrib/xml2/xpath.c`

The bulk of `contrib/xml2`. Exposes the **DEPRECATED** `xpath_*` family of
SQL functions for evaluating XPath against TEXT-encoded XML documents
using libxml2's DOM parser. The whole module is documented as
deprecated in favor of the core `xml` type's XPath support (introduced
in PG 8.4). Includes the awkward `xpath_table` function — a Set-Returning
Function that runs an SPI query to retrieve XML documents from another
table and then applies XPath to each. [verified-by-code]

## API / entry points

- `pgxml_parser_init(strictness)` `:67-81` — exported helper used by
  `xslt_proc.c`. Returns a `PgXmlErrorContext *` and initialises the
  libxml parser. Caller MUST `PG_TRY` and `pg_xml_done` to release it.
  [from-comment] `:62-66`
- `xml_encode_special_chars(text)` `:88-129` — encodes `<>&"\r` as
  XML entities. [verified-by-code]
- `xpath_nodeset(doc, xpath, toptag, septag)` `:264-302` — wraps the
  nodeset result with `<toptag>` and each node with `<septag>` tags.
  [verified-by-code]
- `xpath_list(doc, xpath, plainsep)` `:310-347` — joins nodeset
  results with a plain (non-XML) separator. [verified-by-code]
- `xpath_string(doc, xpath)` `:352-402` — wraps xpath in `string(...)`
  and returns the casted-to-string result. [verified-by-code]
- `xpath_number(doc, xpath)` `:407-448` — returns numeric value
  (FLOAT4). NaN is mapped to SQL NULL. [verified-by-code]
- `xpath_bool(doc, xpath)` `:453-490` — returns boolean. [verified-by-code]
- `xpath_table(pkey_field, xml_field, relname, xpaths_pipe_separated,
  condition)` `:631-953` — SRF that SELECTs `pkey, xml_field FROM
  relname WHERE condition` via SPI, then for each row applies the
  pipe-separated XPath expressions and emits a row per match. The
  comment at `:626-628` calls itself out as needing tidying.
  [from-comment + verified-by-code]

## The pattern (what this file teaches)

Every public function follows the same libxml2-wrapper pattern:

1. `pgxml_parser_init(PG_XML_STRICTNESS_LEGACY)` → `xmlerrcxt`.
2. `PG_TRY()` block: allocate workspace (`xpath_workspace { doctree,
   ctxt, res }`), invoke `xmlXPathCtxtCompile` + `xmlXPathCompiledEval`,
   convert result.
3. `PG_CATCH()`: cleanup workspace, `pg_xml_done(xmlerrcxt, true)`,
   `PG_RE_THROW()`.
4. `pg_xml_done(xmlerrcxt, false)` on the success path.

All libxml-allocated pointers are `volatile xmlXxxPtr` so the longjmp
in `pg_xml_error_occurred → xml_ereport` doesn't lose track of them.

## Notable invariants / details

- **INV-1: This whole module is officially deprecated.** From the
  contrib chapter intro and from the comments referring to it as
  "legacy". New code should use the in-core `xml` type and its
  `xpath()` function. [from-README/inferred] **[ISSUE-stale-todo:
  whole module flagged deprecated; still shipped (confirmed)]**
- **INV-2: Uses `PG_XML_STRICTNESS_LEGACY`** rather than
  `PG_XML_STRICTNESS_ALL` for parser init. That accepts more
  malformed XML than the core `xml` type does. [verified-by-code]
  `:277, 322, 377, 419, 464, 747`
- **INV-3: `pgxml_texttoxmlchar` just calls `text_to_cstring`** —
  no validation that the input bytes form a valid encoded XML
  document; libxml2 handles it on parse. [verified-by-code] `:250-254`
- **INV-4: NaN xpath_number result → SQL NULL.** Documented behaviour.
  [verified-by-code] `:444`
- **INV-5: Unsupported XPath result types emit `NOTICE` and a
  "<unsupported/>" placeholder string** rather than erroring. This
  is unusual for PG — normally we'd error. [verified-by-code]
  `:596-599, 856-862`
- **INV-6: `xpath_table` parses each XML doc separately**, with
  parser init OUTSIDE the SPI execution (comment `:743-746` notes
  "should happen after we are done evaluating the query, in case
  it calls functions that set up libxml differently" — defensive
  ordering). [from-comment]

## Potential issues

- `:625-628` Self-flagged `XXX`-style comment: "It needs some
  tidying (as do the other functions here!)". Acknowledged tech
  debt going back decades. [from-comment] **[ISSUE-stale-todo:
  xpath_table flagged for tidying (nit — module deprecated)]**
- `:782` Treating SPI NULL xmldoc as "not well-formed" emits an
  all-NULL tuple silently. A user expecting NULL → NULL pass-through
  might be surprised. [verified-by-code]
  **[ISSUE-doc-drift: NULL xmldoc → all-NULL tuple, not NULL (nit)]**
- `:670` `MAT_SRF_USE_EXPECTED_DESC` lets the caller declare an
  arbitrary tuple shape; the comment at `:678-684` notes "we trust
  the caller" — no per-row type validation. Bad column declaration
  just fails at coerce-time. [from-comment]
- `:201` `xmlNodeDump(buf, doc, node, 1, 0)` — the literal `1` is
  the "level" (indent depth) and `0` is the format flag. Magic numbers
  with no `#define`. Tutorial-level coding. [verified-by-code]
  **[ISSUE-style: xmlNodeDump call uses magic numbers (nit)]**
- `:540-543` In `pgxml_xpath`'s PG_CATCH, `comppath != NULL` cleanup
  is correct, but the workspace cleanup via `cleanup_workspace` is
  called even though the workspace's individual fields are mutated
  during normal flow. The `cleanup_workspace` helper is null-safe so
  this works, but adds a subtle dependency. [verified-by-code]
- `:594-600` `xpath_string` of an unsupported XPath result type
  (e.g. number, boolean) silently substitutes "<unsupported/>" rather
  than casting. Subtle behaviour for users who don't realize their
  XPath returned a non-string. [verified-by-code]
  **[ISSUE-correctness: silent <unsupported/> on unexpected XPath
  result type (likely confusing)]**
- `:769-771` Reset `values[j] = NULL` to ensure spare columns get
  NULL. Good defensive code.
- libxml security: `XML_PARSE_NOENT` is set on `xmlReadMemory`
  (`:88, 511, 778`) which expands external entities. Combined with
  network-fetchable entities this would be an XXE vulnerability —
  except `xslt_proc.c` sets `XSLT_SECPREF_READ_NETWORK` to
  forbid, and `XML_PARSE_NOENT` in libxml2 alone doesn't enable
  network fetches; only `XML_PARSE_NOENT | XML_PARSE_DTDLOAD`
  would. Still worth flagging. [inferred]
  **[ISSUE-security: XML_PARSE_NOENT enables entity expansion; check
  XXE surface (maybe)]**
