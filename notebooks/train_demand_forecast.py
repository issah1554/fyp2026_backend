from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(SRC_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django


django.setup()

from apps.demand_forecasting.training import train_and_forecast


HORIZON_WEEKS = 4
ESTIMATORS = 200
MIN_ROWS = 200

result = train_and_forecast(
    horizon_weeks=HORIZON_WEEKS,
    estimators=ESTIMATORS,
    min_rows=MIN_ROWS,
)

print(
    "Demand forecast run "
    f"{result.run.public_id} completed: "
    f"MAE={result.run.mae}, RMSE={result.run.rmse}, "
    f"model={result.model_path}"
)
