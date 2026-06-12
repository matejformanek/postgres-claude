---
source_url: https://www.postgresql.org/docs/current/error-style-guide.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §56.3: Error Message Style Guide

The upstream rules for *wording* an `ereport` message — the ones a committer will
bounce a patch over. Direct companion to the `error-handling` skill (which covers
the *mechanics*: `ereport`, SQLSTATE, `PG_TRY`). This page is the prose contract.

## Primary / Detail / Hint — the three-part split [from-docs]

- **Primary message**: short, factual, fits one line, **no implementation
  details**. Keep it brief by pushing specifics to detail/hint.
- **Detail**: implementation specifics (the syscall that failed, etc.); factual.
- **Hint**: a *suggestion* for fixing it — advice that might not always apply.

Canonical rewrite from the docs:
```
BAD:   IpcMemoryCreate: shmget(key=%d, size=%u, 0%o) failed: %m
GOOD:  primary: could not create shared memory segment: %m
       detail:  Failed system call was shmget(key=%d, size=%u, 0%o).
       hint:    (a complete sentence of advice)
```
[verified-by-code, source/src/backend/utils/error/elog.c — `errmsg`/`errdetail`/
`errhint`; via knowledge/idioms/error-handling.md]

## Capitalization & punctuation [from-docs]

- **Primary message**: do **not** capitalize the first letter; **no** trailing
  period (and no `!`).
- **Detail & Hint**: **complete sentences**, capitalized first word, ending
  period; two spaces after a sentence-ending period if another follows (English).
- **Context strings** (the `W` field): not capitalized, no trailing period, not
  usually complete sentences.

## Voice & tense [from-docs]

- **Active voice.** Use a complete sentence when there's an acting subject; use
  "telegram style" (no subject) when the subject would be the program itself.
  **Never use "I"** for the program. Avoid passive voice.
- **Past tense** when an attempt *failed but might succeed later*:
  `could not open file "%s": %m` (disk might not be full next time).
- **Present tense** when the failure is *permanent / conceptually impossible*:
  `cannot open file "%s"`.

  This past-vs-present distinction (could not / cannot) is a real review checkpoint,
  not stylistic taste. [from-docs]

## Word choices [from-docs]

- Avoid **"unable"** → use "cannot" / "could not".
- Avoid **"bad"** → say *why* (e.g. "invalid format").
- Avoid **"illegal"** → use "invalid" and explain.
- Avoid bare **"unknown"** → use "unrecognized" **and include the offending
  value**: `unrecognized node type: 42`, not `unknown node type`.
- Lower case for wording (incl. first letter of primary message); **upper case
  for SQL commands/keywords** appearing in the message.

## Quoting [from-docs]

- **Quote**: file names, user-supplied identifiers, GUC/config variable names,
  any variable that might contain word-like text.
- **Do not quote**: operator names, and output of self-quoting helpers like
  `format_type_be()`.

## Don't name the code [from-docs]

- Don't put the reporting routine's name or a called C-function name in the
  message; describe what was being *attempted*:
```
BAD:   pg_strtoint32: error in "z": cannot parse "z"
GOOD:  invalid input syntax for type integer: "z"
BAD:   open() failed: %m
GOOD:  could not open file "%s": %m
```
  Mention a system call only in the **detail** message if needed. [from-docs]

## State the reason [from-docs]

- *"Messages should always state the reason why an error occurred."*
  `could not open file "%s"` → add the cause, e.g. `%m` or `(I/O failure)`.

## Links into corpus

- [[knowledge/idioms/error-handling.md]] — the `ereport(ERROR, (errcode(...),
  errmsg(...), errdetail(...), errhint(...)))` machinery these rules apply to.
- [[knowledge/docs-distilled/protocol-error-fields.md]] — where the
  primary/detail/hint text lands on the wire (`M`/`D`/`H`).
- [[knowledge/docs-distilled/source.md]] — the surrounding coding-conventions
  chapter.
- The `error-handling` and `coding-style` skills enforce this at edit time.

## Gaps / follow-ups

- SQLSTATE/errcode selection is *not* on this page — that's in the error-handling
  idiom + `src/backend/utils/errcodes.txt`. This page is wording only.
