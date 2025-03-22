import requests
from bs4 import BeautifulSoup
import pandas as pd

class WebBrowsingAgent:
    def __init__(self, name):
        self.name = name

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
        else:
            raise ValueError(f"Unsupported site: {site}")
