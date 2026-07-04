#!/usr/bin/env python3
"""
Upwork Quick Apply — GitHub Actions Version (Apify Edition)
------------------------------------------------------------
Computer OFF bhi kaam karta hai — GitHub ke servers pe run hota hai.
Apify neatrat/upwork-job-scraper se jobs fetch karta hai (Cloudflare bypass built-in).
Qualified jobs pe Elite Prompt v2.0 + Sonnet se proposal generate karta hai.
Email notification dono ko bhejta hai.

GitHub Secrets mein yeh set karo:
  APIFY_TOKEN          → apify.com/account/integrations se
  ANTHROPIC_API_KEY
  NOTIFY_EMAIL
  NOTIFY_EMAIL_CC
  GMAIL_USER
  GMAIL_APP_PASSWORD
"""

import os, json, re, time, random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from job_scorer import score_job, print_score_report
from notifier import notify_new_jobs

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
SEEN_JOBS_FILE      = "seen_jobs.json"
MAX_PROPOSALS       = 5
MIN_BUDGET          = 50
ACTIVE_HOURS_START  = 9    # 9 AM IST
ACTIVE_HOURS_END    = 24   # Midnight IST
SKIP_SUNDAY         = True

# ── Apify Actor ───────────────────────────────────────────────────────────────
APIFY_ACTOR = "neatrat/upwork-job-scraper"

# ── 2 broad queries instead of 15 separate calls → 7.5x fewer Apify runs ─────
# Free tier = 10 runs/month. With 2 queries: 5 workflow executions per month.
# Paid Starter ($29/mo): easily covers hourly runs at this rate.
APIFY_SEARCH_QUERIES = [
    # Niche-specific: GeoDirectory, HivePress, directories, job boards
    "GeoDirectory HivePress Brilliant Directories ListingPro WP Job Manager classified real estate",
    # General WP dev: WooCommerce, Elementor, membership, speed, general dev
    "WordPress WooCommerce Elementor MemberPress speed optimization developer directory",
]

# Original keywords — kept for client-side tagging & scoring context
APIFY_KEYWORDS = [
    # Tier-1 niche
    "GeoDirectory", "HivePress", "Brilliant Directories",
    # Directory/listing
    "WordPress directory website", "ListingPro WordPress",
    # Job boards & classifieds
    "WP Job Manager", "job board WordPress", "classified ads WordPress",
    # Real estate
    "real estate WordPress", "RealHomes theme",
    # Membership
    "WordPress membership MemberPress",
    # High-volume WP
    "WordPress speed optimization",
    "WooCommerce developer", "Elementor developer", "WordPress developer",
]

# ── Portfolio links ───────────────────────────────────────────────────────────
PORTFOLIO = {
    "geodirectory": [
        "https://opensupplyco.com/", "https://easywedding.me/",
        "https://www.thegayweddingguide.co.uk/", "https://gaydenver.com/new-home-page/",
        "https://www.motorsportprospects.com/", "https://tamarindoguide.com/",
        "https://greenvillepros.com/", "https://1mblk.com/",
    ],
    "hivepress": [
        "https://www.taskhelp.at/", "https://adoptist.com/",
        "https://mamklasyka.pl/", "https://elektricniautomobili.eu/",
        "https://directory.diffandnet.com/", "https://evnzy.com/",
    ],
    "bd": [
        "https://www.ninbb.com/", "https://www.cadgurus.com/",
        "https://realestatephotography.com/", "https://www.interiorsandbuild.com/",
        "https://www.aefreelance.com/", "https://www.blackchef.com/",
        "https://www.diversecounsel.com/",
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def now_str():
    return datetime.now().strftime("%H:%M:%S")


def is_active_hours() -> bool:
    ist     = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist)
    hour    = now_ist.hour
    weekday = now_ist.weekday()
    if SKIP_SUNDAY and weekday == 6:
        return False
    if ACTIVE_HOURS_END >= 24:
        return hour >= ACTIVE_HOURS_START
    return ACTIVE_HOURS_START <= hour < ACTIVE_HOURS_END


def load_seen_jobs() -> set:
    if Path(SEEN_JOBS_FILE).exists():
        with open(SEEN_JOBS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen)[-1000:], f, indent=2)


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_apply_link(url: str) -> str:
    match = re.search(r"~(\w+)", url)
    return (
        f"https://www.upwork.com/nx/proposals/job/~{match.group(1)}/apply/"
        if match else url
    )


