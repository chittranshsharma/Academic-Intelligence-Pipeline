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
    "singh", "kaur", "gill", "dhaliwal", "sidhu", "brar", "grewal", "sandhu",
    "dhillon", "bajwa", "randhawa", "anand", "arora", "bhatia", "chopra",
    "kapoor", "khanna", "malhotra", "mehra", "nagpal", "sachdeva", "saluja",
    "sehgal", "sethi", "talwar", "taneja", "vohra", "walia",
    # South Indian
    "nair", "pillai", "menon", "iyer", "iyengar", "krishnan", "krishna",
    "subramanian", "subramaniam", "rajan", "rajagopal", "rajagopalan",
    "venkataraman", "venkatesh", "venkatesan", "narayanan", "narayana",
    "gopalan", "gopinath", "anantharaman", "ramachandran", "chandrasekaran",
    "parthasarathy", "srinivasan", "srinivas", "nagarajan", "suresh",
    "balakrishnan", "balasubramanian", "sundaram", "sundararajan",
    "natarajan", "viswanathan", "swaminathan", "ramasubramanian",
    "murugan", "murugesan", "selvam", "arumugam", "palaniswamy",
    "reddy", "redd", "rao", "naidu", "prasad", "murthy", "murali",
    "madhavan", "mahadevan", "krishnamurthy", "krishnamurthhy",
    "anand", "kumar", "kumari", "nandi", "bandyopadhyay",
    # Bengali / East Indian
    "bose", "roy", "chatterjee", "chattopadhyay", "banerjee", "bandyopadhyay",
    "mukherjee", "mukhopadhyay", "ghosh", "chakraborty", "chakrabarti",
    "sen", "dutta", "datta", "sarkar", "ganguly", "ganguli", "mitra",
    "dasgupta", "guha", "biswas", "sanyal", "majumdar", "majumder",
    "bhattacharya", "bhattacharyya", "saha", "bhadra",
    # Rajasthani / Marwari
    "gupta", "agarwal", "aggarwal", "agrawal", "jain", "goel", "goyal",
    "bansal", "mittal", "singhal", "goyal", "khandelwal", "maheshwari",
    "jhunjhunwala", "birla", "somani",
    # UP / Bihar
    "yadav", "verma", "srivastava", "shrivastava", "tripathi", "tripathy",
    "kesarwani", "kushwaha",
    # Kashmiri / North Indian
    "raina", "koul", "kaul", "dhar", "kak", "matto", "mattoo",
    # Maharashtra / Western India
    "kulkarni", "deshpande", "joshi", "patil", "deshmukh", "bhosle",
