"""Plot AI-issue lobbyists by year and by quarter, 2020 through Q3 2026.

Reads data/ai_by_year.csv and data/ai_by_quarter.csv (from get_data.py) and
writes figures/ai_lobbyists.png. Public Citizen's published yearly totals
(Generative Influence, Feb 2026, Table 1) are overlaid for comparison.
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt

DATA = Path("data")
OUT = Path("figures/ai_lobbyists.png")

# Public Citizen, "Generative Influence" (Feb 2026), Table 1.
PUBLIC_CITIZEN = {2020: 1311, 2021: 1269, 2022: 1332, 2023: 2210, 2024: 3101, 2025: 3570}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"


def read(path):
    with open(path) as fh:
        return [{k: (int(v) if v.lstrip("-").isdigit() else v) for k, v in r.items()}
                for r in csv.DictReader(fh)]


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))


def bars(ax, xs, values, partial):
    for x, v, p in zip(xs, values, partial):
        ax.bar(x, v, width=0.8, color=SERIES_1, alpha=0.35 if p else 1.0,
               hatch="///" if p else None, edgecolor=SURFACE if not p else SERIES_1,
               linewidth=0 if not p else 0.8)


def main():
    years = read(DATA / "ai_by_year.csv")
    quarters = read(DATA / "ai_by_quarter.csv")

    fig, (ax_y, ax_q) = plt.subplots(
        2, 1, figsize=(11, 8), gridspec_kw={"height_ratios": [1, 1.15], "hspace": 0.45})
    fig.patch.set_facecolor(SURFACE)

    # Yearly: each lobbyist counted once per year.
    xs = list(range(len(years)))
    labels = [str(r["year"]) + ("\n(Q1–Q2 + partial Q3)" if r["partial"] else "")
              for r in years]
    bars(ax_y, xs, [r["lobbyists"] for r in years], [r["partial"] for r in years])
    for x, r in zip(xs, years):
        # Inside the bar top, so the Public Citizen marker at the same height stays clear.
        ax_y.annotate(f"{r['lobbyists']:,}", (x, r["lobbyists"]), xytext=(0, -12),
                      textcoords="offset points", ha="center", va="top",
                      fontsize=9, color=INK if r["partial"] else "white")
    pc = [(x, PUBLIC_CITIZEN[r["year"]]) for x, r in zip(xs, years) if r["year"] in PUBLIC_CITIZEN]
    ax_y.scatter([p[0] for p in pc], [p[1] for p in pc], s=60, marker="D", color=SERIES_2,
                 edgecolor=SURFACE, linewidth=2, zorder=3,
                 label="Public Citizen published total (Feb 2026)")
    ax_y.bar([], [], color=SERIES_1, label="This replication (House LD-2 XML)")
    ax_y.set_xticks(xs, labels)
    ax_y.set_title("By year", loc="left", fontsize=11, color=INK_2)
    ax_y.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK_2)
    style(ax_y)

    # Quarterly: each lobbyist counted in every quarter they appear.
    xs, ticks, ticklabels = [], [], []
    x = 0
    for i, r in enumerate(quarters):
        if i and r["quarter"] == 1:
            x += 0.6  # gap between years
        xs.append(x)
        if r["quarter"] == 1:
            ticks.append(x + 1.5)
            ticklabels.append(str(r["year"]))
        x += 1
    bars(ax_q, xs, [r["lobbyists"] for r in quarters], [r["partial"] for r in quarters])
    last = quarters[-1]
    if last["partial"]:
        ax_q.annotate(f"{last['lobbyists']:,}", (xs[-1], last["lobbyists"]), xytext=(0, 3),
                      textcoords="offset points", ha="center", va="bottom",
                      fontsize=8, color=INK_2)
    for xi, r in zip(xs, quarters):
        if r["quarter"] == 4 or (r is quarters[-2] and last["partial"]):
            ax_q.annotate(f"{r['lobbyists']:,}", (xi, r["lobbyists"]), xytext=(0, 3),
                          textcoords="offset points", ha="center", va="bottom",
                          fontsize=8, color=INK)
    ax_q.set_xticks(ticks, ticklabels)
    ax_q.set_title("By quarter (Q1–Q4 within each year)", loc="left", fontsize=11, color=INK_2)
    style(ax_q)

    fig.suptitle("Lobbyists reporting AI-related lobbying, 2020–2026", x=0.125, ha="left",
                 fontsize=15, color=INK, y=0.98)
    fig.text(0.125, 0.925,
             "Unique lobbyists named on LD-2 issue sections mentioning artificial intelligence, "
             "autonomous vehicles/systems, or data centers",
             fontsize=9.5, color=INK_2)
    fig.text(0.125, 0.02,
             "Source: U.S. House Clerk lobbying disclosure XML; method after Public Citizen, "
             "“Generative Influence” (Feb 2026).\nHatched = incomplete period: Q3 2026 LD-2 reports "
             "are due Oct 20, 2026, so most were not yet filed when the data were downloaded.",
             fontsize=8, color=INK_2)

    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=200, facecolor=SURFACE)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
