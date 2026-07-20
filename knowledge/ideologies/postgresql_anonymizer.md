# postgresql_anonymizer (`anon`) — masking policy as a SECURITY LABEL provider

- **Repo:** gitlab.com/dalibo/postgresql_anonymizer (canonical home is
  **GitLab**, not GitHub — raw fetch path is
  `https://gitlab.com/dalibo/postgresql_anonymizer/-/raw/<ref>/<path>`;
  this unblocked the long-standing `[pending]` TODO where GitHub raw 404'd
  all branches).
- **Version examined:** `master`, default_version `1.3.3`
  (`anon.control:3`).
- **Fetched:** `README.md`, `anon.control`, `META.json`, `anon.c` (1267 lines),
  `anon.sql` (3048 lines, library body — skimmed, not line-cited).

## Domain & purpose

Declarative **data masking / anonymization**. Instead of an external ETL
scrubber, `anon` keeps the masking *rules* inside the database schema and
applies them at query, dump, or in-place-rewrite time. The rules are written
as `SECURITY LABEL` statements (`README.md:51-65`):

```sql
SECURITY LABEL FOR anon ON COLUMN player.name
  IS 'MASKED WITH FUNCTION anon.fake_last_name()';
SECURITY LABEL FOR anon ON ROLE skynet IS 'MASKED';
```

Three application modes: **static masking** (`anonymize_database()` destroys
PII in place), **dynamic masking** (masked roles see fake data via a shadow
view schema), and **anonymous dumps** (`pg_dump_anon`). The masking-function
library (fake names, partial scrambling, noise, shuffling, k-anonymity) is
~3000 lines of PL/pgSQL/SQL in `anon.sql` built on top of `pgcrypto`.

## How it hooks into PG

The `anon` shared library is a thin C layer whose real job is to **register a
security-label provider** — the same core API `sepgsql` uses
([[knowledge/subsystems/contrib-sepgsql]]). `_PG_init` (`anon.c:305`):

1. Declares ~10 GUCs via `DefineCustom*Variable` (`anon.c:312-450`) — salt,
   algorithm, `strict_mode`, `privacy_by_default`,
   `transparent_dynamic_masking`, and a `masking_policies` list.
2. **Registers one label provider per masking policy** plus a second provider
   for k-anonymity (`anon.c:452-470`):
   ```c
   register_label_provider(guc_anon_k_anonymity_provider,
                           pa_k_anonymity_object_relabel);
   ...
   register_label_provider(policy, pa_masking_policy_object_relabel);
   ```
3. Installs `post_parse_analyze_hook` and `ProcessUtility_hook`
   (`anon.c:471-477`).

The relabel callback `pa_masking_policy_object_relabel` (`anon.c:153`) is where
the label *grammar* is validated: it switches on `object->classId` and does
prefix matching on the label string — `MASKED WITH FUNCTION` (`:200`),
`MASKED WITH VALUE` (`:211`), `NOT MASKED` (`:221`), `TABLESAMPLE …` on a table
or database (`:164`,`:180`), `MASKED` on a role (`:232`), `TRUSTED` on a schema
(`:245`, superuser-only). Anything else `ereport(ERROR)`s. So the "masking DDL"
is really just free-text security labels whose syntax is enforced entirely in
this one C callback — no bespoke parser, no new catalog.

Masking values are produced by `pa_masking_value_for_att` (`anon.c:1090`):
`GetSecurityLabel(&columnobject, policy)` looks up the column's label, strips
the `MASKED WITH FUNCTION`/`VALUE` prefix, and (in `strict_mode`) casts the
expression to the column's `atttypid` via `pa_cast_as_regtype` (`:1111`). For
static masking / COPY this is stitched into a `SELECT <expr…> FROM sch.tbl`
string that is re-parsed with `pg_parse_query` (`pa_masking_stmt_for_table`,
`anon.c:855`).

## Where it diverges from core idioms

- **Security label as a rule DSL, not a security model.** `sepgsql` uses
  labels to attach SELinux security contexts consulted by an access-control
  hook; `anon` repurposes the exact same provider API to store a *masking
  expression grammar* in `pg_seclabel`. The relabel callback becomes a
  hand-rolled DDL validator (`anon.c:153-262`). This is a genuinely unusual
  second use of the label-provider extension point — contrast
  [[knowledge/ideologies/pgsodium]] and [[knowledge/ideologies/vault]], which
  also touch column-level protection but via TCE/transparent-column-encryption
  and a key catalog rather than labels.
- **Raw `malloc` in the backend.** The relabel and value paths use bare
  `malloc(strnlen(...))` (`anon.c:200,211,1108`), not `palloc`
  in a memory context. These allocations are never freed and bypass PG's
  context-reset cleanup — a direct departure from
  [[knowledge/idioms/memory-contexts]]. (The copies are small and per-DDL /
  per-column, so the leak is bounded, but it is still off-idiom.)
