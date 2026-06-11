# Issues — `contrib/passwordcheck`

Per-subsystem issue register for **passwordcheck**, the 1-file
backend extension that installs `check_password_hook` to enforce
password policy. Created 2026-06-11 by A21 sweep.

**Parent doc:** `knowledge/files/contrib/passwordcheck/passwordcheck.c.md`

## Headlines

1. **Default policy is weak by design**. min_password_length = 8,
   "contains a letter AND a non-letter", rejects username substring.
   No history, no rate-limit, no proper dictionary check unless
   `USE_CRACKLIB` is compiled in (it usually isn't on packaged
   builds).

2. **Encrypted-password path can only check `username == password`**
   because the server sees just the hash. The README warns; the
   source briefly notes; many users miss this and assume "policy
   applied" means "policy applied to all paths".

3. **Letter+non-letter composition rejects high-entropy passphrases**
   like `correcthorsebatterystaple`. This is the textbook
   anti-pattern modern guidance (NIST 800-63B) explicitly counsels
   against.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:99-105 | security | maybe | Default min length 8 bytes; bytes-vs-chars discrepancy on UTF-8 | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:114-126 | correctness | nit | Letter+non-letter rule rejects long random-words passphrases | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:132-139 | security | likely | cracklib not compiled in default packaged builds → minimal policy | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:80-83 | doc-drift | nit | Encrypted-path "only checks user=pw" not in source comment block | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:78 | style | nit | logdetail diagnostic from plain_crypt_verify discarded | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:52-55 | undocumented-invariant | nit | validuntil_time/validuntil_null parameters are silently ignored | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |
| 2026-06-11 | contrib/passwordcheck/passwordcheck.c:108-111 | undocumented-invariant | nit | substring check on username is case-sensitive; matches PG role naming | open | knowledge/files/contrib/passwordcheck/passwordcheck.c.md §Potential issues |

## Notes

This extension is explicitly **sample / reference** code per the
upstream docs and the file's own comment block. Real deployments
should either harden it or replace it with an external IdP. The
upstream wiki has discussed deprecating it; nothing has landed.
