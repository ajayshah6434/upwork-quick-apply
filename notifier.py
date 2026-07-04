#!/usr/bin/env python3
"""
Upwork Notifier — Email + WhatsApp
------------------------------------
Naye Upwork jobs milne pe turant notify karta hai.

Channels:
  1. Email  — Gmail SMTP (App Password se)
  2. WhatsApp — CallMeBot (free, setup 2 min)

Usage:
  python notifier.py --test          # Sample notification bhejo
  python notifier.py --test --email  # Sirf email test
  python notifier.py --test --whatsapp  # Sirf WhatsApp test
"""

import os, requests, smtplib, argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# ── Config — .env mein set karo ─────────────────────────────────────────────
NOTIFY_EMAIL        = os.environ.get("NOTIFY_EMAIL", "shahajay6434@gmail.com")
NOTIFY_EMAIL_CC     = os.environ.get("NOTIFY_EMAIL_CC", "bharatb754@gmail.com")  # Partner Bharat
GMAIL_USER          = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")   # 16-char App Password

WHATSAPP_PHONE      = os.environ.get("WHATSAPP_PHONE", "")       # with country code, e.g. 919876543210
WHATSAPP_API_KEY    = os.environ.get("WHATSAPP_API_KEY", "")     # CallMeBot se milega
# ─────────────────────────────────────────────────────────────────────────────


