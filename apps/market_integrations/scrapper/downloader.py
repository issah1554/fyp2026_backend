import json
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

SCRAPPER_DIR = Path(__file__).resolve().parent
DOCUMENTS_FILE = SCRAPPER_DIR / "data" / "documents.json"
DOWNLOAD_DIRECTORY = SCRAPPER_DIR / "data" / "pdfs"
DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)


def download_pdf(
    session: requests.Session,
    document_url: str,
) -> Path:
    encoded_name = Path(urlparse(document_url).path).name
    filename = unquote(encoded_name)

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    output_path = DOWNLOAD_DIRECTORY / filename

    if output_path.exists():
        return output_path

    response = session.get(document_url, timeout=60)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        raise ValueError(f"URL did not return a PDF: {document_url}")

    temporary_path = output_path.with_suffix(".tmp")
    temporary_path.write_bytes(response.content)
    temporary_path.replace(output_path)

    return output_path


def load_documents(documents_file: Path = DOCUMENTS_FILE) -> list[dict[str, str]]:
    with documents_file.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    if not isinstance(documents, list):
        raise ValueError(f"Expected a list of documents in {documents_file}")

    return documents


def download_documents(documents_file: Path = DOCUMENTS_FILE) -> list[Path]:
    documents = load_documents(documents_file)
    downloaded_paths: list[Path] = []

    with requests.Session() as session:
        for index, document in enumerate(documents, start=1):
            document_url = document.get("url")

            if not document_url:
                print(f"Skipping document {index}: missing url")
                continue

            try:
                output_path = download_pdf(session, document_url)
            except Exception as error:
                print(f"Failed to download {document_url}: {error}")
                continue

            downloaded_paths.append(output_path)
            print(f"Downloaded {index}/{len(documents)}: {output_path}")

    return downloaded_paths


if __name__ == "__main__":
    if not DOCUMENTS_FILE.exists():
        raise SystemExit(
            f"{DOCUMENTS_FILE} was not found. Run `python pdfs_collector.py` first."
        )

    downloaded_paths = download_documents()
    print(f"Finished. Downloaded {len(downloaded_paths)} files.")
