# GCC Market Report: Saudi Arabia

A monthly commercial reporting pipeline on **real GCC data**: the Saudi Food and Drug Authority's public Drugs List (8,207 registered products with public prices), staged into a central database behind a validation gate, harmonised into the therapy classes MSD competes in, and published as a report pack (an Excel workbook with live formulas, checked in Excel against Python).

It mirrors the data side of a Commercial Operations analyst role: prepare and validate the month's data sources, load them into one database, consolidate them into a report, and say what changed since last month. The data is prices and registrations, not sales: GCC sales by product are not public.

## What the first snapshot (18 October 2026) shows

- **Januvia and Janumet face 80 other sitagliptin products from 27 companies** in Saudi Arabia. The cheapest is **52% below** MSD's lowest price per tablet.
- **Bridion (sugammadex) faces 19 other versions from 14 companies**, the cheapest **35% cheaper** per vial.
- **Isentress** faces one other raltegravir product, 6.7% cheaper per tablet. **Pifeltro, Delstrigo, Keytruda, Welireg, Winrevair, Prevymis, Zerbaxa and Recarbrio** have no other version of the same molecule registered.
- **Vaccines:** Gardasil 9 costs SAR 605 a dose against SAR 266 for Cervarix; RotaTeq (SAR 199.55) and Rotarix (SAR 200.65) are priced almost the same; Vaxneuvance and Capvaxive compete with Prevenar and Synflorix.
- **The US pays far more than Saudi Arabia for the same tablet.** The US pharmacy acquisition cost (NADAC) per tablet is **11.7 times** the Saudi public price for Januvia 100 mg and Janumet 50/1,000 mg, 5.0 times for Pifeltro and 4.3 times for Delstrigo. Four MSD oral brands have no same-strength tablet in the Saudi list, and the report says so instead of comparing different strengths.

338 products in 37 ATC classes are followed: 35 MSD products, 51 other brands and 252 generic or other versions, from 77 marketing companies.

## How it works

```
SFDA Drugs List (459 pages) + detail pages (ATC, pack size, company, agent) + ingredient searches
   │   taken through a browser on the snapshot day; kept as dated raw files
   ▼
gr.stage    validation gate (11 checks) -> data/warehouse/gcc.duckdb (central database), quarantine.csv
gr.analyse  class positioning, generic and brand competition per MSD molecule, US reference pricing
gr.diff     month on month: new registrations, products not seen, price changes (matched on the SFDA id)
gr.workbook Excel report pack; tools/check_workbook.ps1 + gr.check_workbook recalculate it in Excel and compare with Python
```

- **Harmonisation.** Products are classed by the ATC code on their SFDA detail page. Within a molecule, a product is MSD's (by marketing company: Merck Sharp & Dohme, not Merck KGaA), an originator brand (a hand-written list per molecule) or a generic or other version. Vaccines are grouped by ATC class, because their scientific names vary too much to match ("G1 REASSORTANT..." is RotaTeq), and a competing vaccine counts as another brand, not a generic.
- **Price per unit** is the public pack price over the pack size. The riyal is pegged at 3.75 to the dollar; in the workbook the rate is a yellow input cell.
- **Reference pricing** compares only the same tablet: the same number of active ingredients, the MSD molecule's strength present and the same release form. Delstrigo's tenofovir is written 300 mg in the US and 245 mg in Saudi Arabia (the salt against the base), so only the first strength must match exactly.
- **The workbook** recalculates in Excel to the same values as Python: 768 values agree at 3.75 riyals per dollar, and they agree again at 4.10.

## Validation gate (first snapshot)

5 pass, 5 for review, 1 for information, 0 fail. The reviews are honest limits of a public website:

- **The list's order shifts while it is paged**, so reading all 459 pages gave 9,173 rows but only 8,208 distinct products (89.5%). Products in the followed classes were also searched by ingredient, which found 5 the list read had missed.
- 1 product has no SFDA id and is quarantined; 2 have no price; 1 is missing a name or form; 5 prices changed between the list read and the detail read minutes later.

## Run it

```powershell
python -m venv .venv; .venv\Scripts\pip install pandas duckdb openpyxl pydantic pytest
$env:PYTHONPATH = "src"
.venv\Scripts\python -m gr.stage; .venv\Scripts\python -m gr.analyse; .venv\Scripts\python -m gr.diff; .venv\Scripts\python -m gr.workbook
powershell -File tools\check_workbook.ps1 -Path excel\GCC-Market-Report.xlsx -Out xl.json -Rate 3.75; .venv\Scripts\python -m gr.check_workbook xl.json
.venv\Scripts\python -m pytest -q     # 8 tests
```

The raw snapshot files are committed, so everything after the browser step reproduces from this repository.

## Limits

- One country so far. Abu Dhabi's drug search sits behind a CAPTCHA and is not used; other GCC ministries publish price lists as news or PDFs, not as data.
- Public prices, not net prices or sales. The US figure is a pharmacy acquisition cost, not a net price either.
- An independent analysis of public data, not produced or endorsed by MSD or any company named.
