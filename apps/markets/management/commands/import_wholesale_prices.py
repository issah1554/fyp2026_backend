import csv
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

if __name__ == "__main__":
    sys.exit(
        "Run this as a Django management command, for example:\n"
        "python manage.py import_wholesale_prices "
        "\"data/www.viwanda.go.tz/sw-1785153773-Wholesale Price 24 Julai, 2026.pdf\" "
        "--user admin_sample"
    )

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.areas.models import AdmArea
from apps.commodities.models import Commodity, CommodityUnit
from apps.markets.models import Market, MarketCommodityPrice


MONTHS_SW = {
    "januari": 1,
    "februari": 2,
    "machi": 3,
    "aprili": 4,
    "mei": 5,
    "juni": 6,
    "julai": 7,
    "agosti": 8,
    "septemba": 9,
    "oktoba": 10,
    "novemba": 11,
    "desemba": 12,
}

COMMODITIES = [
    ("Maize", "Mahindi"),
    ("Rice", "Mchele"),
    ("Sorghum", "Mtama"),
    ("Bulrush Millet", "Uwele"),
    ("Finger Millet", "Ulezi"),
    ("Wheat Grain", "Ngano"),
    ("Beans", "Maharage"),
    ("Irish Potatoes", "Viazi Mviringo"),
]

VIWANDA_MARKET_ROWS = [
    ("Dar es salaam", "Ilala"),
    ("Dar es salaam", "Tandika"),
    ("Dar es salaam", "Temeke"),
    ("Dar es salaam", "Tandale"),
    ("Dar es salaam", "Ubungo"),
    ("Dar es salaam", "Mwananyamala"),
    ("Dar es salaam", "Buguruni"),
    ("Kilimanjaro", "Moshi"),
    ("Singida", "Namfua"),
    ("Arusha", "Kilombero"),
    ("Dodoma", "Majengo"),
    ("Morogoro", "Morogoro"),
    ("Mtwara", "Mtwara DC"),
    ("Lindi", "Lindi mjini"),
    ("Iringa", "Iringa"),
    ("Mara", "Musoma"),
    ("Tanga", "Mgandini"),
    ("Songwe", "Songwe"),
    ("Tabora", "Tabora"),
    ("Geita", "Nyankumbu"),
    ("Kagera", "Bukoba"),
    ("Katavi", "Majengo"),
    ("Mbeya", "Igawilo/Soweto"),
    ("Ruvuma", "Songea"),
    ("Shinyanga", "Shinyanga"),
    ("Mwanza", "Mwanza"),
    ("Pwani", "Mlandizi"),
    ("Simiyu", "Bariadi TC"),
    ("Kigoma", "Kigoma"),
    ("Njombe", "Makambako"),
    ("Rukwa", "Sumbawanga"),
]

VIWANDA_COLUMN_CENTERS = [
    (575, 710),
    (860, 1010),
    (1150, 1291),
    (1431, 1571),
    (1711, 1852),
    (1992, 2148),
    (2296, 2451),
    (2598, 2767),
]


