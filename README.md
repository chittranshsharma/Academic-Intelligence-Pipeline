<div align="center">

<h1>🎓 Academic Intelligence Pipeline</h1>

<p>
  <strong>Automated faculty profile discovery, extraction, and classification system<br>powered by Python · Playwright · Local LLMs · Data Automation</strong>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Playwright-Async-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright"/>
  <img src="https://img.shields.io/badge/LLM-Ollama%20%2F%20OpenAI-FF6B6B?style=for-the-badge&logo=openai&logoColor=white" alt="LLM"/>
  <img src="https://img.shields.io/badge/Pandas-Data%20Pipeline-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas"/>
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

The **Academic Intelligence Pipeline** is a fully automated, end-to-end data engineering system that discovers, scrapes, parses, and classifies faculty profiles from university websites across global institutions. It was architected to eliminate manual data collection bottlenecks and replace slow, error-prone human research with a deterministic, AI-augmented pipeline.

At its core, the system combines **Playwright-driven browser automation** for JavaScript-rendered discovery pages, **high-concurrency HTTPX** for bulk profile downloads, **local LLM inference** (via Ollama) for structured field extraction, and **name-based heuristic filtering** to classify academic profiles by ethnicity/origin — all wired together in a three-phase asynchronous pipeline with structured logging and error recovery.

> **Use Case:** Automatically build a structured dataset of South Asian-origin faculty members at global research institutions — complete with names, roles, departments, emails, research interests, and source URLs — with zero manual intervention after initial configuration.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ACADEMIC INTELLIGENCE PIPELINE                    │
│                                                                     │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────────┐  │
│  │  PHASE 1    │    │    PHASE 2        │    │    PHASE 3         │  │
│  │  CRAWLING   │───▶│  PARSING & LLM   │───▶│  EXPORT & REPORT  │  │
│  │             │    │  CLASSIFICATION  │    │                    │  │
│  │ Playwright  │    │ BeautifulSoup +  │    │  CSV / XLSX        │  │
│  │ HTTPX       │    │ Local LLM (Any)  │    │  Deduplication     │  │
│  │ Smart URL   │    │ Name Heuristics  │    │  Styled Reports    │  │
│  │ Heuristics  │    │ Role Validation  │    │                    │  │
│  └─────────────┘    └──────────────────┘    └────────────────────┘  │
│                                                                     │
│              Structured Logging · Async I/O · Error Recovery        │
└─────────────────────────────────────────────────────────────────────┘
```

The pipeline is broken into three clearly separated, independently testable phases orchestrated by `main.py`:

| Phase | Module | Responsibility |
|-------|--------|---------------|
| **1 — Crawl** | `crawler.py` | Discover profile URLs from faculty directory pages via Playwright; download raw HTML via HTTPX or Playwright |
| **2 — Parse** | `parser.py` | Clean HTML → run local LLM extraction → apply name + role filters → enrich with personal website content |
| **3 — Export** | `exporter.py` | Deduplicate, normalize, and export structured data to styled `.csv` and `.xlsx` |

---

## ✨ Key Features

### 🤖 AI-Augmented Profile Extraction
- Uses any **local LLM** (e.g. Qwen, Llama via Ollama or custom local models) to extract structured fields — name, role, email, department, research interests, origin — directly from raw HTML text
- Enforces a strict zero-hallucination prompt: the model is instructed to return only explicitly stated information
- **JSON-mode output** with robust multi-strategy parsing fallback for malformed LLM responses

### 🕸️ Dual-Engine Web Crawler
- **Playwright engine**: Headless Chromium for JavaScript-rendered directory pages; handles pagination automatically with `rel="next"`, text-based, and class-based link detection
- **HTTPX engine**: Async, high-concurrency (configurable; default 10) bulk profile downloader using connection pooling — dramatically faster than browser-based alternatives
- Smart URL heuristics filter out generic links (about, search, policies) and isolate only valid individual profile URLs

### 🧬 Name-Based Heuristic Pre-Filter
- A curated, comprehensive surname/first-name dataset spanning **India (all regions), Pakistan, Bangladesh, Sri Lanka, and Nepal** — 400+ entries
- Applied as a fast pre-filter before any LLM call, cutting compute cost by skipping clearly non-matching profiles
- Post-LLM double-check validates the extracted name against the same dataset

### 📊 Automated Data Processing & Deduplication
- Profile-URL-based deduplication ensures no duplicate records in the output
- Field normalization: invalid emails (no `@`) and invalid phone numbers are automatically cleared
- Confidence scoring on each record (`Name Matched + LLM Verified`)

### 📁 Professional Report Export
- Exports to both **CSV** and **styled XLSX**
- XLSX features: dark navy header, alternating row colors, frozen header row, calibrated column widths, wrapped text, border styling — production-ready for stakeholder delivery

### 📋 Structured Logging & Error Recovery
- Full file + console logging with timestamps and module identifiers
- On LLM or parsing failure: automatic Playwright screenshot capture for forensic debugging
- Graceful error handling at every stage — the pipeline never crashes silently

---

## 📂 Project Structure

```
academic-intelligence-pipeline/
│
├── main.py              # 🚀 Orchestrator — runs all 3 pipeline phases
├── crawler.py           # 🕸️  Phase 1: URL discovery + HTML download (Playwright + HTTPX)
├── parser.py            # 🧠  Phase 2: HTML cleaning + LLM extraction + filtering
├── exporter.py          # 📊  Phase 3: Deduplication + CSV/XLSX export
│
├── requirements.txt     # Python dependencies
│
├── raw_html/            # Intermediate: raw downloaded HTML files (auto-created)
├── logs/                # Structured pipeline logs (auto-created)
├── screenshots/         # Debug screenshots on parse errors (auto-created)
├── output/              # Final output: faculty_data.csv, faculty_data.xlsx
│
├── raw_data.json        # Intermediate: crawl output (URL + HTML path index)
└── cleaned_data.json    # Intermediate: LLM-parsed, filtered profile records
```

---

## ⚙️ Installation

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| [Ollama](https://ollama.ai) | Latest |
| Qwen3:14b model | via Ollama |
| Chromium (for Playwright) | Auto-installed |

### 1. Clone the repository

```bash
git clone https://github.com/your-username/academic-intelligence-pipeline.git
cd academic-intelligence-pipeline
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Start Ollama and pull the LLM model

