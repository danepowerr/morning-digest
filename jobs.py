"""
Startup Jobs — finds roles at young Utah and Bay Area startups that fit a finance / IB background.

How it works:
  1. Read the public job board of every company in settings.COMPANIES
  2. Keep jobs in the company's region (or remote) whose titles match settings.ROLE_CATEGORIES,
     then read each description and drop anything that asks for 2+ years of experience
  3. Remember when each job first appeared (data/seen_jobs.json) so new ones get a badge
  4. Log each company's total openings per day (data/job_history.json) as a growth signal
  5. Save everything to data/jobs.json and rebuild output/index.html

Run it:  .venv/bin/python jobs.py
"""

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import page
import settings

HERE = Path(__file__).parent
SEEN_FILE = HERE / "data" / "seen_jobs.json"
HISTORY_FILE = HERE / "data" / "job_history.json"
JOBS_FILE = HERE / "data" / "jobs.json"
HEADERS = {"User-Agent": "Mozilla/5.0 MorningDigest/1.0", "Accept": "application/json"}


# ─── Step 1: read each job board (each provider formats data a bit differently) ─

def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def from_greenhouse(board):
    for j in get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")["jobs"]:
        yield {
            "id": str(j["id"]),
            "title": j["title"],
            "location": j["location"]["name"],
            "url": j["absolute_url"],
            "posted": j.get("first_published") or j.get("updated_at"),
            "description": html.unescape(j.get("content", "")),  # Greenhouse double-encodes its HTML
        }


def from_lever(board):
    for j in get(f"https://api.lever.co/v0/postings/{board}?mode=json"):
        yield {
            "id": j["id"],
            "title": j["text"],
            "location": j["categories"].get("location") or j.get("workplaceType", ""),
            "url": j["hostedUrl"],
            "posted": datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat(),
            "description": "\n".join(
                [j.get("descriptionPlain", "")]
                + [f"{x['text']}\n{x['content']}" for x in j.get("lists", [])]
                + [j.get("additionalPlain", "")]
            ),
        }


def from_ashby(board):
    for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")["jobs"]:
        if not j.get("isListed", True):
            continue
        location = j.get("location", "")
        if j.get("isRemote") and "remote" not in location.lower():
            location += " (Remote)"
        yield {
            "id": j["id"],
            "title": j["title"],
            "location": location,
            "url": j["jobUrl"],
            "posted": j.get("publishedAt"),
            "description": j.get("descriptionPlain", ""),
        }


def from_rippling(board):
    for j in get(f"https://api.rippling.com/platform/api/ats/v1/board/{board}/jobs"):
        yield {
            "id": j["uuid"],
            "title": j["name"],
            "location": (j.get("workLocation") or {}).get("label", ""),
            "url": j["url"],
            "posted": None,  # Rippling doesn't publish posting dates
            # The list doesn't include descriptions — fetched later, only for jobs that pass the title filter.
            "detail_url": f"https://api.rippling.com/platform/api/ats/v1/board/{board}/jobs/{j['uuid']}",
        }


def from_bamboohr(board):
    for j in get(f"https://{board}.bamboohr.com/careers/list")["result"]:
        where = ", ".join(x for x in (j["location"].get("city"), j["location"].get("state")) if x)
        if j.get("isRemote"):
            where = f"{where} (Remote)".strip()
        yield {
            "id": str(j["id"]),
            "title": j["jobOpeningName"],
            "location": where,
            "url": f"https://{board}.bamboohr.com/careers/{j['id']}",
            "posted": None,  # BambooHR doesn't publish posting dates
            "detail_url": f"https://{board}.bamboohr.com/careers/{j['id']}/detail",
        }


def from_hirehive(board):
    for j in get(f"https://{board}.hirehive.com/api/v1/jobs")["jobs"]:
        yield {
            "id": str(j["id"]),
            "title": j["title"],
            "location": ", ".join(x for x in (j.get("location"), j.get("stateCode")) if x),
            "url": j["hostedUrl"],
            "posted": datetime.fromtimestamp(j["publishedDate"], timezone.utc).isoformat() if j.get("publishedDate") else None,
            "description": (j.get("description") or {}).get("html", ""),
        }


