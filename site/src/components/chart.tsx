"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

// Shared chart plumbing: measuring a box, a tooltip that works for pointer and keyboard, and the frame
// (title, view switch, legend, source line) every chart sits in.

export function useWidth<T extends HTMLElement>(initial = 640): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const apply = () => setW(Math.max(280, Math.floor(el.clientWidth)));
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export type TipRow = { label: string; value: string; color?: string };
export type TipState = { x: number; y: number; title: string; rows: TipRow[] } | null;

/** Tooltip state for one chart. `host` is the positioned element the tooltip lives in. */
export function useTip(host: RefObject<HTMLElement | null>) {
  const [tip, setTip] = useState<TipState>(null);
  const atPointer = useCallback(
    (title: string, rows: TipRow[]) => (e: { clientX: number; clientY: number }) => {
      const r = host.current?.getBoundingClientRect();
      if (!r) return;
      setTip({ x: e.clientX - r.left, y: e.clientY - r.top, title, rows });
    },
    [host],
  );
  const atElement = useCallback(
    (title: string, rows: TipRow[]) => (e: { currentTarget: Element }) => {
      const r = host.current?.getBoundingClientRect();
      if (!r) return;
      const b = e.currentTarget.getBoundingClientRect();
      setTip({ x: b.left + b.width / 2 - r.left, y: b.top - r.top, title, rows });
    },
    [host],
  );
  const hide = useCallback(() => setTip(null), []);
  return { tip, atPointer, atElement, hide };
}

export function Tip({ tip, width }: { tip: TipState; width: number }) {
  if (!tip) return null;
  const left = Math.min(Math.max(tip.x + 14, 4), Math.max(4, width - 200));
  return (
    <div className="tip" role="status" style={{ left, top: Math.max(tip.y - 12, 0), transform: "translateY(-100%)" }}>
      <b>{tip.title}</b>
      {tip.rows.map((r) => (
        <div className="row" key={r.label}>
          <span>
            {r.color && <i className="key" style={{ background: r.color }} />}
            {r.label}
          </span>
          <span>{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Frame({
  title,
  sub,
  legend,
  controls,
  view,
  onView,
  source,
  children,
  table,
  id,
}: {
  title: string;
  sub?: ReactNode;
  legend?: ReactNode;
  controls?: ReactNode;
  view?: "chart" | "table";
  onView?: (v: "chart" | "table") => void;
  source?: ReactNode;
  children: ReactNode;
  table: ReactNode;
  id?: string;
}) {
  const showTable = view === "table";
  return (
    <figure className="fig" id={id}>
      <div className="fig-head">
        <div>
          <h3>{title}</h3>
          {sub && <p className="sub">{sub}</p>}
        </div>
        {onView && (
          <div className="seg" role="group" aria-label={`${title}: view`}>
            <button type="button" aria-pressed={!showTable} onClick={() => onView("chart")}>
              Chart
            </button>
            <button type="button" aria-pressed={showTable} onClick={() => onView("table")}>
              Table
            </button>
          </div>
        )}
      </div>
      {controls}
      {!showTable && legend}
      {showTable ? (
        <div className="tbl-wrap" tabIndex={0} role="region" aria-label={`${title}: table`}>
          {table}
        </div>
      ) : (
        children
      )}
      {source && <figcaption className="src">{source}</figcaption>}
    </figure>
  );
}

export function useView(initial: "chart" | "table" = "chart"): ["chart" | "table", (v: "chart" | "table") => void] {
  return useState<"chart" | "table">(initial);
}

/** Shorten a label with an ellipsis so it fits in `px` pixels at roughly 6.4px a character. */
export function fit(s: string, px: number, charPx = 6.4): string {
  const max = Math.max(4, Math.floor(px / charPx));
  return s.length <= max ? s : `${s.slice(0, max - 1).trimEnd()}…`;
}

/** Round a maximum up to a clean axis end, and give clean ticks. */
export function niceTicks(max: number, count = 4): { top: number; ticks: number[] } {
  if (max <= 0) return { top: 1, ticks: [0, 1] };
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step / 1000; v += step) ticks.push(v);
  return { top, ticks };
}

/** Path for a bar with a rounded data end and a square baseline end. dir: "up" | "right" */
export function roundedBar(x: number, y: number, w: number, h: number, r: number, dir: "up" | "right"): string {
  const rr = Math.min(r, w / 2, h);
  if (h <= 0 || w <= 0) return "";
  if (dir === "up") {
    return `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${y + h} Z`;
  }
  const rb = Math.min(r, h / 2, w);
  return `M${x},${y} L${x + w - rb},${y} Q${x + w},${y} ${x + w},${y + rb} L${x + w},${y + h - rb} Q${x + w},${y + h} ${x + w - rb},${y + h} L${x},${y + h} Z`;
}
