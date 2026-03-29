import requests
from bs4 import BeautifulSoup
import json

class SocialMediaScraper:
    def __init__(self, url):
        self.url = url
        self.text_dump = ""
        self.redundant_phrases = set()

    def get_soup(self):
        """Fetch the webpage and return a BeautifulSoup object."""
        try:
            print(f"Fetching URL: {self.url}")
            response = requests.get(self.url, verify=False)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Failed to fetch URL: {self.url} with error: {e}")
            return None

    def extract_text(self, soup):
        """Extract and filter text from the webpage."""
        raw_text = soup.get_text(separator=" ", strip=True)
        filtered_text = self.filter_redundant_text(raw_text)
        self.text_dump = f"URL: {self.url}\n\nContent:\n{filtered_text}\n\n{'=' * 50}\n"

    def filter_redundant_text(self, text):
        """Filter out commonly occurring phrases."""
        words = text.split()
        phrase_length = 15  # Adjust the phrase length as needed
        phrases = [' '.join(words[i:i + phrase_length]) for i in range(len(words) - phrase_length + 1)]

        # Update redundant phrases set if a phrase appears too often
        threshold = 3  # Adjust as needed
        for phrase in phrases:
            if text.count(phrase) > threshold:
                self.redundant_phrases.add(phrase)

        # Remove redundant phrases from text
        for phrase in self.redundant_phrases:
            text = text.replace(phrase, "")

        return text.strip()

    def scrape(self):
        """Perform the scraping operation."""
        soup = self.get_soup()
        if not soup:
            return "Failed to fetch the content."

        print
        self.extract_text(soup)
        return self.text_dump


if __name__ == "__main__":
    social_media = SocialMediaScraper(
        url = "https://www.linkedin.com/company/veolia-india-pvt-ltd/?originalSubdomain=in"
    )
    

    result = social_media.scrape()
    with open("social media.json", 'w') as file:
        json.dump(result, file, indent=4)
    print("--debug [Company]--- done")
    # print("---")
    # print(formatted_result)