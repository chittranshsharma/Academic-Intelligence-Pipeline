<div align="center">

<h1>🎓 Academic Intelligence Pipeline</h1>

<p>
  <strong>Automated faculty profile discovery, extraction, and classification system<br>powered by Python · Playwright · Groq AI / Local LLMs · FastAPI · Chrome Extension</strong>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-Server-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Chrome_Extension-Manifest_V3-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Chrome Extension"/>
  <img src="https://img.shields.io/badge/LLM-Groq%20%2F%20Ollama-FF6B6B?style=for-the-badge&logo=openai&logoColor=white" alt="LLM"/>
  <img src="https://img.shields.io/badge/Export-CSV%20%7C%20XLSX-217346?style=for-the-badge&logo=microsoft-excel&logoColor=white" alt="Export"/>
</p>

<p>
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square"/>
  <img src="https://img.shields.io/badge/Automation-Production%20Ready-orange?style=flat-square"/>
</p>

</div>

---

## 📌 Overview

The **Academic Intelligence Pipeline** is an end-to-end data engineering system and browser assistant designed to discover, scrape, parse, and classify faculty profiles from global university websites. It eliminates manual data collection bottlenecks and replaces slow research with an AI-augmented pipeline and real-time browser companion.

At its core, the system combines **Playwright browser automation**, **high-concurrency HTTPX fetching**, **Groq AI inference** (`llama-3.3-70b-versatile`) or local LLMs (via Ollama), **name-based heuristic filtering**, a **FastAPI backend**, and a **Manifest V3 Chrome Extension** with dynamic API key uploading.

> **Use Case:** Automatically build a structured dataset of South Asian-origin faculty members at global research institutions — complete with names, roles, departments, emails, research interests, and source URLs — via CLI batch jobs or directly while browsing faculty directories in your browser.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ACADEMIC INTELLIGENCE PIPELINE                           │
│                                                                             │
│   ┌─────────────────────┐                 ┌─────────────────────────────┐   │
│   │ 🚀 CLI Orchestrator │                 │ 🧩 Chrome Extension (MV3)   │   │
│   │ (main.py batch job) │                 │ Real-time & SSE Streaming   │   │
│   └──────────┬──────────┘                 └──────────────┬──────────────┘   │
│              │                                           │                  │
│              └───────────────────┬───────────────────────┘                  │
│                                  ▼                                          │
│                      ┌───────────────────────┐                              │
│                      │  ⚡ Local FastAPI     │                              │
│                      │  Server (server.py)   │                              │
│                      └───────────┬───────────┘                              │
│                                  │                                          │
│    ┌─────────────────────────────┼─────────────────────────────┐            │
│    ▼                             ▼                             ▼            │
│  ┌─────────────┐       ┌──────────────────┐       ┌────────────────────┐    │
│  │  PHASE 1    │       │    PHASE 2       │       │    PHASE 3         │    │
│  │  CRAWLING   │──────▶│  PARSING & LLM   │──────▶│  EXPORT & REPORT  │    │
│  │             │       │  CLASSIFICATION  │       │                    │    │
│  │ Playwright  │       │ BeautifulSoup +  │       │  CSV / XLSX        │    │
│  │ HTTPX       │       │ Groq API / LLM   │       │  Deduplication     │    │
│  │ Smart URL   │       │ Name Heuristics  │       │  Styled Reports    │    │
│  │ Heuristics  │       │ Role Validation  │       │                    │    │
│  └─────────────┘       └──────────────────┘       └────────────────────┘    │
│                                                                             │
│              Structured Logging · Async I/O · Error Recovery                │
└─────────────────────────────────────────────────────────────────────────────┘
```

The pipeline operates via two complementary entry points:
1. **Batch CLI (`main.py`)**: Runs high-throughput multi-institution scraping tasks.
2. **Browser Sidekick (`server.py` + `extension/`)**: Real-time single profile classification and live directory streaming right inside Google Chrome.

---

## ✨ Key Features

### 🧩 Chrome Extension & Real-Time Assistant
- **Manifest V3 Popup UI**: Dark-mode glassmorphism interface displaying connection status, dataset counts, and current tab preview.
- **⚡ Single Page Classifier**: Instantly classify the current profile tab with one click.
- **📋 Directory Scraper (SSE Stream)**: Auto-paginate and stream batch classification results live without keeping the popup open.
- **🔑 Dynamic Groq API Key Uploader**: Paste/update your Groq API key directly from the browser popup without restarting the Python server.

### 🤖 AI-Augmented Profile Extraction (Groq & Local LLMs)
- Powered by **Groq API** (`llama-3.3-70b-versatile`) or local Ollama models (`qwen3:14b`, `llama3`).
- Zero-hallucination prompt architecture enforcing structured JSON output for name, position, department, university, email, research interests, and origin.
- Multi-strategy parsing fallbacks handle invalid JSON or truncated responses gracefully.

### 🕸️ Dual-Engine Web Crawler
- **Playwright Engine**: Handles JavaScript-rendered directory pages with automated `rel="next"` and heuristic pagination.
- **HTTPX Engine**: High-concurrency async fetching for profile pages using connection pooling.
- Smart URL heuristics filter out generic site pages (about, search, policies) to target valid faculty profile links.

### 🧬 Name-Based Heuristic Pre-Filter
- A curated surname and first-name database covering **India (all regions), Pakistan, Bangladesh, Sri Lanka, and Nepal** (400+ entries).
- Fast pre-filtering skips non-matching profiles before LLM inference to optimize API calls and speed.

### 📊 Professional Report Export
- Exports to clean **CSV** and styled **XLSX** spreadsheets (`output/faculty_data.xlsx`).
- Features dark navy headers, alternating row striping, auto-calibrated column widths, wrapped text, and URL-based deduplication.

---

## 📂 Project Structure

```
academic-intelligence-pipeline/
│
├── main.py              # 🚀 CLI Orchestrator — runs batch crawling & parsing
├── server.py            # ⚡ FastAPI Local Server — bridges Chrome extension & Groq API
├── crawler.py           # 🕸️  Phase 1: Playwright directory pagination + HTTPX downloads
├── parser.py            # 🧠  Phase 2: HTML cleaning + LLM extraction + name heuristics
├── exporter.py          # 📊  Phase 3: Deduplication + CSV/XLSX export
│
├── extension/           # 🧩 Chrome Extension (Manifest V3)
│   ├── manifest.json    # Extension manifest definition
│   ├── popup.html       # Popup user interface & API key card
│   ├── popup.js         # Popup logic, server bridge & single classification
│   ├── background.js    # Service worker for background SSE directory scraping
│   └── icons/           # Extension icons (16, 48, 128px)
│
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (GROQ_API_KEY)
│
├── raw_html/            # Intermediate raw HTML downloads (auto-created)
├── logs/                # Pipeline logs (auto-created)
├── screenshots/         # Debug screenshots on parse error (auto-created)
├── output/              # Final datasets: faculty_data.csv, faculty_data.xlsx
│
├── raw_data.json        # Intermediate crawl output
└── cleaned_data.json    # Intermediate LLM-parsed records
```

---

## ⚙️ Installation & Setup

### Prerequisites

| Requirement | Version / Link |
|-------------|----------------|
| Python | 3.11+ |
| Groq API Key | Free key from [console.groq.com/keys](https://console.groq.com/keys) |
| Browser | Google Chrome / Chromium |

### 1. Clone the repository

```bash
git clone https://github.com/chittranshsharma/Academic-Intelligence-Pipeline.git
cd Academic-Intelligence-Pipeline
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies & Playwright browser

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure Groq API Key

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

