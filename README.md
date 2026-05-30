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
│  │ HTTPX       │    │ Local LLM (Qwen) │    │  Deduplication     │  │
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
- Uses a **local LLM** (Qwen 3 14B via Ollama) to extract structured fields — name, role, email, department, research interests, origin — directly from raw HTML text
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
