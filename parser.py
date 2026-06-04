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
