import json
import logging
import os
import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

HARD_INCLUDE_ROLES = [
    'professor', 'lecturer', 'reader', 'fellow', 'chair',
    'assistant professor', 'associate professor', 'senior lecturer'
]
HARD_EXCLUDE_ROLES = [
    'student', 'phd', 'doctoral', 'candidate', 'undergraduate',
    'coordinator', 'administrator', 'emeritus'
]

# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive South Asian Name List
# Covers: India, Pakistan, Bangladesh, Sri Lanka, Nepal, Bhutan, Maldives
# ─────────────────────────────────────────────────────────────────────────────
SOUTH_ASIAN_SURNAMES = {
    # ── INDIAN ──
    # Hindi belt / General Indian
    "sharma", "shukla", "mishra", "misra", "pandey", "tiwari", "dubey", "dwivedi",
    "trivedi", "chaturvedi", "bajpai", "upadhyay", "upadhyaya", "pathak", "joshi",
    "pant", "dikshit", "dixit",
    # Patels / Gujarati
    "patel", "shah", "mehta", "gandhi", "desai", "parikh", "bhatt", "modi",
    "jani", "vyas", "trivedi", "amin", "rana", "raval", "kapadia",
    # Punjabi / Sikh
