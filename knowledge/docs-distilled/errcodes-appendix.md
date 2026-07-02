---
source_url: https://www.postgresql.org/docs/current/errcodes-appendix.html
fetched_at: 2026-07-02T20:56:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — PostgreSQL Error Codes (Appendix A)

The full SQLSTATE table — the class/condition taxonomy behind every ereport.
The single most useful reference for the `error-handling` skill. Companion:
`knowledge/docs-distilled/error-message-reporting.md`,
`knowledge/idioms/error-handling.md`.

## SQLSTATE is 5 chars: 2-char class + 3-char condition

- **A SQLSTATE is 5 characters: the first two are the CLASS, the last three the
  condition within it.** Apps can branch on the class alone even when they don't
  recognize the exact code. Each class has a generic `xxx000` code (e.g. `23000`
  = the un-subclassed integrity-constraint violation). [from-docs]
- **The whole table is GENERATED from `src/backend/utils/errcodes.txt`.** That
  file is the single source; it drives both this appendix, the C macro header
  `utils/errcodes.h` (`ERRCODE_UNIQUE_VIOLATION` …), and the PL/pgSQL condition
  names. Add an error code → edit `errcodes.txt`, regenerate. [from-docs]
- **Condition names** (the lowercase `unique_violation` form usable in a
  PL/pgSQL `EXCEPTION WHEN` clause) map 1:1 to the uppercase C macro
  `ERRCODE_UNIQUE_VIOLATION`. Not every SQLSTATE has a spelled condition name —
  those are caught by code only. [from-docs]

## The class map (2-char prefixes)

- **Non-error / soft classes:** `00` Successful Completion, `01` Warning, `02`
  No Data, `03` Statement Not Yet Complete. [from-docs]
- **Connection / feature:** `08` Connection Exception, `0A` Feature Not
  Supported, `0B` Invalid Transaction Initiation, `0F/0L/0P/0Z` locator /
  grantor / role-spec / diagnostics. [from-docs]
- **Data / constraint core:** `22` Data Exception (overflow, division-by-zero,
  bad cast, invalid text-rep), `23` Integrity Constraint Violation (PK/FK/
  unique/check/not-null), `24` Invalid Cursor State, `25` Invalid Transaction
  State, `21` Cardinality Violation, `20` Case Not Found. [from-docs]
- **Auth / naming:** `26/27/28/2B/2D/2F` statement-name / triggered-data /
  auth / dependent-privilege / invalid-txn-termination / routine-exception;
  `34/38/39/3B/3D/3F` cursor-name / external-routine / external-invocation /
  savepoint / catalog-name / schema-name. [from-docs]
- **Transaction / syntax:** `40` Transaction Rollback (serialization failure,
  deadlock), `42` Syntax Error or Access Rule Violation (the big parser/
  semantic bucket), `44` WITH CHECK OPTION Violation. [from-docs]
- **Resource / operational:** `53` Insufficient Resources (OOM, disk full, too
  many connections), `54` Program Limit Exceeded (too complex / too many
  columns), `55` Object Not In Prerequisite State (lock not available, object
  in use), `57` Operator Intervention (cancel/shutdown), `58` System Error
  (I/O). [from-docs]
- **Special:** `72` Snapshot Too Old, `F0` Configuration File Error, `HV`
  FDW-specific, `P0` PL/pgSQL, **`XX` Internal Error** (the "this is a PG bug or
  corruption" class). [from-docs]

## Codes a backend hacker actually types

```
23502 not_null_violation      23503 foreign_key_violation
23505 unique_violation        23514 check_violation
40001 serialization_failure   40P01 deadlock_detected
42601 syntax_error            42P01 undefined_table    42703 undefined_column
53200 out_of_memory           55P03 lock_not_available (NOWAIT/SKIP LOCKED)
57014 query_canceled          25P02 in_failed_sql_transaction
XX000 internal_error          XX001 data_corrupted     XX002 index_corrupted
```

- **`XX000` internal_error / `XX001` data_corrupted / `XX002` index_corrupted**
  are what `elog(ERROR, ...)` and corruption reports (amcheck, checksum
  failures) surface — if a user query returns `XX0xx`, it's a PG-side bug or on-
  disk corruption, not a user error. **`40001`/`40P01`** are the retry-worthy
  ones (SSI conflict / deadlock). **`55P03`** is what `NOWAIT` raises.
  [from-docs]

## Choosing a code (error-handling skill cross-ref)

- New ereport → pick the most specific existing condition from `errcodes.txt`;
  fall back to the class's generic `xxx000` only if none fits. Use `XX000`
  (`internal_error`, the default for bare `elog`) only for genuine
  can't-happen/assertion-style failures — a user-triggerable condition should
  get a real SQLSTATE so clients can branch on it. [inferred-from-docs +
  error-handling skill]

## Links into corpus

- [[knowledge/docs-distilled/error-message-reporting.md]] — the ereport/elog machinery that carries these codes.
- [[knowledge/docs-distilled/error-style-guide.md]] — message wording that pairs with the code.
- [[knowledge/idioms/error-handling.md]] — errcode() / SQLSTATE selection idiom.
- Skill: `error-handling` — picking a SQLSTATE from errcodes.txt, errcode_for_file_access, soft errors.

## Confidence note

Class list + specific codes `[from-docs]` (Error Codes appendix, fetched
2026-07-02). The "generated from `src/backend/utils/errcodes.txt`" statement is
made by the appendix itself; the exact anchor-SHA line numbers of that file are
not re-pinned this run (reference file, stable location). The code-selection
guidance is `[inferred]` from the appendix + the error-handling skill.
