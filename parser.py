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
    "shinde", "pawar", "chavan", "jadhav", "thakur",
    # Assamese / North East
    "borah", "baruah", "deka", "kalita", "saikia", "gogoi",
    # Odiya
    "panda", "mohapatra", "mohanty", "das", "mishra", "jena", "nayak",
    # Common suffixes / standalone surnames
    "kumar", "devi", "lal", "ram", "das",

    # ── PAKISTANI ──
    "khan", "ahmed", "ahmad", "siddiqui", "siddique", "qureshi", "malik",
    "chaudhry", "chaudhary", "choudhury", "choudhary", "akhtar", "akhter",
    "hussain", "husain", "mirza", "sheikh", "shaikh", "baig", "hashmi",
    "hashimi", "abbasi", "bukhari", "naqvi", "rizvi", "zaidi", "jafri",
    "gilani", "raza", "nawaz", "butt", "bhatti", "cheema", "bajwa",
    "warraich", "awan", "niazi", "afridi", "yousafzai", "durrani",
    "tarin", "kashmiri", "ansari", "farooqui", "farooki", "osmani",
    "syed", "saeed", "saeid", "saad", "mian", "iqbal", "saleem",
    "nadeem", "anwar", "aslam", "asif", "ashraf", "akbar", "akram",
    "ghafoor", "rehman", "rahman", "latif", "rashid", "rashed",
    "pervez", "pervaiz", "asghar", "gul", "javed", "zahid", "zafar",
    "tariq", "shafiq", "waqar", "imran", "wasim",

    # ── BANGLADESHI ──
    "islam", "hossain", "hasan", "hosen", "alam", "ali", "begum",
    "chowdhury", "molla", "molla", "bhuiyan", "bhuyan", "sarker",
    "uddin", "karim", "kabir", "monir", "akter", "khatun", "parvin",
    "sultana", "talukder", "taluqdar", "dewan",

    # ── SRI LANKAN ──
    "perera", "fernando", "de silva", "desilva", "jayawardena", "jayawardene",
    "wickramasinghe", "wickremasinghe", "rajapaksa", "rajapaksha",
    "gunasekera", "gunawardena", "gunawardana", "amarasinghe",
    "dissanayake", "dissanayaka", "ranasinghe", "weerasinghe",
    "wickramaratne", "seneviratne", "karunaratne", "pathirana",
    "rodrigo", "siriwardena", "kumarasinghe", "senanayake",
    "thilakaratne", "samarasinghe", "samarageewa", "weerasekera",
    "bandara", "rathnayake", "rathnayaka", "kumara", "madushan",
    "herath", "jayasekera", "jayasinghe", "aluthge",

    # ── NEPALI ──
    "thapa", "rai", "tamang", "gurung", "magar", "shrestha", "karki",
    "poudel", "pokhrel", "adhikari", "bhattarai", "dahal", "koirala",
    "acharya", "bhandari", "khadka", "subedi", "tiwari", "neupane",
    "lama", "sherpa", "limbu", "chhetri",

    # ── ADDITIONAL SOUTH INDIAN COMPOUND NAMES & PATTERNS ──
    # These are common name tokens in South Indian full names
    "vijayakumar", "vijayakumar", "rajakumar", "ramakumar", "senthilkumar",
    "selvakumar", "manikandan", "karthikeyan", "karthik", "murugesan",
    "sureshkumar", "rajkumar", "harikumar", "rajendran", "mahendran",
    "sivasubramanian", "thirunavukkarasu", "shanmugasundaram",
    "venkatraman", "venkataraman", "lakshmanan", "lakshminarayanan",
    "paramasivam", "subramanyan", "narayanasamy", "devanathan",
    "krishnaswamy", "krishnaswami", "sivaraman", "sivaramakrishnan",
    "sundaresan", "balamurugan", "deivasigamani", "annamalai",
    "senthil", "sethu", "saravanan", "vasanthan", "vairamuthu",
    "ramamurthy", "raghunathan", "raghavendra", "raghavan",
    "jayaraman", "jayakumar", "jayaraj", "jeyaraj",
    "ganesan", "ganesh", "ganeshkumar", "ganapathy", "ganapathi",
    "prabhakar", "prabhakaran", "prabhu", "prabhakara",
    "thiruvengadam", "thiruvenkatam", "thiagarajan", "thyagarajan",
    "kuppuswamy", "kumarasamy", "kumaraswamy", "kumaresan",
    "palaniappan", "palanisamy", "palanivelrajan",
    "chidambaram", "chinnasamy", "chinnathambi",
    "arunachalam", "arumughan", "arumugam", "arumuganathan",
    # Telugu-specific
    "venkatesh", "venkateswarlu", "venkataramana", "venkatarao",
    "suryanarayana", "subrahmanyam", "satyanarayana", "satyamurthy",
    "nagabhushanam", "lakshmipathi", "koteshwar", "kondaiah",
    # Kannada-specific
    "hegde", "shetty", "gowda", "naik", "bangera", "nambiar",
    "balasubramanya", "shivakumar", "siddaramaiah",
    # Malayalam-specific additional
    "namboothiri", "nambudiri", "varma", "narayanan", "gopakumar",
    "harikrishnan", "balachandran", "surendran", "sudhakaran",
    "raveendran", "raveendranath", "mohanan", "mohankumar",
    # Common South Asian first names missed before
    "ajitha", "ajith", "maithilee", "maithili", "kunda", "kundal",
    "pradeepkumar", "rajagopalan", "sivarajan", "sivaraja",
    "thirumalai", "thirumurthy", "thirupathi", "thirumalaikolundu",

    # ── COMMON SOUTH ASIAN FIRST NAMES (for when surname alone is ambiguous) ──
    "amit", "anil", "ajay", "alok", "anoop", "arjun", "arvind", "ashish",
    "ashok", "atul", "deepak", "dhruv", "girish", "hardik", "harish",
    "hemant", "hitesh", "kamal", "karan", "lalit", "mahesh", "manish",
    "manoj", "mayank", "mukesh", "naresh", "naveen", "nikhil", "nitin",
    "pankaj", "parag", "parth", "piyush", "pradeep", "prakash", "prasad",
    "praveen", "priyank", "rajesh", "rakesh", "ramesh", "rohit", "sachin",
    "sandeep", "sanjay", "santosh", "saurabh", "shyam", "sudhir", "sumit",
    "sunil", "suresh", "tarun", "umesh", "uday", "vijay", "vikram",
    "vinay", "vineet", "vishal", "vivek", "yogesh",
    "priya", "anita", "kavita", "rekha", "sunita", "usha", "meena",
    "geeta", "gita", "nisha", "neha", "pooja", "puja", "ritu", "sonal",
    "swati", "deepa", "divya", "manisha", "mridula", "nidhi", "puja",
    "radha", "sarita", "seema", "shipra", "shweta", "smita", "sneha",
    "sonia", "sujata", "varsha", "vidya",
    # Pakistani / Bangladeshi first names
    "ayesha", "aisha", "fatima", "fathima", "zainab", "zaynab",
    "maryam", "mariam", "hafsa", "sana", "sara", "amina", "aminah",
    "nadia", "nafia", "rizwana", "sumaiya", "sumaiya", "tahira",
    "muhammad", "mohammed", "mohammad", "usman", "umar", "omar",
    "bilal", "hamza", "hassan", "humaira", "saad", "talha", "taha",
    "zaid", "zayd", "yusuf", "yousuf", "shoaib", "qasim", "obaid",
    "mujeeb", "mubashir", "mehboob", "mazhar", "masood",
}

