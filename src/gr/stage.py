"""Stage the monthly SFDA snapshot into the central database, behind a validation gate.

    python -m gr.stage          (reads data/raw/*.json, writes data/warehouse/gcc.duckdb and data/marts/validation.csv)

A snapshot is the Saudi Food and Drug Authority's public Drugs List (trade name, scientific name, strength,
dosage form, public price in SAR) taken on one day, plus detail pages (registration number, ATC code, pack
size, marketing company, local agent) for the products in the therapy classes this report follows. Each
snapshot keeps its date, so a later month can be compared with this one (gr.diff).

The gate: every check has a status; a "fail" stops the report from being built.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "warehouse" / "gcc.duckdb"
MARTS = ROOT / "data" / "marts"


def num(s: str | None) -> float | None:
    if s is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


def latest(pattern: str) -> Path:
    files = sorted(RAW.glob(pattern))
    if not files:
        raise SystemExit(f"no raw file matching {pattern} in {RAW}")
    return files[-1]


def snapshot_date(p: Path) -> str:
    return re.search(r"(\d{4}-\d{2}-\d{2})", p.name).group(1)


def load() -> tuple[str, list[dict], dict, list[dict], dict]:
    lp = latest("sfda_drugs_list_*.json")
    dp = latest("sfda_class_details_*.json")
    lst = json.loads(lp.read_text(encoding="utf-8"))
    det = json.loads(dp.read_text(encoding="utf-8"))
    if "rows" in det:  # the compact form: one array per product, named by "fields"
        f = det["fields"]
        det["records"] = [
            {"id": r[0], "trade": r[1], "sci": r[2], "strength": r[3], "form": r[4], "price": r[5], "via": r[6], "detail": {k: v for k, v in zip(f[7:], r[7:]) if v}}
            for r in det["rows"]
        ]
    return snapshot_date(lp), lst["records"], lst, det["records"], det


def main() -> None:
    snap, rows, lst, det, detmeta = load()
    checks: list[dict] = []

    def add(cid, name, status, result, rule):
        checks.append({"id": cid, "check": name, "status": status, "result": result, "rule": rule})

    # 1. The list itself
    quarantined = [r for r in rows if not r.get("id")]
    rows = [r for r in rows if r.get("id")]
    ids = [r["id"] for r in rows]
    add("V01", "List rows without an SFDA id are quarantined", "pass" if not quarantined else "warn", f"{len(quarantined)} quarantined ({', '.join(q['trade'] for q in quarantined[:3])})", "a row without a details link cannot be traced; it is kept aside, not loaded")
    add("V02", "Ids are unique after de-duplication", "pass" if len(set(ids)) == len(ids) else "fail", f"{len(ids):,} rows, {len(set(ids)):,} ids", "one row per id")
    (MARTS).mkdir(parents=True, exist_ok=True)
    with (MARTS / "quarantine.csv").open("w", newline="", encoding="utf-8") as qf:
        qw = csv.writer(qf)
        qw.writerow(["trade", "sci", "strength", "form", "price", "reason"])
        for q in quarantined:
            qw.writerow([q["trade"], q["sci"], q["strength"], q["form"], q["price"], "no SFDA id (no details link)"])
    expected = lst["pages"] * 20
    coverage = lst["unique"] / lst["rows_seen"]
    add(
        "V03",
        "Share of the list's rows that are distinct products",
        "warn" if coverage < 0.98 else "pass",
        f"{lst['unique']:,} distinct of {lst['rows_seen']:,} rows read ({coverage:.1%}); {lst['pages']} pages of up to 20 ({expected:,})",
        "the list's order shifts between pages, so a page read later can repeat products and skip others; class products are filled in by searching each ingredient (V08)",
    )
    prices = [num(r["price"]) for r in rows]
    bad_price = sum(1 for p in prices if p is None or p <= 0)
    add("V04", "Every product has a positive public price", "pass" if bad_price == 0 else "warn", f"{bad_price} without", "price > 0 SAR")
    missing = sum(1 for r in rows if not r["trade"] or not r["sci"] or not r["form"])
    add("V05", "Trade name, scientific name and dosage form are filled", "pass" if missing == 0 else "warn", f"{missing} rows missing one", "0")

    # 2. The detail pages for the followed classes
    with_detail = [r for r in det if r.get("detail")]
    errors = [r for r in det if r.get("detail_error")]
    add("V06", "Detail pages read for every followed product", "pass" if not errors else "warn", f"{len(with_detail)} read, {len(errors)} failed", "0 failures")
    no_atc = [r["trade"] for r in with_detail if not r["detail"].get("ATC Code 1")]
    add("V07", "Followed products carry an ATC code", "pass" if len(no_atc) <= len(with_detail) * 0.05 else "warn", f"{len(no_atc)} without ({', '.join(no_atc[:4])}{'...' if len(no_atc) > 4 else ''})", "at most 5% without")
    from_search = sum(1 for r in det if str(r.get("via", "")).startswith("search:"))
    add("V08", "Products found only by the ingredient search, not in the list read", "info", f"{from_search}", "the list read missed them (see V03)")
    pack = [num(r["detail"].get("Package Size")) for r in with_detail]
    add("V09", "Pack size known for followed products", "pass" if sum(1 for p in pack if p) >= len(with_detail) * 0.9 else "warn", f"{sum(1 for p in pack if p)} of {len(with_detail)}", "at least 90%, needed for price per unit")
    detail_ids = {r["id"] for r in det}
    price_mismatch = 0
    by_id = {r.get("id"): r for r in rows if r.get("id")}
    for r in det:
        lr = by_id.get(r["id"])
        if lr and num(lr["price"]) != num(r["price"]):
            price_mismatch += 1
    add("V10", "List price equals the price read again with the details", "pass" if price_mismatch == 0 else "warn", f"{price_mismatch} differ", "0 (the two reads were minutes apart)")

    # 3. Load the central database
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("create or replace table sfda_list (snapshot date, id varchar, trade varchar, sci varchar, strength varchar, form varchar, price_sar double)")
    con.executemany(
        "insert into sfda_list values (?, ?, ?, ?, ?, ?, ?)",
        [(snap, r.get("id"), r["trade"], r["sci"], r["strength"], r["form"], num(r["price"])) for r in rows],
    )
    con.execute(
        """create or replace table sfda_detail (snapshot date, id varchar, reg_no varchar, trade varchar, sci varchar, strength varchar,
        strength_unit varchar, form varchar, route varchar, pack_size double, price_sar double, legal_status varchar, distribution varchar,
        marketing_company varchar, marketing_country varchar, agent varchar, manufacturers varchar, atc varchar, status varchar, found_by varchar)"""
    )
    con.executemany(
        "insert into sfda_detail values (" + ",".join(["?"] * 20) + ")",
        [
            (
                snap, r["id"], d.get("Register Number"), r["trade"], r["sci"], d.get("Strength") or r["strength"], d.get("Strength Unit"), d.get("Dosage Form") or r["form"],
                d.get("Route of Administration"), num(d.get("Package Size")), num(r["price"]), d.get("Legal Status"), d.get("Distribution Site"),
                d.get("Marketing Company"), d.get("Country of marketing company"), d.get("Agents"), d.get("Manufacturers"), (d.get("ATC Code 1") or "").strip() or None,
                d.get("Authorization Status"), r.get("via") or "list",
            )
            for r in det
            for d in [r.get("detail") or {}]
        ],
    )
    n_list = con.execute("select count(*) from sfda_list").fetchone()[0]
    n_det = con.execute("select count(*) from sfda_detail").fetchone()[0]
    add("V11", "Database holds every staged row", "pass" if (n_list, n_det) == (len(rows), len(det)) else "fail", f"list {n_list:,}, details {n_det:,}", "rows in = rows loaded")
    con.close()

    MARTS.mkdir(parents=True, exist_ok=True)
    with (MARTS / "validation.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0]))
        w.writeheader()
        w.writerows(checks)
    for c in checks:
        print(f"{c['id']} {c['status']:5} {c['check']}: {c['result']}")
    if any(c["status"] == "fail" for c in checks):
        raise SystemExit("validation failed: the report is not built")
    print(f"snapshot {snap} staged; {len(detail_ids)} followed products")


if __name__ == "__main__":
    main()
