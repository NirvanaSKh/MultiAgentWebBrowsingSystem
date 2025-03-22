import streamlit as st
import pandas as pd
import json
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# --- LangChain LLM ---
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def parse_user_input(user_input: str) -> dict:
    prompt = (
        "You are a filter extractor. Given a user input, extract:\n"
        "- author (if any)\n"
        "- tag (if any)\n"
        "- site: quotes, books, blogs\n\n"
        "Respond ONLY in JSON format like:\n"
        '{"author": "Albert Einstein", "tag": "inspirational", "site": "quotes"}\n\n'
        f"User Input: {user_input}"
    )
    result = llm.invoke([HumanMessage(content=prompt)])
    try:
        return json.loads(result.content)
    except json.JSONDecodeError:
        return {}

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)

def scrape_quotes(driver, author_filter=None, tag_filter=None):
    driver.get("https://quotes.toscrape.com")
    all_data = []
    while True:
        soup = BeautifulSoup(driver.page_source, "html.parser")
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
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, ".next > a")
            next_btn.click()
            time.sleep(1)
        except NoSuchElementException:
            break
    return all_data

def scrape_books(driver):
    driver.get("https://books.toscrape.com/")
    all_data = []
    while True:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        books = soup.find_all("article", class_="product_pod")
        for b in books:
            title = b.h3.a['title']
            price = b.find("p", class_="price_color").text
            availability = b.find("p", class_="instock availability").text.strip()
            all_data.append({"title": title, "price": price, "availability": availability})
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, ".next > a")
            next_btn.click()
            time.sleep(1)
        except NoSuchElementException:
            break
    return all_data

def scrape_blogs(driver):
    driver.get("https://www.python.org/blogs/")
    soup = BeautifulSoup(driver.page_source, "html.parser")
    blogs = soup.select("ul.list-recent-posts li")
    return [{"title": b.a.text, "link": b.a['href'], "date": b.find("time").text} for b in blogs]

def run_scraper(parsed_filters):
    site = parsed_filters.get("site")
    author = parsed_filters.get("author")
    tag = parsed_filters.get("tag")
    driver = setup_driver()
    if site == "quotes":
        data = scrape_quotes(driver, author, tag)
    elif site == "books":
        data = scrape_books(driver)
    elif site == "blogs":
        data = scrape_blogs(driver)
    else:
        driver.quit()
        return [], "Invalid site"
    driver.quit()
    return data, None

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
            data, error = run_scraper(parsed)
            if error:
                st.error(error)
            elif not data:
                st.warning("No results found.")
            else:
                df = pd.DataFrame(data)
                st.dataframe(df)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download CSV", csv, file_name=f"{parsed['site']}_results.csv")
                st.json(data)
