"""Cross-country tables: Saudi Arabia and Bahrain on one classification.

    python -m gr.gcc        (after gr.stage, gr.analyse and gr.bahrain; writes data/marts/gcc_*.csv and bahrain_changes.csv)

- gcc_products: every followed product in both countries, price per unit in local currency and in US dollars.
- gcc_msd_prices: each MSD product registered in both countries, matched on brand, strengths and release form,
  with the price per unit in each and Saudi against Bahrain.
- gcc_competition: per country and MSD molecule (or vaccine class): other versions, generics, the cheapest
  generic against MSD's price.
- bahrain_changes: Bahrain retail prices on 18 February 2024 against 7 September 2026, matched on registration number.
- reference_pricing (rewritten): the US pharmacy cost per tablet against Saudi Arabia and Bahrain.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from gr.analyse import SAR_PER_USD
from gr.bahrain import BHD_PER_USD

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "warehouse" / "gcc.duckdb"
MARTS = ROOT / "data" / "marts"
REF = ROOT / "data" / "ref"


def strengths(s: str) -> tuple[float, ...]:
    """Strength numbers as a sorted tuple: "1000/50", "1000,50" and "50-1,000" all give (50.0, 1000.0)."""
    s = str(s or "")
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s) if "-" in s else s  # US names write thousands with a comma
    return tuple(sorted(float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)))


def form_group(form: str) -> str:
    f = str(form or "").upper()
    if any(w in f for w in ("TABLET", "CAPSULE")):
        return "oral solid"
    if any(w in f for w in ("INJECTION", "INFUSION", "CONCENTRATE", "POWDER FOR", "SUSPENSION FOR INJ", "SYRINGE")):
        return "injectable"
    return f.split()[0].lower() if f else ""


# Brand spellings that differ between the registers: Bahrain writes "KETRUDA SC" for subcutaneous Keytruda, and the
# MMR vaccine is "M.M.R II" in Saudi Arabia and "M-M-R II" in Bahrain.
BRAND_SPELLINGS = {"KETRUDA": "KEYTRUDA", "M.M.R": "M-M-R II", "M M R": "M-M-R II"}


def brand(name: str) -> str:
    raw = str(name or "").upper()
    if raw.startswith(("M.M.R", "M-M-R", "M M R")):
        return "M-M-R II"
    n = raw.replace("-", " ")
    words = n.split()
    if not words:
        return ""
    # Two-word brands that are not a strength or a form: "JANUMET XR", "GARDASIL 9", "PNEUMOVAX 23", "M M R".
    first = BRAND_SPELLINGS.get(words[0], words[0])
    if len(words) > 1 and words[1] in {"XR", "9", "23", "SC"}:
        return f"{first} {words[1]}"
    return first


def products(con) -> pd.DataFrame:
    sa = pd.read_csv(MARTS / "class_position.csv", keep_default_na=False)
    sa = pd.DataFrame({
        "country": "Saudi Arabia", "atc5": sa.atc5, "class": sa["class"], "ingredient": sa.ingredient, "name": sa.trade, "brand": sa.trade.map(brand),
        "strength": sa.strength.astype(str), "form": sa.form, "units_per_pack": sa.pack_size, "price_local": sa.price_sar, "currency": "SAR",
        "price_per_unit_local": sa.price_per_unit_sar, "price_per_unit_usd": sa.price_per_unit_usd, "role": sa.role, "company": sa.marketing_company, "reg_no": sa.reg_no.astype(str),
    })
    bh = con.execute("select * from bh_list where ingredient is not null").df()
    bh_units = bh.units_per_pack.where(bh.units_per_pack > 0)
    bh = pd.DataFrame({
        "country": "Bahrain", "atc5": bh.atc5.fillna(""), "class": "", "ingredient": bh.ingredient, "name": bh.name, "brand": bh.name.map(brand),
        "strength": bh.strength.fillna("").astype(str), "form": bh.form.fillna(""), "units_per_pack": bh.units_per_pack, "price_local": bh.price_bhd, "currency": "BHD",
        "price_per_unit_local": bh.price_bhd / bh_units, "price_per_unit_usd": bh.price_bhd / bh_units / BHD_PER_USD, "role": bh.role, "company": bh.mah, "reg_no": bh.reg_no, "pack_raw": bh.pack_raw,
    })
    names = dict(zip(sa.atc5, sa["class"]))
    bh["class"] = bh.atc5.map(names).fillna("")
    out = pd.concat([sa, bh], ignore_index=True)
    out["pid"] = range(len(out))  # row id; the workbook's Products sheet holds product pid on row pid + 2
    return out


def msd_prices(p: pd.DataFrame) -> pd.DataFrame:
    m = p[p.role == "MSD"].copy()
    m["key_strength"] = m.strength.map(strengths)
    m["xr"] = m.name.str.upper().str.contains(r"\bXR\b|EXTENDED", regex=True) | m.form.str.upper().str.contains("EXTENDED")
    m["fg"] = m.form.map(form_group)
    m = m[((m.key_strength.map(len) > 0) | m.ingredient.str.endswith("vaccines")) & m.price_per_unit_usd.notna()]
    # A product is the same in both countries when brand, strengths, form, release and units per pack all agree.
    # Vaccines are compared per dose on the brand alone: their strengths are often blank and packs hold 1 or 10 doses.
    vac = m.ingredient.str.endswith("vaccines")
    m["key"] = [(b, "vaccine") if v else (b, k, f, x, u) for b, k, f, x, u, v in zip(m.brand, m.key_strength, m.fg, m.xr, m.units_per_pack, vac)]
    sa, bh = m[m.country == "Saudi Arabia"], m[m.country == "Bahrain"]
    rows = []
    for key, s_grp in sa.groupby("key"):
        b_grp = bh[bh.key == key]
        if b_grp.empty:
            continue
        s, b = s_grp.iloc[0], b_grp.iloc[0]
        base = {"brand": s.brand, "strength": s.strength, "form": s.form, "ingredient": s.ingredient, "units_per_pack": int(s.units_per_pack)}
        # Two packs on either side that agree on everything recorded (Bridion 2 ml and 5 ml vials, whose volume SFDA's
        # list does not give) are not compared: which one corresponds to which cannot be known from the data.
        if len(s_grp) > 1 or len(b_grp) > 1:
            rows.append({**base, "saudi_pack": "; ".join(s_grp["name"]), "saudi_per_unit_usd": None, "bahrain_pack": "; ".join(b_grp["name"] + " " + b_grp.pack_raw.fillna("")), "bahrain_per_unit_usd": None,
                         "saudi_vs_bahrain": None, "note": f"not compared: {len(s_grp)} Saudi and {len(b_grp)} Bahrain packs agree on every recorded field"})
            continue
        rows.append({**base, "saudi_pid": int(s.pid), "bahrain_pid": int(b.pid), "saudi_pack": s["name"], "saudi_per_unit_usd": s.price_per_unit_usd, "bahrain_pack": f"{b['name']} {b.pack_raw}", "bahrain_per_unit_usd": b.price_per_unit_usd,
                     "saudi_vs_bahrain": s.price_per_unit_usd / b.price_per_unit_usd - 1, "note": ""})
    return pd.DataFrame(rows).sort_values(["ingredient", "brand", "strength"])


def competition(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country, c in p.groupby("country"):
        for ing, d in c.groupby("ingredient"):
            msd = d[d.role == "MSD"]
            if msd.empty:
                continue
            gen = d[d.role == "Generic or other"]
            other = d[d.role == "Originator"]
            m = msd.price_per_unit_usd.min()
            rows.append({
                "country": country, "ingredient": ing, "msd_products": int(len(msd)), "msd_lowest_per_unit_usd": m,
                "other_brands": int(len(other)), "generic_or_other": int(len(gen)), "generic_companies": int(gen.company.nunique()),
                "cheapest_generic_per_unit_usd": gen.price_per_unit_usd.min() if len(gen) else None,
                "cheapest_generic_vs_msd": (gen.price_per_unit_usd.min() / m - 1) if len(gen) and m == m else None,
            })
    return pd.DataFrame(rows).sort_values(["ingredient", "country"])


def bahrain_changes(con) -> pd.DataFrame:
    now = con.execute("select reg_no, name, strength, pack_raw, price_bhd, ingredient, mah from bh_list").df()
    old = con.execute("select reg_no, name as name_2024, price_bhd_2024, list from bh_list_2024").df()
    # A registration can hold several packs in 2026; the 2024 lists hold one row each. Match on registration and keep
    # the 2026 pack whose price is closest, so a new pack size is not read as a price change.
    j = old.merge(now, on="reg_no", how="inner")
    j["change"] = j.price_bhd / j.price_bhd_2024 - 1
    j = j.loc[j.groupby("reg_no").change.apply(lambda s: s.abs().idxmin())]
    return j.sort_values("change")


def reference(p: pd.DataFrame) -> pd.DataFrame:
    us = pd.read_csv(REF / "us_nadac_msd.csv", keep_default_na=False)
    us = us[us.in_nadac.astype(str).str.lower() == "true"]
    tabs = p[(p.role == "MSD") & p.form.str.upper().str.contains("TABLET")].copy()
    tabs["key_strength"] = tabs.strength.map(strengths)
    tabs["xr"] = tabs.name.str.upper().str.contains(r"\bXR\b", regex=True) | tabs.form.str.upper().str.contains("EXTENDED")
    rows = []
    for r in us.itertuples():
        m = re.search(r"([\d,.\-]+)\s*MG", r.pack)
        want = strengths(m.group(1)) if m else ()
        xr = " XR" in r.pack.upper()
        out = {"brand": r.family, "us_pack": r.pack, "us_nadac_per_tablet_usd": float(r.price_latest)}
        for country, col in (("Saudi Arabia", "saudi"), ("Bahrain", "bahrain")):
            c = tabs[(tabs.country == country) & (tabs.brand == r.family) & (tabs.xr == xr)]
            # Same strengths; Delstrigo's tenofovir is 300 mg in the US and 245 mg (base) in Saudi Arabia, so a
            # three-part strength may differ in its last part.
            exact = c[c.key_strength == want]
            if exact.empty and len(want) == 3:
                exact = c[c.key_strength.map(lambda k: len(k) == 3 and k[:2] == want[:2] or (len(k) == 3 and set(want) - set(k) <= {300.0}))]
            if exact.empty:
                out[f"{col}_product"] = "no same-strength tablet"
                out[f"{col}_per_tablet_usd"] = None
                out[f"us_vs_{col}"] = None
            else:
                k = exact.sort_values("price_per_unit_usd").iloc[0]
                out[f"{col}_product"] = f"{k['name']} {k.strength} x{int(k.units_per_pack)}"
                out[f"{col}_pid"] = int(k.pid)
                out[f"{col}_per_tablet_usd"] = k.price_per_unit_usd
                out[f"us_vs_{col}"] = float(r.price_latest) / k.price_per_unit_usd
        rows.append(out)
    return pd.DataFrame(rows)


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    p = products(con)
    ch = bahrain_changes(con)
    con.close()
    mp = msd_prices(p)
    comp = competition(p)
    ref = reference(p)
    p.to_csv(MARTS / "gcc_products.csv", index=False)
    mp.to_csv(MARTS / "gcc_msd_prices.csv", index=False)
    comp.to_csv(MARTS / "gcc_competition.csv", index=False)
    ch.to_csv(MARTS / "bahrain_changes.csv", index=False)
    ref.to_csv(MARTS / "reference_pricing.csv", index=False)
    print(f"products: {len(p)} ({p.country.value_counts().to_dict()}); MSD matched in both countries: {len(mp)}")
    print(mp[["brand", "strength", "saudi_per_unit_usd", "bahrain_per_unit_usd", "saudi_vs_bahrain"]].to_string(index=False))
    print(ref.to_string(index=False))
    print(f"Bahrain 2024->2026 matched: {len(ch)}; cut {int((ch.change < -0.005).sum())}, raised {int((ch.change > 0.005).sum())}, same {int((ch.change.abs() <= 0.005).sum())}; median {ch.change.median():+.1%}")


if __name__ == "__main__":
    main()
