"""
aqi_calculator.py

Converts raw OpenAQ pollutant CONCENTRATIONS (e.g. PM2.5 = 35 ug/m3) into an
actual CPCB AQI number. OpenAQ does not report AQI directly -- it reports
measured concentrations, and CPCB's AQI is computed from those via an
official piecewise-linear breakpoint formula, taking the worst (maximum)
sub-index across all measured pollutants.

Reference: CPCB "National Air Quality Index" (2014), breakpoint table.
Formula:  Ip = (IHi - ILo) / (BPHi - BPLo) * (Cp - BPLo) + ILo

IMPORTANT LIMITATIONS (documented, not hidden):
- CPCB's official breakpoints are defined for 24-hour average concentrations
  (8-hour for CO and O3). OpenAQ's "latest" reading is typically a single
  recent measurement, not a true rolling 24h/8h average. Using it directly
  is a reasonable real-time approximation, not the strict regulatory
  methodology -- the same simplification most "live AQI" apps make.
- Units: breakpoints below are in ug/m3 for all pollutants except CO, which
  CPCB defines in mg/m3. OpenAQ's normalized v3 data is generally in ug/m3.
  Readings whose reported unit doesn't match what's expected here are
  skipped rather than guessed at, since a wrong unit conversion would
  silently produce a wildly wrong AQI.
- CPCB requires a minimum of 3 pollutants (one being PM10/PM2.5) for a
  fully valid AQI. This implementation relaxes that to "at least one of
  PM10/PM2.5 present", since real-time station coverage is patchy, but
  still requires at least one particulate measurement -- gas pollutants
  alone never produce an AQI here.
"""

import pandas as pd

# (BPLo, BPHi, ILo, IHi) breakpoints per CPCB's official table.
# All concentrations in ug/m3 EXCEPT "co", which is in mg/m3.
CPCB_BREAKPOINTS = {
    "pm10": [(0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200),
             (251, 350, 201, 300), (351, 430, 301, 400), (430, 600, 401, 500)],
    "pm25": [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200),
             (91, 120, 201, 300), (121, 250, 301, 400), (250, 500, 401, 500)],
    "no2": [(0, 40, 0, 50), (41, 80, 51, 100), (81, 180, 101, 200),
            (181, 280, 201, 300), (281, 400, 301, 400), (400, 600, 401, 500)],
    "so2": [(0, 40, 0, 50), (41, 80, 51, 100), (81, 380, 101, 200),
            (381, 800, 201, 300), (801, 1600, 301, 400), (1600, 2400, 401, 500)],
    "o3": [(0, 50, 0, 50), (51, 100, 51, 100), (101, 168, 101, 200),
           (169, 208, 201, 300), (209, 748, 301, 400), (748, 900, 401, 500)],
    "co": [(0, 1.0, 0, 50), (1.1, 2.0, 51, 100), (2.1, 10, 101, 200),
           (10.1, 17, 201, 300), (17.1, 34, 301, 400), (34, 50, 401, 500)],  # mg/m3
    "nh3": [(0, 200, 0, 50), (201, 400, 51, 100), (401, 800, 101, 200),
            (801, 1200, 201, 300), (1201, 1800, 301, 400), (1800, 2400, 401, 500)],
}

# Expected OpenAQ unit per pollutant -- readings in any other unit are skipped.
EXPECTED_UNITS = {
    "pm10": "ug/m3", "pm25": "ug/m3", "no2": "ug/m3", "so2": "ug/m3",
    "o3": "ug/m3", "nh3": "ug/m3", "co": "mg/m3",
}

# OpenAQ parameter name variants seen in the wild -> our canonical keys above.
PARAM_ALIASES = {
    "pm25": "pm25", "pm2.5": "pm25", "pm10": "pm10",
    "no2": "no2", "so2": "so2", "o3": "o3", "co": "co", "nh3": "nh3",
}


def concentration_to_subindex(pollutant, concentration):
    """Piecewise-linear CPCB sub-index for one pollutant's concentration.
    Returns None if the pollutant isn't recognized or concentration is negative.
    Concentrations above the top defined breakpoint are capped at AQI 500
    (CPCB's top bracket is officially open-ended, e.g. "PM2.5 250+").
    """
    table = CPCB_BREAKPOINTS.get(pollutant)
    if table is None or concentration is None or concentration < 0:
        return None
    if concentration > table[-1][1]:
        return 500.0
    for bp_lo, bp_hi, i_lo, i_hi in table:
        if bp_lo <= concentration <= bp_hi:
            if bp_hi == bp_lo:
                return float(i_lo)
            return (i_hi - i_lo) / (bp_hi - bp_lo) * (concentration - bp_lo) + i_lo
    return None


def compute_live_aqi(readings):
    """
    readings: list of dicts, each with at least {'parameter': str, 'value': float, 'unit': str}
    for ONE area, ideally all from the same/nearby measurement time.

    Returns dict {aqi, category, dominant_pollutant, n_pollutants_used} or None
    if there isn't enough valid data (no PM10/PM2.5 reading, or nothing usable).
    """
    sub_indices = {}
    for r in readings:
        param = PARAM_ALIASES.get(str(r.get("parameter", "")).lower().strip())
        if param is None:
            continue
        expected_unit = EXPECTED_UNITS[param]
        actual_unit = str(r.get("unit", "")).lower().replace("µ", "u").replace("³", "3").strip()
        if actual_unit != expected_unit:
            continue  # don't guess at unit conversions -- skip rather than risk a wrong AQI
        sub_index = concentration_to_subindex(param, r.get("value"))
        if sub_index is not None:
            # if multiple readings for the same pollutant (multiple stations), keep the worst
            sub_indices[param] = max(sub_index, sub_indices.get(param, -1))

    if not sub_indices:
        return None
    if "pm25" not in sub_indices and "pm10" not in sub_indices:
        return None  # CPCB rule: AQI requires at least one particulate measurement

    dominant = max(sub_indices, key=sub_indices.get)
    return {
        "aqi": round(sub_indices[dominant], 1),
        "dominant_pollutant": dominant,
        "n_pollutants_used": len(sub_indices),
        "sub_indices": sub_indices,
    }


def categorize(aqi_value):
    bins = [-1, 50, 100, 200, 300, 400, 10_000]
    labels = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    return pd.cut([aqi_value], bins=bins, labels=labels)[0]


if __name__ == "__main__":
    # Sanity check against CPCB's own published worked example:
    # PM2.5 = 110 ug/m3 should give sub-index ~265.86 (Poor)
    test = concentration_to_subindex("pm25", 110)
    print(f"PM2.5=110 ug/m3 -> sub-index {test:.2f} (CPCB reference: 265.86)")
    assert abs(test - 265.86) < 0.1, "Breakpoint formula doesn't match CPCB's reference example!"
    print("Breakpoint formula verified against official CPCB example.")