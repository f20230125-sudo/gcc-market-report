import csv

import pandas as pd
import pytest

from gr import analyse, bahrain, diff, gcc, stage

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
    assert "1000,50" in j.saudi_product and "XR" not in j.saudi_product
    i = rp[rp.brand == "ISENTRESS"].iloc[0]
    assert i.saudi_product.startswith("no same-strength")  # only 600 mg is registered in Saudi Arabia
    assert i.bahrain_product.startswith("ISENTRESS 400")  # Bahrain has the US strength
    jan = rp[rp.brand == "JANUVIA"].iloc[0]
    assert float(jan.us_vs_saudi) == pytest.approx(float(jan.us_nadac_per_tablet_usd) / (94.75 / 28 / 3.75))
    assert float(jan.us_vs_bahrain) == pytest.approx(float(jan.us_nadac_per_tablet_usd) / (15.06 / 28 / 0.376))


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


@pytest.mark.parametrize("raw,units", [("30", 30), ("10 X 2ML", 10), ("1 + 1", 1), ("10 +10", 10), ("3 (2 X 80MG + 1 X 125MG)", 3), ("4ML", 1), ("0.5ML", 1), ("30G", 1), ("1 X 0.5ML", 1), ("28 TABLETS", 28), ("BLISTER", None), (None, None)])
def test_bahrain_units_per_pack(raw, units):
    assert bahrain.units_per_pack(raw) == units


def test_bahrain_classification_and_spelling_fixes():
    atc = {"DORAVIRINE": "J05AG", "SITAGLIPTIN": "A10BH"}
    assert bahrain.classify("DELSTRIGO", "DORAVIRIN + LAMIVUDINE + TINOFOVIR", "MERCK SHARP & DOHME BV", atc) == ("DORAVIRINE", "J05AG", "MSD")
    assert bahrain.classify("GARDASIL 9", None, "MERCK SHARP & DOHME LLC, USA.", atc) == ("HPV vaccines", "J07BM", "MSD")
    assert bahrain.classify("CERVARIX", None, "GLAXOSMITHKLINE", atc)[2] == "Originator"
    assert bahrain.classify("SITAGLO", "SITAGLIPTIN", "LOCAL PHARMA", atc) == ("SITAGLIPTIN", "A10BH", "Generic or other")


def test_brand_names_are_harmonised():
    assert gcc.brand("KETRUDA SC") == "KEYTRUDA SC"
    assert gcc.brand("M.M.R II 0.5ML VACCINE") == gcc.brand("M-M-R II VACCINE") == "M-M-R II"
    assert gcc.brand("JANUMET XR") == "JANUMET XR"
    assert gcc.brand("JANUVIA 100MG F.C. TABLETS") == "JANUVIA"
    assert gcc.strengths("1000/50") == gcc.strengths("1000,50") == gcc.strengths("50-1,000") == (50.0, 1000.0)


def test_cross_country_matches_are_one_to_one_or_set_aside():
    mp = pd.read_csv(MARTS / "gcc_msd_prices.csv", keep_default_na=False)
    compared = mp[mp.note == ""]
    assert len(compared) >= 20
    assert set(mp[mp.note != ""].brand) == {"BRIDION"}  # two Saudi vial sizes that SFDA does not tell apart
    j = compared[(compared.brand == "JANUVIA") & (compared.strength.astype(str) == "100")].iloc[0]
    assert float(j.saudi_vs_bahrain) == pytest.approx((94.75 / 28 / 3.75) / (15.06 / 28 / 0.376) - 1)
    assert {"GARDASIL 9", "ROTATEQ", "M-M-R II", "VAXNEUVANCE"} <= set(compared.brand)


def test_bahrain_price_changes_since_2024():
    ch = pd.read_csv(MARTS / "bahrain_changes.csv", keep_default_na=False)
    assert len(ch) == 267 and ch.reg_no.is_unique
    lantus = ch[ch.name.str.startswith("LANTUS SOLOSTAR")].iloc[0]
    assert float(lantus.change) == pytest.approx(30.79 / 23.89 - 1)
