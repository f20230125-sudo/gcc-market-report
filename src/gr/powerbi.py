"""Write a Power BI project (PBIP) for the GCC market report.

    python -m gr.powerbi            # writes powerbi/ (CSV data + semantic model + report)

The output is a Power BI Desktop project: plain-text folders Desktop opens directly (File > Open > GCCMarketReport.pbip).
  powerbi/data/*.csv                       the tables, a star schema of the marts
  powerbi/GCCMarketReport.SemanticModel/   TMDL: tables, relationships, DAX measures
  powerbi/GCCMarketReport.Report/          PBIR: six pages of visuals and a theme
Generated from code (adapted from Rx Market Pulse's generator), so the model, the measures and the report stay in
step with the data and in git. Opening it needs one "Refresh now", since the project carries no data cache.
"""

from __future__ import annotations

import csv
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MARTS = ROOT / "data" / "marts"
PBI = ROOT / "powerbi"
DATA = PBI / "data"
MODEL = PBI / "GCCMarketReport.SemanticModel"
REPORT = PBI / "GCCMarketReport.Report"

TEAL, OCHRE, SLATE, RUST = "#008E7C", "#B5731A", "#5B6B73", "#A8472A"
INK, PAPER, RULE = "#15302C", "#FAF8F3", "#E1DCCD"


def _guid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gcc-market-report/{name}"))


def _oid(name: str) -> str:
    return hashlib.sha1(name.encode()).hexdigest()[:20]


@dataclass
class Table:
    name: str
    columns: list[tuple[str, str]]  # (name, dataType) dataType in string|int64|double|dateTime
    rows: list[tuple]
    measures: list[tuple[str, str, str]] = field(default_factory=list)  # (name, dax, formatString)
    hidden_cols: set[str] = field(default_factory=set)


