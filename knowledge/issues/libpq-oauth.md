# Issues — `libpq-oauth`

Per-subsystem issue register for the libpq client-side OAuth Device
Authorization module (`src/interfaces/libpq-oauth/`) plus the
`src/interfaces/libpq/test/` URI-regress helper. See
`knowledge/issues/README.md` for the tag convention, severity scale, and
workflow.

**Parent docs:** `knowledge/files/src/interfaces/libpq-oauth/*.md`

Surfaced 2026-06-11 by the `pg-file-backfiller` cloud routine while
documenting the OAuth device-flow engine (anchor
`e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa`). Conservative — the module is
careful, well-commented security code; these are second-look items, not
confirmed defects.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | oauth-curl.c:998 | correctness | maybe | `parse_json_number` uses `sscanf("%lf")`, which honors `LC_NUMERIC`; a comma-decimal locale could truncate JSON `interval`/`expires_in` (e.g. `"5.5"`→5). Low impact (cadence/prompt hint, clamped) but locale-fragile. | open | knowledge/files/src/interfaces/libpq-oauth/oauth-curl.c.md §Potential issues |
| 2026-06-11 | oauth-curl.c:344 | leak | maybe | `client_secret` (and the urlencoded `username`/`password` copies at oauth-curl.c:2402-2403) freed with plain `free()`, no `explicit_bzero`, while the access token IS scrubbed (oauth-curl.c:368). Credential lingers in freed heap; asymmetry worth review. | open | knowledge/files/src/interfaces/libpq-oauth/oauth-curl.c.md §Potential issues |
| 2026-06-11 | oauth-curl.c:2363 | undocumented-invariant | nit | UTF-8 pre-encoding (RFC 6749 App. B) skipped on the assumption client id/secret are 7-bit ASCII (App. A), but the conninfo values are never validated as ASCII. | open | knowledge/files/src/interfaces/libpq-oauth/oauth-curl.c.md §Potential issues |
| 2026-06-11 | test-oauth-curl.c:149 | correctness | maybe | `fill_pipe` saves status flags via `F_GETFL` but restores via `F_SETFD` (descriptor-flags command) — wrong fcntl namespace; looks like a `F_SETFL` slip. Test-only, harmless in practice. | open | knowledge/files/src/interfaces/libpq-oauth/test-oauth-curl.c.md §Potential issues |
| 2026-06-11 | libpq_uri_regress.c:50 | undocumented-invariant | nit | Pre-existing `XXX`: lockstep `opts`/`defs` walk assumes both APIs return options in identical keyword order. True by construction today; brittle coupling. | open | knowledge/files/src/interfaces/libpq/test/libpq_uri_regress.c.md §Invariants & gotchas |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- The module is intentionally decoupled from `libpq-int.h` in the
  dynamic-library build (`USE_DYNAMIC_OAUTH`); the duplicated SIGPIPE /
  threadlock / gettext shims in `oauth-utils.c` are a standing
  doc-drift watch point against libpq's real internal definitions (the
  source comment itself flags deduplication as future work).
- Real security gates in this module are solid and worth remembering as
  positive findings: byte-exact issuer match (RFC 9207 mix-up defense,
  oauth-curl.c:2256), HTTPS-only endpoint enforcement (oauth-curl.c:2306),
  256 KiB response cap + JSON depth cap 16 + up-front UTF-8 verification,
  and token scrubbing on cleanup. The `PGOAUTHDEBUG` trace mode
  deliberately exposes secrets and is opt-in only (oauth-curl.c:1668).
