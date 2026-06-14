# contrib-xml2 (legacy XPath + XSLT)

- **Source path:** `source/contrib/xml2/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `xml2.control`)
- **Trusted:** no (XML processing has security implications)
- **Status:** Deprecated. Use built-in `xml` type instead for
  new code.

## 1. Purpose

Legacy XML processing extension predating PG's built-in
`xml` data type. Provides:

- **XPath querying** — `xpath_*` family of functions for
  extracting values from XML.
- **XSLT transformation** — `xslt_process` for applying
  stylesheets.
- **XML I/O** — `xml_is_well_formed`, `xml_valid`, etc.

Most functionality is **superseded by the built-in `xml`
type** (PG 8.3+) and core SQL/XML functions. xml2 lives on
for backwards compatibility with schemas built before SQL/XML
support.

## 2. The two C files

| File | LOC | What it does |
|---|---|---|
| `xpath.c` | 953 | XPath querying via libxml2 |
| `xslt_proc.c` | 276 | XSLT transformation |

[verified-by-code `wc -l source/contrib/xml2/*.c`]

Both use `libxml2` (and `libxslt` for the XSLT) directly.
The `--with-libxml` (always) and `--with-libxslt` (XSLT
only) build flags must have been set.

## 3. Why deprecated?

The historical context:
- xml2 was added in PG 8.0 to provide minimal XML processing.
- PG 8.3 added the `xml` data type with proper SQL/XML
  support.
- Core SQL functions (`xpath`, `xpath_exists`, `xmlparse`,
  `xmlserialize`) cover most use cases.
- xml2's "string-based XML" approach is fragile vs the
  proper xml type.

The README in `source/contrib/xml2/` says:

> Most of the functionality provided by this module has
> been superseded by the SQL/XML support added to the main
> server in PostgreSQL 8.3 and later.

## 4. SQL surface — XPath family

| Function | Returns |
|---|---|
| `xpath_string(xml, path)` | Single string match |
| `xpath_number(xml, path)` | Numeric match |
| `xpath_bool(xml, path)` | Boolean predicate |
| `xpath_nodeset(xml, path)` | All matching nodes |
| `xpath_list(xml, path, separator)` | Joined values |
| `xpath_table(...)` | Tabular result |

The signatures pre-date proper PG XML types; arguments are
text/XML mixed. The modern core `xpath(xpath_expr, xml)`
covers most use cases with cleaner semantics.

## 5. The xpath_table function

The interesting one — projects XML into a table:

```sql
SELECT * FROM xpath_table(
    'id',                       -- key column XPath
    'name|email|phone',         -- value column XPaths
    'people_xml',               -- table to read from
    '/person',                  -- record root
    'id IS NOT NULL'           -- WHERE clause
) AS x(id int, name text, email text, phone text);
```

Like a multi-row XPath join. Modern alternative: parse XML
with `xpath` to extract individual values, no special
function needed.

## 6. SQL surface — XSLT

```sql
SELECT xslt_process(my_xml, my_stylesheet);
SELECT xslt_process(my_xml, my_stylesheet, 'param1=value1');
```

[verified-by-code `xslt_proc.c`]

Apply an XSLT stylesheet to an XML document, returning the
transformed result. Supports parameters via a comma-
separated `name=value` string.

XSLT is a transformation language; useful for converting
XML-encoded data to text/HTML/other formats. PG doesn't have
a built-in equivalent — xml2 is still the way to do XSLT in
PG.

## 7. Security implications

XML processing is a known attack surface:

- **XXE (XML External Entity)** — malicious XML can fetch
  files or external URLs at parse time.
- **Billion-laughs** — DoS via nested entity expansion.
- **XSLT extension elements** — some libxslt features can
  execute arbitrary code.

xml2 uses libxml2's default parser settings, which DO
disable external-entity fetching by default. But XSLT
remains a risk: don't apply user-supplied stylesheets.

## 8. Production-use guidance

- **For new code, use the core `xml` type** + SQL/XML
  functions.
- **For XSLT, use xml2's `xslt_process`** — it's the only
  in-tree XSLT.
- **Don't expose `xslt_process` to untrusted input** —
  stylesheets can be hostile.
- **For XML schemas that predate PG 8.3**, xml2's
  XPath functions remain compatible.
- **Migrate when you can** — xml2 may eventually be removed.

## 9. Invariants

- **[INV-1]** Built on libxml2 (`--with-libxml` required).
- **[INV-2]** XSLT requires libxslt (`--with-libxslt`).
- **[INV-3]** Mostly deprecated; new code uses core `xml`
  type.
- **[INV-4]** XML processing has security implications;
  audit input sources.
- **[INV-5]** `xslt_process` is the only in-tree XSLT.

## 10. Useful greps

- The xpath entry points:
  `grep -n 'PG_FUNCTION_INFO_V1\|xpath_' source/contrib/xml2/xpath.c | head -10`
- The XSLT entry:
  `grep -n 'xslt_process' source/contrib/xml2/xslt_proc.c`
- The core xml type alternative:
  `grep -n 'xpath\|xmlparse' source/src/backend/utils/adt/xml.c | head -10`

## 11. Cross-references

- `knowledge/subsystems/contrib-pgcrypto.md` — sibling
  external-library-dependent contrib.
- `.claude/skills/fmgr-and-spi/SKILL.md` — SQL-callable
  pattern.
- `.claude/skills/extension-development/SKILL.md` —
  `--with-libxml` build-time gate.
- `source/contrib/xml2/` — implementation directory.
- `source/src/backend/utils/adt/xml.c` — the modern core
  `xml` type + SQL/XML functions.