def num(v):
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def build_tables() -> list[Table]:
    p = pd.read_csv(MARTS / "gcc_products.csv", keep_default_na=False)
    comp = pd.read_csv(MARTS / "gcc_competition.csv", keep_default_na=False)
    mp = pd.read_csv(MARTS / "gcc_msd_prices.csv", keep_default_na=False)
    rp = pd.read_csv(MARTS / "reference_pricing.csv", keep_default_na=False)
    ch = pd.read_csv(MARTS / "bahrain_changes.csv", keep_default_na=False)
    v_sa = pd.read_csv(MARTS / "validation.csv", keep_default_na=False)
    v_bh = pd.read_csv(MARTS / "validation_bahrain.csv", keep_default_na=False)
    t: list[Table] = []

    t.append(Table("dim_country", [("country", "string"), ("currency", "string"), ("source", "string")],
                   [("Saudi Arabia", "SAR", "SFDA Drugs List, 18 Oct 2026"), ("Bahrain", "BHD", "NHRA Registered Medicine Price List, 7 Sep 2026")]))
    classes = p[p.atc5 != ""][["atc5", "class"]].drop_duplicates("atc5").sort_values("atc5")
    t.append(Table("dim_class", [("atc5", "string"), ("class_name", "string")], [(a, c or a) for a, c in classes.itertuples(index=False)] + [("", "Unclassed")]))
    t.append(Table("fact_products", [("pid", "int64"), ("country", "string"), ("atc5", "string"), ("ingredient", "string"), ("name", "string"), ("brand", "string"),
                                     ("strength", "string"), ("form", "string"), ("units_per_pack", "double"), ("pack_price_local", "double"), ("currency", "string"),
                                     ("price_per_unit_usd", "double"), ("role", "string"), ("company", "string")],
                   [(int(r.pid), r.country, r.atc5, r.ingredient, r.name, r.brand, str(r.strength), r.form, num(r.units_per_pack), num(r.price_local), r.currency,
                     num(r.price_per_unit_usd), r.role, r.company) for r in p.itertuples()]))
    t.append(Table("fact_competition", [("country", "string"), ("ingredient", "string"), ("msd_lowest_per_unit_usd", "double"), ("other_brands", "int64"),
                                        ("generic_or_other", "int64"), ("generic_companies", "int64"), ("cheapest_generic_per_unit_usd", "double"), ("cheapest_generic_vs_msd", "double")],
                   [(r.country, r.ingredient, num(r.msd_lowest_per_unit_usd), int(r.other_brands), int(r.generic_or_other), int(r.generic_companies),
                     num(r.cheapest_generic_per_unit_usd), num(r.cheapest_generic_vs_msd)) for r in comp.itertuples()]))
    t.append(Table("fact_gcc_prices", [("brand", "string"), ("strength", "string"), ("product", "string"), ("saudi_per_unit_usd", "double"), ("bahrain_per_unit_usd", "double"),
                                       ("saudi_vs_bahrain", "double"), ("note", "string")],
                   [(r.brand, str(r.strength), f"{r.brand} {r.strength} x{r.units_per_pack}", num(r.saudi_per_unit_usd), num(r.bahrain_per_unit_usd), num(r.saudi_vs_bahrain), r.note)
                    for r in mp.itertuples()]))
    ref_rows = []
    for r in rp.itertuples():
        for country, prod, per, ratio in (("Saudi Arabia", r.saudi_product, r.saudi_per_tablet_usd, r.us_vs_saudi), ("Bahrain", r.bahrain_product, r.bahrain_per_tablet_usd, r.us_vs_bahrain)):
            ref_rows.append((r.brand, r.us_pack, num(r.us_nadac_per_tablet_usd), country, prod, num(per), num(ratio)))
    t.append(Table("fact_reference", [("brand", "string"), ("us_pack", "string"), ("us_per_tablet_usd", "double"), ("country", "string"), ("gcc_product", "string"),
                                      ("gcc_per_tablet_usd", "double"), ("us_over_gcc", "double")], ref_rows))
    t.append(Table("fact_bahrain_changes", [("reg_no", "string"), ("name", "string"), ("list_2024", "string"), ("price_feb_2024_bd", "double"), ("price_sep_2026_bd", "double"),
                                            ("change", "double"), ("direction", "string")],
                   [(r.reg_no, r.name, r.list, num(r.price_bhd_2024), num(r.price_bhd), num(r.change),
                     "Unchanged" if abs(float(r.change)) <= 0.005 else ("Raised" if float(r.change) > 0 else "Cut")) for r in ch.itertuples()]))
    vrows = [("Saudi Arabia", r.id, r.check, r.status, r.result) for r in v_sa.itertuples()] + [("Bahrain", r.id, r.check, r.status, r.result) for r in v_bh.itertuples()]
    t.append(Table("fact_validation", [("country", "string"), ("id", "string"), ("check", "string"), ("status", "string"), ("result", "string")], vrows))
    return t


USD = '"$"#,##0.00'
PCT = "0.0%"


