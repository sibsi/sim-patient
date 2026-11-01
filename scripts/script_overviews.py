"""
Write a readable overview of each frozen script: per turn the doctor question,
the fact shards and the background shards written out, plus unused shards.

Run from the project root:  python -m scripts.script_overviews
Out:  data/patient_cases/frozen_exchanges/script_overviews/<name>_script.md
"""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "patient_cases"
SCRIPTS_DIR = CASES_DIR / "frozen_exchanges"
OUT_DIR = SCRIPTS_DIR / "script_overviews"


def shard_lines(ids, lookup):
    return [f"- `{i}` {lookup.get(i, '!! MISSING SHARD !!')}" for i in ids]


def overview(case, script):
    lookup = {s["shard_id"]: s["statement"] for s in case["shards"]}
    lookup.update({s["life_id"]: s["statement"] for s in case["life_shards"]})

    lines = [f"# {case['name']} ({case['age']}{case['sex']}, {case['diagnosis']})", ""]
    used = set()
    for ex in script["exchanges"]:
        facts = ex.get("fact_ids") or []
        background = ex.get("background_fact_ids") or []
        used |= set(facts) | set(background)
        tags = f"  _[{', '.join(ex['tags'])}]_" if ex.get("tags") else ""
        lines += [f"## Turn {ex['turn']} ({ex['type']}){tags}", "", f"**Doctor:** {ex['question']}", ""]
        lines += ["**Facts:**", *shard_lines(facts, lookup)] if facts else ["**Facts:** none"]
        if background:
            lines += ["", "**Background:**", *shard_lines(background, lookup)]
        lines.append("")

    unused = [i for i in lookup if i not in used]
    lines += ["## Not used in any turn", "", *(shard_lines(unused, lookup) or ["- none"]), ""]
    return "\n".join(lines)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for case_path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(case_path.read_text(encoding="utf-8"))
        script = yaml.safe_load((SCRIPTS_DIR / f"{case_path.stem}_frozen.yaml").read_text(encoding="utf-8"))
        out = OUT_DIR / f"{case['name'].lower()}_script.md"
        out.write_text(overview(case, script), encoding="utf-8")
        print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
