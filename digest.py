"""
Morning Digest — builds a newsletter of today's top Tech, Venture, and AI stories.

How it works, step by step:
  1. Pull recent headlines from every RSS feed listed in settings.py
  2. Drop anything you've already been shown (tracked in data/seen_stories.json)
  3. Ask Claude to pick the most important stories for each section
  4. Download the full text of those stories
  5. Ask Claude to write a 2–3 sentence summary of each
  6. Save the brief (data/briefs/) and rebuild output/index.html — the one page that
     holds both the brief and the jobs board — then remember what you've seen

There are two ways to do the AI steps (3 and 5):

  A) Your Claude subscription (the daily scheduled task does this). The script does the
     mechanical parts and Claude, in the task session, does the reading and writing:
        digest.py prepare            → saves today's unseen stories to data/candidates.json
        digest.py articles 3 7 12    → prints the full text of the chosen stories
        (Claude writes its picks + summaries to data/today.json)
        digest.py publish            → builds the page and remembers what you've seen

  B) An Anthropic API key, fully automatic:  digest.py api

Preview the layout without any AI:  digest.py preview
"""

import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import anthropic
import feedparser
import requests
from pydantic import BaseModel

import page
import settings

HERE = Path(__file__).parent
SEEN_FILE = HERE / "data" / "seen_stories.json"
BRIEFS_DIR = HERE / "data" / "briefs"
RAISES_FILE = HERE / "data" / "utah_raises.json"
RAISES = "Utah Raises"  # label for candidates that came from the funding-news feeds
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) MorningDigest/1.0"}
FORGET_AFTER_DAYS = 30  # seen-story memory is trimmed after this long


# ─── Step 1: fetch headlines ──────────────────────────────────────────────────

def clean_url(url):
    """Strip tracking junk (?utm_source=...) so the same story always has the same URL."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_feed(section, source, url, hours):
    """Download one RSS feed and return stories from the last `hours` hours as simple dicts."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ! {source}: {e}")
        return []

    stories = []
    for entry in feedparser.parse(resp.content).entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if not stamp or not entry.get("link"):
            continue
        published = datetime(*stamp[:6], tzinfo=timezone.utc)
        if published < cutoff:
            continue
        body = entry.get("content", [{}])[0].get("value") or entry.get("summary", "")
        stories.append({
            "url": clean_url(entry.link),
            "link": entry.link,
            "title": strip_html(entry.get("title", "")),
            "blurb": strip_html(body)[:4000],
            "source": source,
            "feed_section": section,
            "published": published.isoformat(),
        })
    return stories


def fetch_all_feeds():
    jobs = [(section, name, url, cfg["hours"]) for section, cfg in settings.SECTIONS.items() for name, url in cfg["feeds"]]
    # Funding-news feeds for the Utah Raises table (they look back further than the news sections).
    jobs += [(RAISES, name, url, settings.RAISES_DAYS * 24) for name, url in settings.RAISES_FEEDS]
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = pool.map(lambda j: fetch_feed(*j), jobs)
    # The same story can appear in two feeds (e.g. TechCrunch + TechCrunch AI) — keep one.
    unique = {}
    for story in (s for batch in results for s in batch):
        unique.setdefault(story["url"], story)
    return list(unique.values())


# ─── Step 2: remember what you've seen ───────────────────────────────────────

def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def save_seen(seen):
    cutoff = (datetime.now() - timedelta(days=FORGET_AFTER_DAYS)).date().isoformat()
    seen = {url: info for url, info in seen.items() if info["date"] >= cutoff}
    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=1))


def recently_shown_headlines(seen, days=4):
    """Headlines you were shown lately, so Claude avoids the same news under a new URL."""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    today = datetime.now().date().isoformat()
    return [info["title"] for info in seen.values()
            if info.get("shown") and cutoff <= info["date"] < today]


# ─── Step 4: download full article text ──────────────────────────────────────