def is_south_asian_name(full_name: str) -> bool:
    """
    Fast pre-filter: check if any token in the name matches our South Asian name list.
    Case-insensitive. Returns True if at least one name part matches.
    """
    if not full_name:
        return False
    tokens = re.split(r'[\s\-\.]+', full_name.lower())
    for token in tokens:
        token = token.strip()
        if len(token) < 2:
            continue
        if token in SOUTH_ASIAN_SURNAMES:
            return True
    return False


class FacultyParser:
    def __init__(self, input_json="raw_data.json", output_json="cleaned_data.json", screenshots_dir="screenshots"):
        self.input_json = input_json
        self.output_json = output_json
        self.screenshots_dir = screenshots_dir
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self.client = AsyncOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        self.model_name = "qwen3:14b"

    def _is_valid_role(self, role: str) -> bool:
        if not role:
            return False
        role_lower = role.lower()
        for exclude in HARD_EXCLUDE_ROLES:
            if exclude in role_lower:
                return False
        for include in HARD_INCLUDE_ROLES:
            if include in role_lower:
                return True
        return False

    async def _take_screenshot(self, html_filepath, error_name):
        try:
            abs_path = os.path.abspath(html_filepath)
            file_url = f"file:///{abs_path.replace(chr(92), '/')}"
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(file_url)
                screenshot_path = os.path.join(self.screenshots_dir, f"{error_name}.png")
                await page.screenshot(path=screenshot_path)
                await browser.close()
        except Exception as e:
            logger.error(f"Failed to take screenshot for {html_filepath}: {e}")

    def _clean_html(self, html_content):
        """Strip HTML to plain readable text only."""
        soup = BeautifulSoup(html_content, 'html.parser')
        for element in soup(["script", "style", "nav", "footer", "header", "meta", "noscript"]):
            element.extract()
        lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
        text = "\n".join(line for line in lines if line)
        return text[:14000]

    def _extract_personal_website(self, html_content, profile_url="") -> str:
        """Extract a personal/lab website URL from the profile HTML if present.
        Only considers external links (different domain) to avoid picking up
        internal university pages like accessibility statements."""
        from urllib.parse import urlparse
        soup = BeautifulSoup(html_content, 'html.parser')
        profile_domain = urlparse(profile_url).netloc if profile_url else ""

        # Blocked path fragments — internal/admin university pages
        blocked_fragments = [
            'accessibility', 'privacy', 'cookie', 'terms', 'policy',
            'statement', 'login', 'search', 'contact', 'support', 'help',
            'admin', 'intranet', 'my.', 'portal'
        ]

        keywords = ['personal website', 'homepage', 'personal home', 'lab website',
                    'research group', 'personal page', 'website', 'home page',
                    'personal site', 'my website', 'group website']

        for a in soup.find_all('a', href=True):
            link_text = a.get_text(strip=True).lower()
            href = a['href']
            if not href.startswith('http'):
                continue
            parsed = urlparse(href)
            # Must be a different domain (external / truly personal)
            if profile_domain and parsed.netloc == profile_domain:
                continue
            # Skip blocked internal pages
            full_path = (parsed.netloc + parsed.path).lower()
            if any(b in full_path for b in blocked_fragments):
                continue
            if any(kw in link_text for kw in keywords):
                return href
        return ""


    async def _fetch_personal_website_text(self, url: str) -> str:
        """Fetch a personal website and return its cleaned plain text."""
        if not url:
            return ""
        try:
            logger.info(f"Fetching personal website: {url}")
            async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                         headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header",
                                  "meta", "noscript", "aside"]):
                element.extract()
            lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
            text = "\n".join(line for line in lines if line)
            logger.info(f"Got {len(text)} chars from personal website.")
            return text[:8000]  # Cap so we don't blow LLM context
        except Exception as e:
            logger.warning(f"Could not fetch personal website {url}: {e}")
            return ""

    def _get_name_from_url(self, url: str) -> str:
        """Try to extract a readable name from the profile URL as a quick pre-check."""
        try:
            path = url.rstrip('/').split('/')[-1]
            path = re.sub(r'\.html?$', '', path, flags=re.IGNORECASE)
            # Convert underscores/dashes to spaces
            name = path.replace('_', ' ').replace('-', ' ')
            # If there are no spaces, it's likely a merged slug (e.g. amythomas)
            # We return "" so the pre-filter skips and the LLM extracts the real name.
            if ' ' not in name:
                return ""
            return name.strip()
        except Exception:
            return ""

    def _parse_json(self, raw_text):
        """Robustly extract JSON from LLM response."""
        if not raw_text:
            return None
        text = re.sub(r'^```(?:json)?', '', raw_text.strip(), flags=re.IGNORECASE)
        text = re.sub(r'```$', '', text.strip()).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        logger.warning(f"Could not parse JSON from LLM response: {raw_text[:200]}")
        return None

    async def _extract_profile_data(self, page_text, url):
        """
        Extract all structured profile fields using the LLM.
        Instructs the model to ONLY report what is explicitly on the page — no hallucinations.
        """
        system_prompt = (
            "You are a precise academic data extraction assistant. "
            "Extract ONLY information that is EXPLICITLY WRITTEN on the page. "
            "Do NOT infer, guess, or hallucinate. "
            "If a field is not clearly present, return an empty string. "
            "Return ONLY a raw JSON object with no markdown or explanation."
        )

        user_prompt = f"""
Extract the following from this university faculty profile page.
Return a JSON object with exactly these keys:

- "university": Full official university name (NOT a URL). Look in page header/footer/title.
- "department": Full department or school name.
- "name": Faculty member's full name WITHOUT any titles (no Prof., Dr., Mr., Ms., etc.).
- "role": Academic position exactly as stated (e.g., "Professor", "Lecturer", "Reader", "Senior Lecturer").
- "email": Email address. Must contain @. Empty string if not found.
- "phone": Phone number as written (with country code if present). Empty string if not found.
- "research_interests": A VERY SHORT (maximum 10-15 words) comma-separated list of their core research topics. DO NOT write paragraphs. Keep it under one line. Do NOT leave this empty if research content is present.
- "summary": A VERY SHORT (maximum 10-15 words) single-sentence summary of the person's role or main focus. DO NOT write paragraphs. Keep it under one line. Do NOT leave this empty if any biographical content is present.
- "origin": Specific South Asian country of origin deduced from their name and any biographical info
             (e.g., "India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal"). 
             Only use South Asian countries here. If unclear, write "South Asian".

STRICT RULES:
1. "name" = person's name only, no titles at all.
2. "email" must contain @. If not, set to "".
3. "phone" must only have digits, spaces, +, -, (, ). No other text.
4. For research_interests and summary: extract from ALL content provided including the personal website
   section. These are the most important fields — do your best to populate them.
5. Never invent data not present anywhere in the text.

Profile URL: {url}

Combined Page Content (university profile + personal website):
{page_text}
"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            return self._parse_json(raw)
        except Exception as e:
            logger.error(f"LLM call failed for {url}: {e}")
            return None

    async def process(self):
        if not os.path.exists(self.input_json):
            logger.error(f"Input file {self.input_json} does not exist.")
            return

        with open(self.input_json, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        cleaned_data = []
        skipped_not_south_asian = 0
        skipped_role = 0

        for idx, item in enumerate(raw_data):
            html_file = item.get("raw_html_file")
            profile_url = item.get("profile_url", "")

            if not html_file or not os.path.exists(html_file):
                logger.warning(f"HTML file missing for {profile_url}")
                continue

            # ── FAST PRE-FILTER: Check name from URL before any LLM call ──
            url_name = self._get_name_from_url(profile_url)
            if url_name and not is_south_asian_name(url_name):
                logger.info(f"[{idx+1}/{len(raw_data)}] Skipped '{url_name}' — name not South Asian (URL pre-filter).")
                skipped_not_south_asian += 1
                continue

            # ── This profile looks potentially South Asian — call LLM ──
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                page_text = self._clean_html(html_content)

                # ── Fetch personal website for richer Research & Notes ──
                personal_site_url = self._extract_personal_website(html_content, profile_url)
                personal_site_text = await self._fetch_personal_website_text(personal_site_url)
                if personal_site_text:
                    page_text = (
                        page_text
                        + "\n\n=== PERSONAL WEBSITE CONTENT ===\n"
