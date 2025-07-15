import os
import sys
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import csv

# Load API keys
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# --- Config ---
CREDIBLE_SOURCES = [
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "marketwatch.com"
]
SEARCH_ENGINE = "google"
ARTICLES_PER_COMPANY = 3
OPENAI_MODEL = "gpt-3.5-turbo"
SEARCH_DAYS = 7

# --- Ticker to Company Mapping ---
TICKER_COMPANY_MAP = {
    "AAPL": "Apple",
    "TSLA": "Tesla",
    "NESN": "Nestlé",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta",
    "NVDA": "Nvidia",
    "NFLX": "Netflix",
}

# --- Helper Functions ---

def get_company_ticker(company):
    # Reverse lookup for company to ticker
    for ticker, name in TICKER_COMPANY_MAP.items():
        if name.lower() == company.lower():
            return ticker
    return "N/A"

def get_company_name_from_ticker(ticker):
    return TICKER_COMPANY_MAP.get(ticker.upper(), ticker.upper())

def search_news(company):
    """Search news using SerpAPI and filter by credible sources and recency."""
    params = {
        "engine": SEARCH_ENGINE,
        "q": f'{company} stock news',
        "api_key": SERPAPI_API_KEY,
        "tbm": "nws",
        "num": 10,
    }
    url = "https://serpapi.com/search"
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return []
    results = resp.json().get("news_results", [])
    filtered = []
    now = datetime.utcnow()
    for r in results:
        link = r.get("link", "")
        source = r.get("source", "").lower()
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        date_str = r.get("date", "")
        # Filter by credible source
        if not any(domain in link for domain in CREDIBLE_SOURCES):
            continue
        # Filter by recency (last 24h)
        if "hour" in date_str or "minute" in date_str or "just now" in date_str:
            pass  # recent
        elif "day" in date_str:
            if int(date_str.split()[0]) > SEARCH_DAYS:
                continue
        else:
            continue  # skip if not recent
        filtered.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "source": source,
        })
        if len(filtered) >= ARTICLES_PER_COMPANY:
            break
    return filtered

def gpt_summarise(ticker, company, article):
    prompt = f"""
You are a financial news analyst. Summarise the following news article for an investor, using the structure below. Only include information relevant to valuation, strategy, or risk. Ignore articles about price moves or technical analysis.

• Ticker: {ticker}
• Company: {company}
• Title: {article['title']}
• Link: {article['link']}
• Snippet: {article['snippet']}

Structure your answer as:
• Ticker:
• Company:
• Title:
• Link:
• Summary (2–3 bullet points of what happened):
• Category (e.g., earnings, M&A, regulatory, product news, etc.):
• Sentiment (positive/neutral/negative):
• Analyst View (impact on fundamental value: positive/neutral/negative, and why):
• Thesis Check (impact on investment thesis):

If the article is not relevant to valuation, strategy, or risk, reply: "Skip (not relevant)".
"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 350,
        "temperature": 0.3,
    }
    resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"].strip()
    else:
        return "Error: Could not summarise article."

def read_tickers_from_csv(filename="tickers.csv"):
    if not os.path.exists(filename):
        return None
    tickers = []
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            for item in row:
                ticker = item.strip()
                if ticker:
                    tickers.append(ticker)
    return tickers if tickers else None

def main():
    # --- Input ---
    tickers = read_tickers_from_csv()
    if tickers:
        companies = [(ticker, get_company_name_from_ticker(ticker)) for ticker in tickers]
    elif len(sys.argv) > 1:
        companies = [(get_company_ticker(c.strip()), c.strip()) for c in sys.argv[1:]]
    else:
        default_companies = ["Apple", "Tesla", "Nestlé"]
        companies = [(get_company_ticker(c), c) for c in default_companies]

    print(f"\n# News Summary ({datetime.utcnow().strftime('%Y-%m-%d')})\n")

    for ticker, company in companies:
        print(f"## {company} ({ticker})\n")
        articles = search_news(company)
        if not articles:
            print("_No relevant news found._\n")
            continue
        for article in articles:
            summary = gpt_summarise(ticker, company, article)
            if "Skip (not relevant)" in summary:
                continue
            print(summary)
            print("\n---\n")
        time.sleep(1)  # To avoid hitting rate limits

if __name__ == "__main__":
    main() 