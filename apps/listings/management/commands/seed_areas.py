from django.core.management.base import BaseCommand
from django.db import transaction
from apps.listings.models import AdmArea
from apps.listings.data.tz_areas import TZ_AREAS
from apps.common.ids import generate_unique_public_id


class Command(BaseCommand):
    help = "Seed administrative areas database table from compiled offline Tanzanian administrative areas dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding administrative areas...")

        # Clear existing data if possible
        try:
            AdmArea.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared existing administrative areas."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not clear existing areas: {e}"))

        # Separate by level to guarantee parent insertion first
        regions = [x for x in TZ_AREAS if x["level"] == "region"]
        districts = [x for x in TZ_AREAS if x["level"] == "district"]
        wards = [x for x in TZ_AREAS if x["level"] == "ward"]

        self.stdout.write(f"Found {len(regions)} regions, {len(districts)} districts, {len(wards)} wards.")

        # Dictionary to map SQL id to AdmArea database instance
        area_map = {}

        # 1. Insert Regions
        self.stdout.write("Inserting regions...")
        for r in regions:
            area = AdmArea(
                id=r["id"],
                name=r["name"],
                level=r["level"],
                parent=None
            )
            area.public_id = generate_unique_public_id(AdmArea)
            area.save()
            area_map[r["id"]] = area

        # 2. Insert Districts
        self.stdout.write("Inserting districts...")
        for d in districts:
            parent = area_map.get(d["parent_id"])
            if not parent and d["parent_id"]:
                parent = AdmArea.objects.filter(id=d["parent_id"]).first()
            
            area = AdmArea(
                id=d["id"],
                name=d["name"],
                level=d["level"],
                parent=parent
            )
            area.public_id = generate_unique_public_id(AdmArea)
            area.save()
            area_map[d["id"]] = area

        # 3. Insert Wards
        self.stdout.write("Inserting wards...")
        for w in wards:
            parent = area_map.get(w["parent_id"])
            if not parent and w["parent_id"]:
                parent = AdmArea.objects.filter(id=w["parent_id"]).first()

            area = AdmArea(
                id=w["id"],
                name=w["name"],
                level=w["level"],
                parent=parent
            )
            area.public_id = generate_unique_public_id(AdmArea)
            area.save()
            area_map[w["id"]] = area

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {AdmArea.objects.count()} administrative areas into the database."
            )
        )
