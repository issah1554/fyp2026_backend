import os
import sys
import threading
import time
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


def start_background_sync():
    # Delay initial run slightly to ensure server is fully started and ready
    time.sleep(30)
    
    while True:
        try:
            from apps.market_integrations.services import run_automatic_sync
            run_automatic_sync()
        except Exception as e:
            logger.error(f"Error in background sync loop: {e}", exc_info=True)
            
        # Sleep for 15 minutes before checking again
        time.sleep(900)


class MarketIntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.market_integrations"
    verbose_name = "Market Integrations"

    def ready(self):
        # Prevent running during typical management commands
        if len(sys.argv) > 1:
            cmd = sys.argv[1]
            if cmd in ["migrate", "makemigrations", "collectstatic", "test", "shell", "createsuperuser", "showmigrations", "sqlmigrate"]:
                return

        # Handle runserver double-execution by checking RUN_MAIN
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        # Start the background sync thread
        thread = threading.Thread(target=start_background_sync, daemon=True, name="MarketIntegrationSyncThread")
        thread.start()
        logger.info("Started market integration automatic background sync thread.")
