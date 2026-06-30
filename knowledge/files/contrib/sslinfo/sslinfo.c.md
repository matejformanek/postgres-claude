# sslinfo.c

## One-line summary

476-line contrib module exposing TLS-connection introspection (version, cipher, peer certificate DN fields, X.509 extensions) to SQL via PG_FUNCTION_INFO_V1 wrappers around OpenSSL — every function gated on `MyProcPort->ssl_in_use` and (for peer-cert info) `peer_cert_valid`. Source pin `4b0bf0788b0`.

## Public API / entry points

SQL-callable functions (all `PG_FUNCTION_INFO_V1`):

- `ssl_is_used()` → `bool`. `source/contrib/sslinfo/sslinfo.c:44-49` [verified-by-code]
- `ssl_version()` → `text` (NULL if not SSL). `source/contrib/sslinfo/sslinfo.c:55-69` [verified-by-code]
- `ssl_cipher()` → `text` (NULL if not SSL). `source/contrib/sslinfo/sslinfo.c:75-89` [verified-by-code]
- `ssl_client_cert_present()` → `bool`. Returns `MyProcPort->peer_cert_valid`. `source/contrib/sslinfo/sslinfo.c:98-103` [verified-by-code]
- `ssl_client_serial()` → `numeric` (NULL if no client cert). `source/contrib/sslinfo/sslinfo.c:114-134` [verified-by-code]
- `ssl_client_dn_field(text fieldname)` → `text`. Returns a single field (e.g. `CN`) of the subject DN. `source/contrib/sslinfo/sslinfo.c:236-252` [verified-by-code]
- `ssl_issuer_field(text fieldname)` → `text`. Same for issuer DN. `source/contrib/sslinfo/sslinfo.c:271-287` [verified-by-code]
- `ssl_client_dn()` → `text`. Full subject DN string. `source/contrib/sslinfo/sslinfo.c:299-314` [verified-by-code]
- `ssl_issuer_dn()` → `text`. Full issuer DN string. `source/contrib/sslinfo/sslinfo.c:326-341` [verified-by-code]
- `ssl_extension_info()` → SETOF `(name text, value text, critical bool)`. SRF over `X509_get_ext_count`. `source/contrib/sslinfo/sslinfo.c:352-476` [verified-by-code]

Internal helpers:

- `ASN1_STRING_to_text(const ASN1_STRING *str)` — converts an OpenSSL ASN1_STRING into a server-encoded `text` Datum. `source/contrib/sslinfo/sslinfo.c:150-181` [verified-by-code]
- `X509_NAME_field_to_text(const X509_NAME *name, text *fieldName)` — looks up a named field (`CN`, `OU`, etc.) by OID and converts. `source/contrib/sslinfo/sslinfo.c:196-217` [verified-by-code]

## Key invariants

