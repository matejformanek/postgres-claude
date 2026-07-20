# pgjwt — a JSON Web Token sign/verify protocol implemented entirely in SQL/PL-pgSQL over pgcrypto, with zero C

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `michelp/pgjwt` @ branch `master`. All `file:line` cites below point
> into that repo (raw.githubusercontent.com), not `source/`, since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against the files fetched on 2026-07-19 (see Sources footer).
> `pgjwt--0.2.0.sql` is authoritative; `pgjwt--0.1.1.sql` is read only for the
> version diff.

## Domain & purpose

pgjwt is a "PostgreSQL implementation of JSON Web Tokens" (`README.md:1-2`)
`[from-README]`. It implements the two HMAC-signed-JWT operations — `sign()` a
JSON payload into a compact `header.payload.signature` token, and `verify()` a
token back into `(header, payload, valid)` — as **six SQL/PL-pgSQL functions and
nothing else**. The entire install script is 80 lines (`pgjwt--0.2.0.sql`), it
ships no `.so`, and it leans on `pgcrypto`'s `hmac()` for the actual keyed hash.
It is the corpus's cleanest example of a **cryptographic wire protocol
implemented as ordinary SQL functions** — the opposite pole from
`[[pgsodium]]`/`[[vault]]`, which push crypto down into C/libsodium precisely to
keep key material out of the SQL surface.

## How it hooks into PG

There are no hooks. pgjwt is a pure relocatable-`false`, non-superuser SQL
extension:

- **Control file**: `default_version = '0.2.0'`, `relocatable = false`,
  `superuser = false`, and crucially `requires = pgcrypto`
  (`pgjwt.control:1-6`) `[verified-by-code]`. The `requires` is the whole
  dependency story — pgjwt needs `pgcrypto` in the search path because
  `algorithm_sign` calls `@extschema@.hmac(...)` (`pgjwt--0.2.0.sql:30`),
  resolved to pgcrypto's `hmac(text, text, text)`.
- **Build**: plain PGXS, `EXTENSION = pgjwt`, DATA lists the base script plus
  two migration scripts (`Makefile:1-3`) `[verified-by-code]`. No `MODULE_big`,
  no `SHLIB_LINK` — nothing compiles.
- **Everything is SQL**: `url_encode`/`url_decode` (base64url), `algorithm_sign`
  (HMAC dispatch), `sign`, `try_cast_double` (the only PL/pgSQL function), and
  `verify` (`pgjwt--0.2.0.sql:4-80`) `[verified-by-code]`. All object references
  are schema-qualified with `@extschema@.` so the functions work wherever the
  extension is installed.

## Where it diverges from core idioms

### 1. Signature verification uses a plain `=`, not a constant-time compare

This is the security-load-bearing divergence. `verify` recomputes the signature
over `header.payload` and checks it against the token's third segment with SQL
equality:

```
r[3] = @extschema@.algorithm_sign(r[1] || '.' || r[2], secret, algorithm) AS signature_ok
```

(`pgjwt--0.2.0.sql:77`) `[verified-by-code]`. `=` on `text` is `texteq`, a
`memcmp`-style comparison that **short-circuits on the first differing byte** —
its runtime is data-dependent. JWT/HMAC verification is the canonical place
where the literature demands a *constant-time* comparison (e.g.
`hmac_equal`/`crypto_verify`) to deny an attacker a timing oracle on the
expected MAC. pgjwt has no such guard — and none is easily reachable from pure
SQL, since PL/pgSQL has no timing-safe string compare. `[verified-by-code]`:
this is a plain equality, flagged as a divergence from crypto best practice.
(In practice HMAC's second-preimage resistance makes the classic byte-by-byte
forgery attack hard, but "we rely on the MAC being unforgeable" is not the same
guarantee as "the compare leaks no timing" — the divergence stands.) Contrast
`[[pgsodium]]`/`[[vault]]`, which route comparisons through libsodium's
constant-time primitives.

### 2. The secret is a plain function argument — it lands in logs and pg_stat_statements

