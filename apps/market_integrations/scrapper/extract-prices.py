from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import pdfplumber

PDF_DIRECTORY = Path("data/pdfs")
JSON_OUTPUT_FILE = Path("data/prices.json")
CSV_OUTPUT_FILE = Path("data/prices.csv")

MONTHS_SW = {
    "januari": "01",
    "februari": "02",
    "machi": "03",
    "aprili": "04",
    "mei": "05",
    "juni": "06",
    "julai": "07",
    "agosti": "08",
    "septemba": "09",
    "oktoba": "10",
    "novemba": "11",
    "desemba": "12",
}

MONTHS_EN = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}

MONTHS = MONTHS_SW | MONTHS_EN


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def clean_price(value: Any) -> int | None:
    text = clean_text(value).upper()

    if not text or text == "NA":
        return None

    digits = re.sub(r"[^\d]", "", text)

    if not digits:
        return None

    return int(digits)


def extract_date(text: str) -> str | None:
    normalized = clean_text(text).lower()
    month_pattern = "|".join(sorted(MONTHS, key=len, reverse=True))
    pattern = rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern}),?\s+(\d{{4}})"
    match = re.search(pattern, normalized, flags=re.IGNORECASE)

    if not match:
        return None

    day, month_name, year = match.groups()
    return f"{year}-{MONTHS[month_name.lower()]}-{int(day):02d}"


def commodity_columns(header_row: list[Any]) -> list[tuple[int, str]]:
    columns: list[tuple[int, str]] = []
    last_commodity = ""

    for index, value in enumerate(header_row[2:], start=2):
        text = clean_text(value)

        if text:
            last_commodity = text

        if index % 2 == 0 and last_commodity:
            columns.append((index, last_commodity))

    return columns


def extract_table_prices(
    table: list[list[Any]],
    source_pdf: Path,
    document_date: str | None,
    page_number: int,
) -> list[dict[str, Any]]:
    if len(table) < 4:
        return []

    title = clean_text(table[0][0] if table[0] else "")
    header_row = table[1]
    columns = commodity_columns(header_row)
    records: list[dict[str, Any]] = []

    for row_number, row in enumerate(table[3:], start=4):
        if len(row) < 4:
            continue

        region = clean_text(row[0])
        market = clean_text(row[1])

        if not region or not market:
            continue

        for min_index, commodity in columns:
            max_index = min_index + 1

            if max_index >= len(row):
                continue

            min_price = clean_price(row[min_index])
            max_price = clean_price(row[max_index])

            if min_price is None and max_price is None:
                continue

            records.append(
                {
                    "date": document_date,
                    "region": region,
                    "market": market,
                    "commodity": commodity,
                    "min_price": min_price,
                    "max_price": max_price,
                    "unit": "TZS per 100kg",
                    "source_pdf": source_pdf.name,
                    "page": page_number,
                    "table_title": title,
                    "row_number": row_number,
                }
            )

    return records


def extract_pdf_prices(pdf_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        first_text = pdf.pages[0].extract_text() if pdf.pages else ""
        document_date = extract_date(first_text or pdf_path.name)

        for page_number, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                records.extend(
                    extract_table_prices(table, pdf_path, document_date, page_number)
                )

    return records


def write_json(records: list[dict[str, Any]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_csv(records: list[dict[str, Any]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "date",
        "region",
        "market",
        "commodity",
        "min_price",
        "max_price",
        "unit",
        "source_pdf",
        "page",
        "table_title",
        "row_number",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def extract_all_prices(pdf_directory: Path = PDF_DIRECTORY) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    pdf_files = sorted(pdf_directory.glob("*.pdf"))

    for index, pdf_path in enumerate(pdf_files, start=1):
        try:
            pdf_records = extract_pdf_prices(pdf_path)
        except Exception as error:
            print(f"Failed to extract {pdf_path.name}: {error}")
            continue

        records.extend(pdf_records)
        print(
            f"Extracted {index}/{len(pdf_files)}: "
            f"{pdf_path.name} ({len(pdf_records)} records)"
        )

    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract commodity prices from PDFs.")
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIRECTORY)
    parser.add_argument("--json", type=Path, default=JSON_OUTPUT_FILE)
    parser.add_argument("--csv", type=Path, default=CSV_OUTPUT_FILE)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    price_records = extract_all_prices(args.pdf_dir)

    write_json(price_records, args.json)
    write_csv(price_records, args.csv)

    print(f"Saved {len(price_records)} price records to {args.json}")
    print(f"Saved {len(price_records)} price records to {args.csv}")
