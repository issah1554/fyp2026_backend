from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.viwanda.go.tz"
LIST_URL = f"{BASE_URL}/documents/product-prices-domestic"
SCRAPPER_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SCRAPPER_DIR / "data" / "documents.json"

HEADERS = {
    "User-Agent": ("MarketPriceResearchCrawler/1.0 " "(contact: admin@example.com)")
}


def load_documents(documents_file: Path = OUTPUT_FILE) -> list[dict[str, str]]:
    if not documents_file.exists():
        return []
    with documents_file.open("r", encoding="utf-8") as file:
        documents = json.load(file)
    if not isinstance(documents, list):
        raise ValueError(f"Expected a list of documents in {documents_file}")
    return documents


def collect_documents(max_pages: int = 46) -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    # Load existing to avoid duplicate entries and preserve old history
    try:
        existing = load_documents(OUTPUT_FILE)
        seen_urls = {doc["url"] for doc in existing if "url" in doc}
        documents.extend(existing)
    except Exception:
        pass

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for page in range(1, max_pages + 1):
            url = f"{LIST_URL}?page={page}"
            print(f"Reading page {page}: {url}")

            try:
                response = session.get(url, timeout=30)
                response.raise_for_status()
            except Exception as e:
                print(f"Failed to read page {page}: {e}")
                break

            soup = BeautifulSoup(response.text, "html.parser")
            links = soup.select('a[href*="/uploads/documents/"]')
            if not links:
                break

            for link in links:
                href = link.get("href")

                if not href:
                    continue

                document_url = urljoin(BASE_URL, href)

                if document_url in seen_urls:
                    continue

                seen_urls.add(document_url)

                # Prepend new documents to keep list chronological
                documents.insert(
                    0,
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
