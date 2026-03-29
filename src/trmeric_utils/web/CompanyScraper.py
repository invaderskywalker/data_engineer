# from urllib.parse import urlparse, urljoin
# from scrapingbee import ScrapingBeeClient
# from bs4 import BeautifulSoup
# from concurrent.futures import ThreadPoolExecutor
# from threading import Lock
# from collections import Counter
# import time
# import json

# class CompanyInfoScraper:
#     def __init__(self, landing_page_url, max_workers=3):
#         self.landing_page_url = landing_page_url
#         self.base_url = self.get_base_url(landing_page_url)
#         self.visited_links = set()
#         self.text_dump = []
#         self.lock = Lock()
#         self.max_workers = max_workers
#         self.redundant_phrases = Counter()
#         self.client = ScrapingBeeClient(api_key="2OGFMNNSP6A3QQS8FZIA4OOG43TFQEJJOQQ0FMX3EKJ1MLXGWA7B0LXWBK6MBB98J66YSOYH0DCTPH2B")  # Initialize ScrapingBee client

#     def get_base_url(self, url):
#         parsed_url = urlparse(url)
#         return f"{parsed_url.scheme}://{parsed_url.netloc}"

#     def get_soup(self, url, retries=2, backoff_factor=1.0):
#         for attempt in range(retries):
#             try:
#                 print(f"Fetching URL (Attempt {attempt + 1}): {url}")
#                 response = self.client.get(
#                     url,
#                     params={
#                         'render_js': 'true',  # Enable JavaScript rendering
#                         'premium_proxy': 'true',  # Use premium proxies for better reliability
#                     }
#                 )
#                 response.raise_for_status()
#                 return BeautifulSoup(response.content, "html.parser")
#             except Exception as e:
#                 print(f"Attempt {attempt + 1} failed for {url}: {e}")
#                 if attempt < retries - 1:
#                     sleep_time = backoff_factor * (2 ** attempt)
#                     print(f"Retrying in {sleep_time} seconds...")
#                     time.sleep(sleep_time)
#                 else:
#                     print(f"All attempts failed for {url}")
#                     return None

#     def extract_links(self, soup, from_header=False):
#         links = set()
#         if from_header:
#             header = soup.find("header")
#             if header:
#                 for a_tag in header.find_all("a", href=True):
#                     href = self.normalize_link(a_tag['href'])
#                     if self.is_valid_link(href):
#                         links.add(href)
#         else:
#             for a_tag in soup.find_all("a", href=True):
#                 href = self.normalize_link(a_tag['href'])
#                 if self.is_valid_link(href):
#                     links.add(href)
#         return links

#     def normalize_link(self, href):
#         """Resolve relative links to absolute ones based on the base URL."""
#         normalized_link = urljoin(self.base_url, href)
#         return normalized_link

#     def is_valid_link(self, href):
#         """Check if the link has not been visited and belongs to the same domain."""
#         parsed_href = urlparse(href)
#         base_netloc = urlparse(self.base_url).netloc
#         is_valid = parsed_href.netloc == base_netloc and href not in self.visited_links
#         return is_valid

#     def extract_all_text(self, soup, url):
#         text_content = soup.get_text(separator=" ", strip=True)
#         filtered_content = self.filter_redundant_text(text_content)
#         with self.lock:
#             self.text_dump.append(f"URL: {url}\n\nContent:\n{filtered_content}\n\n{'='*50}\n")

#     def filter_redundant_text(self, text):
#         """Filter out redundant information that appears frequently across multiple pages."""
#         words = text.split()
#         phrase_length = 15  # Adjust the phrase length as needed
#         phrases = [' '.join(words[i:i+phrase_length]) for i in range(len(words) - phrase_length + 1)]
        
#         with self.lock:
#             self.redundant_phrases.update(phrases)
        
#         threshold = 3  # Adjust the threshold as needed
#         common_phrases = {phrase for phrase, count in self.redundant_phrases.items() if count > threshold}
        
#         for phrase in common_phrases:
#             text = text.replace(phrase, "")
        
#         return text.strip()

#     def scrape_page(self, link):
#         if link not in self.visited_links:
#             with self.lock:
#                 self.visited_links.add(link)
#             sub_soup = self.get_soup(link)
#             if sub_soup:
#                 self.extract_all_text(sub_soup, link)

#     def scrape(self):
#         soup = self.get_soup(self.landing_page_url)
#         if not soup:
#             print("Failed to fetch landing page. Exiting.")
#             return

#         self.visited_links.add(self.landing_page_url)
#         links_to_visit = self.extract_links(soup)
        
