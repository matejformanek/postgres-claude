# src/include/commands/explain_format.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 59 [verified-by-code]

## Role

Format-agnostic output writers for EXPLAIN. Wraps the 4 output formats
(TEXT / XML / JSON / YAML) behind a `ExplainProperty*` API and a
group-open/close stack.

## Public API

- Property writers: `ExplainPropertyList`, `ExplainPropertyListNested`,
  `ExplainPropertyText`, `ExplainPropertyInteger`, `ExplainPropertyUInteger`,
  `ExplainPropertyFloat`, `ExplainPropertyBool` (`:21-35`).
- Grouping stack: `ExplainOpenGroup` / `ExplainCloseGroup`, plus
  `ExplainOpenSetAsideGroup` + `ExplainSaveGroup` / `ExplainRestoreGroup`
  used by parallel-worker output redirection (`:37-48`).
- Top-of-output: `ExplainBeginOutput`, `ExplainEndOutput`,
  `ExplainSeparatePlans` (`:53-55`).
- `ExplainIndentText` — TEXT-format hand-indent helper (`:57`).

## Invariants

- INV-EXPLAIN-FORMAT: opaque forward `typedef struct ExplainState
  ExplainState;` at line 19 — this header DOES NOT include `explain_state.h`,
  to avoid pulling in `parsenodes.h` everywhere. Extension callers
  needing field access must include `explain_state.h` themselves.
- `ExplainOpenGroup` / `Close` are stack-disciplined — every open must
  match a close at the same depth, else `ExplainEndOutput` will assert.
- `labeled` argument: false means anonymous (e.g. plan-array elements in JSON).

## Trust boundary / Phase D surface

- **A14 pg_overexplain echo.** Extension EXPLAIN options register through
  `explain_state.h` (`RegisterExtensionExplainOption`); the actual write
  path goes through THESE functions. A buggy extension can emit
  unescaped text via `ExplainPropertyText` (the writer escapes; the
  group-name does NOT — caller's responsibility).
- **A7 ruleutils security-clause loss echo.** EXPLAIN output for a view
  with `security_barrier`/RLS may leak the underlying qual via deparsed
  expressions in the Plan-node properties; that's a `ruleutils.c` /
  `show_plan_tlist` concern, NOT this header — but THIS header is the
  funnel everything goes through, so any sanitization gap shows up here.
- **JSON/YAML/XML escape gap risk.** If an extension passes a string
  containing the format's quote character into a `labelname` (not `value`),
  the output can be malformed JSON. Caller-side concern; this header
  doesn't document the contract.

## Cross-references

- `commands/explain_state.h` — `ExplainState` definition + extension
  registration API.
- `commands/explain.h` — top-level `ExplainQuery` entry.
- `backend/commands/explain_format.c` — implementations.

## Issues / drift

- `[ISSUE-DOC: header gives no escaping contract — caller's responsibility for labelname vs value is implicit (medium)] — source/src/include/commands/explain_format.h:21-48`
- `[ISSUE-TRUST: A7 echo — RLS qual deparsing path runs through these writers; header lacks "do not include secret-bearing strings" note (low)] — source/src/include/commands/explain_format.h:1-15`
