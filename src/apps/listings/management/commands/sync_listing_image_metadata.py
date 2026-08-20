from django.core.management.base import BaseCommand, CommandError

from apps.listings.models import ListingImage
from apps.listings.services import (
    cloudinary_public_id_from_url,
    sync_listing_image_cloudinary_metadata,
)


class Command(BaseCommand):
    help = "Sync ListingImage public IDs into Cloudinary context metadata for existing listing images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report images that would be synced without updating Cloudinary.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        images = ListingImage.objects.select_related("listing", "listing__commodity").order_by("id")
        synced = 0
        skipped = 0
        failed = 0

        for image in images:
            public_id = cloudinary_public_id_from_url(image.image_url)
            if not public_id:
                skipped += 1
                continue

            if dry_run:
                synced += 1
                self.stdout.write(f"WOULD SYNC image_id={image.public_id} cloudinary_public_id={public_id}")
                continue

            try:
                sync_listing_image_cloudinary_metadata(image)
                synced += 1
                self.stdout.write(self.style.SUCCESS(f"SYNCED image_id={image.public_id}"))
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"FAILED image_id={image.public_id}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(f"Done. synced={synced} skipped={skipped} failed={failed}")
        )
        if failed:
            raise CommandError(f"{failed} image metadata sync(s) failed.")
