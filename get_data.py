"""Download House LD-2 quarterly XML filings and count AI-issue lobbyists.

Replicates (and extends) Public Citizen's "Generative Influence" (Feb 2026)
count of lobbyists reporting AI-related lobbying, using the House Clerk's
quarterly XML bulk files:

    https://disclosurespreview.house.gov/data/LD/<YEAR>_<N>Quarter_XML.zip

Each ZIP holds one XML per LD-2 report (originals, amendments, terminations).
A lobbyist counts as an AI lobbyist in a quarter if they are listed under an
issue section ("ali_info") whose free-text description matches one of the
keyword patterns below.

Outputs (in data/):
    ai_lobbyist_rows.csv     one row per AI lobbyist x filing section
    ai_by_quarter.csv        counts per quarter, plus AI lobbyists per client
    ai_by_year.csv           counts per year (each lobbyist counted once/year)

Usage:
    python get_data.py            # download missing/changed ZIPs, then parse
    python get_data.py --no-download
"""

import argparse
import csv
import re
import statistics
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

BASE_URL = "https://disclosurespreview.house.gov/data/LD/"
RAW_DIR = Path("data/raw")
OUT_DIR = Path("data")

FIRST_YEAR = 2020
# Last quarter with a complete filing set; later quarters are flagged partial.
LAST_COMPLETE = (2026, 2)
# Last quarter to download at all (Q3 2026 LD-2s are due Oct 20, 2026).
LAST_QUARTER = (2026, 3)

ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}

# Keyword groups, following Public Citizen's methodology: AI and its variants,
# autonomous vehicles/systems, and data centers.
PATTERNS = {
    "ai": [
        re.compile(r"artificial[\s-]+intelligen", re.I),
        re.compile(r"\bA\.\s?I\.(?=\W|$)"),
        re.compile(r"\bAI\b"),  # case-sensitive on purpose
        re.compile(r"\bmachine[\s-]+learning\b", re.I),
        re.compile(r"\blarge[\s-]+language[\s-]+models?\b", re.I),
        re.compile(r"\bLLMs?\b"),
        re.compile(r"\bfacial[\s-]+recognition\b", re.I),
        re.compile(r"\bdeep[\s-]?fakes?\b", re.I),
    ],
    "autonomous": [
        re.compile(
            r"\bautonomous\s+(vehicle|system|driving|truck|weapon|aircraft|vessel)s?\b",
            re.I,
        ),
        re.compile(r"\bself[\s-]+driving\b", re.I),
        re.compile(r"\bautomated\s+(vehicle|driving)s?\b", re.I),
    ],
    "data_center": [
        re.compile(r"\bdata[\s-]?cent(er|re)s?\b", re.I),
    ],
}


def quarters():
    for year in range(FIRST_YEAR, LAST_QUARTER[0] + 1):
        for q in range(1, 5):
            if (year, q) <= LAST_QUARTER:
                yield year, q


def zip_name(year, q):
    return f"{year}_{ORDINAL[q]}Quarter_XML.zip"


def remote_size(url):
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return int(resp.headers.get("Content-Length", -1))


def download(year, q):
    """Fetch the quarter's ZIP unless a local copy of the same size exists."""
    name = zip_name(year, q)
    url = BASE_URL + name
    dest = RAW_DIR / name
    size = remote_size(url)
    if dest.exists() and dest.stat().st_size == size:
        print(f"  {name}: up to date ({size / 1e6:.0f} MB)")
        return dest
    print(f"  {name}: downloading {size / 1e6:.0f} MB ...", flush=True)
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)
    return dest


def text(el, tag):
    found = el.find(tag)
    return (found.text or "").strip() if found is not None else ""


def norm(s):
    s = re.sub(r"[^\w\s]", " ", s.upper())
    return re.sub(r"\s+", " ", s).strip()


def matched_groups(description):
    return [g for g, pats in PATTERNS.items() if any(p.search(description) for p in pats)]


def parse_filing(raw):
    """Return filing metadata and its sections as (description, [lobbyists])."""
    root = ET.fromstring(raw)
    registrant = text(root, "organizationName") or " ".join(
        x for x in (text(root, "firstName"), text(root, "lastName")) if x
    )
    meta = {
        "house_id": text(root, "houseID"),
        "report_year": text(root, "reportYear"),
        "report_type": text(root, "reportType"),
        "signed": text(root, "signedDate"),
        "registrant": registrant,
        "client": text(root, "clientName"),
    }
    sections = []
    for ali in root.iter("ali_info"):
        desc = " ".join(
            (d.text or "").strip() for d in ali.iter("description") if d.text
        )
        people = []
        for lob in ali.iter("lobbyist"):
            first, last = text(lob, "lobbyistFirstName"), text(lob, "lobbyistLastName")
            if first or last:
                people.append(norm(f"{first} {last}"))
        sections.append((desc, people))
    return meta, sections


