"""Writes the one JSON file the web report reads, and copies the Excel pack next to it for download.

    python -m gr.export_json      (writes site/public/data/report.json and site/public/downloads/GCC-Market-Report.xlsx)

Every number on the page comes from this file, and this file only from the marts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "site" / "public" / "data"
DL = ROOT / "site" / "public" / "downloads"
UNCHANGED = 0.005  # a 2024-to-2026 price within half a percent counts as unchanged


def num(v, n: int = 4):
    return None if v is None or v != v else round(float(v), n)


def records(df: pd.DataFrame, cols: dict[str, str]) -> list[dict]:
    out = []
    for row in df.to_dict("records"):
        out.append({k: (num(row[c]) if isinstance(row[c], float) else (int(row[c]) if hasattr(row[c], "item") and not isinstance(row[c], str) else row[c])) for k, c in cols.items()})
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DL.mkdir(parents=True, exist_ok=True)
    head = dict(pd.read_csv(MARTS / "headline.csv").values)
    p = pd.read_csv(MARTS / "gcc_products.csv", keep_default_na=False)
    comp = pd.read_csv(MARTS / "gcc_competition.csv")
    mp = pd.read_csv(MARTS / "gcc_msd_prices.csv", keep_default_na=False)
    for c in ("saudi_per_unit_usd", "bahrain_per_unit_usd", "saudi_vs_bahrain"):
        mp[c] = pd.to_numeric(mp[c], errors="coerce")
    rp = pd.read_csv(MARTS / "reference_pricing.csv")
    ch = pd.read_csv(MARTS / "bahrain_changes.csv", keep_default_na=False)
    ch["change"] = ch.change.astype(float)
    v_sa = pd.read_csv(MARTS / "validation.csv", keep_default_na=False)
    v_bh = pd.read_csv(MARTS / "validation_bahrain.csv", keep_default_na=False)
    bh_rows = int(v_bh[v_bh.id == "B01"].result.iloc[0].replace(",", ""))

    countries = []
    for c, d in p.groupby("country"):
        countries.append({
            "country": c,
            "products": len(d),
            "msd": int((d.role == "MSD").sum()),
            "generic": int((d.role == "Generic or other").sum()),
            "otherBrands": int((d.role == "Originator").sum()),
            "companies": int(d[d.company != ""].company.nunique()),
        })

    compared = mp.dropna(subset=["saudi_vs_bahrain"])  # each row is one pack matched one to one (Winrevair's 1- and 2-vial kits are separate packs)
    moved = ch[ch.change.abs() > UNCHANGED].sort_values("change")
    report = {
        "snapshots": {"saudi": head["snapshot"], "bahrain": "2026-09-07", "bahrain2024": "2024-02-18"},
        "sources": {"saudiProducts": int(head["products_in_list"]), "saudiDetailed": int(head["followed_products"]), "bahrainProducts": bh_rows},
        "rates": {"sarPerUsd": 3.75, "bhdPerUsd": 0.376},
        "countries": countries,
        "competition": records(comp.sort_values(["ingredient", "country"]), {
            "country": "country", "ingredient": "ingredient", "msdProducts": "msd_products", "msdLowest": "msd_lowest_per_unit_usd",
            "otherBrands": "other_brands", "generic": "generic_or_other", "genericCompanies": "generic_companies",
            "cheapestGeneric": "cheapest_generic_per_unit_usd", "discount": "cheapest_generic_vs_msd"}),
        "msdPrices": records(mp, {"brand": "brand", "strength": "strength", "form": "form", "ingredient": "ingredient", "units": "units_per_pack", "saudi": "saudi_per_unit_usd",
                                  "bahrain": "bahrain_per_unit_usd", "saudiVsBahrain": "saudi_vs_bahrain", "note": "note"}),
        "compared": len(compared),
        "comparedCheaperInSaudi": int((compared.saudi_vs_bahrain < 0).sum()),
        "comparedMedian": num(compared.saudi_vs_bahrain.median()),
        "reference": records(rp, {"brand": "brand", "usPack": "us_pack", "us": "us_nadac_per_tablet_usd", "saudiProduct": "saudi_product", "saudi": "saudi_per_tablet_usd",
                                  "usVsSaudi": "us_vs_saudi", "bahrainProduct": "bahrain_product", "bahrain": "bahrain_per_tablet_usd", "usVsBahrain": "us_vs_bahrain"}),
        "bahrainChanges": {
            "matched": len(ch),
            "unchanged": int((ch.change.abs() <= UNCHANGED).sum()),
            "rose": int((ch.change > UNCHANGED).sum()),
            "fell": int((ch.change < -UNCHANGED).sum()),
            "moved": records(moved, {"name": "name", "strength": "strength", "pack": "pack_raw", "before": "price_bhd_2024", "after": "price_bhd", "change": "change", "holder": "mah"}),
        },
        "validation": {
            "Saudi Arabia": records(v_sa, {"id": "id", "check": "check", "status": "status", "result": "result", "rule": "rule"}),
            "Bahrain": records(v_bh, {"id": "id", "check": "check", "status": "status", "result": "result", "rule": "rule"}),
        },
    }
    (OUT / "report.json").write_text(json.dumps(report, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(ROOT / "excel" / "GCC-Market-Report.xlsx", DL / "GCC-Market-Report.xlsx")
    print(f"wrote report.json: {len(report['competition'])} competition rows, {len(report['msdPrices'])} MSD price rows, "
          f"{report['compared']} products compared, {len(moved)} Bahrain price moves; copied the Excel pack")


if __name__ == "__main__":
    main()
