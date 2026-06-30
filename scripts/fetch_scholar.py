#!/usr/bin/env python3
"""
Fetch Google Scholar citations and aggregate them into per-year × per-field
intensity for the site's citation heatmap.

Output: _data/citations.json  (read by lab.html via Jekyll `site.data.citations`)

Usage:
    python3 -m pip install scholarly        # one-time
    python3 scripts/fetch_scholar.py        # full run
    python3 scripts/fetch_scholar.py --limit 5   # quick smoke test

Notes:
- Google Scholar has no official API and rate-limits aggressively. This script
  fills each publication to read its per-year citation series (`cites_per_year`).
  Raw results are cached in scripts/.scholar_cache.json so reruns are cheap and
  you don't re-hit Scholar.
- If a publication exposes no per-year series, its lifetime total is spread over
  time with a standard citation-aging curve as a fallback.
- If the whole fetch is blocked (CAPTCHA), the page keeps using its built-in
  illustrative model, so the site never breaks.
"""
import argparse, json, os, sys, time
from pathlib import Path

AUTHOR_ID = "8qiZ3zMAAAAJ"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_data" / "citations.json"
CACHE = Path(__file__).resolve().parent / ".scholar_cache.json"
Y0, Y1 = 2008, 2026

# Ordered field rules — FIRST match wins. Keep names identical to THEMES in lab.html.
FIELD_RULES = [
    ("Hackathons & open innovation",
     ["hackathon", "diplomacy", "open geneva", "play and work", "for good", "participatory"]),
    ("Technology forecasting & scientometrics",
     ["forecast", "techrank", "scientometric", "carrying capacity", "carrying-capacity",
      "convergence", "patent", "labor needs", "link prediction", "text mining",
      "future cyberdefense", "market monitoring", "arxiv", "anticipating", "development in information technolog"]),
    ("Privacy, surveillance & neuro-rights",
     ["privacy", "surveillance", "thought", "brain", "mind reading", "purchase data",
      "caviar", "erosion of privacy", "thoughts"]),
    ("Social interaction & digital phenotyping",
     ["autism", "pose", "video-audio", "video based", "sleep", "haptic", "physiological",
      "bio-sensory", "biosensory", "phenotyping", "social scene", "theory of mind",
      "social interaction", "screening", "multimodal"]),
    ("Cyber risks & resilience",
     ["cyber", "security", "bug bount", "breach", "insurance", "economics of information",
      "weis", "resilience", "attack", "incentive", "investment"]),
    ("Collective intelligence & open source",
     ["open source", "linux", "zipf", "superlinear", "wikipedia", "collective intelligence",
      "prediction market", "productive burst", "co-located", "collaboration", "aristotle",
      "ringelmann", "whole really more", "commons", "license", "knowledge production", "eyeballs",
      "collective action", "sustainability", "betterment", "artificial intelligence"]),
    ("Complex systems & human dynamics",
     ["heavy-tail", "heavy tail", "self-excited", "epidemic", "rationality", "human dynamics",
      "nuclear", "safety", "entropy", "scale-free", "complex", "coping with crises",
      "deviations", "stability"]),
]
FALLBACK_FIELD = "Complex systems & human dynamics"

# citation-aging curve (fraction of total citations by paper-age in years), used only
# when a paper has no per-year series. Roughly: ramp up over ~5y, long tail.
AGE_CURVE = [0.02, 0.07, 0.13, 0.16, 0.15, 0.12, 0.10, 0.08, 0.06, 0.04, 0.03, 0.02, 0.02]


def classify_all(title):
    """Return EVERY field whose keywords match — a paper can count in several."""
    t = (title or "").lower()
    hits = [field for field, kws in FIELD_RULES if any(k in t for k in kws)]
    return hits


def spread_total_over_years(total, pub_year):
    """Fallback: distribute a lifetime total across years via the aging curve."""
    out = {}
    for age, frac in enumerate(AGE_CURVE):
        y = pub_year + age
        if Y0 <= y <= Y1:
            out[y] = out.get(y, 0) + total * frac
    return out


