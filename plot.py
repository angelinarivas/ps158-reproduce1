"""Plot AI-issue lobbyists by year and by quarter as a black-and-white journal figure.

Reads data/ai_by_year.csv and data/ai_by_quarter.csv (from get_data.py) and
writes figures/ai_lobbyists.pdf (vector) and figures/ai_lobbyists.png, with a
numbered caption and source note below the panels. Public Citizen's published
yearly totals (Generative Influence, Feb 2026, Table 1) are overlaid.
"""

import csv
import datetime as dt
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

DATA = Path("data")
OUT = Path("figures/ai_lobbyists")

FIGURE_NUMBER = 1

# Public Citizen, "Generative Influence" (Feb 2026), Table 1.
PUBLIC_CITIZEN = {2020: 1311, 2021: 1269, 2022: 1332, 2023: 2210, 2024: 3101, 2025: 3570}

BAR_GRAY = "0.72"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "axes.linewidth": 0.6,
    "hatch.linewidth": 0.5,
    "pdf.fonttype": 42,  # embed TrueType so text stays editable in the PDF
})


def read(path):
    with open(path) as fh:
        return [{k: (int(v) if v.lstrip("-").isdigit() else v) for k, v in r.items()}
                for r in csv.DictReader(fh)]


def style(ax, panel):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="x", length=0, pad=4)
    ax.tick_params(axis="y", length=3, width=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel("Lobbyists")
    ax.text(-0.08, 1.04, f"({panel})", transform=ax.transAxes, fontsize=10,
            fontweight="bold", va="bottom")


def bars(ax, xs, values, partial, width=0.8):
    for x, v, p in zip(xs, values, partial):
        ax.bar(x, v, width=width, color="white" if p else BAR_GRAY,
               edgecolor="black", linewidth=0.6, hatch="////" if p else None)


def main():
    years = read(DATA / "ai_by_year.csv")
    quarters = read(DATA / "ai_by_quarter.csv")
    retrieved = dt.date.fromtimestamp((DATA / "ai_by_quarter.csv").stat().st_mtime)
    partial_q = [r for r in quarters if r["partial"]]

    fig = plt.figure(figsize=(7, 6.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.1], hspace=0.42,
                          top=0.96, bottom=0.30, left=0.1, right=0.98)
    ax_y, ax_q = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    # (a) Yearly: each lobbyist counted once per year.
    xs = list(range(len(years)))
    bars(ax_y, xs, [r["lobbyists"] for r in years], [r["partial"] for r in years], width=0.7)
    for x, r in zip(xs, years):
        ax_y.annotate(f"{r['lobbyists']:,}", (x, r["lobbyists"]), xytext=(0, -6),
                      textcoords="offset points", ha="center", va="top", fontsize=8,
                      bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none")
                      if r["partial"] else None)
    pc = [(x, PUBLIC_CITIZEN[r["year"]]) for x, r in zip(xs, years) if r["year"] in PUBLIC_CITIZEN]
    ax_y.scatter([p[0] for p in pc], [p[1] for p in pc], s=22, marker="D", color="black",
                 edgecolor="white", linewidth=0.8, zorder=3,
                 label="Public Citizen (2026) published total")
    ax_y.set_xticks(xs, [str(r["year"]) + ("*" if r["partial"] else "") for r in years])
    handles, _ = ax_y.get_legend_handles_labels()
    handles.append(Patch(facecolor=BAR_GRAY, edgecolor="black", linewidth=0.6,
                         label="This study"))
    ax_y.legend(handles=handles, frameon=False, loc="upper left", fontsize=8,
                handlelength=1.2)
    style(ax_y, "a")

    # (b) Quarterly: each lobbyist counted in every quarter they appear.
    xs, ticks, ticklabels = [], [], []
    x = 0
    for i, r in enumerate(quarters):
        if i and r["quarter"] == 1:
            x += 0.7  # gap between years
        xs.append(x)
        if r["quarter"] == 1:
            ticks.append(x + 1.5)
            ticklabels.append(str(r["year"]))
        x += 1
    bars(ax_q, xs, [r["lobbyists"] for r in quarters], [r["partial"] for r in quarters])
    ax_q.set_xticks(ticks, ticklabels)
    ax_q.set_xlim(xs[0] - 0.8, xs[-1] + 0.8)
    style(ax_q, "b")

    partial_note = ""
    if partial_q:
        labels = ", ".join(f"Q{r['quarter']} {r['year']}" for r in partial_q)
        partial_note = (
            f" Hatched bars and asterisk mark incomplete periods: reports for {labels} "
            f"were not yet due when the data were retrieved on {retrieved:%B %-d, %Y}."
        )
    caption = (
        f"Figure {FIGURE_NUMBER}. Lobbyists reporting AI-related lobbying, 2020–2026. "
        "(a) Unique lobbyists per year, each counted once per year. "
        "(b) Unique lobbyists per quarter, each counted in every quarter in which they appear. "
        "Counts include lobbyists named in quarterly LD-2 report issue sections whose "
        "descriptions mention artificial intelligence (or a variant), autonomous vehicles "
        "or systems, or data centers; amended reports replace the originals. "
        "Diamonds show Public Citizen's published yearly totals." + partial_note
    )
    source = (
        "Source: Author's calculations from U.S. House of Representatives, Office of the "
        "Clerk, Lobbying Disclosure LD-2 XML files; Public Citizen, “Generative "
        "Influence” (February 2026), Table 1."
    )
    cap = fig.text(0.02, 0.215, textwrap.fill(caption, 130), fontsize=9, va="top",
                   linespacing=1.3)
    # Anchor the source note to the caption's bottom edge so they never overlap.
    fig.add_artist(plt.Annotation(textwrap.fill(source, 145), xy=(0, 0), xycoords=cap,
                                  xytext=(0, -6), textcoords="offset points", va="top",
                                  fontsize=8, style="italic", linespacing=1.3))

    OUT.parent.mkdir(exist_ok=True)
    for ext, kw in (("pdf", {}), ("png", {"dpi": 300})):
        fig.savefig(OUT.with_suffix(f".{ext}"), facecolor="white", bbox_inches="tight",
                    pad_inches=0.1, **kw)
        print(f"wrote {OUT.with_suffix(f'.{ext}')}")


if __name__ == "__main__":
    main()
