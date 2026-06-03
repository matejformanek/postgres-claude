---
path: src/bin/psql/prompt.h
anchor_sha: 4b0bf0788b0
loc: 17
depth: read
---

# prompt.h

- **Source path:** `source/src/bin/psql/prompt.h`
- **Lines:** 17
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `prompt.c` (implementation), `fe_utils/psqlscan.h` (where `promptStatus_t` enum actually lives), `fe_utils/conditional.h` (`ConditionalStack`).

## Purpose

Declares the single externally visible function of the prompt subsystem. The bulk of the type machinery is re-exported from `fe_utils/psqlscan.h`.

## Public surface

- `get_prompt(promptStatus_t status, ConditionalStack cstack)` (15) — returns a pointer to a `static` buffer (see prompt.c notes). [verified-by-code, prompt.h:15]

## Phase D notes

- The header re-exposes `promptStatus_t` via the include. Callers see the enum (PROMPT_READY, PROMPT_CONTINUE, PROMPT_SINGLEQUOTE, PROMPT_DOUBLEQUOTE, PROMPT_DOLLARQUOTE, PROMPT_COMMENT, PROMPT_PAREN, PROMPT_COPY) but those values are owned by the psqlscan FSM. [from-comment, prompt.h:12]
- No security surface in this header.

## Confidence tag tally
`[verified-by-code]=1 [from-comment]=1`
