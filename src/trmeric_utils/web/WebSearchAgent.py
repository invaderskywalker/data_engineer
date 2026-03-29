# web_search.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import parse_qs, urlparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import random

class WebSearchAgent:
    """A class to handle web searches and extract insights for projects and trends."""
    
    def __init__(self):
        # Google Custom Search API credentials
        self.api_key = "AIzaSyCuINySNqEeiHm2tvL1MB1kRlg6QhaMn5c"
        self.search_engine_id = "02f4980774286429c" 
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
        self.headers = {'User-Agent': random.choice(self.user_agents)}  # Randomly select a User-Agent
        self.lock = threading.Lock()
        
    def _fetch_google_results(self, query, num=5):
        """Fetches search results using Google Custom Search API."""
        base_url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': num
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching API results: {e}")
            return None
    
    def _parse_api_results(self, api_response, skip_source=False):
        """Parses JSON response from Google Custom Search API."""
        if not api_response or 'items' not in api_response:
            return []
        
        results = []
        for item in api_response['items']:
            result = {
                'title': item.get('title', ''),
                'snippet': item.get('snippet', '')
            }
            
            if not skip_source:
                result['source'] = item.get('link', '')
                
            results.append(result)
            
        return results
    
    def query_search_engine(self, query, skip_source=False, n=2):
        """Fetches initial search results and retrieves full content for each."""
        # print("debug --- query_search_engine----", query)
        
        # Use Google Custom Search API instead of scraping
        api_response = self._fetch_google_results(query, num=n)
        raw_results = self._parse_api_results(api_response)
        
        # print("debug --- query_search_engine----", query, len(raw_results))
        if not raw_results:
            return []
        
        answers = []
        answers.append({
            "raw_data": raw_results
        })
        
        with ThreadPoolExecutor(max_workers=min(3, len(raw_results))) as executor:
            future_to_query = {
                executor.submit(self._fetch_full_content, result['source']): query 
                for result in raw_results if 'source' in result
            }
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    answers.append(result)
                except Exception as e:
                    print(f"Error processing web search for query '{query}': {e}")
                    answers.append([]) 
                    
        return answers
    
    def _fetch_full_content(self, url, tokens=1000):
        """Fetches and extracts meaningful content from a webpage."""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove non-content elements
            for element in soup.select('nav, footer, header, aside, script, style, [class*="nav"], [class*="menu"], [class*="sidebar"], [class*="footer"], [class*="header"], [class*="banner"], [class*="ad-"], [id*="ad-"], [class*="promo"], [class*="cookie"]'):
                element.decompose()
            
            # Look for main content containers first
            main_content = None
            for container in ['main', 'article', '[role="main"]', '#content', '.content', '.post', '.article', '.post-content', '.entry-content']:
                content_area = soup.select_one(container)
                if content_area and len(content_area.get_text(strip=True)) > 200:
                    main_content = content_area
                    break
            
            # Extract text with priority to main content area
            if main_content:
                paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'li'])
                text_blocks = []
                
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 20:  # Ignore very short fragments
                        # Add headings with special formatting
                        if p.name.startswith('h'):
                            text_blocks.append(f"[{text}]")
                        else:
                            text_blocks.append(text)
                
                full_text = " ".join(text_blocks)
            
            # Fallback to all paragraphs if no main content found or main content is too small
            if not main_content or len(full_text) < 100:
                # Get all paragraphs with meaningful content
                paragraphs = soup.find_all(['p', 'li'])
                text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
                full_text = " ".join(text_blocks)
            
            # Clean the text
            full_text = self._clean_text(full_text)
            
            # Remove duplicate sentences
            sentences = full_text.split('. ')
            unique_sentences = []
            seen = set()
            
            for sentence in sentences:
                # Create a normalized version for comparison
                normalized = re.sub(r'[^a-zA-Z0-9]', '', sentence.lower())
                if normalized and normalized not in seen and len(normalized) > 20:
                    seen.add(normalized)
                    unique_sentences.append(sentence)
            
            full_text = '. '.join(unique_sentences)
            
            # Ensure we don't exceed token limit
            return full_text[:tokens] if full_text else ""
        except requests.RequestException as e:
            print(f"Error fetching full content from {url}: {e}")
            return ""
    
    def _clean_text(self, text):
        """Removes common garbage patterns from text."""
        patterns = [
            r"© \d{4}.*?All rights reserved",
            r"Subscribe now|Sign up|Login|Click here",
            r"\b(advertisement|ad|promo)\b",
            r"Cookie settings",
            r"Privacy Policy",
            r"Terms of (Use|Service)",
            r"We use cookies",
            r"Related articles",
            r"Share this (article|post)",
            r"Follow us on",
            r"Read more about",
            r"Click here to",
            r"You might also like",
        ]
        
        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.I)
            
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove sequences of special characters
        cleaned = re.sub(r'[^\w\s.,!?;:()-]+([\s]|$)', ' ', cleaned)
        
        return cleaned
