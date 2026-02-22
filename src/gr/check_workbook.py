"""Compares the workbook's formula results, recalculated by Excel, with Python's own calculation.

    powershell -File tools/check_workbook.ps1 -Path excel/GCC-Market-Report.xlsx -Out xl.json -Sar 3.75 -Bhd 0.376
    python -m gr.check_workbook xl.json

Python recomputes everything here from the marts, independently of the workbook's formulas, at the rates Excel
was given and with the same test forecast the PowerShell script typed. Every value must agree to 0.5%.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from gr.workbook import RETENTION

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"


def close(a, b, tol=0.005) -> bool:
    blank = lambda v: v in (None, "") or (isinstance(v, float) and v != v)  # noqa: E731
    if blank(a) and blank(b):
        return True
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return False


def main(path: str) -> None:
    res = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    sar, bhd = float(res["sar"]), float(res["bhd"])
    p = pd.read_csv(MARTS / "gcc_products.csv", keep_default_na=False)
    units = pd.to_numeric(p.units_per_pack, errors="coerce")
    p["ppu_local"] = p.price_local.astype(float) / units.where(units > 0)
    p["ppu_usd"] = p.ppu_local / p.currency.map({"SAR": sar, "BHD": bhd})
    problems: list[str] = []
    n = 0

    def check(label, got, exp):
        nonlocal n
        n += 1
        if not close(got, exp):
            problems.append(f"{label}: Excel {got} vs Python {exp}")

    for (loc, usd), r in zip(res["products"], p.itertuples()):
        check(f"product {r.pid} local", loc, r.ppu_local)
        check(f"product {r.pid} usd", usd, r.ppu_usd)
    if len(res["products"]) != len(p):
        problems.append(f"Products has {len(res['products'])} rows, the mart {len(p)}")

    for country, ing, n_msd, msd_min, other, gen, cheapest, vs in res["competition"]:
        d = p[(p.country == country) & (p.ingredient == ing)]
        m = d[d.role == "MSD"].ppu_usd.min()
        g = d[d.role == "Generic or other"].ppu_usd
        for label, got, exp in (("msd", n_msd, (d.role == "MSD").sum()), ("msd min", msd_min, m), ("other", other, (d.role == "Originator").sum()),
                                ("generic", gen, len(g)), ("cheapest", cheapest, g.min() if len(g) else None), ("vs", vs, (g.min() / m - 1) if len(g) else None)):
            check(f"{country} {ing} {label}", got, exp)

    pid_usd = dict(zip(p.pid, p.ppu_usd))
    mp = pd.read_csv(MARTS / "gcc_msd_prices.csv", keep_default_na=False)
    for (brand, s_usd, b_usd, vs), r in zip(res["gcc"], mp.itertuples()):
        if r.saudi_pid == "":
            check(f"{brand} not compared", s_usd, None)
            continue
        es, eb = pid_usd[int(float(r.saudi_pid))], pid_usd[int(float(r.bahrain_pid))]
        check(f"{brand} saudi", s_usd, es)
        check(f"{brand} bahrain", b_usd, eb)
        check(f"{brand} ratio", vs, es / eb - 1)

    rp = pd.read_csv(MARTS / "reference_pricing.csv", keep_default_na=False)
    for (brand, s, us_s, b, us_b), r in zip(res["reference"], rp.itertuples()):
        for got, ratio, pid in ((s, us_s, r.saudi_pid), (b, us_b, r.bahrain_pid)):
            exp = pid_usd[int(float(pid))] if pid != "" else None
            check(f"{brand} per tablet", got, exp)
            check(f"{brand} US ratio", ratio, (float(r.us_nadac_per_tablet_usd) / exp) if exp else None)

    msd = p[p.role == "MSD"].reset_index(drop=True)
    expected_rev = []
    for i, r in msd.iterrows():
        row = i + 3
        entry = 2 if row % 3 == 0 else None
        price = 0.0 if r.ppu_usd != r.ppu_usd else r.ppu_usd
        revs = []
        for q in range(1, 5):
            u = 1000 * (row - 2) + 100 * q
            keep = 1.0 if entry is None or q < entry else RETENTION[min(q - entry, 3)]
            revs.append(u * price * keep)
        expected_rev.append((r.country, r.brand, revs))
        got = res["forecast"][i]
        check(f"forecast row {row} price", got[0], r.ppu_usd if r.ppu_usd == r.ppu_usd else None)
        for q in range(4):
            check(f"forecast row {row} q{q + 1}", got[1 + q], revs[q])
        check(f"forecast row {row} total", got[5], sum(revs))
    for country, brand, total in res["summary"]:
        if country == "Total":
            check("forecast grand total", total, sum(sum(x[2]) for x in expected_rev))
            continue
        check(f"summary {country} {brand}", total, sum(sum(x[2]) for x in expected_rev if x[0] == country and x[1] == brand))

    if problems:
        print("\n".join(problems[:25]))
        raise SystemExit(f"{len(problems)} disagreements in {n} values (SAR {sar}, BHD {bhd})")
    print(f"{n} values agree with Python (SAR {sar}, BHD {bhd})")


if __name__ == "__main__":
    main(sys.argv[1])
