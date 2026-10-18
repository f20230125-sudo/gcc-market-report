"""The monthly market report's tables, from the central database.

    python -m gr.analyse        (writes data/marts/*.csv)

- class_position: every product in the classes MSD competes in, with price per unit in SAR and USD, whether it
  is MSD's, an originator brand or a generic/other, and its price against the class median.
- generic_pressure: for each MSD molecule, how many other products of the same molecule are registered and how
  far below MSD's price the cheapest one is.
- reference_pricing: MSD's oral brands, Saudi public price per tablet against the US pharmacy acquisition cost
  (NADAC) per tablet from Drug Price Watch.

Price per unit is the pack's public price over its pack size (a tablet, a capsule, a vial or a pre-filled pen).
The Saudi riyal is pegged at 3.75 to the US dollar; the rate is an input, not a lookup.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "warehouse" / "gcc.duckdb"
MARTS = ROOT / "data" / "marts"
REF = ROOT / "data" / "ref"
SAR_PER_USD = 3.75

# Originator brands by ingredient keyword. A product of the same molecule under another name is counted as a
# generic or other version. Written by hand; a test checks every MSD brand is here.
ORIGINATORS = {
    "SITAGLIPTIN": ["JANUVIA", "JANUMET"], "VILDAGLIPTIN": ["GALVUS"], "LINAGLIPTIN": ["TRAJENTA", "JENTADUETO"],
    "SAXAGLIPTIN": ["ONGLYZA", "KOMBIGLYZE"], "ALOGLIPTIN": ["VIPIDIA", "VIPDOMET"], "ERTUGLIFLOZIN": ["STEGLATRO", "SEGLUROMET", "STEGLUJAN"],
    "EMPAGLIFLOZIN": ["JARDIANCE", "SYNJARDY", "GLYXAMBI"], "DAPAGLIFLOZIN": ["FORXIGA", "XIGDUO", "QTERN"], "CANAGLIFLOZIN": ["INVOKANA", "VOKANAMET"],
    "PEMBROLIZUMAB": ["KEYTRUDA"], "NIVOLUMAB": ["OPDIVO"], "ATEZOLIZUMAB": ["TECENTRIQ"], "DURVALUMAB": ["IMFINZI"], "CEMIPLIMAB": ["LIBTAYO"],
    "DOSTARLIMAB": ["JEMPERLI"], "PAPILLOMA": ["GARDASIL", "CERVARIX"], "RALTEGRAVIR": ["ISENTRESS"], "DOLUTEGRAVIR": ["TIVICAY", "TRIUMEQ", "DOVATO", "JULUCA"],
    "BICTEGRAVIR": ["BIKTARVY"], "DORAVIRINE": ["PIFELTRO", "DELSTRIGO"], "LETERMOVIR": ["PREVYMIS"], "SUGAMMADEX": ["BRIDION"],
    "FIDAXOMICIN": ["DIFICID", "DIFICLIR"], "CEFTOLOZANE": ["ZERBAXA"], "AVIBACTAM": ["ZAVICEFTA"], "RELEBACTAM": ["RECARBRIO"], "BELZUTIFAN": ["WELIREG"],
    "SOTATERCEPT": ["WINREVAIR"], "SUVOREXANT": ["BELSOMRA"], "LEMBOREXANT": ["DAYVIGO"], "DARIDOREXANT": ["QUVIVIQ"], "VERICIGUAT": ["VERQUVO"],
    "APREPITANT": ["EMEND"], "NETUPITANT": ["AKYNZEO"], "TEDIZOLID": ["SIVEXTRO"], "PNEUMOCOCC": ["PREVENAR", "VAXNEUVANCE", "PNEUMOVAX", "CAPVAXIVE", "SYNFLORIX"],
    "ROTAVIRUS": ["ROTATEQ", "ROTARIX"],
}
MSD_RE = re.compile(r"MERCK SHARP|\bMSD\b", re.I)
# The class each MSD brand competes in, named for the report. ATC codes come from SFDA's own detail pages.
CLASS_NAMES = {
    "A10BH": "DPP-4 inhibitors", "A10BD": "Diabetes combinations", "A10BK": "SGLT2 inhibitors", "L01FF": "PD-1 / PD-L1 antibodies",
    "J07BM": "HPV vaccines", "J07AL": "Pneumococcal vaccines", "J07BH": "Rotavirus vaccines", "J07BC": "Hepatitis B vaccines",
    "J07BD": "Measles, mumps and rubella vaccines", "J07BK": "Varicella and zoster vaccines", "J05AJ": "HIV integrase inhibitors",
    "J05AR": "HIV combinations", "J05AG": "HIV NNRTIs", "J05AX": "Other antivirals", "V03AB": "Antidotes", "A07AA": "Intestinal anti-infectives",
    "J01DI": "Other cephalosporins", "J01DH": "Carbapenems", "L01XX": "Other antineoplastics", "C02KX": "Pulmonary hypertension",
    "N05CJ": "Orexin receptor antagonists", "C01DX": "Other cardiac vasodilators", "A04AD": "Other antiemetics", "J01XX": "Other antibacterials",
}


def ingredient_key(sci: str) -> str | None:
    s = (sci or "").upper()
    for k in ORIGINATORS:
        if k in s:
            return k
    return None


def role(trade: str, sci: str, company: str | None) -> str:
    if company and MSD_RE.search(company):
        return "MSD"
    key = ingredient_key(sci)
    t = (trade or "").upper()
    if key and any(t.startswith(o) or f" {o}" in f" {t}" for o in ORIGINATORS[key]):
        return "Originator"
    return "Generic or other"


def class_position(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    d = con.execute("select * from sfda_detail where status is null or status ilike 'valid%'").df()
    d["atc5"] = d.atc.fillna("").str[:5]
    d["class"] = d.atc5.map(CLASS_NAMES).fillna("")
    d["ingredient"] = d.sci.map(ingredient_key)
    d["role"] = [role(t, s, c) for t, s, c in zip(d.trade, d.sci, d.marketing_company)]
    # Vaccines are named too many ways to match by text ("G1 REASSORTANT..." is RotaTeq), so they are grouped by
    # their ATC class, and a competing vaccine is another company's brand, not a generic.
    vac = d.atc5.str.startswith("J07")
    d.loc[vac, "ingredient"] = d.loc[vac, "atc5"].map(CLASS_NAMES).fillna(d.loc[vac, "atc5"])
    d.loc[vac & (d.role != "MSD"), "role"] = "Originator"
    d["price_per_unit_sar"] = d.price_sar / d.pack_size.where(d.pack_size > 0)
    d["price_per_unit_usd"] = d.price_per_unit_sar / SAR_PER_USD
    med = d.groupby("atc5").price_per_unit_sar.transform("median")
    d["vs_class_median"] = d.price_per_unit_sar / med - 1
    cols = ["atc5", "class", "ingredient", "trade", "sci", "strength", "strength_unit", "form", "pack_size", "price_sar", "price_per_unit_sar", "price_per_unit_usd",
            "vs_class_median", "role", "marketing_company", "agent", "reg_no", "found_by"]
    return d[cols].sort_values(["atc5", "ingredient", "price_per_unit_sar"])


def generic_pressure(cp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    msd = cp[cp.role == "MSD"]
    for ing, m in msd.groupby("ingredient"):
        same = cp[(cp.ingredient == ing) & (cp.role != "MSD")]
        gens = same[same.role == "Generic or other"]
        msd_min = m.price_per_unit_sar.min()
        cheapest = gens.price_per_unit_sar.min() if len(gens) else None
        rows.append({
            "ingredient": ing,
            "msd_products": "; ".join(sorted(set(m.trade))),
            "msd_lowest_price_per_unit_sar": msd_min,
            "other_versions": len(same),
            "generic_or_other": len(gens),
            "generic_companies": gens.marketing_company.nunique(),
            "cheapest_generic_per_unit_sar": cheapest,
            "cheapest_vs_msd": (cheapest / msd_min - 1) if cheapest and msd_min else None,
            "other_brands": int((same.role == "Originator").sum()),
            "other_brand_names": "; ".join(sorted(set(same[same.role == "Originator"].trade.str.split().str[0].str.upper()))),
            "cheapest_other_brand_per_unit_sar": same[same.role == "Originator"].price_per_unit_sar.min() if (same.role == "Originator").any() else None,
        })
    return pd.DataFrame(rows).sort_values("generic_or_other", ascending=False)


def reference_pricing(cp: pd.DataFrame) -> pd.DataFrame:
    """Saudi price per tablet for MSD's oral brands against the US NADAC per tablet, for the same pack the US mart names."""
    us = pd.read_csv(REF / "us_nadac_msd.csv", keep_default_na=False)
    us = us[us.in_nadac.astype(str).str.lower() == "true"]
    rows = []
    def us_numbers(s: str) -> list[float]:
        # US names write components with hyphens and thousands with commas: "50-1,000".
        return [float(x.replace(",", "")) for x in s.split("-") if re.search(r"\d", x)]

    def ksa_numbers(s: str) -> list[float]:
        # SFDA writes components with commas and no thousands separator: "1000,50".
        return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]

    for r in us.itertuples():
        m = re.search(r"([\d,.\-]+)\s*MG", r.pack)
        want = us_numbers(m.group(1)) if m else []
        xr = " XR" in r.pack.upper()
        cand = cp[(cp.role == "MSD") & cp.trade.str.upper().str.startswith(r.family) & cp.form.str.contains("tablet", case=False, na=False)].copy()
        # Same number of active ingredients, the MSD molecule's strength (the first in the US name) present, the
        # same release form; then the most strengths in common. Delstrigo's tenofovir is written 300 mg in the
        # US and 245 mg in Saudi Arabia (salt against base), so only the first strength must match exactly.
        cand["nums"] = cand.strength.astype(str).map(ksa_numbers)
        keep = [
            (cand.nums.map(len) == len(want)) if want else (cand.nums.map(len) >= 0),
            cand.nums.map(lambda n: bool(want) and want[0] in n) if want else (cand.nums.map(len) >= 0),
            cand.trade.str.upper().str.contains(" XR") == xr,
        ]
        for k in keep:
            cand = cand[k.reindex(cand.index).fillna(False).astype(bool)] if len(cand) else cand
        if cand.empty:
            rows.append({"brand": r.family, "us_pack": r.pack, "us_nadac_per_tablet_usd": float(r.price_latest), "ksa_product": "no same-strength tablet in the SFDA list", "ksa_per_tablet_usd": None, "us_vs_ksa": None})
            continue
        cand["overlap"] = cand.nums.map(lambda n: len(set(n) & set(want)))
        k = cand.sort_values(["overlap", "price_per_unit_sar"], ascending=[False, True]).iloc[0]
        rows.append({
            "brand": r.family,
            "us_pack": r.pack,
            "us_nadac_per_tablet_usd": float(r.price_latest),
            "ksa_product": f"{k.trade} ({k.strength}{k.strength_unit or ''}, pack of {int(k.pack_size) if k.pack_size == k.pack_size else '?'})",
            "ksa_per_tablet_usd": k.price_per_unit_usd,
            "us_vs_ksa": float(r.price_latest) / k.price_per_unit_usd if k.price_per_unit_usd else None,
        })
    return pd.DataFrame(rows)


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    cp = class_position(con)
    snap = con.execute("select max(snapshot) from sfda_list").fetchone()[0]
    total = con.execute("select count(*) from sfda_list").fetchone()[0]
    con.close()
    gp = generic_pressure(cp)
    rp = reference_pricing(cp)
    MARTS.mkdir(parents=True, exist_ok=True)
    cp.to_csv(MARTS / "class_position.csv", index=False)
    gp.to_csv(MARTS / "generic_pressure.csv", index=False)
    rp.to_csv(MARTS / "reference_pricing.csv", index=False)
    with (MARTS / "headline.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "value"])
        w.writerow(["snapshot", snap])
        w.writerow(["products_in_list", total])
        w.writerow(["followed_products", len(cp)])
        w.writerow(["followed_classes", cp.atc5.nunique()])
        w.writerow(["msd_products", int((cp.role == "MSD").sum())])
        w.writerow(["msd_molecules", gp.ingredient.nunique()])
        w.writerow(["sar_per_usd", SAR_PER_USD])
    print(f"{len(cp)} followed products in {cp.atc5.nunique()} classes; MSD products {(cp.role == 'MSD').sum()}")
    print(gp.to_string(index=False))
    print(rp.to_string(index=False))


if __name__ == "__main__":
    main()
