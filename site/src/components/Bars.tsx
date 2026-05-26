"use client";

import { scaleLinear } from "d3-scale";
import { fit, Tip, useTip, useWidth, type TipRow } from "./chart";

export type Bar = { label: string; sub?: string; value: number; text: string; tone?: "msd" | "ink" | "mute"; tip?: TipRow[] };

/**
 * Horizontal bars with a label column. Values may be negative (a diverging chart around zero); the zero line is drawn.
 * One labelled image: the table view behind every chart carries the same numbers for a screen reader.
 */
export function Bars({ rows, label, ariaLabel, tickFormat, ticks }: { rows: Bar[]; label?: number; ariaLabel: string; tickFormat: (v: number) => string; ticks: number[] }) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const { tip, atPointer, hide } = useTip(ref);
  const lab = Math.min(label ?? 200, Math.round(w * 0.36));
  const row = 30;
  const h = rows.length * row + 26;
  const lo = Math.min(0, ...rows.map((r) => r.value), ...ticks);
  const hi = Math.max(0, ...rows.map((r) => r.value), ...ticks);
  // Room on the right for the longest value label, up to 45% of the width; a longer label is shortened to fit.
  const right = Math.min(Math.round(w * 0.45), Math.max(50, Math.max(...rows.map((r) => r.text.length)) * 6.6 + 12));
  const x = scaleLinear().domain([lo, hi]).range([lab + (lo < 0 ? 44 : 0), w - right]);
  return (
    <div ref={ref} style={{ position: "relative" }} onMouseLeave={hide}>
      <svg className="svg" width={w} height={h} role="img" aria-label={ariaLabel}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={x(t)} x2={x(t)} y1={0} y2={h - 22} />
            <text x={x(t)} y={h - 6} textAnchor="middle" className="t-mute">
              {tickFormat(t)}
            </text>
          </g>
        ))}
        <line className="base" x1={x(0)} x2={x(0)} y1={0} y2={h - 22} />
        {rows.map((r, i) => {
          const y = i * row + 4;
          const x0 = x(Math.min(0, r.value));
          const x1 = x(Math.max(0, r.value));
          const neg = r.value < 0;
          return (
            <g key={`${r.label}-${i}`} onMouseMove={r.tip ? atPointer(r.label, r.tip) : undefined}>
              <rect x={0} y={y - 2} width={w} height={row - 2} fill="transparent" />
              <text x={0} y={y + 15} className="t-strong">
                {fit(r.label, lab - 8)}
              </text>
              <rect x={x0} y={y + 4} width={Math.max(1, x1 - x0)} height={16} rx={1.5} className={`bar-${r.tone ?? "ink"}`} />
              <text x={neg ? x0 - 6 : x1 + 6} y={y + 16} textAnchor={neg ? "end" : "start"}>
                {neg ? r.text : fit(r.text, w - x1 - 8)}
              </text>
            </g>
          );
        })}
      </svg>
      <Tip tip={tip} width={w} />
    </div>
  );
}
