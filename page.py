"""
Builds output/index.html — one page with the latest Morning Brief on top and the
startup jobs board below it. Both digest.py and jobs.py call build() when they finish,
so the page is always current no matter which one ran last.
"""

import html
import json
from datetime import date, timedelta
from pathlib import Path

import settings

HERE = Path(__file__).parent
BRIEFS_DIR = HERE / "data" / "briefs"
JOBS_FILE = HERE / "data" / "jobs.json"
RAISES_FILE = HERE / "data" / "utah_raises.json"
TEMPLATE = HERE / "templates" / "page.html"
OUTPUT = HERE / "output" / "index.html"
SITE = HERE / "docs" / "index.html"  # copy GitHub Pages serves as the website


def latest_brief():
    files = sorted(BRIEFS_DIR.glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None


def render_brief(brief):
    if not brief:
        return '<p class="empty-brief">No brief yet — it appears after the next morning run.</p>'
    blocks = []
    for name, stories in brief["sections"].items():
        if not stories:
            continue
        items = "\n".join(
            f"""        <article class="story">
          <h3><a href="{html.escape(s['link'])}" target="_blank" rel="noopener">{html.escape(s['headline'])}</a></h3>
          <p>{html.escape(s['summary'])}</p>
          <div class="meta">{html.escape(s['source'])}</div>
        </article>"""
            for s in stories
        )
        slug = name.lower().replace(" & ", "-").replace(" ", "-")
        blocks.append(f"""      <section class="brief-section" id="s-{slug}">
        <h2><span>{html.escape(name)}</span><span class="count">{len(stories)}</span></h2>
{items}
      </section>""")
    return "\n".join(blocks)


def render_raises():
    """The Utah Raises table: Utah rounds announced in the last few days, newest first."""
    ledger = json.loads(RAISES_FILE.read_text()) if RAISES_FILE.exists() else []
    cutoff = (date.today() - timedelta(days=settings.RAISES_DAYS)).isoformat()
    recent = sorted((r for r in ledger if r["announced"] >= cutoff), key=lambda r: r["announced"], reverse=True)
    if not recent:
        rows = f"""<tr><td colspan="4" class="raises-none">No Utah pre-seed, seed, Series A, or Series B
          rounds announced in the last {settings.RAISES_DAYS} days.</td></tr>"""
    else:
        rows = "\n".join(
            f"""<tr>
          <td><a href="{html.escape(r['link'])}" target="_blank" rel="noopener"><b>{html.escape(r['company'])}</b></a>
            <div class="r-about">{html.escape(r['about'])} · {html.escape(r['city'])}</div></td>
          <td><span class="round">{html.escape(r['round'])}</span></td>
          <td class="r-amt">{html.escape(r['amount'])}<div class="r-lead">{html.escape(r['lead'] or '—')}</div></td>
          <td class="r-date">{date.fromisoformat(r['announced']).strftime('%b %-d')}</td>
        </tr>"""
            for r in recent
        )
    return f"""      <section class="brief-section" id="s-utah-raises">
        <h2><span>Utah Raises</span><span class="count">last {settings.RAISES_DAYS} days</span></h2>
        <table class="raises">
          <thead><tr><th>Company</th><th>Round</th><th>Amount · Lead</th><th>Announced</th></tr></thead>
          <tbody>
        {rows}
          </tbody>
        </table>
      </section>"""


def build():
    brief = latest_brief()
    jobs = json.loads(JOBS_FILE.read_text()) if JOBS_FILE.exists() else {"jobs": [], "companies": [], "categories": []}
    story_count = sum(len(v) for v in brief["sections"].values()) if brief else 0
    brief_date = date.fromisoformat(brief["date"]) if brief else date.today()

    replacements = {
        "{{DATE_LONG}}": brief_date.strftime("%A, %B %-d, %Y"),
        "{{BIG_PICTURE}}": html.escape(brief["big_picture"]) if brief else "",
        "{{SECTIONS}}": render_brief(brief) + "\n" + render_raises(),
        "{{STORY_COUNT}}": str(story_count),
        "{{READ_MINUTES}}": str(max(1, round(story_count * 0.4))),
        "{{SECTION_LINKS}}": " ".join(
            f'<a href="#s-{n.lower().replace(" & ", "-").replace(" ", "-")}">{html.escape(n)}</a>'
            for n, v in (brief["sections"].items() if brief else []) if v
        ) + ' <a href="#s-utah-raises">Utah Raises</a>',
        # safe to embed inside <script>
        "{{JOBS_DATA}}": json.dumps(jobs).replace("</", "<\\/"),
    }
    out = TEMPLATE.read_text()
    for key, value in replacements.items():
        out = out.replace(key, value)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(out)
    SITE.parent.mkdir(exist_ok=True)
    SITE.write_text(out)
    return OUTPUT


if __name__ == "__main__":
    print(build())
