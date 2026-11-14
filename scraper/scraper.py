import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urlparse

def scrape_website(url):

    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract title
    title = soup.title.get_text(strip=True) if soup.title else "No title"

    # Extract domain
    domain = urlparse(url).netloc

    # Extract paragraphs
    paragraphs = soup.find_all("p")

    main_text = "\n".join(
        p.get_text(" ", strip=True)
        for p in paragraphs
        if p.get_text(strip=True)
    )

    # Store structured data
    page_data = {
        "title": title,
        "url": url,
        "domain": domain,
        "crawl_date": datetime.now(timezone.utc).isoformat(),
        "content": main_text
    }

    return page_data


# Test scraper
if __name__ == "__main__":

    result = scrape_website("https://example.com")

    # Save data into JSON
    with open("data/scraped_data.json", "w") as file:
        json.dump(result, file, indent=4)

    print("Data successfully saved!")

    print(result)