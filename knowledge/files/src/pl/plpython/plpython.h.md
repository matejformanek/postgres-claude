# plpython.h

Covers `source/src/pl/plpython/plpython.h` (41 LOC). Sibling: `plpython_system.h.md`.

Source pin: `4b0bf0788b0`.

## One-line summary

Master plpython header: pins `Py_LIMITED_API` to 3.2, enforces `postgres.h`-before-`Python.h` include order, and pulls in the Python system headers via `plpython_system.h`. Every plpython sub-header `#include`s this one transitively, so .c files never need to include `Python.h` directly.

## Public API / entry points

None — pure preprocessor scaffolding. Defines:

- `Py_LIMITED_API 0x03020000` — pin the stable ABI to Python 3.2 [verified-by-code: `source/src/pl/plpython/plpython.h:29`].
- `TEXTDOMAIN PG_TEXTDOMAIN("plpython")` — gettext domain used by every `dgettext()` call in plpy_elog.c and plpy_exception_set [verified-by-code: `source/src/pl/plpython/plpython.h:38-39`].

## Key invariants

- **`postgres.h` MUST be included before `plpython.h`** — enforced by `#error postgres.h must be included before plpython.h` [verified-by-code: `source/src/pl/plpython/plpython.h:20-21`]. This is the ancient PG/Python ABI dance: PG's `errcode` macro and Python's `errcode` symbol collide on MSVC, see plpython_system.h.
- **`Python.h` MUST be included via plpython.h (not directly)** — enforced by `#elif defined(Py_PYTHON_H) #error Python.h must be included via plpython.h` [verified-by-code: `source/src/pl/plpython/plpython.h:22-23`]. Direct inclusion bypasses the `system_header` pragma and the MSVC errcode shim.

## Notable internals

- The `Py_LIMITED_API 0x03020000` pin means plpython links against the **stable Python ABI subset** introduced in CPython 3.2 [from-comment: `source/src/pl/plpython/plpython.h:27-29`]. Concretely, this forbids use of `PyEval_EvalCode` direct macro form, `_PyObject_LookupAttr`, and other CPython internals not in the limited ABI. Practical consequence: a plpython3.so built against Python 3.10 headers will load against Python 3.12 runtime without recompilation — the same .so works across minor Python versions.
- File-level comment explicitly tells maintainers "It's therefore unnecessary for any plpython *.c files to include it directly" [from-comment: `source/src/pl/plpython/plpython.h:5-7`]. In practice, every `plpy_*.c` file pulls in plpython.h transitively through a `plpy_*.h` header.

## Trust posture

plpython is **untrusted-only**. The pg_language is `plpython3u` (the trailing `u` is the convention for untrusted), defined by `plpython3u.control` with `superuser = true` and the comment "PL/Python3U untrusted procedural language" [verified-by-code: `source/src/pl/plpython/plpython3u.control:1-7`]. There is NO trusted variant — no `plpython3.control`, no `plpython3t`, no separate handler dispatch.

This is the headline divergence from A10-1's plperl (which has both `plperl` trusted and `plperlu` untrusted, with Safe.pm gating the trusted side) and the spiritual mirror of plpgsql (which is trusted because plpgsql has no I/O primitives at all — no file, no socket, no shell).

**Why no trusted Python?** Python's standard library is too large and too interlinked to safely subset; there is no equivalent of Perl's Safe.pm or Tcl's `interp create -safe`. Restricting `import` would not be enough — `__builtins__`, `getattr`, attribute traversal through `()`-cell objects, and ctypes all provide trivial escapes. The PG project's standing answer is "untrusted only, gated on superuser CREATE EXTENSION." See `superuser = true` in the control file.

**What "untrusted" means concretely:**
1. **CREATE EXTENSION plpython3u** requires a superuser (or a role with the `plpython3u` USAGE privilege after a superuser has created it once).
2. After creation, **any role with USAGE on the language can CREATE FUNCTION ... LANGUAGE plpython3u**. That function then runs with the privileges of the *invoking* user (SECURITY INVOKER) or definer (SECURITY DEFINER) — same as any other PG function. The "untrusted" label is purely about *what the language can do at all*, not about *who can invoke a created function*.
3. Inside the function body, Python has full filesystem access, can `os.system`, can open arbitrary sockets, and shares the backend's effective UID. **A non-superuser who can CREATE FUNCTION in plpython3u has root-equivalent access to the PG cluster's filesystem.**

This is enforced at the PG language layer (`pg_language.lanpltrusted = false` after CREATE EXTENSION), not inside plpython itself; plpy_main.c has no notion of trust [inferred from absence of any `trusted` check in plpy_main.c].

## Cross-references

- `plpython_system.h.md` — the system-headers wrapper this file delegates to.
- `plpy_main.c.md` — the entry points; trust posture detail also lives there.
- A9 comparison: plpgsql is trusted because it cannot do I/O at all. plpython's untrusted-only posture is the opposite extreme — Python can do everything, so the gate is moved up to "superuser must CREATE EXTENSION."
- A10-1 plperl: dual-posture (plperl trusted via Safe.pm, plperlu untrusted). plpython has no Safe.pm analogue.
- `source/src/pl/tcl/pltcl.c` — pltcl is dual-posture (pltcl/pltclu) via Tcl `interp create -safe`. plpython has no equivalent.

## Issues spotted

None at this layer — the file is pure scaffolding. The trust-posture decision is enforced in the control file and language catalog, not here.
