"""
Everything you might want to tweak lives in this file.
Change a value, save, and the next run picks it up — no other code to touch.
"""

# ─── AI settings (only used by the optional `digest.py api` mode) ─────────────
MODEL = "claude-opus-5"


# ─── Newsletter sections ──────────────────────────────────────────────────────
# Sections appear in this order. For each one:
#   stories  = the most stories to show (fewer if the news is thin)
#   hours    = how far back to look (Utah news is slower, so it looks back a week)
#   about    = what belongs in the section (Claude reads this when picking)
#   feeds    = (source name, RSS feed URL). To add a source, find its RSS feed
#              (usually site.com/feed) and add a line.
SECTIONS = {
    "AI Startups": {
        "stories": 2,
        "hours": 36,
        "about": "The big AI startups — OpenAI, Anthropic, xAI, Mistral, Perplexity, and peers: "
                 "launches, funding, valuations, deals, strategy shifts.",
        "feeds": [
            ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
            ("The Information", "https://www.theinformation.com/feed"),
            ("The Decoder", "https://the-decoder.com/feed/"),
            ("Axios", "https://api.axios.com/feed/"),
        ],
    },
    "Fast-Growing Startups": {
        "stories": 2,
        "hours": 72,  # startup outlets barely publish on weekends, so look back 3 days
        "about": "Younger, fast-growing startups with under ~1,000 employees: big rounds, breakout "
                 "growth, notable launches. Not the giant AI labs above and not public companies.",
        "feeds": [
            ("TechCrunch Startups", "https://techcrunch.com/category/startups/feed/"),
            ("TechCrunch Venture", "https://techcrunch.com/category/venture/feed/"),
            ("Crunchbase News", "https://news.crunchbase.com/feed/"),
        ],
    },
    "Utah Tech": {
        "stories": 2,
        "hours": 168,
        "about": "Utah tech companies and Utah's startup scene (Silicon Slopes). The story must "
                 "actually be about a Utah-based company or Utah's tech ecosystem.",
        "feeds": [
            ("TechBuzz News", "https://www.techbuzznews.com/feed/"),
            ("Utah Money Watch", "https://www.utahmoneywatch.com/feed/"),
            ("Utah VC", "https://utah.vc/feed"),
            ("Google News", "https://news.google.com/rss/search?q=Utah+tech+startup+when:7d&hl=en-US&gl=US&ceid=US:en"),
        ],
    },
}

# ─── Utah Raises table ────────────────────────────────────────────────────────
# Utah companies announcing a pre-seed, seed, Series A, or Series B round.
# The table shows rounds announced in the last RAISES_DAYS days.
RAISES_DAYS = 10
RAISES_FEEDS = [
    ("Utah Money Watch", "https://www.utahmoneywatch.com/feed/"),
    ("Utah VC", "https://utah.vc/feed"),
    ("TechBuzz News", "https://www.techbuzznews.com/feed/"),
    ("Google News", "https://news.google.com/rss/search?q=Utah+(%22pre-seed%22+OR+%22seed+round%22+OR+%22Series+A%22+OR+%22Series+B%22)+when:10d&hl=en-US&gl=US&ceid=US:en"),
]


