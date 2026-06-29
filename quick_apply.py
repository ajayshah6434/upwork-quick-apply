#!/usr/bin/env python3
"""
Upwork Quick Apply â GitHub Actions Version
--------------------------------------------
Computer OFF bhi kaam karta hai â GitHub ke servers pe run hota hai.
RSS Feeds se 25 keywords ki targeted jobs fetch karta hai (FREE).
Qualified jobs pe Elite Prompt v2.0 + Sonnet se proposal generate karta hai.
Email notification dono ko bhejta hai.

GitHub Secrets mein yeh set karo:
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

# ââ Config âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
SEEN_JOBS_FILE      = "seen_jobs.json"
MAX_PROPOSALS       = 5
MIN_BUDGET          = 50
ACTIVE_HOURS_START  = 9    # 9 AM IST
ACTIVE_HOURS_END    = 24   # Midnight IST
SKIP_SUNDAY         = True

# ââ 25 RSS Keywords âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
RSS_KEYWORDS = [
    # Core specialty
    "GeoDirectory", "HivePress", "Brilliant Directories",
    "WordPress directory", "WordPress listing", "ListingPro",
    # Job boards & classifieds
    "WP Job Manager", "Listify theme", "Jobify theme",
    "job board WordPress", "ClassiPress", "classified ads WordPress",
    # Real estate
    "real estate WordPress", "RealHomes theme", "IDX WordPress",
    # Membership
    "WordPress membership", "MemberPress", "Paid Memberships Pro",
    # High-volume general WP
    "WordPress speed optimization", "Core Web Vitals WordPress",
    "WooCommerce developer", "Elementor developer",
    "WordPress migration", "ACF WordPress", "WordPress developer",
]

# ââ Portfolio links âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
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


# ââ Helpers âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
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


# ââ RSS Scraping (FREE) âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def scrape_jobs_rss() -> list:
    import feedparser

    all_jobs  = []
    seen_urls = set()

    print(f"\n[{now_str()}] RSS Feeds fetch ({len(RSS_KEYWORDS)} keywords)...\n")

    for keyword in RSS_KEYWORDS:
        url = (
            "https://www.upwork.com/ab/feed/jobs/rss"
            f"?q={keyword.replace(' ', '+')}&sort=recency"
        )
        try:
            feed  = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                job_url = entry.get("link", "")
                if not job_url or job_url in seen_urls:
                    continue
                seen_urls.add(job_url)
                description = entry.get("summary", "")
                all_jobs.append({
                    "id":               job_url,
                    "title":            entry.get("title", "").strip(),
                    "description":      strip_html(description)[:600],
                    "url":              job_url,
                    "apply_link":       get_apply_link(job_url),
                    "budget":           parse_budget(description),
                    "skills":           parse_skills(description),
                    "posted":           format_posted(entry.get("published", "")),
                    "payment_verified": False,
                    "client_spent":     0,
                    "client_country":   "",
                    "matched_keyword":  keyword,
                })
                count += 1
            print(f"  [{keyword:35s}] {count} jobs")
            time.sleep(0.3)
        except Exception as e:
            print(f"  [{keyword:35s}] error: {e}")

    print(f"\n  Total unique jobs: {len(all_jobs)}")
    return all_jobs


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def get_apply_link(url: str) -> str:
    match = re.search(r"~(\w+)", url)
    return (
        f"https://www.upwork.com/nx/proposals/job/~{match.group(1)}/apply/"
        if match else url
    )


def parse_budget(description: str) -> str:
    fixed  = re.search(r"Budget:\s*\$([0-9,]+)", description)
    hourly = re.search(r"Hourly Range:\s*\$([0-9.]+)-\$([0-9.]+)", description)
    if fixed:   return f"${fixed.group(1)} fixed"
    if hourly:  return f"${hourly.group(1)}-${hourly.group(2)}/hr"
    return "Not specified"


def parse_skills(description: str) -> list:
    match = re.search(r"Skills?:\s*(.+?)(?:\n|<br|$)", description, re.IGNORECASE)
    if match:
        return [s.strip() for s in match.group(1).split(",")][:6]
    return []


def format_posted(published: str) -> str:
    try:
        from email.utils import parsedate_to_datetime
        dt  = parsedate_to_datetime(published)
        age = datetime.now(timezone.utc) - dt
        m   = int(age.total_seconds() / 60)
        return f"{m} min ago" if m < 60 else f"{m // 60}h ago"
    except Exception:
        return "recently"


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


# ââ Portfolio Detection âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
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


# ââ Proposal Generation â Elite Prompt v2.0 + Claude Sonnet ââââââââââââââââââââ
def generate_cover_letter(job: dict) -> str:
    import anthropic
    client = anthropic.Anthropic()

    job_type        = detect_job_type(job)
    portfolio_links = get_portfolio_links(job_type)
    portfolio_str   = "\n".join(f"- {link}" for link in portfolio_links)

    labels = {"geodirectory": "GeoDirectory", "hivepress": "HivePress", "bd": "BD/WordPress"}
    print(f"    Type: {labels[job_type]} â portfolio injected")

    system_prompt = f"""# Claude System Prompt â Elite Upwork Proposal Strategist v2.0