def parse_spent(spent_str) -> float:
    """'$10K+' → 10000.0"""
    if not spent_str:
        return 0.0
    s = str(spent_str).replace(",", "").upper()
    nums = re.findall(r"[\d.]+", s)
    if not nums:
        return 0.0
    val = float(nums[0])
    if "K" in s:
        val *= 1_000
    elif "M" in s:
        val *= 1_000_000
    return val


def parse_budget_str(item: dict) -> str:
    """Apify item se readable budget string."""
    job_type = str(item.get("jobType", "")).lower()
    if "fixed" in job_type or "fixed" in str(item.get("budget", "")).lower():
        amt = item.get("budget") or item.get("fixedBudget") or item.get("amount")
        if amt:
            try:
                return f"${float(str(amt).replace('$','').replace(',','')):.0f} fixed"
            except Exception:
                return str(amt)
    low  = item.get("hourlyBudgetMin") or item.get("hourlyRangeLow")
    high = item.get("hourlyBudgetMax") or item.get("hourlyRangeHigh")
    if low and high:
        return f"${low}-${high}/hr"
    if low:
        return f"${low}+/hr"
    b = item.get("budget") or item.get("hourlyRange") or item.get("salary")
    return str(b).strip() if b else "Not specified"


def format_posted(posted_val) -> str:
    """ISO timestamp → '8 min ago' format."""
    if not posted_val:
        return "recently"
    s = str(posted_val)
    if "ago" in s.lower():
        return s
    try:
        from email.utils import parsedate_to_datetime
        dt  = parsedate_to_datetime(s)
        age = datetime.now(timezone.utc) - dt
        m   = int(age.total_seconds() / 60)
        return f"{m} min ago" if m < 60 else f"{m // 60}h ago"
    except Exception:
        pass
    try:
        dt  = datetime.fromisoformat(s.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - dt
        m   = int(age.total_seconds() / 60)
        return f"{m} min ago" if m < 60 else f"{m // 60}h ago"
    except Exception:
        pass
    return s[:20]


def find_matched_keyword(title: str, description: str) -> str:
    """Client-side keyword matching — tags which niche a job belongs to."""
    text = (title + " " + description).lower()
    # Check most specific first
    priority = [
        ("GeoDirectory",                    "geodirectory"),
        ("HivePress",                       "hivepress"),
        ("Brilliant Directories",           "brilliant directories"),
        ("ListingPro WordPress",            "listingpro"),
        ("WP Job Manager",                  "wp job manager"),
        ("RealHomes theme",                 "realhomes"),
        ("WordPress membership MemberPress","memberpress"),
        ("WooCommerce developer",           "woocommerce"),
        ("Elementor developer",             "elementor"),
        ("real estate WordPress",           "real estate"),
        ("classified ads WordPress",        "classified"),
        ("job board WordPress",             "job board"),
        ("WordPress speed optimization",    "speed optimization"),
        ("WordPress directory website",     "directory"),
        ("WordPress developer",             "wordpress"),
    ]
    for keyword, term in priority:
        if term in text:
            return keyword
    return "WordPress developer"


# ── Apify Scraping ────────────────────────────────────────────────────────────
def scrape_jobs_apify() -> list:
    """
    Apify neatrat/upwork-job-scraper actor se jobs fetch karo.
    2 broad queries → 15 niche keywords cover hote hain client-side matching se.
    Free tier: 10 runs/month. Paid Starter ($29/mo): ~720 runs/month capacity.
    """
    try:
        from apify_client import ApifyClient
    except ImportError:
        print("  [Apify] apify-client not installed")
        return []

    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        print("  [Apify] APIFY_TOKEN secret missing — skipping")
        return []

    client    = ApifyClient(token)
    all_jobs  = []
    seen_urls = set()

    print(f"\n[{now_str()}] Apify scraping ({len(APIFY_SEARCH_QUERIES)} queries → {len(APIFY_KEYWORDS)} keywords)...\n")

    for query in APIFY_SEARCH_QUERIES:
        try:
            run = client.actor(APIFY_ACTOR).call(
                run_input={
                    "query":           query,
                    "maxJobAge":       {"value": 24, "unit": "hours"},
                    "sortOrder":       "newest",          # Freshest jobs first
                    "resultsPerPage":  50,                # Max results per page
                    "experienceLevel": ["intermediate", "expert"],  # Skip entry-level/low-budget
                },
            )
            dataset_id = run.get("defaultDatasetId", "")
            if not dataset_id:
                print(f"  [{query[:40]:40s}] no dataset")
                continue

            count = 0
            for item in client.dataset(dataset_id).iterate_items():
                job_url = (
                    item.get("url") or item.get("link") or
                    item.get("jobUrl") or ""
                ).strip().split("?")[0]

                if not job_url or job_url in seen_urls:
                    continue
                seen_urls.add(job_url)

                match   = re.search(r"~(\w+)", job_url)
                job_id  = match.group(1) if match else ""

                raw_skills = item.get("skills") or item.get("requiredSkills") or []
                if isinstance(raw_skills, str):
                    raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

                client_info = item.get("clientInfo") or item.get("client") or {}
                if isinstance(client_info, str):
                    client_info = {}

                title       = (item.get("title") or item.get("jobTitle") or "").strip()
                description = (item.get("description") or item.get("jobDescription") or "")[:600]

                all_jobs.append({
                    "id":               job_url,
                    "title":            title,
                    "description":      description,
                    "url":              job_url,
                    "apply_link":       f"https://www.upwork.com/nx/proposals/job/~{job_id}/apply/" if job_id else job_url,
                    "budget":           parse_budget_str(item),
                    "skills":           [str(s) for s in raw_skills][:8],
                    "posted":           format_posted(
                        item.get("postedTime") or item.get("createdOn") or
                        item.get("publishedDate") or item.get("date")
                    ),
                    "payment_verified": bool(
                        item.get("paymentVerified") or item.get("isPaymentVerified") or
                        client_info.get("paymentVerified") or False
                    ),
                    "client_spent":     parse_spent(
                        item.get("clientTotalSpent") or item.get("totalSpent") or
                        client_info.get("totalSpent") or ""
                    ),
                    "client_country":   str(
                        item.get("clientCountry") or item.get("country") or
                        client_info.get("country") or ""
                    ),
                    "matched_keyword":  find_matched_keyword(title, description),
                })
                count += 1

            print(f"  [{query[:40]:40s}] {count} jobs")
            time.sleep(0.5)

        except Exception as e:
            print(f"  [{query[:40]:40s}] error: {e}")

    print(f"\n  ✓ Total unique jobs: {len(all_jobs)}")
    return all_jobs


def filter_new_jobs(jobs: list, seen: set) -> list:
    new = []
    for job in jobs:
        if job["id"] in seen:
            continue
        nums = re.findall(r"\d+", job.get("budget", "").replace(",", ""))
        if nums and max(int(n) for n in nums) < MIN_BUDGET:
            continue
        new.append(job)
    new.sort(key=lambda j: j.get("client_spent", 0), reverse=True)
    return new


# ── Portfolio Detection ───────────────────────────────────────────────────────
def detect_job_type(job: dict) -> str:
    text = (
        job.get("title", "") + " " +
        job.get("description", "") + " " +
        " ".join(str(s) for s in job.get("skills", []))
    ).lower()
    if any(k in text for k in ["hivepress", "hive press", "rental marketplace",
                                "peer-to-peer", "booking marketplace"]):
        return "hivepress"
    if any(k in text for k in ["geodirectory", "geo directory", "geo-directory",
                                "city guide", "local directory", "business directory",
                                "map directory"]):
        return "geodirectory"
    return "bd"


def get_portfolio_links(job_type: str, count: int = 3) -> list:
    pool = PORTFOLIO.get(job_type, PORTFOLIO["bd"])
    return random.sample(pool, min(count, len(pool)))


# ── Proposal Generation — Elite Prompt v2.0 + Claude Sonnet ──────────────────
def generate_cover_letter(job: dict) -> str:
    import anthropic
    client = anthropic.Anthropic()

    job_type        = detect_job_type(job)
    portfolio_links = get_portfolio_links(job_type)
    portfolio_str   = "\n".join(f"- {link}" for link in portfolio_links)

    labels = {"geodirectory": "GeoDirectory", "hivepress": "HivePress", "bd": "BD/WordPress"}
    print(f"    Type: {labels[job_type]} → portfolio injected")

    system_prompt = f"""# Claude System Prompt — Elite Upwork Proposal Strategist v2.0

## ROLE
You are an elite Upwork Proposal Strategist, Sales Consultant, Client Psychology Expert, and Technical Solution Architect.
Your job is to maximize the probability of receiving a client reply, interview invitation, and project award.
Every proposal must feel personally written by an experienced consultant after studying the client's business.
Never generate generic proposals. Never sound like AI. Optimize for trust before selling.

# ABOUT ME
Bharat A. — GeoDirectory specialist, 50+ GeoDirectory sites built, HivePress expert (30+ marketplaces), 124 Upwork jobs, Top Rated, 96% JSS, 5.0 stars.
Strengths: Business-first, excellent communication, clean code, long-term support, honest estimates, fast response.
Never invent experience. Never fabricate numbers or projects.

# RELEVANT PORTFOLIO (use 1-2 naturally in proposal — not as a list)
{portfolio_str}

# GLOBAL RULES
Always write for one specific client. Never use templates. Never exaggerate.
Never use emojis, hype, or AI words (excited/passionate/leverage/utilize/best-in-class).
Never sound like AI. Trust first, sales second.
Think like an experienced consultant — not a freelancer trying to win every job."""

    user_prompt = f"""Analyze this Upwork job and write a winning proposal.

JOB:
Title: {job['title']}
Skills: {', '.join(str(s) for s in job.get('skills', []))}
Budget: {job['budget']}
Matched via keyword: {job.get('matched_keyword', '')}
Description: {job['description'][:600]}

Internally perform (do NOT output):
1. Job analysis: goal, pain points, hidden goal, urgency
2. Client psychology: type, fears, buying motivation
3. Hidden problems client hasn't considered
4. Proposal strategy selection
5. 3 hooks (curiosity/business/technical) — pick strongest

OUTPUT ONLY:

## 6. Winning Proposal
[Ready to paste. Reference 1-2 portfolio links naturally.
Length: small fix=80-150w, small=150-250w, medium=250-450w, large=400-700w.
Flow: Hook → Understanding → Solution → Why Me → Suggestion → Soft CTA
Never start: Hi/Hello/Dear/I am. Vary sentence lengths.]

## 7. Smart Questions
[3-5 expert questions. Skip anything already answered in post.]"""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    full = resp.content[0].text.strip()

    proposal = full
    if "## 6. Winning Proposal" in full:
        start    = full.index("## 6. Winning Proposal") + len("## 6. Winning Proposal")
        end      = full.index("## 7.", start) if "## 7." in full[start:] else len(full)
        proposal = full[start:end].strip()
    return proposal


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"  Upwork Quick Apply (GitHub Actions + Apify) — {now_str()}")
    print(f"  Keyword groups: {len(APIFY_KEYWORDS)} | Apify queries: {len(APIFY_SEARCH_QUERIES)}")
    print(f"{'='*55}\n")

    if not is_active_hours():
        ist     = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist)
        day     = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][now_ist.weekday()]
        print(f"[{now_str()}] Off-hours ({now_ist.strftime('%H:%M')} IST, {day}) — skip.")
        return

    seen     = load_seen_jobs()
    raw_jobs = scrape_jobs_apify()
    new_jobs = filter_new_jobs(raw_jobs, seen)

    print(f"New jobs after filter: {len(new_jobs)}")
    if not new_jobs:
        print(f"[{now_str()}] Koi naya relevant job nahi mila.")
        return

    MAX_SCORE = 10
    print(f"\n🤖 AI Scoring (top {MAX_SCORE})...")
    qualified, skill_jobs, skipped = [], [], []

    for job in new_jobs[:MAX_SCORE]:
        score_result        = score_job(job, use_ai=True)
        job["score_result"] = score_result
        print_score_report(job, score_result)

        action = score_result.get("action", "SKIP")
        if action == "APPLY":
            qualified.append(job)
        elif action == "SKILL":
            skill_jobs.append(job)
        else:
            skipped.append(job)

        if len(qualified) >= MAX_PROPOSALS:
            break

    print(f"\n✅ APPLY: {len(qualified)} | 📚 SKILL: {len(skill_jobs)} | 🚫 SKIP: {len(skipped)}")

    if skill_jobs:
        path2 = Path("skill_gaps.json")
        log   = json.loads(path2.read_text()) if path2.exists() else []
        for j in skill_jobs:
            log.append({
                "date":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                "title":  j.get("title", ""),
                "url":    j.get("url", ""),
                "budget": j.get("budget", ""),
                "score":  j["score_result"]["final_score"],
                "reason": j["score_result"]["reason"],
            })
        path2.write_text(json.dumps(log[-50:], indent=2))

    for j in new_jobs[:MAX_SCORE]:
        seen.add(j["id"])
    save_seen_jobs(seen)

    if not qualified:
        print(f"[{now_str()}] Koi job 65% threshold cross nahi kar paya.")
        return

    top_jobs  = qualified[:MAX_PROPOSALS]
    proposals = []
    print(f"\n✍️  Proposals generate kar raha hoon ({len(top_jobs)})...")
    for job in top_jobs:
        print(f"  → {job['title'][:60]}...")
        job["cover_letter"] = generate_cover_letter(job)
        proposals.append(job)
        time.sleep(1)

    notify_new_jobs(proposals)
    print(f"\n✅ {len(proposals)} proposals ready! Email sent.")


if __name__ == "__main__":
       main()
