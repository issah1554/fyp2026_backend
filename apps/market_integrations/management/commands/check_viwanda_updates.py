from django.core.management.base import BaseCommand
from apps.market_integrations.services import check_viwanda_updates


class Command(BaseCommand):
    help = "Run the scraper to check for new files from viwanda.go.tz, extract prices, and sync them to the database."

    def handle(self, *args, **options):
        self.stdout.write("Checking for updates from viwanda.go.tz...")
        try:
            result = check_viwanda_updates()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully checked for updates.\n"
                    f"- Downloaded: {result['downloaded_count']} new files\n"
                    f"- Total Extracted Records: {result['total_extracted']}\n"
                    f"- DB Synced: {result['sync_result']['created']} created, {result['sync_result']['updated']} updated."
                )
            )
            for error in result["sync_result"]["errors"]:
                self.stdout.write(self.style.WARNING(f"{error['source']}: {error['error']}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error checking for updates: {e}"))
