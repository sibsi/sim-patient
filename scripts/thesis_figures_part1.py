"""Thesis figure for Part 1: each profile's difference from the moderate profile, pooled over the four speakers.

Differences are paired on speaker, case and seed (64 pairs per profile); intervals are 95% bootstraps.
Reads dialogues.csv from thesis_tables_part1.py and uses the plot style of the Part 2 figures.

python scripts/thesis_figures_part1.py [--analysis outputs/Part1_ANALYSIS]
"""
import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
from thesis_figures_part2 import (GRID, HIGH, INK, INK_2, LOW, MODERATE, ROOT, bootstrap, dot_panel, number, read,
                                  save, style)

PROFILES = [f"{trait} {level}" for trait in "NAOEC" for level in ("high", "low")]
NAMES = {"N": "Neuroticism", "A": "Agreeableness", "O": "Openness", "E": "Extraversion", "C": "Conscientiousness"}
PANELS = [("direct_disclosure_pct", "Requested facts\ndisclosed (pp)"),
          ("background_disclosure_pct", "Background facts\ndisclosed (pp)"),
          ("words_per_turn", "Words\nper reply"), ("affect/worry_pct", "Turns with\nworry (pp)")]


def differences(rows, profile, key):
    """Profile minus moderate over (speaker, case, seed) pairs."""
    moderate = {(r["speaker"], r["case"], r["seed"]): number(r[key]) for r in rows if r["profile"] == "moderate"}
    return [number(r[key]) - moderate[r["speaker"], r["case"], r["seed"]]
            for r in rows if r["profile"] == profile and number(r[key]) is not None
            and moderate.get((r["speaker"], r["case"], r["seed"])) is not None]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--analysis", type=Path, default=ROOT / "outputs/Part1_ANALYSIS")
    args = parser.parse_args()
    rows = read(args.analysis / "dialogues.csv")
    figure, axes = plt.subplots(1, len(PANELS), figsize=(7.4, 3.4), sharey=True)
    for axis, (key, title) in zip(axes, PANELS):
        for p, profile in enumerate(PROFILES):
            colour = HIGH if profile.endswith("high") else LOW
            dot_panel(axis, [bootstrap(differences(rows, profile, key))], [p], colour)
        axis.axvline(0, color=MODERATE, linewidth=1)
        axis.set_title(title, fontsize=8.5)
        style(axis)
    axes[0].set_yticks(range(len(PROFILES)), [f"{p[0]} {p.split()[1]}" for p in PROFILES], color=INK)
    axes[0].set_ylim(len(PROFILES) - 0.5, -0.5)
    for edge in (1.5, 3.5, 5.5, 7.5):
        for axis in axes:
            axis.axhline(edge, color=GRID, linewidth=0.8)
    handles = [Line2D([], [], marker="o", linestyle="", color=colour, markersize=6.5, label=label)
               for label, colour in (("High", HIGH), ("Low", LOW))]
    handles.append(Line2D([], [], color=MODERATE, linewidth=1, label="Moderate (0)"))
    figure.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.07), ncol=3, fontsize=8,
                  labelcolor=INK_2)
    figure.tight_layout(w_pad=1.2)
    save(figure, args.analysis / "figures", "study1_profiles")
    print(f"{len(rows)} dialogues -> {args.analysis / 'figures'}")


if __name__ == "__main__":
    main()
