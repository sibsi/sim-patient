"""Thesis figures and tables for Part 2, from the analysis CSVs of analyze_interactive.py.

Intervals are 95% percentile bootstraps over conversations (2000 resamples). Trait effects are paired:
the high and low profile share case and seed, so each pair gives one difference.
Writes figures/*.pdf and *.png, tables.md and behavior_categories.tex into the analysis folder.

python scripts/thesis_figures_part2.py [--analysis outputs/Part2_ANALYSIS]
"""
import argparse
import collections
import csv
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # quiet the semibold fallback notices

ROOT = Path(__file__).resolve().parents[1]
SURFACE, INK, INK_2, GRID, NEUTRAL_DOT = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e1", "#3d3c39"
# trait level, as in Part 1: low blue, moderate gray, high red
LOW, MODERATE, HIGH = "#2a78d6", "#8a8984", "#e34948"
DASH = {HIGH: "-", MODERATE: (0, (4, 2)), LOW: (0, (1, 1.5))}  # line style follows the level too
MODELS = [("Qwen/Qwen3.5-27B", "Qwen3.5-27B"), ("google/gemma-4-31B-it", "Gemma-4-31B")]
PROFILES = [("b5_moderate", "Moderate", MODERATE), ("b5_N_high", "N high", HIGH), ("b5_N_low", "N low", LOW),
            ("b5_A_high", "A high", HIGH), ("b5_A_low", "A low", LOW), ("b5_O_low", "O low", LOW)]
LABEL = {key: label for key, label, _ in PROFILES}
TRAITS = [("Neuroticism", "b5_N_high", "b5_N_low"), ("Agreeableness", "b5_A_high", "b5_A_low"),
          ("Openness", None, "b5_O_low")]
WINDOWS = ((1, 5), (6, 10), (11, 15))
RNG_SEED, RESAMPLES = 1, 2000