def add_measures(tables: dict[str, Table]) -> None:
    tables["fact_products"].measures = [
        ("Products", "COUNTROWS(fact_products)", "#,##0"),
        ("MSD Products", 'CALCULATE(COUNTROWS(fact_products), fact_products[role] = "MSD")', "#,##0"),
        ("Generic Versions", 'CALCULATE(COUNTROWS(fact_products), fact_products[role] = "Generic or other")', "#,##0"),
        ("Other Brands", 'CALCULATE(COUNTROWS(fact_products), fact_products[role] = "Originator")', "#,##0"),
        ("Companies", "DISTINCTCOUNT(fact_products[company])", "#,##0"),
        ("Median Price per Unit USD", "MEDIAN(fact_products[price_per_unit_usd])", USD),
        ("MSD Lowest per Unit USD", 'CALCULATE(MIN(fact_products[price_per_unit_usd]), fact_products[role] = "MSD")', USD),
        ("Cheapest Generic per Unit USD", 'CALCULATE(MIN(fact_products[price_per_unit_usd]), fact_products[role] = "Generic or other")', USD),
        # Blank when there is no generic: in DAX a blank minus 1 is -1, which would read as "100% cheaper".
        ("Cheapest Generic vs MSD", "IF(ISBLANK([Cheapest Generic per Unit USD]) || ISBLANK([MSD Lowest per Unit USD]), BLANK(), DIVIDE([Cheapest Generic per Unit USD], [MSD Lowest per Unit USD]) - 1)", PCT),
    ]
    tables["fact_competition"].measures = [
        ("Generic Versions per Molecule", "SUM(fact_competition[generic_or_other])", "#,##0"),
    ]
    tables["fact_gcc_prices"].measures = [
        ("Products Compared", "COUNTROWS(FILTER(fact_gcc_prices, NOT ISBLANK(fact_gcc_prices[saudi_vs_bahrain])))", "0"),
        ("Median Saudi vs Bahrain", "MEDIAN(fact_gcc_prices[saudi_vs_bahrain])", PCT),
        ("Saudi Cheaper", "COUNTROWS(FILTER(fact_gcc_prices, fact_gcc_prices[saudi_vs_bahrain] < 0))", "0"),
    ]
    tables["fact_reference"].measures = [
        ("US over GCC (median)", "MEDIAN(fact_reference[us_over_gcc])", '0.0"x"'),
    ]
    tables["fact_bahrain_changes"].measures = [
        ("Prices Matched", "COUNTROWS(fact_bahrain_changes)", "0"),
        ("Share Unchanged", 'DIVIDE(CALCULATE(COUNTROWS(fact_bahrain_changes), fact_bahrain_changes[direction] = "Unchanged"), COUNTROWS(fact_bahrain_changes))', PCT),
        ("Median Change", "MEDIAN(fact_bahrain_changes[change])", PCT),
    ]
    tables["fact_validation"].measures = [
        ("Checks", "COUNTROWS(fact_validation)", "0"),
        ("Checks Failed", 'CALCULATE(COUNTROWS(fact_validation), fact_validation[status] = "fail") + 0', "0"),
    ]


RELATIONSHIPS = [
    ("fact_products", "country", "dim_country", "country"),
    ("fact_products", "atc5", "dim_class", "atc5"),
    ("fact_competition", "country", "dim_country", "country"),
    ("fact_reference", "country", "dim_country", "country"),
    ("fact_validation", "country", "dim_country", "country"),
]


# ------------------------------------------------------------------------------------------------ writers
def write_csv(t: Table) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / f"{t.name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([c for c, _ in t.columns])
        for row in t.rows:
            out = []
            for v, (_, ty) in zip(row, t.columns):
                if v is None:
                    out.append("")
                elif ty == "dateTime":
                    out.append(v.isoformat())
                elif ty == "double":
                    out.append(repr(float(v)))
                else:
                    out.append(v)
            w.writerow(out)


_M_TYPES = {"string": "type text", "int64": "Int64.Type", "double": "type number", "dateTime": "type date"}


