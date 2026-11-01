"""Thesis tables for Part 1: per speaker model, each Big Five profile against the moderate baseline.

Each profile cell averages its 16 dialogues (8 cases x 2 seeds); the value in brackets is the
difference from moderate over the same cases and seeds. Writes tables.md, dialogues.csv, summary.md
(effects consistent across models), heatmap.png and neuroticism_affect.png.

python scripts/thesis_tables_part1.py [--output outputs/Part1_ANALYSIS]
"""
import argparse
import csv
import json
import os
import re
from pathlib import Path
from statistics import mean
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_evaluations import contradiction_timing
from evaluation.personality import behavior_summary
from evaluation.reporting import evaluation_overview, linguistic_metrics
from evaluation.schemas import BEHAVIOR_SUBTYPES

# Run folders exceed the Windows path limit.
RESULTS = Path("\\\\?\\" + str(ROOT / "outputs/Part1_RESULTS")) if os.name == "nt" else ROOT / "outputs/Part1_RESULTS"
PROFILES = ["moderate"] + [f"{t} {level}" for t in "OCEAN" for level in ("high", "low")]
RESPONSE = [("direct_disclosure_pct", "Direct disclosure %"), ("background_disclosure_pct", "Background disclosure %"),
            ("contradictions", "Contradictions"), ("unsupported_additions", "Unsupported additions"),
            ("naturalness", "Naturalness (1-5)"), ("fit", "Fit (1-5)"),
            ("words_per_turn", "Words / turn"), ("mattr", "MATTR")]
BEHAVIOR = [(f"{c}_pct", c.replace("_", " ")) for c in BEHAVIOR_SUBTYPES]
# Measures for the summary and heatmap: (key, label, smallest difference from moderate that counts).
EFFECTS = [("words_per_turn", "words / turn", 3), ("background_disclosure_pct", "background disclosure", 3),
           ("unsupported_additions", "unsupported additions", 1), ("affect_pct", "affect", 3),
           ("affect/worry_pct", "worry", 3), ("affect/calm_optimism_pct", "calm / optimism", 2),
           ("patient_question_pct", "questions", 2), ("interaction_stance_pct", "interaction stance", 2),
           ("own_interpretation_pct", "own interpretation", 2), ("unasked_content_pct", "unasked content", 2),
           ("care_engagement_pct", "care engagement", 2)]
# Diverging blue (lower than moderate) to red (higher), gray midpoint.
LOWER, NEUTRAL, HIGHER = "#2a78d6", "#8a8984", "#e34948"


def dialogue_row(document):
    generation = document["generation"]
    behaviors = behavior_summary(document["turns"], len(document["report_context"]))["behaviors"]
    overview = evaluation_overview(document, {"behaviors": behaviors})
    metrics = linguistic_metrics(document["report_context"])
    timing = [c["fact_timing"] for c in contradiction_timing(document)]
    speaker = re.sub(r"-(Instruct-\d+|it)$", "", generation["speaker"]["model_name"].split("/")[-1])
    row = {"speaker": speaker,
           "profile": generation["personality_condition"].removeprefix("b5_").replace("_", " "),
           "case": generation["patient_id"], "seed": generation["run_seed"],
           "direct_disclosure_pct": overview["disclosure"]["directly_relevant"]["percentage"],
           "background_disclosure_pct": overview["disclosure"]["related_background"]["percentage"],
           "contradictions": len(timing),
           "contradictions_not_yet_given": timing.count("future"),
           "unsupported_additions": overview["factual_findings"]["unsupported_addition"],
           "naturalness": overview["realism"]["spoken_naturalness"], "fit": overview["realism"]["conversational_fit"],
           "words_per_turn": metrics["mean_words_per_turn"], "mattr": metrics["mattr"]}
    # Share of assessed turns showing the behavior; subtypes go to the CSV only.
    for category, counts in behaviors.items():
        share = lambda c: 100 * c["count"] / c["assessed_turns"] if c["assessed_turns"] else None
        row[f"{category}_pct"] = share(counts)
        for subtype, sub in counts["subtypes"].items():
            row[f"{category}/{subtype}_pct"] = share(sub)
    return row


def average(rows, key):
    values = [r[key] for r in rows if r[key] is not None]
    return mean(values) if values else None


def table(rows, columns, digits=1):
    lines = ["| Profile | " + " | ".join(label for _, label in columns) + " |", "|---" * (len(columns) + 1) + "|"]
    baseline = {key: average([r for r in rows if r["profile"] == "moderate"], key) for key, _ in columns}
    for profile in PROFILES:
        cells = []
        for key, _ in columns:
            value = average([r for r in rows if r["profile"] == profile], key)
            if value is None:
                cells.append("–")
            elif profile == "moderate":
                cells.append(f"{value:.{digits}f}")
            else:
                cells.append(f"{value:.{digits}f} ({value - baseline[key]:+.{digits}f})")
        lines.append(f"| {profile} | " + " | ".join(cells) + " |")
    return lines


def differences(rows, speakers):
    """Profile mean minus moderate mean, per speaker, profile and effect measure."""
    result = {}
    for speaker in speakers:
        mine = [r for r in rows if r["speaker"] == speaker]
        baseline = {key: average([r for r in mine if r["profile"] == "moderate"], key) for key, _, _ in EFFECTS}
        result[speaker] = {profile: {key: average([r for r in mine if r["profile"] == profile], key) - baseline[key]
                                     for key, _, _ in EFFECTS} for profile in PROFILES[1:]}
    return result


