#!/usr/bin/env python3
"""Render an animated GitHub stats card (stats.svg) in the profile's visual style.

Only uses the standard library. Needs a token in GH_TOKEN or GITHUB_TOKEN.
Usage: python stats.py <github-user> <output.svg>
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USER = sys.argv[1] if len(sys.argv) > 1 else "rzig1"
OUT = sys.argv[2] if len(sys.argv) > 2 else "stats.svg"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

# ---- palette (matches assets/*.svg) -------------------------------------
BG0, BG1, LINE, TILE = "#0b1120", "#111a33", "#1e2a4a", "#0f172a"
TXT1, TXT2, TXT3 = "#f1f5f9", "#cbd5e1", "#94a3b8"  # text tokens: never series colors
SKY, PINK, AMB, VIO, MINT, OTHER = "#38bdf8", "#fb7185", "#fbbf24", "#a78bfa", "#34d399", "#64748b"
# categorical order validated for CVD separation on the dark surface; never cycled
LANG_COLORS = [SKY, PINK, AMB, VIO, MINT]

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch():
    if not TOKEN:
        sys.exit("Set GH_TOKEN or GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if body.get("errors"):
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]["user"]


def streaks(days):
    """Current and longest streak (in days) over the calendar window."""
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    # today may not have activity yet: start counting from yesterday in that case
    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1
        i -= 1
    return current, longest


def compact(n):
    if n >= 10_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return f"{n:,}"


# ---- shapes (same morph vocabulary as the hero) --------------------------
def icon(kind, color):
    if kind == "circle":
        return f'<circle r="7" fill="none" stroke="{color}" stroke-width="2.5"/>'
    if kind == "square":
        return f'<rect x="-6.5" y="-6.5" width="13" height="13" rx="3" fill="none" stroke="{color}" stroke-width="2.5"/>'
    if kind == "triangle":
        return f'<polygon points="0,-8 7.5,6 -7.5,6" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
    return (f'<path d="M0,-9 C1,-1 1,-1 9,0 C1,1 1,1 0,9 C-1,1 -1,1 -9,0 C-1,-1 -1,-1 0,-9Z" '
            f'fill="{color}"/>')  # star


def render(u):
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal["weeks"]][-52:]
    current, longest = streaks(days)
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    commits = (u["contributionsCollection"]["totalCommitContributions"]
               + u["contributionsCollection"]["restrictedContributionsCount"])

    langs = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    total = sum(langs.values()) or 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    top = ranked[:5]
    other = sum(v for _, v in ranked[5:])
    segs = [(n, v / total, LANG_COLORS[i]) for i, (n, v) in enumerate(top)]
    if other:
        segs.append(("Other", other / total, OTHER))

    W, H = 860, 430
    o = []
    o.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">GitHub stats for {escape(USER)}</title>
<desc id="d">{cal["totalContributions"]} contributions in the last year, {commits} commits, {stars} stars, {u["pullRequests"]["totalCount"]} pull requests, current streak {current} day{"s" * (current != 1)}, longest streak {longest} day{"s" * (longest != 1)}. Top languages: {", ".join(f"{escape(n)} {p:.0%}" for n, p, _ in segs)}.</desc>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient>
<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="{LINE}"/></pattern>
<linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{SKY}"/><stop offset="1" stop-color="{VIO}"/></linearGradient>
<clipPath id="langclip"><rect x="24" y="352" height="14" width="0"><animate attributeName="width" from="0" to="{W - 48}" dur="1.4s" begin=".9s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".6 0 .2 1"/></rect></clipPath>
</defs>
<style>
text{{font-family:'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif;}} .mono{{font-family:'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace;}}
@keyframes up{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
@keyframes ring{{to{{stroke-dashoffset:var(--to)}}}}
.t{{opacity:0;animation:up .7s cubic-bezier(.2,.8,.2,1) forwards}}
.b{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .6s cubic-bezier(.3,1.3,.5,1) forwards}}
.ic{{transform-box:fill-box;transform-origin:center;animation:spin 12s linear infinite}}
</style>
<rect width="{W}" height="{H}" rx="20" fill="url(#bg)"/>
<rect width="{W}" height="{H}" rx="20" fill="url(#dots)"/>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="20" fill="none" stroke="{LINE}"/>
<text x="24" y="36" class="mono" font-size="13" fill="{TXT3}">// github, by the numbers</text>
<text x="{W - 24}" y="36" text-anchor="end" class="mono" font-size="11" fill="{TXT3}">updated {dt.date.today().isoformat()}</text>''')

    # ---- stat tiles
    tiles = [
        (compact(cal["totalContributions"]), "contributions / yr", "star", SKY),
        (compact(commits), "commits / yr", "square", PINK),
        (compact(u["pullRequests"]["totalCount"]), "pull requests", "triangle", AMB),
        (compact(stars), "stars earned", "circle", VIO),
        (compact(u["repositories"]["totalCount"]), "public repos", "square", MINT),
    ]
    tw, gap = (W - 48 - 4 * 12) / 5, 12
    for i, (val, label, shape, col) in enumerate(tiles):
        x = 24 + i * (tw + gap)
        o.append(f'<g class="t" style="animation-delay:{.1 + i * .08:.2f}s">'
                 f'<rect x="{x:.1f}" y="54" width="{tw:.1f}" height="84" rx="14" fill="{TILE}" stroke="{LINE}"/>'
                 f'<g transform="translate({x + tw - 22:.1f},76)"><g class="ic">{icon(shape, col)}</g></g>'
                 f'<text x="{x + 16:.1f}" y="98" font-size="30" font-weight="800" fill="{TXT1}">{val}</text>'
                 f'<text x="{x + 16:.1f}" y="122" class="mono" font-size="11" fill="{TXT3}">{label}</text></g>')

    # ---- weekly contributions: single series, columns from one baseline
    cx0, cx1, base, top_y = 24, 560, 300, 188
    peak = max(weeks) or 1
    slot = (cx1 - cx0) / len(weeks)
    bw = min(24, slot - 2)  # 2px surface gap between neighbours
    o.append(f'<text x="{cx0}" y="170" font-size="14" font-weight="700" fill="{TXT1}">Contributions per week</text>'
             f'<text x="{cx1}" y="170" text-anchor="end" class="mono" font-size="11" fill="{TXT3}">last 52 weeks · all repos</text>')
    peak_i = max(range(len(weeks)), key=lambda i: weeks[i])
    for i, v in enumerate(weeks):
        if not v:
            continue
        h = max(2, (base - top_y) * v / peak)
        x = cx0 + i * slot + (slot - bw) / 2
        r = min(3, bw / 2, h)
        d = (f"M{x:.2f},{base} V{base - h + r:.2f} Q{x:.2f},{base - h:.2f} {x + r:.2f},{base - h:.2f} "
             f"H{x + bw - r:.2f} Q{x + bw:.2f},{base - h:.2f} {x + bw:.2f},{base - h + r:.2f} V{base}Z")
        o.append(f'<path class="b" style="animation-delay:{.4 + i * .015:.3f}s" d="{d}" fill="{SKY}" '
                 f'fill-opacity="{.45 + .55 * v / peak:.2f}"/>')
    px = cx0 + peak_i * slot + slot / 2
    anchor = "end" if px > cx1 - 60 else ("start" if px < cx0 + 60 else "middle")
    o.append(f'<text class="t" style="animation-delay:1.3s" x="{px:.1f}" y="{base - (base - top_y) - 8}" '
             f'text-anchor="{anchor}" font-size="11" font-weight="700" fill="{TXT2}">peak {weeks[peak_i]}</text>')
    o.append(f'<line x1="{cx0}" y1="{base + .5}" x2="{cx1}" y2="{base + .5}" stroke="{LINE}"/>'
             f'<text x="{cx0}" y="{base + 18}" class="mono" font-size="10.5" fill="{TXT3}">a year ago</text>'
             f'<text x="{cx1}" y="{base + 18}" text-anchor="end" class="mono" font-size="10.5" fill="{TXT3}">this week</text>')

    # ---- streak ring
    rx, ry, rr = 708, 228, 54
    circ = 2 * 3.14159 * rr
    frac = min(1, current / longest) if longest else 0
    o.append(f'<g class="t" style="animation-delay:.6s">'
             f'<rect x="584" y="154" width="{W - 24 - 584}" height="166" rx="14" fill="{TILE}" stroke="{LINE}"/>'
             f'<circle cx="{rx}" cy="{ry}" r="{rr}" fill="none" stroke="{LINE}" stroke-width="9"/>'
             f'<circle cx="{rx}" cy="{ry}" r="{rr}" fill="none" stroke="url(#ring)" stroke-width="9" stroke-linecap="round" '
             f'transform="rotate(-90 {rx} {ry})" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" '
             f'style="--to:{circ * (1 - frac):.1f};animation:ring 1.6s cubic-bezier(.6,0,.2,1) forwards 1s"/>'
             f'<g transform="translate({rx + rr * .72:.1f},{ry - rr * .72:.1f})"><g class="ic">{icon("star", AMB)}</g></g>'
             f'<text x="{rx}" y="{ry + 8}" text-anchor="middle" font-size="34" font-weight="800" fill="{TXT1}">{current}</text>'
             f'<text x="{rx}" y="{ry + 26}" text-anchor="middle" class="mono" font-size="10.5" fill="{TXT3}">day streak</text>'
             f'<text x="{rx}" y="{ry + rr + 24}" text-anchor="middle" class="mono" font-size="11" fill="{TXT2}">longest · {longest} day{"s" * (longest != 1)}</text></g>')

    # ---- languages: one stacked bar, 2px surface gaps, legend with name + %
    o.append(f'<text x="24" y="342" font-size="14" font-weight="700" fill="{TXT1}">Languages across my repos</text>'
             f'<text x="{W - 24}" y="342" text-anchor="end" class="mono" font-size="11" fill="{TXT3}">by code size</text>')
    o.append('<g clip-path="url(#langclip)">')
    x, span = 24.0, W - 48 - 2 * (len(segs) - 1)
    for i, (name, p, col) in enumerate(segs):
        w = max(1.0, span * p)
        rl = 4 if i == 0 else 0
        rr_ = 4 if i == len(segs) - 1 else 0
        o.append(f'<path d="M{x + rl:.2f},352 H{x + w - rr_:.2f} Q{x + w:.2f},352 {x + w:.2f},{352 + rr_} V{366 - rr_} '
                 f'Q{x + w:.2f},366 {x + w - rr_:.2f},366 H{x + rl:.2f} Q{x:.2f},366 {x:.2f},{366 - rl} V{352 + rl} '
                 f'Q{x:.2f},352 {x + rl:.2f},352Z" fill="{col}"/>')
        x += w + 2
    o.append('</g>')
    lx, ly = 24.0, 396
    for i, (name, p, col) in enumerate(segs):
        label = f"{escape(name)}"
        pct = f"{p * 100:.1f}%"
        o.append(f'<g class="t" style="animation-delay:{1.6 + i * .08:.2f}s">'
                 f'<rect x="{lx:.1f}" y="{ly - 10}" width="10" height="10" rx="3" fill="{col}"/>'
                 f'<text x="{lx + 16:.1f}" y="{ly}" font-size="12.5" fill="{TXT2}">{label} '
                 f'<tspan class="mono" fill="{TXT3}">{pct}</tspan></text></g>')
        lx += 16 + 6.9 * len(name) + 7.6 * len(pct) + 4 + 22
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    svg = render(fetch())
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT}")