class ParagraphGrabber(HTMLParser):
    """Collects the text inside <p> tags — a rough but reliable way to get article text."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.paragraphs = []
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "p" and self.depth:
            self.depth -= 1
            text = " ".join("".join(self.current).split())
            # Skip captions, bylines, and boilerplate that sites repeat on every page.
            if len(text) > 60 and text not in self.paragraphs:
                self.paragraphs.append(text)
            self.current = []

    def handle_data(self, data):
        if self.depth:
            self.current.append(data)


def fetch_article_text(story):
    """Try to download the article; fall back to the RSS blurb if the site blocks us."""
    try:
        resp = requests.get(story["link"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
        grabber = ParagraphGrabber()
        grabber.feed(resp.text)
        text = "\n".join(grabber.paragraphs)
    except (requests.RequestException, ValueError):
        text = ""
    # Use whichever source gave us more to work with.
    best = text if len(text) > len(story["blurb"]) else story["blurb"]
    return best[:6000]


# ─── Steps 3 & 5: Claude picks and summarizes ────────────────────────────────
# These instructions are shared by both modes (subscription task and API key), so
# Claude judges stories the same way no matter how it's run.

READER = (
    "The reader is a college finance student headed into investment banking who follows "
    "venture capital, startups, big tech, and AI closely. They want the stories that "
    "actually matter — major launches, funding rounds, M&A, IPOs, strategy shifts, "
    "policy moves — not listicles, product reviews, deals-of-the-day, or opinion fluff."
)


def selection_prompt(candidates, already_shown):
    listing = "\n".join(
        f"[{s['id']}] ({s['source']}, from {s['feed_section']} feed) {s['title']} — {s['blurb'][:250]}"
        for s in candidates
    )
    shown = "\n".join(f"- {t}" for t in already_shown) or "(none)"
    limits = "\n".join(f"- {name} (up to {cfg['stories']}): {cfg['about']}" for name, cfg in settings.SECTIONS.items())
    return f"""{READER}

Below are today's candidate stories. Choose stories for these newsletter sections:
{limits}

Separately, list raise_ids: every candidate (from any feed) that may announce a Utah-based
company raising a pre-seed, seed, Series A, or Series B round. Be generous here — the
articles get checked in the next step. Leave it empty if there are none.

Rules:
- Pick the most important, newsworthy stories. Fewer is fine if the rest are weak.
- If several candidates cover the same news, pick only the best one.
- Skip anything that's the same news as a headline the reader already saw recently.
- Put each story in the section where it fits best, regardless of which feed it came from.
- Candidates from the "Utah Raises" feed are only for raise_ids unless they're also great Utah Tech news.
- Order picks within a section from most to least important.

Already shown in the last few days:
{shown}

Candidates:
{listing}"""


def summary_prompt(stories, raise_candidates=()):
    raise_articles = "\n\n".join(
        f"<raise_candidate id=\"{s['id']}\" source=\"{s['source']}\" published=\"{s['published'][:10]}\">\n"
        f"TITLE: {s['title']}\n{s['text']}\n</raise_candidate>"
        for s in raise_candidates
    ) or "(none today)"
    articles = "\n\n".join(
        f"<article id=\"{s['id']}\" source=\"{s['source']}\">\nTITLE: {s['title']}\n{s['text']}\n</article>"
        for s in stories
    )
    return f"""{READER}

Write the newsletter copy for these articles. For each one, write:
- headline: a clear, plain-English headline (under 14 words, no clickbait)
- summary: 2–3 sentences covering what happened and why it matters. Include the concrete
  numbers (dollar amounts, valuations, investors, dates) when the article has them.
  Stick strictly to what the article says.

Also write big_picture: 2 sentences tying together the day's main theme, like the opening
line of a well-written morning newsletter.

Finally, fill in raises from the raise candidates below. Include a raise ONLY if all are true:
- the company is headquartered in Utah (not just operating there — check the text),
- the round is pre-seed, seed, Series A, or Series B,
- it's a new announcement dated within the last {settings.RAISES_DAYS} days, not an old round
  being re-posted (check the dates in the text; if unsure, leave it out).
For each: id, company, city, round (e.g. "Seed", "Series A"), amount (e.g. "$15M"),
lead (lead investor(s), or "" if not stated), about (what the company does, under 10 words),
announced (YYYY-MM-DD). Use only facts in the text. A story can be both a newsletter story
and a raise.

{articles}

