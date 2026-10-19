# GCC Market Report: Saudi Arabia and Bahrain

A monthly commercial reporting pipeline on **real GCC data**: two regulators' public medicine price lists, prepared and validated each month, loaded into one central database, harmonised onto one classification, and published as a Power BI report and an Excel pack with a quarterly forecast entry sheet.

It mirrors the data side of a Commercial Operations analyst role at a pharmaceutical company in the Gulf: prepare and validate the month's data sources before they reach the central database, consolidate them into reports, keep the quarterly forecast inputs ready for the team, and say what changed since the last period. The data is prices and registrations, not sales: GCC sales by product are not public.

## Sources

| Country | Source | What it holds |
| --- | --- | --- |
| Saudi Arabia | SFDA public Drugs List (snapshot 18 Oct 2026), its detail pages and its ingredient search | 8,207 registered products with public prices in riyals; ATC code, pack size, marketing company and agent for 338 products in MSD's classes |
| Bahrain | NHRA Registered Medicine Price List (7 Sep 2026), and the Innovator and Generics price lists of 18 Feb 2024 | 5,560 products with retail prices in dinars, pack size, active substance and authorisation holder; 280 prices from 2024 |
| United States | NADAC per tablet, from Drug Price Watch | the reference for international price comparison |

## What it shows

