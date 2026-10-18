"""The monthly GCC report pack as an Excel workbook with live formulas.

    python -m gr.workbook        (writes excel/GCC-Market-Report.xlsx)

Yellow cells are inputs: the two exchange rates, the generic-erosion curve, and on Forecast input the units
the team expects to sell. Everything else is a formula over the Products sheet, so pasting next month's
products, or typing a forecast, recalculates the pack. tools/check_workbook.ps1 opens the file in Excel, types
a test forecast, recalculates, and gr.check_workbook compares every result with Python.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from gr.analyse import SAR_PER_USD
from gr.bahrain import BHD_PER_USD

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "excel" / "GCC-Market-Report.xlsx"

INPUT = PatternFill("solid", fgColor="FFF6D6")
HEAD = PatternFill("solid", fgColor="15302C")
WHITE = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
QUARTERS = ["2027Q1", "2027Q2", "2027Q3", "2027Q4"]
# Median share of pre-entry brand spend kept k quarters after the first generic (Rx Market Pulse, 48 molecules).
RETENTION = [0.766, 0.599, 0.518, 0.461]


def header(ws, row: int, names: list[str]) -> None:
    for i, n in enumerate(names, 1):
        c = ws.cell(row=row, column=i, value=n)
        c.fill, c.font = HEAD, WHITE
        c.alignment = Alignment(wrap_text=True, vertical="top")


def widths(ws, w: list[int]) -> None:
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x


def money(cell, fmt: str = "#,##0.00") -> None:
    cell.number_format = fmt


def main() -> None:
    p = pd.read_csv(MARTS / "gcc_products.csv", keep_default_na=False)
    comp = pd.read_csv(MARTS / "gcc_competition.csv", keep_default_na=False)
    mp = pd.read_csv(MARTS / "gcc_msd_prices.csv", keep_default_na=False)
    rp = pd.read_csv(MARTS / "reference_pricing.csv", keep_default_na=False)
    ch = pd.read_csv(MARTS / "bahrain_changes.csv", keep_default_na=False)
    val = list(csv.DictReader((MARTS / "validation.csv").open(encoding="utf-8"))) + list(csv.DictReader((MARTS / "validation_bahrain.csv").open(encoding="utf-8")))
    head = {r["key"]: r["value"] for r in csv.DictReader((MARTS / "headline.csv").open(encoding="utf-8"))}
    assert (p.pid == range(len(p))).all(), "products must be in pid order"

    wb = Workbook()
    rd = wb.active
    rd.title = "Read me"
    lines = [
        "GCC Market Report: Saudi Arabia and Bahrain",
        f"Saudi Arabia: SFDA public Drugs List, snapshot {head['snapshot']} ({int(head['products_in_list']):,} products). Bahrain: NHRA Registered Medicine Price List of 7 September 2026, with the February 2024 price lists for comparison.",
        f"{len(p)} products are followed in the classes MSD competes in, {int((p.role == 'MSD').sum())} of them MSD's, classed on Saudi ATC codes in both countries.",
        "Yellow cells are inputs. Everything else is a formula over the Products sheet.",
        "Forecast input is the quarterly forecast entry sheet: type the units you expect per product and quarter, and a generic entry quarter if any; Forecast summary adds them up by country and brand.",
        "Price per unit = public pack price / units per pack. Both currencies are pegged to the dollar; the rates are inputs. US prices are pharmacy acquisition costs (NADAC), not net prices.",
        "An independent analysis of public data, not produced or endorsed by MSD or any company named.",
    ]
    for i, t in enumerate(lines, 1):
        c = rd.cell(row=i, column=1, value=t)
        if i == 1:
            c.font = Font(bold=True, size=14)
    rd.column_dimensions["A"].width = 150

    inp = wb.create_sheet("Inputs")
    inp["A1"], inp["B1"] = "Saudi riyals per US dollar", SAR_PER_USD
    inp["A2"], inp["B2"] = "Bahraini dinars per US dollar", BHD_PER_USD
    inp["A4"] = "Brand revenue kept after the first generic (share of the quarter before entry)"
    for k, v in enumerate(RETENTION):
        inp.cell(row=5 + k, column=1, value=f"{k} quarters after entry" if k else "Quarter of entry")
        inp.cell(row=5 + k, column=2, value=v)
        inp.cell(row=5 + k, column=2).number_format = "0.0%"
    for r in (1, 2, 5, 6, 7, 8):
        inp.cell(row=r, column=2).fill = INPUT
    inp["A10"] = "Source of the curve: median across 48 molecules that lost US exclusivity, measured in Rx Market Pulse. Replace it with a GCC curve when one is available."
    widths(inp, [60, 12])

    # Products: both countries; price per unit in local currency and USD are formulas.
    ps = wb.create_sheet("Products")
    cols = ["Country", "Class", "Class name", "Ingredient", "Name", "Brand", "Strength", "Form", "Units per pack", "Pack price", "Currency",
            "Price per unit (local)", "Price per unit USD", "Role", "Company", "Registration no."]
    header(ps, 1, cols)
    for i, r in enumerate(p.itertuples(), start=2):
        vals = [r.country, r.atc5, r._3, r.ingredient, r.name, r.brand, str(r.strength), r.form, float(r.units_per_pack) if r.units_per_pack != "" else None,
                float(r.price_local), r.currency, None, None, r.role, r.company, str(r.reg_no)]
        for j, v in enumerate(vals, 1):
            ps.cell(row=i, column=j, value=v)
        ps.cell(row=i, column=12, value=f'=IF(AND(ISNUMBER(I{i}),I{i}>0),J{i}/I{i},"")')
        ps.cell(row=i, column=13, value=f'=IF(L{i}="","",L{i}/IF(K{i}="SAR",Inputs!$B$1,Inputs!$B$2))')
        money(ps.cell(row=i, column=12))
        money(ps.cell(row=i, column=13))
    last = len(p) + 1
    t = Table(displayName="Products", ref=f"A1:P{last}")
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
    ps.add_table(t)
    widths(ps, [13, 7, 22, 16, 40, 14, 14, 26, 8, 11, 8, 12, 12, 16, 34, 14])
    ps.freeze_panes = "F2"
    R = lambda col: f"Products!${col}$2:${col}${last}"  # noqa: E731

    # Competition: per country and MSD molecule, all by formula.
    cs = wb.create_sheet("Competition")
    header(cs, 1, ["Country", "Molecule or vaccine class", "MSD products", "MSD lowest per unit USD", "Other brands", "Generic or other", "Cheapest generic per unit USD", "Cheapest generic vs MSD"])
    for i, r in enumerate(comp.itertuples(), start=2):
        cs.cell(row=i, column=1, value=r.country)
        cs.cell(row=i, column=2, value=r.ingredient)
        cs.cell(row=i, column=3, value=f'=COUNTIFS({R("A")},A{i},{R("D")},B{i},{R("N")},"MSD")')
        cs.cell(row=i, column=4, value=f'=_xlfn.MINIFS({R("M")},{R("A")},A{i},{R("D")},B{i},{R("N")},"MSD")')
        cs.cell(row=i, column=5, value=f'=COUNTIFS({R("A")},A{i},{R("D")},B{i},{R("N")},"Originator")')
        cs.cell(row=i, column=6, value=f'=COUNTIFS({R("A")},A{i},{R("D")},B{i},{R("N")},"Generic or other")')
        cs.cell(row=i, column=7, value=f'=IF(F{i}=0,"",_xlfn.MINIFS({R("M")},{R("A")},A{i},{R("D")},B{i},{R("N")},"Generic or other"))')
        cs.cell(row=i, column=8, value=f'=IF(G{i}="","",G{i}/D{i}-1)')
        money(cs.cell(row=i, column=4))
        money(cs.cell(row=i, column=7))
        cs.cell(row=i, column=8).number_format = "0%"
    widths(cs, [13, 34, 9, 14, 9, 10, 14, 12])

    # GCC prices: each MSD product in both countries, prices referenced from its Products row.
    gs = wb.create_sheet("GCC prices")
    header(gs, 1, ["Brand", "Strength", "Units per pack", "Saudi product", "Saudi per unit USD", "Bahrain product", "Bahrain per unit USD", "Saudi vs Bahrain", "Note"])
    for i, r in enumerate(mp.itertuples(), start=2):
        gs.cell(row=i, column=1, value=r.brand)
        gs.cell(row=i, column=2, value=str(r.strength))
        gs.cell(row=i, column=3, value=r.units_per_pack)
        gs.cell(row=i, column=4, value=r.saudi_pack)
        gs.cell(row=i, column=6, value=r.bahrain_pack)
        gs.cell(row=i, column=9, value=r.note)
        if r.saudi_pid != "":
            gs.cell(row=i, column=5, value=f"=Products!M{int(float(r.saudi_pid)) + 2}")
            gs.cell(row=i, column=7, value=f"=Products!M{int(float(r.bahrain_pid)) + 2}")
            gs.cell(row=i, column=8, value=f"=E{i}/G{i}-1")
            gs.cell(row=i, column=8).number_format = "0.0%"
        money(gs.cell(row=i, column=5))
        money(gs.cell(row=i, column=7))
    widths(gs, [14, 16, 8, 40, 12, 32, 12, 10, 60])

    # Reference pricing: the US per tablet (a value) against both countries (formulas).
    rs = wb.create_sheet("Reference pricing")
    header(rs, 1, ["Brand", "US pack", "US NADAC per tablet USD", "Saudi product", "Saudi per tablet USD", "US / Saudi", "Bahrain product", "Bahrain per tablet USD", "US / Bahrain"])
    for i, r in enumerate(rp.itertuples(), start=2):
        rs.cell(row=i, column=1, value=r.brand)
        rs.cell(row=i, column=2, value=r.us_pack)
        rs.cell(row=i, column=3, value=float(r.us_nadac_per_tablet_usd))
        rs.cell(row=i, column=4, value=r.saudi_product)
        rs.cell(row=i, column=7, value=r.bahrain_product)
        for pid, col, ratio in ((r.saudi_pid, 5, 6), (r.bahrain_pid, 8, 9)):
            if pid != "":
                rs.cell(row=i, column=col, value=f"=Products!M{int(float(pid)) + 2}")
                rs.cell(row=i, column=ratio, value=f"=C{i}/{get_column_letter(col)}{i}")
                rs.cell(row=i, column=ratio).number_format = '0.0"x"'
            money(rs.cell(row=i, column=col))
        money(rs.cell(row=i, column=3))
    widths(rs, [12, 30, 12, 36, 12, 9, 28, 12, 9])

    # Bahrain 2024 -> 2026.
    bs = wb.create_sheet("Bahrain changes")
    header(bs, 1, ["Registration no.", "Name", "2024 list", "Price Feb 2024 BD", "Price Sep 2026 BD", "Change"])
    for i, r in enumerate(ch.itertuples(), start=2):
        for j, v in enumerate([r.reg_no, r.name, r.list, float(r.price_bhd_2024), float(r.price_bhd)], 1):
            bs.cell(row=i, column=j, value=v)
        bs.cell(row=i, column=6, value=f"=E{i}/D{i}-1")
        bs.cell(row=i, column=6).number_format = "0.0%"
    widths(bs, [14, 30, 10, 12, 12, 9])

    # Forecast input: one row per MSD product; units are typed, revenue follows.
    fs = wb.create_sheet("Forecast input")
    msd = p[p.role == "MSD"]
    fs["A1"] = "Quarterly forecast entry. Type expected units in the yellow cells (blank = no forecast), and the quarter (1 to 4) a first generic launches, if any."
    fs["A1"].font = BOLD
    cols = ["Country", "Brand", "Product", "Price per unit USD", *[f"Units {q}" for q in QUARTERS], "Generic entry quarter (1-4)", *[f"Revenue {q} USD" for q in QUARTERS], "Revenue 2027 USD"]
    header(fs, 2, cols)
    dv = DataValidation(type="whole", operator="between", formula1="1", formula2="4", allow_blank=True, showErrorMessage=True, errorTitle="Quarter", error="Type 1, 2, 3 or 4, or leave it blank.")
    fs.add_data_validation(dv)
    for i, r in enumerate(msd.itertuples(), start=3):
        fs.cell(row=i, column=1, value=r.country)
        fs.cell(row=i, column=2, value=r.brand)
        fs.cell(row=i, column=3, value=f"{r.name} {r.strength}".strip())
        fs.cell(row=i, column=4, value=f"=Products!M{int(r.pid) + 2}")
        money(fs.cell(row=i, column=4))
        for q in range(4):
            fs.cell(row=i, column=5 + q).fill = INPUT
        fs.cell(row=i, column=9).fill = INPUT
        dv.add(fs.cell(row=i, column=9))
        for q in range(4):
            units = f"{get_column_letter(5 + q)}{i}"
            keep = f'IF(OR($I{i}="",{q + 1}<$I{i}),1,INDEX(Inputs!$B$5:$B$8,MIN({q + 1}-$I{i}+1,4)))'
            fs.cell(row=i, column=10 + q, value=f'=IF({units}="","",{units}*IF($D{i}="",0,$D{i})*{keep})')
            money(fs.cell(row=i, column=10 + q), "#,##0")
        fs.cell(row=i, column=14, value=f"=SUM(J{i}:M{i})")
        money(fs.cell(row=i, column=14), "#,##0")
    flast = len(msd) + 2
    widths(fs, [13, 14, 40, 12, 10, 10, 10, 10, 12, 13, 13, 13, 13, 14])
    fs.freeze_panes = "E3"

    ss = wb.create_sheet("Forecast summary")
    header(ss, 1, ["Country", "Brand", *[f"Revenue {q} USD" for q in QUARTERS], "Revenue 2027 USD"])
    pairs = msd[["country", "brand"]].drop_duplicates().sort_values(["country", "brand"])
    F = lambda col: f"'Forecast input'!${col}$3:${col}${flast}"  # noqa: E731
    for i, (c, b) in enumerate(pairs.itertuples(index=False), start=2):
        ss.cell(row=i, column=1, value=c)
        ss.cell(row=i, column=2, value=b)
        for q in range(5):
            col = get_column_letter(10 + q)
            ss.cell(row=i, column=3 + q, value=f'=SUMIFS({F(col)},{F("A")},A{i},{F("B")},B{i})')
            money(ss.cell(row=i, column=3 + q), "#,##0")
    tot = len(pairs) + 2
    ss.cell(row=tot, column=1, value="Total").font = BOLD
    for q in range(5):
        col = get_column_letter(3 + q)
        ss.cell(row=tot, column=3 + q, value=f"=SUM({col}2:{col}{tot - 1})")
        money(ss.cell(row=tot, column=3 + q), "#,##0")
    widths(ss, [13, 14, 14, 14, 14, 14, 16])

    vs = wb.create_sheet("Validation")
    header(vs, 1, ["Id", "Check", "Status", "Result", "Rule"])
    for i, r in enumerate(val, start=2):
        for j, k in enumerate(["id", "check", "status", "result", "rule"], 1):
            vs.cell(row=i, column=j, value=r[k])
    widths(vs, [6, 52, 8, 70, 70])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(p)} products, {len(comp)} competition rows, {len(mp)} GCC price rows, {len(msd)} forecast rows")


if __name__ == "__main__":
    main()
