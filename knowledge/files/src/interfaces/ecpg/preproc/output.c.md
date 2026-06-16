---
path: src/interfaces/ecpg/preproc/output.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 247
depth: deep
---

# `output.c` — emits the translated C source for the ecpg preprocessor

## Purpose
This file is the back end of the ecpg preprocessor: it takes the parsed SQL
constructs and writes the corresponding C code (the `ECPGdo`/`ECPGprepare`/
`ECPGdeallocate` runtime calls plus `#line` directives and `WHENEVER` action
guards) to the output stream `base_yyout`. Everything that lands in the
generated `.c` file from a SQL statement passes through one of the
`output_*` functions here. It also owns the global `WHENEVER` action state
and the C-string escaping logic needed to embed SQL text as a C string
literal. `[verified-by-code]` (whole file)

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `output_line_number` | `output.c:9` | Writes a `#line` directive by delegating to `hashline_number()`. `[verified-by-code]` |
| `output_simple_statement` | `output.c:17` | Emits an escaped statement, optional `WHENEVER` action, then a `#line`. `[verified-by-code]` |
| `when_error`, `when_nf`, `when_warn` | `output.c:30` | Global `struct when` holding the active `WHENEVER` actions (SQLERROR / NOT FOUND / SQLWARNING). `[verified-by-code]` |
| `whenever_action` | `output.c:63` | Emits the `if (sqlca...) <action>` guards after a statement; `mode & 2` closes the wrapping brace. `[verified-by-code]` |
| `hashline_number` | `output.c:91` | Builds the `\n#line N "file"\n` string (with filename escaped); returns `""` when no filename or in YYDEBUG. `[verified-by-code]` |
| `output_statement` | `output.c:133` | Emits a full `{ ECPGdo(...) ... ECPGt_EORT);` call, dumping input/result host variables. `[verified-by-code]` |
| `output_prepare_statement` | `output.c:167` | Emits `{ ECPGprepare(__LINE__, ...)` for PREPARE. `[verified-by-code]` |
| `output_deallocate_prepare_statement` | `output.c:178` | Emits `ECPGdeallocate` or `ECPGdeallocate_all` for DEALLOCATE. `[verified-by-code]` |

## Internal landmarks
- `print_action(struct when *w)` — `output.c:34`: switch over the `WHENEVER`
  action code (`W_SQLPRINT`, `W_GOTO`, `W_DO`, `W_STOP`, `W_BREAK`,
  `W_CONTINUE`); unknown codes emit a `/* N not implemented yet */`
  placeholder (`output.c:58`). `[verified-by-code]`
- `ecpg_statement_type_name[]` — `output.c:124`: lookup table mapping
  `enum ECPG_statement_type` ordinals to their string names emitted into the
  `ECPGdo` call. Index must stay in sync with the enum. `[verified-by-code]`
- `output_escaped_str(const char *str, bool quoted)` — `output.c:195`: the
  char-by-char escaper. Filters `"`, `\n`, `\\`, and `\r\n`; recognizes
  backslash line continuations so they are not double-escaped
  (`output.c:217`-`output.c:235`). `[verified-by-code]`

## Invariants & gotchas
- **`#line` discipline.** `whenever_action` calls `output_line_number()`
  before *and* after emitting action guards (`output.c:68`, `output.c:88`)
  so the C compiler always attributes generated lines back to the original
  `.pgc` source line. Reordering these emits would scramble error line
  reporting. `[verified-by-code]`
- **`hashline_number` suppresses `#line` in debug.** Returns the empty
  string when `input_filename` is null or (under `YYDEBUG`) `base_yydebug`
  is set (`output.c:95`-`output.c:99`). Callers must tolerate an empty
  string. `[verified-by-code]`
- **`hashline_number` filename escaping.** The buffer is sized with
  `strlen(input_filename) * 2` to allow escaping every `\` and `"` in the
  filename, plus `sizeof(int) * CHAR_BIT * 10 / 3` digits for the line
  number (`output.c:102`). The "* 2" comment documents the escape headroom.
  `[verified-by-code]`
- **`output_statement` passes some text raw.** For
  `ECPGst_execute` / `ECPGst_exec_immediate` the `stmt` is a CSTRING or
  host variable and is emitted directly (`output.c:147`-`output.c:148`);
  otherwise it is wrapped in quotes and escaped (`output.c:150`-`output.c:154`).
  `[from-comment]` (`output.c:141`-`output.c:145`)
- **`ECPGst_prepnormal` downgrade.** When `auto_prepare` is off, a
  `prepnormal` statement is rewritten to `ECPGst_normal` before the type
  name is looked up (`output.c:138`-`output.c:139`). `[verified-by-code]`
- **`whenever_action(mode | 2)` always closes the brace.** `output_statement`
  ORs in bit 2 (`output.c:164`) so the `{` opened at `output.c:136` is matched
  by the `fputc('}', ...)` at `output.c:85`-`output.c:86`. `output_prepare_statement`
  and `output_deallocate_prepare_statement` call `whenever_action(2)` for the
  same reason. `[verified-by-code]`
- **`mode & 1` gates the NOT FOUND guard.** Only when bit 1 is set is the
  `ECPG_NOT_FOUND` check emitted (`output.c:66`). `[verified-by-code]`
- **Transient escaped output.** `output_escaped_str` writes directly to
  `base_yyout` char-by-char rather than building a buffer, so there is no
  intermediate allocation to overflow. `[verified-by-code]`

## Cross-refs
- [[util.c]] — `loc_alloc` (used by `hashline_number` at `output.c:102`),
  `mmerror`/`mmfatal`, and the `cat*_str`/`make*_str` string builders that
  feed `stmt` into the `output_*` functions.
- [[ecpg.c]] — drives the preprocessor and consumes `ret_value`; owns
  `base_yyout`/`base_yyin`/`output_filename`.
- [[type.c]], [[variable.c]] — `dump_variables(argsinsert/argsresult, 1)`
  (`output.c:157`, `output.c:160`) lives there; host-variable emission.
- `preproc_extern.h` — declares the `output_*` prototypes, the `struct when`
  type, `enum ECPG_statement_type`, and the globals `compat`,
  `force_indicator`, `connection`, `questionmarks`, `auto_prepare`,
  `base_yylineno`, `input_filename`.

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-correctness: `output_escaped_str` quoted-close test reads `str[len]`]** `output.c:245` — the closing
  branch tests `str[0] == '"' && str[len] == '"'`, but `len` was already
  decremented at `output.c:202` for the quoted case, so `str[len]` now points
  at the original closing quote rather than the terminator. This is the
  intended symmetry with the opening test (`output.c:201` checks `str[len-1]`
  before the decrement), so it appears correct by construction, not a bug —
  noted only because the index arithmetic is subtle and easy to misread.
  Severity: info. `[inferred]`
- **[ISSUE-robustness: empty-string indexing in `output_escaped_str`]** `output.c:201` — the
  guarded test `str[0] == '"' && str[len - 1] == '"'` evaluates `str[len-1]`
  with `len = strlen(str)`; for an empty string `len == 0` makes this
  `str[-1]`. The `&&` short-circuits on `str[0] == '"'` first (false for
  `'\0'`), so an empty string never reaches `str[-1]`. Safe as written, but
  the safety depends on short-circuit order. Severity: info. `[inferred]`