- **Sitagliptin is where MSD faces the most generics.** Saudi Arabia registers 80 other sitagliptin products from 27 companies, the cheapest 52% below Januvia and Janumet's lowest price per tablet; Bahrain has 31 from 12, the cheapest 26% below. Sugammadex (Bridion) has 19 other versions in Saudi Arabia and 5 in Bahrain, 35% and 41% cheaper.
- **The same MSD product usually costs about 3.5% less in Saudi Arabia than in Bahrain**, consistent with GCC price alignment. The exceptions are large: Janumet 42% less, Januvia 100 mg 37% less, Keytruda 25% less, Capvaxive 16% less. Of 25 products matched in both countries, 20 are cheaper in Saudi Arabia (median 5% cheaper).
- **The US pays several times the GCC price for the same tablet**: about 12 times the Saudi price for Januvia and Janumet (7 times Bahrain's), about 5 times for Pifeltro, 4 times for Delstrigo, and 1.7 times Bahrain's price for Isentress 400 mg, a strength Saudi Arabia does not register.
- **Vaccines:** Gardasil 9 costs $161 a dose in Saudi Arabia and $177 in Bahrain, against $71 for Cervarix in Saudi Arabia; RotaTeq and Rotarix are priced almost the same.
- **Bahrain's prices barely moved after its February 2024 repricing:** of 267 products still listed, 247 (92.5%) are unchanged, 18 rose (Lantus up 29% to 34%, Zovirax up 63%) and 2 fell (Actemra about 19%).

## How it works

```
SFDA list + detail pages + ingredient search (through a browser)     NHRA price lists 2026 and 2024 (xlsx downloads)
            │                                                                      │
gr.stage   validation gate, 11 checks ──┐                         gr.bahrain   validation, 11 checks
            ▼                           ▼                                          ▼
                     data/warehouse/gcc.duckdb  (the central database: sfda_list, sfda_detail, bh_list, bh_list_2024)
                                              │
gr.analyse  Saudi classes, competition, US reference        gr.gcc  both countries on one classification:
gr.diff     month on month: new, not seen, price changes             products, MSD prices in both, competition, Bahrain changes
                                              │
gr.workbook  Excel pack with live formulas, quarterly forecast entry and summary      gr.powerbi  Power BI project (PBIP), 6 pages, 19 measures
tools/check_workbook.ps1 + gr.check_workbook (in Excel)                                 tools/check_powerbi_engine.ps1 + gr.check_powerbi (in Power BI's engine)
```

**Harmonisation** is most of the work:

- **One classification for two countries.** SFDA gives each product an ATC code; Bahrain does not. A Bahrain product is classed through its active substance, using the class SFDA gives the same molecule.
- **Spelling.** Bahrain writes doravirine as "DORAVIRIN", tenofovir as "TINOFOVIR" and Keytruda subcutaneous as "KETRUDA SC"; the MMR vaccine is "M.M.R II" in one register and "M-M-R II" in the other. Each fix is listed in code and counted by a check.
- **Pack sizes.** Bahrain writes them as free text ("10 X 2ML", "1 + 1", "3 (2 X 80MG + 1 X 125MG)"); a parser reads units per pack for 98.2% of products and leaves the rest unknown rather than guessing.
- **Matching the same product.** Two countries' packs are compared only when brand, strengths, form, release and units per pack all agree, and only one to one. Bridion is set aside: Saudi Arabia lists 2 ml and 5 ml vials that its list does not tell apart. Vaccines are compared per dose, on the brand.
- **Roles.** Within a molecule, a product is MSD's (Merck Sharp & Dohme, not Merck KGaA), an originator brand, or a generic or other version; a competing vaccine is another brand, not a generic.

## The quarterly forecast entry sheet

`Forecast input` in the workbook lists every MSD product in both countries. The team types the units it expects per quarter of 2027 and, if any, the quarter a first generic launches; the price per unit comes from the Products sheet and the exchange rate from Inputs, and revenue after a generic launch follows the median brand retention measured in Rx Market Pulse (77% of pre-entry revenue in the first quarter, 46% by the fourth), itself an input. `Forecast summary` adds it up by country and brand.

## Checked, not assumed

- **Excel:** `tools/check_workbook.ps1` opens the pack in Excel, sets the rates, types a test forecast into every row, recalculates, and `gr.check_workbook` recomputes everything in Python: **1,857 values agree**, at 3.75 SAR and 0.376 BHD to the dollar and again at 4.10 and 0.40.
- **Power BI:** `tools/check_powerbi_engine.ps1` opens the project in Power BI Desktop, refreshes it through the engine Desktop runs (the Tabular object model and ADOMD client that ship with Desktop), and evaluates every measure in DAX; `gr.check_powerbi` compares: **all 8 tables load and 194 values agree**. This check found a real bug: "cheapest generic vs MSD" read -100% where there is no generic, because a blank minus 1 is -1 in DAX.
- **Tests:** 24 pytest tests: parsers, harmonisation, matching rules, the month-on-month diff and the published figures.

## Validation

Saudi Arabia: 5 pass, 5 for review, 1 for information. Reading SFDA's list page by page gave 9,173 rows but only 8,208 distinct products (the order shifts between pages), so the followed molecules are also searched by ingredient; 1 product without an id is quarantined, 2 have no price, 5 prices changed between two reads minutes apart. Bahrain: 6 pass, 5 for information, including the 7 MSD products outside the followed classes (Cancidas, Enflonsia, Esmeron, Invanz, Noxafil, Temodal, Vaqta).

## Run it

```powershell
python -m venv .venv; .venv\Scripts\pip install pandas duckdb openpyxl pydantic pytest
$env:PYTHONPATH = "src"
.venv\Scripts\python -m gr.stage; .venv\Scripts\python -m gr.analyse; .venv\Scripts\python -m gr.bahrain; .venv\Scripts\python -m gr.gcc
.venv\Scripts\python -m gr.diff; .venv\Scripts\python -m gr.workbook; .venv\Scripts\python -m gr.powerbi
powershell -File tools\check_workbook.ps1 -Path excel\GCC-Market-Report.xlsx -Out xl.json; .venv\Scripts\python -m gr.check_workbook xl.json
powershell -File tools\check_powerbi_engine.ps1 -Pbip powerbi\GCCMarketReport.pbip -Out pbi.json; .venv\Scripts\python -m gr.check_powerbi pbi.json
.venv\Scripts\python -m pytest -q
```

Open `powerbi/GCCMarketReport.pbip` in Power BI Desktop and press Refresh once (the project carries no data cache). The data folder is an absolute path set when the project is generated; regenerate it after moving the repository.

## Limits

- Two of six GCC countries. The UAE's price list is a paid service, Abu Dhabi's drug search sits behind a CAPTCHA, and Oman, Kuwait and Qatar publish price changes as news or PDFs rather than data.
- Public prices, not net prices, and no sales volumes; the forecast sheet takes units from the team.
- An independent analysis of public data, not produced or endorsed by MSD or any company named.
