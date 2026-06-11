# `contrib/xml2/xslt_proc.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 276
- **Source:** `source/contrib/xml2/xslt_proc.c`

The XSLT-transform half of `contrib/xml2`. Provides
`xslt_process(doc, stylesheet [, params])` which applies an XSLT
stylesheet to an XML document using `libxslt`. The entire file is
`#ifdef USE_LIBXSLT`-gated: if libxslt was not found at configure time,
the function compiles to a stub that errors with "not available
without libxslt". DEPRECATED alongside the rest of `contrib/xml2`.
[verified-by-code]

## API / entry points

- `xslt_process(text doct, text ssheet [, text paramstr])` `:45-213` —
  the single SQL-callable function. Two-arg (no params) or three-arg
  form. Params string is `name1=value1,name2=value2,...`.
  [verified-by-code]
- `parse_params(text)` `:217-274` — internal helper that destructively
  splits a TEXT comma-and-equals string into a `(name, value, name,
  value, ..., NULL)` array suitable for `xsltApplyStylesheetUser`.
  Grows the array geometrically. [verified-by-code]

## The pattern (what this file teaches)

1. **Defence in depth via `xsltSetSecurityPrefs`**: explicitly
   forbid `READ_FILE`, `WRITE_FILE`, `CREATE_DIRECTORY`,
   `READ_NETWORK`, `WRITE_NETWORK`. (`:117-138`) Without these, an
   XSLT could `document('file:///etc/passwd')`. [verified-by-code]
2. **`PG_TRY` with `volatile`-tagged libxml/libxslt pointers** so
   that PG_CATCH cleanup is correct even if a longjmp fires from
   `xml_ereport`. [verified-by-code] `:56-62`
3. **`xsltParseStylesheetDoc(ssdoc)` takes ownership of ssdoc on
   success.** The code sets `ssdoc = NULL` on success so the
   PG_CATCH cleanup doesn't double-free. Comment explains.
   [from-comment + verified-by-code] `:103-109`
4. **Cleanup order in PG_CATCH** mirrors libxslt resource hierarchy
   (free results before context, context before stylesheet,
   stylesheet before docs). `:166-181` [verified-by-code]
5. **`xsltCleanupGlobals()`** called on both success and error paths
   to clear libxslt's global state. [verified-by-code] `:181, 194`

## Notable invariants / details

- **INV-1: Five security prefs are set explicitly to `xsltSecurityForbid`.**
  Any single failure flips a sticky `xslt_sec_prefs_error` flag; the
  subsequent ereport(ERROR) refuses to run the stylesheet. So **no
  XSLT can read/write files or do network I/O**. [verified-by-code]
- **INV-2: Empty-string result is normalised to `cstring_to_text("")`.**
  `xsltSaveResultToString` may return resstr=NULL on empty; code
  treats that as legitimate empty rather than NULL/error.
  [from-comment + verified-by-code] `:155-162`
- **INV-3: `resstat < 0` returns SQL NULL** rather than ereporting.
  Comment at `:201` calls this out as "pretty dubious, really
  ought to throw error instead". [from-comment]
  **[ISSUE-correctness: resstat < 0 silently becomes NULL (likely)]**
- **INV-4: Both `xmlReadMemory` calls use
  `XML_PARSE_NOENT`** (substitute entities). Combined with
  `XSLT_SECPREF_READ_NETWORK = xsltSecurityForbid`, network entity
  fetches are blocked at the libxslt layer — but XML entity
  expansion still happens at the libxml2 parse layer. So a "billion
  laughs" attack on the doc OR stylesheet text is still possible.
  [verified-by-code]
  **[ISSUE-security: billion-laughs / entity-expansion DoS possible
  via XML_PARSE_NOENT (maybe)]**
- **INV-5: Module gates ENTIRE function with `#ifdef USE_LIBXSLT`.**
  Build configure-time decision: with libxslt → real impl; without
  → stub that errors `ERRCODE_FEATURE_NOT_SUPPORTED`. [verified-by-code]
  `:206-211`
- **INV-6: `parse_params` is `static`** and only compiled when
  USE_LIBXSLT. [verified-by-code] `:215-216`

## Potential issues

- `:201-203` Self-flagged "XXX this is pretty dubious" — returning
  NULL on `xsltSaveResultToString` failure. [from-comment]
  **[ISSUE-stale-todo: XXX comment on dubious NULL-return path (nit)]**
- `:230` `max_params = 20; /* must be even! */` — magic-number
  initial size with constraint encoded in a comment only. Geometric
  doubling keeps it even, but a one-off bug could break that
  silently. [verified-by-code] **[ISSUE-style: even-array
  invariant encoded only in comment (nit)]**
- `:251-256` "If no equal sign, ignore this parameter" — silent
  drop. A user who typoed `param=val,foo,otherparam=val` would
  silently lose the middle entry. [verified-by-code]
  **[ISSUE-correctness: malformed XSLT parameters silently dropped
  (likely confusing)]**
- `:181, 194` `xsltCleanupGlobals` — called in both PG_CATCH and on
  the success path. libxslt's docs note that calling it while another
  transform is active is unsafe. In a concurrent backend (which we
  don't have — fork model) this would be a problem; in PG's model
  it's fine but worth noting. [inferred]
- `:140-141` `ereport(ERROR, errmsg("could not set libxslt security
  preferences"))` lacks an errcode. [verified-by-code]
  **[ISSUE-style: missing errcode on security-prefs error (nit)]**
- Whole module deprecated; new code should use the in-core
  XMLTABLE/XML functions. [inferred] **[ISSUE-stale-todo: module
  deprecated, still shipped (confirmed)]**
