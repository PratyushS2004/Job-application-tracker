# Job Application Tracker

A Python CLI tool that parses job listings using the **Gemini AI API**, then automatically logs structured data to a **Google Sheet** — so you can track applications without copy-pasting into spreadsheets by hand.

Built this to automate the tedious part of job hunting instead of manually copying job details into a spreadsheet, paste a listing or drop URLs into a file and it handles the rest. Uses Gemini to parse unstructured job text into clean structured data.

---

## Features

- **AI-powered parsing** — paste any job listing or give it a URL and Gemini extracts title, company, pay, location, work type, employment type, and key requirements
- **Batch mode** — drop a list of URLs into `urls.txt` and process all of them in one command
- **Duplicate detection** — re-running batch mode skips URLs already logged in your sheet
- **Google Sheets logging** — one row per listing, headers auto-created on first run
- **URL scraping** — works best on Greenhouse (`boards.greenhouse.io`) and Lever (`jobs.lever.co`) listings

---

## Sheet Output

| Date Added | Job Title | Company | Pay Range | Location | Work Type | Employment Type | Key Requirements | Application Status |

| 2025-01-15 | Embedded Software Engineer | Anduril | $120k–$160k/yr | Costa Mesa, CA | In-Person | W-2 | C/C++ • RTOS • CAN bus • 2+ yrs exp • BS CE/EE required | Not Applied |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/job-application-tracker.git
cd job-application-tracker
pip install -r requirements.txt
```

### 2. Get your Gemini API key

1. Go to [aistudio.google.com](https://aistudio.google.com) → Get API Key
2. Create a new key and copy it

### 3. Set up Google Cloud (one-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create a project
2. Enable the **Google Sheets API** and **Google Drive API**
3. Go to **IAM & Admin → Service Accounts → Create Service Account** → name it anything → finish
4. Click the service account → **Keys tab → Add Key → Create new key → JSON**
5. Save the downloaded file as `credentials.json` in the project root

### 4. Share your Google Sheet with the service account

1. Create a Google Sheet named exactly `Job Applications`
2. Open `credentials.json` and copy the `client_email` value
3. Share the sheet with that email, give it **Editor** access

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_CREDENTIALS_FILE=credentials.json
SHEET_NAME=Job Applications
```

---

## Usage

```bash
python tracker.py
```

### Mode 1 — Single listing

Choose `[1]` to paste job text manually, or `[2]` to enter a URL and have it scraped automatically. You'll see a preview of the extracted data and confirm before anything is logged.

### Mode 2 — Batch mode

Add job listing URLs to `urls.txt`, one per line:

```
# urls.txt
https://job-boards.greenhouse.io/andurilindustries/jobs/5100716007
https://jobs.lever.co/pyka/7bb26cc6-027c-4930-b1a7-fe3314b6d361
https://job-boards.greenhouse.io/spacex/jobs/8546113002
```

Then run the tracker and pick `[2]`. It processes every URL, skipping ones already in your sheet.

**Finding URLs:** Use Google with site search to find fresh listings:
```
site:boards.greenhouse.io "embedded software engineer"
site:boards.greenhouse.io "FPGA"
site:jobs.lever.co "firmware engineer"
```

Set Google's time filter to **Past 24 hours** to find the newest postings.

---

## Project Structure

```
job-application-tracker/
├── tracker.py          # main script
├── urls.txt            # batch URL list (edit this)
├── requirements.txt
├── .env.example        # copy to .env and fill in your keys
├── .gitignore          # excludes .env and credentials.json
└── README.md
```

---

## Security

- `credentials.json` and `.env` are in `.gitignore` — never committed
- The service account only has access to sheets you explicitly share with it
- API keys are loaded from environment variables, never hardcoded

---

## Tech Stack

| Component | Library / Service |
|---|---|
| AI parsing | Google Gemini API (`gemini-2.5-flash`) |
| Google Sheets | `gspread` + `google-auth` |
| Config | `python-dotenv` |

---

## Author

**Pratyush Shrestha** · Computer Engineering, Ohio State University  
[GitHub](https://github.com/PratyushS2004)