"use client";

import { useState } from "react";
import type { Check, Country, Report as R } from "@/lib/types";
import { pct, signedPct } from "@/lib/format";
import { Bars, type Bar } from "./Bars";
import { Fig } from "./Fig";
import { ThemeToggle } from "./ThemeToggle";

const SECTIONS = [
  { id: "competition", label: "Competition" },
  { id: "prices", label: "Saudi vs Bahrain" },
  { id: "reference", label: "US reference" },
  { id: "changes", label: "Bahrain 2024 to 2026" },
  { id: "quality", label: "Data quality" },
  { id: "method", label: "Method" },
];
const STATUS_WORD = { pass: "Pass", warn: "Review", fail: "Fail", info: "Info" } as const;
const COUNTRIES: Country[] = ["Saudi Arabia", "Bahrain"];

/** Price per unit in dollars: two decimals under $100, whole dollars above. */
export function perUnit(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "n/a";
  return v < 100 ? `$${v.toFixed(2)}` : `$${Math.round(v).toLocaleString("en-US")}`;
}
const times = (v: number | null | undefined) => (v == null ? "n/a" : `${v.toFixed(1)}×`);
/** "SITAGLIPTIN" -> "Sitagliptin", "JANUMET XR" -> "Janumet XR", "M-M-R II" stays: only plain words longer than three letters are recased. */
export const title = (s: string) => s.replace(/\b[A-Z]{4,}\b/g, (w) => w.charAt(0) + w.slice(1).toLowerCase());
const FORM_SHORT = (f: string) => (/infusion/i.test(f) ? "infusion" : /tablet/i.test(f) ? "tablets" : /inject/i.test(f) ? "injection" : f.toLowerCase());
const dateLabel = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

function StatusGlyph({ s }: { s: Check["status"] }) {
  // Shape carries the meaning, not colour: a tick, a ring with a bar, a cross, a ring with a dot.
  const d = { pass: "M3 8.5l3 3 7-7", warn: "M8 4v5", fail: "M4 4l8 8M12 4l-8 8", info: "M8 7v5" }[s];
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      {s !== "pass" && s !== "fail" && <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.3" />}
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      {s === "warn" && <circle cx="8" cy="11.6" r="1" fill="currentColor" />}
      {s === "info" && <circle cx="8" cy="4.6" r="1" fill="currentColor" />}
    </svg>
  );
}

