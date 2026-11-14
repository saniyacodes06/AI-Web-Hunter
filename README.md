
# 🛰️ AI Web Signal Hunter

### Turning Public Web Conversations into Actionable Market Intelligence

<img width="100%" alt="AI Web Signal Hunter Dashboard" src="https://github.com/user-attachments/assets/2436e8bc-4c02-4b66-af5e-f68620547d67" />

An AI-powered web intelligence project designed to explore publicly accessible web content and identify useful market information from a given topic.


## Project Overview

AI Web Signal Hunter accepts a research topic, discovers relevant web pages, extracts their content and presents the collected sources in an interactive dashboard.

The current working version focuses on web discovery, crawling, source exploration and data export.

## Features

- Topic-based web search and URL discovery
- Crawling of publicly accessible web pages
- Duplicate URL and content filtering
- Extraction of page titles, domains and text
- Crawl progress and domain statistics
- Searchable source explorer
- Page content preview
- CSV and JSON data export

## Technology Stack

- Python
- Streamlit
- Requests
- BeautifulSoup
- DuckDuckGo Search (DDGS)
- Pandas

## Project Structure

```text
AI Web Signal Hunter/
│
├── app.py
├── scraper/
│   └── crawler.py
├── analyzer/
│   ├── ai_analyzer.py
│   └── opportunities.py
├── utils/
├── data/
├── requirements.txt
└── README.md
```

## Installation and Setup

1. Clone or download the project.
2. Open the project directory.
3. Create and activate a virtual environment.
4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the application:

```bash
streamlit run app.py
```

6. Open the local URL displayed in the terminal.

## Current Test Run

Research topic: Problems small businesses face with WhatsApp automation.

- Unique pages successfully crawled: 14
- Unique domains: 14
- Total discovered URLs: 32

The crawl target was 25 pages. This test run did not reach the target.

## Current Limitations

- Some websites restrict automated access or return HTTP errors.
- Search requests may time out.
- The current version focuses on source discovery and exploration.
- LLM-based signal analysis is currently disabled and is not part of the verified working functionality.

## Future Improvements

- Improve search reliability and crawl coverage.
- Add robust retry and error handling.
- Enable LLM-based signal classification and ranking.
- Generate evidence-backed market opportunities.
- Add filtering and prioritization of extracted signals.

## Note

Only publicly accessible pages are considered. The application respects website crawling restrictions and does not guarantee that every discovered URL can be successfully fetched.
