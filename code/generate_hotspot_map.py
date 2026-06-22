"""
generate_hotspot_map.py

Builds a standalone interactive HTML map from predicted_hotspots.csv
(produced by predict_hotspots.py). Just double-click the resulting
.html file to open it in any browser -- no server, no Python needed
to VIEW it (only to generate it). Requires internet on first load for
the Leaflet.js/map-tile CDN.

Usage:
    python generate_hotspot_map.py
"""

import json
import pandas as pd
from string import Template

IN_CSV = "D:/Pollution Hotspot Predictor/predicted_hotspots.csv"
OUT_HTML = "hotspot_map.html"

# CPCB-style severity colors: green (clean) -> maroon (severe)
CATEGORY_COLORS = {
    "Good": "#22c55e",
    "Satisfactory": "#84cc16",
    "Moderate": "#eab308",
    "Poor": "#f97316",
    "Very Poor": "#ef4444",
    "Severe": "#7f1d1d",
}


def build_map(in_csv=IN_CSV, out_html=OUT_HTML):
    df = pd.read_csv(in_csv)
    total = len(df)
    plottable = df.dropna(subset=["lat", "lon"]).copy()

    # draw hotspots last so they render on top of the calmer markers
    plottable = plottable.sort_values("predicted_aqi")

    points = []
    for _, r in plottable.iterrows():
        points.append({
            "area": r["area"],
            "state": r["state"],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "last_known_aqi": int(r["last_known_aqi"]),
            "predicted_aqi": round(float(r["predicted_aqi"]), 1),
            "category": r["predicted_category"],
            "forecast_date": str(r["forecast_date"]),
            "is_hotspot": bool(r["is_hotspot"]),
        })

    forecast_date = plottable["forecast_date"].mode().iloc[0] if len(plottable) else "N/A"
    n_hotspots = int(plottable["is_hotspot"].sum())

    html = Template(HTML_TEMPLATE).safe_substitute(
        DATA_JSON=json.dumps(points),
        COLORS_JSON=json.dumps(CATEGORY_COLORS),
        TOTAL=total,
        PLOTTED=len(plottable),
        FORECAST_DATE=forecast_date,
        N_HOTSPOTS=n_hotspots,
    )

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Plotted {len(plottable)} of {total} areas ({total - len(plottable)} lack coordinates)")
    print(f"Saved -> {out_html}  (open this file in any browser)")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pollution Hotspot Forecast - India</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; }
  #header {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    color: #f1f5f9;
    padding: 18px 24px;
    border-bottom: 1px solid #334155;
  }
  #header h1 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -0.01em; }
  #header p { margin: 4px 0 0; font-size: 13px; color: #94a3b8; }
  #header .stat { color: #f97316; font-weight: 600; }
  #map { height: calc(100vh - 76px); width: 100%; }
  .legend {
    background: rgba(15, 23, 42, 0.92);
    color: #e2e8f0;
    padding: 12px 14px;
    border-radius: 10px;
    font-size: 12.5px;
    line-height: 1.7;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    border: 1px solid #334155;
  }
  .legend strong { display: block; margin-bottom: 6px; font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.03em; }
  .legend .swatch { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }
  .leaflet-popup-content-wrapper { border-radius: 10px; }
  .popup-title { font-weight: 700; font-size: 14px; margin-bottom: 2px; }
  .popup-state { color: #64748b; font-size: 12px; margin-bottom: 8px; }
  .popup-row { font-size: 13px; margin: 3px 0; }
  .popup-badge {
    display: inline-block; padding: 2px 8px; border-radius: 999px;
    color: white; font-size: 11px; font-weight: 600; margin-top: 4px;
  }
</style>
</head>
<body>

<div id="header">
  <h1>Pollution Hotspot Forecast &mdash; India</h1>
  <p>7-day-ahead AQI prediction &middot; Forecast date: <span class="stat">$FORECAST_DATE</span>
     &middot; <span class="stat">$N_HOTSPOTS</span> hotspots flagged
     &middot; $PLOTTED of $TOTAL areas plotted (rest lack coordinates)</p>
</div>
<div id="map"></div>

<script>
const points = $DATA_JSON;
const colors = $COLORS_JSON;

const map = L.map('map', { zoomControl: true }).setView([22.6, 80.0], 5);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  maxZoom: 12,
}).addTo(map);

function radiusFor(aqi) {
  return Math.max(6, Math.min(22, 5 + aqi / 18));
}

points.forEach(p => {
  const color = colors[p.category] || '#888';
  const marker = L.circleMarker([p.lat, p.lon], {
    radius: radiusFor(p.predicted_aqi),
    fillColor: color,
    color: p.is_hotspot ? '#ffffff' : color,
    weight: p.is_hotspot ? 2.5 : 1,
    fillOpacity: 0.82,
    opacity: p.is_hotspot ? 1 : 0.6,
  }).addTo(map);

  marker.bindPopup(`
    <div class="popup-title">${p.area}</div>
    <div class="popup-state">${p.state}</div>
    <div class="popup-row">Last known AQI: <b>${p.last_known_aqi}</b></div>
    <div class="popup-row">Predicted (${p.forecast_date}): <b>${p.predicted_aqi}</b></div>
    <span class="popup-badge" style="background:${color}">${p.category}</span>
  `);
});

const legend = L.control({ position: 'bottomleft' });
legend.onAdd = function () {
  const div = L.DomUtil.create('div', 'legend');
  let rows = '<strong>Predicted AQI Category</strong>';
  for (const [cat, col] of Object.entries(colors)) {
    rows += `<div><span class="swatch" style="background:${col}"></span>${cat}</div>`;
  }
  div.innerHTML = rows;
  return div;
};
legend.addTo(map);
</script>

</body>
</html>
"""

if __name__ == "__main__":
    build_map()