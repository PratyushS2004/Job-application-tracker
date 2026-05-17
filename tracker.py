"""
Job Application Tracker
Parses job listings with Gemini and logs them to Google Sheets.
Supports single listings (paste or URL) and batch mode via urls.txt.
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import html
import re
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
SHEET_NAME        = os.getenv("SHEET_NAME", "Job Applications")
CREDENTIALS_FILE  = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GEMINI_MODEL      = "gemini-2.5-flash"
URLS_FILE         = "urls.txt"
DELAY_BETWEEN     = 3  # seconds between requests in batch mode

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = [
    "Date Added",
    "Job Title",
    "Company",
    "Pay Range",
    "Location",
    "Work Type",
    "Employment Type",
    "Key Requirements",
    "Application Status",
    "Notes",
    "Source URL",
]

# ── Gemini extraction ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a precise job listing parser. Extract structured information from raw job listing text.
Always respond with valid JSON only — no markdown fences, no extra commentary.

Return this exact schema:
{
  "job_title": "string or null",
  "company": "string or null",
  "pay_range": "string (e.g. '$80,000 – $110,000/yr' or 'Not listed') or null",
  "location": "string (city, state or 'Remote') or null",
  "work_type": "Remote | Hybrid | In-Person | Not specified",
  "employment_type": "W-2 | Contract | 1099 | Not specified",
  "key_requirements": "concise bullet summary, max 5 points, separated by ' • '",
  "notes": "any other relevant info (visa sponsorship, equity, benefits highlights) or empty string"
}

Be concise. If info isn't in the listing, use null or 'Not listed' as appropriate."""


def extract_job_data(listing_text: str, url: str = "") -> dict:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(GEMINI_MODEL)

    user_content = listing_text
    if url:
        user_content = f"Source URL: {url}\n\n{listing_text}"

    response = model.generate_content(SYSTEM_PROMPT + "\n\nJob listing:\n" + user_content)
    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_sheet():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)

    try:
        sh = gc.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        print(f"  ✗ Sheet '{SHEET_NAME}' not found.")
        print(f"    Create a Google Sheet named '{SHEET_NAME}' and share it")
        print(f"    with the service account email in your credentials.json.")
        sys.exit(1)

    ws = sh.sheet1

    if ws.row_count == 0 or ws.cell(1, 1).value != SHEET_HEADERS[0]:
        ws.clear()
        ws.append_row(SHEET_HEADERS, value_input_option="USER_ENTERED")
        ws.format("A1:K1", {"textFormat": {"bold": True}})

    return ws


def get_existing_urls(ws) -> set:
    """Return set of URLs already logged so we skip duplicates."""
    url_col = ws.col_values(11)  # Source URL is column 11
    return set(u.strip() for u in url_col if u.strip())


