"""Velocity chart: planned vs completed story points per sprint (docs/process/velocity.md).

Run: uv run --no-project --with matplotlib python scripts/velocity_chart.py docs/process/velocity.png
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1]
sprints = ["Sprint 0\n16–18 Oct", "Sprint 1\n19–25 Oct", "Sprint 2\n26 Oct–1 Nov", "Sprint 3\n2–8 Nov"]
planned = [12, 28, 31, 28]
completed = [0, 6, 65, 18]
avg = sum(completed) / len(completed)

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=300)
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

x = range(len(sprints))
w = 0.36
gap = 0.02  # surface gap between the paired bars
bp = ax.bar([i - w / 2 - gap for i in x], planned, w, color=ORANGE, label="Planned (sprint plan)", zorder=3)
bc = ax.bar([i + w / 2 + gap for i in x], completed, w, color=BLUE, label="Completed (met Definition of Done)", zorder=3)

for bars in (bp, bc):
    for b in bars:
        h = b.get_height()
        ax.text(
            b.get_x() + b.get_width() / 2,
            h + 1.2,
            f"{h:g}",
            ha="center",
            va="bottom",
            color=INK,
            fontsize=10,
            zorder=4,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5},
        )

ax.axhline(avg, color=INK2, lw=1.2, ls=(0, (5, 3)), zorder=2)
ax.text(
    -0.45,
    avg + 1.2,
    f"average {avg:.0f}",
    ha="left",
    va="bottom",
    color=INK2,
    fontsize=9.5,
    zorder=4,
    bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5},
)

ax.set_xticks(list(x))
ax.set_xticklabels(sprints, color=INK2)
ax.set_ylabel("Story points", color=INK2)
ax.set_ylim(0, 75)
ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
ax.tick_params(colors=MUTED, length=0)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.legend(frameon=False, loc="upper left", fontsize=9.5, labelcolor=INK2)
ax.set_title("POlaris velocity, Sprints 0–3", loc="left", color=INK, fontsize=12, fontweight="bold")
fig.tight_layout()
fig.savefig(OUT, facecolor=SURFACE)
print("wrote", OUT)
