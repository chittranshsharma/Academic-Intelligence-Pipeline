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
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )

            for dir_url in directory_urls:
                logger.info(f"Starting discovery for directory: {dir_url}")
                page_links = await self._discover_profiles_recursive(context, dir_url)
                for link in page_links:
                    if link not in discovered_profiles:
                        discovered_profiles.append(link)
                        if len(discovered_profiles) >= self.max_profiles:
                            logger.info(f"Reached maximum profile limit of {self.max_profiles}. Stopping discovery.")
                            break
                if len(discovered_profiles) >= self.max_profiles:
                    break
                    
            await browser.close()
            
        logger.info(f"Discovery complete. Discovered {len(discovered_profiles)} unique profile links.")
        
        if not discovered_profiles:
            logger.warning("No profile links discovered. Exiting.")
            return self.output_json

        # --- PHASE 2: DOWNLOAD PROFILES ---
        logger.info("=========================================")
        logger.info("   PHASE 2: DOWNLOADING PROFILE PAGES    ")
        logger.info("=========================================")
        
        if self.use_playwright_profiles:
            logger.info("Downloading profiles using Playwright engine (slower)...")
            await self._download_profiles_playwright(discovered_profiles, directory_urls[0])
        else:
            logger.info(f"Downloading profiles using HTTPX engine (concurrency={self.concurrency})...")
            await self._download_profiles_httpx(discovered_profiles, directory_urls[0])
            
        # Write discovered data to output JSON
        with open(self.output_json, 'w', encoding='utf-8') as f:
            json.dump(self.raw_data, f, indent=4)
            
        logger.info(f"Crawling complete. Saved {len(self.raw_data)} profiles to {self.output_json}")
        return self.output_json

    async def _discover_profiles_recursive(self, context, start_url):
        discovered = []
        visited_pages = set()
        current_url = start_url
        page_num = 1
        
        page = await context.new_page()
        
        try:
            while current_url and page_num <= self.max_pages:
                if current_url in visited_pages:
                    logger.info("Detected circular loop in pagination. Stopping.")
                    break
                    
                visited_pages.add(current_url)
                logger.info(f"Loading directory page {page_num}: {current_url}")
                
                try:
                    await page.goto(current_url, wait_until="networkidle", timeout=30000)
                except PlaywrightTimeoutError:
                    logger.warning(f"Timeout loading directory page {current_url}. Trying to parse partial DOM...")
                
                # Extract all absolute links on this page
                links = await page.eval_on_selector_all('a[href]', 'elements => elements.map(e => e.href)')
                
                # Filter out general links
                page_profiles = []
                for link in links:
                    if link and is_likely_profile_link(link, start_url):
                        # Remove fragment
                        clean_link = link.split('#')[0]
                        if clean_link not in discovered and clean_link not in page_profiles:
                            page_profiles.append(clean_link)
                            
                logger.info(f"Found {len(page_profiles)} profile links on page {page_num}")
                discovered.extend(page_profiles)
                
                if len(discovered) >= self.max_profiles:
                    break
                    
                # Find Next page URL
                next_url = await self._find_next_page_url(page, start_url)
                if next_url:
                    current_url = next_url
                    page_num += 1
