import fs from "node:fs";
import path from "node:path";
import type { Report } from "./types";

/** Reads the report at build time; a file without what the page needs fails the build with the reason. */
export function loadReport(): Report {
  const r = JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", "data", "report.json"), "utf-8")) as Report;
  const problems = [
    r.countries?.length !== 2 && "two countries",
    !r.competition?.length && "competition rows",
    !r.msdPrices?.length && "MSD prices",
    !r.reference?.length && "reference prices",
    !r.bahrainChanges?.matched && "Bahrain changes",
    !(r.validation?.["Saudi Arabia"]?.length && r.validation?.Bahrain?.length) && "validation for both countries",
  ].filter(Boolean);
  if (problems.length) throw new Error(`report.json is missing: ${problems.join(", ")}`);
  return r;
}
