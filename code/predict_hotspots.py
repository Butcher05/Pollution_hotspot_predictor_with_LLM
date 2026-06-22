"""
predict_hotspots.py

Uses the trained model to forecast AQI 'horizon' days ahead for every area,
classify each into India's standard CPCB AQI category, and flag hotspots.

CPCB National AQI categories:
    0-50    Good
    51-100  Satisfactory
    101-200 Moderate
    201-300 Poor
    301-400 Very Poor
    401-500 Severe

HOTSPOT_THRESHOLD below marks "Poor" (201+) and worse as a hotspot --
change it if you want a stricter/looser definition.

Usage:
    python predict_hotspots.py
"""

import joblib
import pandas as pd

from build_features import latest_snapshot, FEATURE_COLUMNS

MODEL_PATH = "D:/Pollution Hotspot Predictor/aqi_forecaster_7day.joblib"
AQI_PATH = "D:/Pollution Hotspot Predictor/data/raw/aqi.csv"
HORIZON_DAYS = 7
HOTSPOT_THRESHOLD = 201  
STALE_DAYS_THRESHOLD = 14  
OUT_CSV = "predicted_hotspots.csv"
STALE_OUT_CSV = "excluded_stale_areas.csv"
CATEGORY_BINS = [-1, 50, 100, 200, 300, 400, 10_000]
CATEGORY_LABELS = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]


def categorize(aqi_values):
    return pd.cut(aqi_values, bins=CATEGORY_BINS, labels=CATEGORY_LABELS)


def main():
    print("Loading trained model...")
    model = joblib.load(MODEL_PATH)

    print("Building latest-known feature snapshot for every area...")
    snap = latest_snapshot(horizon=HORIZON_DAYS)
    as_of_date = snap["date"].max()
    days_stale = (as_of_date - snap["date"]).dt.days
    stale_mask = days_stale > STALE_DAYS_THRESHOLD

    if stale_mask.any():
        stale = snap.loc[stale_mask, ["area", "state", "date"]].rename(
            columns={"date": "last_known_date"}
        ).copy()
        stale["days_since_last_report"] = days_stale[stale_mask].values
        stale.sort_values("days_since_last_report", ascending=False).to_csv(STALE_OUT_CSV, index=False)
        print(f"Excluded {stale_mask.sum()} stale areas (no report in {STALE_DAYS_THRESHOLD}+ days "
              f"as of {as_of_date.date()}) -> {STALE_OUT_CSV}")

    snap = snap.loc[~stale_mask].reset_index(drop=True)
    full_history = pd.read_csv(AQI_PATH)
    full_history["area_key"] = full_history["area"] + " | " + full_history["state"]
    area_mean = full_history.groupby("area_key")["aqi_value"].mean()
    global_mean = full_history["aqi_value"].mean()
    snap["area_mean_encoded"] = snap["area_key"].map(area_mean).fillna(global_mean)

    feature_cols = FEATURE_COLUMNS + ["area_mean_encoded"]
    X = snap[feature_cols]

    print(f"Predicting AQI {HORIZON_DAYS} days ahead for {len(snap)} areas...")
    snap["predicted_aqi"] = model.predict(X)
    snap["predicted_category"] = categorize(snap["predicted_aqi"])
    snap["is_hotspot"] = snap["predicted_aqi"] >= HOTSPOT_THRESHOLD

    result = snap[[
        "area", "state", "lat", "lon", "date", "aqi_value",
        "target_date", "predicted_aqi", "predicted_category", "is_hotspot",
    ]].rename(columns={
        "date": "last_known_date",
        "aqi_value": "last_known_aqi",
        "target_date": "forecast_date",
    }).sort_values("predicted_aqi", ascending=False).reset_index(drop=True)

    result.to_csv(OUT_CSV, index=False)

    n_hotspots = result["is_hotspot"].sum()
    print(f"\n{n_hotspots} of {len(result)} active areas predicted as hotspots (AQI >= {HOTSPOT_THRESHOLD})")
    fc_min, fc_max = result["forecast_date"].min(), result["forecast_date"].max()
    if fc_min == fc_max:
        print(f"Forecast date: {fc_min.date()}")
    else:
        print(f"Forecast dates range from {fc_min.date()} to {fc_max.date()} "
              f"(areas reported on slightly different days within the {STALE_DAYS_THRESHOLD}-day freshness window)")
    print(f"\nTop 15 highest-risk areas:")
    print(result.head(15).to_string(index=False))
    print(f"\nSaved full results -> {OUT_CSV}")


if __name__ == "__main__":
    main()