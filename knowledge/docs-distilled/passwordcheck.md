---
source_url: https://www.postgresql.org/docs/current/passwordcheck.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — passwordcheck (the check_password_hook example)

`contrib/passwordcheck` is the smallest non-trivial hook example in the tree: it
installs `check_password_hook` to reject weak passwords at `CREATE/ALTER ROLE`
time. Read it as the template for *any* role-policy hook — and as the canonical
illustration of why a cleartext-only hook is bypassable. `[from-docs]`

## The hook install (verified against source)

- Saves the prior hook then installs its own — the same chaining idiom as
  auto_explain: `prev_check_password_hook = check_password_hook;
  check_password_hook = check_password;` at
  `source/contrib/passwordcheck/passwordcheck.c:165-166`; the wrapper calls
  `prev_check_password_hook(...)` first (`:63-64`) so modules chain.
  `[verified-by-code]`
- Must be in `shared_preload_libraries` (server restart). A rejection
  `ereport(ERROR, ...)` aborts the `CREATE/ALTER ROLE`. `[from-docs]`

## Default checks (verified against source)

- Minimum length: GUC **`passwordcheck.min_password_length`**, default **8**
  bytes (`static int min_password_length = 8;` `passwordcheck.c:37`; defined via
  `DefineCustomIntVariable("passwordcheck.min_password_length", …)` `:152`).
  `[verified-by-code]` (Note: the GUC is real in current PG — older lore that
  the length is a hardcoded `#define MIN_PWD_LENGTH` is stale.)
- Also rejects passwords that contain the role name, and (in source) too-short
  passwords trigger the `errdetail` quoting the GUC name (`:100-105`).
  `[verified-by-code]`

## The load-bearing security caveat

- **Pre-hashed passwords defeat it.** Clients (incl. `psql` by default) send the
  password *already* MD5/SCRAM-encrypted. The hook then only sees the hash, not
  the cleartext, so length/content rules cannot apply — the check is trivially
  bypassed. The only robust fix is to *reject* pre-encrypted passwords, which
  forces cleartext transmission (its own risk). `[from-docs]`
- Shipped as a **template to customize and recompile** (e.g. CrackLib
  integration is two commented `Makefile` lines, off by default for licensing).
  Not recommended as a serious security control; external auth (GSSAPI) is
  preferred. `[from-docs]`

## Links into corpus

- `[[knowledge/docs-distilled/sasl-authentication.md]]` — why the server usually
  receives a SCRAM verifier, not cleartext (the root of the caveat).
- `[[knowledge/docs-distilled/auto-explain.md]]` — same save-prev/install/call-prev
  hook-chaining idiom on a different hook.
- Skills: `bgworker-and-extensions` (hook installation on `_PG_init`),
  `error-handling` (the rejection `ereport`), `gucs-config`.
