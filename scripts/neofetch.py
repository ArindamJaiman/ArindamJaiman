"""
Render the neofetch-style terminal card at the top of the profile README.

Writes neofetch-dark.svg and neofetch-light.svg: the blackletter "A" from
assets/blackletter-a.txt on the left, system "info" + live GitHub stats on
the right. Stdlib only, so the workflow needs no pip install.

    GITHUB_TOKEN=... python scripts/neofetch.py --user ArindamJaiman --out dist

Without GITHUB_TOKEN the card still renders, with "--" in place of the stats.
"""

import argparse
import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_FILE = os.path.join(ROOT, "assets", "blackletter-a.txt")

# ── Card content ──────────────────────────────────────────────────────────────
LOGIN, HOST = "arindam", "github"

# (key, value) rows; a str is a section header, None is a blank line.
PROFILE = [
    ("OS", "Windows 11 + WSL"),
    ("Uptime", "{uptime}"),
    ("Host", "github.com/{user}"),
    ("Kernel", "Full-Stack Developer"),
    ("IDE", "VS Code"),
    ("Focus", "Building scalable web apps"),
    ("Ask me", "Web dev, tech, open source"),
    ("Fuel", "Coffee -> code"),
    None,
    "Stack",
    ("Languages", "Python, C++, C, Java, JS, TS"),
    ("Frontend", "React, Next.js, Tailwind CSS"),
    ("Backend", "Node.js, Express, Supabase"),
    ("Databases", "PostgreSQL, MongoDB, Firebase"),
    ("Tools", "Git, Docker, WSL"),
    None,
    "GitHub",
]

# Markup, styling and build files say little about what someone writes.
IGNORED_LANGUAGES = {"HTML", "CSS", "SCSS", "Less", "Jupyter Notebook", "Dockerfile", "Makefile", "Batchfile"}