PROVIDERS = {
    "greenhouse": from_greenhouse,
    "lever": from_lever,
    "ashby": from_ashby,
    "rippling": from_rippling,
    "bamboohr": from_bamboohr,
    "hirehive": from_hirehive,
}


def fetch_company(company):
    try:
        return company, list(PROVIDERS[company["provider"]](company["board"]))
    except requests.HTTPError as e:
        if e.response.status_code == 404:  # board exists on their site but nothing is posted
            return company, []
        print(f"  ! {company['name']}: couldn't read job board ({e})")
        return company, None
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"  ! {company['name']}: couldn't read job board ({e})")
        return company, None


# ─── Step 2: decide which jobs are relevant ──────────────────────────────────

def categorize(title):
    """Return the role category for a job title, or None if it's not a fit."""
    t = f" {title.lower()} "
    if any(word in t for word in settings.EXCLUDE_TITLE_KEYWORDS):
        return None
    # Managers aren't undergrad roles — except "Associate Product Manager" and similar.
    if "manager" in t and "associate" not in t:
        return None
    for category, keywords in settings.ROLE_CATEGORIES.items():
        if any(word in t for word in keywords):
            return category
    return None


def in_region(location, region):
    loc = f" {location.lower()} "
    if any(word in loc for word in settings.NON_US_KEYWORDS):
        return False
    return any(word in loc for word in settings.REGION_LOCATIONS[region] + settings.REMOTE_KEYWORDS)


def is_early_career(title):
    t = f" {title.lower()} "
    # "Associate Product Manager" is entry-level even though it says "manager".
    if any(word in t for word in settings.NOT_EARLY_KEYWORDS) and "associate" not in t:
        return False
    return any(word in t for word in settings.EARLY_CAREER_KEYWORDS)


# ─── Step 2b: read the description for experience requirements ──────────────

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10}
NUM = r"(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")"
# Matches "3+ years of experience", "3-5 years' experience", "at least two years of relevant experience", ...
YEARS_RE = re.compile(
    NUM + r"\s*(?:\+|plus)?\s*(?:(?:-|–|—|to)\s*" + NUM + r")?\s*\+?\s*(?:years?|yrs?)\b([^.\n]{0,80})",
    re.IGNORECASE,
)
# Words that make a requirement optional when they sit right next to it...
OPTIONAL_NEARBY = ("preferred", "a plus", "nice to have", "bonus")
# ...or when the requirement is listed under one of these section headings.
OPTIONAL_HEADINGS = re.compile(r"bonus|nice[- ]to[- ]have|even better|preferred qualifications|pluses", re.I)
REQUIRED_HEADINGS = re.compile(
    r"required|requirements|qualifications|you have|you bring|looking for|who you are|about you|must[- ]have", re.I)
GRAD_WORDS = ("new grad", "recent grad", "entry-level", "entry level", "graduating", "class of 20",
              "no experience required", "early-career", "early career", "internship", "current student")


def plain_text(description):
    text = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", description or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def as_number(word):
    return int(word) if word.isdigit() else NUMBER_WORDS[word.lower()]


def is_optional(text, m):
    """True when a years-of-experience mention is a nice-to-have rather than a requirement."""
    line_start = text.rfind("\n", 0, m.start()) + 1
    before = text[line_start:m.start()].lower()
    after = m.group(3).lower()[:40]
    if any(w in before or w in after for w in OPTIONAL_NEARBY) or "ideally" in before:
        return True
    # Which kind of section heading came most recently before this line?
    preceding = text[:line_start]
    last_optional = max((h.end() for h in OPTIONAL_HEADINGS.finditer(preceding)), default=-1)
    last_required = max((h.end() for h in REQUIRED_HEADINGS.finditer(preceding)), default=-1)
    return last_optional >= last_required and last_optional != -1


