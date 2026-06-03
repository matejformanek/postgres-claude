# pg-gssapi.h

- **Source path:** `source/src/include/libpq/pg-gssapi.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definitions for including GSSAPI headers" — thin shim that pulls in
`<gssapi.h>` (or `<gssapi/gssapi.h>` depending on platform) and works
around a Windows symbol collision. No PG-defined API; pure include
plumbing [from-comment].

## Public API surface

- (Conditional on `ENABLE_GSS`) re-exports `<gssapi.h>` + `<gssapi_ext.h>`,
  picking the right path based on `HAVE_GSSAPI_H`.
- `#undef X509_NAME` at the bottom — Windows `<wincrypt.h>` defines this
  symbol, which collides with OpenSSL's. The comment explains the include
  order issue can't be reliably fixed because `libpq-be.h` pulls in OpenSSL
  [from-comment].

## Cross-refs

- Used by: `knowledge/files/src/include/libpq/libpq-be.h.md`,
  `knowledge/files/src/include/libpq/be-gssapi-common.h.md`.

## Potential issues

- **[ISSUE-stale-todo: documented but unfixable include-order hack]**
  `pg-gssapi.h:29-38` — the `#undef X509_NAME` is a fragile collision
  workaround; if a future Windows SDK change moves the macro elsewhere or
  another OpenSSL header defines the same name in a different way, the
  workaround becomes silently wrong. The comment acknowledges the
  fragility ("can't reliably fix that by re-ordering #includes"). Severity:
  maybe.

## Tally

`[verified-by-code]=2 [from-comment]=2`