- **Every cert-returning function returns NULL when `!ssl_in_use || !peer_cert_valid`.** So a non-SSL connection cannot probe certificate fields. `source/contrib/sslinfo/sslinfo.c:121, 243, 305, 332` [verified-by-code]
- **`ssl_is_used()` and `ssl_client_cert_present()` are exceptions** — they return `bool` directly (false for non-SSL), so they're safe to call in any session. `source/contrib/sslinfo/sslinfo.c:48, 102` [verified-by-code]
- **`ssl_issuer_field()` has a different gate than `ssl_client_dn_field()`.** It checks `!MyProcPort->peer` (the raw `X509 *`), not `!ssl_in_use || !peer_cert_valid`. So it can return data from an UNVERIFIED peer certificate if one was sent. `source/contrib/sslinfo/sslinfo.c:278-279` [verified-by-code] `[ISSUE-security: asymmetric NULL-gate — ssl_issuer_field reveals issuer of an unverified cert while ssl_client_dn_field requires verification; intentional? (likely)]`
- **DN encoding is RFC 2253-flavored UTF-8.** `ASN1_STRING_print_ex` is called with `(ASN1_STRFLGS_RFC2253 & ~ASN1_STRFLGS_ESC_MSB) | ASN1_STRFLGS_UTF8_CONVERT` — RFC 2253 escaping minus high-bit escaping, plus UTF-8 output. `source/contrib/sslinfo/sslinfo.c:166-168` [verified-by-code]
- **The DN string is re-encoded via `pg_any_to_server`.** Any UTF-8 bytes that can't represent in the server encoding are replaced (per comment, by question marks). `source/contrib/sslinfo/sslinfo.c:142-143, 173` [from-comment + verified-by-code]
- **`ssl_client_dn()` and `ssl_issuer_dn()` use `NAMEDATALEN`-sized stack buffers.** 64 bytes. Long DNs are silently truncated by the backend's `be_tls_get_peer_subject_name` / `be_tls_get_peer_issuer_name` — those callers don't error on overflow. `source/contrib/sslinfo/sslinfo.c:303, 308, 330, 335` [verified-by-code]
- **`ssl_client_serial` also uses a 64-byte `NAMEDATALEN` buffer.** Serial number → decimal → `numeric_in` via `DirectFunctionCall3`. A 64-byte decimal can represent ~158 decimal digits → ~525-bit integer, larger than the 159-bit RFC 5280 max, so safe in practice. `source/contrib/sslinfo/sslinfo.c:118, 124, 129-132` [verified-by-code]
- **No superuser check anywhere.** All functions are SQL-callable by any role with `EXECUTE` on the function (default grant is PUBLIC per the typical `.sql` install script). `source/contrib/sslinfo/sslinfo.c` [verified-by-code, by absence] `[ISSUE-defense-in-depth: cert details (peer DN, issuer, extensions, serial) exposed to any role with TLS; useful for app-layer auth but also means a SECURITY DEFINER caller can leak its own connection's cert metadata (maybe)]`

## Notable internals

### `ASN1_STRING_to_text` flow (lines 150-181)

1. `BIO_new(BIO_s_mem())` — heap-allocated OpenSSL memory BIO. NULL → `ereport(ERROR, ERRCODE_OUT_OF_MEMORY)`.
2. `ASN1_STRING_print_ex(membuf, str, flags)` — flags described above. **Return value not checked** — the function returns `int` (length written, -1 on error) but the source ignores it. `source/contrib/sslinfo/sslinfo.c:166-168` [verified-by-code] `[ISSUE-error-handling: ASN1_STRING_print_ex return value ignored — malformed ASN1_STRING input could produce empty BIO that gets converted to "" silently (maybe)]`
3. Manual null-termination: `BIO_write(membuf, &nullterm, 1)` then `BIO_get_mem_data(membuf, &sp); size-1`. Standard idiom for OpenSSL memory BIOs that don't auto-terminate.
4. `pg_any_to_server(sp, size-1, PG_UTF8)` — encoding conversion. Returns either a new pstrdup'd buffer or `sp` itself if no conversion needed.
5. `cstring_to_text(dp)` then `if (dp != sp) pfree(dp)` — frees only the conversion result if it differs from `sp`.
6. `BIO_free(membuf)` — error path: `elog(ERROR, ...)` if non-1 (note: `elog`, not `ereport`, so no SQLSTATE explicit).
7. **`BIO_free` failure leaks `result`.** If `BIO_free` returns non-1, `elog(ERROR)` longjmps without explicitly freeing `result` — but `result` was palloc'd in the per-tuple memory context so the longjmp's context-reset handles it. `[verified-by-code: result is via cstring_to_text → palloc → context-managed]`

### `X509_NAME_field_to_text` flow (lines 196-217)