*(Alternatively, you can paste your Groq API key directly inside the Chrome Extension popup).*

---

## 🧩 Installing the Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked**.
4. Select the `extension/` folder inside this repository.
5. Pin **Faculty Intelligence** 🎓 to your Chrome toolbar.

---

## 🚀 Usage

### 1. Running via Chrome Extension (Recommended for Interactive Use)

Start the local server:

```bash
python server.py
```
*Server starts on `http://127.0.0.1:8765`.*

**Using the Extension:**
- **Upload API Key**: Click the 🔑 **Groq API Key** card in the extension popup to paste or update your key anytime.
- **Classify Current Tab**: Navigate to any faculty member's profile page and click **⚡ Classify This Page**.
- **Scrape Directory**: Navigate to a directory listing page, switch to **📋 Scrape Directory**, configure Max Pages/Profiles, and click **Scrape This Directory**. Progress will stream live.
- **Export**: Click **📊 Export** to generate `output/faculty_data.xlsx` and `output/faculty_data.csv`.

---

### 2. Running via Command Line (Batch Processing)

Scrape a single university faculty directory:

```bash
python main.py --urls "https://www.example-university.ac.uk/staff"
```

Scrape multiple institutions listed in a text file:

```bash
# urls.txt — one directory URL per line
python main.py --file urls.txt
```

Full CLI configuration:

```bash
python main.py \
  --file urls.txt \
  --max-pages 50 \
  --max-profiles 500 \
  --concurrency 15 \
  --model llama-3.3-70b-versatile
```

#### CLI Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--urls` | — | Space-separated list of directory URLs to scrape |
| `--file` | — | Path to `.txt` file containing one URL per line |
| `--max-pages` | `100` | Maximum directory pages to paginate per URL |
| `--max-profiles` | `1000` | Hard cap on profiles to crawl |
| `--concurrency` | `10` | Concurrent HTTPX download workers |
| `--use-playwright-profiles` | `False` | Use Playwright for profile downloads (slower, JS-heavy) |
| `--model` | `llama-3.3-70b-versatile` | Groq model ID or local model name |
| `--groq-api-key` | — | Overrides `GROQ_API_KEY` environment variable |

---

## 📤 Output Dataset Format

Extracted records are deduplicated by `profile_link` and saved to `output/`:

### `faculty_data.xlsx` / `faculty_data.csv`

| S No | Region | University Name | Department | Faculty Name | Origin | Position | Email | Phone | Profile Link | Research | Notes |
|------|--------|-----------------|------------|--------------|--------|----------|-------|-------|--------------|----------|-------|
| 1 | UK | University of Cambridge | Dept. of Computer Science | Dr. Priya Nair | India | Associate Professor | p.nair@cam.ac.uk | +44 … | https://… | NLP, ML | Expert in multi-lingual … |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Server Framework | FastAPI + Uvicorn |
| Browser Extension | Chrome Extension API (Manifest V3, SSE) |
| Browser Automation | Playwright (async, headless Chromium) |
| HTTP Client | HTTPX (async, connection pooling) |
| HTML Parsing | BeautifulSoup4 |
| LLM Backend | Groq API (`llama-3.3-70b-versatile`) / Local Ollama |
| Data Engineering | Pandas, openpyxl |
| Async Runtime | Python `asyncio` |

---

## 🔒 Privacy & Ethics

- Intended for **academic research and dataset generation only**.
- Operates exclusively on **publicly available** institutional faculty web pages.
- Respects rate limits with soft delays (`asyncio.sleep`) between HTTP requests.

---

## 📄 License

Licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

<div align="center">

**Built with Python · FastAPI · Playwright · Groq AI · Chrome Extension**

</div>
