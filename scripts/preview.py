#!/usr/bin/env python3
"""Minimal Jekyll renderer for this site.

Covers exactly the Liquid surface used by lab.html (verified by enumerating
every {{ }} / {% %} tag in the file). Not a general Liquid engine.
"""
import json, os, re, sys, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_preview")

def load_yaml(p):
    with open(p, encoding="utf-8") as f: return yaml.safe_load(f)

def load_json(p):
    with open(p, encoding="utf-8") as f: return json.load(f)

def front_matter(path):
    """Split a Jekyll page into (front matter dict, body)."""
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", txt, re.S)
    if not m: return {}, txt
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)

def collection(dirname):
    d = os.path.join(ROOT, dirname)
    items = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"): continue
        fm, _ = front_matter(os.path.join(d, fn))
        items.append(fm)
    return items

site = load_yaml(os.path.join(ROOT, "_config.yml"))
data = {
    "citations":        load_json(os.path.join(ROOT, "_data/citations.json")),
    "events":           load_yaml(os.path.join(ROOT, "_data/events.yml")),
    "topics":           load_yaml(os.path.join(ROOT, "_data/topics.yml")),
    "github_activity":  load_json(os.path.join(ROOT, "_data/github_activity.json")),
}
research = [i for i in collection("_research")        if i.get("published") is not False]
grants   = [i for i in collection("_grants")          if i.get("published") is not False]
hacks    = [i for i in collection("_sdg_hackathons")  if i.get("published") is not False]

def jsonify(v):
    # Jekyll's jsonify -> compact-ish JSON; separators match Ruby's to_json
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

def truncate(s, n=70, ellipsis="..."):
    s = str(s or "")
    if len(s) <= n: return s
    return s[: max(0, n - len(ellipsis))] + ellipsis

fm, body = front_matter(os.path.join(ROOT, "lab.html"))
page = {"url": "/", "title": fm.get("title", "")}

# --- {% assign %} lines: already computed above; strip the tags ---
body = re.sub(r"\{%\s*assign (research|grants|hacks) = .*?%\}\n?", "", body)

# --- {% unless site.data.citations %}X{% endunless %} ---
def _unless(m):
    return "" if data["citations"] else m.group(1)
body = re.sub(r"\{%\s*unless site\.data\.citations\s*%\}(.*?)\{%\s*endunless\s*%\}", _unless, body, flags=re.S)

# --- {%- comment -%} ... {%- endcomment -%} ---
body = re.sub(r"\{%-?\s*comment\s*-?%\}.*?\{%-?\s*endcomment\s*-?%\}", "", body, flags=re.S)

# --- server-rendered events fallback: {% for e in site.data.events %} ... {% endfor %} ---
def _esc(v):
    return (str(v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))

def _events_fallback(m):
    out = []
    for e in data["events"]:
        row = ["<li>", "<b>%s</b>" % _esc(e.get("title"))]
        if e.get("role"):  row.append(" \u2014 %s" % _esc(e["role"]))
        if e.get("venue"): row.append(" \u00b7 %s" % _esc(e["venue"]))
        if e.get("when"):  row.append(" <i>%s</i>" % _esc(e["when"]))
        if e.get("blob"):
            row.append("<p>%s</p>" % _esc(" ".join(str(e["blob"]).split("\n"))))
        row.append("</li>")
        out.append("".join(row))
    return "\n".join(out)

body = re.sub(r"\{%-?\s*for e in site\.data\.events\s*-?%\}.*?\{%-?\s*endfor\s*-?%\}",
              _events_fallback, body, flags=re.S)

# --- WRITING loop: research | sort:"year" | reverse, limit 5 ---
latest = sorted(research, key=lambda i: i.get("year", 0))[::-1]
def _writing(m):
    out = []
    for i in latest[:5]:
        url = (i.get("links") or [{}])[0].get("url") or i.get("url")
        out.append("{title:%s, meta:%s, url:%s}," % (
            jsonify(i.get("title")), jsonify(truncate(i.get("summary"))), jsonify(url)))
    return "".join(out)
body = re.sub(r"\{%\s*assign latest = research.*?%\}\s*\{%\s*for i in latest limit:5\s*%\}.*?\{%\s*endfor\s*%\}",
              _writing, body, flags=re.S)

# --- {{ site.data.X | jsonify }} ---
body = re.sub(r"\{\{\s*site\.data\.(\w+)\s*\|\s*jsonify\s*\}\}",
              lambda m: jsonify(data.get(m.group(1))), body)

# --- scalar {{ site.x }} / {{ page.x }} ---
body = re.sub(r"\{\{\s*site\.(\w+)\s*\}\}", lambda m: str(site.get(m.group(1), "")), body)
body = re.sub(r"\{\{\s*page\.(\w+)\s*\}\}", lambda m: str(page.get(m.group(1), "")), body)

leftover = re.findall(r"\{\{.*?\}\}|\{%.*?%\}", body)
if leftover:
    print("!! UNRENDERED LIQUID:", leftover[:10], file=sys.stderr)

os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(body)

# copy assets so PDF links resolve
import shutil
src = os.path.join(ROOT, "assets")
dst = os.path.join(OUT, "assets")
if os.path.isdir(src):
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(src, dst)

print("rendered ->", os.path.join(OUT, "index.html"))
print("collections: research=%d grants=%d hacks=%d events=%d topics=%d" % (
    len(research), len(grants), len(hacks), len(data["events"]), len(data["topics"])))
