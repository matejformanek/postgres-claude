# `src/backend/commands/explain_format.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~714
- **Source:** `source/src/backend/commands/explain_format.c`

PG18+ split out of `explain.c`: format-agnostic helpers for emitting
EXPLAIN output across the four supported formats (`text`, `xml`, `json`,
`yaml`). Every helper switches on `es->format` and emits the appropriate
shape. Open/Close group routines maintain `es->grouping_stack` so that
JSON arrays/objects get correct comma separators and YAML gets correct
"- " markers. [verified-by-code]

## API / entry points

- `ExplainPropertyList(qlabel, data, es)` — list of unlabeled C strings
  as a property of the current group. [verified-by-code]
- `ExplainPropertyListNested(qlabel, data, es)` — nested-list flavor;
  text/xml fall back to `ExplainPropertyList`. [verified-by-code]
- `ExplainPropertyText/Integer/UInteger/Float/Bool(qlabel, ...)` —
  type-specific wrappers around static `ExplainProperty`. Integer
  forms use `INT64_FORMAT`/`UINT64_FORMAT`; float uses `psprintf`
  with explicit `ndigits`. [verified-by-code]
- `ExplainOpenGroup` / `ExplainCloseGroup(objtype, labelname, labeled, es)`
  — start/end a JSON object or array (or YAML equivalent). `labeled`
  selects `{}` vs `[]` for JSON. [verified-by-code]
- `ExplainOpenSetAsideGroup` / `ExplainSaveGroup` / `ExplainRestoreGroup`
  — used when EXPLAIN needs to buffer subordinate output (e.g. for
  parallel-worker reordering) and then splice it in. `depth` parameter
  allows skipping intermediate nesting levels. [from-comment]
- `ExplainDummyGroup(objtype, labelname, es)` — emit an empty group
  (used when a node has nothing interesting). [verified-by-code]
- `ExplainBeginOutput` / `ExplainEndOutput(es)` — top-level
  start/end-of-output boilerplate; XML emits `<explain xmlns=...>`,
  JSON opens an array `[`, YAML pushes a 0 onto the stack.
  [verified-by-code]
- `ExplainSeparatePlans(es)` — blank line between multiple plans in
  text format; no-op in others. [verified-by-code]
- `ExplainIndentText(es)` — text-only; indents to `es->indent*2`
  unless current line already has data on it (cf. parallel workers).
  Asserts text format. [from-comment]

## Notable invariants / details

- `es->grouping_stack` is an integer list. Per format meaning:
  - JSON: 0 = nothing emitted at this level, 1 = at least one item
    emitted (so the next needs a leading comma). [from-comment]
  - YAML: 0 = nothing emitted AND this level is unlabeled and must be
    prefixed with `"- "`. [from-comment]
- `ExplainJSONLineEnding` (line 666) is what makes JSON commas
  correct: emit comma if `linitial_int != 0`, else flip to 1, then
  newline. The newline-before-property design is what allows the
  comma to be inserted at line-start. [from-comment]
- `ExplainYAMLLineStarting` (line 686) is analogous: first property
  rides on the same line as `"- "`, subsequent ones get newline +
  indent.
- XML tag-name sanitization (line 624): only `[A-Za-z0-9-_.]`
  allowed; everything else becomes `-`. So `"I/O Read Time"` →
  `"I-O-Read-Time"`. [from-comment]
- `escape_yaml(buf, str)` (line 711) is implemented as `escape_json`.
  The 5-line comment explains the YAML quoting rules are too
  complicated to do properly, so the code quotes everything (which is
  valid YAML). [from-comment]
- `ExplainOpenSetAsideGroup` has no `Close` counterpart on purpose —
  always paired with `ExplainSaveGroup`. [from-comment]

## Potential issues

- Lines 711-714. `escape_yaml` is one line wrapping `escape_json`;
  comment is 8 lines. Easy to skim past and assume YAML has
  format-specific escaping when it doesn't. [ISSUE-doc-drift: escape_yaml
  body vs comment mismatch (nit)]
- `ExplainProperty` and friends pass `numeric=true` for ints/floats/bools
  to skip JSON quoting; the `bool` path emits `"true"`/`"false"` —
  correct JSON literals — but if `numeric` were ever wrong the JSON
  output would be malformed. Defensive but coupled. [unverified]

## Synthesized by
<!-- backlinks:auto -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `commands`](../../../../issues/commands.md)
<!-- issues:auto:end -->
