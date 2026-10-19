"""Compares the Power BI measures, evaluated with DAX in Power BI Desktop's own engine, with Python.

    powershell -File tools/check_powerbi_engine.ps1 -Pbip powerbi/GCCMarketReport.pbip -Out pbi.json
    python -m gr.check_powerbi pbi.json

Python recomputes each measure from the marts; every table must have loaded ("Ready") and every value must agree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"


def close(a, b, tol=1e-6) -> bool:
    blank = lambda v: v is None or (isinstance(v, float) and v != v)  # noqa: E731
    if blank(a) and blank(b):
        return True
    if blank(a) or blank(b):
        return False
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def main(path: str) -> None:
    res = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    problems: list[str] = []
    n = 0

    def check(label, got, exp):
        nonlocal n
        n += 1
        if not close(got, exp):
            problems.append(f"{label}: Power BI {got} vs Python {exp}")

    for t, p in res["partitions"].items():
        n += 1
        if p["state"] != "Ready" or p["error"]:
            problems.append(f"table {t}: {p['state']} {p['error']}")

    p = pd.read_csv(MARTS / "gcc_products.csv", keep_default_na=False)
    p["usd"] = pd.to_numeric(p.price_per_unit_usd, errors="coerce")
    comp = pd.read_csv(MARTS / "gcc_competition.csv")
    mp = pd.read_csv(MARTS / "gcc_msd_prices.csv")
    rp = pd.read_csv(MARTS / "reference_pricing.csv")
    ch = pd.read_csv(MARTS / "bahrain_changes.csv")
    v = {"Saudi Arabia": pd.read_csv(MARTS / "validation.csv"), "Bahrain": pd.read_csv(MARTS / "validation_bahrain.csv")}

    (counts,) = res["counts"]
    for label, got, exp in zip("pcgrbv", counts, [len(p), len(comp), len(mp), 2 * len(rp), len(ch), sum(len(x) for x in v.values())]):
        check(f"rows {label}", got, exp)

    for country, products, msd, gen, other, companies, median, checks, failed in res["by_country"]:
        d = p[p.country == country]
        for label, got, exp in (("products", products, len(d)), ("msd", msd, (d.role == "MSD").sum()), ("generic", gen, (d.role == "Generic or other").sum()),
                                ("other", other, (d.role == "Originator").sum()), ("companies", companies, d[d.company != ""].company.nunique()),
                                ("median", median, d.usd.median()), ("checks", checks, len(v[country])), ("failed", failed, (v[country].status == "fail").sum())):
            check(f"{country} {label}", got, exp)

    for country, ing, msd_low, gen_low, disc in res["by_ingredient"]:
        d = p[(p.country == country) & (p.ingredient == ing)]
        m = d[d.role == "MSD"].usd.min()
        g = d[d.role == "Generic or other"].usd.min()
        m = None if m != m else m
        g = None if g != g else g
        check(f"{country} {ing} msd low", msd_low, m)
        check(f"{country} {ing} generic low", gen_low, g)
        check(f"{country} {ing} discount", disc, (g / m - 1) if (g is not None and m) else None)

    (g,) = res["gcc"]
    compared = mp.saudi_vs_bahrain.dropna()
    exp = [len(compared), compared.median(), int((compared < 0).sum()),
           pd.concat([rp.us_vs_saudi, rp.us_vs_bahrain]).dropna().median(),
           len(ch), (ch.change.abs() <= 0.005).mean(), ch.change.median(), comp.generic_or_other.sum()]
    for label, got, e in zip(["compared", "median saudi vs bahrain", "saudi cheaper", "us over gcc", "matched", "share unchanged", "median change", "generic per molecule"], g, exp):
        check(label, got, e)

    if problems:
        print("\n".join(problems[:25]))
        raise SystemExit(f"{len(problems)} disagreements in {n} values")
    print(f"{n} Power BI values agree with Python; every table loaded")


if __name__ == "__main__":
    main(sys.argv[1])
