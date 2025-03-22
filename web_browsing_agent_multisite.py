import streamlit as st
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class WebBrowsingAgent:
    def __init__(self, name):
        self.name = name
        self.domain_scrapers = {}

    def register_domain(self, domain, scraper_function):
        self.domain_scrapers[domain.lower()] = scraper_function

    def extract_domain(self, text):
        match = re.search(r'https?://([^/\s]+)', text)
        if match:
            return urlparse(match.group(0)).netloc.lower()
        return None

    def fallback_scraper(self, url):
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        data = []
        for tag in ['h1', 'h2', 'h3', 'p']:
            for element in soup.find_all(tag):
                text = element.get_text(strip=True)
                if text:
                    data.append({"tag": tag, "text": text})
        return data

    def run(self, user_input: str, author=None, tag=None):
        domain = self.extract_domain(user_input)
        if not domain:
            raise ValueError("No valid domain found in input.")
        url_match = re.search(r'https?://[^\s]+', user_input)
        url = url_match.group(0) if url_match else None
        if domain in self.domain_scrapers:
            return self.domain_scrapers[domain](author, tag)
        elif url:
            return self.fallback_scraper(url)
        else:
            raise ValueError(f"Could not scrape: {domain}")

# Built-in scrapers
def scrape_quotes_toscrape(author_filter=None, tag_filter=None):
    base_url = "https://quotes.toscrape.com"
    all_data, next_url = [], "/page/1/"
    while next_url:
        res = requests.get(base_url + next_url)
        soup = BeautifulSoup(res.text, "html.parser")
        for q in soup.find_all("div", class_="quote"):
            text = q.find("span", class_="text").text
            author = q.find("small", class_="author").text
            tags = [t.text for t in q.find_all("a", class_="tag")]
            if author_filter and author_filter.lower() not in author.lower():
                continue
            if tag_filter and tag_filter.lower() not in [t.lower() for t in tags]:
                continue
            all_data.append({"quote": text, "author": author, "tags": ", ".join(tags)})
        btn = soup.select_one(".next > a")
        next_url = btn["href"] if btn else None
    return all_data

def scrape_books_toscrape(*args, **kwargs):
    base_url = "https://books.toscrape.com"
    all_data, next_url = [], "catalogue/page-1.html"
    while next_url:
        res = requests.get(f"{base_url}/{next_url}")
        soup = BeautifulSoup(res.text, "html.parser")
        for b in soup.find_all("article", class_="product_pod"):
            all_data.append({
                "title": b.h3.a["title"],
                "price": b.find("p", class_="price_color").text,
                "availability": b.find("p", class_="instock availability").text.strip()
            })
        btn = soup.select_one(".next > a")
        if btn:
            page_num = int(next_url.split("-")[1].split(".")[0]) + 1
            next_url = f"catalogue/page-{page_num}.html"
        else:
            next_url = None
    return all_data

def scrape_python_blogs(*args, **kwargs):
    url = "https://www.python.org/blogs/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    return [{"title": b.a.text, "link": b.a["href"], "date": b.find("time").text}
            for b in soup.select("ul.list-recent-posts li")]

# LangChain LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def parse_user_input(user_input: str) -> dict:
    prompt = (
        "You are a filter extractor. Given a user input, extract:\n"
        "- author (if any)\n"
        "- tag (if any)\n"
        "- site: include full URL if possible\n\n"
        "Respond ONLY in JSON format like:\n"
        '{"author": "Albert Einstein", "tag": "inspirational", "site": "https://quotes.toscrape.com"}\n\n'
        f"User Input: {user_input}"
    )
    result = llm.invoke([HumanMessage(content=prompt)])
    try:
        return json.loads(result.content)
    except json.JSONDecodeError:
        return {}

# --- Streamlit UI ---
st.set_page_config(page_title="MAS Web Scraper (Auto-Fallback)", layout="wide")
st.title("🌐 MAS: Auto-Fallback Multi-Agent Web Scraper")

agent = WebBrowsingAgent("MASAgent")
agent.register_domain("quotes.toscrape.com", scrape_quotes_toscrape)
agent.register_domain("books.toscrape.com", scrape_books_toscrape)
agent.register_domain("www.python.org", scrape_python_blogs)

user_input = st.text_input("What do you want to scrape?", placeholder="e.g., Scrape quotes from https://quotes.toscrape.com")
if st.button("Run Scraper"):
    if not user_input.strip():
        st.warning("Please enter a valid prompt.")
    else:
        with st.spinner("Processing request..."):
            try:
                filters = parse_user_input(user_input)
                st.write("### 🎯 Detected Filters", filters)
                data = agent.run(user_input, author=filters.get("author"), tag=filters.get("tag"))
                if not data:
                    st.warning("No results found.")
                else:
                    df = pd.DataFrame(data)
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Download CSV", csv, file_name="results.csv")
                    st.json(data)
            except Exception as err:
                st.error(f"❌ {str(err)}")
