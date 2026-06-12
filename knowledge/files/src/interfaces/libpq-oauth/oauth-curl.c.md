---
path: src/interfaces/libpq-oauth/oauth-curl.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 3163
depth: deep
---

# `oauth-curl.c` — libcurl implementation of the OAuth Device Authorization flow

## Purpose

This file is the entire client-side engine for libpq's built-in
OAUTHBEARER authentication, implementing the **OAuth 2.0 Device
Authorization Grant** (RFC 8628) on top of libcurl's *multi* (async)
interface. When a server demands `OAUTHBEARER` SASL and the application
hasn't supplied its own token via a custom hook, libpq loads this module
(`libpq-oauth`, a separately-linked dynamic library — see
[[oauth-utils.c]] for why it's decoupled from `libpq-int.h`) and calls
`pg_start_oauthbearer()`. The module then drives three HTTP exchanges
entirely without blocking the caller's event loop: (1) an OIDC
*discovery* GET to learn the provider's endpoints, (2) a *device
authorization* POST to obtain a `user_code` + `verification_uri` to show
the human, and (3) a polling loop of *token* POSTs until the user
finishes the out-of-band browser login or the device code expires. The
resulting bearer token is handed back to libpq's SASL layer. Everything
is structured as a resumable state machine (`enum OAuthStep`) so a single
logical flow can span many `PQconnectPoll()` calls; the file exposes a
single multiplexer fd (epoll on Linux, kqueue on the BSDs/macOS) as the
`altsock` the client selects on.

## Public symbols

| Symbol | Kind | Site | Notes |
|---|---|---|---|
| `pg_start_oauthbearer(PGconn *, PGoauthBearerRequestV2 *)` | extern fn | oauth-curl.c:3062 | The only exported entry point (decl in [[oauth-curl.h]]). Allocates `async_ctx`, parses conninfo, wires up the async + cleanup callbacks, builds the curl + multiplexer handles. Returns 0 / -1. |

Everything else is `static`. The two function pointers installed into
the request drive the rest of the flow:

| Installed callback | Site | Role |
|---|---|---|
| `pg_fe_run_oauth_flow` | oauth-curl.c:2996 | `request->v1.async` — pumped by `PQconnectPoll`; wraps the impl in SIGPIPE masking. |
| `pg_fe_cleanup_oauth_flow` | oauth-curl.c:355 | `request->v1.cleanup` — tears down curl handles, scrubs the token. |

## Internal landmarks

### The async state machine
`enum OAuthStep` (oauth-curl.c:206) — `INIT → DISCOVERY →
DEVICE_AUTHORIZATION → TOKEN_REQUEST ⇄ WAIT_INTERVAL`. The driver
`pg_fe_run_oauth_flow_impl` (oauth-curl.c:2796) is modeled on
`PQconnectPoll`: a first `switch` finishes the in-flight request (or
waits on the timer), a second `switch` starts the next one. Each network
step is a `start_*`/`finish_*` pair with `drive_request()` pumping libcurl
in between.

- `struct async_ctx` (oauth-curl.c:220) — the heap state that survives
  across calls: cached conninfo (`client_id`, `client_secret`, `ca_file`),
  the curl multi + easy handles, the `mux`/`timerfd` descriptors, the
  three-part error accumulator (`errctx` + `errbuf` + `curl_err`,
  oauth-curl.c:247-271), and the cached `provider`/`authz` documents.
- `free_async_ctx` (oauth-curl.c:290) — single teardown path; removes the
  easy handle from the multi handle, cleans up both, frees the parsed docs,
  closes `mux`/`timerfd`.

### Multiplexer abstraction (epoll vs kqueue)
`setup_multiplexer` (oauth-curl.c:1224), `register_socket`
(oauth-curl.c:1282), `comb_multiplexer` (oauth-curl.c:1448),
`set_timer`/`timer_expired`/`drain_timer_events` (oauth-curl.c:1496,
1593, 1639). libcurl hands us sockets via `CURLMOPT_SOCKETFUNCTION` and a
desired timeout via `CURLMOPT_TIMERFUNCTION`; we mirror both into a single
epoll set (with a `timerfd`) or a kqueue (with a *chained* kqueue acting
as the timer). The hard-won invariant: **all registrations are
level-triggered, including the timer**, which is why kqueue uses a
chained kqueue rather than `EVFILT_TIMER` on the top-level mux — see the
long comment at oauth-curl.c:1458-1470 and `comb_multiplexer`.

### JSON parsing
`parse_oauth_json` (oauth-curl.c:870) drives `pg_parse_json` (the core
`common/jsonapi` SAX parser) through a table-driven field matcher
(`struct json_field`, oauth-curl.c:479). Per-document schemas:
`parse_provider` (957), `parse_device_authz` (1068), `parse_token_error`
(1122), `parse_access_token` (1182). The SAX callbacks
(`oauth_json_*`, oauth-curl.c:548-805) enforce: top-level must be an
object, no duplicate keys, depth ≤ `MAX_OAUTH_NESTING_LEVEL` (16), and
type-correctness per field. Hardening lives in `parse_oauth_json`:
explicit Content-Type check, embedded-NUL rejection, and an up-front
`pg_encoding_verifymbstr(PG_UTF8, …)` because `pg_parse_json` does **not**
validate UTF-8 itself (oauth-curl.c:889-897).

### HTTP plumbing
`setup_curl_handles` (oauth-curl.c:1754) configures the easy handle:
`CURLOPT_NOSIGNAL`, HTTPS-only via `CURLOPT_PROTOCOLS[_STR]`, optional
`CURLOPT_CAINFO` from `oauth_ca_file`, a suppressed `Accept:` header, and
(only under `PGOAUTHDEBUG`) `CURLOPT_VERBOSE` + a `debug_callback`.
`start_request`/`drive_request` (1915, 1970) run the request to
completion; `append_data` (1875) caps the response at
`MAX_OAUTH_RESPONSE_SIZE` (256 KiB). Request bodies are built with the
`x-www-form-urlencoded` helpers `append_urlencoded`/`build_urlencoded`
(2069, 2127), which also do the `%20`→`+` query-form fixup.

### Security gates worth knowing
- **Issuer match** — `check_issuer` (oauth-curl.c:2230) requires
  byte-exact `strcmp` between the configured `oauth_issuer` and the
  discovery document's `issuer` (RFC 9207 mix-up-attack defense; OIDC
  Discovery §4.3). No normalization.
