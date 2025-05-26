"use client";

import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";

function current(): Theme {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// The theme lives on <html data-theme>, outside React, so the button subscribes to it instead of copying it into state.
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", onChange);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, current, () => null);
  const flip = () => {
    const next: Theme = current() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("gcc-theme", next);
    } catch {
      /* storage can be blocked; the choice then lasts for this visit only */
    }
  };
  return (
    <button type="button" className="btn theme" onClick={flip}>
      {theme === "dark" ? "Light" : theme === "light" ? "Dark" : "Theme"}
      {theme && <span className="hide-xs"> theme</span>}
    </button>
  );
}