def log_to_sheet(ws, data: dict, url: str = ""):
    today = datetime.date.today().strftime("%Y-%m-%d")
    row = [
        today,
        data.get("job_title") or "",
        data.get("company") or "",
        data.get("pay_range") or "Not listed",
        data.get("location") or "",
        data.get("work_type") or "Not specified",
        data.get("employment_type") or "Not specified",
        data.get("key_requirements") or "",
        "Not Applied",
        data.get("notes") or "",
        url,
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")


# ── Scraping ──────────────────────────────────────────────────────────────────

def scrape_url(url: str) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobTracker/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")

        text = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s{3,}", "\n\n", text)
        return text[:12000]
    except Exception as e:
        print(f"  ⚠ Could not scrape: {e}")
        return ""


# ── Modes ─────────────────────────────────────────────────────────────────────

def process_single(ws):
    print("How do you want to add a listing?")
    print("  [1] Paste listing text")
    print("  [2] Enter a URL (auto-scrape)")
    choice = input("\nChoice (1/2): ").strip()

    listing_text = ""
    url = ""

    if choice == "2":
        url = input("URL: ").strip()
        print("\n  Scraping...", end="", flush=True)
        listing_text = scrape_url(url)
        if not listing_text:
            print(" failed. Falling back to manual paste.")
            choice = "1"
        else:
            print(f" got {len(listing_text)} chars.")

    if choice != "2" or not listing_text:
        print("\nPaste the job listing below.")
        print("When done, type END on its own line and press Enter:\n")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        listing_text = "\n".join(lines)

    if not listing_text.strip():
        print("✗ No listing text provided. Exiting.")
        sys.exit(1)

    print("\n  Extracting with Gemini...", end="", flush=True)
    try:
        data = extract_job_data(listing_text, url)
    except json.JSONDecodeError as e:
        print(f" ✗ Invalid JSON from Gemini: {e}")
        sys.exit(1)
    except Exception as e:
        print(f" ✗ Gemini API error: {e}")
        sys.exit(1)
    print(" done.")

    print("\n── Extracted Data ──────────────────")
    print(f"  Title:    {data.get('job_title', '—')}")
    print(f"  Company:  {data.get('company', '—')}")
    print(f"  Pay:      {data.get('pay_range', '—')}")
    print(f"  Location: {data.get('location', '—')} ({data.get('work_type', '—')})")
    print(f"  Type:     {data.get('employment_type', '—')}")
    print(f"  Reqs:     {data.get('key_requirements', '—')}")
    if data.get("notes"):
        print(f"  Notes:    {data.get('notes')}")
    print("────────────────────────────────────")

    confirm = input("\nLog this to Google Sheets? (y/n): ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    log_to_sheet(ws, data, url)
    print(f"\n✓ Logged '{data.get('job_title', 'listing')}' to '{SHEET_NAME}'!")


def process_batch(ws):
    if not os.path.exists(URLS_FILE):
        print(f"✗ '{URLS_FILE}' not found.")
        print(f"  Create a file called urls.txt with one job listing URL per line.")
        sys.exit(1)

    with open(URLS_FILE) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        print(f"✗ No URLs found in '{URLS_FILE}'.")
        sys.exit(1)

    existing = get_existing_urls(ws)
    to_process = [u for u in urls if u not in existing]
    skipped = len(urls) - len(to_process)

    print(f"  Found {len(urls)} URLs — {skipped} already logged, {len(to_process)} to process.\n")

    if not to_process:
        print("✓ Nothing new to log.")
        return

    success, failed = 0, 0

    for i, url in enumerate(to_process, 1):
        print(f"  [{i}/{len(to_process)}] {url[:70]}{'...' if len(url) > 70 else ''}")

        print("    Scraping...", end="", flush=True)
        listing_text = scrape_url(url)
        if not listing_text:
            print(" failed — skipping.")
            failed += 1
            continue
        print(f" {len(listing_text)} chars.")

        print("    Extracting...", end="", flush=True)
        try:
            data = extract_job_data(listing_text, url)
        except Exception as e:
            print(f" failed ({e}) — skipping.")
            failed += 1
            continue
        print(f" done. → {data.get('job_title', '?')} at {data.get('company', '?')}")

        log_to_sheet(ws, data, url)
        success += 1

        if i < len(to_process):
            time.sleep(DELAY_BETWEEN)

    print(f"\n✓ Batch complete — {success} logged, {failed} failed.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n╔══════════════════════════════════╗")
    print("║   Job Application Tracker v2.0   ║")
    print("╚══════════════════════════════════╝\n")

    if not os.getenv("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"✗ Google credentials not found at '{CREDENTIALS_FILE}'.")
        sys.exit(1)

    print("Mode:")
    print("  [1] Add a single listing (paste or URL)")
    print("  [2] Batch mode — process all URLs in urls.txt")
    mode = input("\nChoice (1/2): ").strip()

    print("\n  Connecting to Google Sheets...", end="", flush=True)
    ws = get_sheet()
    print(" done.\n")

    if mode == "2":
        process_batch(ws)
    else:
        process_single(ws)


if __name__ == "__main__":
    main()