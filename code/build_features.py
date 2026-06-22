import pandas as pd
AQI_PATH = "D:/Pollution Hotspot Predictor/data/raw/aqi.csv"
MATCHED_AREAS_PATH = "D:/Pollution Hotspot Predictor/matched_areas.csv"
ALL_POLLUTANTS = ["PM10", "PM2.5", "O3", "CO", "SO2", "NO2", "NH3", "Pb"]
def _compute_base_features(aqi_path=AQI_PATH):
    
    df = pd.read_csv(aqi_path)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)
    df["area_key"] = df["area"] + " | " + df["state"]
    df = df.sort_values(["area_key", "date"]).reset_index(drop=True)
    grp = df.groupby("area_key")["aqi_value"]
    df["lag_1"] = grp.shift(1)
    df["lag_3"] = grp.shift(3)
    df["lag_7"] = grp.shift(7)
    df["roll_mean_3"] = grp.transform(lambda s: s.shift(1).rolling(3).mean())
    df["roll_mean_7"] = grp.transform(lambda s: s.shift(1).rolling(7).mean())
    df["roll_std_7"] = grp.transform(lambda s: s.shift(1).rolling(7).std())
    for p in ALL_POLLUTANTS:
        col = f"has_{p.replace('.', '').lower()}"
        df[col] = df["prominent_pollutants"].str.contains(p, regex=False).astype(int)

    return df

def load_and_engineer(aqi_path=AQI_PATH, matched_path=MATCHED_AREAS_PATH, horizon=1):
    df = _compute_base_features(aqi_path)

    target_grp = df.groupby("area_key")
    df["target_aqi"] = target_grp["aqi_value"].shift(-horizon)
    df["target_date"] = target_grp["date"].shift(-horizon)
    df["target_month"] = df["target_date"].dt.month
    df["target_dayofweek"] = df["target_date"].dt.dayofweek
    df["target_dayofyear"] = df["target_date"].dt.dayofyear
    df["target_is_weekend"] = (df["target_dayofweek"] >= 5).astype(int)

    gap_days = (df["target_date"] - df["date"]).dt.days
    df = df[gap_days == horizon].copy()
    df["baseline_pred"] = df["aqi_value"]
    matched = pd.read_csv(matched_path)[["area", "state", "lat", "lon"]]
    df = df.merge(matched, on=["area", "state"], how="left")
    df = df.dropna(subset=["target_aqi"]).reset_index(drop=True)
    df["state"] = df["state"].astype("category")
    return df


def latest_snapshot(aqi_path=AQI_PATH, matched_path=MATCHED_AREAS_PATH, horizon=7):
  
    df = _compute_base_features(aqi_path)
    latest = df.groupby("area_key", as_index=False).tail(1).copy()
    latest["target_date"] = latest["date"] + pd.Timedelta(days=horizon)
    latest["target_month"] = latest["target_date"].dt.month
    latest["target_dayofweek"] = latest["target_date"].dt.dayofweek
    latest["target_dayofyear"] = latest["target_date"].dt.dayofyear
    latest["target_is_weekend"] = (latest["target_dayofweek"] >= 5).astype(int)

    matched = pd.read_csv(matched_path)[["area", "state", "lat", "lon"]]
    latest = latest.merge(matched, on=["area", "state"], how="left")
    latest["state"] = latest["state"].astype("category")

    return latest.reset_index(drop=True)

FEATURE_COLUMNS = (
    ["state", "lat", "lon",
     "lag_1", "lag_3", "lag_7", "roll_mean_3", "roll_mean_7", "roll_std_7",
     "number_of_monitoring_stations",
     "target_month", "target_dayofweek", "target_dayofyear", "target_is_weekend"]
    + [f"has_{p.replace('.', '').lower()}" for p in ALL_POLLUTANTS]
)
if __name__ == "__main__":
    data = load_and_engineer()
    print(f"Rows: {len(data)}")
    print(f"Date range: {data['date'].min().date()} -> {data['target_date'].max().date()}")
    print(f"Areas with lat/lon: {data['lat'].notna().sum()} / {len(data)} rows")
    print("\nSample:")
    print(data[["area", "date", "aqi_value", "target_date", "target_aqi", "lag_1", "roll_mean_7"]].head(10))