plt.rcParams.update({
    "font.family": ["Segoe UI", "Arial", "DejaVu Sans"], "font.size": 8.5, "pdf.fonttype": 42,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 9,
    "axes.titlelocation": "left", "axes.titleweight": "semibold", "xtick.color": INK_2, "ytick.color": INK_2,
    "xtick.major.size": 0, "ytick.major.size": 0, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "legend.frameon": False})


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bootstrap(values, statistic=np.mean):
    """(estimate, low, high) for a statistic over the rows of values."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(RNG_SEED)
    draws = [statistic(values[rng.integers(0, len(values), len(values))]) for _ in range(RESAMPLES)]
    return statistic(values), *np.percentile(draws, [2.5, 97.5], axis=0)


def ratio(pairs):
    """Pooled share: sum of disclosed over sum of total; the last axis holds (disclosed, total)."""
    return pairs[..., 0].sum(axis=0) / pairs[..., 1].sum(axis=0)


def sensitive_share(row):
    disclosed, total = map(int, row["sensitive_disclosed"].split("/"))
    return (disclosed, total) if total else None


def style(axis, grid="x"):
    """Hairline grid on the value axis, no frame."""
    axis.grid(axis=grid, color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    for spine in axis.spines.values():
        spine.set_visible(False)


def save(figure, folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        figure.savefig(folder / f"{name}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(figure)


def dot_panel(axis, rows, positions, colour, marker="o"):
    """Dot with a 95% interval line; rows are (estimate, low, high)."""
    for y, (estimate, low, high) in zip(positions, rows):
        axis.plot([low, high], [y, y], color=colour, linewidth=2, solid_capstyle="round", zorder=2)
        axis.plot(estimate, y, marker=marker, markersize=7.5, color=colour, markeredgecolor=SURFACE,
                  markeredgewidth=1.5, zorder=3)


def set_range(axis, limits, right):
    """1-5 rating scales keep their full range; counts start at zero, with a margin so zero markers are not cut."""
    if limits:
        axis.set_xlim(limits[0] - 0.2, limits[1] + 0.2)
        axis.set_xticks(range(limits[0], limits[1] + 1))
    else:
        axis.set_xlim(-0.04 * right, right)


def model_figure(conversations, folder):
    """RQ1: speech and grounding per patient model."""
    panels = [("words_per_reply", "Words\nper reply", None),
              ("realism_spoken_naturalness", "Spoken\nnaturalness (1-5)", (1, 5)),
              ("realism_conversational_fit", "Conversational\nfit (1-5)", (1, 5)),
              ("raw_medical_inventions", "Checker: inventions\nbefore repair", None),
              ("unsupported_additions", "Judge: unsupported\nadditions", None)]
    figure, axes = plt.subplots(1, len(panels), figsize=(7.4, 2.0), sharey=True)
    for axis, (key, title, limits) in zip(axes, panels):
        rows = [bootstrap([number(r[key]) for r in conversations
                           if r["patient_model"] == model and number(r[key]) is not None]) for model, _ in MODELS]
        dot_panel(axis, rows, range(len(MODELS)), NEUTRAL_DOT)
        for y, (estimate, _, high) in enumerate(rows):
            axis.annotate(f"{estimate:.1f}" if estimate >= 1 else f"{estimate:.2f}", (high, y), xytext=(5, 0),
                          textcoords="offset points", va="center", fontsize=8, color=INK)
        axis.set_title(title, fontsize=8.5)
        set_range(axis, limits, max(high for _, _, high in rows) * 1.35)
        style(axis)
    axes[0].set_yticks(range(len(MODELS)), [label for _, label in MODELS], color=INK)
    axes[0].set_ylim(len(MODELS) - 0.4, -0.6)
    figure.tight_layout(w_pad=1.2)
    save(figure, folder, "fig1_models")


def profile_figure(conversations, panels, name, folder):
    """Dot plot per profile and model: colour is the trait level, the marker is the model."""
    figure, axes = plt.subplots(1, len(panels), figsize=(7.4, 3.1), sharey=True)
    markers = ["o", "D"]
    for axis, (key, title) in zip(axes, panels):
        right = 0
        for m, (model, _) in enumerate(MODELS):
            for p, (profile, _, colour) in enumerate(PROFILES):
                mine = [r for r in conversations if r["patient_model"] == model and r["profile"] == profile]
                if key == "sensitive_pct":
                    pairs = [s for s in map(sensitive_share, mine) if s]
                    estimate, low, high = (100 * v for v in bootstrap(pairs, ratio))
                else:
                    estimate, low, high = bootstrap([number(r[key]) for r in mine if number(r[key]) is not None])
                dot_panel(axis, [(estimate, low, high)], [p + (m - 0.5) * 0.36], colour, markers[m])
                right = max(right, high)
        axis.set_title(title, fontsize=8.5)
        set_range(axis, (1, 5) if "(1-5)" in title else None, 105 if key == "sensitive_pct" else right * 1.1 + 0.05)
        style(axis)
    axes[0].set_yticks(range(len(PROFILES)), [label for _, label, _ in PROFILES], color=INK)
    axes[0].set_ylim(len(PROFILES) - 0.45, -0.55)
    for p in (0.5, 2.5, 4.5):  # separate moderate | N | A | O
        for axis in axes:
            axis.axhline(p, color=GRID, linewidth=0.8)
    handles = [Line2D([], [], marker=markers[m], linestyle="", color=NEUTRAL_DOT, markersize=6.5, label=label)
               for m, (_, label) in enumerate(MODELS)]
    handles += [Line2D([], [], marker="s", linestyle="", color=colour, markersize=6.5, label=label)
                for label, colour in (("High", HIGH), ("Moderate", MODERATE), ("Low", LOW))]
    figure.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.07), ncol=5, fontsize=8, handletextpad=0.3,
                  columnspacing=1.4, labelcolor=INK_2)
    figure.tight_layout(w_pad=1.2)
    save(figure, folder, name)


def trait_groups(trait):
    """Profiles drawn for a trait: high (if in the design), moderate and low."""
    _, high, low = trait
    return ([(high, HIGH)] if high else []) + [("b5_moderate", MODERATE), (low, LOW)]


def per_run(turns, key):
    """Run id -> (model, profile, array of the measure over turns 1..15)."""
    runs = collections.defaultdict(dict)
    meta = {}
    for r in turns:
        runs[r["run_id"] + r["patient_model"]][int(r["turn"])] = number(r[key])
        meta[r["run_id"] + r["patient_model"]] = (r["patient_model"], r["profile"])
    return {run: (*meta[run], np.array([values.get(t, np.nan) for t in range(1, 16)])) for run, values in runs.items()}


def curve(axis, series, colour, label):
    estimate, low, high = series
    turns = np.arange(1, 16)
    axis.fill_between(turns, low, high, color=colour, alpha=0.1, linewidth=0)
    axis.plot(turns, estimate, color=colour, linestyle=DASH[colour], linewidth=2, solid_capstyle="round",
              dash_capstyle="round", label=label)


def disclosure_figure(turns, folder):
    """RQ2: cumulative share of sensitive facts disclosed by turn, per trait and model."""
    disclosed, total = per_run(turns, "sensitive_so_far"), per_run(turns, "sensitive_total")
    figure, axes = plt.subplots(len(MODELS), len(TRAITS), figsize=(7.4, 4.0), sharex=True, sharey=True)
    for i, (model, model_label) in enumerate(MODELS):
        for j, trait in enumerate(TRAITS):
            axis = axes[i][j]
            for profile, colour in trait_groups(trait):
                runs = [run for run, (m, p, values) in total.items() if m == model and p == profile and values[0] > 0]
                stacked = np.stack([np.stack([disclosed[run][2], total[run][2]], axis=1) for run in runs])
                curve(axis, [100 * v for v in bootstrap(stacked, ratio)], colour, LABEL[profile])
            axis.set_title(trait[0] if i == 0 else "", fontsize=9)
            axis.set_ylim(0, 102)
            axis.set_xlim(1, 15)
            axis.set_xticks([1, 5, 10, 15])
            style(axis, "y")
            if j == 0:
                axis.set_ylabel(f"{model_label}\ndisclosed (%)", color=INK_2)
            if i == len(MODELS) - 1:
                axis.set_xlabel("Turn")
    level_legend(figure)
    figure.tight_layout(h_pad=1.0, w_pad=1.0)
    save(figure, folder, "fig2_sensitive_timing")


def level_legend(figure):
    handles = [Line2D([], [], color=colour, linestyle=DASH[colour], linewidth=2, label=label)
               for label, colour in (("High", HIGH), ("Moderate", MODERATE), ("Low", LOW))]
    figure.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.0, 1.04), ncol=3, fontsize=8, labelcolor=INK_2)


def trajectory_figure(turns, folder):
    """RQ3: logged anxiety (neuroticism profiles) and trust (agreeableness profiles) per turn."""
    rows = [("anxiety", "Anxiety", TRAITS[0]), ("trust", "Trust", TRAITS[1])]
    figure, axes = plt.subplots(len(rows), len(MODELS), figsize=(7.4, 4.0), sharex=True, sharey=True)
    for i, (key, label, trait) in enumerate(rows):
        runs = per_run(turns, key)
        for j, (model, model_label) in enumerate(MODELS):
            axis = axes[i][j]
            for profile, colour in trait_groups(trait):
                stacked = np.stack([values for m, p, values in runs.values() if m == model and p == profile])
                curve(axis, bootstrap(stacked, lambda v: v.mean(axis=0)), colour, LABEL[profile])
            axis.set_title(model_label if i == 0 else "", fontsize=9)
            axis.set_ylim(1, 5)
            axis.set_yticks([1, 2, 3, 4, 5])
            axis.set_xlim(1, 15)
            axis.set_xticks([1, 5, 10, 15])
            for edge in (5.5, 10.5):  # analysis windows 1-5, 6-10, 11-15
                axis.axvline(edge, color=GRID, linewidth=0.8)
            if i == 0:
                for first, last in WINDOWS:
                    axis.text((first + last) / 2, 1.15, f"turns {first}-{last}", ha="center", va="bottom",
                              fontsize=7.5, color=INK_2)
            style(axis, "y")
            if j == 0:
                axis.set_ylabel(f"{label} (1-5)\n{trait[0].lower()} profiles", color=INK_2)
            if i == len(rows) - 1:
                axis.set_xlabel("Turn")
    level_legend(figure)
    figure.tight_layout(h_pad=1.0, w_pad=1.0)
    save(figure, folder, "fig5_state_trajectories")


def plan_figure(matrix, folder):
    """RQ2: planned action against what the judge observed, row shares per model."""
    planned = ["disclose", "hint", "withhold", "deny", "volunteer"]
    observed = ["disclosed", "hinted", "denied", "not said"]
    colours = LinearSegmentedColormap.from_list("blue", ["#f0efec", "#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
    figure, axes = plt.subplots(1, len(MODELS), figsize=(7.4, 2.6), sharey=True)
    for axis, (model, model_label) in zip(axes, MODELS):
        counts = collections.Counter()
        for r in matrix:
            if r["patient_model"] == model and r["condition"] == "plan":
                counts[r["planned"], r["observed"]] += int(r["count"])
        grid = np.array([[counts[a, o] for o in observed] for a in planned], dtype=float)
        totals = grid.sum(axis=1)
        shares = 100 * grid / np.where(totals[:, None] > 0, totals[:, None], 1)
        axis.imshow(shares, cmap=colours, vmin=0, vmax=100, aspect="auto")
        for a in range(len(planned)):
            for o in range(len(observed)):
                axis.text(o, a, f"{shares[a, o]:.0f}", ha="center", va="center", fontsize=8,
                          color="#ffffff" if shares[a, o] > 55 else INK)
            axis.text(len(observed) - 0.45, a, f"n={int(totals[a])}", ha="left", va="center", fontsize=7.5, color=INK_2)
        for a, o in enumerate([0, 1, 3, 2, 0]):  # observed outcome that matches the plan
            axis.add_patch(Rectangle((o - 0.5, a - 0.5), 1, 1, fill=False, edgecolor=INK, linewidth=1.2))
        axis.set_xticks(range(len(observed)), observed)
        axis.set_yticks(range(len(planned)), planned, color=INK)
        axis.set_title(f"{model_label} (row %)", fontsize=9)
        axis.set_xlabel("Observed (judge)")
        for spine in axis.spines.values():
            spine.set_visible(False)
    axes[0].set_ylabel("Planned", color=INK_2)
    figure.tight_layout(w_pad=4.5)
    save(figure, folder, "fig6_plan_vs_observed")


def paired(conversations, model, first, second, value):
    """Differences first - second over (case, seed) pairs of one model."""
    keyed = {(r["case"], r["seed"], r["profile"]): r for r in conversations if r["patient_model"] == model}
    diffs = []
    for (case, seed, profile), row in keyed.items():
        other = keyed.get((case, seed, second))
        if profile == first and other and value(row) is not None and value(other) is not None:
            diffs.append(value(row) - value(other))
    return diffs


def effect_table(conversations):
    def column(key):
        return lambda r: number(r[key])

    def share(r):
        s = sensitive_share(r)
        return 100 * s[0] / s[1] if s else None

    effects = [("N high - N low", "b5_N_high", "b5_N_low",
                [("Anxiety (1-5)", column("anxiety_mean")), ("Worry (turns)", column("turns_affect/worry")),
                 ("Sensitive disclosed (%)", share), ("Asked, not disclosed", column("asked_not_disclosed"))]),
               ("A high - A low", "b5_A_high", "b5_A_low",
                [("Trust (1-5)", column("trust_mean")),
                 ("Challenge (turns)", column("turns_interaction_stance/challenge")),
                 ("Sensitive disclosed (%)", share), ("Asked, not disclosed", column("asked_not_disclosed")),
                 ("Planned withholds", column("plan_withhold"))]),
               ("O low - moderate", "b5_O_low", "b5_moderate",
                [("Words per reply", column("words_per_reply")),
                 ("Unasked content (turns)", column("turns_unasked_content")),
                 ("First sensitive disclosure (turn)", column("first_sensitive_disclosure")),
                 ("Sensitive disclosed (%)", share)])]
    lines = ["## Paired trait effects", "",
             "Mean difference over (case, seed) pairs with a 95% bootstrap interval; n = number of pairs.", "",
             "| Comparison | Measure | " + " | ".join(label for _, label in MODELS) + " |",
             "|---|---|" + "---|" * len(MODELS)]
    for name, first, second, measures in effects:
        for label, value in measures:
            cells = []
            for model, _ in MODELS:
                diffs = paired(conversations, model, first, second, value)
                estimate, low, high = bootstrap(diffs)
                cells.append(f"{estimate:+.2f} [{low:+.2f}, {high:+.2f}] (n={len(diffs)})")
            lines.append(f"| {name} | {label} | " + " | ".join(cells) + " |")
    return lines


def drift_table(turns):
    """Gap high - low per window, paired by case and seed, for the logged states and worry."""
    lines = ["", "## State gaps per window (drift)", "",
             "Per conversation the measure is averaged within each window; "
             "the gap is the paired high - low difference.", "",
             "| Model | Measure | Turns 1-5 | Turns 6-10 | Turns 11-15 |", "|---|---|---|---|---|"]
    measures = (("anxiety", "Anxiety, N high - N low", TRAITS[0]),
                ("affect/worry", "Worry share, N high - N low", TRAITS[0]),
                ("trust", "Trust, A high - A low", TRAITS[1]))
    for model, model_label in MODELS:
        for key, label, (_, high, low) in measures:
            # (case, seed, profile) -> {turn: value}; the seed is read from the run folder name
            series = collections.defaultdict(dict)
            for r in turns:
                if r["patient_model"] == model and r["profile"] in (high, low):
                    seed = r["run_id"].split("__seed")[1][0]
                    series[r["case"], seed, r["profile"]][int(r["turn"])] = number(r[key])
            cells = []
            for first, last in WINDOWS:
                def window_mean(values):
                    return np.mean([values[t] for t in range(first, last + 1) if values.get(t) is not None])
                diffs = [window_mean(values) - window_mean(series[case, seed, low])
                         for (case, seed, profile), values in list(series.items())
                         if profile == high and (case, seed, low) in series]
                estimate, lo, hi = bootstrap(diffs)
                cells.append(f"{estimate:+.2f} [{lo:+.2f}, {hi:+.2f}]")
            lines.append(f"| {model_label} | {label} | " + " | ".join(cells) + " |")
    return lines


def mean_of(rows, key, digits=2):
    values = [number(r[key]) for r in rows if number(r[key]) is not None]
    return f"{np.mean(values):.{digits}f}"


def total_of(rows, key):
    return str(sum(int(r[key]) for r in rows))


def sensitive_count(rows):
    disclosed, total = np.sum([s for s in map(sensitive_share, rows) if s], axis=0)
    return f"{disclosed}/{total}"


def overview_tables(conversations):
    lines = ["# Part 2 results", "", "## Overview per patient model", "",
             "| Measure | " + " | ".join(label for _, label in MODELS) + " |", "|---|" + "---|" * len(MODELS)]
    measures = [
        ("Conversations", lambda rows: str(len(rows))),
        ("Words per reply", lambda rows: mean_of(rows, "words_per_reply", 1)),
        ("Medical inventions before repair (per conversation)", lambda rows: mean_of(rows, "raw_medical_inventions")),
        ("Repaired turns (per conversation)", lambda rows: mean_of(rows, "repaired_turns")),
        ("Turns where repair failed (total)", lambda rows: total_of(rows, "repair_failed_turns")),
        ("Unsupported additions, judge (per conversation)", lambda rows: mean_of(rows, "unsupported_additions")),
        ("Spoken naturalness (1-5)", lambda rows: mean_of(rows, "realism_spoken_naturalness")),
        ("Conversational fit (1-5)", lambda rows: mean_of(rows, "realism_conversational_fit")),
        ("Sensitive facts disclosed by turn 15", sensitive_count),
        ("Change judge: stable / adapting / drifting",
         lambda rows: " / ".join(str(sum(r["change_overall"] == label for r in rows))
                                 for label in ("stable", "adapting", "drifting"))),
        ("Changes motivated / unmotivated",
         lambda rows: f"{total_of(rows, 'changes_motivated')} / {total_of(rows, 'changes_unmotivated')}")]
    for label, compute in measures:
        cells = [compute([r for r in conversations if r["patient_model"] == model]) for model, _ in MODELS]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    columns = [("sensitive_disclosed", "Sensitive disclosed"), ("first_sensitive_disclosure", "First sensitive (turn)"),
               ("asked_not_disclosed", "Asked, not disclosed"), ("denied", "Denied"),
               ("plan_withhold", "Planned withholds"), ("trust_mean", "Trust"), ("anxiety_mean", "Anxiety"),
               ("turns_affect/worry", "Worry (turns)"), ("turns_interaction_stance/challenge", "Challenge (turns)"),
               ("words_per_reply", "Words / reply")]
    for model, model_label in MODELS:
        lines += ["", f"## {model_label} by profile (mean per conversation, 16 conversations each)", "",
                  "| Profile | " + " | ".join(label for _, label in columns) + " |", "|---|" + "---|" * len(columns)]
        for profile, label, _ in PROFILES:
            rows = [r for r in conversations if r["patient_model"] == model and r["profile"] == profile]
            cells = [sensitive_count(rows) if key == "sensitive_disclosed" else mean_of(rows, key)
                     for key, _ in columns]
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return lines


def behavior_tables(conversations):
    """All seven categories, counted once per turn, for Markdown and the thesis appendix."""
    categories = [("affect", "Emotional expression"), ("patient_question", "Questions to the doctor"),
                  ("interaction_stance", "Interaction stance"), ("own_interpretation", "Own interpretation"),
                  ("unasked_content", "Unasked content"), ("reporting_style", "Reporting style"),
                  ("care_engagement", "Care engagement")]
    markdown = ["", "## All behavior categories", "",
                "Mean assessed turns per consultation; each category counts at most once per turn. "
                "Categories can overlap. The conversations CSV records the number of assessed behavior turns."]
    latex = []
    for model, model_label in MODELS:
        headers = [label for _, label, _ in PROFILES]
        markdown += ["", f"### {model_label}", "", "| Category | " + " | ".join(headers) + " |",
                     "|---|" + "---|" * len(headers)]
        latex += [r"\textbf{" + model_label + r"}\par\smallskip",
                  r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lrrrrrr@{}}", r"\toprule",
                  "Category & " + " & ".join(headers) + r" \\", r"\midrule"]
        for key, label in categories:
            cells = [mean_of([r for r in conversations if r["patient_model"] == model and r["profile"] == profile],
                             f"turns_{key}") for profile, _, _ in PROFILES]
            markdown.append("| " + label + " | " + " | ".join(cells) + " |")
            latex.append(label + " & " + " & ".join(cells) + r" \\")
        latex += [r"\bottomrule", r"\end{tabular*}", r"\par\medskip"]
    return markdown, latex


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--analysis", type=Path, default=ROOT / "outputs/Part2_ANALYSIS")
    args = parser.parse_args()
    conversations = read(args.analysis / "conversations.csv")
    turns = read(args.analysis / "turns.csv")
    matrix = read(args.analysis / "plan_vs_observed.csv")
    figures = args.analysis / "figures"
    model_figure(conversations, figures)
    disclosure_figure(turns, figures)
    profile_figure(conversations, [("sensitive_pct", "Sensitive facts disclosed (%)"),
                                   ("asked_not_disclosed", "Asked, not yet\ndisclosed"), ("denied", "Denials"),
                                   ("plan_withhold", "Plan entries:\nwithhold")], "fig3_concealment", figures)
    profile_figure(conversations, [("anxiety_mean", "Anxiety (1-5)\nfrom plans"), ("turns_affect/worry", "Worry (turns)\nfrom judge"),
                                   ("trust_mean", "Trust (1-5)\nfrom plans"),
                                   ("turns_interaction_stance/challenge", "Challenge (turns)\nfrom judge")],
                   "fig4_expression", figures)
    trajectory_figure(turns, figures)
    plan_figure(matrix, figures)
    behaviors, latex = behavior_tables(conversations)
    lines = overview_tables(conversations) + behaviors + [""] + effect_table(conversations) + drift_table(turns)
    (args.analysis / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.analysis / "behavior_categories.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")
    print(f"{len(conversations)} conversations -> {figures} and {args.analysis / 'tables.md'}")


if __name__ == "__main__":
    main()
