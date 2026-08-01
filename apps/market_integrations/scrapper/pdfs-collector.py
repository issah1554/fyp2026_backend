from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.viwanda.go.tz"
LIST_URL = f"{BASE_URL}/documents/product-prices-domestic"
OUTPUT_FILE = Path("data/documents.json")

HEADERS = {
    "User-Agent": ("MarketPriceResearchCrawler/1.0 " "(contact: admin@example.com)")
}


def collect_documents(max_pages: int = 46) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for page in range(1, max_pages + 1):
            url = f"{LIST_URL}?page={page}"
            print(f"Reading page {page}: {url}")

            response = session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for link in soup.select('a[href*="/uploads/documents/"]'):
                href = link.get("href")

                if not href:
                    continue

                document_url = urljoin(BASE_URL, href)

                if document_url in seen_urls:
                    continue

                seen_urls.add(document_url)

                documents.append(
                    {
                        "title": link.get_text(" ", strip=True),
                        "url": document_url,
                        "listing_page": str(page),
                    }
                )

            time.sleep(1)

    return documents


def save_documents(documents: list[dict[str, str]], output_file: Path = OUTPUT_FILE) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    documents = collect_documents()
    save_documents(documents)

    print(f"Found {len(documents)} documents")
    print(f"Saved document list to {OUTPUT_FILE}")

    for document in documents[:5]:
        print(document)
