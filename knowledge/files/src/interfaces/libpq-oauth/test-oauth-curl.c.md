---
path: src/interfaces/libpq-oauth/test-oauth-curl.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 527
depth: read
---

# `test-oauth-curl.c` — unit-test driver for the OAuth multiplexer/timer internals

## Purpose

A standalone TAP test that exercises the **static** internals of
[[oauth-curl.c]] — specifically the platform-specific multiplexer and
timer plumbing, which is the trickiest, least HTTP-dependent part of the
module. It does this the white-box way: `#include "oauth-curl.c"` at line
13, so it can call `setup_multiplexer`, `register_socket`, `set_timer`,
`timer_expired`, `drain_timer_events`, and `comb_multiplexer` directly.
The whole suite is gated on `USE_ASSERT_CHECKING`; without cassert it
prints `1..0 # skip`.

## Internal landmarks

- **Minimal TAP harness** — `ok()`/`ok_impl()` (line 28) and the
  `is()`/`is_diag()` integer-comparison macro (line 55), plus `num_tests`.
  Deliberately tiny so it has no dependency on Perl `Test::More`.
- `init_test_actx`/`free_test_actx` (lines 82, 101) — build a
  partially-initialized `async_ctx` with just a multiplexer + errbuf,
  using `OAUTHDEBUG_LEGACY_UNSAFE` debug flags.
- `fill_pipe`/`drain_pipe` (lines 120, 157) — saturate / empty a pipe to
  drive a socket between readable/writable states deterministically.
- `mux_is_ready`/`mux_is_not_ready` (lines 190, 200) — assert the
  multiplexer's readiness via `PQsocketPoll`. The comment at lines
  183-188 pins the load-bearing expectation that the mux is *readable*
  when libcurl's sockets are *writable* (`PGRES_POLLING_READING` is
  hardcoded throughout the real flow).
- `test_set_timer` (line 214) and `test_register_socket` (line 264) — the
  two suites. The latter runs twice (`CURL_POLL_IN`/`OUT` vs `INOUT`) and
  accounts for FreeBSD's bidirectional pipes by emulating unidirectional
  behavior with `fill_pipe`.

## Invariants & gotchas

- This file is **not** linked against a server; it talks only to local
  pipes and the epoll/kqueue mux. No network, no real curl request.
- Because it `#include`s the `.c`, any new `static` helper in
  oauth-curl.c is immediately reachable here — handy, but it also means a
  rename in oauth-curl.c can break the test build directly.
- Timeout comes from `PG_TEST_TIMEOUT_DEFAULT` (line 492), defaulting to
  180 s; the tests poll against an absolute deadline rather than spinning.

## Potential issues

- **[ISSUE-correctness: wrong fcntl command in `fill_pipe` cleanup
  (test-only)]** `test-oauth-curl.c:127-149` — `fill_pipe` saves the
  descriptor's *status* flags with `F_GETFL` (to set `O_NONBLOCK`), but
  restores them with `F_SETFD` (the *descriptor* flags command, which
  governs `FD_CLOEXEC`). `mode` therefore lands in the wrong fcntl
  namespace; e.g. a write-end fd (`O_WRONLY` == 1) would get `FD_CLOEXEC`
  set rather than `O_NONBLOCK` cleared. Harmless in practice (transient
  test pipes, closed shortly after), but it looks like a `F_SETFL`
  copy-paste slip. Severity `maybe`. Mirrored in the register.

## Cross-refs

- [[oauth-curl.c]] — the file under test (included wholesale).
- `knowledge/issues/libpq-oauth.md` — issue register.

<!-- issues:auto:begin -->
- [Issue register — `libpq-oauth`](../../../../issues/libpq-oauth.md)
<!-- issues:auto:end -->
