import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-serif/500.css";
import "@fontsource/ibm-plex-serif/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./globals.css";

export const metadata: Metadata = {
  // Share-image addresses are built from this; set NEXT_PUBLIC_SITE_URL to the real address when the site is published.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://gcc-market-report.vercel.app"),
  title: "GCC Market Report: MSD's products in the Saudi and Bahraini price lists",
  description:
    "The public medicine price lists of Saudi Arabia and Bahrain, validated, harmonised onto one classification and compared: generic competition for MSD's molecules, the same pack in both countries, US reference prices and Bahrain's price changes since 2024.",
  authors: [{ name: "Mohammad Uzair Khan" }],
};

export const viewport: Viewport = {
  themeColor: "#faf8f3",
  width: "device-width",
  initialScale: 1,
};

// Sets the theme before first paint so there is no flash: the saved choice, otherwise light.
const themeScript = `var t;try{t=localStorage.getItem("gcc-theme")}catch(e){}document.documentElement.setAttribute("data-theme",t==="dark"?"dark":"light")`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