- **Masking by SQL string re-parse.** Rather than building a rewritten
  `Query` node tree, `anon` assembles a `SELECT` text and re-runs the parser
  (`pa_masking_stmt_for_table`, `anon.c:855`). Column and relation names are
  guarded with `quote_identifier`, but the masking *expression* is the
  label text verbatim, so trust is pushed onto the `TRUSTED`-schema check
  (`pa_is_trusted_namespace`) and the superuser-only relabel of schemas.
- **The "transparent" SELECT engine is a stub.** `guc_anon_transparent_dynamic_masking`
  gates a `pa_rewrite(query, policy)` call in the post-parse-analyze hook
  (`anon.c:951-955`), but `pa_rewrite` is an **empty function** — the body is
  commented `NOT IMPLEMENTED YET` (`anon.c:1023-1034`). The shipped dynamic
  masking therefore does **not** work by query-tree rewriting; it works by the
  PL/pgSQL side (`start_dynamic_masking()` in `anon.sql`) building a shadow
  schema of masking **views** that masked roles' `search_path` resolves to.
  Only the **COPY** path is genuinely rewritten in C.

## Notable design decisions

- **COPY interception for dumps.** `pa_ProcessUtility_hook` (`anon.c:120`)
  checks `pa_get_masking_policy(GetUserId())`; for a masked role it calls
  `pa_rewrite_utility` (`anon.c:1041`), which for `COPY tbl TO` nulls out
  `copystmt->relation`/`attlist` and swaps in `copystmt->query =
  pa_masking_stmt_for_table(relid, policy)` (`anon.c:1063-1075`). A masked role
  running `COPY` thus silently exports masked columns — the mechanism behind
  `pg_dump_anon`. The same hook hard-errors `EXPLAIN` and `TRUNCATE` for masked
  roles with *"Masked roles are read-only"* (`anon.c:1050-1058`).
- **Role→policy resolution is single-level.** `pa_get_masking_policy`
  (`anon.c:810`) checks the role's own label but the parent-role walk is
  commented out (`anon.c:817-823`) — a masked role's inherited group
  memberships are **not** consulted, an intentional-looking but easily-missed
  limitation.
- **`init()` can't run in `_PG_init`.** Marking the `anon`/`pg_catalog`
  schemas `TRUSTED` for each policy is done in the SQL-callable `anon_init`
  (`anon.c:497+`), with a comment that "for some reasons this can't be done in
  `_PG_init()`" (`anon.c:492`) — the catalog isn't writable that early in
  startup.
- **k-anonymity as a separate provider.** `pa_k_anonymity_object_relabel`
  (`anon.c:271`) accepts only `QUASI IDENTIFIER` / `INDIRECT IDENTIFIER`
  labels on columns; the actual k computation lives in `anon.sql`.

## Links into corpus

- [[knowledge/subsystems/contrib-sepgsql]] — core's canonical
  `register_label_provider` user; the API `anon` reuses for a different purpose.
- [[knowledge/idioms/memory-contexts]] — the `malloc` departure above.
- [[knowledge/idioms/guc-variables]] — the `DefineCustom*Variable` +
  check/assign-hook pattern (`pa_check_masking_policies`, `anon.c:90`).
- [[knowledge/subsystems/contrib-pgcrypto]] — the crypto primitives the
  `anon.sql` faking/hashing library is built on.
- [[knowledge/ideologies/pgsodium]], [[knowledge/ideologies/vault]] —
  sibling "protect column data" extensions with a keep-the-key-out-of-SQL
  posture, contrasting with `anon`'s label-as-rule approach.
- [[knowledge/ideologies/supautils]], [[knowledge/ideologies/pgddl]] — other
  extensions that lean on `ProcessUtility_hook` to police / rewrite DDL/utility.

## Sources

- `https://gitlab.com/dalibo/postgresql_anonymizer/-/raw/master/README.md`
- `https://gitlab.com/dalibo/postgresql_anonymizer/-/raw/master/anon.control`
- `https://gitlab.com/dalibo/postgresql_anonymizer/-/raw/master/anon.c`
- `https://gitlab.com/dalibo/postgresql_anonymizer/-/raw/master/META.json`
- `anon.sql` (3048 lines) fetched and skimmed for the SQL-side dynamic-masking
  view engine; not line-cited here (the C surface is the divergence story).

Confidence: hooks/registration/relabel-grammar/COPY-rewrite are
`[verified-by-code]` against `anon.c`; the shadow-view dynamic-masking
mechanism is `[from-README]` + `[inferred]` from the `pa_rewrite` stub.