def tmdl_table(t: Table) -> str:
    L: list[str] = [f"table {t.name}", f"\tlineageTag: {_guid('table/' + t.name)}", ""]
    for name, dax, fmt in t.measures:
        qn = f"'{name}'" if any(c in name for c in " .=:'()") else name
        L.append(f"\tmeasure {qn} = {dax}")
        L.append(f"\t\tformatString: {fmt}")
        L.append(f"\t\tdisplayFolder: Measures")
        L.append(f"\t\tlineageTag: {_guid('measure/' + t.name + '/' + name)}")
        L.append("")
    for name, ty in t.columns:
        qn = f"'{name}'" if any(c in name for c in " .=:'()") else name
        L.append(f"\tcolumn {qn}")
        L.append(f"\t\tdataType: {ty}")
        if ty == "dateTime":
            L.append("\t\tformatString: mmm yyyy")
        elif ty == "int64":
            L.append("\t\tformatString: 0")
        L.append(f"\t\tlineageTag: {_guid('column/' + t.name + '/' + name)}")
        L.append("\t\tsummarizeBy: none")
        L.append(f"\t\tsourceColumn: {name}")
        L.append("")
    m_types = ", ".join(f'{{"{n}", {_M_TYPES[ty]}}}' for n, ty in t.columns)
    L += [
        f"\tpartition {t.name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "{t.name}.csv"), [Delimiter=",", Columns={len(t.columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{m_types}}}, \"en-US\")",
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(L)


def write_model(tables: list[Table]) -> None:
    defn = MODEL / "definition"
    (defn / "tables").mkdir(parents=True, exist_ok=True)
    (MODEL / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (MODEL / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "GCCMarketReport"},
        "config": {"version": "2.0", "logicalId": _guid("semantic-model")}}, indent=2), encoding="utf-8")
    (defn / "database.tmdl").write_text("database GCCMarketReport\n\tcompatibilityLevel: 1601\n", encoding="utf-8")
    refs = "\n".join(f"ref table {t.name}" for t in tables)
    (defn / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n"
        "\tsourceQueryCulture: en-US\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        f"{refs}\n\nref expression DataFolder\n", encoding="utf-8")
    data_dir = str(DATA).replace("/", "\\") + "\\"
    (defn / "expressions.tmdl").write_text(
        f'expression DataFolder = "{data_dir}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
        f"\tlineageTag: {_guid('expression/DataFolder')}\n\n"
        "\tannotation PBI_ResultType = Text\n", encoding="utf-8")
    rel = []
    for frm, fcol, to, tcol in RELATIONSHIPS:
        rel.append(f"relationship {_guid(f'rel/{frm}.{fcol}-{to}.{tcol}')}\n\tfromColumn: {frm}.{fcol}\n\ttoColumn: {to}.{tcol}\n")
    (defn / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")
    for t in tables:
        (defn / "tables" / f"{t.name}.tmdl").write_text(tmdl_table(t), encoding="utf-8")


# ---- report (PBIR)
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def colour(hex_: str) -> dict:
    return {"solid": {"color": lit(f"'{hex_}'")}}


def col_ref(table: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def meas_ref(table: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(field_: dict, table: str, prop: str, active: bool = True) -> dict:
    return {"field": field_, "queryRef": f"{table}.{prop}", "nativeQueryRef": prop, "active": active}


def C(table: str, prop: str, active: bool = False) -> dict:
    return proj(col_ref(table, prop), table, prop, active)


def cols(table: str, *props: str) -> list[dict]:
    """Table columns: each one active so every field is shown."""
    return [C(table, p_, True) for p_ in props]


def Mz(table: str, prop: str) -> dict:
    return proj(meas_ref(table, prop), table, prop)


@dataclass
class V:
    kind: str
    x: int
    y: int
    w: int
    h: int
    roles: dict[str, list[dict]] = field(default_factory=dict)
    title: str | None = None
    objects: dict | None = None
    sort: tuple[dict, str] | None = None
    text: list[tuple[str, str, str]] | None = None  # for textbox: (text, size, weight)
    pick: tuple[str, str, str] | None = None  # slicer default: (table, column, value)
    ignore: tuple[int, ...] = ()  # indexes of slicers on the page that must not filter this visual


def visual_json(page: str, i: int, v: V) -> dict:
    vis: dict = {"visualType": v.kind}
    if v.kind == "textbox":
        runs = [{"textRuns": [{"value": t, "textStyle": {"fontSize": s, "fontWeight": w, "color": INK}}]} for t, s, w in (v.text or [])]
        vis["objects"] = {"general": [{"properties": {"paragraphs": runs}}]}
    else:
        q: dict = {"queryState": {role: {"projections": ps} for role, ps in v.roles.items()}}
        if v.sort:
            q["sortDefinition"] = {"sort": [{"field": v.sort[0], "direction": v.sort[1]}]}
        vis["query"] = q
        if v.objects:
            vis["objects"] = v.objects
        vis["drillFilterOtherVisuals"] = True
    out: dict = {
        "$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json",
        "name": _oid(f"{page}/{i}"),
        "position": {"x": v.x, "y": v.y, "z": i, "height": v.h, "width": v.w, "tabOrder": i},
        "visual": vis,
    }
    if v.pick:
        tbl, colname, val = v.pick
        sel = {"Version": 2, "From": [{"Name": "d", "Entity": tbl, "Type": 0}],
               "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": colname}}],
                                               "Values": [[{"Literal": {"Value": f"'{val}'"}}]]}}}]}
        out["visual"].setdefault("objects", {})["general"] = [{"properties": {"filter": {"filter": sel}}}]
    if v.title:
        out["visual"]["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{v.title}'"), "fontSize": lit("12D"), "fontColor": colour(INK)}}]}
    return out


