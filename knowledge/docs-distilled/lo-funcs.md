---
source_url: https://www.postgresql.org/docs/current/lo-funcs.html
chapter: "35.4 Large Objects: Server-Side Functions (lo-funcs)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# Large object server-side functions — lo-funcs

The SQL-callable `lo_*` / `loread` / `lowrite` functions implemented in
`src/backend/libpq/be-fsstubs.c` — the *server* half of Chapter 35, callable
directly from SQL/PL without a libpq client. They fall in two groups: (1) SQL
twins of the client fast-path calls (§35.3,
`[[knowledge/docs-distilled/lo-interfaces.md]]`), and (2) three SQL-only whole-
object convenience functions (`lo_from_bytea`, `lo_get`, `lo_put`).

## Non-obvious claims

- **The server functions are named `be_lo_*` in C but registered as `lo_*` in
  `pg_proc`.** Every client fast-path OID resolves to one of these
  [verified-by-code be-fsstubs.c: be_lo_open :87, be_lo_close :126, be_lo_creat
  :249, be_lo_create :262, be_lo_lseek :206, be_lo_lseek64 :231, be_lo_tell
  :275, be_lo_tell64 :298, be_lo_unlink :314, be_lo_import :403,
  be_lo_import_with_oid :415, be_lo_export :486, be_lo_truncate :580,
  be_lo_truncate64 :592]. Same engine, two front doors (SQL vs fast-path).
- **`loread` / `lowrite` drop the underscore** — the SQL analogs of client
  `lo_read`/`lo_write` are spelled `loread(fd, len)` and `lowrite(fd, bytea)`
  [verified-by-code be-fsstubs.c: be_loread :362, be_lowrite :380]. The
  underscore-less spelling is a historical quirk, not a typo.
- **Three SQL-only whole-object convenience functions have no client twin:**
  - `lo_from_bytea(loid, data) → oid` — create an LO from a `bytea` in one call
    (0 → server picks the OID) [verified-by-code be_lo_from_bytea :833].
  - `lo_get(loid [, offset, length]) → bytea` — read the whole object, or a
    byte range; the range form is `be_lo_get_fragment` [verified-by-code
    be_lo_get :798, be_lo_get_fragment :812].
  - `lo_put(loid, offset, data) → void` — write `data` at `offset`, **enlarging
    the LO if needed** [verified-by-code be_lo_put :856].
  These let PL/SQL manipulate whole small-to-medium LOs without the
  open/seek/read/close descriptor dance.
- **Server-side `lo_import`/`lo_export` read/write the *server's* filesystem
  with the *database server's* OS permissions — superuser-only by default.**
  The docs warn this privilege is effectively superuser-equivalent: "A
  malicious user of such privileges could easily parlay them into becoming
  superuser (for example by rewriting server configuration files)… Access to
  roles having such privilege must therefore be guarded just as carefully as
  access to superuser roles." [from-docs] Contrast the *client* `lo_import`/
  `lo_export` in §35.3, which touch the client machine.
- **Per-object GRANT privileges still apply, gated by `lo_compat_privileges`.**
  `SELECT` to read, `UPDATE` to write/truncate; owner-or-superuser to unlink
  [from-docs, and the `lo_compat_privileges` bypass at be-fsstubs.c:330]. This
  is the same permission model documented in §35.5.
- **`lo_get`'s range form is offset+length, 0-based.** `lo_get(24528, 0, 3)`
  returns the first 3 bytes. [from-docs]
- **All the descriptor-style server functions (`lo_open`, `loread`, `lowrite`,
  `lo_lseek`, `lo_tell`, `lo_close`, `lo_truncate`) share the client
  transaction-scope rule** — an fd opened by SQL `lo_open` is only valid within
  the current transaction. [from-docs] (Same `inv_api.c` fd table underneath.)

## Server function inventory (SQL name → C entry)

| SQL function | C entry (be-fsstubs.c) | Client twin? |
|---|---|---|
| `lo_creat(int)` | `be_lo_creat` :249 | yes |
| `lo_create(oid)` | `be_lo_create` :262 | yes |
| `lo_open(oid,int)` | `be_lo_open` :87 | yes |
| `loread(int,int)` | `be_loread` :362 | `lo_read` |
| `lowrite(int,bytea)` | `be_lowrite` :380 | `lo_write` |
| `lo_lseek` / `lo_lseek64` | `be_lo_lseek` :206 / :231 | yes |
| `lo_tell` / `lo_tell64` | `be_lo_tell` :275 / :298 | yes |
| `lo_truncate` / `lo_truncate64` | `be_lo_truncate` :580 / :592 | yes |
| `lo_close(int)` | `be_lo_close` :126 | yes |
| `lo_unlink(oid)` | `be_lo_unlink` :314 | yes |
| `lo_import(text[,oid])` | `be_lo_import` :403 / `be_lo_import_with_oid` :415 | *server-fs* |
| `lo_export(oid,text)` | `be_lo_export` :486 | *server-fs* |
| `lo_from_bytea(oid,bytea)` | `be_lo_from_bytea` :833 | — SQL only |
| `lo_get(oid[,bigint,int])` | `be_lo_get` :798 / `be_lo_get_fragment` :812 | — SQL only |
| `lo_put(oid,bigint,bytea)` | `be_lo_put` :856 | — SQL only |

## Links into corpus

- `[[knowledge/docs-distilled/lo-interfaces.md]]` — §35.3, the client-side
  fast-path twins whose OIDs resolve to these `be_lo_*` entries.
- `[[knowledge/docs-distilled/lo-implementation.md]]` — §35.5, the shared
  `inv_api.c` / `pg_largeobject` storage below both front doors.
- Skill `fmgr-and-spi` — `be_lo_*` are ordinary `PG_FUNCTION_ARGS` builtins;
  `row-level-security` / catalog `pg_largeobject_metadata` for the per-object
  GRANT model.

## Verification note

C entry points verified against `src/backend/libpq/be-fsstubs.c` @ `d774576f6f0`
(function line anchors above). The superuser-equivalence warning, GRANT model,
and `lo_get`/`lo_put` byte-range semantics are [from-docs]. `lo_compat_privileges`
gate at be-fsstubs.c:330.