Raise candidates:
{raise_articles}"""


# Shapes of Claude's answers (used for the API mode, and to check data/today.json).

class Pick(BaseModel):
    id: int
    section: str


class Selection(BaseModel):
    picks: list[Pick]
    raise_ids: list[int] = []


class Summary(BaseModel):
    id: int
    headline: str
    summary: str


class Raise(BaseModel):
    id: int
    company: str
    city: str
    round: str
    amount: str
    lead: str
    about: str
    announced: str


class Digest(BaseModel):
    big_picture: str
    stories: list[Summary]
    raises: list[Raise] = []


def ask_claude(client, prompt, schema):
    response = client.messages.parse(
        model=settings.MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
        # If Claude's safety filter ever declines a request, retry on a fallback model
        # automatically instead of failing the whole digest.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    )
    if response.stop_reason == "refusal":
        sys.exit("Claude declined this request — try again later.")
    return response.parsed_output


def add_article_text(stories):
    with ThreadPoolExecutor(max_workers=8) as pool:
        for story, text in zip(stories, pool.map(fetch_article_text, stories)):
            story["text"] = text
    return stories


# ─── Put it all together ─────────────────────────────────────────────────────

CANDIDATES_FILE = HERE / "data" / "candidates.json"
TODAY_FILE = HERE / "data" / "today.json"


def get_fresh_stories(seen):
    print("Fetching feeds…")
    stories = fetch_all_feeds()
    # Skip stories from earlier days' briefs. Stories first seen *today* stay eligible, so
    # re-running (e.g. hitting "Run now" twice) rebuilds today's brief instead of emptying it.
    today = datetime.now().date().isoformat()
    fresh = [s for s in stories if s["url"] not in seen or seen[s["url"]]["date"] == today]
    fresh.sort(key=lambda s: s["published"], reverse=True)
    for i, s in enumerate(fresh):
        s["id"] = i
    print(f"  {len(stories)} recent stories, {len(fresh)} you haven't seen")
    return fresh


def build_sections(candidates, digest):
    """Turn Claude's picks + summaries into {section: [stories]} in Claude's order."""
    by_id = {s["id"]: s for s in candidates}
    sections = {name: [] for name in settings.SECTIONS}
    for item in digest["stories"]:
        story = by_id.get(item["id"])
        if story and item.get("section") in sections:
            sections[item["section"]].append({**story, **item})
    return sections


def save_page(sections, big_picture):
    """Save today's brief as data, then rebuild the combined page."""
    today = datetime.now()
    brief = {
        "date": today.date().isoformat(),
        "big_picture": big_picture,
        "sections": {
            name: [{k: s[k] for k in ("headline", "summary", "source", "link")} for s in items]
            for name, items in sections.items()
        },
    }
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEFS_DIR / f"{brief['date']}.json").write_text(json.dumps(brief, indent=1))
    return page.build()


def save_raises(candidates, raises):
    """Add newly found Utah rounds to data/utah_raises.json (one entry per company + round)."""
    by_id = {s["id"]: s for s in candidates}
    ledger = json.loads(RAISES_FILE.read_text()) if RAISES_FILE.exists() else []
    known = {(r["company"].lower(), r["round"].lower()) for r in ledger}
    added = 0
    for r in raises:
        key = (r["company"].lower(), r["round"].lower())
        if key in known or r["id"] not in by_id:
            continue
        ledger.append({k: v for k, v in r.items() if k != "id"} | {"link": by_id[r["id"]]["link"]})
        known.add(key)
        added += 1
    RAISES_FILE.parent.mkdir(exist_ok=True)
    RAISES_FILE.write_text(json.dumps(ledger, indent=1))
    return added


def remember(seen, candidates, sections):
    """Mark every story Claude considered as seen, so tomorrow only brings new ones."""
    today = datetime.now().date().isoformat()
    shown_urls = {s["url"] for items in sections.values() for s in items}
    for s in candidates:
        seen[s["url"]] = {"title": s["title"], "date": today, "shown": s["url"] in shown_urls}
    save_seen(seen)


# --- Subscription mode: three small steps, with Claude working in between ---

def cmd_prepare():
    seen = load_seen()
    fresh = get_fresh_stories(seen)
    CANDIDATES_FILE.parent.mkdir(exist_ok=True)
    CANDIDATES_FILE.write_text(json.dumps(fresh, indent=1))
    TODAY_FILE.unlink(missing_ok=True)
    if not fresh:
        print("Nothing new since your last digest.")
        return
    print("\n" + selection_prompt(fresh, recently_shown_headlines(seen)))
    print("\nNEXT: run `digest.py articles <story ids> --raises <raise ids>` (omit --raises if none).")


