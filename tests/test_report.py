import csv

import pandas as pd
import pytest

from gr import analyse, diff, stage

MARTS = stage.MARTS


def test_number_parsing():
    assert stage.num("94.75") == 94.75
    assert stage.num("1,361.80") == 1361.80
    assert stage.num("") is None


def test_roles():
    assert analyse.role("JANUVIA 100MG F.C. TABLETS", "SITAGLIPTIN PHOSPHATE", "MERCK SHARP & DOHME") == "MSD"
    assert analyse.role("GALVUS 50MG", "VILDAGLIPTIN", "Novartis Pharma AG") == "Originator"
    assert analyse.role("SITAGLO 100MG", "SITAGLIPTIN", "Jamjoom Pharma") == "Generic or other"
    # Merck KGaA is a different company and must not be read as MSD.
    assert analyse.role("GLUCOPHAGE", "METFORMIN", "Merck Serono") == "Generic or other"


def test_every_msd_brand_has_an_originator_entry():
    cp = pd.read_csv(MARTS / "class_position.csv", keep_default_na=False)
    msd = cp[cp.role == "MSD"]
    assert len(msd) > 0
    assert (msd.ingredient != "").all()


def test_price_per_unit_is_price_over_pack():
    cp = pd.read_csv(MARTS / "class_position.csv", keep_default_na=False)
    r = cp[cp.trade == "JANUVIA 100MG F.C. TABLETS"].iloc[0]
    assert r.pack_size == 28 and r.price_sar == pytest.approx(94.75)
    assert r.price_per_unit_sar == pytest.approx(94.75 / 28)
    assert r.price_per_unit_usd == pytest.approx(94.75 / 28 / 3.75)


def test_generic_pressure_on_sitagliptin():
    gp = pd.read_csv(MARTS / "generic_pressure.csv", keep_default_na=False)
    s = gp[gp.ingredient == "SITAGLIPTIN"].iloc[0]
    assert s.generic_or_other >= 50
    assert float(s.cheapest_vs_msd) < 0


def test_reference_pricing_matches_same_strength_only():
    rp = pd.read_csv(MARTS / "reference_pricing.csv", keep_default_na=False)
    j = rp[rp.brand == "JANUMET"].iloc[0]
    assert "1000,50" in j.ksa_product and " XR" not in j.ksa_product
    i = rp[rp.brand == "ISENTRESS"].iloc[0]
    assert i.ksa_product.startswith("no same-strength")  # only 600 mg is registered in Saudi Arabia
    jan = rp[rp.brand == "JANUVIA"].iloc[0]
    assert float(jan.us_vs_ksa) == pytest.approx(float(jan.us_nadac_per_tablet_usd) / (94.75 / 28 / 3.75))


def test_validation_has_no_failures():
    rows = list(csv.DictReader((MARTS / "validation.csv").open(encoding="utf-8")))
    assert len(rows) == 11
    assert [r["id"] for r in rows if r["status"] == "fail"] == []


def test_month_on_month_diff():
    old = [{"id": "1", "trade": "A", "sci": "X", "form": "Tablet", "price": "10.00"}, {"id": "2", "trade": "B", "sci": "Y", "form": "Tablet", "price": "5"}]
    new = [{"id": "1", "trade": "A", "sci": "X", "form": "Tablet", "price": "9.00"}, {"id": "3", "trade": "C", "sci": "Z", "form": "Vial", "price": "100"}]
    out = {r["change"]: r for r in diff.compare(old, new)}
    assert out["new"]["id"] == "3"
    assert out["not seen"]["id"] == "2"
    assert out["price"]["change_pct"] == pytest.approx(-0.1)
    assert diff.compare(old, old) == []
