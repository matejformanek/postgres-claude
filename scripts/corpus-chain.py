#!/usr/bin/env python3
"""corpus-chain — traverse the pg-claude knowledge graph.

Given an anchor (scenario slug, idiom slug, or source file path — or
a set of keywords), emit a "chain map": scenarios / idioms / files /
subsystems / past-planning-runs reachable from the anchor within
1-2 hops, ranked by evidence strength.

The graph edges used:

  scenario  --(§Files section)-->  file
  scenario  --(direct/companion_skills)-->  idiom
  scenario  --(§Idioms invoked block)-->  idiom
  idiom     --(§Call sites block)-->  file
  idiom     --(§Scenarios that use me)-->  scenario
  file      --(backlinks:auto block)-->  subsystem / idiom / data-struct
  subsystem --(path prefix match)-->  file
  planning/ --(sessions/ + slugs)-->  scenario / file

Usage
-----
  scripts/corpus-chain.py --scenario add-new-wal-record
  scripts/corpus-chain.py --idiom memory-contexts
  scripts/corpus-chain.py --file src/backend/access/heap/heapam.c
  scripts/corpus-chain.py --keywords "server side variables"
  scripts/corpus-chain.py --keywords "add memory leak fix" --depth 2

Emits markdown to stdout. Redirect to a planning/ file or paste into
a brainstorm.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from collections import defaultdict
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            text=True,
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parent.parent


ROOT = _repo_root()
KNOWLEDGE = ROOT / "knowledge"
SCENARIOS = KNOWLEDGE / "scenarios"
IDIOMS = KNOWLEDGE / "idioms"
SUBSYSTEMS = KNOWLEDGE / "subsystems"
DATA_STRUCTURES = KNOWLEDGE / "data-structures"
FILES_DOCS = KNOWLEDGE / "files"
PLANNING = ROOT / "planning"
SESSIONS = ROOT / "sessions"

SOURCE_PATH_PREFIXED = re.compile(
    r"`?source/([A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)(?::\d+(?:-\d+)?)?`?"
)
SOURCE_PATH_BARE = re.compile(
    r"(?<![/\w])`?((?:src|contrib)/[A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)(?::\d+(?:-\d+)?)?`?"
)


def _paths_in(text: str) -> set[str]:
    return set(SOURCE_PATH_PREFIXED.findall(text)) | set(SOURCE_PATH_BARE.findall(text))


def _slug_ok(name: str) -> bool:
    return name.lower() not in {"readme.md", "_index.md", "template.md", "_template.md"}


# ---------------------------------------------------------------------------
# Graph loaders
# ---------------------------------------------------------------------------


def load_idioms():
    """idiom_slug → {'callsites': set[path], 'scenarios': set[scenario_slug]}"""
    data: dict[str, dict] = {}
    for p in sorted(IDIOMS.glob("*.md")):
        if not _slug_ok(p.name):
            continue
        text = p.read_text()
        callsites = set()
        m = re.search(
            r"## Call sites\s*\n<!-- callsites:auto -->(.*?)<!-- /callsites:auto -->",
            text,
            re.DOTALL,
        )
        if m:
            callsites = _paths_in(m.group(1))
        else:
            callsites = _paths_in(text)
        scenarios_using = set()
        m2 = re.search(
            r"## Scenarios that use me\s*\n<!-- scenarios:auto -->(.*?)<!-- /scenarios:auto -->",
            text,
            re.DOTALL,
        )
        if m2:
            scenarios_using = set(re.findall(r"\[`([A-Za-z0-9_-]+)`\]", m2.group(1)))
        data[p.stem] = {
            "path": p,
            "callsites": callsites,
            "scenarios": scenarios_using,
            "title": _first_heading(text),
        }
    return data


def load_scenarios():
    """scenario_slug → {'files': set[path], 'idioms': set[idiom_slug], 'related': set[scenario_slug]}"""
    data: dict[str, dict] = {}
    for p in sorted(SCENARIOS.glob("*.md")):
        if not _slug_ok(p.name):
            continue
        text = p.read_text()
        files = _paths_in(text)
        idioms = set()
        m = re.search(
            r"## Idioms invoked\s*\n<!-- idioms-invoked:auto -->(.*?)<!-- /idioms-invoked:auto -->",
            text,
            re.DOTALL,
        )
        if m:
            idioms = set(re.findall(r"\[`([A-Za-z0-9_-]+)`\]", m.group(1)))
        # related_scenarios frontmatter
        related: set[str] = set()
        fm = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
        if fm:
            rm = re.search(r"related_scenarios:\s*\[(.*?)\]", fm.group(1))
            if rm:
                related = {
                    x.strip().strip('"').strip("'")
                    for x in rm.group(1).split(",")
                    if x.strip()
                }
        data[p.stem] = {
            "path": p,
            "files": files,
            "idioms": idioms,
            "related": related,
            "title": _first_heading(text),
        }
    return data


def load_data_structures():
    """ds_slug → {'callsites': set[path], 'title': str}"""
    data: dict[str, dict] = {}
    if not DATA_STRUCTURES.exists():
        return data
    for p in sorted(DATA_STRUCTURES.glob("*.md")):
        if not _slug_ok(p.name):
            continue
        text = p.read_text()
        callsites = set()
        m = re.search(
            r"## Call sites\s*\n<!-- callsites:auto -->(.*?)<!-- /callsites:auto -->",
            text,
            re.DOTALL,
        )
        if m:
            callsites = _paths_in(m.group(1))
        else:
            callsites = _paths_in(text)
        data[p.stem] = {
            "path": p,
            "callsites": callsites,
            "title": _first_heading(text),
        }
    return data


def load_subsystems():
    """subsystem_slug → {'path': …, 'title': …, 'refs_files': set[path]}"""
    data: dict[str, dict] = {}
    for p in sorted(SUBSYSTEMS.glob("*.md")):
        if not _slug_ok(p.name):
            continue
        text = p.read_text()
        data[p.stem] = {
            "path": p,
            "title": _first_heading(text),
            "refs_files": _paths_in(text),
        }
    return data


def load_planning_slugs() -> list[str]:
    if not PLANNING.exists():
        return []
    return sorted(
        d.name
        for d in PLANNING.iterdir()
        if d.is_dir() and d.name not in {"_template", "README"}
    )


def load_session_slugs() -> list[Path]:
    if not SESSIONS.exists():
        return []
    return sorted(SESSIONS.glob("*.md"))


def _first_heading(text: str) -> str:
    # Skip frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3 :]
    m = re.search(r"^# (.+)$", text, re.M)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Anchor resolution
# ---------------------------------------------------------------------------


def resolve_keyword_anchors(keywords: str, scenarios, idioms):
    """Return (scenario_hits, idiom_hits, source_file_hits) — string sets."""
    words = [w.lower() for w in re.findall(r"\w+", keywords) if len(w) >= 3]
    if not words:
        return set(), set(), set()

    def hit_count(name: str, extra_text: str = "") -> int:
        haystack = (name + " " + extra_text).lower()
        return sum(1 for w in words if w in haystack)

    sc_hits = {slug for slug in scenarios if hit_count(slug, scenarios[slug]["title"]) > 0}
    id_hits = {slug for slug in idioms if hit_count(slug, idioms[slug]["title"]) > 0}
    # File hits: leave to targeted grep of source paths — coarse for now
    return sc_hits, id_hits, set()


# ---------------------------------------------------------------------------
# Chain traversal
# ---------------------------------------------------------------------------


def chain_from_scenario(
    slug: str, scenarios, idioms, subsystems, data_structures, depth: int = 1
):
    if slug not in scenarios:
        return None
    node = scenarios[slug]
    files = node["files"]
    # Idioms: from the pre-computed Idioms invoked block + fallback via file overlap.
    direct_idioms = node["idioms"]
    transitive_idioms: dict[str, set[str]] = defaultdict(set)
    for f in files:
        for idm, meta in idioms.items():
            if f in meta["callsites"]:
                transitive_idioms[idm].add(f)
    all_idioms = set(direct_idioms) | set(transitive_idioms.keys())

    # Adjacent scenarios: related_scenarios frontmatter + file-overlap
    adj_scenarios: dict[str, dict] = {}
    for other, m in scenarios.items():
        if other == slug:
            continue
        shared = files & m["files"]
        why: list[str] = []
        if other in node["related"]:
            why.append("related_scenarios frontmatter")
        if shared:
            why.append(f"shares {len(shared)} file(s)")
        if why:
            adj_scenarios[other] = {"why": "; ".join(why), "shared": shared}

    # Subsystems: infer from file paths
    subs = _map_files_to_subsystems(files, subsystems)

    # Data-structures reachable via file overlap
    ds_hits: dict[str, set[str]] = defaultdict(set)
    for f in files:
        for ds, meta in data_structures.items():
            if f in meta["callsites"]:
                ds_hits[ds].add(f)

    return {
        "anchor": {"kind": "scenario", "slug": slug, "title": node["title"]},
        "files": sorted(files),
        "idioms_direct": sorted(direct_idioms),
        "idioms_transitive": {
            k: sorted(v) for k, v in sorted(transitive_idioms.items()) if k not in direct_idioms
        },
        "all_idioms": sorted(all_idioms),
        "adjacent_scenarios": adj_scenarios,
        "subsystems": subs,
        "data_structures": {k: sorted(v) for k, v in ds_hits.items()},
    }


def chain_from_idiom(slug: str, scenarios, idioms, subsystems, data_structures, depth: int = 1):
    if slug not in idioms:
        return None
    node = idioms[slug]
    callsites = node["callsites"]
    scenarios_using = node["scenarios"]

    # Sibling idioms: those sharing >=1 call site with this one.
    sibling_idioms: dict[str, set[str]] = defaultdict(set)
    for other, meta in idioms.items():
        if other == slug:
            continue
        shared = callsites & meta["callsites"]
        if shared:
            sibling_idioms[other] = shared

    subs = _map_files_to_subsystems(callsites, subsystems)

    # Data-structures reachable via file overlap
    ds_hits: dict[str, set[str]] = defaultdict(set)
    for f in callsites:
        for ds, meta in data_structures.items():
            if f in meta["callsites"]:
                ds_hits[ds].add(f)

    return {
        "anchor": {"kind": "idiom", "slug": slug, "title": node["title"]},
        "callsites": sorted(callsites),
        "scenarios_using": sorted(scenarios_using),
        "sibling_idioms": {k: sorted(v)[:5] for k, v in sibling_idioms.items()},
        "subsystems": subs,
        "data_structures": {k: sorted(v) for k, v in ds_hits.items()},
    }


def chain_from_file(path: str, scenarios, idioms, subsystems, data_structures):
    # Owner subsystem: via path prefix
    subs = _map_files_to_subsystems({path}, subsystems)
    # Idioms citing this file
    citing = sorted(slug for slug, m in idioms.items() if path in m["callsites"])
    # Data-structures citing this file
    ds_citing = sorted(slug for slug, m in data_structures.items() if path in m["callsites"])
    # Scenarios touching this file
    touching = sorted(slug for slug, m in scenarios.items() if path in m["files"])
    # File doc pointer
    doc = None
    for cand in [FILES_DOCS / f"{path}.md", FILES_DOCS / f"{Path(path).with_suffix('').as_posix()}.md"]:
        if cand.exists():
            doc = cand
            break
    return {
        "anchor": {"kind": "file", "path": path, "doc": str(doc.relative_to(ROOT)) if doc else None},
        "subsystems": subs,
        "idioms_citing": citing,
        "data_structures_citing": ds_citing,
        "scenarios_touching": touching,
    }


def _map_files_to_subsystems(files: set[str], subsystems) -> dict[str, list[str]]:
    """For each subsystem that references any of these files, list matching files."""
    hits: dict[str, list[str]] = defaultdict(list)
    for slug, meta in subsystems.items():
        for f in files:
            if f in meta["refs_files"]:
                hits[slug].append(f)
    return {k: sorted(v) for k, v in hits.items()}


# ---------------------------------------------------------------------------
# Analogous past features
# ---------------------------------------------------------------------------


def past_features_for(files, keywords: list[str]) -> list[dict]:
    """Return planning/ + sessions/ artifacts overlapping with the query."""
    hits: list[dict] = []
    files = set(files) if files else set()
    kw_lc = [k.lower() for k in keywords if len(k) >= 3]
    if PLANNING.exists():
        for d in sorted(PLANNING.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            plan_files = list(d.rglob("*.md"))
            score = 0
            evidence: list[str] = []
            for f in plan_files:
                try:
                    text = f.read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                text_lc = text.lower()
                for kw in kw_lc:
                    if kw in text_lc:
                        score += 1
                        evidence.append(f"'{kw}' in {f.name}")
                        break
                if files:
                    plan_paths = _paths_in(text)
                    common = files & plan_paths
                    if common:
                        score += len(common)
                        evidence.append(f"{len(common)} shared file(s) in {f.name}")
            if score:
                hits.append({"kind": "planning", "slug": d.name, "score": score, "evidence": evidence[:3]})
    if SESSIONS.exists():
        for f in sorted(SESSIONS.glob("*.md")):
            try:
                text = f.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            text_lc = text.lower()
            score = sum(1 for kw in kw_lc if kw in text_lc)
            if files:
                sess_paths = _paths_in(text)
                common = files & sess_paths
                if common:
                    score += len(common)
            if score:
                hits.append({"kind": "session", "slug": f.stem, "score": score, "evidence": []})
    hits.sort(key=lambda h: -h["score"])
    return hits[:10]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(chain, past=None) -> str:
    if chain is None:
        return "_(anchor not found)_\n"
    kind = chain["anchor"]["kind"]
    lines: list[str] = []

    if kind == "scenario":
        slug = chain["anchor"]["slug"]
        title = chain["anchor"]["title"] or slug
        lines.append(f"# Chain map: scenario `{slug}`")
        lines.append("")
        lines.append(f"**Title:** {title}")
        lines.append(f"**Doc:** [`knowledge/scenarios/{slug}.md`](knowledge/scenarios/{slug}.md)")
        lines.append("")

        lines.append("## Files touched")
        if chain["files"]:
            for f in chain["files"]:
                lines.append(f"- `{f}`")
        else:
            lines.append("_(scenario declares no source files)_")
        lines.append("")

        lines.append("## Idioms invoked")
        for idm in chain["all_idioms"]:
            tag = "*direct*" if idm in chain["idioms_direct"] else "_transitive_"
            samples = chain["idioms_transitive"].get(idm, [])[:2]
            sample_note = f" (shares {', '.join('`' + s + '`' for s in samples)})" if samples else ""
            lines.append(f"- [`{idm}`](knowledge/idioms/{idm}.md) — {tag}{sample_note}")
        if not chain["all_idioms"]:
            lines.append("_(none)_")
        lines.append("")

        lines.append("## Adjacent scenarios")
        for other, meta in sorted(chain["adjacent_scenarios"].items(), key=lambda kv: (-len(kv[1]["shared"]), kv[0])):
            lines.append(f"- [`{other}`](knowledge/scenarios/{other}.md) — {meta['why']}")
        if not chain["adjacent_scenarios"]:
            lines.append("_(none)_")
        lines.append("")

        lines.append("## Subsystems")
        for sub, files in sorted(chain["subsystems"].items()):
            lines.append(f"- [`{sub}`](knowledge/subsystems/{sub}.md) — {len(files)} file(s)")
        if not chain["subsystems"]:
            lines.append("_(subsystem docs don't cite these files directly — path-prefix map may be needed)_")
        lines.append("")

        ds = chain.get("data_structures", {})
        if ds:
            lines.append("## Data structures involved")
            for name, files in sorted(ds.items()):
                lines.append(f"- [`{name}`](knowledge/data-structures/{name}.md) — {len(files)} file(s)")
            lines.append("")

    elif kind == "idiom":
        slug = chain["anchor"]["slug"]
        title = chain["anchor"]["title"] or slug
        lines.append(f"# Chain map: idiom `{slug}`")
        lines.append("")
        lines.append(f"**Title:** {title}")
        lines.append(f"**Doc:** [`knowledge/idioms/{slug}.md`](knowledge/idioms/{slug}.md)")
        lines.append("")

        lines.append(f"## Call sites ({len(chain['callsites'])})")
        for f in chain["callsites"][:15]:
            lines.append(f"- `{f}`")
        if len(chain["callsites"]) > 15:
            lines.append(f"- _... +{len(chain['callsites']) - 15} more_")
        lines.append("")

        lines.append(f"## Scenarios that use me ({len(chain['scenarios_using'])})")
        for sc in chain["scenarios_using"]:
            lines.append(f"- [`{sc}`](knowledge/scenarios/{sc}.md)")
        lines.append("")

        lines.append("## Sibling idioms (share ≥1 call site)")
        siblings = sorted(chain["sibling_idioms"].items(), key=lambda kv: -len(kv[1]))[:10]
        for other, shared in siblings:
            preview = ", ".join(f"`{s}`" for s in shared[:2])
            lines.append(f"- [`{other}`](knowledge/idioms/{other}.md) — shares {len(shared)} file(s): {preview}")
        lines.append("")

        lines.append("## Subsystems")
        for sub, files in sorted(chain["subsystems"].items()):
            lines.append(f"- [`{sub}`](knowledge/subsystems/{sub}.md) — {len(files)} file(s)")
        lines.append("")

        ds = chain.get("data_structures", {})
        if ds:
            lines.append("## Data structures involved")
            for name, files in sorted(ds.items()):
                lines.append(f"- [`{name}`](knowledge/data-structures/{name}.md) — {len(files)} file(s)")
            lines.append("")

    elif kind == "file":
        path = chain["anchor"]["path"]
        lines.append(f"# Chain map: file `{path}`")
        lines.append("")
        if chain["anchor"]["doc"]:
            lines.append(f"**File doc:** [`{chain['anchor']['doc']}`]({chain['anchor']['doc']})")
        else:
            lines.append("_(no file doc under `knowledge/files/`)_")
        lines.append("")
        lines.append(f"## Idioms applying here ({len(chain['idioms_citing'])})")
        for idm in chain["idioms_citing"]:
            lines.append(f"- [`{idm}`](knowledge/idioms/{idm}.md)")
        lines.append("")
        ds = chain.get("data_structures_citing", [])
        if ds:
            lines.append(f"## Data structures documented here ({len(ds)})")
            for name in ds:
                lines.append(f"- [`{name}`](knowledge/data-structures/{name}.md)")
            lines.append("")
        lines.append(f"## Scenarios touching this file ({len(chain['scenarios_touching'])})")
        for sc in chain["scenarios_touching"]:
            lines.append(f"- [`{sc}`](knowledge/scenarios/{sc}.md)")
        lines.append("")
        lines.append("## Subsystems referencing this file")
        for sub, files in sorted(chain["subsystems"].items()):
            lines.append(f"- [`{sub}`](knowledge/subsystems/{sub}.md)")
        lines.append("")

    if past:
        lines.append("## Analogous past features")
        for hit in past:
            kind = hit["kind"]
            slug = hit["slug"]
            if kind == "planning":
                lines.append(f"- planning: [`{slug}`](planning/{slug}/) — score {hit['score']}")
            else:
                lines.append(f"- session: [`{slug}`](sessions/{slug}.md) — score {hit['score']}")
            for e in hit["evidence"]:
                lines.append(f"    - {e}")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_keyword_map(sc_hits, id_hits, scenarios, idioms, past) -> str:
    lines = ["# Chain map: keyword search", ""]
    lines.append(f"## Matching scenarios ({len(sc_hits)})")
    for sl in sorted(sc_hits):
        lines.append(f"- [`{sl}`](knowledge/scenarios/{sl}.md) — {scenarios[sl]['title']}")
    lines.append("")
    lines.append(f"## Matching idioms ({len(id_hits)})")
    for sl in sorted(id_hits):
        lines.append(f"- [`{sl}`](knowledge/idioms/{sl}.md) — {idioms[sl]['title']}")
    lines.append("")
    if past:
        lines.append("## Analogous past features")
        for hit in past:
            slug = hit["slug"]
            if hit["kind"] == "planning":
                lines.append(f"- planning: [`{slug}`](planning/{slug}/) — score {hit['score']}")
            else:
                lines.append(f"- session: [`{slug}`](sessions/{slug}.md) — score {hit['score']}")
        lines.append("")
    lines.append("**Next step:** pick a scenario/idiom from above and re-run with `--scenario <slug>` / `--idiom <slug>` for the full chain.")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Traverse the pg-claude knowledge graph.")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--scenario", help="Anchor: scenario slug (e.g. add-new-wal-record).")
    grp.add_argument("--idiom", help="Anchor: idiom slug (e.g. memory-contexts).")
    grp.add_argument("--file", help="Anchor: source file path (e.g. src/backend/access/heap/heapam.c).")
    grp.add_argument("--keywords", help="Search: free-text keywords across scenarios+idioms+planning.")
    ap.add_argument("--depth", type=int, default=1, help="Traversal depth (currently 1-2; default 1).")
    args = ap.parse_args()

    scenarios = load_scenarios()
    idioms = load_idioms()
    subsystems = load_subsystems()
    data_structures = load_data_structures()

    if args.scenario:
        chain = chain_from_scenario(args.scenario, scenarios, idioms, subsystems, data_structures, args.depth)
        if not chain:
            print(f"_(scenario `{args.scenario}` not found — available: {', '.join(sorted(scenarios)[:8])}, ...)_")
            return 1
        past = past_features_for(chain["files"], [args.scenario])
        print(render(chain, past))
    elif args.idiom:
        chain = chain_from_idiom(args.idiom, scenarios, idioms, subsystems, data_structures, args.depth)
        if not chain:
            print(f"_(idiom `{args.idiom}` not found — available: {', '.join(sorted(idioms)[:8])}, ...)_")
            return 1
        past = past_features_for(chain["callsites"], [args.idiom])
        print(render(chain, past))
    elif args.file:
        chain = chain_from_file(args.file, scenarios, idioms, subsystems, data_structures)
        past = past_features_for({args.file}, [Path(args.file).stem])
        print(render(chain, past))
    elif args.keywords:
        sc_hits, id_hits, _ = resolve_keyword_anchors(args.keywords, scenarios, idioms)
        words = re.findall(r"\w+", args.keywords)
        past = past_features_for(None, words)
        print(render_keyword_map(sc_hits, id_hits, scenarios, idioms, past))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
