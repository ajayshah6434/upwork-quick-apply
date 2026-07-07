#!/usr/bin/env python3
"""
Upwork Notifier — Email
------------------------
Naye Upwork jobs milne pe turant email notify karta hai.

Usage:
  python notifier.py --test          # Sample notification bhejo
  python notifier.py --test --email  # Email test
"""

import os, smtplib, argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

NOTIFY_EMAIL        = os.environ.get("NOTIFY_EMAIL", "shahajay6434@gmail.com")
NOTIFY_EMAIL_CC     = os.environ.get("NOTIFY_EMAIL_CC", "bharatb754@gmail.com")
GMAIL_USER          = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")


def send_email(subject: str, html_body: str, plain_body: str = "") -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("  [Email] GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping")
        return False
    try:
        recipients = [NOTIFY_EMAIL]
        if NOTIFY_EMAIL_CC:
            recipients.append(NOTIFY_EMAIL_CC)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = NOTIFY_EMAIL
        msg["Cc"]      = NOTIFY_EMAIL_CC
        msg.attach(MIMEText(plain_body or html_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, recipients, msg.as_string())
        print(f"  ✅ Email sent → {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"  ❌ Email error: {e}")
        return False


def _make_cards_apply(proposals):
    cards = ""
    for i, p in enumerate(proposals, 1):
        score = p.get("score_result", {}).get("final_score", "?")
        cards += (
            f'<div style="background:#f8f9fa;border-left:4px solid #14a800;border-radius:6px;padding:16px;margin:12px 0;">'
            f'<p style="margin:0 0 6px;font-size:16px;font-weight:600;color:#0d0d0d;">{i}. {p["title"]}</p>'
            f'<p style="margin:0 0 10px;font-size:13px;color:#555;">'
            f'\U0001f4b0 {p["budget"]} &nbsp;|&nbsp; \U0001f3af {score}% win probability'
            f'&nbsp;|&nbsp; ⏱ {p.get("posted","just now")}</p>'
            f'<div style="background:#fff;border:1px solid #e0e0e0;border-radius:4px;'
            f'padding:12px;margin-bottom:12px;font-size:14px;color:#333;font-style:italic;">'
            f'"{p["cover_letter"]}"</div>'
            f'<a href="{p["apply_link"]}" style="display:inline-block;background:#14a800;color:#fff;'
            f'padding:10px 20px;border-radius:5px;text-decoration:none;font-size:14px;font-weight:600;">'
            f'Apply Now →</a></div>'
        )
    return cards


def _make_sheet_section(sheet_url):
    if not sheet_url:
        return ""
    return (
        f'<div style="margin:20px 0;padding:16px;background:#e8f4ff;border-radius:6px;'
        f'border-left:4px solid #1a73e8;text-align:center;">'
        f'<p style="margin:0 0 6px;font-size:14px;color:#333;font-weight:600;">'
        f'\U0001f4ca Sabhi Scored Jobs — Google Sheet</p>'
        f'<p style="margin:0 0 12px;font-size:12px;color:#666;">APPLY + SKILL + SKIP — poora history ek jagah</p>'
        f'<a href="{sheet_url}" style="display:inline-block;background:#1a73e8;color:#fff;'
        f'padding:10px 24px;border-radius:5px;text-decoration:none;font-size:14px;font-weight:600;">'
        f'\U0001f4ca Open Job Tracker Sheet →</a></div>'
    )


def notify_new_jobs(proposals: list, sheet_url: str = None):
    """Naye qualified jobs milne pe email notify karo."""
    count = len(proposals)
    if count == 0:
        return

    subject = f"⚡ {count} Upwork Job{'s' if count>1 else ''} — Apply Within 15 Min!"
    cards = _make_cards_apply(proposals)
    sheet_section = _make_sheet_section(sheet_url)

    html = (
        '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">'
        '<div style="background:#14a800;padding:20px 24px;border-radius:8px 8px 0 0;">'
        f'<h1 style="color:#fff;margin:0;font-size:20px;">⚡ {count} Naye Upwork Job{"s" if count>1 else ""} — Abhi Apply Karo!</h1>'
        '<p style="color:#d4f5d4;margin:6px 0 0;font-size:13px;">15 minute window mein apply karo — early proposals win rate badhate hain</p>'
        '</div>'
        '<div style="background:#fff;padding:20px 24px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">'
        f'{cards}{sheet_section}'
        '<p style="font-size:12px;color:#999;margin-top:20px;text-align:center;">Upwork Quick Apply System • Bharat A.</p>'
        '</div></div>'
    )

    plain = f"{count} naye Upwork jobs mile:\n\n"
    for i, p in enumerate(proposals, 1):
        plain += f"{i}. {p['title']}\n{p['apply_link']}\n{p['cover_letter']}\n\n"
    if sheet_url:
        plain += f"\nSabhi Jobs Google Sheet: {sheet_url}\n"

    send_email(subject, html, plain)


def notify_skill_jobs(skill_jobs: list, sheet_url: str = None):
    """35-65% score wale SKILL jobs ka email bhejo (no cover letter, just links)."""
    count = len(skill_jobs)
    if count == 0:
        return

    subject = f"\U0001f4da {count} Upwork Job{'s' if count>1 else ''} — Skill Gap (35–65% Score)"

    cards = ""
    for i, p in enumerate(skill_jobs, 1):
        score    = p.get("score_result", {}).get("final_score", "?")
        reason   = p.get("score_result", {}).get("reason", "")
        job_link = p.get("apply_link", p.get("url", "#"))
        cards += (
            f'<div style="background:#fffbea;border-left:4px solid #f4a400;border-radius:6px;padding:16px;margin:12px 0;">'
            f'<p style="margin:0 0 6px;font-size:16px;font-weight:600;color:#0d0d0d;">{i}. {p["title"]}</p>'
            f'<p style="margin:0 0 8px;font-size:13px;color:#555;">'
            f'\U0001f4b0 {p["budget"]} &nbsp;|&nbsp; \U0001f3af {score}% score'
            f'&nbsp;|&nbsp; ⏱ {p.get("posted","just now")}</p>'
            f'<p style="margin:0 0 12px;font-size:13px;color:#777;font-style:italic;">⚠️ {reason}</p>'
            f'<a href="{job_link}" '
            f'style="display:inline-block;background:#f4a400;color:#fff;'
            f'padding:8px 18px;border-radius:5px;text-decoration:none;font-size:13px;font-weight:600;">'
            f'View Job →</a></div>'
        )

    sheet_section = _make_sheet_section(sheet_url)

    html = (
        '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">'
        '<div style="background:#f4a400;padding:20px 24px;border-radius:8px 8px 0 0;">'
        f'<h1 style="color:#fff;margin:0;font-size:20px;">\U0001f4da {count} Job{"s" if count>1 else ""} — Skill Gap (35–65%)</h1>'
        '<p style="color:#fff3cc;margin:6px 0 0;font-size:13px;">In jobs pe apply nahi kiya — score thoda kam tha. Dekho aur decide karo.</p>'
        '</div>'
        '<div style="background:#fff;padding:20px 24px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">'
        f'{cards}{sheet_section}'
        '<p style="font-size:12px;color:#999;margin-top:20px;text-align:center;">Upwork Quick Apply System • Bharat A.</p>'
        '</div></div>'
    )

    plain = f"\U0001f4da {count} SKILL jobs (35-65% score) — manually review karo:\n\n"
    for i, p in enumerate(skill_jobs, 1):
        score  = p.get("score_result", {}).get("final_score", "?")
        reason = p.get("score_result", {}).get("reason", "")
        plain += (
            f"{i}. {p['title']}\n"
            f"   Score: {score}% | Budget: {p['budget']}\n"
            f"   Reason: {reason}\n"
            f"   Link: {p.get('apply_link', p.get('url', ''))}\n\n"
        )
    if sheet_url:
        plain += f"\nSabhi Jobs Google Sheet: {sheet_url}\n"

    send_email(subject, html, plain)


def send_test_notification():
    """Sample notification bhejo email pe."""
    sample_proposals = [{
        "title":        "GeoDirectory Expert Needed for Business Directory",
        "budget":       "$350 fixed",
        "posted":       "3 min ago",
        "apply_link":   "https://www.upwork.com/nx/proposals/job/~01example/apply/",
        "cover_letter": "Hi. I work with GeoDirectory daily & just built a 500-listing business directory.",
        "score_result": {"final_score": 88}
    }, {
        "title":        "HivePress Marketplace Setup on WordPress",
        "budget":       "$25-40/hr",
        "posted":       "7 min ago",
        "apply_link":   "https://www.upwork.com/nx/proposals/job/~02example/apply/",
        "cover_letter": "Hi. I work with HivePress daily & recently launched 3 similar marketplaces.",
        "score_result": {"final_score": 82}
    }]

    print("\n📤 Sending test notification...\n")
    notify_new_jobs(sample_proposals, sheet_url="https://docs.google.com/spreadsheets/d/example")
    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test",  action="store_true", help="Sample notification bhejo")
    parser.add_argument("--email", action="store_true", help="Email test")
    args = parser.parse_args()

    if args.test:
        send_test_notification()
    else:
        print("Usage:")
        print("  python notifier.py --test          # Test email")
        print("  python notifier.py --test --email  # Email only")
