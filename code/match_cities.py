import unicodedata
import difflib
import pandas as pd

AQI_PATH = "D:/Pollution Hotspot Predictor/data/raw/aqi.csv"
CITIES_PATH = "D:/Pollution Hotspot Predictor/data/raw/India_Cities_LatLng.csv"
FUZZY_CUTOFF = 0.85  


def normalize(name):
    if pd.isna(name):
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name))
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.lower().strip()


def build_matches(aqi_path=AQI_PATH, cities_path=CITIES_PATH):
    aqi = pd.read_csv(aqi_path)
    cities = pd.read_csv(cities_path)

    cities["norm"] = cities["city"].apply(normalize)
    cities["state_norm"] = cities["admin_name"].apply(normalize)
    city_lookup = dict(zip(cities["norm"], zip(cities["lat"], cities["lng"])))

    by_state = {}
    for _, c in cities.iterrows():
        by_state.setdefault(c["state_norm"], {})[c["norm"]] = (c["lat"], c["lng"])

    areas = aqi[["area", "state"]].drop_duplicates().reset_index(drop=True)

    matched_rows, review_rows, unmatched_rows = [], [], []
    for _, row in areas.iterrows():
        area, state = row["area"], row["state"]
        norm_area = normalize(area)
        norm_state = normalize(state)

        if norm_area in city_lookup:
            lat, lon = city_lookup[norm_area]
            matched_rows.append((area, state, lat, lon, "exact"))
            continue

        same_state_candidates = by_state.get(norm_state, {})
        close = difflib.get_close_matches(norm_area, same_state_candidates.keys(), n=1, cutoff=FUZZY_CUTOFF)
        if close:
            lat, lon = same_state_candidates[close[0]]
            matched_rows.append((area, state, lat, lon, "fuzzy_same_state"))
            continue

        close_any = difflib.get_close_matches(norm_area, city_lookup.keys(), n=1, cutoff=FUZZY_CUTOFF)
        if close_any:
            lat, lon = city_lookup[close_any[0]]
            review_rows.append((area, state, close_any[0], lat, lon))
        else:
            unmatched_rows.append((area, state))

    matched_df = pd.DataFrame(matched_rows, columns=["area", "state", "lat", "lon", "match_type"])
    review_df = pd.DataFrame(review_rows, columns=["area", "state", "candidate_city", "candidate_lat", "candidate_lon"])
    unmatched_df = pd.DataFrame(unmatched_rows, columns=["area", "state"])
    return matched_df, review_df, unmatched_df


if __name__ == "__main__":
    matched_df, review_df, unmatched_df = build_matches()

    matched_df.to_csv("matched_areas.csv", index=False)
    review_df.to_csv("review_cross_state.csv", index=False)
    unmatched_df.to_csv("unmatched_areas.csv", index=False)

    print(f"Matched (safe): {len(matched_df)} areas -> matched_areas.csv")
    print(f"Needs manual review (cross-state fuzzy): {len(review_df)} -> review_cross_state.csv")
    print(f"Unmatched: {len(unmatched_df)} areas -> unmatched_areas.csv (need manual coords/geocoding)")