class Command(BaseCommand):
    help = "Import wholesale market prices from the viwanda PDF or a cleaned CSV export."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Path to the PDF or CSV file.")
        parser.add_argument("--date", dest="price_date", help="Price date in YYYY-MM-DD. Defaults to date in filename.")
        parser.add_argument("--currency", default="TZS", help="Currency code. Defaults to TZS.")
        parser.add_argument("--unit", default="100kg", help="Commodity unit symbol. Defaults to 100kg.")
        parser.add_argument("--user", help="Username or email to use as created_by/updated_by.")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to the database.")

    @transaction.atomic
    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.exists():
            raise CommandError(f"Source file does not exist: {source}")

        price_date = self._parse_date(options["price_date"], source.name)
        currency = options["currency"].upper()
        user = self._get_user(options.get("user"))

        rows = self._read_rows(source)
        if not rows:
            raise CommandError("No market price rows were extracted from the source.")

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: parsed {len(rows)} market rows for {price_date}. No database changes were made."
                )
            )
            return

        unit, _ = CommodityUnit.objects.get_or_create(
            symbol=options["unit"],
            defaults={"name": options["unit"], "description": "Wholesale market price unit."},
        )

        created_prices = 0
        updated_prices = 0
        markets_seen = set()

        for row in rows:
            area, _ = AdmArea.objects.get_or_create(
                name=row["region"],
                level=AdmArea.Level.REGION,
                parent=None,
            )
            market, _ = Market.objects.get_or_create(
                name=row["market"],
                admin_area=area,
                deleted_at__isnull=True,
                defaults={"created_by": user, "status": Market.Status.ACTIVE},
            )
            markets_seen.add(market.pk)

            for english_name, sw_name in COMMODITIES:
                min_price = row.get(f"{english_name}_min")
                max_price = row.get(f"{english_name}_max")
                if min_price is None and max_price is None:
                    continue

                commodity, _ = Commodity.objects.get_or_create(
                    name=english_name,
                    defaults={
                        "unit": options["unit"],
                        "unit_ref": unit,
                        "description": sw_name,
                    },
                )
                defaults = {
                    "price": self._representative_price(min_price, max_price),
                    "min_price": min_price,
                    "max_price": max_price,
                    "currency": currency,
                    "updated_by": user,
                }
                _, created = MarketCommodityPrice.all_objects.update_or_create(
                    market=market,
                    commodity=commodity,
                    price_date=price_date,
                    deleted_at__isnull=True,
                    defaults={**defaults, "created_by": user},
                )
                if created:
                    created_prices += 1
                else:
                    updated_prices += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(markets_seen)} markets for {price_date}. "
                f"Created prices: {created_prices}. Updated prices: {updated_prices}."
            )
        )

    def _read_rows(self, source):
        if source.suffix.lower() == ".csv":
            return self._read_csv(source)
        return self._read_pdf(source)

    def _read_csv(self, source):
        rows = []
        with source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required = {"region", "market"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
            for raw in reader:
                row = {
                    "region": (raw.get("region") or "").strip(),
                    "market": (raw.get("market") or "").strip(),
                }
                if not row["region"] or not row["market"]:
                    continue
                for english_name, _ in COMMODITIES:
                    row[f"{english_name}_min"] = self._decimal_or_none(raw.get(f"{english_name}_min"))
                    row[f"{english_name}_max"] = self._decimal_or_none(raw.get(f"{english_name}_max"))
                rows.append(row)
        return rows

    def _read_pdf(self, source):
        try:
            import pdfplumber
        except ImportError as exc:
            raise CommandError("PDF import requires pdfplumber. Install project requirements first.") from exc

        with pdfplumber.open(source) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        if not text.strip():
            return self._read_scanned_viwanda_pdf(source)

        raise CommandError(
            "PDF text extraction is available, but this source layout is not supported yet. "
            "Use a cleaned CSV export for this import."
        )

    def _read_scanned_viwanda_pdf(self, source):
        try:
            from PIL import ImageEnhance, ImageOps
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise CommandError(
                "Scanned PDF import requires rapidocr-onnxruntime and Pillow. "
                "Install project requirements first, or import a cleaned CSV."
            ) from exc

        import pdfplumber

        with pdfplumber.open(source) as pdf:
            if not pdf.pages:
                return []
            image = pdf.pages[0].to_image(resolution=300).original.rotate(270, expand=True)

        table_box = (380, 330, 3225, 2360)
        table = image.crop(table_box)
        table = ImageOps.grayscale(table)
        table = ImageEnhance.Contrast(table).enhance(3)
        table = table.resize((table.width * 2, table.height * 2))

        ocr = RapidOCR()
        result, _ = ocr(table)
        if not result:
            raise CommandError("OCR did not detect any table values in the scanned PDF.")

        values = {}
        for points, raw_text, confidence in result:
            if confidence < 0.85:
                continue
            text = str(raw_text).strip().upper()
            if text != "NA" and not re.fullmatch(r"\d{1,3}(?:[,.]\d{3})+", text):
                continue
            xs = [point[0] / 2 + table_box[0] for point in points]
            ys = [point[1] / 2 + table_box[1] for point in points]
            x_center = (min(xs) + max(xs)) / 2
            y_center = (min(ys) + max(ys)) / 2
            row_index = round((y_center - 491) / 53)
            if row_index < 0 or row_index >= len(VIWANDA_MARKET_ROWS):
                continue
            col_index = self._nearest_index(x_center, [center for pair in VIWANDA_COLUMN_CENTERS for center in pair])
            if col_index is None:
                continue
            values[(row_index, col_index)] = text

        rows = []
        for row_index, (region, market) in enumerate(VIWANDA_MARKET_ROWS):
            row = {"region": region, "market": market}
            for commodity_index, (english_name, _) in enumerate(COMMODITIES):
                min_text = values.get((row_index, commodity_index * 2))
                max_text = values.get((row_index, commodity_index * 2 + 1))
                row[f"{english_name}_min"] = self._decimal_or_none(min_text)
                row[f"{english_name}_max"] = self._decimal_or_none(max_text)
            rows.append(row)

        extracted_cells = sum(
            1
            for row in rows
            for english_name, _ in COMMODITIES
            if row.get(f"{english_name}_min") is not None or row.get(f"{english_name}_max") is not None
        )
        if extracted_cells < 100:
            raise CommandError(
                f"OCR extracted too few price cells ({extracted_cells}). "
                "Use a cleaned CSV export to avoid importing incomplete data."
            )
        return rows

    def _nearest_index(self, value, centers, tolerance=45):
        distances = [(abs(value - center), index) for index, center in enumerate(centers)]
        distance, index = min(distances)
        return index if distance <= tolerance else None

    def _get_user(self, identifier):
        User = get_user_model()
        queryset = User.objects.all()
        if identifier:
            user = queryset.filter(username=identifier).first() or queryset.filter(email=identifier).first()
            if not user:
                raise CommandError(f"No user found for --user={identifier}")
            return user
        user = queryset.filter(is_superuser=True).first() or queryset.filter(is_staff=True).first()
        if not user:
            raise CommandError("No superuser/staff user found. Pass --user=<username-or-email>.")
        return user

    def _parse_date(self, supplied_date, filename):
        if supplied_date:
            return date.fromisoformat(supplied_date)
        match = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", filename, re.IGNORECASE)
        if not match:
            raise CommandError("Could not infer date from filename. Pass --date=YYYY-MM-DD.")
        day, month_name, year = match.groups()
        month = MONTHS_SW.get(month_name.lower())
        if not month:
            raise CommandError(f"Unknown Swahili month in filename: {month_name}")
        return date(int(year), month, int(day))

    def _decimal_or_none(self, value):
        if value is None:
            return None
        cleaned = str(value).strip().upper().replace(",", "")
        if not cleaned or cleaned == "NA":
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise CommandError(f"Invalid price value: {value}") from exc

    def _representative_price(self, min_price, max_price):
        if min_price is not None and max_price is not None:
            return (min_price + max_price) / Decimal("2")
        return min_price if min_price is not None else max_price
