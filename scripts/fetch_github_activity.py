#!/usr/bin/env python3
"""
Summarise recent GitHub activity for the "In flight" panel.

For each repo pushed in the last N days (default 7), pull up to 10 recent commits
and extract: the SENSE of the work (repo description + commit subjects), one KEY
SENTENCE (the most descriptive commit message), and one KEY CODE SNIPPET (added
lines from the largest content change).

Output: _data/github_activity.json  (read by lab.html via site.data.github_activity)

Usage:
    python3 scripts/fetch_github_activity.py            # last 7 days
    python3 scripts/fetch_github_activity.py --days 30  # widen the window

Unauthenticated GitHub REST (60 req/h). Set GITHUB_TOKEN to raise the limit.
"""
import argparse, json, os, re, ssl, sys, urllib.request, datetime
from pathlib import Path

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    SSL_CTX = ssl._create_unverified_context()

USER = "wazaahhh"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_data" / "github_activity.json"

SKIP_FILES = re.compile(r"(LICENSE|\.lock$|lock\.json$|\.gitignore|\.png$|\.jpg$|\.svg$|\.ipynb$)", re.I)
LANG_BY_EXT = {".py":"python",".js":"javascript",".ts":"typescript",".jsx":"jsx",".tsx":"tsx",
               ".md":"markdown",".html":"html",".css":"css",".sh":"bash",".r":"r",".jl":"julia",
               ".yml":"yaml",".yaml":"yaml",".json":"json",".java":"java",".go":"go",".rs":"rust"}


def gh(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "inflight-fetch"})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
        return json.load(r)


def lang_of(fn):
    ext = os.path.splitext(fn)[1].lower()
    return LANG_BY_EXT.get(ext, "")


def pick_snippet(full_name, commits):
    """Find the largest non-trivial added hunk across recent commits."""
    best = None
    for c in commits[:5]:
        try:
            detail = gh(f"https://api.github.com/repos/{full_name}/commits/{c['sha']}")
        except Exception:
            continue
        for f in detail.get("files", []):
            fn = f.get("filename", "")
            if SKIP_FILES.search(fn) or "patch" not in f:
                continue
            adds = [ln[1:] for ln in f["patch"].splitlines()
                    if ln.startswith("+") and not ln.startswith("+++") and ln[1:].strip()]
            if adds and (best is None or len(adds) > best["n"]):
                code = "\n".join(adds[:9])[:600]
                best = {"file": fn, "lang": lang_of(fn), "code": code, "n": len(adds)}
    if best:
        best.pop("n", None)
    return best


def key_sentence(subjects):
    """Most descriptive commit subject: prefer ones with a dash/long, skip 'Merge'."""
    cands = [s for s in subjects if not s.lower().startswith("merge")]
    cands = cands or subjects
    # favour subjects containing an em/en dash (often the headline), else longest
    dashed = [s for s in cands if "—" in s or " - " in s]
    pool = dashed or cands
    return max(pool, key=len) if pool else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=args.days)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")

    repos = gh(f"https://api.github.com/users/{USER}/repos?sort=pushed&per_page=30")
    out = []
    for r in repos:
        pushed = datetime.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
        if pushed < since:
            continue
        full = r["full_name"]
        try:
            commits = gh(f"https://api.github.com/repos/{full}/commits?since={since_iso}&per_page=10")
        except Exception as e:
            print(f"  ! commits failed for {full}: {e}"); continue
        if not commits:
            continue
        subjects = [c["commit"]["message"].split("\n")[0].strip() for c in commits]
        snippet = pick_snippet(full, commits)
        out.append({
            "name": r["name"],
            "url": r["html_url"],
            "desc": r.get("description") or "",
            "lang": r.get("language") or "",
            "last_push": r["pushed_at"][:10],
            "n_commits": len(commits),
            "subjects": subjects,
            "key_sentence": key_sentence(subjects),
            "snippet": snippet,
        })
        print(f"✓ {r['name']}: {len(commits)} commits, snippet={'yes' if snippet else 'no'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "window_days": args.days,
        "repos": out,
    }, indent=2))
    print(f"\n✓ wrote {OUT}  ({len(out)} repos in last {args.days}d)")


if __name__ == "__main__":
    main()
