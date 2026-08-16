from django.core.management.base import BaseCommand

from apps.demand_forecasting.training import train_and_forecast


class Command(BaseCommand):
    help = "Train a Random Forest demand forecasting model and persist forecast rows."

    def add_arguments(self, parser):
        parser.add_argument("--horizon-weeks", dest="horizon_weeks", type=int, default=4)
        parser.add_argument("--estimators", type=int, default=200)
        parser.add_argument("--min-rows", dest="min_rows", type=int, default=200)

    def handle(self, *args, **options):
        result = train_and_forecast(
            horizon_weeks=options["horizon_weeks"],
            estimators=options["estimators"],
            min_rows=options["min_rows"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Demand forecast run {result.run.public_id} completed: "
                f"MAE={result.run.mae}, RMSE={result.run.rmse}, "
                f"model={result.model_path}"
            )
        )
