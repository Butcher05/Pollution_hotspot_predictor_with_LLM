"""
pages/2_Pollution_Map.py  -- Page 3: interactive pollution hotspot map

Self-contained: reads predicted_hotspots.csv directly and builds the same
Leaflet map as the standalone generate_hotspot_map.py script, but renders
it inline inside Streamlit instead of writing a separate .html file.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = APP_ROOT / "data" / "raw"
PREDICTIONS_CSV = DATA_DIR / "D:/Pollution Hotspot Predictor/predicted_hotspots.csv"

CATEGORY_COLORS = {
    "Good": "#22c55e",
    "Satisfactory": "#84cc16",
    "Moderate": "#eab308",
    "Poor": "#f97316",
    "Very Poor": "#ef4444",
    "Severe": "#7f1d1d",
}

st.set_page_config(page_title="Pollution Map", page_icon="🗺️", layout="wide")
st.title("🗺️ Pollution Hotspot Map")

if not PREDICTIONS_CSV.exists():
    st.error(f"Couldn't find {PREDICTIONS_CSV}. Run predict_hotspots.py first.")
    st.stop()

df = pd.read_csv(PREDICTIONS_CSV)

with st.sidebar:
    st.subheader("Filter")

    all_states = ["All States"] + sorted(df["state"].unique())
    selected_state = st.selectbox("State", all_states)

    if selected_state != "All States":
        city_pool = df.loc[df["state"] == selected_state, "area"]
    else:
        city_pool = df["area"]
    city_options = ["All Cities"] + sorted(city_pool.unique())
    selected_city = st.selectbox("City / Area", city_options)

    selected_cats = st.multiselect(
        "Show categories", options=list(CATEGORY_COLORS.keys()),
        default=list(CATEGORY_COLORS.keys()),
    )
    only_hotspots = st.checkbox("Only show flagged hotspots", value=False)

# --- apply filters to the full dataset (not just plottable rows), so the
#     table below stays complete even for areas missing coordinates ---
view = df[df["predicted_category"].isin(selected_cats)]
if only_hotspots:
    view = view[view["is_hotspot"]]
if selected_state != "All States":
    view = view[view["state"] == selected_state]
if selected_city != "All Cities":
    view = view[view["area"] == selected_city]

map_points_df = view.dropna(subset=["lat", "lon"]).copy().sort_values("predicted_aqi")

st.caption(
    f"Showing {len(view)} areas ({len(map_points_df)} plottable) &middot; "
    f"{view['is_hotspot'].sum()} flagged as hotspots",
    unsafe_allow_html=True,
)

# --- dynamic map center/zoom based on the current selection ---
if selected_city != "All Cities" and len(map_points_df) == 1:
    center_lat, center_lon = float(map_points_df.iloc[0]["lat"]), float(map_points_df.iloc[0]["lon"])
    zoom = 10
elif selected_city != "All Cities" and len(map_points_df) == 0:
    st.info(f"'{selected_city}' has no coordinates available, so it can't be centered on the map. Showing all of India instead.")
    center_lat, center_lon, zoom = 22.6, 80.0, 5
elif selected_state != "All States" and len(map_points_df) > 0:
    center_lat, center_lon = float(map_points_df["lat"].mean()), float(map_points_df["lon"].mean())
    zoom = 6
else:
    center_lat, center_lon, zoom = 22.6, 80.0, 5

points = [
    {
        "area": r["area"], "state": r["state"],
        "lat": float(r["lat"]), "lon": float(r["lon"]),
        "last_known_aqi": int(r["last_known_aqi"]),
        "predicted_aqi": round(float(r["predicted_aqi"]), 1),
        "category": r["predicted_category"],
        "forecast_date": str(r["forecast_date"]),
        "is_hotspot": bool(r["is_hotspot"]),
    }
    for _, r in map_points_df.iterrows()
]

map_html = f"""
<div id="map" style="height:680px; border-radius:12px; overflow:hidden;"></div>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  .legend {{
    background: rgba(15, 23, 42, 0.92); color: #e2e8f0; padding: 10px 12px;
    border-radius: 10px; font-size: 12px; line-height: 1.6;
    border: 1px solid #334155; font-family: -apple-system, sans-serif;
  }}
  .legend .swatch {{
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    margin-right: 6px; vertical-align: middle;
  }}
  .leaflet-popup-content-wrapper {{ border-radius: 10px; }}
</style>
<script>
  const points = {json.dumps(points)};
  const colors = {json.dumps(CATEGORY_COLORS)};

  const map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 12,
  }}).addTo(map);

  function radiusFor(aqi) {{ return Math.max(6, Math.min(22, 5 + aqi / 18)); }}

  points.forEach(p => {{
    const color = colors[p.category] || '#888';
    const marker = L.circleMarker([p.lat, p.lon], {{
      radius: radiusFor(p.predicted_aqi),
      fillColor: color,
      color: p.is_hotspot ? '#ffffff' : color,
      weight: p.is_hotspot ? 2.5 : 1,
      fillOpacity: 0.82,
      opacity: p.is_hotspot ? 1 : 0.6,
    }}).addTo(map);

    marker.bindPopup(
      '<b>' + p.area + '</b><br>' + p.state +
      '<br>Last known AQI: <b>' + p.last_known_aqi + '</b>' +
      '<br>Predicted (' + p.forecast_date + '): <b>' + p.predicted_aqi + '</b>' +
      '<br><span style="background:' + color + ';color:white;padding:2px 8px;' +
      'border-radius:999px;font-size:11px;">' + p.category + '</span>'
    );
  }});

  const legend = L.control({{ position: 'bottomleft' }});
  legend.onAdd = function () {{
    const div = L.DomUtil.create('div', 'legend');
    let rows = '<b>Predicted AQI Category</b><br>';
    for (const cat in colors) {{
      rows += '<span class="swatch" style="background:' + colors[cat] + '"></span>' + cat + '<br>';
    }}
    div.innerHTML = rows;
    return div;
  }};
  legend.addTo(map);
</script>
"""

components.html(map_html, height=700, scrolling=False)

st.divider()
st.dataframe(
    view[["area", "state", "last_known_aqi", "predicted_aqi", "predicted_category", "is_hotspot"]]
    .sort_values("predicted_aqi", ascending=False),
    hide_index=True,
    use_container_width=True,
)