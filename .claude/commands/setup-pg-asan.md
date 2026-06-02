---
description: Sanitizer-build profile — meson setup + build + install with AddressSanitizer + UndefinedBehaviorSanitizer into dev/{build,install}-asan. Use for memory-bug hunting (UAF, OOB, double-free, signed overflow). Sibling to /setup-pg.
---

# setup-pg-asan

Parallel build profile to `/setup-pg`. Same build, plus
`-Db_sanitize=address,undefined`. Lands in `dev/build-asan/` and
`dev/install-asan/` so it can coexist with the normal debug build.

**When to use:** chasing a SIGSEGV, suspected use-after-free, heap-buffer-overflow,
double-free, signed-integer overflow, alignment violation, or anything else
the C debug build can't catch by itself. For everyday backend stepping use
plain `/setup-pg` — ASan adds ~2-3x slowdown.

## What to run

From the project root:

```bash
if [ -f dev/build-asan/build.ninja ] && [ "$1" != "--force" ]; then
  echo "build-asan already configured; skipping meson setup (use --force to reconfigure)"
else
  rm -rf dev/build-asan
  meson setup dev/build-asan dev \
    --buildtype=debug \
    -Dcassert=true \
    -Ddebug=true \
    -Db_sanitize=address,undefined \
    -Db_lundef=false \
    -Dprefix=$PWD/dev/install-asan
fi

ninja -C dev/build-asan
ninja -C dev/build-asan install
```

`-Db_lundef=false` is required on clang / macOS: ASan needs late-resolved
symbols and without this flag linking fails with `Undefined symbols for
architecture arm64: ___asan_init…`.

## After running

Binaries are at `dev/install-asan/bin/`. Next step: `/pg-start-asan`.

The two profiles are independent — `dev/install-debug/` and
`dev/install-asan/` coexist; pick which one to PATH based on the task.

## macOS note: LeakSanitizer is not available

The `b_sanitize=address` flag enables ASan but **NOT** LeakSanitizer on
Darwin. `/pg-start-asan` exports `ASAN_OPTIONS=…detect_leaks=0…` to keep
the runtime from erroring out. For real leak detection on macOS use
`leaks <pid>` against either build profile, or rebuild this profile on
Linux. See `.claude/skills/debugging/SKILL.md` §11.3.

## Worktree note

Same as `/setup-pg`: this command writes to `dev/` (which symlinks into
the `postgresql-dev/` clone). From a worktree, either run it from main,
or ensure the `dev` symlink exists in the worktree first. See
`.claude/skills/build-and-run/SKILL.md` "Running these from a git
worktree".

## Troubleshooting

- **`meson.build … unknown option b_sanitize`** — your meson is too old.
  `pip install -U meson` or `brew upgrade meson`. ≥ 0.55 is fine.
- **`ld: library not found for -lclang_rt.asan_osx_dynamic`** — clang
  install is incomplete or PATH is pointing at Apple's `cc` shim. Confirm
  `cc -v` reports a real Clang version with a resource dir.
- **Linker errors during install only** — `ninja install` may still
  attempt to relink. `rm -rf dev/install-asan && ninja -C dev/build-asan
  install` cleanly.
- **`/pg-start-asan` says "PG_VERSION mismatch"** — you cannot share
  `dev/data-asan/` between major versions. The asan profile uses its own
  data dir (`dev/data-asan/`) precisely so it doesn't collide with the
  debug profile's `dev/data-debug/`.
