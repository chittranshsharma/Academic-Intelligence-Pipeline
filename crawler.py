import asyncio
import json
import logging
import os
import re
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

def is_likely_profile_link(url, base_url):
    """
    Smart heuristic to determine if a URL is likely an individual faculty profile
    rather than a general site link (about, courses, help, terms, etc.)
    """
    parsed = urlparse(url)
    parsed_base = urlparse(base_url)
    if parsed.netloc and parsed.netloc != parsed_base.netloc:
        return False
        
    path = parsed.path.lower()
    parts = [p for p in path.split('/') if p]
    if not parts:
        return False
        
    # Generic rule: must have a directory keyword, AND an identifier AFTER the keyword
    for kw in ['people', 'profile', 'staff', 'faculty', 'expert', 'member']:
        if kw in parts:
            idx = parts.index(kw)
            # The path must continue after the keyword (e.g. /staff/john-doe)
            if idx < len(parts) - 1:
                after_kw = parts[idx+1]
                # Filter out obvious non-profile directory paths
                if after_kw not in ['index.html', 'index.php', 'search', 'all']:
                    return True
    return False

class FacultyCrawler:
    def __init__(self, raw_html_dir="raw_html", output_json="raw_data.json", 
                 max_pages=100, max_profiles=1000, concurrency=10, 
                 use_playwright_profiles=False):
        self.raw_html_dir = raw_html_dir
        self.output_json = output_json
        self.max_pages = max_pages
        self.max_profiles = max_profiles
        self.concurrency = concurrency
        self.use_playwright_profiles = use_playwright_profiles
        
        os.makedirs(self.raw_html_dir, exist_ok=True)
        self.raw_data = []

    async def crawl_directories(self, directory_urls):
        discovered_profiles = []
        
        # --- PHASE 1: DISCOVER PROFILE URLS ---
        logger.info("=========================================")
        logger.info("   PHASE 1: DISCOVERING PROFILE URLS     ")
        logger.info("=========================================")
