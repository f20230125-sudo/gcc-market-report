"use client";

import type { ReactNode } from "react";
import { Frame, useView } from "./chart";

/** A figure with a Chart / Table switch. A client component so the page itself can be rendered at build time. */
export function Fig({
  title,
  sub,
  legend,
  source,
  table,
  children,
  id,
  start = "chart",
}: {
  title: string;
  sub?: ReactNode;
  legend?: ReactNode;
  source?: ReactNode;
  table: ReactNode;
  children: ReactNode;
  id?: string;
  start?: "chart" | "table";
}) {
  const [view, setView] = useView(start);
  return (
    <Frame id={id} title={title} sub={sub} legend={legend} source={source} view={view} onView={setView} table={table}>
      {children}
    </Frame>
  );
}
