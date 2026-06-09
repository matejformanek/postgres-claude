# utils/xml.h — XML datum, libxml2 wrappers, table_func

Source: `source/src/include/utils/xml.h` (94 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Declares the `xmltype` (alias for `varlena`), the libxml2 error-context wrapper, the strictness enum, and the public XML manipulation API (xmlconcat, xmlelement, xmlparse, xmlpi, xmlroot, xmltotext).

## Public API

- `typedef varlena xmltype;` (`xml.h:23`) — XML is just a varlena with a different OID.
- `XmlStandaloneType` (`xml.h:25-31`) — YES / NO / NO_VALUE / OMITTED for the XML declaration.
- `XmlBinaryType` (`xml.h:33-37`) — BASE64 / HEX for xmlbinary GUC.
- `PgXmlStrictness` (`xml.h:39-45`): LEGACY / WELLFORMED / ALL.
- `pg_xml_init_library`, `pg_xml_init(strictness)`, `pg_xml_done`, `pg_xml_error_occurred`, `xml_ereport` (`xml.h:65-70`).
- `xmlparse(data, xmloption_arg, preserve_whitespace, escontext)` (`xml.h:76`) — soft-error capable.
- `xmltotext_with_options`, `escape_xml`, `map_sql_identifier_to_xml_name`, `map_xml_name_to_sql_identifier`, `map_sql_value_to_xml_value` (`xml.h:80-86`).
- `XmlTableRoutine` — TableFuncRoutine const (`xml.h:92`).

## Invariants

- **INV-xml-builds-with-or-without-libxml** [inferred]: most function bodies are `#ifdef USE_LIBXML`; on builds without libxml, they ereport at runtime. Header declares the prototypes unconditionally.
- **INV-xml-strictness-tiers** [from-comment, `xml.h:41-44`]:
  - LEGACY: ignore errors unless function result says so.
  - WELLFORMED: ignore non-parser messages.
  - ALL: report everything.
  Choice affects whether warnings + non-parse errors propagate to SQL.
- **INV-xml-xmloption-GUC-enum** [verified-by-code, `xml.h:90`]: `extern int xmloption` for the GUC enum; cast to `XmlOptionType` at use.

## Notable internals

- `PgXmlErrorContext` is opaque (`xml.h:48`); lives in xml.c, returned from `pg_xml_init` and passed to every libxml call inside a `pg_xml_init` / `pg_xml_done` bracket.

## Trust-boundary / Phase-D surface

- **A7 XXE custom defense** [from-corpus]: xml.c's `pg_xml_init` installs custom libxml error/loader callbacks specifically to defeat XXE (XML External Entity) attacks. This header declares `pg_xml_init` but does NOT mention that calling libxml without going through `pg_xml_init` defeats the XXE defense. Any new XML code path that uses libxml directly is a potential XXE regression.
- **`XML_PARSE_NONET` absence** — the header surfaces no constant for "block network parses", because the defense is implemented via custom loader callback rather than the standard libxml flag. Documenting this here would help reviewers spot regressions.
- **xmlparse `escontext`** (`xml.h:76`) — soft-error path; old `xmlparse` callers must migrate.

## Cross-refs

- `source/src/backend/utils/adt/xml.c` — pg_xml_init custom callbacks (XXE defense).
- `source/src/backend/executor/nodeTableFuncscan.c` — `XmlTableRoutine` consumer.
- A7 finding cluster: XXE defense is the headline Phase-D anchor in this file.

## Issues

- `[ISSUE-INVARIANT: pg_xml_init must wrap every libxml call (high)]` — header does not state this; new contrib code calling libxml directly would bypass the XXE defense silently. Recommend a `// NOTE: ALWAYS bracket libxml calls with pg_xml_init/pg_xml_done` comment block.
- `[ISSUE-DOC: XML_PARSE_NONET not referenced (medium)]` — the *absence* of this libxml flag is the point (custom callback used instead); header could document that intentional choice.