THEMES = {
    "dark": {
        "bg": "#0d1117", "bar": "#161b22", "border": "#30363d",
        "fg": "#e6edf3", "dim": "#6e7681", "key": "#ffa657", "user": "#7ee787",
        "path": "#79c0ff", "track": "#21262d", "art": ("#3fb950", "#39c5cf", "#58a6ff"), "glow": True,
        "palette": ["#484f58", "#ff7b72", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"],
    },
    "light": {
        "bg": "#ffffff", "bar": "#f6f8fa", "border": "#d0d7de",
        "fg": "#1f2328", "dim": "#8c959f", "key": "#953800", "user": "#1a7f37",
        "path": "#0969da", "track": "#eaeef2", "art": ("#1a7f37", "#1b7c83", "#0969da"), "glow": False,
        "palette": ["#24292f", "#cf222e", "#116329", "#9a6700", "#0969da", "#8250df", "#1b7c83", "#6e7781"],
    },
}

# ── Grid geometry (px) ────────────────────────────────────────────────────────
FONT_SIZE = 14
CW = 8.4             # column width; every glyph gets an explicit x, so any monospace font lines up
LH = 17.5            # line height (≈ the 2.05 aspect ascii_art.py renders for)
PAD_X = 24
TITLE_H = 34
PAD_TOP = 18
GAP = 5              # columns between the art and the info
KEY_W = 14           # "Languages ... " — dotted key column
INFO_W = 50          # section rule / language bar width, in columns


# ── GitHub stats ──────────────────────────────────────────────────────────────
QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def graphql(token, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "neofetch-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def fetch_stats(user, token):
    """Return a dict of stats, or None if there's no token to ask with."""
    if not token:
        return None

    repos, cursor = [], None
    while True:
        data = graphql(token, {"login": user, "cursor": cursor})
        page = data["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    # sqrt per repo, so one giant (or vendored) codebase doesn't drown out the rest
    score, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in IGNORED_LANGUAGES:
                continue
            score[name] = score.get(name, 0) + math.sqrt(edge["size"])
            colors[name] = edge["node"]["color"] or "#8b949e"
    total = sum(score.values()) or 1
    languages = [(name, s / total, colors[name]) for name, s in sorted(score.items(), key=lambda kv: -kv[1])]

    contrib = data["contributionsCollection"]
    days = [d for w in contrib["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    current, best = streaks(days)

    return {
        "created": datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
        "repos": data["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": data["followers"]["totalCount"],
        "commits": contrib["totalCommitContributions"],
        "contributions": contrib["contributionCalendar"]["totalContributions"],
        "streak": current,
        "best_streak": best,
        "languages": languages,
    }


def streaks(days):
    """(current, longest) run of days with contributions in the calendar."""
    counts = [d["contributionCount"] for d in sorted(days, key=lambda d: d["date"])]
    best = run = 0
    for n in counts:
        run = run + 1 if n else 0
        best = max(best, run)
    # Today isn't over yet, so a zero there doesn't break the streak.
    if counts and counts[-1] == 0:
        counts = counts[:-1]
    current = 0
    for n in reversed(counts):
        if not n:
            break
        current += 1
    return current, best


def uptime(start, now):
    """'1 year, 11 months, 2 days' between two dates."""
    y, m, d = now.year - start.year, now.month - start.month, now.day - start.day
    if d < 0:
        m -= 1
        d += (date(now.year, now.month, 1) - timedelta(days=1)).day
    if m < 0:
        y -= 1
        m += 12
    parts = [(y, "year"), (m, "month"), (d, "day")]
    return ", ".join(f"{n} {unit}{'' if n == 1 else 's'}" for n, unit in parts if n) or "0 days"


# ── Card layout ───────────────────────────────────────────────────────────────
# A line is a list of (text, class) spans, or one of the markers below that
# render() draws as shapes instead of text. Class "dot:<hex>" is a coloured
# bullet taking two columns.
LANGBAR, PALETTE = "langbar", "palette"


def dotted(key, width=KEY_W):
    return f"{key} {'.' * max(width - len(key) - 2, 3)} "


def pair(key, value, value_w=0, key_w=KEY_W):
    return [(dotted(key, key_w), "key"), (value.ljust(value_w), "fg")]


def info_lines(user, stats, now):
    """The right-hand column of the card."""
    na = "--"
    s = stats or {}
    fill = {"user": user, "uptime": uptime(s["created"], now) if stats else na}

    title = f"{LOGIN}@{HOST}"
    lines = [
        [(LOGIN, "user"), ("@", "fg"), (HOST, "user")],
        [("-" * len(title), "dim")],
    ]
    for row in PROFILE:
        if row is None:
            lines.append([])
        elif isinstance(row, str):
            lines.append([("- ", "dim"), (row, "path"), (" " + "-" * (INFO_W - len(row) - 3), "dim")])
        else:
            key, value = row
            lines.append(pair(key, value.format(**fill)))

    def num(key, suffix=""):
        return f"{s[key]:,}{suffix}" if stats else na

    streak = f"{s['streak']}d (best {s['best_streak']}d)" if stats else na
    lines += [
        pair("Repos", num("repos"), 10) + pair("Stars", num("stars"), 0, KEY_W - 2),
        pair("Followers", num("followers"), 10) + pair("Commits", num("commits", " (1y)"), 0, KEY_W - 2),
        pair("Contribs", num("contributions", " (1y)"), 10) + pair("Streak", streak, 0, KEY_W - 2),
        LANGBAR,
        *legend_lines(s.get("languages", [])),
        [],
        PALETTE,
    ]
    return lines


def legend_lines(languages, per_line=3, slot=17):
    top = languages[:6]
    if not top:
        return [[("no language data", "dim")]]
    return [
        [span for name, pct, color in top[i:i + per_line]
         for span in ((None, f"dot:{color}"), (f"{name} {pct * 100:.0f}%".ljust(slot - 2), "fg"))]
        for i in range(0, len(top), per_line)
    ]


# ── SVG ───────────────────────────────────────────────────────────────────────
def x_at(col):
    return PAD_X + col * CW


def run(text, col, cls):
    """A tspan with one x per non-space character, pinned to the column grid."""
    xs, chars = [], []
    for i, ch in enumerate(text):
        if ch != " ":
            xs.append(f"{x_at(col + i):.1f}")
            chars.append(ch)
    if not chars:
        return ""
    return f'<tspan x="{" ".join(xs)}" class="{cls}">{escape("".join(chars))}</tspan>'


def prompt(command=""):
    spans = [run(f"{LOGIN}@{HOST}", 0, "user"), run(":", 14, "fg"), run("~", 15, "path"), run("$", 16, "fg")]
    if command:
        spans.append(run(command, 18, "fg"))
    return spans


def langbar(stats, x, y, w, t):
    """Stacked bar of the top six languages over a track for everything else."""
    track = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="8" rx="4" fill="{t["track"]}"/>'
    if not stats:
        return track
    segs, cx = [], x
    for name, pct, color in stats["languages"][:6]:
        segs.append(f'<rect x="{cx:.1f}" y="{y:.1f}" width="{w * pct:.1f}" height="8" fill="{color}">'
                    f'<title>{escape(name)} {pct * 100:.1f}%</title></rect>')
        cx += w * pct
    return (f'{track}<clipPath id="bar"><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="8" rx="4"/></clipPath>'
            f'<g clip-path="url(#bar)">{"".join(segs)}</g>')


def render(theme_name, user, stats, art, now):
    t = THEMES[theme_name]
    info = info_lines(user, stats, now)
    info_col = max(len(line) for line in art) + GAP
    info_w = max(sum(len(text or "  ") for text, _ in line) for line in info if isinstance(line, list))

    body_rows = max(len(art), len(info))
    art_top = (body_rows - len(art)) // 2
    end_row = 2 + body_rows + 1           # prompt, blank, body, blank, prompt
    width = round(PAD_X * 2 + (info_col + max(info_w, INFO_W)) * CW)
    height = round(TITLE_H + PAD_TOP + (end_row + 1) * LH + 12)

    def baseline(row):
        return TITLE_H + PAD_TOP + row * LH + FONT_SIZE * 0.8

    def text_el(row, spans, cls=None):
        attr = f' class="{cls}"' if cls else ""
        return f'<text y="{baseline(row):.1f}"{attr}>{"".join(spans)}</text>'

    # Art sits on its own layer so the dark theme can make it glow.
    art_els = [text_el(2 + art_top + i, [run(line, 0, "a")], "art") for i, line in enumerate(art)]

    text_els, shapes = [text_el(0, prompt("neofetch --ascii blackletter-a"))], []
    for i, line in enumerate(info):
        row = 2 + i
        mid = baseline(row) - FONT_SIZE * 0.32
        if line == LANGBAR:
            shapes.append(langbar(stats, x_at(info_col), mid - 4, INFO_W * CW, t))
        elif line == PALETTE:
            shapes += [f'<rect x="{x_at(info_col + k * 3):.1f}" y="{mid - 6:.1f}" width="{CW * 3 - 2:.1f}" '
                       f'height="12" rx="2" fill="{color}"/>' for k, color in enumerate(t["palette"])]
        elif line:
            spans, col = [], info_col
            for text, cls in line:
                if cls.startswith("dot:"):
                    shapes.append(f'<circle cx="{x_at(col) + CW / 2:.1f}" cy="{mid:.1f}" r="3.6" fill="{cls[4:]}"/>')
                    col += 2
                    continue
                spans.append(run(text, col, cls))
                col += len(text)
            text_els.append(text_el(row, spans))
    text_els.append(text_el(end_row, prompt()))

    a0, a1, a2 = t["art"]
    art_y0, art_y1 = baseline(2 + art_top) - FONT_SIZE, baseline(2 + art_top + len(art))
    nl = "\n"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(user)} — neofetch</title>
<desc id="desc">A terminal running neofetch: a blackletter A drawn in ASCII characters next to profile info and GitHub stats.</desc>
<defs>
  <linearGradient id="art" gradientUnits="userSpaceOnUse" x1="0" y1="{art_y0:.0f}" x2="0" y2="{art_y1:.0f}">
    <stop offset="0" stop-color="{a0}"/><stop offset=".55" stop-color="{a1}"/><stop offset="1" stop-color="{a2}"/>
  </linearGradient>
  <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
    <feGaussianBlur stdDeviation="2.4" result="blur"/>
    <feComponentTransfer in="blur" result="soft"><feFuncA type="linear" slope=".55"/></feComponentTransfer>
    <feMerge><feMergeNode in="soft"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>
  text {{ font: {FONT_SIZE}px ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; }}
  .art {{ font-weight: 700; }}
  .a {{ fill: url(#art); }}
  .fg {{ fill: {t["fg"]}; }} .dim {{ fill: {t["dim"]}; }} .key {{ fill: {t["key"]}; }}
  .user {{ fill: {t["user"]}; font-weight: 700; }} .path {{ fill: {t["path"]}; font-weight: 700; }}
  /* Only the cursor moves: anything that hides content at t=0 shows up blank in static renderers. */
  .cur {{ animation: blink 1.1s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .cur {{ animation: none; }} }}
</style>
<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>
<path d="M1 {TITLE_H}V11a10 10 0 0 1 10-10h{width - 22}a10 10 0 0 1 10 10V{TITLE_H}z" fill="{t["bar"]}"/>
<line x1="1" x2="{width - 1}" y1="{TITLE_H}" y2="{TITLE_H}" stroke="{t["border"]}"/>
<circle cx="20" cy="{TITLE_H / 2}" r="6" fill="#ff5f57"/><circle cx="40" cy="{TITLE_H / 2}" r="6" fill="#febc2e"/><circle cx="60" cy="{TITLE_H / 2}" r="6" fill="#28c840"/>
<text x="{width / 2}" y="{TITLE_H / 2 + 4.5}" text-anchor="middle" class="dim" style="font-size:12px">{LOGIN}@{HOST}: ~ — neofetch</text>
<g{' filter="url(#glow)"' if t["glow"] else ""}>
{nl.join(art_els)}
</g>
{nl.join(text_els)}
{nl.join(shapes)}
<rect class="cur" x="{x_at(18):.1f}" y="{baseline(end_row) - FONT_SIZE * 0.85:.1f}" width="{CW:.1f}" height="{FONT_SIZE * 1.05:.1f}" fill="{t["fg"]}"/>
</svg>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", default="ArindamJaiman")
    parser.add_argument("--out", default="dist")
    args = parser.parse_args()

    with open(ART_FILE, encoding="utf-8") as f:
        art = [line.rstrip("\n") for line in f]

    now = datetime.now(timezone.utc)
    stats = fetch_stats(args.user, os.environ.get("GITHUB_TOKEN"))
    if stats is None:
        print("GITHUB_TOKEN not set; rendering without stats")

    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(args.out, f"neofetch-{theme}.svg")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render(theme, args.user, stats, art, now))
        print("wrote", path)


if __name__ == "__main__":
    main()