# ─── Startups to watch for jobs ───────────────────────────────────────────────
# Young startups, roughly 300 people or fewer. Headcounts are estimates and change
# fast, so prune anything that has gotten big.
#   provider: greenhouse, lever, ashby, rippling, bamboohr, or hirehive
#   board:    the id in the company's job-board link, e.g. jobs.ashbyhq.com/<board>
COMPANIES = [
    # Utah
    {"name": "Jump", "region": "Utah", "provider": "ashby", "board": "jump-app",
     "about": "AI assistant for financial advisors"},
    {"name": "Tava Health", "region": "Utah", "provider": "ashby", "board": "tavahealth",
     "about": "Mental health care for employers"},
    {"name": "Zanskar", "region": "Utah", "provider": "lever", "board": "zanskar",
     "about": "AI-driven geothermal energy"},
    {"name": "Enzo Health", "region": "Utah", "provider": "rippling", "board": "enzo-health",
     "about": "AI for home health agencies"},
    {"name": "AskElephant", "region": "Utah", "provider": "ashby", "board": "askelephant",
     "about": "AI revenue platform for sales teams"},
    {"name": "Clozd", "region": "Utah", "provider": "lever", "board": "clozd",
     "about": "Win-loss analysis for B2B sales"},
    {"name": "Redo", "region": "Utah", "provider": "hirehive", "board": "redo",
     "about": "Returns and post-purchase software for online stores"},
    {"name": "Neighbor", "region": "Utah", "provider": "lever", "board": "neighbor",
     "about": "Peer-to-peer storage marketplace"},
    {"name": "Boostly", "region": "Utah", "provider": "ashby", "board": "boostly",
     "about": "Text marketing for restaurants"},
    {"name": "Brevium", "region": "Utah", "provider": "greenhouse", "board": "brevium",
     "about": "Patient reactivation software for clinics"},
    {"name": "SponsorCX", "region": "Utah", "provider": "bamboohr", "board": "sponsorcx",
     "about": "Sponsorship CRM for sports teams"},
    {"name": "SchoolAI", "region": "Utah", "provider": "rippling", "board": "schoolai",
     "about": "AI tools for classrooms"},
    {"name": "Databento", "region": "Utah", "provider": "greenhouse", "board": "databento",
     "about": "Market data API for traders"},
    {"name": "TaxBit", "region": "Utah", "provider": "greenhouse", "board": "taxbit",
     "about": "Crypto tax and accounting software"},
    {"name": "Canopy", "region": "Utah", "provider": "greenhouse", "board": "canopytax",
     "about": "Practice management for accounting firms"},
    {"name": "Route", "region": "Utah", "provider": "greenhouse", "board": "route",
     "about": "Package tracking and protection for online stores"},
    {"name": "Gabb", "region": "Utah", "provider": "lever", "board": "gabbwireless",
     "about": "Safe phones and watches for kids"},
    {"name": "Workstream", "region": "Utah", "provider": "greenhouse", "board": "workstream",
     "about": "Hiring and HR for hourly workforces"},
    {"name": "YouScience", "region": "Utah", "provider": "rippling", "board": "youscience",
     "about": "Career aptitude platform for students"},

    # Bay Area
    {"name": "Rillet", "region": "Bay Area", "provider": "ashby", "board": "rillet",
     "about": "AI-native accounting ERP"},
    {"name": "Numeric", "region": "Bay Area", "provider": "ashby", "board": "numeric",
     "about": "AI for the accounting close"},
    {"name": "Campfire", "region": "Bay Area", "provider": "ashby", "board": "campfire",
     "about": "AI accounting platform"},
    {"name": "Finch", "region": "Bay Area", "provider": "lever", "board": "finch",
     "about": "Unified API for payroll and HR data"},
    {"name": "Pylon", "region": "Bay Area", "provider": "ashby", "board": "pylon",
     "about": "Customer support platform for B2B"},
    {"name": "Unify", "region": "Bay Area", "provider": "ashby", "board": "unify",
     "about": "AI outbound sales platform"},
    {"name": "Artisan", "region": "Bay Area", "provider": "ashby", "board": "artisan",
     "about": "AI sales agents"},
    {"name": "Gamma", "region": "Bay Area", "provider": "ashby", "board": "gamma",
     "about": "AI presentations and docs"},
    {"name": "Julius", "region": "Bay Area", "provider": "ashby", "board": "julius",
     "about": "AI data analyst"},
    {"name": "Hex", "region": "Bay Area", "provider": "ashby", "board": "hex",
     "about": "Collaborative data analytics"},
    {"name": "Mintlify", "region": "Bay Area", "provider": "ashby", "board": "mintlify",
     "about": "Developer documentation platform"},
    {"name": "Browserbase", "region": "Bay Area", "provider": "ashby", "board": "browserbase",
     "about": "Web browsers for AI agents"},
    {"name": "Reducto", "region": "Bay Area", "provider": "ashby", "board": "reducto",
     "about": "Document parsing for AI"},
    {"name": "Vapi", "region": "Bay Area", "provider": "ashby", "board": "vapi",
     "about": "Voice AI agent platform"},
    {"name": "Cartesia", "region": "Bay Area", "provider": "ashby", "board": "cartesia",
     "about": "Real-time voice AI models"},
    {"name": "Sesame", "region": "Bay Area", "provider": "ashby", "board": "sesame",
     "about": "Conversational voice AI"},
    {"name": "Physical Intelligence", "region": "Bay Area", "provider": "ashby", "board": "physicalintelligence",
     "about": "AI models for robots"},
    {"name": "Pika", "region": "Bay Area", "provider": "ashby", "board": "pika",
     "about": "AI video generation"},
    {"name": "Decagon", "region": "Bay Area", "provider": "ashby", "board": "decagon",
     "about": "AI customer service agents"},
    {"name": "Baseten", "region": "Bay Area", "provider": "ashby", "board": "baseten",
     "about": "Infrastructure for running AI models"},
    {"name": "Mercor", "region": "Bay Area", "provider": "ashby", "board": "mercor",
     "about": "AI-powered hiring and expert marketplace"},
    {"name": "Replit", "region": "Bay Area", "provider": "ashby", "board": "replit",
     "about": "AI app-building platform"},
]