- **HTTPS enforcement** — `check_for_device_flow` (oauth-curl.c:2275)
  rejects non-`https://` device-authz and token endpoints (unless
  `OAUTHDEBUG_UNSAFE_HTTP`).
- **Client auth** — `add_client_identification` (oauth-curl.c:2334): if
  an `oauth_client_secret` is set (zero-length is allowed!), it goes via
  HTTP Basic auth (`CURLOPT_USERNAME`/`PASSWORD`, both urlencoded per RFC
  6749 App. B), and `used_basic_auth` is recorded so a 401 can be blamed
  on a bad secret (`record_token_error`, oauth-curl.c:1150). Otherwise the
  `client_id` goes in the request body and auth is `CURLAUTH_NONE`.
- **Token scrubbing** — `pg_fe_cleanup_oauth_flow` (oauth-curl.c:355)
  `explicit_bzero`s libpq's copy of the token after libpq has duplicated
  it.

### Thread-safe global init
`initialize_curl` (oauth-curl.c:2689) calls `curl_global_init` exactly
once, guarded by the libpq threadlock when curl isn't known-threadsafe,
and double-checks `CURL_VERSION_THREADSAFE` at runtime to catch silent
downgrades between compile and run.

## Invariants & gotchas

- **`async_ctx.errctx` must point to static (translatable) storage** —
  it's never freed (oauth-curl.c:269). The three-part error is assembled
  in `append_actx_error` (oauth-curl.c:378) into `work_data`.
