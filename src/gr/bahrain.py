"""Stage Bahrain's public medicine price lists (NHRA) into the central database, behind their own checks.

    python -m gr.bahrain        (after gr.stage; adds tables bh_list, bh_list_2024 and data/marts/validation_bahrain.csv)

Sources, downloaded from nhra.bh/OpenData/Licensed Medicines:
- the Registered Medicine Price List of 7 September 2026 (every registered product, retail price in Bahraini dinars);
- the Innovator and Generics price lists implemented on 18 February 2024, matched to 2026 on the registration number.

Bahrain's list has no ATC code. A product is classed through its active substance, using the class SFDA's own
detail pages give the same molecule in Saudi Arabia: the two countries are harmonised on one classification.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import duckdb
import pandas as pd

from gr.analyse import CLASS_NAMES, ORIGINATORS, ingredient_key

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "bahrain"
DB = ROOT / "data" / "warehouse" / "gcc.duckdb"
MARTS = ROOT / "data" / "marts"
CURRENT = RAW / "nhra_registered_price_list_2026-09-07.xlsx"
INNOVATOR_2024 = RAW / "nhra_innovator_price_list_2024-02-18.xlsx"
GENERICS_2024 = RAW / "nhra_generics_price_list_2024-02-18.xlsx"
BHD_PER_USD = 0.376  # the dinar's peg

# Vaccines by brand, since their active substances are written many ways or not at all.
VACCINE_BRANDS = {
    "GARDASIL": "HPV vaccines", "CERVARIX": "HPV vaccines", "ROTATEQ": "Rotavirus vaccines", "ROTARIX": "Rotavirus vaccines",
    "M-M-R": "Measles, mumps and rubella vaccines", "PRIORIX": "Measles, mumps and rubella vaccines", "PNEUMOVAX": "Pneumococcal vaccines",
    "VAXNEUVANCE": "Pneumococcal vaccines", "PREVENAR": "Pneumococcal vaccines", "CAPVAXIVE": "Pneumococcal vaccines", "SYNFLORIX": "Pneumococcal vaccines",
    "VARIVAX": "Varicella and zoster vaccines", "VARILRIX": "Varicella and zoster vaccines", "SHINGRIX": "Varicella and zoster vaccines",
    "RECOMBIVAX": "Hepatitis B vaccines", "ENGERIX": "Hepatitis B vaccines",
}
CLASS_OF_VACCINE = {v: k for k, v in CLASS_NAMES.items() if k.startswith("J07")}


def units_per_pack(raw: str | None) -> float | None:
    """How many units (tablets, vials, syringes) a pack holds, from Bahrain's free-text pack size.

    "30" -> 30; "10 X 2ML" -> 10; "1 + 1" (powder and solvent) -> 1; "3 (2 X 80MG + 1 X 125MG)" -> 3;
    "4ML", "0.5ML", "30G" (one container) -> 1. Anything else is unknown, not guessed.
    """
    if raw is None or (isinstance(raw, float) and raw != raw):
        return None
    s = str(raw).strip().upper()
    if re.fullmatch(r"\d+", s):
        return float(s)
    m = re.match(r"^(\d+)\s*(?:X|\(|\+)", s)
    if m:
        return float(m.group(1))
    if re.fullmatch(r"\d+(?:\.\d+)?\s*(ML|G|L|MG|GM)", s):
        return 1.0
    m = re.match(r"^(\d+)\s*(TABLETS?|TABS?|CAPSULES?|CAPS?|VIALS?|AMPOULES?|SACHETS?|PENS?|SYRINGES?)\b", s)
    if m:
        return float(m.group(1))
    return None


def vaccine_class(name: str) -> str | None:
    n = (name or "").upper()
    for b, c in VACCINE_BRANDS.items():
        if n.startswith(b):
            return c
    return None


def classify(name: str, active: str, mah: str, atc_of_ingredient: dict[str, str]) -> tuple[str | None, str | None, str]:
    """(ingredient group, ATC class, role) for one Bahrain product."""
    vac = vaccine_class(name)
    msd = bool(re.search(r"MERCK SHARP|\bMSD\b", mah or "", re.I))
    if vac:
        return vac, CLASS_OF_VACCINE.get(vac), "MSD" if msd else "Originator"
    ing = ingredient_key(active or "")
    if ing is None:
        return None, None, "MSD" if msd else "Generic or other"
    atc = atc_of_ingredient.get(ing)
    if msd:
        return ing, atc, "MSD"
    n = (name or "").upper()
    if any(n.startswith(o) for o in ORIGINATORS[ing]):
        return ing, atc, "Originator"
    return ing, atc, "Generic or other"


def read_current() -> pd.DataFrame:
    d = pd.read_excel(CURRENT, dtype=str)
    d.columns = [re.sub(r"\s+", " ", c).strip() for c in d.columns]
    return d.dropna(how="all")


def read_2024() -> pd.DataFrame:
    inn = pd.read_excel(INNOVATOR_2024, dtype=str, header=1)
    inn = inn.rename(columns=lambda c: re.sub(r"\s+", " ", str(c)).strip())
    inn = pd.DataFrame({"reg_no": inn["Drug Registration Number"], "name": inn["Brand name"], "price_bhd_2024": inn["Retail Price (BD)"], "list": "innovator"})
    gen = pd.read_excel(GENERICS_2024, dtype=str, header=4)
    gen = gen.rename(columns=lambda c: re.sub(r"\s+", " ", str(c)).strip())
    gen = pd.DataFrame({"reg_no": gen["Drug Registration NO"], "name": gen["Trade Name"], "price_bhd_2024": gen["New Retail Price BD"], "list": "generics"})
    out = pd.concat([inn, gen], ignore_index=True)
    out = out[out.reg_no.fillna("").str.match(r"^\s*DRN-")]
    out["reg_no"] = out.reg_no.str.strip()
    out["price_bhd_2024"] = pd.to_numeric(out.price_bhd_2024.str.replace(",", ""), errors="coerce")
    return out


def main() -> None:
    con = duckdb.connect(str(DB))
    atc_rows = con.execute(
        "select sci, substr(atc, 1, 5) as atc5, count(*) n from sfda_detail where atc is not null group by 1, 2"
    ).fetchall()
    votes: dict[str, dict[str, int]] = {}
    for sci, atc5, n in atc_rows:
        k = ingredient_key(sci)
        if k:
            votes.setdefault(k, {}).setdefault(atc5, 0)
            votes[k][atc5] += n
    # The class most Saudi products of that molecule carry (combinations can sit in a combination class).
    atc_of = {k: max(v, key=v.get) for k, v in votes.items()}

    d = read_current()
    checks: list[dict] = []

    def add(cid, name, status, result, rule):
        checks.append({"id": cid, "check": name, "status": status, "result": result, "rule": rule})

    n_rows = len(d)
    add("B01", "Rows read from the 2026 list", "info", f"{n_rows:,}", "every non-empty row of the sheet")
    reg_ok = d["DRUG REGISTRATION NUMBER"].fillna("").str.match(r"^DRN-\d{5}/\d{2}$")
    add("B02", "Registration numbers have the DRN-nnnnn/yy form", "pass" if reg_ok.mean() > 0.99 else "warn", f"{(~reg_ok).sum()} do not", "at least 99%")
    price = pd.to_numeric(d["RETAIL PRICE BD"].fillna("").str.replace(",", ""), errors="coerce")
    add("B03", "Every product has a positive retail price", "pass" if (price > 0).all() else "warn", f"{(~(price > 0)).sum()} without", "price > 0 BD")
    dup = d.duplicated(["DRUG REGISTRATION NUMBER", "PACK SIZE"], keep=False)
    add("B04", "A registration number and pack size appear once", "pass" if not dup.any() else "warn", f"{dup.sum()} rows share one", "one row per registration and pack")
    upp = d["PACK SIZE"].map(units_per_pack)
    add("B05", "Units per pack read from the pack-size text", "pass" if upp.notna().mean() >= 0.9 else "warn", f"{upp.notna().sum():,} of {n_rows:,} ({upp.notna().mean():.1%})", "at least 90%; the rest stay unknown, not guessed")

    rows = []
    for (_, r), u, p in zip(d.iterrows(), upp, price):
        ing, atc5, role = classify(r.get("MEDICINE NAME"), r.get("ACTIVE SUBSTANCES"), r.get("MAH NAME"), atc_of)
        rows.append((
            "2026-09-07", r.get("DRUG REGISTRATION NUMBER"), r.get("MEDICINE NAME"), r.get("STRENGTH"), r.get("UNIT OF STRENGTH"), r.get("PHARMACEUTICAL FORM"),
            r.get("PACK SIZE"), u, r.get("ROUTE OF ADMINISTRATION"), r.get("PRODUCT TYPE"), r.get("ACTIVE SUBSTANCES"), p, r.get("AGENT NAME"), r.get("MAH NAME"),
            ing, atc5, role,
        ))
    con.execute(
        """create or replace table bh_list (snapshot date, reg_no varchar, name varchar, strength varchar, strength_unit varchar, form varchar,
        pack_raw varchar, units_per_pack double, route varchar, product_type varchar, active varchar, price_bhd double, agent varchar,
        mah varchar, ingredient varchar, atc5 varchar, role varchar)"""
    )
    con.executemany("insert into bh_list values (" + ",".join(["?"] * 17) + ")", rows)
    followed = sum(1 for x in rows if x[14])
    msd = sum(1 for x in rows if x[16] == "MSD")
    no_class = sorted({x[14] for x in rows if x[14] and not x[15] and not x[14].endswith("vaccines")})
    add("B06", "Products in the followed molecules and vaccine classes", "info", f"{followed} (MSD {msd})", "matched by active substance or vaccine brand")
    fixed = sum(1 for x in rows if x[10] and any(w.strip() in str(x[10]).upper() for w in __import__("gr.analyse", fromlist=["SPELLINGS"]).SPELLINGS))
    add("B10", "Active substances matched only after a spelling fix", "info", f"{fixed} (e.g. DORAVIRIN, TINOFOVIR)", "spelling variants listed in gr.analyse.SPELLINGS")
    outside = sorted({str(x[2]) for x in rows if x[16] == "MSD" and not x[14]})
    add("B11", "MSD products in Bahrain outside the followed classes", "info", f"{len(outside)}: {', '.join(outside)}", "not compared: no Saudi detail pages for these molecules")
    add("B07", "Followed molecules given an ATC class from the Saudi data", "pass" if not no_class else "warn", f"without a class: {', '.join(no_class) or 'none'}", "every followed molecule classed")

    old = read_2024()
    con.execute("create or replace table bh_list_2024 as select * from old")
    matched = old.reg_no.isin(set(d["DRUG REGISTRATION NUMBER"]))
    add("B08", "2024 price-list entries found in the 2026 list", "info", f"{matched.sum():,} of {len(old):,} ({matched.mean():.1%})", "matched on the registration number; the rest were cancelled or renumbered")
    n_bh = con.execute("select count(*) from bh_list").fetchone()[0]
    add("B09", "Database holds every staged Bahrain row", "pass" if n_bh == n_rows else "fail", f"{n_bh:,}", "rows in = rows loaded")
    con.close()

    with (MARTS / "validation_bahrain.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0]))
        w.writeheader()
        w.writerows(checks)
    for c in checks:
        print(f"{c['id']} {c['status']:5} {c['check']}: {c['result']}")
    if any(c["status"] == "fail" for c in checks):
        raise SystemExit("Bahrain validation failed")


if __name__ == "__main__":
    main()
