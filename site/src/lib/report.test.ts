import { describe, expect, it } from "vitest";
import { perUnit } from "@/components/Report";
import { loadReport } from "./load";

const r = loadReport();

describe("report data", () => {
  it("has both countries and the headline figures the page states", () => {
    expect(r.countries.map((c) => c.country).sort()).toEqual(["Bahrain", "Saudi Arabia"]);
    const sita = r.competition.filter((c) => c.ingredient === "SITAGLIPTIN");
    expect(sita.find((c) => c.country === "Saudi Arabia")!.generic).toBe(80);
    expect(sita.find((c) => c.country === "Bahrain")!.generic).toBe(31);
    expect(r.compared).toBe(r.msdPrices.filter((p) => p.saudiVsBahrain != null).length);
    expect(r.bahrainChanges.unchanged + r.bahrainChanges.rose + r.bahrainChanges.fell).toBe(r.bahrainChanges.matched);
    expect(r.bahrainChanges.moved).toHaveLength(r.bahrainChanges.rose + r.bahrainChanges.fell);
  });
  it("no check failed", () => {
    expect([...r.validation["Saudi Arabia"], ...r.validation.Bahrain].filter((c) => c.status === "fail")).toEqual([]);
  });
  it("a discount is the cheapest generic over MSD's lowest, minus one", () => {
    for (const c of r.competition.filter((x) => x.discount != null)) expect(c.discount!).toBeCloseTo(c.cheapestGeneric! / c.msdLowest! - 1, 3);
  });
});

describe("price formatting", () => {
  it("shows cents under $100 and whole dollars above", () => {
    expect(perUnit(0.4252)).toBe("$0.43");
    expect(perUnit(9665.92)).toBe("$9,666");
    expect(perUnit(null)).toBe("n/a");
  });
});