def cmd_articles(ids, raise_ids):
    candidates = {s["id"]: s for s in json.loads(CANDIDATES_FILE.read_text())}
    chosen = add_article_text([candidates[i] for i in ids if i in candidates])
    raise_candidates = add_article_text([candidates[i] for i in raise_ids if i in candidates])
    print(summary_prompt(chosen, raise_candidates))
    print(f"""
NEXT: write {TODAY_FILE} as JSON shaped like:
{{"big_picture": "...",
  "stories": [{{"id": 12, "section": "{next(iter(settings.SECTIONS))}", "headline": "...", "summary": "..."}}],
  "raises": [{{"id": 40, "company": "...", "city": "Lehi", "round": "Seed", "amount": "$5M",
              "lead": "...", "about": "...", "announced": "2026-09-25"}}]}}
List stories in newsletter order (most important first within each section).
Sections must be exactly one of: {", ".join(settings.SECTIONS)}. Then run `digest.py publish`.""")


def cmd_publish():
    candidates = json.loads(CANDIDATES_FILE.read_text())
    digest = json.loads(TODAY_FILE.read_text())
    Digest.model_validate(digest)  # fails loudly if the file is malformed
    sections = build_sections(candidates, digest)
    if not any(sections.values()):
        sys.exit("today.json didn't match any candidate stories — nothing published.")
    added = save_raises(candidates, digest.get("raises", []))
    out = save_page(sections, digest["big_picture"])
    remember(load_seen(), candidates, sections)
    CANDIDATES_FILE.unlink()
    TODAY_FILE.unlink()
    print(f"Published {sum(map(len, sections.values()))} stories and {added} new Utah raises → {out}")


# --- API-key mode: everything in one go ---

def cmd_api():
    seen = load_seen()
    fresh = get_fresh_stories(seen)
    if not fresh:
        print("Nothing new since your last digest.")
        return
    client = anthropic.Anthropic()
    try:
        print("Claude is picking the top stories…")
        selection = ask_claude(client, selection_prompt(fresh, recently_shown_headlines(seen)), Selection)
        by_id = {s["id"]: s for s in fresh}
        chosen = [{**by_id[p.id], "section": p.section} for p in selection.picks if p.id in by_id]
        raise_candidates = [by_id[i] for i in selection.raise_ids if i in by_id]

        print(f"Reading {len(chosen) + len(raise_candidates)} articles…")
        add_article_text(chosen)
        add_article_text(raise_candidates)

        print("Claude is writing summaries…")
        written = ask_claude(client, summary_prompt(chosen, raise_candidates), Digest)
    except anthropic.AuthenticationError:
        sys.exit("No valid Anthropic API key found. See README.md.")
    except anthropic.RateLimitError:
        sys.exit("Hit the API rate limit — wait a minute and run again.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Claude API error ({e.status_code}): {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Couldn't reach the Claude API — check your internet connection.")

    section_of = {s["id"]: s["section"] for s in chosen}
    order = {s["id"]: n for n, s in enumerate(chosen)}
    stories = sorted(
        ({**w.model_dump(), "section": section_of[w.id]} for w in written.stories if w.id in section_of),
        key=lambda w: order[w["id"]],
    )
    sections = build_sections(fresh, {"stories": stories})
    save_raises(fresh, [r.model_dump() for r in written.raises])
    out = save_page(sections, written.big_picture)
    remember(seen, fresh, sections)
    print(f"Done → {out}")


def cmd_preview():
    """Layout check with no AI: newest items per feed section, raw feed text."""
    fresh = get_fresh_stories(load_seen())
    sections = {
        name: [{**s, "headline": s["title"], "summary": s["blurb"][:300]}
               for s in fresh if s["feed_section"] == name][: cfg["stories"]]
        for name, cfg in settings.SECTIONS.items()
    }
    out = save_page(sections, "Preview mode — these are the newest feed items, not AI-picked or summarized.")
    print(f"Preview → {out}  (nothing marked as seen)")


def main():
    parser = argparse.ArgumentParser(description="Build the Morning Brief.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare", help="fetch unseen stories and print picking instructions")
    arts = sub.add_parser("articles", help="print full text of chosen story ids")
    arts.add_argument("ids", type=int, nargs="*")
    arts.add_argument("--raises", type=int, nargs="*", default=[], help="candidate ids to check for Utah raises")
    sub.add_parser("publish", help="build the page from data/today.json")
    sub.add_parser("api", help="do everything automatically with an Anthropic API key")
    sub.add_parser("preview", help="layout preview, no AI")
    args = parser.parse_args()

    if args.command == "articles":
        cmd_articles(args.ids, args.raises)
    else:
        {"prepare": cmd_prepare, "publish": cmd_publish, "api": cmd_api, "preview": cmd_preview}[args.command]()


if __name__ == "__main__":
    main()