```bash
# Install Ollama from https://ollama.ai, then:
ollama pull qwen3:14b
ollama serve
```

> **Note:** The LLM runs entirely **locally** — no data leaves your machine and no API keys are required.

---

## 🚀 Usage

### Basic — scrape a single faculty directory

```bash
python main.py --urls "https://www.example-university.ac.uk/staff"
```

### Bulk — scrape multiple institutions from a file

```bash
# urls.txt — one URL per line
python main.py --file urls.txt
```

### Full configuration

```bash
python main.py \
  --file urls.txt \
  --max-pages 50 \
  --max-profiles 500 \
  --concurrency 15 \
  --use-playwright-profiles
```

### CLI Reference

| Argument | Default | Description |
|----------|---------|-------------|
| `--urls` | — | Space-separated list of directory URLs to scrape |
| `--file` | — | Path to a `.txt` file with one URL per line |
| `--max-pages` | `100` | Maximum directory pages to paginate through per URL |
| `--max-profiles` | `1000` | Hard cap on profiles to discover |
| `--concurrency` | `10` | Parallel HTTPX download workers |
| `--use-playwright-profiles` | `False` | Use Playwright (slower, more robust) for profile downloads |

---

## 📤 Output

After a successful pipeline run, results are saved to the `output/` directory:

### `faculty_data.csv`
Raw tabular export for downstream processing or database ingestion.

### `faculty_data.xlsx`
Professionally styled spreadsheet — ready for immediate stakeholder delivery.

| S No | Region | University Name | Department | Faculty Name | Origin | Position | Email | Phone | Profile Link | Research | Notes |
|------|--------|-----------------|------------|--------------|--------|----------|-------|-------|--------------|----------|-------|
| 1 | UK | University of Cambridge | Dept. of Computer Science | Dr. Priya Nair | India | Associate Professor | p.nair@cam.ac.uk | +44 … | https://… | NLP, ML | Expert in multi-lingual … |
| … | … | … | … | … | … | … | … | … | … | … | … |

---

## 🔬 Technical Deep Dive

### Crawler — Smart URL Heuristics

