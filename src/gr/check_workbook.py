"""Compares the workbook's formula results, recalculated by Excel, with Python's own calculation.

    powershell -File tools/check_workbook.ps1 -Path excel/GCC-Market-Report.xlsx -Out excel-results.json -Rate 3.75
    python -m gr.check_workbook excel-results.json

Python recomputes everything from data/marts/class_position.csv here, independently of the workbook's
formulas, at the rate Excel was given. Every cell must agree to a hundredth of a riyal or dollar.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"


def close(a, b, tol=0.005) -> bool:
    if a in (None, "") and b in (None, ""):
        return True
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return False


def main(path: str) -> None:
    res = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    rate = float(res["rate"])
    cp = pd.read_csv(MARTS / "class_position.csv", keep_default_na=False, dtype={"reg_no": str})
    cp["ppu"] = cp.price_sar.astype(float) / cp.pack_size.astype(float)
    problems: list[str] = []
    checked = 0

    # The Products sheet is written in the mart's row order; a registration number can cover several packs, so match by position.
    if len(res["products"]) != len(cp):
        problems.append(f"Products sheet has {len(res['products'])} rows, the mart {len(cp)}")
    for (reg, ppu_sar, ppu_usd), exp, mart_reg in zip(res["products"], cp.ppu, cp.reg_no):
        if str(reg) != str(mart_reg):
            problems.append(f"row order differs at registration {reg}")
            break
        checked += 2
        if not close(ppu_sar, exp) or not close(ppu_usd, exp / rate):
            problems.append(f"product {reg}: Excel {ppu_sar}, {ppu_usd} vs Python {exp:.4f}, {exp / rate:.4f}")

    for ing, msd_min, other, gen, cheapest, vs in res["generic"]:
        d = cp[cp.ingredient == ing]
        m = d[d.role == "MSD"].ppu.min()
        g = d[d.role == "Generic or other"].ppu
        exp = [m, int((d.role != "MSD").sum()), len(g), g.min() if len(g) else "", (g.min() / m - 1) if len(g) else ""]
        got = [msd_min, other, gen, cheapest, vs]
        for e, x in zip(exp, got):
            checked += 1
            if not close(x, e):
                problems.append(f"{ing}: Excel {got} vs Python {exp}")
                break

    rp = pd.read_csv(MARTS / "reference_pricing.csv", keep_default_na=False)
    for brand, ksa_usd, ratio in res["reference"]:
        r = rp[rp.brand == brand].iloc[0]
        if r.ksa_per_tablet_usd in ("", None):
            checked += 1
            if ksa_usd not in (None, ""):
                problems.append(f"{brand}: Excel has a Saudi price where Python found none")
            continue
        exp_ksa = float(r.ksa_per_tablet_usd) * 3.75 / rate
        checked += 2
        if not close(ksa_usd, exp_ksa) or not close(ratio, float(r.us_nadac_per_tablet_usd) / exp_ksa):
            problems.append(f"{brand}: Excel {ksa_usd}, {ratio} vs Python {exp_ksa:.4f}, {float(r.us_nadac_per_tablet_usd) / exp_ksa:.3f}")

    if problems:
        print("\n".join(problems[:20]))
        raise SystemExit(f"{len(problems)} disagreements in {checked} values at rate {rate}")
    print(f"{checked} values agree with Python at rate {rate}")


if __name__ == "__main__":
    main(sys.argv[1])
