from django.core.management.base import BaseCommand

from apps.market_integrations.services import sync_prices


class Command(BaseCommand):
    help = "Fetch, normalize, and store market prices from configured integration sources."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=["platform_a", "platform_b", "internal", "viwanda"])
        parser.add_argument("--commodity")
        parser.add_argument("--market")
        parser.add_argument("--limit", type=int)

    def handle(self, *args, **options):
        result = sync_prices(
            source_key=options.get("source"),
            commodity=options.get("commodity"),
            market=options.get("market"),
            limit=options.get("limit"),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced market integrations: {result['created']} created, {result['updated']} updated."
            )
        )
        for error in result["errors"]:
            self.stdout.write(self.style.WARNING(f"{error['source']}: {error['error']}"))