- **`work_data` is shared scratch** — both the response-body sink and the
  request-body builder reuse it; every `start_*` resets it first, and the
  comment at oauth-curl.c:244 warns not to stash anything across a call.
- **SIGPIPE is masked around the whole impl** (oauth-curl.c:3024) because
  `CURLOPT_NOSIGNAL` disables libcurl's own handling; uses the copied
  `pq_block_sigpipe`/`pq_reset_sigpipe` from [[oauth-utils.c]].
- **Zero-length client secret is meaningful** (oauth-curl.c:2344) — a
  present-but-empty secret still triggers Basic auth; only a NULL secret
  takes the body path.
- **`slow_down` permanently bumps the poll interval by 5 s**
  (oauth-curl.c:2621), with an explicit overflow check — the only two
  tolerated token-endpoint errors are `authorization_pending` and
  `slow_down` (oauth-curl.c:2610).
- **`grant_types_supported` is deliberately *not* required to contain
  `device_code`** (oauth-curl.c:2291) — MS Entra omits it, so the only
  hard requirement is a `device_authorization_endpoint`.
- **`pg_parse_json` does not validate UTF-8** — callers must pre-verify
  (oauth-curl.c:889); forgetting this elsewhere would be a latent bug.

## Cross-refs

- [[oauth-curl.h]] — the one exported prototype.
- [[oauth-utils.c]] / [[oauth-utils.h]] — the glue that lets this file
  build without `libpq-int.h` in the dynamic-library configuration.
- [[test-oauth-curl.c]] — `#include`s this file to unit-test the static
  multiplexer/timer helpers.
- [[fe-auth-oauth.c]] (in `src/interfaces/libpq/`) — the SASL-layer
  caller that selects this module and consumes the token.
- `knowledge/files/src/common/jsonapi.c.md` — the SAX JSON engine driven
  here (if present in corpus).
- `knowledge/issues/libpq-oauth.md` — issue register for this directory.

## Potential issues

- **[ISSUE-correctness: JSON number parse via `sscanf("%lf")` is
  LC_NUMERIC-dependent]** `oauth-curl.c:998` — `parse_json_number` parses
  the lexer-validated `interval`/`expires_in` numbers with
  `sscanf(s, "%lf", …)`. `%lf` honors the active `LC_NUMERIC` decimal
  separator, but JSON numbers always use `.`. A libpq application running
  under a comma-decimal locale (e.g. `de_DE`) could have `"5.5"` parsed as
  `5`, silently truncating. Impact is low (the values feed polling cadence
  / a prompt hint, and `parse_interval` clamps anyway), but it's a genuine
  locale-correctness gap. Mirrored in the register.
- **[ISSUE-leak: client secret freed without scrubbing]**
  `oauth-curl.c:344-347` (and the urlencoded copies at
  `oauth-curl.c:2402-2403`) — the access *token* is `explicit_bzero`'d on
  cleanup (oauth-curl.c:368), but `actx->client_secret` and the
  `username`/`password` urlencoded duplicates are released with plain
  `free()`, leaving the credential in freed heap. Partial mitigation only,
  since `CURLOPT_PASSWORD` already hands a copy to libcurl, but the
  asymmetry with the token path is worth a look. Severity `maybe`.
- **[ISSUE-undocumented-invariant: client_id/secret assumed 7-bit ASCII
  but unenforced]** `oauth-curl.c:2363-2366` — the code skips RFC 6749
  Appendix B's UTF-8 pre-encoding step on the documented assumption that
  client id/secret are 7-bit ASCII (App. A), but nothing validates the
  conninfo-supplied values. A non-ASCII secret would be percent-encoded
  byte-wise without normalization and could mismatch the provider.
  Severity `nit`.
