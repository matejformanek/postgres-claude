---
source_url: https://www.postgresql.org/docs/current/xml2.html
fetched_at: 2026-07-16
anchor_sha: 572c3b2ddf8c
module: contrib/xml2
---

# xml2 — legacy XPath / XSLT (DEPRECATED)

Pre-SQL/XML XPath querying + an XSLT bridge, kept only for migration. **Deprecated
since PostgreSQL 8.3** in favor of the in-core `xml` type, `XMLTABLE()`,
`XMLEXISTS()`, and standard XPath functions; scheduled for eventual removal.
Its API is deliberately incompatible with the standard one. Author: John Gray.

## Non-obvious claims

- Everything operates on **`text`, not the core `xml` type** — the module
  predates the `xml` type entirely. `xml_valid(document text) → boolean` is
  just an alias for core `xml_is_well_formed()` and (per the docs' own note)
  is *misnamed*: it checks **well-formedness, not DTD/schema validity**.
  `[from-README]`
- Scalar XPath extractors each coerce the XPath result to a SQL type by name:
  `xpath_string → text`, `xpath_number → real`, `xpath_bool → boolean`. All
  take `(document text, query text)`. `[verified-by-code source/contrib/xml2/xpath.c:365,420,466]`
- `xpath_nodeset(document, query [, toptag] [, itemtag]) → text` wraps a
  node-set as `<toptag><itemtag>…</itemtag>…</toptag>`; 1-/2-/3-arg overloads
  drop the tags. `xpath_list(document, query [, separator]) → text` flattens a
  node-set to a delimited scalar (default separator `,`).
  `[verified-by-code source/contrib/xml2/xpath.c:277,323]`
- The headline function `xpath_table(key, document, relation, xpaths,
  criteria) → setof record` is a **table function that builds and runs SQL by
  string substitution**: internally it issues `SELECT <key>,<document> FROM
  <relation> WHERE <criteria>` via SPI, then applies each `|`-separated XPath
  to the document column. Requires an `AS t(...)` column list; must have ≥1
  output column (`errmsg "xpath_table must have at least one output column"`).
  `[verified-by-code source/contrib/xml2/xpath.c:644,647,691,739]`
- **`criteria` cannot be empty** — pass `true` (or `1=1`) to select all rows,
  because it is spliced directly into the generated WHERE clause. `[from-README]`
- **SQL-injection hazard, by design:** `relation`, `criteria`, etc. are
  substituted into plain SQL with no parameterization — the docs explicitly
  warn to validate any user-supplied value. This is a core reason it's
  deprecated, not merely superseded. `[from-README][verified-by-code xpath.c:739 SPI query built from args]`
- **Multivalued-row quirk:** `xpath_table` treats every XPath as potentially
  multi-valued and emits `max(matches over all xpaths)` rows, filling short
  columns with NULL positionally. A single-valued XPath (e.g. `/doc/@num`)
  therefore appears **only on the first row**; the documented workaround is to
  self-join two `xpath_table` calls. This positional-zip behavior is the
  module's most surprising semantics. `[from-README]`
- `xslt_process(document, stylesheet [, paramlist]) → text` applies an XSLT
  stylesheet; **compiled only `#ifdef USE_LIBXSLT`** — without libxslt the
  function is silently unavailable. `paramlist` is `a=1,b=2` form and its
  parser is "simple-minded": **parameter values cannot contain commas**.
  `[verified-by-code source/contrib/xml2/xslt_proc.c:4,15,25-29][from-README]`
- `xml_encode_special_chars(text) → text` (entity-escape helper) is also
  exported. `[verified-by-code source/contrib/xml2/xpath.c:86]`

## Migration mapping (why it's deprecated)

| xml2 | in-core replacement |
|------|---------------------|
| `xml_valid` | `xml_is_well_formed` |
| `xpath_string/_number/_bool` | `xpath(...)` + cast, or `XMLEXISTS` |
| `xpath_table` | `XMLTABLE()` (SQL:2006, proper row-generating) |
| `xslt_process` | (no core equivalent; keep libxslt or move out of DB) |

## Links into corpus

- Core XML type + `XMLTABLE` / `XMLEXISTS` that supersede this module:
  no dedicated docs-distilled note yet — candidate gap
  (`gap:core-xml-xmltable`). The core code lives in
  `src/backend/utils/adt/xml.c`.
- SPI query execution `xpath_table` relies on:
  `[[knowledge/docs-distilled/spi.md]]`.
- Set-returning-function protocol (`setof record`, `AS t(...)` column
  binding): `[[knowledge/docs-distilled/xfunc-c.md]]`,
  `[[knowledge/docs-distilled/tablefunc.md]]`.