`sign(payload, secret, algorithm)` and `verify(token, secret, algorithm)` take
the HMAC secret as an ordinary `text` parameter (`pgjwt--0.2.0.sql:34,64`)
`[verified-by-code]`. Because the secret travels *in the query text*, it is
exposed anywhere query text is captured: `log_statement = 'all'` /
`log_min_duration_statement` server logs, `pg_stat_activity.query`,
`pg_stat_statements` (until normalized — and a literal secret is a constant that
normalization may or may not squash), `EXPLAIN` output, and `.psql_history`.
This is the mirror image of the `[[pgsodium]]`/`[[vault]]` posture, whose entire
C layer exists to keep the root key *out* of any SQL-visible surface. pgjwt
makes the opposite trade: zero C, maximum simplicity, secret-in-the-clear on the
wire into the backend. `[inferred]` from the argument signature — the leakage is
a property of passing secrets as SQL literals, not something pgjwt narrates.

### 3. `verify` is marked `IMMUTABLE` but reads `CURRENT_TIMESTAMP` — a volatility bug the 0.2.0 rewrite introduced

Every function is tagged `IMMUTABLE` (`pgjwt--0.2.0.sql:6,18,31,49,61,80`)
`[verified-by-code]`. For the pure functions (`url_encode`, `url_decode`,
`algorithm_sign`, `sign`, `try_cast_double`) that is correct — same inputs,
same output. But `verify` in 0.2.0 gained an expiry/not-before check that reads
the clock:

```
jwt.signature_ok AND tstzrange(
  to_timestamp(@extschema@.try_cast_double(jwt.payload->>'nbf')),
  to_timestamp(@extschema@.try_cast_double(jwt.payload->>'exp'))
) @> CURRENT_TIMESTAMP AS valid
```

(`pgjwt--0.2.0.sql:69-72`) `[verified-by-code]`. A function whose result depends
on `CURRENT_TIMESTAMP` is at most `STABLE`, never `IMMUTABLE` — core's contract
is that an `IMMUTABLE` function may be constant-folded at plan time and its
result cached across rows/executions. So a plan that inlines or folds a
`verify(...)` call could pin `valid` to the planning-time clock, making an
expired token read `valid = true` (or vice-versa) within a long-lived cached
plan. This is a genuine mismarking, and it is a *regression the version bump
created*: in 0.1.1 `verify` did no time comparison, so `IMMUTABLE` was correct
there (`pgjwt--0.1.1.sql:52-59`) `[verified-by-code]`. The `exp`/`nbf` feature
was bolted onto the query without downgrading the volatility label. See the
`guc-variables`/`plan-cache` idioms for why the planner trusts the label.

### 4. base64url is hand-rolled from `encode('base64')` + `translate`

JWT requires base64url (`-_` alphabet, no `=` padding, no line breaks), but
pgcrypto/`encode` only give standard base64. pgjwt bridges the two with
`translate`:

- **encode** (`pgjwt--0.2.0.sql:5`): `translate(encode(data,'base64'),
  E'+/=\n', '-_')` — a 4-source / 2-target `translate`, so `+`→`-`, `/`→`_`, and
  both `=` and newline map to *nothing* (deleted, since they have no
  corresponding target char). One expression does alphabet-swap, de-padding, and
  de-chunking. `[verified-by-code]`
- **decode** (`pgjwt--0.2.0.sql:9-18`): `translate(data, '-_', '+/')` to restore
  the standard alphabet, then re-append `=` padding computed from
  `length % 4` before `decode(..., 'base64')`. `[verified-by-code]`

## Notable design decisions (cited)

- **HMAC algorithm dispatch via a `CASE` producing a pgcrypto digest name**
  (`pgjwt--0.2.0.sql:24-30`): `HS256/384/512` → `sha256/384/512`; anything else
  yields `''`, which pgcrypto's `hmac` rejects with an error — the comment
  `-- hmac throws error` (`:29`) shows this is the intended "reject unknown alg"
  path rather than silent failure. `[verified-by-code]`
- **`sign` builds the JWT by string concat, not a JSON library**
  (`pgjwt--0.2.0.sql:37-48`): the header is the *literal string*
  `'{"alg":"' || algorithm || '","typ":"JWT"}'` (`:38`), base64url'd; the
  payload is `payload::text` base64url'd (`:41`); the token is
  `signables || '.' || algorithm_sign(signables, ...)` (`:46-48`).
  `[verified-by-code]`