## ROLE
You are an elite Upwork Proposal Strategist, Sales Consultant, Client Psychology Expert, and Technical Solution Architect.
Your job is to maximize the probability of receiving a client reply, interview invitation, and project award.
Every proposal must feel personally written by an experienced consultant after studying the client's business.
Never generate generic proposals. Never sound like AI. Optimize for trust before selling.

# ABOUT ME
Bharat A. â GeoDirectory specialist, 50+ GeoDirectory sites built, HivePress expert (30+ marketplaces), 124 Upwork jobs, Top Rated, 96% JSS, 5.0 stars.
Strengths: Business-first, excellent communication, clean code, long-term support, honest estimates, fast response.
Never invent experience. Never fabricate numbers or projects.

# RELEVANT PORTFOLIO (use 1-2 naturally in proposal â not as a list)
{portfolio_str}

# GLOBAL RULES
Always write for one specific client. Never use templates. Never exaggerate.
Never use emojis, hype, or AI words (excited/passionate/leverage/utilize/best-in-class).
Never sound like AI. Trust first, sales second.
Think like an experienced consultant â not a freelancer trying to win every job."""

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
5. 3 hooks (curiosity/business/technical) â pick strongest

OUTPUT ONLY:

## 6. Winning Proposal
[Ready to paste. Reference 1-2 portfolio links naturally.
Length: small fix=80-150w, small=150-250w, medium=250-450w, large=400-700w.
Flow: Hook â Understanding â Solution â Why Me â Suggestion â Soft CTA
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


# ââ Main ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def main():
    print(f"\n{'='*55}")
    print(f"  Upwork Quick Apply (GitHub Actions) â {now_str()}")
    print(f"  RSS Keywords: {len(RSS_KEYWORDS)} skills")
    print(f"{'='*55}\n")

    if not is_active_hours():
        ist     = timezone(timedelta(hours=5, minutes=30))
        now_ist = datetime.now(ist)
        day     = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][now_ist.weekday()]
        print(f"[{now_str()}] Off-hours ({now_ist.strftime('%H:%M')} IST, {day}) â skip.")
        return

    seen     = load_seen_jobs()
    raw_jobs = scrape_jobs_rss()
    new_jobs = filter_new_jobs(raw_jobs, seen)

    print(f"New jobs after filter: {len(new_jobs)}")
    if not new_jobs:
        print(f"[{now_str()}] Koi naya relevant job nahi mila.")
        return

    # AI Scoring â Haiku (top 10)
    MAX_SCORE = 10
    print(f"\nð¤ AI Scoring (top {MAX_SCORE})...")
    qualified, skill_jobs, skipped = [], [], []

    for job in new_jobs[:MAX_SCORE]:
        score_result     = score_job(job, use_ai=True)
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

    print(f"\nâ APPLY: {len(qualified)} | ð SKILL: {len(skill_jobs)} | ð« SKIP: {len(skipped)}")

    # Skill gaps log
    if skill_jobs:
        path = Path("skill_gaps.json")
        log  = json.loads(path.read_text()) if path.exists() else []
        for j in skill_jobs:
            log.append({
                "date":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                "title":  j.get("title", ""),
                "url":    j.get("url", ""),
                "budget": j.get("budget", ""),
                "score":  j["score_result"]["final_score"],
                "reason": j["score_result"]["reason"],
            })
        path.write_text(json.dumps(log[-50:], indent=2))

    # Seen jobs save (before proposal â taaki crash pe bhi save ho)
    for j in new_jobs[:MAX_SCORE]:
        seen.add(j["id"])
    save_seen_jobs(seen)

    if not qualified:
        print(f"[{now_str()}] Koi job 65% threshold cross nahi kar paya.")
        return

    # Proposals â Sonnet
    top_jobs  = qualified[:MAX_PROPOSALS]
    proposals = []
    print(f"\nâï¸  Proposals generate kar raha hoon ({len(top_jobs)})...")
    for job in top_jobs:
        print(f"  â {job['title'][:60]}...")
        job["cover_letter"] = generate_cover_letter(job)
        proposals.append(job)
        time.sleep(1)

    # Email
    notify_new_jobs(proposals)
    print(f"\nâ {len(proposals)} proposals ready! Email sent.")


if __name__ == "__main__":
    main()