def signed_key(s):
    """Sortable key for 'M/D/YYYY h:mm:ss AM' timestamps."""
    m = re.match(r"(\d+)/(\d+)/(\d{4})\s+(\d+):(\d+):(\d+)\s*([AP]M)?", s)
    if not m:
        return (0,)
    mo, d, y, h, mi, sec, ampm = m.groups()
    h = int(h) % 12 + (12 if ampm == "PM" else 0) if ampm else int(h)
    return (int(y), int(mo), int(d), h, int(mi), int(sec))


def parse_quarter(path, year, q):
    """Parse one ZIP; keep only the latest version of each registrant-client report."""
    latest = {}  # house_id -> (signed_key, filename, meta, sections)
    errors = 0
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".xml"):
                continue
            try:
                meta, sections = parse_filing(zf.read(info))
            except ET.ParseError:
                errors += 1
                continue
            if meta["report_year"] != str(year):
                continue
            key = meta["house_id"] or info.filename
            rank = (signed_key(meta["signed"]), info.filename)
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank, info.filename, meta, sections)

    rows, all_lobbyists = [], set()
    for _, fname, meta, sections in latest.values():
        for desc, people in sections:
            all_lobbyists.update(people)
            groups = matched_groups(desc)
            if not groups:
                continue
            for person in people:
                rows.append({
                    "year": year,
                    "quarter": q,
                    "file": fname,
                    "house_id": meta["house_id"],
                    "report_type": meta["report_type"],
                    "registrant": meta["registrant"],
                    "client": meta["client"],
                    "lobbyist": person,
                    "match_ai": int("ai" in groups),
                    "match_autonomous": int("autonomous" in groups),
                    "match_data_center": int("data_center" in groups),
                })
    print(f"  {path.name}: {len(latest):,} reports, {len(rows):,} AI lobbyist rows,"
          f" {errors} unparseable", flush=True)
    return rows, all_lobbyists


def per_client_stats(team):
    """Distribution of AI lobbyists per client: {client: set(lobbyists)} -> stats."""
    sizes = sorted(len(v) for v in team.values())
    q1, _, q3 = statistics.quantiles(sizes, n=4, method="inclusive")
    return {
        "per_client_median": float(statistics.median(sizes)),
        "per_client_p25": q1,
        "per_client_p75": q3,
        "per_client_mean": round(statistics.mean(sizes), 2),
    }


def summarize(rows, all_by_period):
    """Unique lobbyists, lobbyist-client pairs, clients, and team sizes per period."""
    def tally(period_of):
        acc = defaultdict(lambda: defaultdict(set))
        teams = defaultdict(lambda: defaultdict(set))
        for r in rows:
            p = period_of(r)
            # A client's AI team: everyone lobbying for it, in-house or via outside firms.
            teams[p][norm(r["client"])].add(r["lobbyist"])
            acc[p]["lobbyists"].add(r["lobbyist"])
            acc[p]["lobbyist_client_pairs"].add((r["lobbyist"], r["house_id"]))
            acc[p]["clients"].add(norm(r["client"]))
            if r["match_ai"]:
                acc[p]["lobbyists_ai_terms"].add(r["lobbyist"])
            if r["match_data_center"]:
                acc[p]["lobbyists_data_center"].add(r["lobbyist"])
        return acc, teams

    by_q, teams_q = tally(lambda r: (r["year"], r["quarter"]))
    by_y, teams_y = tally(lambda r: r["year"])
    fields = ["lobbyists", "lobbyists_ai_terms", "lobbyists_data_center",
              "lobbyist_client_pairs", "clients"]

    q_out = []
    for (y, q) in sorted(by_q):
        rec = {"year": y, "quarter": q, "period": f"{y} Q{q}"}
        rec.update({f: len(by_q[(y, q)][f]) for f in fields})
        rec.update(per_client_stats(teams_q[(y, q)]))
        rec["all_lobbyists"] = len(all_by_period[(y, q)])
        rec["partial"] = int((y, q) > LAST_COMPLETE)
        q_out.append(rec)

    y_out = []
    for y in sorted(by_y):
        rec = {"year": y}
        rec.update({f: len(by_y[y][f]) for f in fields})
        rec["all_lobbyists"] = len(set().union(
            *(v for (yy, _), v in all_by_period.items() if yy == y)))
        rec.update(per_client_stats(teams_y[y]))
        rec["partial"] = int((y, 4) > LAST_COMPLETE)
        y_out.append(rec)
    return q_out, y_out


def write_csv(path, records):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    print(f"wrote {path} ({len(records):,} rows)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-download", action="store_true",
                    help="parse ZIPs already in data/raw without checking the server")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows, all_by_period = [], {}
    for year, q in quarters():
        path = RAW_DIR / zip_name(year, q)
        if not args.no_download:
            path = download(year, q)
        if not path.exists():
            sys.exit(f"missing {path}; run without --no-download")
        q_rows, q_all = parse_quarter(path, year, q)
        rows.extend(q_rows)
        all_by_period[(year, q)] = q_all

    write_csv(OUT_DIR / "ai_lobbyist_rows.csv", rows)
    q_out, y_out = summarize(rows, all_by_period)
    write_csv(OUT_DIR / "ai_by_quarter.csv", q_out)
    write_csv(OUT_DIR / "ai_by_year.csv", y_out)


if __name__ == "__main__":
    main()
