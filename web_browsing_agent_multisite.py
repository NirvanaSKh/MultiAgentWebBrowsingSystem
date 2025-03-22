import streamlit as st
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class MASDispatcherAgent:
    def __init__(self):
        self.category_routes = {
            "quotes": self.scrape_quotes,
            "books": self.scrape_books,
            "blogs": self.scrape_blogs,
            "news": self.scrape_news,
            "ecommerce": self.scrape_books  # fallback to books.toscrape
        }

    def extract_domain(self, text):
        match = re.search(r'https?://([^/\s]+)', text)
        if match:
            return urlparse(match.group(0)).netloc.lower()
        return None

    def scrape_quotes(self, filters):
        base_url = "https://quotes.toscrape.com"
        all_data, next_url = [], "/page/1/"
        while next_url:
            res = requests.get(base_url + next_url)
            soup = BeautifulSoup(res.text, "html.parser")
            for q in soup.find_all("div", class_="quote"):
                text = q.find("span", class_="text").text
                author = q.find("small", class_="author").text
                tags = [t.text for t in q.find_all("a", class_="tag")]
                if filters.get("author") and filters["author"].lower() not in author.lower():
                    continue
                if filters.get("tag") and filters["tag"].lower() not in [t.lower() for t in tags]:
                    continue
                all_data.append({
                    "quote": text,
                    "author": author,
                    "tags": ", ".join(tags),
                    "link": base_url + next_url
                })
            btn = soup.select_one(".next > a")
            next_url = btn["href"] if btn else None
        return all_data

    def scrape_books(self, filters=None):
        base_url = "https://books.toscrape.com"
        all_data, next_url = [], "catalogue/page-1.html"
        while next_url:
            res = requests.get(f"{base_url}/{next_url}")
            soup = BeautifulSoup(res.text, "html.parser")
            for b in soup.find_all("article", class_="product_pod"):
                all_data.append({
                    "title": b.h3.a["title"],
                    "price": b.find("p", class_="price_color").text,
                    "availability": b.find("p", class_="instock availability").text.strip(),
                    "link": base_url + "/" + b.h3.a["href"]
                })
            btn = soup.select_one(".next > a")
            if btn:
                page_num = int(next_url.split("-")[1].split(".")[0]) + 1
                next_url = f"catalogue/page-{page_num}.html"
            else:
                next_url = None
        return all_data

    def scrape_blogs(self, filters=None):
        url = "https://www.python.org/blogs/"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        return [{
            "title": b.a.text,
            "link": b.a["href"],
            "date": b.find("time").text
        } for b in soup.select("ul.list-recent-posts li")]

    def scrape_news(self, filters=None):
        url = "https://www.reuters.com"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        headlines = soup.find_all("h3")
        return [{
            "headline": h.text.strip(),
            "link": url
        } for h in headlines if h.text.strip()]

    def fallback(self, filters):
        url = filters.get("site") or filters.get("url")
        if not url:
            raise ValueError("No site URL provided for fallback.")
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        return [{
            "tag": tag,
            "text": el.text.strip(),
            "link": url
        } for tag in ['h1', 'h2', 'h3', 'p']
          for el in soup.find_all(tag) if el.text.strip()]

    def route(self, filters):
        category = filters.get("category", "").lower()
        if category in self.category_routes:
            return self.category_routes[category](filters)
        return self.fallback(filters)

# LLM to extract task filters + category
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def parse_prompt(prompt: str) -> dict:
    query = (
        "You're a task interpreter. Extract the site, category (quotes, books, blogs, news, ecommerce), "
        "author, tag, and full site URL (if available) from this prompt:\n\n"
        f"{prompt}

"
        "Respond in JSON format like: {"category": "quotes", "author": "Albert Einstein", "
        ""tag": "life", "site": "https://quotes.toscrape.com"}"
    )
    result = llm.invoke([HumanMessage(content=query)])
    try:
        return json.loads(result.content)
    except:
        return {"category": "unknown", "site": "", "author": "", "tag": ""}

# Streamlit UI
st.set_page_config(page_title="MAS Category-Based Scraper", layout="wide")
st.title("🧠 MAS: Intent-Based Web Scraper with Clickable Links")

prompt = st.text_input("What do you want to scrape?", placeholder="e.g., Get latest Python blogs from https://www.python.org")
if st.button("Run Scraper"):
    with st.spinner("Thinking..."):
        filters = parse_prompt(prompt)
        st.write("### 🧾 Parsed Filters", filters)
        agent = MASDispatcherAgent()
        try:
            data = agent.route(filters)
            if not data:
                st.warning("No results found.")
            else:
                df = pd.DataFrame(data)
                if "link" in df.columns:
                    df["link"] = df["link"].apply(lambda x: f"[🔗 Open]({x})")
                st.markdown("### 🔍 Scraped Data")
                st.write(df.to_markdown(index=False), unsafe_allow_html=True)
                st.download_button("📥 Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="mas_output.csv")
        except Exception as e:
            st.error(f"❌ {str(e)}")