1. `text_to_cstring(fieldName)` — palloc'd cstring.
2. `OBJ_txt2nid(string_fieldname)` — OpenSSL OID-database lookup; accepts both short names ("CN") and long names ("commonName").
3. `NID_undef` → `ereport(ERROR, ERRCODE_INVALID_PARAMETER_VALUE)` — typo in field name is a hard error.
4. `pfree(string_fieldname)` AFTER the error check (so the error path leaks the cstring, but it's per-call so the executor cleanup handles it).
5. `X509_NAME_get_index_by_NID(unconstify(X509_NAME *, name), nid, -1)` — `unconstify` cast is because pre-1.1 OpenSSL took a non-const here. Modern OpenSSL 1.1+ accepts const but the project keeps the cast for portability.
6. `index < 0` → return `(Datum) 0` (NOT a NULL Datum — a literal numeric 0). The callers check `if (!result)` to convert this sentinel to SQL NULL. `source/contrib/sslinfo/sslinfo.c:213-214` [verified-by-code] `[ISSUE-api-shape: returning Datum 0 as "no such field" sentinel is fragile — if a valid Datum ever evaluated to 0 it would be misinterpreted; safe for text Datums (always pointers) but worth a comment (nit)]`
7. `X509_NAME_get_entry → X509_NAME_ENTRY_get_data` — no NULL check on either intermediate result. OpenSSL guarantees non-NULL if `index >= 0`, but this is convention. `[ISSUE-correctness: missing defensive NULL checks on OpenSSL X509_NAME_get_entry / X509_NAME_ENTRY_get_data return values; OpenSSL contract says non-NULL if index valid, but malformed certs have surprised callers before (nit)]`

### `ssl_extension_info` SRF (lines 352-476)

- Standard `funcapi.h` SRF pattern with `SRF_IS_FIRSTCALL` / `SRF_FIRSTCALL_INIT` / `SRF_PERCALL_SETUP` / `SRF_RETURN_NEXT` / `SRF_RETURN_DONE`.
- Per-call BIO allocation: a fresh `BIO_new(BIO_s_mem())` on every iteration. Could be hoisted to firstcall, but the overhead is negligible for typical cert extension counts (~5-10).
- `OBJ_obj2nid(obj)` on the extension OID → `NID_undef` → `ereport(ERROR, ERRCODE_FEATURE_NOT_SUPPORTED, "unknown OpenSSL extension ... at position %d")`. **A cert with an unregistered OID extension causes a hard error mid-iteration.** `source/contrib/sslinfo/sslinfo.c:441-446` [verified-by-code] `[ISSUE-error-handling: ssl_extension_info errors on first unknown-OID extension instead of skipping/returning OID-as-text; downside: caller can't enumerate the cert at all if one extension is OID-only (likely)]`
- `X509V3_EXT_print(membuf, ..., flag=0, indent=0)` returns `<= 0` → `ereport(ERROR, ERRCODE_FEATURE_NOT_SUPPORTED, "could not print extension value ...")`. Same brittle-iteration concern. `source/contrib/sslinfo/sslinfo.c:451-455` [verified-by-code]
- `cstring_to_text_with_len(buf, len)` — uses the BIO's exact byte length; no encoding sanitization. **The extension value is NOT passed through `pg_any_to_server` like DN strings are.** Extension contents that aren't UTF-8 will be stored as-is and may be invalid in the server encoding. `source/contrib/sslinfo/sslinfo.c:457` [verified-by-code] `[ISSUE-correctness: ssl_extension_info "value" field bypasses pg_any_to_server; if a malicious peer sends an extension with high-bit bytes the resulting text may be invalid in non-UTF8 server encodings (likely)]`
- `BIO_free(membuf)` failure → `elog(ERROR, ...)` mid-SRF; partial tuple already built but not yet returned. `source/contrib/sslinfo/sslinfo.c:468-469` [verified-by-code]

## Trust boundary / Phase D surface

### Function-level privilege

- **All ten SQL functions are unrestricted.** No `superuser()` check, no `pg_read_all_settings` membership check. The default install grants `EXECUTE` to `PUBLIC` (per typical contrib `.sql` script — not shown here, but consistent with the pattern).
- **Implication:** any authenticated user on a TLS connection can read their own cert details. Useful for app-layer auth (e.g., `CREATE POLICY ... USING (current_user = ssl_client_dn_field('CN'))`).
- **Side-channel:** a non-SSL connection probing `ssl_version()` gets NULL; an SSL connection gets a string. This is a 1-bit channel between SSL/non-SSL — but the caller already knows that from their own `pg_hba.conf` outcome, so not novel.

### Cross-session leakage

- **`MyProcPort` is per-backend.** Each connection sees only its own SSL state. There is no shared state between backends, and no way to query another session's certificate via these functions. `source/src/include/libpq/libpq-be.h` [cross-ref]

### DN encoding gotchas

- **RFC 2253 escaping minus ESC_MSB plus UTF8_CONVERT.** Multi-byte UTF-8 characters in CN/O/OU are emitted as UTF-8 bytes (not `\XX` escapes). `source/contrib/sslinfo/sslinfo.c:166-168` [verified-by-code]
- **`pg_any_to_server` converts UTF-8 → server encoding** with replacement chars on unmappable code points. If your server is SQL_ASCII you get bytes through unchanged; if it's LATIN1 you get `?` for any non-LATIN1 character. The function comment says "Any invalid characters are replaced by question marks" but **the actual implementation is `pg_any_to_server`, whose replacement behavior depends on whether the source/destination pair has a registered conversion**. `source/contrib/sslinfo/sslinfo.c:142-143, 173` [from-comment, verified-by-code] `[ISSUE-documentation: comment overstates the "?" replacement guarantee — pg_any_to_server ERRORs on unmappable bytes for some encoding pairs; only for others does it substitute (nit)]`
- **Embedded NULs in DN strings:** ASN1_STRING_to_text uses `cstring_to_text(dp)` which is `strlen`-based. A DN containing a NUL byte would be truncated at the NUL. RFC 5280 forbids embedded NULs in DirectoryString but a malformed cert could carry them. `source/contrib/sslinfo/sslinfo.c:174` [verified-by-code] `[ISSUE-correctness: embedded NUL in an ASN1_STRING DN field is silently truncated by cstring_to_text; for a SECURITY-relevant DN comparison this could be a downgrade (CN="admin\0evil.com" → "admin") (likely)]`

### OpenSSL API surface

- `ASN1_STRING_print_ex` — encoding flags as above.
- `OBJ_txt2nid` / `OBJ_obj2nid` / `OBJ_nid2sn` — OID-database lookup; depends on OpenSSL's compile-time OID table.
- `X509_NAME_get_index_by_NID` / `X509_NAME_get_entry` / `X509_NAME_ENTRY_get_data` — DN field walk.
- `X509_get_subject_name` / `X509_get_issuer_name` — subject/issuer accessors.
- `X509_get_ext_count` / `X509_get_ext` / `X509_EXTENSION_get_object` / `X509_EXTENSION_get_critical` / `X509V3_EXT_print` — extension iteration.
- **No `X509_NAME_print_ex` use here** (the related but distinct DN-printing function); the full-DN strings come from the backend's `be_tls_get_peer_subject_name` / `be_tls_get_peer_issuer_name`, which internally use `X509_NAME_print_ex` per `src/backend/libpq/be-secure-openssl.c`. Cross-reference for encoding gotchas.
- **No OpenSSL 3.0-specific shims here** (no `EVP_*_fetch`, no provider API). The module uses the X509/ASN1 surface that's stable from 1.1.0 through 3.x. `[verified-by-code: only openssl/x509.h, x509v3.h, asn1.h headers]`
- **`unconstify` casts on lines 212 and 438, 451** — accommodates pre-1.1 OpenSSL where some accessors took non-const X509_NAME / X509_EXTENSION. `source/contrib/sslinfo/sslinfo.c:212, 438, 451` [verified-by-code]

### `ssl_extension_info` and malformed certs

- The function iterates `X509_get_ext_count` extensions and parses each. A peer-cert with a malformed extension can:
  - Cause `OBJ_obj2nid` to return `NID_undef` → mid-iteration ERROR (covered above).
  - Cause `X509V3_EXT_print` to return `<= 0` → mid-iteration ERROR.
  - Carry non-UTF8 bytes that propagate through `cstring_to_text_with_len` (no sanitization).
- The cert was already validated by the TLS handshake before being exposed via `MyProcPort->peer`, but **the TLS handshake's validation is structural, not semantic** — OpenSSL accepts certs with weird-but-spec-conformant extensions, which sslinfo then surfaces. `[ISSUE-defense-in-depth: ssl_extension_info trusts the TLS handshake's validation; a self-signed-trusted cert (clientcert=verify-ca with a malicious CA) can carry arbitrary extension data that lands directly in user-visible text columns (maybe)]`

### `MemoryContextSwitchTo` discipline in the SRF

- The firstcall switches into `multi_call_memory_ctx` for `fctx` palloc and `BlessTupleDesc`; switches back before the early `SRF_RETURN_DONE(funcctx)` branch — good.
- The per-call loop uses the default per-tuple context for `BIO_new`, `heap_form_tuple`, etc. No explicit switch needed because SRF_PERCALL_SETUP doesn't change the context. `source/contrib/sslinfo/sslinfo.c:374, 398, 402` [verified-by-code]

## Cross-references

- `source/src/backend/libpq/be-secure-openssl.c` — implements `be_tls_get_version`, `be_tls_get_cipher`, `be_tls_get_peer_serial`, `be_tls_get_peer_subject_name`, `be_tls_get_peer_issuer_name`. The sslinfo module is a thin SQL wrapper over these.
- `source/src/backend/libpq/auth.c` — the peer-cert verification path that sets `MyProcPort->peer_cert_valid`.
- `source/src/include/libpq/libpq-be.h` — `struct Port` definition: `ssl_in_use`, `peer_cert_valid`, `peer` (the raw `X509 *`).
- `source/src/backend/utils/mb/mbutils.c` — `pg_any_to_server`.
- Prior sweep A2 (libpq SSL/SCRAM) — handshake-side of TLS that produces the `MyProcPort` fields sslinfo reads.
- `source/contrib/sslinfo/sslinfo.sql.in` — function declarations and GRANTs (not examined in this sweep; would confirm `PUBLIC EXECUTE` default).

<!-- issues:auto:begin -->
- [Issue register — `sslinfo`](../../../issues/sslinfo.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-security: ssl_issuer_field gates on !peer instead of !ssl_in_use || !peer_cert_valid — returns issuer-DN data from an UNVERIFIED peer cert; asymmetric vs ssl_client_dn_field (likely)]`
- `[ISSUE-defense-in-depth: no superuser/role check; cert metadata callable by PUBLIC (maybe)]`
- `[ISSUE-correctness: embedded NUL in an ASN1_STRING DN field silently truncates the field via cstring_to_text; security-sensitive for app-layer DN comparisons (likely)]`
- `[ISSUE-correctness: ssl_extension_info "value" bypasses pg_any_to_server — non-UTF8 extension content lands in text columns without encoding validation (likely)]`
- `[ISSUE-error-handling: ASN1_STRING_print_ex return value ignored at sslinfo.c:166 — malformed input produces silently-empty output (maybe)]`
- `[ISSUE-error-handling: ssl_extension_info errors hard on first unknown-OID extension via OBJ_obj2nid; caller can't enumerate even the known extensions of a cert that has any unknown one (likely)]`
- `[ISSUE-api-shape: X509_NAME_field_to_text uses Datum 0 as "no such field" sentinel — works for text Datums (pointers) but is fragile if function ever returns a non-pointer Datum type (nit)]`
- `[ISSUE-defense-in-depth: ssl_extension_info trusts TLS-handshake structural validation; a verify-ca with malicious CA can plant arbitrary extension text into user-visible rows (maybe)]`
- `[ISSUE-documentation: ASN1_STRING_to_text comment says "?" replacement but actual behavior depends on pg_any_to_server's encoding-conversion pair semantics (nit)]`
- `[ISSUE-correctness: missing defensive NULL checks on X509_NAME_get_entry / X509_NAME_ENTRY_get_data return values; OpenSSL contract guarantees non-NULL but malformed certs have surprised callers historically (nit)]`
- `[ISSUE-memory: ssl_extension_info allocates a fresh BIO_new per row; cheap but unnecessary — could hoist to firstcall (nit)]`
- `[ISSUE-api-shape: ssl_client_dn() returns the full DN via NAMEDATALEN=64 buffer; long DNs silently truncated by be_tls_get_peer_subject_name without any indication (maybe)]`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-sslinfo.md](../../../subsystems/contrib-sslinfo.md)