def required_years(text):
    """The most years of experience the posting *requires* (ignoring nice-to-haves), or None."""
    required = []
    for m in YEARS_RE.finditer(text):
        after = m.group(3).lower()
        # "3+ years of experience", "3-6 years in investment banking", "2 years as an SDR"...
        # but not "founded 10 years ago" or "8x year over year".
        if not ("experience" in after or re.match(r"\s*(of|in|at|as|working|doing)\b", after)):
            continue
        if is_optional(text, m):
            continue
        required.append(as_number(m.group(1)))
    return max(required) if required else None


def fetch_description(job):
    """Rippling and BambooHR need one extra request per job to get the description."""
    try:
        data = get(job["detail_url"])
    except (requests.RequestException, ValueError):
        return ""
    if "result" in data:  # BambooHR
        return data["result"]["jobOpening"].get("description", "")
    return " ".join(str(v) for v in (data.get("description") or {}).values())  # Rippling


def experience_label(years, text):
    lower = text.lower()
    if any(word in lower for word in GRAD_WORDS):
        return "New grad friendly"
    if years is None:
        return "No experience listed"
    return f"{years}+ yr" if years else "No experience required"


# ─── Steps 3–4: memory files ─────────────────────────────────────────────────

def load_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=1))


def tracked_since(history, company):
    """The first day we ever checked this company (today if it's brand new)."""
    days = sorted(d for d in history if company in history[d])
    return days[0] if days else datetime.now().date().isoformat()


def growth(history, company, today_count, days=30):
    """Change in total openings vs. the oldest snapshot within the last `days` days."""
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    older = sorted(d for d in history if d >= cutoff and company in history[d])
    if not older or older[0] == datetime.now().date().isoformat():
        return None
    return today_count - history[older[0]][company]


# ─── Put it all together ─────────────────────────────────────────────────────

def main():
    today = datetime.now().date().isoformat()
    seen = load_json(SEEN_FILE)
    history = load_json(HISTORY_FILE)

    print(f"Checking {len(settings.COMPANIES)} startups…")
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(fetch_company, settings.COMPANIES))

    jobs, companies, snapshot = [], [], {}
    skipped_for_experience = 0
    for company, postings in results:
        name = company["name"]
        if postings is None:
            continue
        since = tracked_since(history, name)
        snapshot[name] = len(postings)
        matched = 0
        for p in postings:
            category = categorize(p["title"])
            if not category or not in_region(p["location"], company["region"]):
                continue
            if "detail_url" in p:
                p["description"] = fetch_description(p)
            text = plain_text(p.pop("description", ""))
            p.pop("detail_url", None)
            years = required_years(text)
            if years is not None and years >= settings.MAX_YEARS_EXPERIENCE:
                skipped_for_experience += 1
                continue
            experience = experience_label(years, text)
            first_seen = seen.setdefault(f"{name}:{p['id']}", today)
            matched += 1
            jobs.append({
                **p,
                "company": name,
                "region": company["region"],
                "category": category,
                "experience": experience,
                # "Early career" = the posting itself signals it's built for new grads.
                "early": is_early_career(p["title"]) or experience in ("New grad friendly", "1+ yr", "No experience required"),
                "first_seen": first_seen,
                # Jobs that were already up the day we started tracking a company aren't "new".
                "appeared_since_tracking": first_seen > since,
            })
        companies.append({
            "name": name,
            "region": company["region"],
            "about": company["about"],
            "open": len(postings),
            "relevant": matched,
            "change": growth(history, name, len(postings)),
        })

    history[today] = snapshot
    save_json(SEEN_FILE, seen)
    save_json(HISTORY_FILE, history)

    # Newest first: jobs you've never seen before float to the top.
    jobs.sort(key=lambda j: (j["first_seen"], j["posted"] or ""), reverse=True)
    companies.sort(key=lambda c: c["open"], reverse=True)
    save_json(JOBS_FILE, {
        "updated": datetime.now().isoformat(timespec="minutes"),
        "categories": list(settings.ROLE_CATEGORIES),
        "jobs": jobs,
        "companies": companies,
    })
    out = page.build()
    print(f"  {len(jobs)} undergrad-friendly roles across {len(companies)} companies → {out}")
    print(f"  (skipped {skipped_for_experience} that ask for {settings.MAX_YEARS_EXPERIENCE}+ years of experience)")


if __name__ == "__main__":
    main()
