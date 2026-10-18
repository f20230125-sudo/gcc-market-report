"""Month on month: what changed between two SFDA list snapshots.

    python -m gr.diff            (compares the two latest data/raw/sfda_drugs_list_*.json; writes data/marts/changes.csv)

New registrations, products no longer listed, and public price changes, matched on the SFDA id. With only one
snapshot it says so and writes an empty table, so the monthly job runs the same way from the first month on.
Because the list read can repeat and skip products (validation V03), a product missing from the new read is
reported as "not seen", not as withdrawn.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from gr.stage import RAW, MARTS, num

FIELDS = ["change", "id", "trade", "sci", "form", "old_price_sar", "new_price_sar", "change_pct"]


def compare(old: list[dict], new: list[dict]) -> list[dict]:
    o = {r["id"]: r for r in old if r.get("id")}
    n = {r["id"]: r for r in new if r.get("id")}
    out = []
    for i in sorted(n.keys() - o.keys()):
        r = n[i]
        out.append({"change": "new", "id": i, "trade": r["trade"], "sci": r["sci"], "form": r["form"], "old_price_sar": "", "new_price_sar": num(r["price"]), "change_pct": ""})
    for i in sorted(o.keys() - n.keys()):
        r = o[i]
        out.append({"change": "not seen", "id": i, "trade": r["trade"], "sci": r["sci"], "form": r["form"], "old_price_sar": num(r["price"]), "new_price_sar": "", "change_pct": ""})
    for i in sorted(o.keys() & n.keys()):
        a, b = num(o[i]["price"]), num(n[i]["price"])
        if a and b and abs(a - b) > 0.005:
            r = n[i]
            out.append({"change": "price", "id": i, "trade": r["trade"], "sci": r["sci"], "form": r["form"], "old_price_sar": a, "new_price_sar": b, "change_pct": round(b / a - 1, 4)})
    return out


def main() -> None:
    snaps = sorted(RAW.glob("sfda_drugs_list_*.json"))
    MARTS.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if len(snaps) < 2:
        print(f"one snapshot ({snaps[-1].name if snaps else 'none'}): nothing to compare yet")
    else:
        old = json.loads(snaps[-2].read_text(encoding="utf-8"))["records"]
        new = json.loads(snaps[-1].read_text(encoding="utf-8"))["records"]
        rows = compare(old, new)
        counts = {k: sum(1 for r in rows if r["change"] == k) for k in ("new", "not seen", "price")}
        print(f"{snaps[-2].name} -> {snaps[-1].name}: {counts}")
    with (MARTS / "changes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
