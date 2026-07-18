from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.ussd.forecasting import ForecastUnavailable, get_forecast_service
from apps.ussd.recommendations import RecommendationRefreshService

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None


class Command(BaseCommand):
    help = (
        "Generate and store cached USSD recommendations for supported roles and commodities "
        "from the saved prediction data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="target_date",
            help="Target date in YYYY-MM-DD format. Defaults to today.",
        )

    @staticmethod
    def _render_progress(progress):
        total = max(progress.get("total") or 1, 1)
        current = min(progress.get("current") or 0, total)
        percent = int((current / total) * 100)
        bar_width = 20
        filled = int((current / total) * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        detail = f"{progress['role']} | {progress['commodity']}"
        status = progress["status"].upper()
        message = progress["message"]
        return f"[{bar}] {current}/{total} {percent:>3}% | {status} | {detail} | {message}"

    def handle(self, *args, **options):
        raw_date = options.get("target_date")
        try:
            target_date = date.fromisoformat(raw_date) if raw_date else None
        except ValueError as exc:
            raise CommandError("Invalid --date value. Use YYYY-MM-DD.") from exc

        service = RecommendationRefreshService(get_forecast_service())
        self.stdout.write("Starting cached USSD recommendation refresh...")
        progress_state = {"bar": None}

        class ProgressAwareStdout:
            def __init__(self, wrapped_stdout, state):
                self._wrapped_stdout = wrapped_stdout
                self._state = state

            def write(self, msg="", style_func=None, ending="\n"):
                active_bar = self._state["bar"]
                if active_bar is not None and tqdm is not None:
                    active_bar.clear()
                    self._wrapped_stdout.write(msg, style_func=style_func, ending=ending)
                    active_bar.refresh()
                    return
                self._wrapped_stdout.write(msg, style_func=style_func, ending=ending)

            def flush(self):
                if hasattr(self._wrapped_stdout, "flush"):
                    self._wrapped_stdout.flush()

        progress_stdout = ProgressAwareStdout(self.stdout, progress_state)

        def progress_callback(progress):
            detail = f"{progress['role']} | {progress['commodity']}"
            current = min(progress.get("current") or 0, max(progress.get("total") or 1, 1))
            total = max(progress.get("total") or 1, 1)
            message = progress["message"]

            if tqdm is None:
                self.stdout.write(self._render_progress(progress))
                return

            bar = progress_state["bar"]
            if progress["status"] == "started":
                if bar is not None:
                    bar.close()
                progress_state["bar"] = tqdm(
                    total=total,
                    desc=detail,
                    leave=False,
                    dynamic_ncols=True,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                )
                bar = progress_state["bar"]
                if message:
                    bar.set_postfix_str(message)
                return

            if bar is None:
                progress_state["bar"] = tqdm(
                    total=total,
                    desc=detail,
                    leave=False,
                    dynamic_ncols=True,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                )
                bar = progress_state["bar"]

            bar.total = total
            bar.n = current
            if message:
                bar.set_postfix_str(message)
            bar.refresh()

            if progress["status"] in {"completed", "skipped"}:
                bar.close()
                progress_state["bar"] = None

        try:
            refresh_summary = service.refresh_for_date(
                target_date=target_date,
                stdout=progress_stdout,
                progress_callback=progress_callback,
            )
        except ForecastUnavailable as exc:
            raise CommandError(str(exc)) from exc
        finally:
            if progress_state["bar"] is not None:
                progress_state["bar"].close()
                progress_state["bar"] = None

        selected_date = target_date.isoformat() if target_date else "today"
        results = refresh_summary["results"]
        failures = refresh_summary["failures"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Saved {len(results)} cached USSD recommendations for {selected_date}."
            )
        )
        if failures:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {len(failures)} recommendation set(s) for {selected_date}."
                )
            )
