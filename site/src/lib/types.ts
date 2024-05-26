export type Country = "Saudi Arabia" | "Bahrain";
export type CountrySummary = { country: Country; products: number; msd: number; generic: number; otherBrands: number; companies: number };
export type Competition = {
  country: Country;
  ingredient: string;
  msdProducts: number;
  msdLowest: number | null;
  otherBrands: number;
  generic: number;
  genericCompanies: number;
  cheapestGeneric: number | null;
  discount: number | null;
};
export type MsdPrice = { brand: string; strength: string; form: string; ingredient: string; units: number | null; saudi: number | null; bahrain: number | null; saudiVsBahrain: number | null; note: string };
export type Reference = {
  brand: string;
  usPack: string;
  us: number;
  saudiProduct: string | null;
  saudi: number | null;
  usVsSaudi: number | null;
  bahrainProduct: string | null;
  bahrain: number | null;
  usVsBahrain: number | null;
};
export type PriceMove = { name: string; strength: string; pack: string; before: number; after: number; change: number; holder: string };
export type Check = { id: string; check: string; status: "pass" | "warn" | "fail" | "info"; result: string; rule: string };

export type Report = {
  snapshots: { saudi: string; bahrain: string; bahrain2024: string };
  sources: { saudiProducts: number; saudiDetailed: number; bahrainProducts: number };
  rates: { sarPerUsd: number; bhdPerUsd: number };
  countries: CountrySummary[];
  competition: Competition[];
  msdPrices: MsdPrice[];
  compared: number;
  comparedCheaperInSaudi: number;
  comparedMedian: number;
  reference: Reference[];
  bahrainChanges: { matched: number; unchanged: number; rose: number; fell: number; moved: PriceMove[] };
  validation: Record<Country, Check[]>;
};