# A job shows up if its location matches its region's keywords (or says remote).
REGION_LOCATIONS = {
    "Utah": [
        "utah", ", ut", " ut,", " ut ", "salt lake", "lehi", "provo", "draper", "orem",
        "lindon", "sandy", "south jordan", "american fork", "park city", "ogden", "main office",
    ],
    "Bay Area": [
        "san francisco", " sf", "sf,", "bay area", "palo alto", "mountain view", "menlo park",
        "san mateo", "redwood city", "sunnyvale", "san jose", "oakland", "berkeley",
    ],
}
REMOTE_KEYWORDS = ["remote", "united states", "us-remote", "us remote"]

# Skip roles based outside the US, even when they're marked remote.
NON_US_KEYWORDS = [
    "london", " uk", "united kingdom", "europe", "emea", "india", "canada", "toronto",
    "germany", "poland", "latam", "mexico", "brazil", "apac", "australia", "singapore",
]

# Role categories → title keywords. A job lands in the FIRST category it matches.
# Keywords are matched against the lowercase job title.
ROLE_CATEGORIES = {
    "Finance & Strategy": [
        "strategic finance", "fp&a", "financial analyst", "finance", "corporate development",
        "corp dev", "investor relations", "treasury", "m&a", "strategy", "bizops",
        "business operations", "chief of staff", "pricing", "operations associate",
        "operations analyst", "founding operator", "deployment strategist",
    ],
    "Sales & BD": [
        "sdr", "bdr", "sales development", "business development", "junior account executive",
        "associate account executive", "partnerships", "partner manager", "growth associate",
    ],
    "Product & Analytics": [
        "product analyst", "associate product manager", "product operations",
        "data analyst", "business analyst", "analytics", "insights",
        "revenue operations", "revops", "sales operations", "gtm operations",
        "go-to-market operations",
    ],
    "Internships": ["intern", "internship", "co-op"],
}

# Skip any job whose description requires this many years of experience or more.
# 1 = undergrad roles only: any stated experience requirement ("1+ year", "3-5 years",
# "at least two years"...) rules a job out. Lines saying "preferred" don't count.
MAX_YEARS_EXPERIENCE = 1

# Titles containing any of these are skipped (too senior or not a fit).
EXCLUDE_TITLE_KEYWORDS = [
    "vp", "vice president", "director", "head of", "principal", "staff ",
    "senior", "sr.", "sr ", " lead", "lead,", "leader",
    "engineer", "developer", "chief financial", "cfo", "counsel", "attorney",
    "accounts payable", "payroll", "tax manager", "design", "ux ", "recruit",
    "clinician", "nurse", "physician", "research", "mechatronics", "hardware",
    "robotics", "machine learning", "software", "firmware", "product marketing",
    "data scientist", "data science",
]

# Titles containing these get an "Early career" tag...
EARLY_CAREER_KEYWORDS = [
    "intern", "associate", "analyst", "sdr", "bdr", "sales development",
    "coordinator", "junior", "entry", "new grad", "rotational", "representative",
]

# ...unless the title also says one of these.
NOT_EARLY_KEYWORDS = ["senior", "sr.", "sr ", "manager", "lead"]