def fetch_raw(limit=None):
    """Return list of {title, year, total, per_year:{year:cites}} via scholarly, cached."""
    if CACHE.exists():
        print(f"• using cache {CACHE}")
        return json.loads(CACHE.read_text())
    try:
        from scholarly import scholarly
    except ImportError:
        sys.exit("scholarly not installed → run: python3 -m pip install scholarly")

    print(f"• querying author {AUTHOR_ID} …")
    author = scholarly.search_author_id(AUTHOR_ID)
    author = scholarly.fill(author, sections=["publications"])
    pubs = author.get("publications", [])
    if limit:
        pubs = pubs[:limit]
    print(f"• {len(pubs)} publications; filling per-year citations (this is slow)…")

    raw = []
    for i, p in enumerate(pubs, 1):
        try:
            scholarly.fill(p)
        except Exception as e:
            print(f"  ! fill failed on #{i}: {e}")
        bib = p.get("bib", {})
        raw.append({
            "title": bib.get("title", ""),
            "year": int(bib.get("pub_year")) if str(bib.get("pub_year", "")).isdigit() else None,
            "total": int(p.get("num_citations", 0) or 0),
            "per_year": {int(y): int(c) for y, c in (p.get("cites_per_year") or {}).items()},
        })
        print(f"  [{i}/{len(pubs)}] {raw[-1]['title'][:60]} … {raw[-1]['total']} cites")
        time.sleep(1.0)  # be polite

    CACHE.write_text(json.dumps(raw, indent=2))
    print(f"• cached raw → {CACHE}")
    return raw


def aggregate(raw):
    fields = {name: {} for name, _ in FIELD_RULES}
    paper_counts = {name: 0 for name, _ in FIELD_RULES}     # multi-counted
    citation_totals = {name: 0 for name, _ in FIELD_RULES}  # multi-counted
    top = {name: {} for name, _ in FIELD_RULES}             # per field/year top-cited paper
    unmatched = []
    for p in raw:
        matched = classify_all(p["title"])
        if not matched:
            unmatched.append(p["title"])
            matched = [FALLBACK_FIELD]
        series = p["per_year"] or (spread_total_over_years(p["total"], p["year"]) if p["year"] else {})
        # a paper in N fields is counted in ALL N
        for field in matched:
            paper_counts[field] += 1
            for y, c in series.items():
                y = int(y)
                if Y0 <= y <= Y1:
                    ys = str(y)
                    fields[field][ys] = round(fields[field].get(ys, 0) + c, 2)
                    citation_totals[field] = round(citation_totals[field] + c, 2)
                    cur = top[field].get(ys)
                    if cur is None or c > cur["c"]:
                        top[field][ys] = {"t": p["title"], "c": round(c, 2)}
    return fields, paper_counts, citation_totals, top, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="only fetch first N pubs (smoke test)")
    ap.add_argument("--refresh", action="store_true", help="ignore cache and refetch")
    args = ap.parse_args()
    if args.refresh and CACHE.exists():
        CACHE.unlink()

    raw = fetch_raw(limit=args.limit)
    fields, paper_counts, citation_totals, top, unmatched = aggregate(raw)
    # totals_by_year: count each paper once (avoid double-count inflation of the year axis)
    totals_by_year = {}
    for p in raw:
        series = p["per_year"] or (spread_total_over_years(p["total"], p["year"]) if p["year"] else {})
        for y, c in series.items():
            y = int(y)
            if Y0 <= y <= Y1:
                totals_by_year[str(y)] = round(totals_by_year.get(str(y), 0) + c, 2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "author": AUTHOR_ID,
        "year_range": [Y0, Y1],
        "fields": fields,
        "paper_counts": paper_counts,
        "citation_totals": citation_totals,
        "top": top,
        "totals_by_year": totals_by_year,
        "unmatched": unmatched,
        "n_pubs": len(raw),
    }, indent=2))
    print(f"\n✓ wrote {OUT}")
    print(f"  fields: {sum(1 for f in fields.values() if f)} populated / {len(fields)}")
    print(f"  multi-counted papers per field: " + ", ".join(f"{n}×{f.split(' ')[0]}" for f,n in paper_counts.items()))
    if unmatched:
        print(f"  ⚠ {len(unmatched)} unmatched titles (sent to '{FALLBACK_FIELD}'):")
        for t in unmatched:
            print(f"     - {t[:70]}")


if __name__ == "__main__":
    main()