def bar_colour(c: str) -> dict:
    return {"dataPoint": [{"properties": {"fill": colour(c)}}]}


def series_colours(pairs: list[tuple[str, str]]) -> dict:
    return {"dataPoint": [{"properties": {"fill": colour(c)}, "selector": {"metadata": ref}} for ref, c in pairs]}


def pages() -> list[tuple[str, str, list[V]]]:
    P: list[tuple[str, str, list[V]]] = []
    country = lambda x, y, w=250, h=80: V("slicer", x, y, w, h, {"Values": [C("dim_country", "country", True)]},  # noqa: E731
                                          objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]}, title="Country")
    head = lambda text, sub: [V("textbox", 24, 6, 900, 52, text=[(text, "22pt", "bold")]), V("textbox", 24, 58, 940, 30, text=[(sub, "11pt", "normal")])]  # noqa: E731

    # 1. Overview
    P.append(("overview", "Overview", head("GCC market report: Saudi Arabia and Bahrain", "Registered products in the classes MSD competes in, from each regulator's public price list. Public prices, not sales.") + [
        country(990, 14),
        V("card", 24, 100, 300, 110, {"Values": [Mz("fact_products", "Products")]}, title="Products followed"),
        V("card", 340, 100, 300, 110, {"Values": [Mz("fact_products", "MSD Products")]}, title="MSD products"),
        V("card", 656, 100, 300, 110, {"Values": [Mz("fact_products", "Generic Versions")]}, title="Generic or other versions"),
        V("card", 972, 100, 284, 110, {"Values": [Mz("fact_products", "Companies")]}, title="Marketing companies"),
        V("clusteredBarChart", 24, 232, 620, 456, {"Category": [C("dim_class", "class_name", True)], "Y": [Mz("fact_products", "MSD Products"), Mz("fact_products", "Other Brands"), Mz("fact_products", "Generic Versions")]},
          title="Products by class: MSD, other brands, generics", sort=(meas_ref("fact_products", "Generic Versions"), "Descending"),
          objects=series_colours([("fact_products.MSD Products", TEAL), ("fact_products.Other Brands", SLATE), ("fact_products.Generic Versions", OCHRE)])),
        V("tableEx", 664, 232, 592, 456, {"Values": [*cols("dim_country", "country", "source"), Mz("fact_products", "Products"), Mz("fact_products", "MSD Products")]},
          title="Sources"),
    ]))

    # 2. Competition
    P.append(("competition", "Competition", head("How many versions compete with each MSD molecule", "Other versions of the same molecule (vaccines: the same vaccine class), and the cheapest generic's price per unit against MSD's.") + [
        country(990, 14),
        V("clusteredBarChart", 24, 100, 560, 588, {"Category": [C("fact_competition", "ingredient", True)], "Y": [Mz("fact_competition", "Generic Versions per Molecule")]},
          title="Generic or other versions per molecule", objects=bar_colour(OCHRE), sort=(meas_ref("fact_competition", "Generic Versions per Molecule"), "Descending")),
        V("tableEx", 600, 100, 656, 588, {"Values": [*cols("fact_competition", "country", "ingredient", "generic_or_other", "generic_companies", "msd_lowest_per_unit_usd", "cheapest_generic_per_unit_usd", "cheapest_generic_vs_msd")]},
          title="Competition per country and molecule", sort=(col_ref("fact_competition", "generic_or_other"), "Descending")),
    ]))

    # 3. Saudi vs Bahrain
    P.append(("gcc-prices", "Saudi vs Bahrain", head("The same MSD product in two countries", "Price per unit in US dollars; matched on brand, strengths, form, release and units per pack (vaccines per dose).") + [
        V("card", 24, 100, 300, 110, {"Values": [Mz("fact_gcc_prices", "Products Compared")]}, title="Products compared"),
        V("card", 340, 100, 300, 110, {"Values": [Mz("fact_gcc_prices", "Median Saudi vs Bahrain")]}, title="Median: Saudi price vs Bahrain"),
        V("card", 656, 100, 300, 110, {"Values": [Mz("fact_gcc_prices", "Saudi Cheaper")]}, title="Cheaper in Saudi Arabia"),
        V("clusteredBarChart", 24, 232, 620, 456, {"Category": [C("fact_gcc_prices", "product", True)], "Y": [Mz("fact_gcc_prices", "Median Saudi vs Bahrain")]},
          title="Saudi price per unit against Bahrain's", objects=bar_colour(TEAL), sort=(meas_ref("fact_gcc_prices", "Median Saudi vs Bahrain"), "Ascending")),
        V("tableEx", 664, 232, 592, 456, {"Values": [*cols("fact_gcc_prices", "brand", "strength", "saudi_per_unit_usd", "bahrain_per_unit_usd", "saudi_vs_bahrain", "note")]},
          title="Matched products", sort=(col_ref("fact_gcc_prices", "saudi_vs_bahrain"), "Ascending")),
    ]))

    # 4. US reference
    P.append(("reference", "US reference", head("What the US pays for the same tablet", "US pharmacy acquisition cost (NADAC) per tablet, over the GCC public price per tablet. Neither is a net price.") + [
        country(990, 14),
        V("clusteredBarChart", 24, 100, 620, 588, {"Category": [C("fact_reference", "brand", True)], "Y": [Mz("fact_reference", "US over GCC (median)")]},
          title="US price per tablet as a multiple of the GCC price", objects=bar_colour(RUST), sort=(meas_ref("fact_reference", "US over GCC (median)"), "Descending")),
        V("tableEx", 664, 100, 592, 588, {"Values": [*cols("fact_reference", "brand", "country", "gcc_product", "us_per_tablet_usd", "gcc_per_tablet_usd", "us_over_gcc")]},
          title="Same-strength tablets", sort=(col_ref("fact_reference", "us_over_gcc"), "Descending")),
    ]))

    # 5. Bahrain changes
    P.append(("changes", "Bahrain 2024 to 2026", head("Bahrain retail prices since the February 2024 repricing", "The 2024 innovator and generic price lists matched to the September 2026 list on the registration number.") + [
        V("card", 24, 100, 300, 110, {"Values": [Mz("fact_bahrain_changes", "Prices Matched")]}, title="Prices matched"),
        V("card", 340, 100, 300, 110, {"Values": [Mz("fact_bahrain_changes", "Share Unchanged")]}, title="Unchanged"),
        V("card", 656, 100, 300, 110, {"Values": [Mz("fact_bahrain_changes", "Median Change")]}, title="Median change"),
        V("columnChart", 24, 232, 420, 456, {"Category": [C("fact_bahrain_changes", "direction", True)], "Y": [Mz("fact_bahrain_changes", "Prices Matched")]},
          title="Products by direction of change", objects=bar_colour(TEAL)),
        V("tableEx", 460, 232, 796, 456, {"Values": [*cols("fact_bahrain_changes", "name", "list_2024", "price_feb_2024_bd", "price_sep_2026_bd", "change")]},
          title="Every matched product", sort=(col_ref("fact_bahrain_changes", "change"), "Descending")),
    ]))

    # 6. Data quality
    P.append(("quality", "Data quality", head("How far to trust it", "The validation gate that runs before the report is built, for each country's source.") + [
        country(990, 14),
        V("card", 24, 100, 300, 110, {"Values": [Mz("fact_validation", "Checks")]}, title="Checks"),
        V("card", 340, 100, 300, 110, {"Values": [Mz("fact_validation", "Checks Failed")]}, title="Failed"),
        V("tableEx", 24, 232, 1232, 456, {"Values": [*cols("fact_validation", "country", "id", "check", "status", "result")]}, title="Validation checks"),
    ]))
    return P