def summary(diffs, speakers):
    """Effects that move the same way in at least three of the four models by at least the threshold."""
    lines = ["# Part 1: consistent effects", "",
             f"A change is listed when at least 3 of the {len(speakers)} speaker models move the same way by at least "
             "the threshold (3 words, 3 points of turns or disclosure, 2 for smaller categories, 1 addition) and "
             "none moves the opposite way. Brackets: models agreeing, then the range of differences from moderate.", "",
             "| Profile | Consistent effects vs. moderate |", "|---|---|"]
    for profile in PROFILES[1:]:
        effects = []
        for key, label, threshold in EFFECTS:
            values = [diffs[s][profile][key] for s in speakers]
            up, down = sum(v >= threshold for v in values), sum(v <= -threshold for v in values)
            for count, other, arrow in ((up, down, "↑"), (down, up, "↓")):
                if count >= 3 and other == 0:
                    effects.append(f"{label} {arrow} ({count}/{len(speakers)}, {min(values):+.1f} to {max(values):+.1f})")
        lines.append(f"| {profile} | {'; '.join(effects) or '—'} |")
    return lines


def heatmap(diffs, speakers, path):
    """One panel per model; colour is the difference in multiples of the measure's threshold, the text is the difference."""
    colours = LinearSegmentedColormap.from_list("diverging", ["#184f95", "#6da7ec", "#f0efec", "#ef8f8e", "#b8302f"])
    keys = [key for key, _, _ in EFFECTS]
    figure, axes = plt.subplots(1, len(speakers), figsize=(5.2 * len(speakers), 6.2), sharey=True)
    for axis, speaker in zip(axes, speakers):
        grid = [[diffs[speaker][p][k] / threshold for k, _, threshold in EFFECTS] for p in PROFILES[1:]]
        axis.imshow(grid, cmap=colours, vmin=-4, vmax=4, aspect="auto")
        for i, profile in enumerate(PROFILES[1:]):
            for j, key in enumerate(keys):
                axis.text(j, i, f"{diffs[speaker][profile][key]:+.0f}", ha="center", va="center", fontsize=7.5, color="#0b0b0b")
        axis.set_title(speaker, fontsize=11, color="#0b0b0b")
        axis.set_xticks(range(len(keys)), [label for _, label, _ in EFFECTS], rotation=55, ha="right", fontsize=8.5)
        axis.set_yticks(range(len(PROFILES) - 1), PROFILES[1:], fontsize=9)
        axis.tick_params(length=0, colors="#52514e")
        for spine in axis.spines.values():
            spine.set_visible(False)
    figure.suptitle("Difference from the moderate baseline (red higher, blue lower; full colour at 4× the summary threshold)",
                    fontsize=12, color="#0b0b0b")
    figure.tight_layout()
    figure.savefig(path, dpi=200, facecolor="#fcfcfb")
    plt.close(figure)


def neuroticism_bars(rows, speakers, path, key="affect_pct"):
    """Share of turns with affect under N low, moderate and N high, per speaker model."""
    conditions = [("N low", LOWER), ("moderate", NEUTRAL), ("N high", HIGHER)]
    width = 0.26
    figure, axis = plt.subplots(figsize=(8.5, 4.6))
    for offset, (profile, colour) in enumerate(conditions):
        values = [average([r for r in rows if r["speaker"] == s and r["profile"] == profile], key) for s in speakers]
        positions = [i + (offset - 1) * (width + 0.02) for i in range(len(speakers))]
        bars = axis.bar(positions, values, width, color=colour, label=profile)
        axis.bar_label(bars, fmt="%.0f", fontsize=8.5, color="#52514e", padding=2)
    axis.set_xticks(range(len(speakers)), speakers, fontsize=9.5, color="#0b0b0b")
    axis.set_ylabel("Turns with affect (%)", color="#52514e")
    axis.set_title("Affect by neuroticism level", fontsize=12, color="#0b0b0b", loc="left")
    axis.legend(frameon=False, fontsize=9)
    axis.grid(axis="y", color="#e6e5e1", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.tick_params(length=0, colors="#52514e")
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    figure.tight_layout()
    figure.savefig(path, dpi=200, facecolor="#fcfcfb")
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/Part1_ANALYSIS")
    args = parser.parse_args()
    rows = [dialogue_row(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(RESULTS.rglob("evaluation.json"))]
    speakers = sorted({r["speaker"] for r in rows})

    lines = ["# Part 1 results", "",
             "Each cell is the mean over 16 dialogues (8 cases × 2 seeds); brackets give the difference from "
             "moderate. Disclosure is the share of supplied facts the judge found communicated. Contradictions and "
             "additions are counts per dialogue. Behaviors are the share of turns showing the category.", ""]
    for speaker in speakers:
        mine = [r for r in rows if r["speaker"] == speaker]
        lines += [f"## {speaker}", "", "### Response measures", ""] + table(mine, RESPONSE, 2)
        lines += ["", "### Model-added behavior (% of turns)", ""] + table(mine, BEHAVIOR) + [""]
    lines += ["## Contradictions by whether the fact was already given", "",
              "| Speaker | Dialogues | Contradictions | Fact already given | Fact not yet given |", "|---|---|---|---|---|"]
    for speaker in speakers:
        mine = [r for r in rows if r["speaker"] == speaker]
        total, later = sum(r["contradictions"] for r in mine), sum(r["contradictions_not_yet_given"] for r in mine)
        lines.append(f"| {speaker} | {len(mine)} | {total} | {total - later} | {later} |")

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(args.output / "dialogues.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    diffs = differences(rows, speakers)
    (args.output / "summary.md").write_text("\n".join(summary(diffs, speakers)) + "\n", encoding="utf-8")
    heatmap(diffs, speakers, args.output / "heatmap.png")
    neuroticism_bars(rows, speakers, args.output / "neuroticism_affect.png")
    print(f"{len(rows)} dialogues, {len(speakers)} speakers -> {args.output}")


if __name__ == "__main__":
    main()
