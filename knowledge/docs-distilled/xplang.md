---
source_url: https://www.postgresql.org/docs/current/xplang.html
also_fetched:
  - https://www.postgresql.org/docs/current/xplang-install.html
fetched_at: 2026-06-18T20:47:00Z
anchor_sha: ab3023ad1e68
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Procedural Languages — the SQL-registration side (ch. 40 / 40.1)

The SQL-level half of "how a PL exists": `CREATE EXTENSION` / `CREATE LANGUAGE`,
the handler/inline/validator function trio, and the trusted-vs-untrusted access
rule. The C-handler-authoring half is `plhandler.md`. Pairs with the
`extension-development` and `fmgr-and-spi` skills.

## Non-obvious claims

- **The server has zero built-in knowledge of a PL's source text.** For a PL
  function, parsing/execution is handed entirely to a *call handler* — itself a C
  function compiled into a shared object and loaded on demand, exactly like any
  other C function. The handler may interpret the body itself or glue to an
  existing language runtime. [from-docs]
- **A PL is installed per database**, not per cluster. A language installed into
  `template1` is automatically available in every database created afterward;
  others must be added to each database explicitly. [from-docs]
- **Preferred install is `CREATE EXTENSION langname`** for the four bundled PLs;
  the manual `CREATE FUNCTION ... LANGUAGE C` + `CREATE LANGUAGE` path is for
  languages not packaged as extensions and is superuser-only. (Modern PG dropped
  the old `pg_pltemplate` shortcut in favor of extensions.) [from-docs/inferred]
- **Three support functions, one required:**
  - **call handler** — `RETURNS language_handler`, takes *no* declared args; the
    `language_handler` pseudo-type marks it as not directly SQL-callable.
    **Required.** [from-docs]
  - **inline handler** — `(internal) RETURNS void`; needed only to support `DO`
    anonymous blocks. Optional. [from-docs]
  - **validator** — `(oid) RETURNS void`, `LANGUAGE C STRICT`; invoked by
    `CREATE FUNCTION` to check a new function's definition at creation time.
    Optional. [from-docs]
- **Registration:** `CREATE [TRUSTED] LANGUAGE name HANDLER h [INLINE i]
  [VALIDATOR v];` — populates the `pg_language` catalog. [from-docs]
- **Trusted vs untrusted is an access-control gate, set by the `TRUSTED`
  keyword:**
  - **Trusted** (PL/pgSQL, PL/Tcl, PL/Perl): grants no access a user couldn't
    already get, so **any database user may create functions** in it. [from-docs]
  - **Untrusted** (PL/TclU, PL/PerlU, PL/PythonU): unlimited access to internals
    / filesystem, must **not** be marked `TRUSTED`, and **only superusers may
    create functions** in it. [from-docs]
- **Four standard PLs ship in the distribution:** PL/pgSQL (ch. 41), PL/Tcl
  (42), PL/Perl (43), PL/Python (44). Only **PL/pgSQL is installed in every
  database by default**; the others build their handlers if their language
  support was configured but are not installed until requested. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/plhandler.md]] — §57 the C side: writing the call
  handler / inline handler / validator.
- [[knowledge/docs-distilled/xfunc-internal.md]] — `LANGUAGE internal` builtins,
  a sibling of the LANGUAGE C handler path.
- [[knowledge/files/src/include/catalog/pg_language.h.md]] — the `pg_language`
  catalog row this registration writes.
- [[knowledge/files/src/pl/plpgsql/src/pl_handler.md]] — the canonical trusted
  call-handler implementation.
- [[knowledge/files/src/pl/plpgsql/src/pl_comp.md]] / [[knowledge/files/src/pl/plpgsql/src/pl_exec.md]]
  — what the handler dispatches into for PL/pgSQL.

## Open questions

- The §40.1 default-installation table is version-sensitive (which handlers are
  built when `--with-perl`/`--with-tcl`/`--with-python` are set); re-confirm the
  PG18 defaults on a future pass.
