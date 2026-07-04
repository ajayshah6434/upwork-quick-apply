#!/usr/bin/env python3
"""
Google Sheets Updater — Upwork Job Tracker
-------------------------------------------
Har run ke baad ALL scored jobs ko Google Sheet mein append karta hai.
Sheet history preserve hoti hai — overwrite nahi hota.

Setup:
  1. Google Cloud Console → Service Account banao → JSON key download karo
  2. GitHub Secrets mein add karo:
       GOOGLE_SERVICE_ACCOUNT_JSON  ← pura JSON content (single line ya multiline)
       GOOGLE_SHEET_NAME            ← optional, default: "Upwork Job Tracker"
  3. Service Account ko sheet share karo (auto-hota hai pehle run pe)

Returns: Google Sheet URL (email mein include hota hai)
"""

import os, json
from datetime import datetime

SHEET_NAME_DEFAULT = "Upwork Job Tracker"

HEADERS = [
    "Date", "Time (IST)", "Title", "Budget", "Score %", "Action",
    "Reason", "Keyword", "Client Spent ($)", "Country",
    "Payment Verified", "Posted", "Apply Link", "Cover Letter", "Job URL",
]


def save_jobs_to_sheet(proposals: list, skill_jobs: list, skipped: list) -> str | None:
    """
    proposals  = APPLY jobs (have cover_letter)
    skill_jobs = SKILL jobs (need upskilling)
    skipped    = SKIP jobs (below threshold)

    Returns Google Sheet URL on success, None on failure.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("  [Sheets] gspread not installed — skipping (add to requirements.txt)")
        return None

    # ── Credentials from env var (full JSON string) ───────────────────────────
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not creds_json:
        print("  [Sheets] GOOGLE_SERVICE_ACCOUNT_JSON not set — skipping Google Sheets")
        return None

    try:
        creds_dict = json.loads(creds_json)
    except json.JSONDecodeError as e:
        print(f"  [Sheets] Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc     = gspread.authorize(creds)
    except Exception as e:
        print(f"  [Sheets] Auth error: {e}")
        return None

    # ── Open or create sheet ─────────────────────────────────────────────────
    sheet_name = os.environ.get("GOOGLE_SHEET_NAME", SHEET_NAME_DEFAULT)
    try:
        try:
            sh = gc.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            sh = gc.create(sheet_name)
            notify_email = os.environ.get("NOTIFY_EMAIL", "")
            if notify_email:
                sh.share(notify_email, perm_type="user", role="writer")
                print(f"  [Sheets] Created '{sheet_name}' & shared with {notify_email}")
            else:
                print(f"  [Sheets] Created new sheet: '{sheet_name}'")
    except Exception as e:
        print(f"  [Sheets] Cannot open/create '{sheet_name}': {e}")
        return None

    # ── Write rows ───────────────────────────────────────────────────────────
    try:
        ws = sh.get_worksheet(0)

        # Add header if sheet is blank
        existing = ws.get_all_values()
        if not existing or existing[0] != HEADERS:
            ws.clear()
            ws.append_row(HEADERS, value_input_option="USER_ENTERED")

        now    = datetime.now()
        date_s = now.strftime("%Y-%m-%d")
        time_s = now.strftime("%H:%M") + " IST"

        all_tagged = (
            [(j, "✅ APPLY") for j in proposals] +
            [(j, "📚 SKILL") for j in skill_jobs] +
            [(j, "🚫 SKIP")  for j in skipped]
        )

        rows = []
        for job, action_label in all_tagged:
            sr = job.get("score_result", {})
            rows.append([
                date_s,
                time_s,
                job.get("title", ""),
                job.get("budget", ""),
                sr.get("final_score", ""),
                action_label,
                sr.get("reason", ""),
                job.get("matched_keyword", ""),
                job.get("client_spent", ""),
                job.get("client_country", ""),
                "Yes" if job.get("payment_verified") else "No",
                job.get("posted", ""),
                job.get("apply_link", ""),
                job.get("cover_letter", ""),   # blank for SKILL/SKIP
                job.get("url", ""),
            ])

        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"  ✅ Google Sheet updated — {len(rows)} rows added")
            print(f"     {sh.url}")
        else:
            print("  [Sheets] No rows to add this run")

        return sh.url

    except Exception as e:
        print(f"  [Sheets] Error writing rows: {e}")
        return None
