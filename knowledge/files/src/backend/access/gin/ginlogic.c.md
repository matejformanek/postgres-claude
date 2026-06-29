# ginlogic.c

- **Source path:** `source/src/backend/access/gin/ginlogic.c` (250 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Bridge between **boolean** and **ternary** consistent functions exposed by GIN opclasses. The scan engine in `ginget.c` always *calls* a ternary interface; the opclass may have implemented either form; this file adapts whichever direction is needed. [from-comment, ginlogic.c:1-26]

## Adaptation directions

- **Opclass has ternary**: trivial wrapper that maps `GIN_TRUE/GIN_FALSE/GIN_MAYBE` to TRUE / FALSE / TRUE+recheck.
- **Opclass has only boolean**: simulate ternary by calling the boolean function for every assignment of TRUE/FALSE to MAYBE inputs. If all calls return same → that's the answer; if mixed → MAYBE. Capped at a small number of MAYBE inputs (otherwise 2^k explodes) — over the cap, falls back to MAYBE.

## Why ternary matters

A boolean consistent is enough for correctness, but a ternary one lets the scan engine prove "this item matches regardless of unknown keys" or "cannot possibly match" without fetching every key. This is the core optimization that makes GIN fast for FTS where most keys are sparse. [from-comment, ginlogic.c:20-25]

Tags: [from-comment, ginlogic.c:1-30].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/gin-scan-and-consistent.md](../../../../../idioms/gin-scan-and-consistent.md)

