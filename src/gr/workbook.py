"""The monthly report pack as an Excel workbook with live formulas.

    python -m gr.workbook        (writes excel/GCC-Market-Report.xlsx)

Yellow cells are inputs (the riyal-dollar rate). Everything else is a formula over the Products sheet, so
changing an input or pasting next month's products recalculates the pack. tools/check_workbook.ps1 opens the
file in Excel, recalculates it and compares the results with Python.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "excel" / "GCC-Market-Report.xlsx"

INPUT = PatternFill("solid", fgColor="FFF6D6")
HEAD = PatternFill("solid", fgColor="15302C")
WHITE = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
THIN = Border(bottom=Side(style="thin", color="CDC7B4"))


def header(ws, row: int, names: list[str]) -> None:
    for i, n in enumerate(names, 1):
        c = ws.cell(row=row, column=i, value=n)
        c.fill, c.font = HEAD, WHITE
        c.alignment = Alignment(wrap_text=True, vertical="top")


def widths(ws, w: list[int]) -> None:
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x


def main() -> None:
    cp = pd.read_csv(MARTS / "class_position.csv", keep_default_na=False)
    gp = pd.read_csv(MARTS / "generic_pressure.csv", keep_default_na=False)
    rp = pd.read_csv(MARTS / "reference_pricing.csv", keep_default_na=False)
    val = list(csv.DictReader((MARTS / "validation.csv").open(encoding="utf-8")))
    head = {r["key"]: r["value"] for r in csv.DictReader((MARTS / "headline.csv").open(encoding="utf-8"))}

    wb = Workbook()
    rd = wb.active
    rd.title = "Read me"
    lines = [
        ("GCC Market Report: Saudi Arabia", BOLD),
        (f"Snapshot of the SFDA public Drugs List taken {head['snapshot']}: {int(head['products_in_list']):,} products; {head['followed_products']} followed in the classes MSD competes in.", None),
        ("Yellow cells are inputs. Everything else is a formula over the Products sheet: paste next month's products there and the pack recalculates.", None),
        ("Price per unit = public pack price / pack size (a tablet, capsule, vial or pen). The riyal is pegged to the dollar; the rate is an input.", None),
        ("US prices are the pharmacy acquisition cost (NADAC) per tablet, from Drug Price Watch; they are not net prices.", None),
        ("An independent analysis of public data, not produced or endorsed by MSD or any company named.", None),
    ]
    for i, (t, f) in enumerate(lines, 1):
        c = rd.cell(row=i, column=1, value=t)
        if f:
            c.font = Font(bold=True, size=14)
    rd.column_dimensions["A"].width = 130

    inp = wb.create_sheet("Inputs")
    inp["A1"], inp["B1"] = "Saudi riyals per US dollar", float(head["sar_per_usd"])
    inp["B1"].fill = INPUT
    inp["A1"].font = BOLD
    inp["A2"] = "Change the yellow cell; every USD figure follows."
    widths(inp, [32, 12])

    # Products: the data, with the per-unit formulas.
    ps = wb.create_sheet("Products")
    cols = ["Class", "Class name", "Ingredient", "Trade name", "Strength", "Unit", "Form", "Pack size", "Price SAR", "Price per unit SAR", "Price per unit USD", "Role", "Marketing company", "Local agent", "Registration no."]
    header(ps, 1, cols)
    n = len(cp)
    for i, r in enumerate(cp.itertuples(), start=2):
        vals = [r.atc5, r._2, r.ingredient, r.trade, str(r.strength), r.strength_unit, r.form, float(r.pack_size), float(r.price_sar), None, None, r.role, r.marketing_company, r.agent, str(r.reg_no)]
        for j, v in enumerate(vals, 1):
            ps.cell(row=i, column=j, value=v)
        ps.cell(row=i, column=10, value=f"=IF(H{i}>0,I{i}/H{i},\"\")")
        ps.cell(row=i, column=11, value=f"=IF(J{i}=\"\",\"\",J{i}/Inputs!$B$1)")
        ps.cell(row=i, column=10).number_format = "#,##0.00"
        ps.cell(row=i, column=11).number_format = "#,##0.00"
    last = n + 1
    t = Table(displayName="Products", ref=f"A1:O{last}")
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
    ps.add_table(t)
    widths(ps, [8, 24, 16, 44, 14, 8, 26, 9, 12, 12, 12, 16, 36, 36, 14])
    ps.freeze_panes = "E2"
    rng = lambda col: f"Products!${col}$2:${col}${last}"  # noqa: E731

    # Generic pressure: counts and prices by formula.
    gs = wb.create_sheet("Generic pressure")
    header(gs, 1, ["Ingredient", "MSD products", "MSD lowest per unit SAR", "Other versions", "Generic or other", "Cheapest generic per unit SAR", "Cheapest vs MSD"])
    for i, r in enumerate(gp.itertuples(), start=2):
        gs.cell(row=i, column=1, value=r.ingredient)
        gs.cell(row=i, column=2, value=r.msd_products)
        gs.cell(row=i, column=3, value=f'=_xlfn.MINIFS({rng("J")},{rng("C")},A{i},{rng("L")},"MSD")')
        gs.cell(row=i, column=4, value=f'=COUNTIFS({rng("C")},A{i},{rng("L")},"<>MSD")')
        gs.cell(row=i, column=5, value=f'=COUNTIFS({rng("C")},A{i},{rng("L")},"Generic or other")')
        gs.cell(row=i, column=6, value=f'=IF(E{i}=0,"",_xlfn.MINIFS({rng("J")},{rng("C")},A{i},{rng("L")},"Generic or other"))')
        gs.cell(row=i, column=7, value=f'=IF(F{i}="","",F{i}/C{i}-1)')
        gs.cell(row=i, column=7).number_format = "0%"
        for c in (3, 6):
            gs.cell(row=i, column=c).number_format = "#,##0.00"
    widths(gs, [16, 60, 14, 10, 10, 14, 12])

    # Reference pricing: US per tablet (value) against the Saudi per tablet (formula from Products).
    rs = wb.create_sheet("Reference pricing")
    header(rs, 1, ["Brand", "US pack", "US NADAC per tablet USD", "Saudi product", "Saudi per tablet USD", "US / Saudi"])
    for i, r in enumerate(rp.itertuples(), start=2):
        rs.cell(row=i, column=1, value=r.brand)
        rs.cell(row=i, column=2, value=r.us_pack)
        rs.cell(row=i, column=3, value=float(r.us_nadac_per_tablet_usd))
        rs.cell(row=i, column=4, value=r.ksa_product)
        if r.ksa_per_tablet_usd not in ("", None):
            name = r.ksa_product.split(" (")[0]
            pack = r.ksa_product.rsplit("pack of ", 1)[-1].rstrip(")")
            # The Saudi product row: same trade name and pack size, the MSD role.
            rs.cell(row=i, column=5, value=f'=_xlfn.MINIFS({rng("K")},{rng("D")},"{name}",{rng("H")},{pack},{rng("L")},"MSD")')
            rs.cell(row=i, column=6, value=f"=C{i}/E{i}")
            rs.cell(row=i, column=6).number_format = '0.0"x"'
        for c in (3, 5):
            rs.cell(row=i, column=c).number_format = "#,##0.00"
    widths(rs, [12, 32, 14, 46, 14, 10])

    vs = wb.create_sheet("Validation")
    header(vs, 1, ["Id", "Check", "Status", "Result", "Rule"])
    for i, r in enumerate(val, start=2):
        for j, k in enumerate(["id", "check", "status", "result", "rule"], 1):
            vs.cell(row=i, column=j, value=r[k])
    widths(vs, [6, 52, 8, 70, 70])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}: {n} products, {len(gp)} molecules, {len(rp)} reference prices")


if __name__ == "__main__":
    main()
