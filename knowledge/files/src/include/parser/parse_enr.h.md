# src/include/parser/parse_enr.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 22 [verified-by-code]

## Role

Parser hooks for **Ephemeral Named Relations (ENRs)** — short-lived,
in-memory tuplestores given a SQL name and visible only inside a
specific parse/exec context. Used for trigger transition tables
(`OLD TABLE` / `NEW TABLE` in `REFERENCING` clause) and CTE-like
references in some PL contexts.

## Public API

- `name_matches_visible_ENR(ParseState *pstate, const char *refname)
  -> bool` (`:19`) — relation-name lookup probe.
- `get_visible_ENR(ParseState *pstate, const char *refname) ->
  EphemeralNamedRelationMetadata` (`:20`) — fetch the registered
  ENR metadata (tupledesc + tuplestore handle).

## Invariants

- INV-ENR-SCOPE: ENRs live in the QueryEnvironment (`queryEnv` on
  ParseState); they are NOT in pg_class. Therefore catalog lookups
  miss them, and these hooks are consulted FIRST by parse-relation.
- INV-ENR-LIFETIME: an ENR is registered for a single query
  invocation (trigger fire, PL block); references after teardown
  are use-after-free unless metadata stores a copy of the
  tupledesc.
- INV-ENR-NAMESPACE: ENR names are flat — no schema-qualification.
  Conflict with a real relation of the same name in the search
  path is resolved per the existing precedence rules
  (verify in `parse_relation.c`).

## Notable internals

- The struct `EphemeralNamedRelationMetadata` is defined in
  `utils/queryenvironment.h`; it holds `name`, `reliddesc`,
  `enrtuples`, and an opaque `enrtype`.
- `parse_enr.c` is tiny — these two funcs delegate to
  `QueryEnvironment` lookups.

## Trust boundary / Phase D surface

- **A12 ruleutils echo / A15 echo.** ENR names appear in deparsed
  rule actions and EXPLAIN output. The deparser needs to know
  the ENR exists so it can produce qualifications that round-
  trip. A bug where deparse skips the ENR-qualification could
  cause a rule's serialized text to bind differently on replay.
- **A8 echo (NAME-vs-OID).** ENRs have NO OID. Trigger transition
  tables referenced by name in trigger action bodies are
  re-resolved at every fire by name lookup. A user renaming a
  conflicting real table mid-session could shift resolution
  silently.
- **Permission posture.** ENR access uses the ParseState's
  current role — same as regular table access. No separate ACL.

## Cross-references

- `utils/queryenvironment.h` — ENR metadata structs and the
  `QueryEnvironment` container.
- `parser/parse_relation.h` — `parserOpenTable` and friends
  call into here first.
- `commands/trigger.h` — registers transition tables before
  firing.
- `parser/parse_clause.h` — TABLE function argument resolution.

## Issues / drift

- `[ISSUE-DOC: header lists 2 funcs, zero context — first-time reader can't tell what an ENR is from this file alone (medium)] — source/src/include/parser/parse_enr.h:14-22`
- `[ISSUE-TRUST: A8 echo — ENR vs real-table name collision precedence not commented; relies on parse_relation.c implementation (low)] — source/src/include/parser/parse_enr.h:19-20`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
