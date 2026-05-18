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
