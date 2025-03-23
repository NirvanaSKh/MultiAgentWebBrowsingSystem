import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd

def extract_links_bs4(url):
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        anchors = soup.find_all("a")
        keyword_tags = ["headline", "story", "news", "article", "update"]
        data = []
        for a in anchors:
            text = a.get_text(strip=True)
            href = a.get("href")
            if not text or not href:
                continue
            if any(kw in text.lower() for kw in keyword_tags) or len(text.split()) > 5:
                full_url = href if href.startswith("http") else urlparse(url)._replace(path=href).geturl()
                data.append({"text": text, "link": full_url})
        return data
    except Exception as e:
        print(f"[HTML fallback] Error: {e}")
        return []

def extract_links_selenium(url):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(3)  # wait for JS to render

        soup = BeautifulSoup(driver.page_source, "html.parser")
        anchors = soup.find_all("a")
        keyword_tags = ["headline", "story", "news", "article", "update"]
        data = []
        for a in anchors:
            text = a.get_text(strip=True)
            href = a.get("href")
            if not text or not href:
                continue
            if any(kw in text.lower() for kw in keyword_tags) or len(text.split()) > 5:
                full_url = href if href.startswith("http") else urlparse(url)._replace(path=href).geturl()
                data.append({"text": text, "link": full_url})
        driver.quit()
        return data
    except Exception as e:
        print(f"[Selenium] Error: {e}")
        return []

def mas_scrape(url, mode="smart"):
    print(f"Scraping URL: {url}")
    if mode == "html":
        return extract_links_bs4(url)
    elif mode == "selenium":
        return extract_links_selenium(url)
    elif mode == "smart":
        html_results = extract_links_bs4(url)
        if html_results:
            return html_results
        print("🛑 HTML fallback returned no results. Trying Selenium...")
        return extract_links_selenium(url)
    else:
        raise ValueError("Invalid mode. Choose from: html, selenium, smart")

# Example usage
if __name__ == "__main__":
    url = input("Enter the site to scrape: ").strip()
    mode = input("Choose mode [html | selenium | smart]: ").strip().lower()
    results = mas_scrape(url, mode=mode or "smart")
    df = pd.DataFrame(results)
    print(df.head())
    df.to_csv("mas_scraped_output.csv", index=False)
    print("✅ Data saved to mas_scraped_output.csv")