The crawler uses a path-structure heuristic to distinguish individual faculty profile URLs from generic site links:

```python
# Only accepts URLs where a known directory keyword is followed by a unique identifier
# e.g. /staff/john-doe ✅   /staff/search ❌   /about ❌
for kw in ['people', 'profile', 'staff', 'faculty', 'expert', 'member']:
    if kw in parts and idx < len(parts) - 1:
        if after_kw not in ['index.html', 'search', 'all']:
            return True  # Likely a profile
```

### Parser — LLM Prompt Engineering

The LLM is given a strict, zero-hallucination system prompt and a structured user prompt specifying exact output keys with explicit rules — no markdown, no explanation, raw JSON only:

```
- "name": Faculty member's full name WITHOUT any titles (no Prof., Dr., etc.)
- "email": Must contain @. Empty string if not found.
- "research_interests": Max 10–15 words. No paragraphs.
- "origin": South Asian country only. If unclear, write "South Asian".
```

### Parser — Personal Website Enrichment

For richer research interest and summary fields, the system:
1. Detects external personal/lab website links on the profile page
2. Fetches and cleans their content (up to 8,000 chars)
3. Appends it to the LLM context before extraction

### Exporter — Deduplication Strategy

Deduplication is performed on the `profile_link` (URL) column — the most reliable unique identifier — before any export:

```python
df = df.drop_duplicates(subset=["profile_link"], keep="first")
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Browser Automation | Playwright (async, headless Chromium) |
| HTTP Client | HTTPX (async, connection pooling) |
| HTML Parsing | BeautifulSoup4 |
| LLM Backend | Ollama (local) — Qwen3:14b |
| LLM Client | OpenAI-compatible Python SDK |
| Data Processing | Pandas |
| Report Export | openpyxl (styled XLSX) |
| Logging | Python `logging` (file + console) |
| Async Runtime | asyncio |

---

## 📈 Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| Directory pages crawled/min | ~30–60 (network-dependent) |
| Profile downloads (HTTPX, 10 workers) | ~80–120 profiles/min |
| LLM extraction time per profile | ~2–5s (Qwen3:14b on CPU/GPU) |
| Deduplication overhead | Negligible (<1s for 10k records) |
| End-to-end for 500 profiles | ~15–30 minutes |

---

## 🧪 Running Individual Modules

Each module can be run standalone for development and debugging:

```bash
# Re-run parsing only (uses existing raw_data.json)
python parser.py

# Re-run export only (uses existing cleaned_data.json)
python exporter.py
```

---

## 📝 Logging

All pipeline activity is logged to both the console and `logs/scraper.log`:

```
2026-06-20 14:32:01,042 - main       - INFO - === Starting Faculty Extraction Pipeline ===
2026-06-20 14:32:01,043 - main       - INFO - --- PHASE 1: CRAWLING ---
2026-06-20 14:32:03,211 - crawler    - INFO - Found 48 profile links on page 1
2026-06-20 14:32:45,819 - parser     - INFO - [12/48] LLM extracting: https://...
2026-06-20 14:32:48,002 - parser     - INFO - INCLUDED: Priya Nair | Associate Professor | Univ. of Cambridge | Origin: India
2026-06-20 14:33:10,441 - exporter   - INFO - Removed 3 duplicate entries.
2026-06-20 14:33:10,502 - exporter   - INFO - Exported CSV  -> output/faculty_data.csv
```

On parsing failures, a screenshot of the problematic HTML is automatically saved to `screenshots/` for forensic debugging.

---

## 🔒 Privacy & Ethics

- This pipeline is intended for **research and academic intelligence purposes only**
- All data collected is **publicly available** on institutional websites
- No authentication is bypassed; no private data is accessed
- The system respects standard HTTP conventions and includes soft rate-limiting (`asyncio.sleep`) between requests
- Ensure compliance with the **Terms of Service** of each institution's website before large-scale scraping

---

## 🤝 Contributing

Contributions are welcome. To add support for a new institution's URL pattern or extend the name classification dataset:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/add-institution-support`
3. Make your changes and add tests where applicable
4. Submit a Pull Request with a clear description

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with Python · Playwright · Local LLMs · Data Automation**

*Architected for zero manual intervention. Designed for scale.*

</div>