- **`try_cast_double` is the only PL/pgSQL** (`pgjwt--0.2.0.sql:52-61`): a
  `BEGIN … EXCEPTION WHEN OTHERS THEN RETURN NULL` wrapper so a missing or
  non-numeric `exp`/`nbf` claim becomes `NULL` (→ an unbounded `tstzrange`
  endpoint) instead of raising. This is the classic "cast-or-null" idiom
  (cf. core has no such builtin). `[verified-by-code]`
- **Token split via `regexp_split_to_array(token, '\.')`**
  (`pgjwt--0.2.0.sql:78`): the three dot-separated segments become `r[1]`
  (header), `r[2]` (payload), `r[3]` (signature). A malformed token with the
  wrong number of segments simply yields NULLs / a false `signature_ok` rather
  than a structured error. `[verified-by-code]`
- **Version diff 0.1.1 → 0.2.0**: 0.2.0 adds `try_cast_double` and rewrites
  `verify` from a flat "signature matches?" (`pgjwt--0.1.1.sql:52-59`) into a
  subquery that also enforces the `nbf`/`exp` window via `tstzrange @>
  CURRENT_TIMESTAMP` (`pgjwt--0.2.0.sql:64-80`). `url_encode`, `url_decode`,
  `algorithm_sign`, and `sign` are byte-identical between the two versions. The
  0.2.0 `verify` kept the `IMMUTABLE` label from 0.1.1 despite now reading the
  clock (§3). `[verified-by-code]`

## Links into corpus

- `[[pgsodium]]` — the crypto-in-C counterpole: pgsodium/libsodium exist to keep
  keys out of SQL and to compare in constant time; pgjwt does crypto *in* SQL
  and compares with `=` (§1) and passes the secret as an argument (§2).
- `[[vault]]` — same "secret must not be SQL-visible" ideology as pgsodium;
  contrast pgjwt's secret-as-parameter posture directly.
- `[[pgsql-http]]` / `[[pg_net]]` — the JWT-for-auth story: pgjwt is the token
  half of the PostgREST-style "sign a JWT in the database, verify it on the way
  in" pattern; these are the extensions that would carry such a token outbound.
- `[[credcheck]]` / `[[pgaudit]]` — the secret-leakage surface (§2): audit/log
  capture of query text is exactly where a `sign(payload, 'secret')` literal is
  exposed.
- `knowledge/idioms/guc-variables.md` / `knowledge/idioms/plan-cache.md` — why
  the mismarked `IMMUTABLE` on a clock-reading function (§3) is a correctness
  risk: the planner is entitled to constant-fold `IMMUTABLE` results.

## Sources

Fetched 2026-07-19 (branch `master`):

- `https://raw.githubusercontent.com/michelp/pgjwt/master/pgjwt--0.2.0.sql`
  → HTTP 200 (80 lines; all six functions deep-read — authoritative).
- `https://raw.githubusercontent.com/michelp/pgjwt/master/pgjwt--0.1.1.sql`
  → HTTP 200 (59 lines; read only for the 0.1.1→0.2.0 `verify` diff).
- `https://raw.githubusercontent.com/michelp/pgjwt/master/pgjwt.control`
  → HTTP 200 (6 lines; `requires = pgcrypto`, `superuser = false`).
- `https://raw.githubusercontent.com/michelp/pgjwt/master/Makefile`
  → HTTP 200 (7 lines; PGXS, no compiled module).
- `https://raw.githubusercontent.com/michelp/pgjwt/master/README.md`
  → HTTP 200 (usage examples, pgcrypto/pgtap dependency note, TODO listing
  public/private keys as not-yet-supported).

All structural cites (base64url `translate`, HMAC `CASE` dispatch, `sign`
concat, `verify` subquery + `tstzrange` expiry, plain-`=` signature compare, the
`IMMUTABLE` labels, the version diff) are `[verified-by-code]` against the
fetched `.sql`/`.control`/`Makefile`. The secret-in-logs leakage (§2) is
`[inferred]` from the argument signature, and the "JWT best practice demands
constant-time compare" framing is background, not narrated by this repo.
