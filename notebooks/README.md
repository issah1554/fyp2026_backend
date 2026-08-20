# Training Notebooks

Use this folder for model training work instead of typing Django management commands manually.

## Price Forecast Model

Open `train_price_forecast.ipynb` and run all cells.

It trains from the database-backed `MarketCommodityPrice` table and saves the model to:

```text
ai-models/morogoro_price_forecaster_final.joblib
```

## Demand Forecast Model

Open `train_demand_forecast.ipynb` and run all cells.

It trains the demand model, creates forecast rows, and saves artifacts to:

```text
ai-models/
```

You can edit the constants near the bottom of `train_demand_forecast.py` to adjust:

```python
HORIZON_WEEKS = 4
ESTIMATORS = 200
MIN_ROWS = 200
```
