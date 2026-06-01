# var.c — Var-node analysis and rewriting utilities

- **Source:** 1408 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

PlaceHolderVar and CurrentOfExpr are treated as Vars throughout this
module for the purpose of "contains variables" questions. [from-comment:6-9]

## Public surface

| Line | Function | Notes |
|---|---|---|
| 113 | `pull_varnos(root, node)` | Set of relids referenced; `root` may be NULL if no PHV processing needed [from-comment:103-107] |
| 139 | `pull_varnos_of_level` | Restrict to a specific query level |
| 295 | `pull_varattnos` | Build bitmap of (varattno) used for a single rel |
| 338 | `pull_vars_of_level` | List of Vars/PHVs of a query level (used by subselect handling) |
| 405 | `contain_var_clause(node)` | Quick yes/no |
| 443 | `contain_vars_of_level(node, levelsup)` | Quick yes/no for specific level |
| 510 | `contain_vars_returning_old_or_new` | OLD/NEW returning trigger context — also catches rewritten ReturningExprs [from-comment:495-507] |
| 554 | `locate_var_of_level` | First-found position |
| 652 | `pull_var_clause(node, flags)` | List-of-Vars walker; **does not examine subqueries**, requires sublink→subplan reduction first [from-comment:643-650] |
| 780 | `flatten_join_alias_vars(...)` | Replace JoinExpr alias Vars by underlying expr; nullingrels handled via PHV wrap if base expr isn't Var/PHV [from-comment:770-779] |
| 818 | `flatten_join_alias_for_parser` | Variant for parser callers |
| 998 | `pullup_replace_vars(...)` | Var substitution during subquery pullup; `root` only needed for varnullingrels preservation [from-comment:980-995] |

## Tag tally
`[verified-by-code]` ×4, `[from-comment]` ×7

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
