# Morning Digest

One page, `output/index.html`: your morning newsletter (AI · Tech · Venture · Startups · Utah)
on top, and a jobs board of young Utah and Bay Area startups below it.

## How it runs

A scheduled task in the Claude desktop app, **"Morning Brief + Utah jobs"**, runs every morning
at about 6:30 using your Claude subscription, so no API key is needed. Find it under
**Scheduled** in the sidebar, where you can also change the time or hit **Run now**.

The Claude app has to be open (or opened later) for it to run. If your Mac is asleep or the
app is closed at 6:30, it runs the next time the app is open.

Past briefs are saved as data in `data/briefs/YYYY-MM-DD.json`.

## What each piece does

| Step | Who does it |
|---|---|
| Fetch headlines, skip ones you've seen | `digest.py prepare` |
| Pick the top stories | Claude (in the morning task) |
| Download full articles | `digest.py articles <ids>` |
| Write the 2–3 sentence summaries | Claude, saved to `data/today.json` |
| Save the brief, rebuild the page, remember what you saw | `digest.py publish` |
| Refresh the jobs dashboard | `jobs.py` |

Optional: `digest.py api` does the whole thing in one shot with an Anthropic API key
(`export ANTHROPIC_API_KEY=...` in a `.env` file). This is useful if you ever want it to run
without the desktop app, for example on a server.

## Customize

Everything is in `settings.py`: news sources, stories per section, companies to track,
and which job titles count as a fit for you.

## How "no duplicates" works

- `data/seen_stories.json`: every story Claude has looked at. Tomorrow's run skips these,
  and Claude is also shown your last few days of headlines so the same news under a new
  link gets skipped too. Entries are forgotten after 30 days.
- `data/seen_jobs.json`: the first day each job appeared, which drives the "New" badge.
- `data/job_history.json`: each company's total openings per day, which drives the 30-day
  hiring trend in "Who's hiring".
