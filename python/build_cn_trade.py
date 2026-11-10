"""Build docs/data/us_eu_cbam_cn_trade.json for the dashboard (docs/index.html).

Pulls EU27 imports from the United States (Eurostat Comext DS-045409, monthly, Jan 2021 onward)
for the CBAM CN codes used by the U.S. CBAM Exposure Calculator, plus each code's Comext label.
Stdlib only; the Comext API needs no key.

Hydrogen (CN 2804 10 00 = HS 2804.10) is the exception: Comext's series contains an implausible
Aug 2025 entry (57,134 t at EUR 3.5M), so hydrogen comes from U.S. Census Bureau exports to the
European Union instead (USD converted to EUR at ECB monthly average rates; volume = air + vessel
shipping weight). This needs CENSUS_API_KEY in the environment or in the project .env file.

Usage: python python/build_cn_trade.py
"""
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "us_eu_cbam_cn_trade.json"
START = "2021-01"
SDMX = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
STATS = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409"
CENSUS = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
ECB_FX = "https://data-api.ecb.europa.eu/service/data/EXR/M.USD.EUR.SP00.A?format=csvdata"
H2_CN, H2_HS = "28041000", "280410"

# CN code lists: same as US_CBAM_Exposure-dashboard/scripts/fetch_comext_jan_mar.mjs
SECTORS = {
 "Iron & Steel": "26011200+7201+720211+720241+72026000+7203+7205+72061000+7208+7209+7210+72111300+7212+7213+72142000+7215+7216+721710+721720+72181000+72191100+72193100+7221+722300+722410+72251100+722530+722550+7301+7302+730300+730419+730439+7305+73061900+73063080+73072100+73079100+7308+7309+7310+731100+731815+731816+73182200+73182300+73269098",
 "Aluminium": "7601+7603+76041010+76041090+76042100+76042910+76042990+7605+7606+7607+7608+76090000+76101000+76110000+7612+76130000+7614+76161000+76169100+76169910+76169990",
 "Fertilisers": "28080000+28141000+28142000+28342100+31021012+31021015+31021019+31021090+31022100+31022900+31023010+31023090+31024010+31024090+31025000+31026000+31028000+31029000+31051000+31052010+31052090+31053000+31054000+31055100+31055900+31059020+31059080",
 "Hydrogen": "28041000",
 "Cement": "25070080+25231000+25232100+25232900+25239000+25233000",
}

def get(url):
    for attempt in range(3):
        try:
            return urllib.request.urlopen(url, timeout=170).read().decode()
        except Exception as e:
            print(f"  retry ({e})", file=sys.stderr); time.sleep(5)
    sys.exit(f"Failed: {url[:120]}")

series, periods, last_update = {}, set(), ""
for sector, codes in SECTORS.items():
    print(f"Fetching {sector}...", file=sys.stderr)
    txt = get(f"{SDMX}/M.EU27_2020.US.{codes}.1.VALUE_IN_EUROS+QUANTITY_IN_100KG/?format=SDMX-CSV&startPeriod={START}")
    for r in csv.DictReader(io.StringIO(txt)):
        if r["OBS_VALUE"] == "": continue
        last_update = last_update or r.get("LAST UPDATE", "")
        cn, p = r["product"], r["TIME_PERIOD"]
        periods.add(p)
        s = series.setdefault((sector, cn), {})
        k = "eur" if r["indicators"] == "VALUE_IN_EUROS" else "t"
        v = float(r["OBS_VALUE"]) if k == "eur" else float(r["OBS_VALUE"]) / 10
        s.setdefault(p, {"eur": 0.0, "t": 0.0})[k] += v

all_codes = [c for codes in SECTORS.values() for c in codes.split("+")]
labels = {}
for i in range(0, len(all_codes), 30):
    q = "&".join("product=" + c for c in all_codes[i:i+30])
    j = json.loads(get(f"{STATS}?freq=M&reporter=EU27_2020&partner=US&{q}&flow=1&indicators=VALUE_IN_EUROS&time=2024-01"))
    labels.update(j["dimension"]["product"]["category"]["label"])
# Comext concatenates historical labels as "label(2017-2500);label(2012-2016)..."; keep the current one
clean = lambda l: re.split(r"\(\d{4}-\d{4}\)", l)[0].strip()

P = sorted(periods)

# Hydrogen: replace the Comext series with Census exports to the EU, converted to EUR
def census_key():
    if os.getenv("CENSUS_API_KEY"): return os.environ["CENSUS_API_KEY"]
    env = ROOT / ".env"
    for line in (env.read_text().splitlines() if env.exists() else []):
        k, _, v = line.partition("=")
        if k.strip() == "CENSUS_API_KEY": return v.strip().strip('"\'')
    sys.exit("CENSUS_API_KEY not found (needed for hydrogen); set it or add it to .env")

print("Fetching Hydrogen from U.S. Census...", file=sys.stderr)
q = urllib.parse.urlencode({"get": "ALL_VAL_MO,AIR_WGT_MO,VES_WGT_MO", "E_COMMODITY": H2_HS, "COMM_LVL": "HS6",
                            "CTY_CODE": "0003", "time": f"from {START}", "key": census_key()},
                           quote_via=urllib.parse.quote)  # 0003 = European Union
rows = json.loads(get(f"{CENSUS}?{q}"))
hdr = rows[0]; census = {r[hdr.index("time")]: dict(zip(hdr, r)) for r in rows[1:]}
fx = {r["TIME_PERIOD"]: float(r["OBS_VALUE"]) for r in csv.DictReader(io.StringIO(get(f"{ECB_FX}&startPeriod={START}")))}
# Census omits months with no recorded exports (e.g. 2022-01); those are zero, not missing
missing = [p for p in P if p not in fx or p > max(census)]
if missing: sys.exit(f"ECB rate or Census release missing for {missing}")
h2 = series[("Hydrogen", H2_CN)] = {}
for p in P:
    c = census.get(p, {"ALL_VAL_MO": 0, "AIR_WGT_MO": 0, "VES_WGT_MO": 0})
    h2[p] = {"eur": float(c["ALL_VAL_MO"]) / fx[p], "t": (float(c["AIR_WGT_MO"]) + float(c["VES_WGT_MO"])) / 1000}

out = {"periods": P, "retrieved": date.today().isoformat(), "comext_last_update": last_update,
       "hydrogen_source": {"census_latest": max(census), "usd_per_eur": {p: round(fx[p], 4) for p in P}},
       "sectors": {}}
for sector, codes in SECTORS.items():
    for cn in codes.split("+"):
        s = series.get((sector, cn), {})
        out["sectors"].setdefault(sector, []).append({
            "cn": cn, "label": clean(labels.get(cn, "")), **({"src": "census"} if cn == H2_CN else {}),
            "eur": [round(s.get(p, {}).get("eur", 0)) for p in P],
            "t": [round(s.get(p, {}).get("t", 0), 1) for p in P],
        })
OUT.write_text(json.dumps(out, separators=(",", ":")))
print(f"Wrote {OUT} ({P[0]} to {P[-1]}, {len(all_codes)} CN codes)", file=sys.stderr)
