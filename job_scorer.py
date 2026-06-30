#!/usr/bin/env python3
"""
AI Win-Probability Scorer
--------------------------
Har job ko analyze karta hai aur predict karta hai ki win probability kitni hai.
Sirf 80%+ probability wale jobs ke liye proposal generate hota hai.

Scoring 2 stages mein hota hai:
  Stage 1 â Rule-based pre-filter (fast, no API cost)
  Stage 2 â Claude AI deep analysis (only if Stage 1 passes 50+)

Final score 0-100. 80+ = Apply. Baaki = Skip.
"""

import json
from datetime import datetime, timezone

# ââ Profile Context âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
PROFILE = {
    "name":       "Bharat A.",
    "title":      "GeoDirectory Expert | Brilliant Directories | WordPress | HivePress",
    "rate":       25,          # USD/hr
    "jss":        96,          # Job Success Score %
    "reviews":    91,
    "total_jobs": 124,
    "badge":      "Top Rated",

    # Niche expertise (highest win probability)
    "tier1_skills": ["geodirectory", "hivepress", "brilliant directories", "listingpro"],

    # Mid-level expertise
    "tier2_skills": [
        "wordpress directory", "directory website", "listing website",
        "job board", "business directory", "membership directory",
        "classifieds", "wordpress listing", "wp job manager"
    ],

    # General WordPress
    "tier3_skills": [
        "wordpress", "wp", "elementor", "woocommerce", "divi",
        "wordpress plugin", "wordpress theme", "wordpress customization"
    ],

    # Red flag skills (outside expertise â likely to lose)
    "outside_skills": [
        "react", "angular", "vue", "django", "laravel", "node.js",
        "shopify", "wix", "squarespace", "flutter", "android", "ios",
        "python script", "machine learning", "data science"
    ]
}

WIN_THRESHOLD  = 65   # Apply karne ke liye minimum score
SKILL_THRESHOLD = 1   # Skill match ZERO ho to kabhi apply mat karo (hard rule)


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
#  STAGE 1 â Rule-Based Scoring (no API cost)
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def score_skill_match(job: dict) -> tuple[int, str]:
    """
    Skill match score: 0-35 points

    Tier 1 (GeoDirectory/HivePress/Brilliant Dir): 35 pts â likely to lose)
    "tier2_skills": [
        "wordpress directory", "directory website", "listing website",

    Tier 2 (WordPress directory/listing):          22 pts
    Tier 3 (WordPress general):                    12 pts
    Outside expertise:                             -20 pts (hard negative)
    """
    text = (job.get("title","") + " " + job.get("description","")).lower()
    skills = [s.lower() for s in job.get("skills", [])]
    all_text = text + " " + " ".join(skills)

    # Check outside skills first
    for s in PROFILE["outside_skills"]:
        if s in all_text and s not in ("wordpress", "wp"):
            # Only penalize if it's the PRIMARY requirement
            if all_text.count(s) > all_text.count("wordpress"):
                return -20, f"Primary skill '{s}' is outside expertise"

    # Tier 1
    for s in PROFILE["tier1_skills"]:
        if s in all_text:
            return 35, f"Tier 1 match: '{s}' â near-monopoly expertise"

    # Tier 2
    for s in PROFILE["tier2_skills"]:
        if s in all_text:
            return 22, f"Tier 2 match: '{s}'"

    # Tier 3
    for s in PROFILE["tier3_skills"]:
        if s in all_text:
            return 12, f"Tier 3 match: '{s}'"

    return 0, "No skill match found"


def score_client_quality(job: dict) -> tuple[int, str]:
    """
    Client quality score: 0-25 points

    Payment verified:          +8  (critical â unverified = no payment risk)
    Total spent tiers:        +10 max
    Hire rate:                 +4  max
    Previous hires:            +3  max
    """
    client = job.get("client", {})
    score  = 0
    notes  = []

    # Payment verified (most important)
    if client.get("payment_verified") or client.get("paymentMethodVerified"):
        score += 8
        notes.append("â Payment verified")
    else:
        notes.append("â ï¸ Payment NOT verified")

    # Total spent
    spent = client.get("total_spent") or client.get("stats", {}).get("totalSpent", 0)
    if spent >= 10000:
        score += 10
        notes.append(f"ð° Spent ${spent:,.0f} (high-value client)")
    elif spent >= 5000:
        score += 8
        notes.append(f"ð° Spent ${spent:,.0f}")
    elif spent >= 1000:
        score += 5
        notes.append(f"ð° Spent ${spent:,.0f}")
    elif spent >= 200:
        score += 3
        notes.append(f"ð° Spent ${spent:,.0f}")
    elif spent == 0:
        notes.append("ð New client (no spend history)")

    # Hire rate
    hire_rate = client.get("hire_rate") or client.get("stats", {}).get("hireRate", 0)
    if hire_rate >= 0.7:
        score += 4
        notes.append(f"ð {hire_rate*100:.0f}% hire rate (hires most applicants)")
    elif hire_rate >= 0.4:
        score += 2
        notes.append(f"ð {hire_rate*100:.0f}% hire rate")

    # Total hires
    hires = client.get("total_hires") or client.get("stats", {}).get("totalHires", 0)
    if hires >= 10:
        score += 3
        notes.append(f"ð¥ {hires} total hires (experienced buyer)")
    elif hires >= 3:
        score += 2
        notes.append(f"ð¥ {hires} total hires")

    return score, " | ".join(notes)