def write_report() -> None:
    d = REPORT / "definition"
    (REPORT / "StaticResources" / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    (REPORT / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "GCCMarketReport"},
        "config": {"version": "2.0", "logicalId": _guid("report")}}, indent=2), encoding="utf-8")
    (REPORT / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../GCCMarketReport.SemanticModel"}}}, indent=2), encoding="utf-8")

    theme = {
        "name": "GCCReport",
        "dataColors": [TEAL, OCHRE, SLATE, RUST, "#6FBFB2", "#8A7A4A", "#2D9C8B", "#B9B29E"],
        "background": PAPER, "foreground": INK, "tableAccent": TEAL,
        "textClasses": {"title": {"fontFace": "Georgia", "fontSize": 12, "color": INK}, "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": INK},
                        "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 28, "color": INK}},
        "visualStyles": {
            "*": {"*": {
                "background": [{"color": {"solid": {"color": PAPER}}, "transparency": 0}],
                "border": [{"show": False}],
                "title": [{"fontFamily": "Georgia", "fontSize": 12, "fontColor": {"solid": {"color": INK}}, "alignment": "left"}],
            }},
            "page": {"*": {"background": [{"color": {"solid": {"color": PAPER}}, "transparency": 0}]}},
        },
    }
    (REPORT / "StaticResources" / "RegisteredResources" / "GCCReport.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")

    (d / "pages").mkdir(parents=True, exist_ok=True)
    (d / "version.json").write_text(json.dumps({"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}, indent=2), encoding="utf-8")
    (d / "report.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {"name": "GCCReport.json", "reportVersionAtImport": {"visual": "2.0.0", "report": "3.0.0", "page": "2.0.0"}, "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "GCCReport.json", "path": "GCCReport.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    }, indent=2), encoding="utf-8")

    ps = pages()
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [_oid(k) for k, _, _ in ps], "activePageName": _oid(ps[0][0])}, indent=2), encoding="utf-8")
    for key, display, visuals in ps:
        pdir = d / "pages" / _oid(key)
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        page_json = {"$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": _oid(key), "displayName": display,
                     "displayOption": "FitToPage", "height": 720, "width": 1280}
        inter = [{"source": _oid(f"{key}/{j}"), "target": _oid(f"{key}/{i}"), "type": "NoFilter"}
                 for i, v in enumerate(visuals) for j in v.ignore]
        if inter:
            page_json["visualInteractions"] = inter
        (pdir / "page.json").write_text(json.dumps(page_json, indent=2), encoding="utf-8")
        for i, v in enumerate(visuals):
            vdir = pdir / "visuals" / _oid(f"{key}/{i}")
            vdir.mkdir(parents=True, exist_ok=True)
            (vdir / "visual.json").write_text(json.dumps(visual_json(key, i, v), indent=2), encoding="utf-8")


def main() -> int:
    tables = build_tables()
    by = {t.name: t for t in tables}
    add_measures(by)
    for t in tables:
        write_csv(t)
    write_model(tables)
    write_report()
    (PBI / "GCCMarketReport.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "GCCMarketReport.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    (PBI / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    n = sum(len(t.rows) for t in tables)
    print(f"wrote {len(tables)} tables ({n:,} rows), {sum(len(t.measures) for t in tables)} measures, {len(pages())} report pages to {PBI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
