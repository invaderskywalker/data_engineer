import re
import json
import scrapy
import urllib3
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from scrapy.crawler import CrawlerProcess
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse

# Suppress SSL warnings (use cautiously, enable verification in production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SocialMediaScraper:
    def __init__(self, url,limit=5):
        """
        Initialize the scraper with a LinkedIn URL.
        
        Args:
            url (str): The LinkedIn profile or company page URL (e.g., https://www.linkedin.com/company/xyz).
        """
        self.url = url
        self.profile_data = {
            'url': url,
            'name': '',
            'title': '',
            'company': '',
            'bio': '',
            'social_links': {},
            'raw_content': ''
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.max_links = limit  # Limit to top 5 links

    def get_soup(self) -> Optional[BeautifulSoup]:
        """Fetch the webpage and return a BeautifulSoup object for static content."""
        try:
            print(f"Fetching URL: {self.url}")
            response = requests.get(self.url, headers=self.headers, verify=False, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Failed to fetch URL: {self.url} with error: {e}")
            return None

    def scrape_dynamic(self) -> Optional[str]:
        """Scrape dynamic content using Playwright for JavaScript-rendered LinkedIn pages."""
        try:
            print(f"Scraping dynamic content from: {self.url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.url, timeout=60000)  # 60s timeout
                page.wait_for_load_state('domcontentloaded')  # Wait for content to load
                content = page.content()
                browser.close()
                return content
        except Exception as e:
            print(f"Failed to scrape dynamic content from {self.url} with error: {e}")
            return None

    def clean_url(self, url: str) -> str:
        """Clean URL by removing tracking parameters and duplicates."""
        parsed = urlparse(url)
        # Remove query parameters like 'trk'
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return clean_url

    def extract_profile_data(self, soup: BeautifulSoup) -> None:
        """Extract LinkedIn profile or company page data."""
        # Patterns for social media links (focused on clean profile URLs)
        social_patterns = {
            'linkedin': r'linkedin\.com/(company|in)/[\w-]+/?$',
            'github': r'github\.com/[\w-]+/?$',
            'twitter': r'(twitter|x)\.com/[\w-]+/?$',
            'facebook': r'facebook\.com/[\w-]+/?$',
            'instagram': r'instagram\.com/[\w-]+/?$'
        }

        # Extract name (individual or company)
        name_tag = soup.find('h1', class_=re.compile(r'.*top-card-layout__title.*'))
        self.profile_data['name'] = name_tag.get_text(strip=True) if name_tag else ''

        # Extract title (for individual profiles)
        title_tag = soup.find('h2', class_=re.compile(r'.*top-card-layout__headline.*'))
        self.profile_data['title'] = title_tag.get_text(strip=True) if title_tag else ''

        # Extract company (for individual profiles)
        company_tag = soup.find('span', class_=re.compile(r'.*experience.*company.*'))
        self.profile_data['company'] = company_tag.get_text(strip=True) if company_tag else ''

        # Extract bio/about section
        bio_tag = soup.find('div', class_=re.compile(r'.*about.*section.*'))
        self.profile_data['bio'] = bio_tag.get_text(strip=True) if bio_tag else ''

        # Extract and clean social media links
        link_count = 0
        for link in soup.find_all('a', href=True):
            if link_count >= self.max_links:
                print(f"Reached maximum link limit of {self.max_links}, stopping link extraction")
                break
            href = link['href']
            href = urljoin(self.url, href)
            cleaned_href = self.clean_url(href)
            
            for platform, pattern in social_patterns.items():
                if re.search(pattern, cleaned_href, re.IGNORECASE):
                    # Only store if not a duplicate and not already present
                    if cleaned_href not in self.profile_data['social_links'].values():
                        self.profile_data['social_links'][platform] = cleaned_href
                        print(f"Found {platform} link: {cleaned_href}")
                        link_count += 1
                        break 

        # Extract raw content
        raw_text = soup.get_text(separator=" ", strip=True)
        self.profile_data['raw_content'] = raw_text

    def scrape_with_scrapy(self) -> None:
        """Use Scrapy to crawl the URL for profile data and social media links."""
        class LinkedInSpider(scrapy.Spider):
            name = 'linkedin_spider'
            start_urls = [self.url]
            custom_settings = {
                'USER_AGENT': self.headers['User-Agent'],
                'ROBOTSTXT_OBEY': True,  # Respect robots.txt
                'DOWNLOAD_DELAY': 2  # Add delay to avoid detection
            }

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.profile_data = self.outer.profile_data
                self.max_links = self.outer.max_links
                self.link_count = 0

            def parse(self, response):
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Patterns for social media links
                social_patterns = {
                    'linkedin': r'linkedin\.com/(company|in)/[\w-]+/?$',
                    'github': r'github\.com/[\w-]+/?$',
                    'twitter': r'(twitter|x)\.com/[\w-]+/?$',
                    'facebook': r'facebook\.com/[\w-]+/?$',
                    'instagram': r'instagram\.com/[\w-]+/?$'
                }

                # Extract name
                name_tag = soup.find('h1', class_=re.compile(r'.*top-card-layout__title.*'))
                self.profile_data['name'] = name_tag.get_text(strip=True) if name_tag else ''

                # Extract title
                title_tag = soup.find('h2', class_=re.compile(r'.*top-card-layout__headline.*'))
                self.profile_data['title'] = title_tag.get_text(strip=True) if title_tag else ''

                # Extract company
                company_tag = soup.find('span', class_=re.compile(r'.*experience.*company.*'))
                self.profile_data['company'] = company_tag.get_text(strip=True) if company_tag else ''

                # Extract bio
                bio_tag = soup.find('div', class_=re.compile(r'.*about.*section.*'))
                self.profile_data['bio'] = bio_tag.get_text(strip=True) if bio_tag else ''

                # Extract and clean social links, respecting max_links
                for link in soup.find_all('a', href=True):
                    if self.link_count >= self.max_links:
                        print(f"Reached maximum link limit of {self.max_links} in Scrapy, stopping")
                        break
                    href = link['href']
                    href = urljoin(self.url, href)
                    cleaned_href = self.outer.clean_url(href)
                    for platform, pattern in social_patterns.items():
                        if re.search(pattern, cleaned_href, re.IGNORECASE):
                            if cleaned_href not in self.profile_data['social_links'].values():
                                self.profile_data['social_links'][platform] = cleaned_href
                                print(f"Found {platform} link: {cleaned_href}")
                                self.link_count += 1
                                break

        try:
            print(f"Starting Scrapy crawl for: {self.url}")
            process = CrawlerProcess()
            process.crawl(LinkedInSpider, outer=self)
            process.start()
        except Exception as e:
            print(f"Scrapy crawl failed with error: {e}")

    def scrape(self) -> Dict:
        """Perform the scraping operation: static, dynamic, and Scrapy."""
        # Step 1: Scrape static content with Requests and BeautifulSoup
        soup = self.get_soup()
        print("\n\n\n--debug social media scraper---------", self.url)
        if soup:
            self.extract_profile_data(soup)
        else:
            print(f"Failed to fetch static content from {self.url}")

        # Step 2: Scrape dynamic content with Playwright
        # dynamic_content = self.scrape_dynamic()
        # if dynamic_content:
        #     soup = BeautifulSoup(dynamic_content, 'html.parser')
        #     self.extract_profile_data(soup)
        #     print("Dynamic content scraped successfully")
        # else:
        #     print(f"Failed to fetch dynamic content from {self.url}")

        # Step 3: Crawl with Scrapy (commented out as per your code)
        # self.scrape_with_scrapy()

        return self.profile_data
    
    
    
    def parse_result(self)-> Dict:
        # Extract the JSON part from the input string
        
        scraped_data = self.scrape()
        with open("scraped_data.json", 'w') as file:
            json.dump(scraped_data, file, indent=4)
            
        data_string = json.dumps(scraped_data) if scraped_data else "Not FoUnD"
        
        json_match = re.search(r'\{.*\}', data_string, re.DOTALL)
        if not json_match:
            raise ValueError("No valid JSON found in input.")

        data = json.loads(json_match.group(0))

        raw = data.get("raw_content", "")
        raw = raw.replace("\\n", "\n").replace("\\u00a0", " ").replace("\\", "")

        def extract(pattern):
            match = re.search(pattern, raw)
            return match.group(1).strip() if match else ""

        def extract_all(pattern):
            return [m.strip() for m in re.findall(pattern, raw)]

        # Parse fields
        result = {
            "company_name": extract(r"^([^\|]+)\s+\| LinkedIn"),
            "industry": extract(r"Industry\s+([^\n]+)"),
            "company_size": extract(r"Company size\s+([^\n]+)"),
            "headquarters": extract(r"Headquarters\s+([^\n]+)"),
            "company_type": extract(r"Type\s+([^\n]+)"),
            "founded": extract(r"Founded\s+(\d{4})"),
            "specialties": extract(r"Specialties\s+([^\n]+)").split(", "),
            "follower_count": extract(r"([\d,]+)\s+followers").replace(",", ""),
            "locations": extract_all(r"Get directions\n([^\n]+)"),
            "website": extract(r"Website\s+(https?://[^\s]+)"),
            "about_us": extract(r"About us\n([^\n]+)") or extract(r"About us\s+(.*?)\nWebsite"),
        }
        
        # print("\n\n---debug smmmm---",result)

        return result


if __name__ == "__main__":
    # Example LinkedIn company or profile URL
    scraper = SocialMediaScraper(
        url="https://www.linkedin.com/company/veolia-india-pvt-ltd/?originalSubdomain=in"
    )
    
    # Perform scraping
    result = scraper.scrape()
    
    # Save results to JSON
    with open("linkedin_profile.json", 'w') as file:
        json.dump(result, file, indent=4)
    print("--debug [LinkedIn Profile]--- done")