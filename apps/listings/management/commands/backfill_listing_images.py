import cloudinary
import cloudinary.uploader
import urllib.request
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from urllib.parse import quote

from apps.listings.models import CommodityListing, ListingImage


def commons_image(filename):
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(filename)}?width=1200"


def upload_source_image(source_url, folder, context):
    request = urllib.request.Request(
        source_url,
        headers={
            "User-Agent": "MarketiaListingImageBackfill/1.0 (local development data backfill)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        suffix = ".jpg"
        content_type = response.headers.get("Content-Type", "")
        if "png" in content_type:
            suffix = ".png"
        elif "webp" in content_type:
            suffix = ".webp"

        temp_dir = Path(settings.BASE_DIR) / "scratch" / "listing-image-backfill"
        temp_dir.mkdir(parents=True, exist_ok=True)
        image_path = temp_dir / f"source{suffix}"
        image_path.write_bytes(response.read())
        try:
            return cloudinary.uploader.upload(
                str(image_path),
                folder=folder,
                resource_type="image",
                use_filename=True,
                unique_filename=True,
                context=context,
            )
        finally:
            image_path.unlink(missing_ok=True)


COMMODITY_IMAGES = {
    "Maize": [
        "https://images.unsplash.com/photo-1551754655-cd27e38d2076?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1601593346740-925612772716?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=1200&q=85",
    ],
    "Rice": [
        "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1536304929831-ee1ca9d44906?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1592997571659-0b21ff64313b?auto=format&fit=crop&w=1200&q=85",
    ],
    "Beans": [
        "https://images.unsplash.com/photo-1592924357228-91a4daadcfea?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1515543904379-3d757afe72e3?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1601308810941-0f33d42b812c?auto=format&fit=crop&w=1200&q=85",
    ],
    "Coffee": [
        "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1611854779393-1b2da9d400fe?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1447933601403-0c6688de566e?auto=format&fit=crop&w=1200&q=85",
    ],
    "Irish Potatoes": [
        "https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1590165482129-1b8b27097a69?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1508313880080-c4bef0730395?auto=format&fit=crop&w=1200&q=85",
    ],
    "Wheat Grain": [
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1530267981375-f0de937f5f13?auto=format&fit=crop&w=1200&q=85",
    ],
    "Cocoa": [
        "https://images.unsplash.com/photo-1606312619070-d48b4c652a52?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1610632380989-680fe40816c6?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1603052875302-d376b7c0638a?auto=format&fit=crop&w=1200&q=85",
    ],
    "Sorghum": [
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1509358271058-acd01cc9386a?auto=format&fit=crop&w=1200&q=85",
    ],
    "Finger Millet": [
        "https://images.unsplash.com/photo-1653580524515-77b19c176b88?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1509358271058-acd01cc9386a?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=1200&q=85",
    ],
    "Bulrush Millet": [
        "https://images.unsplash.com/photo-1653580524515-77b19c176b88?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1509358271058-acd01cc9386a?auto=format&fit=crop&w=1200&q=85",
        "https://images.unsplash.com/photo-1574323347407-f5e1ad6d020b?auto=format&fit=crop&w=1200&q=85",
    ],
}

class Command(BaseCommand):
    help = "Upload relevant listing images to Cloudinary and save Cloudinary URLs in ListingImage rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be updated without uploading or writing.",
        )
        parser.add_argument(
            "--include-existing-cloudinary",
            action="store_true",
            help="Re-upload listings that already have only Cloudinary URLs.",
        )
        parser.add_argument(
            "--replace-all",
            action="store_true",
            help="Replace every listing image set from the curated commodity image sources.",
        )

    def handle(self, *args, **options):
        if not all([settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, settings.CLOUDINARY_API_SECRET]):
            raise CommandError("Cloudinary env vars are not configured.")

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )

        dry_run = options["dry_run"]
        include_existing_cloudinary = options["include_existing_cloudinary"]
        replace_all = options["replace_all"]
        uploaded_cache = {}
        updated = 0
        skipped = 0
        errors = []

        listings = CommodityListing.objects.select_related("commodity").prefetch_related("images").order_by("id")
        for listing in listings:
            images = list(listing.images.all())
            source_urls = COMMODITY_IMAGES.get(listing.commodity.name, []) if replace_all else [image.image_url for image in images] or COMMODITY_IMAGES.get(listing.commodity.name, [])

            if not source_urls:
                skipped += 1
                errors.append(f"{listing.public_id}: no source images for {listing.commodity.name}")
                continue

            if (
                not include_existing_cloudinary
                and source_urls
                and all("res.cloudinary.com" in url for url in source_urls)
            ):
                skipped += 1
                continue

            if dry_run:
                updated += 1
                self.stdout.write(f"WOULD UPDATE {listing.public_id} {listing.commodity.name} {len(source_urls)} image(s)")
                continue

            try:
                cloudinary_urls = []
                upload_errors = []
                for source_url in source_urls:
                    if "res.cloudinary.com" in source_url:
                        cloudinary_urls.append(source_url)
                        continue

                    cache_key = (listing.commodity.name, source_url)
                    try:
                        if cache_key not in uploaded_cache:
                            result = upload_source_image(
                                folder=f"{settings.CLOUDINARY_LISTINGS_FOLDER}/backfill",
                                source_url=source_url,
                                context={"listing_id": listing.public_id, "commodity": listing.commodity.name},
                            )
                            uploaded_cache[cache_key] = result.get("secure_url") or result.get("url")
                        cloudinary_urls.append(uploaded_cache[cache_key])
                    except Exception as exc:
                        upload_errors.append(f"{source_url}: {exc}")

                if not cloudinary_urls:
                    fallback_urls = COMMODITY_IMAGES.get(listing.commodity.name, [])
                    for fallback_url in fallback_urls:
                        cache_key = (listing.commodity.name, fallback_url)
                        try:
                            if cache_key not in uploaded_cache:
                                result = upload_source_image(
                                    folder=f"{settings.CLOUDINARY_LISTINGS_FOLDER}/backfill",
                                    source_url=fallback_url,
                                    context={"listing_id": listing.public_id, "commodity": listing.commodity.name},
                                )
                                uploaded_cache[cache_key] = result.get("secure_url") or result.get("url")
                            cloudinary_urls.append(uploaded_cache[cache_key])
                        except Exception as exc:
                            upload_errors.append(f"{fallback_url}: {exc}")

                if not cloudinary_urls:
                    raise RuntimeError("; ".join(upload_errors) or "no images uploaded")

                while len(cloudinary_urls) < 3:
                    cloudinary_urls.append(cloudinary_urls[len(cloudinary_urls) % len(cloudinary_urls)])

                with transaction.atomic():
                    listing.images.all().delete()
                    for index, image_url in enumerate(cloudinary_urls):
                        ListingImage.objects.create(
                            listing=listing,
                            image_url=image_url,
                            is_primary=index == 0,
                        )

                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(f"UPDATED {listing.public_id} {listing.commodity.name} {len(cloudinary_urls)} image(s)")
                )
                for upload_error in upload_errors:
                    self.stdout.write(self.style.WARNING(f"SKIPPED SOURCE {listing.public_id}: {upload_error}"))
            except Exception as exc:
                errors.append(f"{listing.public_id}: {exc}")
                self.stderr.write(self.style.ERROR(f"ERROR {listing.public_id}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. updated={updated} skipped={skipped} errors={len(errors)}"
            )
        )
        for error in errors:
            self.stderr.write(error)
