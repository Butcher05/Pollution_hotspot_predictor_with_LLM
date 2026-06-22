import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from build_features import load_and_engineer, FEATURE_COLUMNS

HORIZON_DAYS = 7     
TEST_DAYS = 60      
MODEL_OUT = "aqi_forecaster_7day.joblib"


def time_based_split(df, test_days=TEST_DAYS):
    cutoff = df["target_date"].max() - pd.Timedelta(days=test_days)
    train = df[df["target_date"] <= cutoff]
    test = df[df["target_date"] > cutoff]
    return train, test


def evaluate(y_true, y_pred, label):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    print(f"{label:25s}  MAE={mae:6.2f}   RMSE={rmse:6.2f}   R2={r2:5.3f}")
    return mae, rmse, r2


def main():
    print("Loading and engineering features...")
    df = load_and_engineer(horizon=HORIZON_DAYS)

    train, test = time_based_split(df)
    print(f"\nTrain: {len(train)} rows  ({train['date'].min().date()} -> {train['target_date'].max().date()})")
    print(f"Test:  {len(test)} rows  ({test['date'].min().date()} -> {test['target_date'].max().date()})")

    area_mean = train.groupby("area_key")["aqi_value"].mean()
    global_mean = train["aqi_value"].mean()
    train = train.copy()
    test = test.copy()
    train["area_mean_encoded"] = train["area_key"].map(area_mean)
    test["area_mean_encoded"] = test["area_key"].map(area_mean).fillna(global_mean)

    feature_cols = FEATURE_COLUMNS + ["area_mean_encoded"]
    X_train, y_train = train[feature_cols], train["target_aqi"]
    X_test, y_test = test[feature_cols], test["target_aqi"]

    print("\n--- Baseline: persistence (future = today's value) ---")
    evaluate(y_test, test["baseline_pred"], "Persistence baseline")

    print("\n--- Model: HistGradientBoostingRegressor ---")
    model = HistGradientBoostingRegressor(
        categorical_features="from_dtype",
        max_iter=300,
        learning_rate=0.05,
        random_state=42,
    )
    model.fit(X_train, y_train)

    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    evaluate(y_train, train_pred, "Model (train)")
    evaluate(y_test, test_pred, "Model (test)")

    from sklearn.inspection import permutation_importance
    sample_idx = np.random.RandomState(42).choice(len(X_test), size=min(2000, len(X_test)), replace=False)
    importances = permutation_importance(
        model, X_test.iloc[sample_idx], y_test.iloc[sample_idx],
        n_repeats=5, random_state=42, n_jobs=-1
    )
    importance_df = pd.DataFrame({
        "feature": feature_cols,
        "importance": importances.importances_mean,
    }).sort_values("importance", ascending=False)
    print("\nTop 10 most important features:")
    print(importance_df.head(10).to_string(index=False))

    joblib.dump(model, MODEL_OUT)
    print(f"\nModel saved -> {MODEL_OUT}")

if __name__ == "__main__":
    main()