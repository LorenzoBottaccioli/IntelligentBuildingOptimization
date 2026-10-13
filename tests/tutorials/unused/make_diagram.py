"""Draws the workflow figure of the tutorials: tutorials/image/bdopt_workflow.png

Run where matplotlib is (image B):

    docker run --rm -v "$PWD:/repo" --entrypoint python jupyter:smartbuilding-surrogate /repo/tests/tutorials/make_diagram.py

Every name written in the figure is a name that exists in bdopt 0.2.0 (checked by the tutorials themselves).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[2] / "tutorials" / "image" / "bdopt_workflow.png"

BLUE, BLUE_DARK, GREY, ORANGE = "#2f6db5", "#1d4a82", "#5b6573", "#d9822b"
STEPS = [
    ("1", "Model", ".idf + .epw", "load_idf", 1),
    ("2", "Problem", "parameters\n+ objectives", "Parameter, FieldSelector,\nRangeParameter, Problem", 1),
    ("3", "Samples", "designs to\nsimulate", "sampling.lhs, sobol,\nhalton, factorial", 1),
    ("4", "Simulate", "dataset: designs\n+ results", "EnergyPlusEvaluator", 2),
    ("5", "Surrogate", "fit and check on\nunseen designs", "make_surrogate,\nGPSurrogate, MLPSurrogate,\nviz.parity", 2),
    ("6", "Optimise", "Pareto front\nof designs", "nsga2, closest_to_ideal,\nviz.pareto", 3),
    ("7", "Verify", "simulate the\nchosen design", "problem.apply,\nEnergyPlusEvaluator", 3),
]
NOTEBOOKS = {1: "1 · bdopt overview", 2: "2 · surrogate modelling", 3: "3 · optimization"}


def main():
    fig, ax = plt.subplots(figsize=(17.2, 5.8))
    ax.set_xlim(0, 17.2)
    ax.set_ylim(0, 5.8)
    ax.axis("off")
    w, h, gap, x0 = 2.1, 1.5, 0.3, 0.3
    y = 2.3
    centres = []
    for i, (num, title, sub, api, nb) in enumerate(STEPS):
        x = x0 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=BLUE, ec=BLUE_DARK, lw=1.5))
        ax.text(x + 0.14, y + h - 0.16, num, color="white", fontsize=11, fontweight="bold", va="top")
        ax.text(x + w / 2, y + h - 0.45, title, color="white", fontsize=14, fontweight="bold", ha="center", va="center")
        ax.text(x + w / 2, y + 0.42, sub, color="white", fontsize=10.5, ha="center", va="center", linespacing=1.15)
        ax.text(x + w / 2, y - 0.2, api, color=GREY, fontsize=9, ha="center", va="top", family="monospace", linespacing=1.25)
        centres.append((x, x + w, nb))
        if i:
            ax.add_patch(FancyArrowPatch((x - gap, y + h / 2), (x, y + h / 2), arrowstyle="-|>", mutation_scale=16, color=BLUE_DARK, lw=1.6))
    # the notebooks that cover each group of steps: two rows, because notebook 2 runs its own samples (3-4) before the surrogate
    brackets = [("1 · bdopt overview", 0, 3, 0), ("2 · surrogate modelling", 2, 4, 1), ("3 · optimization", 5, 6, 0)]
    for label, first, last, row in brackets:
        left, right = centres[first][0], centres[last][1]
        base = y + h + 0.2 + row * 0.75
        ax.plot([left, left, right, right], [base, base + 0.14, base + 0.14, base], color=ORANGE, lw=2)
        ax.text((left + right) / 2, base + 0.22, label, color=ORANGE, fontsize=12.5, fontweight="bold", ha="center", va="bottom")
    # the loop: where the surrogate is not good enough, simulate more designs (step 5 back to step 3)
    a, b, low = centres[4][0] + w / 2, centres[2][0] + w / 2, 0.6
    ax.plot([a, a, b], [y - 1.05, low, low], color=GREY, lw=1.4, linestyle=(0, (5, 3)))
    ax.add_patch(FancyArrowPatch((b, low), (b, y - 1.05), arrowstyle="-|>", mutation_scale=14, color=GREY, lw=1.4))
    ax.text((a + b) / 2, low - 0.08, "where the surrogate is not good enough, simulate more designs (bdopt.adaptive.AdaptiveSampler)",
            color=GREY, fontsize=10, ha="center", va="top", style="italic")
    fig.savefig(OUT, dpi=130, bbox_inches="tight", facecolor="white")
    print("written", OUT)


if __name__ == "__main__":
    main()
