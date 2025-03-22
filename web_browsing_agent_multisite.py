import streamlit as st
import pandas as pd
import json
import requests
from bs4 import BeautifulSoup
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

class WebBrowsingAgent:
    def __init__(self, name):
        self.name = name
        self.custom_sites = {}

    def register_site(self, site_name, scraper_function):
        self.custom_sites[site_name] = scraper_function

    def scrape_quotes(self, author_filter=None, tag_filter=None):
        all_data = []
        base_url = "https://quotes.toscrape.com"
        next_url = "/page/1/"
        while next_url:
            res = requests.get(base_url + next_url)
            soup = BeautifulSoup(res.text, "html.parser")
            quotes = soup.find_all("div", class_="quote")
            for q in quotes:
                text = q.find("span", class_="text").text
                author = q.find("small", class_="author").text
                tags = [t.text for t in q.find_all("a", class_="tag")]
                if author_filter and author_filter.lower() not in author.lower():
                    continue
                if tag_filter and tag_filter.lower() not in [t.lower() for t in tags]:
                    continue
                all_data.append({"quote": text, "author": author, "tags": ", ".join(tags)})
            next_btn = soup.select_one(".next > a")
            next_url = next_btn["href"] if next_btn else None
        return all_data

    def scrape_books(self):
        all_data = []
        base_url = "https://books.toscrape.com"
        next_url = "catalogue/page-1.html"
        while next_url:
            res = requests.get(f"{base_url}/{next_url}")
            soup = BeautifulSoup(res.text, "html.parser")
            books = soup.find_all("article", class_="product_pod")
            for b in books:
                title = b.h3.a['title']
                price = b.find("p", class_="price_color").text
                availability = b.find("p", class_="instock availability").text.strip()
                all_data.append({"title": title, "price": price, "availability": availability})
            next_btn = soup.select_one(".next > a")
            if next_btn:
                current_page = next_url.split("/")[-1]
                page_num = int(current_page.split("-")[1].split(".")[0]) + 1
                next_url = f"catalogue/page-{page_num}.html"
            else:
                next_url = None
        return all_data

    def scrape_blogs(self):
        url = "https://www.python.org/blogs/"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        blogs = soup.select("ul.list-recent-posts li")
        return [{"title": b.a.text, "link": b.a['href'], "date": b.find("time").text} for b in blogs]

    def run(self, site: str, author=None, tag=None):
        print(f"[{self.name}] Scraping site: {site}")
        if site == "quotes":
            return self.scrape_quotes(author, tag)
        elif site == "books":
            return self.scrape_books()
        elif site == "blogs":
            return self.scrape_blogs()
        elif site in self.custom_sites:
            return self.custom_sites[site]()
        else:
            raise ValueError(f"Unsupported site: {site}")

# LangChain LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def parse_user_input(user_input: str) -> dict:
    prompt = (
        "You are a filter extractor. Given a user input, extract:\n"
        "- author (if any)\n"
        "- tag (if any)\n"
        "- site: quotes, books, blogs or custom\n\n"
        "Respond ONLY in JSON format like:\n"
        '{"author": "Albert Einstein", "tag": "inspirational", "site": "quotes"}\n\n'
        f"User Input: {user_input}"
    )
    result = llm.invoke([HumanMessage(content=prompt)])
    try:
        return json.loads(result.content)
    except json.JSONDecodeError:
        return {}

# Example Custom Scraper (static)
def custom_site_scraper():
    url = "https://httpbin.org/html"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.find("h1").text if soup.find("h1") else "No <h1> found"
    return [{"title": title, "source": url}]

# Initialize Agent and register custom site
agent = WebBrowsingAgent("WebScraper")
agent.register_site("custom_site", custom_site_scraper)

# --- Streamlit UI ---
st.set_page_config(page_title="MAS Smart Scraper", layout="wide")
st.title("🧠 MAS: Multi-Agent Smart Web Scraper")

user_input = st.text_input("Enter your scraping request (e.g. 'Get quotes by Steve Jobs about life')")
if st.button("Run Agent"):
    if user_input.strip() == "":
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Thinking..."):
            parsed = parse_user_input(user_input)
            st.write("**Detected Filters:**", parsed)
            try:
                data = agent.run(parsed.get("site"), parsed.get("author"), parsed.get("tag"))
                if not data:
                    st.warning("No results found.")
                else:
                    df = pd.DataFrame(data)
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button("📥 Download CSV", csv, file_name=f"{parsed['site']}_results.csv")
                    st.json(data)
            except Exception as e:
                st.error(str(e))
