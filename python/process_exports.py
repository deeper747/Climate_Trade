import pandas as pd
import os

df = pd.read_csv("data/raw/us_exports_hard_to_abate_comtrade_v1_raw.csv")

# Drop any World aggregate rows if they appear
df = df[df["partnerDesc"].str.lower() != "world"].copy()

df["primaryValue"] = pd.to_numeric(df["primaryValue"], errors="coerce")

partner = (df.groupby(["period","sector","partnerDesc"], as_index=False)
             .agg(export_value_usd=("primaryValue","sum")))

partner["year_sector_total"] = partner.groupby(["period","sector"])["export_value_usd"].transform("sum")
partner["share"] = partner["export_value_usd"] / partner["year_sector_total"]

top3 = (partner.sort_values(["period","sector","export_value_usd"], ascending=[True, True, False])
               .groupby(["period","sector"], as_index=False)
               .head(3))

os.makedirs("data/processed", exist_ok=True)
top3.to_csv("data/processed/us_exports_hard_to_abate_top3_partners.csv", index=False)
print(top3.head(10))