from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(SRC_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

import django
from django.core.management import call_command


django.setup()


call_command(
    "train_price_forecast",
    output_dir=str(PROJECT_ROOT / "data" / "price_forecasting"),
    model_dir=str(PROJECT_ROOT / "ai-models"),
)
