from django.core.management.base import BaseCommand
from apps.market_integrations.services import check_viwanda_updates


class Command(BaseCommand):
    help = "Check Viwanda document links and sync cached scraper prices without downloading PDFs."

    def handle(self, *args, **options):
        self.stdout.write("Checking for updates from viwanda.go.tz...")
        try:
            result = check_viwanda_updates()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully checked for updates.\n"
                    f"- Documents tracked: {result['document_count']}\n"
                    f"- Downloaded: {result['downloaded_count']} files\n"
                    f"- Cached Records: {result['total_extracted']}\n"
                    f"- DB Synced: {result['sync_result']['created']} created, {result['sync_result']['updated']} updated."
                )
            )
            for error in result["sync_result"]["errors"]:
                self.stdout.write(self.style.WARNING(f"{error['source']}: {error['error']}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error checking for updates: {e}"))
