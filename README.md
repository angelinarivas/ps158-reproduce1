# AI lobbying, 2020–2026

Replicates and extends Public Citizen's count of federal lobbyists working on
AI issues ("Generative Influence", February 2026), from 2020 through Q2 2026. One thing I would do next is to update it after the Q3 2026 reports are in after October 20th so that the last quarter could be complete. 

## Figures

- **Figure 1** (`figures/ai_lobbyists.pdf`, `.png`): unique AI lobbyists per
  year and per quarter, with Public Citizen's published yearly totals overlaid.
  Our yearly totals are within 2% of theirs for 2020–2025.
- **Figure 2** (`figures/ai_lobbyists_median.pdf`, `.png`): median AI lobbyists
  per client, with interquartile range and mean. The median stays at 3; the
  growth in Figure 1 comes from more clients, not larger teams.

Q3 2026 is shown hatched as incomplete: those reports were due October 20, 2026,
after the data were downloaded.

## Data

LD-2 quarterly lobbying reports from the U.S. House Clerk, downloaded as one
XML ZIP per quarter from
`https://disclosurespreview.house.gov/data/LD/<YEAR>_<N>Quarter_XML.zip`
(about 1.1 GB for 2020 Q1–2026 Q3).

A lobbyist counts as an AI lobbyist when they are named in a report's issue
section whose description mentions artificial intelligence (or a variant such as
"AI", machine learning or facial recognition), autonomous vehicles or systems,
or data centers. When a report was amended, only the latest version is kept.
Lobbyists are matched by name, since the XML has no lobbyist ID.

Outputs in `data/`:

| File | Contents |
|---|---|
| `ai_by_quarter.csv` | Counts and per-client statistics per quarter |
| `ai_by_year.csv` | The same per year, each lobbyist counted once per year |
| `ai_lobbyist_rows.csv` | One row per AI lobbyist per filing section |

The raw ZIPs go in `data/raw/`, which is not tracked by git.

## Rerun

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python get_data.py
.venv/bin/python plot.py
```

`get_data.py` re-downloads a ZIP only if its size on the server has changed, so
rerunning it after October 20, 2026 picks up the rest of Q3 2026. Use
`--no-download` to re-parse the ZIPs already in `data/raw/`. `plot.py` draws
both figures; `--stat count` or `--stat median` draws just one.

To extend the series, edit `LAST_COMPLETE` and `LAST_QUARTER` at the top of
`get_data.py`.

## Source

Public Citizen, "Generative Influence" (February 2026),
<https://www.citizen.org/article/generative-influence/>.