def score_competition(job: dict) -> tuple[int, str]:
    """
    Competition score: 0-20 points

    Proposals count aur connects cost se competition estimate karo.
    Kam proposals = zzada chance of being seen first.
    """
    proposals = (
        job.get("proposalsCount") or
        job.get("proposals_count") or
        job.get("totalProposals") or
        job.get("vendor", {}).get("totalProposals") or 0
    )
    connects  = job.get("connects_cost") or job.get("applicationCost") or 0

    score = 0
    notes = []

    if proposals == 0:
        score += 20
        notes.append("ð 0 proposals yet â first mover advantage!")
    elif proposals <= 5:
        score += 17
        notes.append(f"ð Only {proposals} proposals( â very low competition")
    elif proposals <= 15:
        score += 12
        notes.append(f"ð¡ {proposals} proposals â" moderate competition")
    elif proposals <= 30:
        score += 6
        notes.append(f"ð  {proposals} proposals â high competition")
    else:
        score += 2
        notes.append(f"ð´ {proposals}+ proposals â crowded")

    # High connects cost = fewer applicants (barrier to entry)
    if connects >= 6:
        score += 3
        notes.append(f"ð {connects} connects needed (filters casual applicants)")

    return min(score, 20), " | ".join(notes)


def score_job_quality(job: dict) -> tuple[int, str]:
    """
    Job quality score: 0-20 points

    Recency, budget fit, description clarity, experience level.
    """
    score = 0
    notes = []

    # Recency (aap sabse pehle apply karo)
    posted = job.get("posted", "")
    try:
        age_mins = int(posted.replace(" min ago", "").replace(" mins ago", ""))
        if age_mins <= 5:
            score += 10
            notes.append(f"â¡ Posted just {age_mins} min ago!")
        elif age_mins <= 15:
            score += 8
            notes.append(f"â±ï¸ Posted {age_mins} min ago")
        elif age_mins <= 30:
            score += 5
            notes.append(f"ð Posted {age_mins} min ago")
        else:
            score += 2
            notes.append(f"ð Posted {age_mins} min ago")
    except Exception:
        score += 5
        notes.append("Posted recently")

    # Budget fit (profile rate $25/hr)
    budget_str = job.get("budget", "").lower()
    if "not specified" not in budget_str and budget_str:
        if "/hr" in budget_str:
            try:
                nums = [int(x.replace("$","")) for x in budget_str.split("-") if x.strip().replace("$","").isdigit()]
                if nums and max(nums) >= 20:
                    score += 5
                    notes.append(f"ðµ Hourly rate fits ({budget_str})")
                elif nums and max(nums) >= 10:
                    score += 2
                    notes.append(f"ðµ Budget slightly low ({budget_str})")
            except Exception:
                score += 3
        elif "fixed" in budget_str:
            try:
                amount = int(budget_str.replace("$","").replace("fixed","").strip())
                if amount >= 200:
                    score += 5
                    notes.append(f"ðµ Good fixed budget ({budget_str})")
                elif amount >= 50:
                    score += 3
                    notes.append(f"ðµ Moderate budget ({budget_str})")
            except Exception:
                score += 3
    else:
        score += 3   # No budget listed is neutral

    # Experience level
    exp = job.get("experience_level", "").lower()
    if "expert" in exp:
        score += 5
        notes.append("ð¯ Expert level required (less competition, higher rate)")
    elif "intermediate" in exp:
        score += 3
        notes.append("ð Intermediate level")
    elif "entry" in exp:
        notes.append("ð Entry level (more competition, lower rate)")

    return min(score, 20), " | ".join(notes)


def rule_based_score(job: dict) -> dict:
    """Stage 1: Fast rule-based scoring."""
    s_skill,  r_skill  = score_skill_match(job)
    s_client, r_client = score_client_quality(job)
    s_comp,   r_comp   = score_competition(job)
    s_job,    r_job    = score_job_quality(job)

    total = max(0, s_skill + s_client + s_comp + s_job)

    return {
        "rule_score":   total,
        "breakdown": {
            "skill_match":      {"score": s_skill,  "max": 35, "reason": r_skill},
            "client_quality":   {"score": s_client, "max": 25, "reason": r_client},
            "competition":      {"score": s_comp,   "max": 20, "reason": r_comp},
            "job_quality":      {"score": s_job,    "max": 20, "reason": r_job},
        }
    }


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
#  STAGE 2 â Claude AI Deep Analysis
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def ai_deep_analysis(job: dict, rule_result: dict) -> dict:
    """
    Stage 2: Claude analyzes the full job description for signals
    that rule-based scoring can't detect.

    Returns: { "ai_adjustment": int, "confidence": str, "green_flags": [], "red_flags": [], "verdict": str }
    """
    import anthropic
    client = anthropic.Anthropic()

    breakdown = rule_result["breakdown"]
    rule_score = rule_result["rule_score"]

    prompt = f"""You are an expert Upwork bidding strategist analyzing a job for this freelancer:

FREELANCER PROFILE:
- Name: Bharat A. (Top Rated, 96% JSS, 5.0â, 124 jobs, $25/hr)
- Core expertise: GeoDirectory plugin, HivePress, Brilliant Directories, WordPress directory/listing websites
- Strong at: WordPress customization, plugin configuration, directory/membership sites
- Weak at: React, Angular, Python scripts, mobile apps, Shopify

RULE-BASED SCORE SO FAR: {rule_score}/100
Skill match: {breakdown['sckill_match']['score']}/35 â {breakdown['skill_match']['reason']}
Client quality: {breakdown['client_quality']['score']}/25 â {breakdown['client_quality']['reason']}
Competition: {breakdown['competition']['score']}/20 â {breakdown['competition']['reason']}
Job quality: {breakdown['job_quality']['score']}/20 â {breakdown['job_quality']['reason']}

JOB TO ANANYZE:
Title: {job.get('title','')}
Budget: {job.get('budget','')}
Skills required: {job.get('skills',[])}
Experience level: {job.get('experience_level','')}
Description:
{job.get('description','')[:600]}

ANALYZE THESE FACTORS (that rules can't detect):
1. Is the job description clear and specific? (vague = risky, specific = good)
2. Any red flags: "lowest price", "simple task", "just need to...", unrealistic scope?
3. Any green flags: returning client, specific technical requirement (especially GeoDirectory/HivePress), clear deliverable?
4. Does the scope match the budget?
5. Is this client likely to be easy or difficult to work with?
6. Does Bharat have a realistic chance of winning vs typical competitors?

Respond in this EXACT JSON format:
{{
  "ai_adjustment": <integer from -20 to +20 to add to rule score>,
  "confidence": "<HBÉGH/MEDIUM/LOW>",
  "green_flags": ["flag1", "flag2"],
  "red_flags": ["flag1", "flag2"],
  "win_prediction": "<brief 1-sentence prediction>",
  "apply_recommendation": "<YES/NO/MAYBE>"
}}

Be realistic. Don't be overly optimistic."""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",   # Fast + cheap for scoring
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        import re
        text = resp.content[0].text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception:
        pass

    return {
        "ai_adjustment": 0,
        "confidence": "LOW",
        "green_flags": [],
        "red_flags": ["Could not parse AI response"],
        "win_prediction": "Uncertain",
        "apply_recommendation": "MAYBE"
    }


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
#  MAIN SCORING FUÕNCTION
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def score_job(job: dict, use_ai: bool = True) -> dict:
    """
    Full scoring pipeline.
    Returns scoring result with final probability and apply decision.
    """

    # Stage 1: Rule-based (fast)
    rule_result = rule_based_score(job)
    rule_score  = rule_result["rule_score"]

    skill_score = rule_result["breakdown"]["skill_match"]["score"]

    # ââ HARD RULE: Skill match ZERO ho to kabhi apply mat karo ââââââââââââââ
    # Chahe baaki sab perfect ho â skill nahi to apply nahi.
    if skill_score <= 0:
        return {
            "final_score":  0,
            "probability":  0,
            "should_apply": False,
            "action":       "HARD_SKIP",   # skill hi nahi â ignore
            "reason":       "â No skill match â " + rule_result["breakdown"]["skill_match"]["reason"],
            "rule_score":    0,
            "ai_adjustment": 0,
            "rule_result":  rule_result,
            "ai_result":    None,
        }

    # Stage 2: AI deep analysis (only if rule score >= 35)
    ai_result     = None
    ai_adjustment = 0

    if use_ai and rule_score >= 35:
        try:
            ai_result     = ai_deep_analysis(job, rule_result)
            ai_adjustment = ai_result.get("ai_adjustment", 0)
        except Exception as e:
            print(f"    AI scoring error: {e}")

    final_score = max(0, min(100, rule_score + ai_adjustment))

    # ââ DECISION LOGIC ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # Skill match hai, to teen possible actions:
    #   APPLY  â score >= 65  â proposal bhejo
    #   SKILL  â score 30-64  â is job mein skill gap hai, note karke seekho
    #   SKIP   â score < 30   â skill match tha but baaki sab weak
    # âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

    # Override: AI says NO strongly
    if ai_result and ai_result.get("apply_recommendation") == "NO" and len(ai_result.get("red_flags", [])) >= 3:
        final_score = min(final_score, 50)   # Force below threshold

    if final_score >= WIN_THRESHOLD:
        action       = "APPLY"
        should_apply = True
        reason       = ai_result.get("win_prediction", "Qualified") if ai_result else "Rule-based pass"
    elif final_score >= 30:
        action       = "SKILL"    # Skill match tha but probability kam hai
        should_apply = False
        gaps         = []
        if ai_result and ai_result.get("red_flags"):
            gaps = ai_result["red_flags"][:2]
        reason = f"Skill match hai but score {final_score}% â Seekhne layak: {' | '.join(gaps) if gaps else 'client quality ya competition weak'}"
    else:
        action       = "SKIP"
        should_apply = False
        reason       = f"Score {final_score}% â skill match tha but baaki criteria weak"

    return {
        "final_score":   final_score,
        "probability":   final_score,
        "should_apply":  should_apply,
        "action":        action,      # "APPLY" / "SKILL" / "SKIP" / "HARD_SKIP"
        "reason":        reason,
        "rule_score":    rule_score,
        "ai_adjustment": ai_adjustment,
        "rule_result":   rule_result,
        "ai_result":     ai_result,
    }


def print_score_report(job: dict, result: dict):
    """Console pe scoring report print karo."""
    title  = job.get("title", "")[:55]
    score  = result["final_score"]
    action = result.get("action", "SKIP")
    icons  = {"APPLY": "â APPLY", "SKILL": "ð SKILL", "SKIP": "â­  SKIP", "HARD_SKIP": "ð« NO MATCH"}
    apply  = icons.get(action, "â SKIP")
    bar    = "â" * (score // 5) + "â" * (20 - score // 5)

    print(f"\n  {'â'*60}")
    print(f"  {apply}  [{bar}] {score}%")
    print(f"  ð {title}")
    print(f"  Rule: {result.get('rule_score',0)}/100  |  AI adj: {result.get('ai_adjustment',0):+d}")

    bd = result["rule_result"]["breakdown"]
    print(f"     Skill: {bd['skill_match']['score']}/35  "
          f"Client: {bd['client_quality']['score']}/25  "
          f"Competition: {bd['competition']['score']}/20  "
          f"Quality: {bd['job_quality']['score']}/20")

    if result.get("ai_result"):
        ai = result["ai_result"]
        if ai.get("green_flags"):
            print(f"  â {' | '.join(ai['green_flags'][:2])}")
        if ai.get("red_flags"):
            print(f"  â ï¸  {' | '.join(ai['red_flags'][:2])}")
        print(f"  ð¬ {ai.get('win_prediction','')}")

    print(f"  Reason: {result['reason']}")


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
#  TEST MODE â Ek job manually test karne ke liye
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

if __name__ == "__main__":
    # Example test job
    test_job = {
        "title": "GeoDirectory Expert Needed for Business Directory Website",
        "description": "We need an expert to set up a business directory using GeoDirectory plugin on WordPress. The site should have categories, search filters, and payment for listings. We have budget and are ready to start immediately.",
        "skills": ["GeoDirectory", "WordPress", "PHP"],
        "budget": "$500 fixed",
        "experience_level": "Expert",
        "posted": "8 min ago",
        "client": {
            "payment_verified": True,
            "total_spent": 3500,
            "hire_rate": 0.6,
            "total_hires": 8,
            "country": "US"
        },
        "connects_cost": 6,
    }

    print("\n" + "="*60)
    print("  AI WIN-PROBABILITY SCORER â Test Run")
    print("="*60)

    result = score_job(test_job, use_ai=True)
    print_score_report(test_job, result)

    print(f"\n  FINAL DECISION: {'â APPLY' if result['should_apply'] else 'â SKIP'}")
    print(f"  Win Probability: {result['final_score']}%")
    print("="*60 + "\n")