def send_email(subject: str, html_body: str, plain_body: str = "") -> bool:
    """Gmail SMTP se email bhejo."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("  [Email] GMAIL_USER / GMAIL_APP_PASSWORD not set in .env — skipping")
        return False

    try:
        recipients = [NOTIFY_EMAIL]
        if NOTIFY_EMAIL_CC:
            recipients.append(NOTIFY_EMAIL_CC)

        msg              = MIMEMultipart("alternative")
        msg["Subject"]   = subject
        msg["From"]      = GMAIL_USER
        msg["To"]        = NOTIFY_EMAIL
        msg["Cc"]        = NOTIFY_EMAIL_CC
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


def send_whatsapp(message: str) -> bool:
    """CallMeBot se WhatsApp message bhejo (free)."""
    if not WHATSAPP_PHONE or not WHATSAPP_API_KEY:
        print("  [WhatsApp] WHATSAPP_PHONE / WHATSAPP_API_KEY not set in .env — skipping")
        return False

    try:
        url  = "https://api.callmebot.com/whatsapp.php"
        params = {
            "phone":  WHATSAPP_PHONE,
            "text":   message,
            "apikey": WHATSAPP_API_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)

        if resp.ok and "Message Sent" in resp.text:
            print(f"  ✅ WhatsApp sent → +{WHATSAPP_PHONE}")
            return True
        else:
            print(f"  ❌ WhatsApp error: {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"  ❌ WhatsApp error: {e}")
        return False


def notify_new_jobs(proposals: list, sheet_url: str = None):
    """
    Naye qualified jobs milne pe dono channels pe notify karo.
    quick_apply.py se call hota hai.

    proposals  — APPLY jobs with cover letters
    sheet_url  — Google Sheet URL (optional, included in email when provided)
    """
    count = len(proposals)
    if count == 0:
        return

    # ── WhatsApp message (short, scannable) ──────────────────────────────────
    wa_lines = [f"⚡ *{count} Upwork Job{'s' if count>1 else ''} Ready — Apply Now!*\n"]
    for i, p in enumerate(proposals, 1):
        score = p.get("score_result", {}).get("final_score", "?")
        wa_lines.append(
            f"*{i}. {p['title'][:55]}*\n"
            f"💰 {p['budget']}  |  🎯 {score}% win\n"
            f"🔗 {p['apply_link']}\n"
            f"📝 _{p['cover_letter'][:120]}_\n"
        )
    wa_lines.append("⏱ 15 min window — jaldi apply karo!")
    if sheet_url:
        wa_lines.append(f"\n📊 All Jobs Sheet: {sheet_url}")
    send_whatsapp("\n".join(wa_lines))

    # ── Email (detailed HTML) ─────────────────────────────────────────────────
    subject = f"⚡ {count} Upwork Job{'s' if count>1 else ''} — Apply Within 15 Min!"

    cards = ""
    for i, p in enumerate(proposals, 1):
        score = p.get("score_result", {}).get("final_score", "?")
        cards += f"""
        <div style="background:#f8f9fa;border-left:4px solid #14a800;border-radius:6px;
                    padding:16px;margin:12px 0;">
          <p style="margin:0 0 6px;font-size:16px;font-weight:600;color:#0d0d0d;">
            {i}. {p['title']}</p>
          <p style="margin:0 0 10px;font-size:13px;color:#555;">
            💰 {p['budget']} &nbsp;|&nbsp; 🎯 {score}% win probability
            &nbsp;|&nbsp; ⏱ {p.get('posted','just now')}</p>
          <div style="background:#fff;border:1px solid #e0e0e0;border-radius:4px;
                      padding:12px;margin-bottom:12px;font-size:14px;color:#333;
                      font-style:italic;">
            "{p['cover_letter']}"
          </div>
          <a href="{p['apply_link']}"
             style="display:inline-block;background:#14a800;color:#fff;
                    padding:10px 20px;border-radius:5px;text-decoration:none;
                    font-size:14px;font-weight:600;">
            Apply Now →
          </a>
        </div>"""

    # Google Sheet button — only shown when sheet_url is available
    sheet_section = ""
    if sheet_url:
        sheet_section = f"""
        <div style="margin:20px 0;padding:16px;background:#e8f4ff;border-radius:6px;
                    border-left:4px solid #1a73e8;text-align:center;">
          <p style="margin:0 0 6px;font-size:14px;color:#333;font-weight:600;">
            📊 Sabhi Scored Jobs — Google Sheet</p>
          <p style="margin:0 0 12px;font-size:12px;color:#666;">
            APPLY + SKILL + SKIP — poora history ek jagah</p>
          <a href="{sheet_url}"
             style="display:inline-block;background:#1a73e8;color:#fff;
                    padding:10px 24px;border-radius:5px;text-decoration:none;
                    font-size:14px;font-weight:600;">
            📊 Open Job Tracker Sheet →
          </a>
        </div>"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#14a800;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">
          ⚡ {count} Naye Upwork Job{'s' if count>1 else ''} — Abhi Apply Karo!</h1>
        <p style="color:#d4f5d4;margin:6px 0 0;font-size:13px;">
          15 minute window mein apply karo — early proposals win rate badhate hain</p>
      </div>
      <div style="background:#fff;padding:20px 24px;border:1px solid #e0e0e0;
                  border-top:none;border-radius:0 0 8px 8px;">
        {cards}
        {sheet_section}
        <p style="font-size:12px;color:#999;margin-top:20px;text-align:center;">
          Upwork Quick Apply System • Bharat A.</p>
      </div>
    </div>"""

    plain = f"{count} naye Upwork jobs mile:\n\n"
    for i, p in enumerate(proposals, 1):
        plain += f"{i}. {p['title']}\n{p['apply_link']}\n{p['cover_letter']}\n\n"
    if sheet_url:
        plain += f"\nSabhi Jobs Google Sheet: {sheet_url}\n"

    send_email(subject, html, plain)


def send_test_notification():
    """Sample notification bhejo dono channels pe."""
    sample_proposals = [{
        "title":        "GeoDirectory Expert Needed for Business Directory",
        "budget":       "$350 fixed",
        "posted":       "3 min ago",
        "apply_link":   "https://www.upwork.com/nx/proposals/job/~01example/apply/",
        "cover_letter": "Hi. I work with GeoDirectory daily & just built a 500-listing business directory. Happy to show you a quick walkthrough.",
        "score_result": {"final_score": 88}
    }, {
        "title":        "HivePress Marketplace Setup on WordPress",
        "budget":       "$25-40/hr",
        "posted":       "7 min ago",
        "apply_link":   "https://www.upwork.com/nx/proposals/job/~02example/apply/",
        "cover_letter": "Hi. I work with HivePress daily & recently launched 3 similar marketplaces. Happy to walk you through my approach — takes 10 mins.",
        "score_result": {"final_score": 82}
    }]

    print("\n📤 Sending test notification...\n")
    notify_new_jobs(sample_proposals, sheet_url="https://docs.google.com/spreadsheets/d/example")
    print("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test",       action="store_true", help="Sample notification bhejo")
    parser.add_argument("--email",      action="store_true", help="Sirf email")
    parser.add_argument("--whatsapp",   action="store_true", help="Sirf WhatsApp")
    args = parser.parse_args()

    if args.test:
        if args.email:
            send_email(
                "⚡ Test — Upwork Quick Apply",
                "<h2>Test email from Upwork Quick Apply!</h2><p>System working ✅</p>",
                "Test email from Upwork Quick Apply — System working!"
            )
        elif args.whatsapp:
            send_whatsapp("⚡ *Test* — Upwork Quick Apply system working! ✅")
        else:
            send_test_notification()
    else:
        print("Usage:")
        print("  python notifier.py --test           # Both channels")
        print("  python notifier.py --test --email   # Email only")
        print("  python notifier.py --test --whatsapp # WhatsApp only")