export function Report({ r, repoUrl }: { r: R; repoUrl?: string }) {
  const [country, setCountry] = useState<Country>("Saudi Arabia");
  const sa = r.competition.find((c) => c.country === "Saudi Arabia" && c.ingredient === "SITAGLIPTIN")!;
  const bh = r.competition.find((c) => c.country === "Bahrain" && c.ingredient === "SITAGLIPTIN")!;
  const msdCount = (c: Country) => r.countries.find((x) => x.country === c)!;

  const contested = r.competition.filter((c) => c.country === country && c.generic + c.otherBrands > 0).sort((a, b) => b.generic + b.otherBrands - (a.generic + a.otherBrands));
  const compRows: Bar[] = contested.map((c) => ({
    label: title(c.ingredient),
    value: c.generic + c.otherBrands,
    tone: c.generic ? "ink" : "mute",
    text: c.generic ? `${c.generic} ${c.generic === 1 ? "version" : "versions"}, cheapest ${signedPct(c.discount)}` : `${c.otherBrands} other ${c.otherBrands === 1 ? "brand" : "brands"}`,
    tip: [
      { label: "Generic or other versions", value: `${c.generic} from ${c.genericCompanies} ${c.genericCompanies === 1 ? "company" : "companies"}` },
      { label: "MSD lowest per unit", value: perUnit(c.msdLowest) },
      { label: "Cheapest generic per unit", value: perUnit(c.cheapestGeneric) },
      { label: "Other brands", value: String(c.otherBrands) },
    ],
  }));
  const compMax = Math.max(...compRows.map((x) => x.value));

  const compared = r.msdPrices.filter((p) => p.saudiVsBahrain != null).sort((a, b) => a.saudiVsBahrain! - b.saudiVsBahrain!);
  // Packs that share a brand and strength are told apart by form, then by units per pack (Winrevair's 1- and 2-vial kits).
  const base = (p: (typeof compared)[number]) => `${title(p.brand)} ${p.strength.length > 10 ? "" : p.strength}`.trim();
  const priceLabel = (p: (typeof compared)[number]) => {
    const same = compared.filter((q) => base(q) === base(p));
    let l = base(p);
    if (new Set(same.map((q) => FORM_SHORT(q.form))).size > 1) l += ` ${FORM_SHORT(p.form)}`;
    else if (new Set(same.map((q) => q.units)).size > 1 && p.units) l += ` x${p.units}`;
    return l;
  };
  const priceRows: Bar[] = compared.map((p) => ({
    label: priceLabel(p),
    value: p.saudiVsBahrain!,
    tone: "msd",
    text: signedPct(p.saudiVsBahrain, 0),
    tip: [
      { label: "Form", value: p.form },
      { label: "Saudi Arabia per unit", value: perUnit(p.saudi) },
      { label: "Bahrain per unit", value: perUnit(p.bahrain) },
    ],
  }));
  const notCompared = r.msdPrices.filter((p) => p.saudiVsBahrain == null && p.note);

  const refRows: Bar[] = r.reference.flatMap((x) => [
    ...(x.usVsSaudi != null ? [{ label: `${title(x.brand)}, Saudi Arabia`, value: x.usVsSaudi, tone: "ink" as const, text: times(x.usVsSaudi) }] : []),
    ...(x.usVsBahrain != null ? [{ label: `${title(x.brand)}, Bahrain`, value: x.usVsBahrain, tone: "mute" as const, text: times(x.usVsBahrain) }] : []),
  ]);
  const ch = r.bahrainChanges;

  return (
    <>
      <a className="skip" href="#main">
        Skip to the report
      </a>
      <header className="bar">
        <div className="shell bar-in">
          <a className="brand" href="#top">
            GCC Market Report
          </a>
          <nav aria-label="Sections">
            {SECTIONS.map((x) => (
              <a key={x.id} href={`#${x.id}`}>
                {x.label}
              </a>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </header>

      <main id="main" className="shell">
        <section className="hero" id="top">
          <p className="kicker">
            <b>GCC Market Report</b> · a commercial data analysis case study by Mohammad Uzair Khan, on the public medicine price lists of Saudi Arabia and Bahrain
          </p>
          <h1>
            Sitagliptin is where MSD meets the most generics: {sa.generic} in Saudi Arabia, the cheapest {pct(-sa.discount!)} below Januvia&rsquo;s lowest price per tablet, and {bh.generic} in Bahrain
          </h1>
          <p className="lede">
            Two regulators&rsquo; price lists, {r.sources.saudiProducts.toLocaleString("en-US")} Saudi and {r.sources.bahrainProducts.toLocaleString("en-US")} Bahraini products, are validated each month, loaded into one database,
            put on one classification and compared: who competes with MSD&rsquo;s {msdCount("Saudi Arabia").msd} Saudi and {msdCount("Bahrain").msd} Bahraini products, what the same pack costs in each country, what the US
            pays for the same tablet, and what changed since Bahrain repriced in 2024. The data is prices and registrations, not sales.
          </p>
          <dl className="figs">
            <div>
              <dt>Products in MSD&rsquo;s classes</dt>
              <dd>
                {msdCount("Saudi Arabia").products} Saudi · {msdCount("Bahrain").products} Bahrain
              </dd>
            </div>
            <div>
              <dt>MSD packs matched in both</dt>
              <dd>
                {r.compared}, {r.comparedCheaperInSaudi} cheaper in Saudi Arabia
              </dd>
            </div>
            <div>
              <dt>Bahrain prices unchanged since Feb 2024</dt>
              <dd>
                {ch.unchanged} of {ch.matched} ({pct(ch.unchanged / ch.matched, 1)})
              </dd>
            </div>
            <div>
              <dt>Checks before loading</dt>
              <dd>
                {r.validation["Saudi Arabia"].length + r.validation.Bahrain.length}, none failed
              </dd>
            </div>
          </dl>
        </section>

        <section className="sec" id="competition" aria-labelledby="competition-h">
          <div className="sec-head">
            <h2 id="competition-h">Competition: where MSD&rsquo;s molecules have other versions</h2>
            <p className="dek">
              Within each molecule a product is MSD&rsquo;s, another originator brand, or a generic or other version. A competing vaccine counts as another brand, not a generic. Molecules where MSD is the only
              product are in the table.
            </p>
          </div>
          <div className="ctl" style={{ marginBottom: 14 }}>
            <div className="seg" role="group" aria-label="Country">
              {COUNTRIES.map((c) => (
                <button key={c} type="button" aria-pressed={c === country} onClick={() => setCountry(c)}>
                  {c}
                </button>
              ))}
            </div>
          </div>
          <Fig
            title={`${country}: other products per MSD molecule`}
            sub="Generic or other versions (solid) and competing brands (light). Hover a bar for MSD's lowest and the cheapest generic price per unit."
            source={
              <>
                Source: SFDA Drugs List ({dateLabel(r.snapshots.saudi)}) and NHRA Registered Medicine Price List ({dateLabel(r.snapshots.bahrain)}). Price per unit (tablet, vial, dose) in US dollars at{" "}
                {r.rates.sarPerUsd} SAR and {r.rates.bhdPerUsd} BHD to the dollar.
              </>
            }
            table={
              <table className="tbl">
                <caption className="sr-only">Competition per MSD molecule, both countries</caption>
                <thead>
                  <tr>
                    <th scope="col">Molecule or class</th>
                    <th scope="col">Country</th>
                    <th scope="col" className="n">
                      MSD products
                    </th>
                    <th scope="col" className="n">
                      MSD lowest per unit
                    </th>
                    <th scope="col" className="n">
                      Other brands
                    </th>
                    <th scope="col" className="n">
                      Generic or other
                    </th>
                    <th scope="col" className="n">
                      Companies
                    </th>
                    <th scope="col" className="n">
                      Cheapest generic
                    </th>
                    <th scope="col" className="n">
                      vs MSD
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {r.competition.map((c) => (
                    <tr key={`${c.ingredient}-${c.country}`}>
                      <th scope="row">{title(c.ingredient)}</th>
                      <td>{c.country}</td>
                      <td className="n">{c.msdProducts}</td>
                      <td className="n">{perUnit(c.msdLowest)}</td>
                      <td className="n">{c.otherBrands}</td>
                      <td className="n">{c.generic}</td>
                      <td className="n">{c.genericCompanies}</td>
                      <td className="n">{c.cheapestGeneric == null ? "" : perUnit(c.cheapestGeneric)}</td>
                      <td className="n">{c.discount == null ? "" : signedPct(c.discount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <Bars
              rows={compRows}
              label={200}
              ariaLabel={`${country}: ${compRows.map((x) => `${x.label}, ${x.text}`).join("; ")}.`}
              tickFormat={(v) => String(v)}
              ticks={compMax > 40 ? [0, 20, 40, 60, 80] : [0, 5, 10, 15, 20, 25, 30]}
            />
          </Fig>
        </section>

        <section className="sec" id="prices" aria-labelledby="prices-h">
          <div className="sec-head">
            <h2 id="prices-h">
              The same MSD pack costs a median {pct(-r.comparedMedian)} less in Saudi Arabia than in Bahrain; {r.comparedCheaperInSaudi} of {r.compared} are cheaper there
            </h2>
            <p className="dek">
              Packs are compared only when brand, strengths, form, release and units per pack all agree, one to one. Vaccines are compared per dose. Most differences are a few percent, consistent with GCC price
              alignment; the exceptions are large.
            </p>
          </div>
          <Fig
            title="Saudi price per unit against Bahrain's, same MSD pack"
            sub="Left of zero: cheaper in Saudi Arabia. Hover a bar for both prices."
            source={<>Source: SFDA and NHRA price lists; public retail prices, not net prices.{notCompared.length ? ` Not compared: ${notCompared.map((n) => `${title(n.brand)}, ${n.note.replace(/^not compared: /, "")}`).join("; ")}.` : ""}</>}
            table={
              <table className="tbl">
                <caption className="sr-only">MSD products priced in both countries</caption>
                <thead>
                  <tr>
                    <th scope="col">Brand</th>
                    <th scope="col">Strength</th>
                    <th scope="col">Form</th>
                    <th scope="col" className="n">
                      Saudi Arabia
                    </th>
                    <th scope="col" className="n">
                      Bahrain
                    </th>
                    <th scope="col" className="n">
                      Saudi vs Bahrain
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {r.msdPrices.map((p, i) => (
                    <tr key={`${p.brand}-${i}`}>
                      <th scope="row">{title(p.brand)}</th>
                      <td>{p.strength}</td>
                      <td>{p.form}</td>
                      <td className="n">{perUnit(p.saudi)}</td>
                      <td className="n">{perUnit(p.bahrain)}</td>
                      <td className="n">{p.saudiVsBahrain == null ? "not compared" : signedPct(p.saudiVsBahrain)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <Bars rows={priceRows} label={170} ariaLabel={`Saudi against Bahrain price per unit: ${priceRows.map((x) => `${x.label} ${x.text}`).join("; ")}.`} tickFormat={(v) => signedPct(v)} ticks={[-0.4, -0.2, 0]} />
          </Fig>
        </section>

        <section className="sec" id="reference" aria-labelledby="reference-h">
          <div className="sec-head">
            <h2 id="reference-h">The US pays several times the GCC price for the same tablet</h2>
            <p className="dek">
              US price: the National Average Drug Acquisition Cost per tablet, from Drug Price Watch. A brand appears where the same strength is registered in that country. Acquisition cost is not net price in
              either market.
            </p>
          </div>
          <Fig
            title="US price per tablet as a multiple of the GCC price"
            sub="Dark: against Saudi Arabia. Light: against Bahrain."
            source={<>Source: CMS NADAC (US), SFDA and NHRA price lists.</>}
            table={
              <table className="tbl">
                <caption className="sr-only">US reference prices</caption>
                <thead>
                  <tr>
                    <th scope="col">Brand</th>
                    <th scope="col">US pack</th>
                    <th scope="col" className="n">
                      US per tablet
                    </th>
                    <th scope="col" className="n">
                      Saudi per tablet
                    </th>
                    <th scope="col" className="n">
                      US ÷ Saudi
                    </th>
                    <th scope="col" className="n">
                      Bahrain per tablet
                    </th>
                    <th scope="col" className="n">
                      US ÷ Bahrain
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {r.reference.map((x) => (
                    <tr key={x.brand}>
                      <th scope="row">{title(x.brand)}</th>
                      <td>{x.usPack}</td>
                      <td className="n">{perUnit(x.us)}</td>
                      <td className="n">{x.saudi == null ? "not registered" : perUnit(x.saudi)}</td>
                      <td className="n">{x.usVsSaudi == null ? "" : times(x.usVsSaudi)}</td>
                      <td className="n">{x.bahrain == null ? "not registered" : perUnit(x.bahrain)}</td>
                      <td className="n">{x.usVsBahrain == null ? "" : times(x.usVsBahrain)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <Bars rows={refRows} label={190} ariaLabel={`US price as a multiple of the GCC price: ${refRows.map((x) => `${x.label} ${x.text}`).join("; ")}.`} tickFormat={(v) => `${v}×`} ticks={[0, 4, 8, 12]} />
          </Fig>
        </section>

        <section className="sec" id="changes" aria-labelledby="changes-h">
          <div className="sec-head">
            <h2 id="changes-h">
              Bahrain&rsquo;s prices barely moved after its February 2024 repricing: {ch.unchanged} of {ch.matched} unchanged
            </h2>
            <p className="dek">
              Products in the {dateLabel(r.snapshots.bahrain2024)} innovator and generics lists matched to the {dateLabel(r.snapshots.bahrain)} list by registration number. {ch.rose} rose and {ch.fell} fell by more
              than half a percent; they are all listed.
            </p>
          </div>
          <div className="tbl-wrap" tabIndex={0} role="region" aria-label="Bahrain price changes: table">
            <table className="tbl">
              <caption>Every Bahrain price that moved, 2024 to 2026, in dinars</caption>
              <thead>
                <tr>
                  <th scope="col">Product</th>
                  <th scope="col">Strength</th>
                  <th scope="col">Pack</th>
                  <th scope="col" className="n">
                    2024
                  </th>
                  <th scope="col" className="n">
                    2026
                  </th>
                  <th scope="col" className="n">
                    Change
                  </th>
                </tr>
              </thead>
              <tbody>
                {ch.moved.map((m, i) => (
                  <tr key={`${m.name}-${i}`}>
                    <th scope="row">{m.name}</th>
                    <td>{m.strength}</td>
                    <td>{m.pack}</td>
                    <td className="n">{m.before.toFixed(2)}</td>
                    <td className="n">{m.after.toFixed(2)}</td>
                    <td className="n">{signedPct(m.change)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="sec" id="quality" aria-labelledby="quality-h">
          <div className="sec-head">
            <h2 id="quality-h">Checked before it reaches the database</h2>
            <p className="dek">
              Each month&rsquo;s files pass a validation gate before they are loaded. A review is not a failure: it names what a person should look at, such as rows that could not be traced or prices that changed
              between two reads.
            </p>
          </div>
          <div className="pair even">
            {COUNTRIES.map((c) => (
              <div className="qgroup" key={c}>
                <h3>{c}</h3>
                <ul className="qlist">
                  {r.validation[c].map((x) => (
                    <li className="qrow" key={x.id}>
                      <span className="st">
                        <StatusGlyph s={x.status} />
                        {STATUS_WORD[x.status]}
                      </span>
                      <span>
                        <span className="nm">{x.check}</span>
                        <span className="rs">
                          {x.result} · rule: {x.rule}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <section className="sec" id="method" aria-labelledby="method-h">
          <div className="sec-head">
            <h2 id="method-h">Method, downloads and limits</h2>
          </div>
          <ol className="method">
            <li>
              <b>Prepare and validate.</b> The SFDA list, its detail pages (ATC code, pack size, company, agent) and its ingredient search; the NHRA 2026 list and its 2024 innovator and generics lists. Each
              passes 11 checks; rows that cannot be traced are quarantined, not loaded.
            </li>
            <li>
              <b>One database.</b> Both countries load into one DuckDB warehouse, and each month is compared with the last: new products, products no longer listed, price changes.
            </li>
            <li>
              <b>Harmonise.</b> Bahrain has no ATC codes, so a product takes the class SFDA gives the same molecule. Spellings are fixed in code and counted (&ldquo;DORAVIRIN&rdquo;, &ldquo;TINOFOVIR&rdquo;,
              &ldquo;KETRUDA SC&rdquo;). Free-text pack sizes (&ldquo;10 X 2ML&rdquo;, &ldquo;1 + 1&rdquo;) are parsed into units per pack, or left unknown rather than guessed.
            </li>
            <li>
              <b>Report.</b> An Excel pack with live formulas and a quarterly forecast entry sheet (the team types units and a generic launch quarter; revenue follows the measured brand retention), checked in Excel
              (1,857 values agree with Python at two exchange-rate settings). A six-page Power BI report, refreshed in Power BI Desktop&rsquo;s engine with every measure compared to Python (194 values agree).
            </li>
          </ol>
          <p className="downloads">
            <a className="btn" href="/downloads/GCC-Market-Report.xlsx" download>
              Download the Excel pack (.xlsx)
            </a>
            {repoUrl && (
              <a className="btn" href={`${repoUrl}/tree/main/powerbi`}>
                Power BI project on GitHub
              </a>
            )}
          </p>
          <p className="limits">
            <b>Limits.</b> Two of six GCC countries: the UAE&rsquo;s price list is a paid service, Abu Dhabi&rsquo;s drug search sits behind a CAPTCHA, and Oman, Kuwait and Qatar publish price changes as news or
            PDFs. Public retail prices, not net prices, and no sales volumes. An independent analysis of public data, not produced or endorsed by MSD or any company named.
          </p>
        </section>
      </main>

      <footer className="foot">
        <div className="shell">
          <p className="disc">
            Built by Mohammad Uzair Khan · {repoUrl ? <a href={repoUrl}>Code on GitHub</a> : "Code on GitHub"} · Saudi list read {dateLabel(r.snapshots.saudi)}
          </p>
        </div>
      </footer>
    </>
  );
}
