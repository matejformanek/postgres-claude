# xml.c — `xml` type I/O + libxml2 integration

## Purpose

Implements the SQL `xml` type and bridges into libxml2 for parsing, XPath evaluation, XSLT-adjacent operations, `XMLTABLE`, `xpath()`, and the SQL/XML standard's transformation functions. Compiled only when `USE_LIBXML` is defined. The most security-sensitive file in the batch — XML parsing on user input is classic XXE territory.

Source: `source/src/backend/utils/adt/xml.c` (5169 lines).

- **Last verified commit:** `f0a4f280b4d3` (2026-06-25; anchor-bump re-pin — precise cites hold, two approximate function-location cites in the xpath/XMLTABLE region re-pinned +170/+180)

## Key functions (indexed)

- `xml_in` / `xml_out` / `xml_recv` / `xml_send` — type I/O. Validates via `xml_parse`. [verified-by-code, std locations]
- `pg_xml_init_library` (line 1208), `pg_xml_init` (line 1254) — set up libxml allocator hooks, error handler, and the entity loader. Every entry point that calls into libxml must wrap work in `PG_TRY` + `pg_xml_done`. [verified-by-code xml.c:1197-1370]
- `xmlSetExternalEntityLoader(xmlPgEntityLoader)` at xml.c:1319 — installs the PG entity loader globally. [verified-by-code]
- `xmlPgEntityLoader` at xml.c:2046 — the entity loader callback. Returns `xmlNewStringInputStream(ctxt, "")` for **every** external entity URL/ID, effectively replacing external entities with the empty string. [verified-by-code xml.c:2046-2051]
- `xml_parse` (line 1791) — the document/content parser. Uses `xmlNewParserCtxt` + `xmlCtxtReadDoc` with options `XML_PARSE_NOENT | XML_PARSE_DTDATTR` (+ `XML_PARSE_NOBLANKS` if requested). [verified-by-code xml.c:1886]
- `xpath` (line 4572) — XPath evaluation; uses `xmlCtxtReadMemory` then `xmlXPathCtxtCompile` + `xmlXPathCompiledEval`. Carefully uses the `Ctxt`-flavored compile to defend against stack overflow in libxml ≤ 2.13.3 (per comment, ref to libxml2 gitlab issue 799). [verified-by-code xml.c:4504-4510]
- `XmlTableFetchRow` (line 4933) / `XmlTableGetValue` (line 4978) — XMLTABLE row source. Per-row XPath eval (`xmlXPathCtxtCompile` at 4884/4918), namespaces honored. [verified-by-code xml.c:4933-4990]

## XXE / external entity stance

**xml.c does NOT set `XML_PARSE_NONET`** explicitly. Instead it sets `XML_PARSE_NOENT` (which would normally expand entities, including externals) and **relies on `xmlPgEntityLoader`** — installed globally via `xmlSetExternalEntityLoader` in `pg_xml_init` — to silently substitute the empty string for every external entity URL or PUBLIC ID. The comment at xml.c:2038-2044 documents this:

> Silently prevent any external entity URL from being loaded. We don't want to throw an error, so instead make the entity appear to expand to an empty string. We would prefer to allow loading entities that exist in the system's global XML catalog; but the available libxml2 APIs make that a complex and fragile task. For now, just shut down all external access.

**Net answer for the Phase D question**:

- `XML_PARSE_NOENT` IS set (entities are expanded — but only internally defined ones, because external resolution is killed).
- `XML_PARSE_NONET` is NOT set. The defense is the entity-loader override, not the libxml option.
- External DTDs cannot load (entity loader blocks them).
- Internal DTDs and `XML_PARSE_DTDATTR` (apply DTD-declared defaults) ARE honored, per SQL/XML:2008 GR 10.16.7.d.

This is a defensible design — `XML_PARSE_NONET` would only block `http://` URLs but not `file://` reads on some libxml builds, whereas the entity-loader replacement is uniform — but it's worth noting the disagreement with the conventional "set NONET" guidance.

## Phase D notes

- **No XXE: external entities are silently replaced with empty strings.** [verified-by-code xml.c:2046-2051]
- **Billion-laughs**: libxml2 has its own internal limits on entity-expansion depth, set via `XML_PARSE_HUGE` (NOT set here) and the global `xmlParserMaxAmplification`. The PG side does not explicitly tune amplification limits. Rely on libxml2 defaults.  `[unverified — would need to confirm libxml2's default-amplification behavior on the deployed version]`.
- **XPath stack overflow**: explicitly defended via `xmlXPathCtxtCompile` (not the deprecated `xmlXPathCompile`); see comment block xml.c:4502-4507. [verified-by-code]
- **XPath argument is xmlChar*** passed through `pg_xmlCharStrndup`. No string-quoting issue — XPath args are passed as compiled expressions, not concatenated into a textual XPath. [verified-by-code]
- **Custom libxml allocator**: `USE_LIBXMLCONTEXT` hooks libxml's malloc to a long-lived `LibxmlContext` MemoryContext so leaks on error can be wholesale freed. [verified-by-code xml.c:2030]
- **PG_TRY discipline**: every entry into libxml is wrapped, and `xmlSetExternalEntityLoader(saved)` is restored on exit; see xml.c:1365.

## Potential issues

- `[ISSUE-xxe: external entity expansion is blocked by xmlPgEntityLoader rather than XML_PARSE_NONET; effective but unconventional. A future libxml2 API change could regress this if the entity loader is bypassed for some new entity-resolution path (maybe; medium severity if regressed)]`.
- `[ISSUE-dos: billion-laughs defense relies on libxml2's internal amplification limit, not a PG-side check; older libxml2 versions had weaker defaults (maybe — version-dependent)]`.
- `[ISSUE-trust-boundary: xml.c emits libxml-generated DETAIL strings; if libxml ever includes attacker-controlled URL content in error text, that text becomes part of the SQL error and could leak through logs (low)]`.
- `[ISSUE-stale-todo: comment at xml.c:2042 says "we would prefer to allow loading entities that exist in the system's global XML catalog; but ... For now, just shut down all external access" — open future-work flag (low)]`.
- `[ISSUE-dos: xml_in on a 1 GiB XML document parses fully; no streaming. By design (low)]`.
- `[ISSUE-correctness: xpath() in non-UTF8 databases skips xml-decl parsing and is documented as "non-ASCII bug-compatible with historical behavior" at xml.c:4449-4451 (low; documented)]`.

Confidence: XXE answer `[verified-by-code]`; amplification claim `[unverified]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
