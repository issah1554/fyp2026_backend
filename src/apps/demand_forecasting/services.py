from .models import DemandForecastRun


def latest_successful_run():
    return DemandForecastRun.objects.filter(status="completed").order_by("-training_finished_at", "-created_at").first()