#         if len(links_to_visit) > 10:
#             header_links = self.extract_links(soup, from_header=True)
#             if header_links:
#                 links_to_visit = header_links

#         self.extract_all_text(soup, self.landing_page_url)

#         with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
#             # Use futures to track completion and handle timeouts
#             futures = [executor.submit(self.scrape_page, link) for link in list(links_to_visit)[:10]]
#             for future in futures:
#                 try:
#                     future.result(timeout=20)  # Wait up to 20 seconds per page
#                 except Exception as e:
#                     print(f"Thread failed: {e}")
        
#         return "\n".join(self.text_dump)

# if __name__ == "__main__":
#     company_search = CompanyInfoScraper(
#         landing_page_url="https://www.veolia.com/en",
#     )

#     result = company_search.scrape()
#     with open("company.json", 'w') as file:
#         json.dump(result, file, indent=4)
#     print("--debug [Company]--- done")



    
from urllib.parse import urlparse, urljoin
import requests
from threading import Lock
from bs4 import BeautifulSoup
from collections import Counter
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
import time


class CompanyInfoScraper:
    def __init__(self, landing_page_url, max_workers=3):  # Reduced workers
        self.landing_page_url = landing_page_url
        self.base_url = self.get_base_url(landing_page_url)
        self.visited_links = set()
        self.text_dump = []
        self.lock = Lock()
        self.max_workers = max_workers
        self.redundant_phrases = Counter()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
        }

    def get_base_url(self, url):
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}"

    def get_soup(self, url, retries=2, backoff_factor=0.5):
        for attempt in range(retries):
            try:
                print(f"Fetching URL (Attempt {attempt + 1}): {url}")
                response = requests.get(
                    url,
                    headers=self.headers,
                    verify=True if attempt < 1 else False,
                    timeout=5  # Increased timeout
                )
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    sleep_time = backoff_factor * (2 ** attempt)
                    print(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    print(f"All attempts failed for {url}")
                    return None

    def extract_links(self, soup, from_header=False):
        links = set()
        if from_header:
            header = soup.find("header")
            if header:
                for a_tag in header.find_all("a", href=True):
                    href = self.normalize_link(a_tag['href'])
                    if self.is_valid_link(href):
                        links.add(href)
        else:
            for a_tag in soup.find_all("a", href=True):
                href = self.normalize_link(a_tag['href'])
                if self.is_valid_link(href):
                    links.add(href)
        return links

    def normalize_link(self, href):
        """Resolve relative links to absolute ones based on the base URL."""
        normalized_link = urljoin(self.base_url, href)
        return normalized_link

    def is_valid_link(self, href):
        """Check if the link has not been visited and belongs to the same domain."""
        parsed_href = urlparse(href)
        base_netloc = urlparse(self.base_url).netloc
        is_valid = parsed_href.netloc == base_netloc and href not in self.visited_links
        return is_valid

    def extract_all_text(self, soup, url):
        text_content = soup.get_text(separator=" ", strip=True)
        filtered_content = self.filter_redundant_text(text_content)
        with self.lock:
            self.text_dump.append(f"URL: {url}\n\nContent:\n{filtered_content}\n\n{'='*50}\n")

    def filter_redundant_text(self, text):
        """Filter out redundant information that appears frequently across multiple pages."""
        words = text.split()
        phrase_length = 15  # Adjust the phrase length as needed
        phrases = [' '.join(words[i:i+phrase_length]) for i in range(len(words) - phrase_length + 1)]
        
        # Update the frequency of each phrase
        with self.lock:
            self.redundant_phrases.update(phrases)
        
        # Identify redundant phrases (appearing more than a threshold)
        threshold = 3  # Adjust the threshold as needed
        common_phrases = {phrase for phrase, count in self.redundant_phrases.items() if count > threshold}
        
        for phrase in common_phrases:
            text = text.replace(phrase, "")
        
        return text.strip()

    def scrape_page(self, link):
        if link not in self.visited_links:
            with self.lock:
                self.visited_links.add(link)
            sub_soup = self.get_soup(link)
            if sub_soup:
                self.extract_all_text(sub_soup, link)

    # def scrape(self):
    #     soup = self.get_soup(self.landing_page_url)
    #     if not soup:
    #         return

    #     self.visited_links.add(self.landing_page_url)
    #     links_to_visit = self.extract_links(soup)
        
    #     # print("\n\n\n--debug [Links]-----", links_to_visit)
    #     # Try extracting links from header if too many links
    #     if len(links_to_visit) > 10:
    #         header_links = self.extract_links(soup, from_header=True)
    #         if header_links:
    #             links_to_visit = header_links

    #     self.extract_all_text(soup, self.landing_page_url)
        
    #     # Use multithreading to scrape multiple pages concurrently
    #     with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    #         executor.map(self.scrape_page, list(links_to_visit)[:15])
    #         executor.map(self.scrape_page, list(links_to_visit)[:15])

    #     return "\n".join(self.text_dump)
    
    
    
    def scrape_v2(self):
        soup = self.get_soup(self.landing_page_url)
        if not soup:
            return

        self.visited_links.add(self.landing_page_url)
        links_to_visit = self.extract_links(soup)
        
        # print("\n\n\n--debug [Links]-----", links_to_visit)
        # Try extracting links from header if too many links
        if len(links_to_visit) > 10:
            header_links = self.extract_links(soup, from_header=True)
            if header_links:
                links_to_visit = header_links

        self.extract_all_text(soup, self.landing_page_url)

        links_traversed = list(links_to_visit)[:15]
        
        # Use multithreading to scrape multiple pages concurrently
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self.scrape_page, list(links_to_visit)[:15])

        result = {
            "data": "\n".join(self.text_dump),
            "image_links": self.fetch_image_links(links_traversed),
            "links": links_traversed
        }
        website_data = result["data"]
        print("---debug website data---", len(website_data))
        return result
    
    
    def fetch_image_links(self, links_to_visit):
        """Fetches image links (.jpg, .jpeg, .svg) from the first 15 links in links_to_visit"""
        
        image_links = set()
        links_to_visit = links_to_visit[7:]
        
        def extract_images(url):
            soup = self.get_soup(url)
            if soup:
                for img in soup.find_all('img', src=True):
                    src = img['src'].lower()
                    if src.endswith(('.jpg', '.jpeg', '.svg')):
                        absolute_url = urljoin(self.base_url, src)
                        with self.lock:
                            image_links.add(absolute_url)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(extract_images, links_to_visit)
            
        # print("--debug image_links-----", image_links)
        result = list(image_links)
        return result[:15]
    
    def scrape(self):
        try:
            print("scrape start ")
            from smart_open import open
            import os
            # 1️⃣ Send POST request to scraping service
            self.service_url = os.getenv("SCRAPING_MACHINE_INTERNAL_ENDPOINT") + "scrape"
            self.key = os.getenv("SCRAPING_MACHINE_KEY")
            target_url = self.landing_page_url
            print("scrape start ", target_url)
            headers = {
                "Content-Type": "application/json",
                "X-Internal-Token": self.key
            }
            payload = {"url": target_url}
            response = requests.post(self.service_url, json=payload, headers=headers)
            response.raise_for_status()  # Raise error if request fails

            # 2️⃣ Parse response JSON to get S3 URL
            result = response.json()
            print("scrape - res ", result)
            s3_url = result.get("s3_url")
            if not s3_url:
                raise ValueError("No s3_url found in service response")

            # 3️⃣ Use smart_open to read JSON directly from S3
            with open(s3_url, 'r') as f:
                data = json.load(f)

            # print("data from web --- ", data)
            return data
        except Exception as e:
            print("error occured ", e)
            return "No content retrieved"

    def scrape_single_page(self):
        try:
            # print("scrape start ")
            from smart_open import open
            import os
            # 1️⃣ Send POST request to scraping service
            self.service_url = os.getenv("SCRAPING_MACHINE_INTERNAL_ENDPOINT") + "page-scrape"
            self.key = os.getenv("SCRAPING_MACHINE_KEY")
            target_url = self.landing_page_url
            print("scrape start ", target_url)
            headers = {
                "Content-Type": "application/json",
                "X-Internal-Token": self.key
            }
            payload = {"url": target_url}
            response = requests.post(self.service_url, json=payload, headers=headers)
            response.raise_for_status()  # Raise error if request fails

            # 2️⃣ Parse response JSON to get S3 URL
            result = response.json()
            print("scrape - res ", result)
            s3_url = result.get("s3_url")
            if not s3_url:
                raise ValueError("No s3_url found in service response")

            # 3️⃣ Use smart_open to read JSON directly from S3
            with open(s3_url, 'r') as f:
                data = json.load(f)

            # print("data from web --- ", data)
            return data
        except Exception as e:
            print("error occured ", e)
            return "No content retrieved"

import json
if __name__ == "__main__":
    company_search = CompanyInfoScraper(
        landing_page_url="https://www.genzoic.com/",
    )


    result = company_search.scrape_v2()
    with open("company.json", 'w') as file:
        json.dump(result, file, indent=4)
    print("--debug [Company]--- done")
    
    # print("---")
    # print(formatted_result)
    