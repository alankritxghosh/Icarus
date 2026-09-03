import type { Metadata } from "next";
import "./globals.css";

const DESCRIPTION =
  "Ask why your code is the way it is. Icarus answers from your repository's own pull requests and issues, with citations, and says \"no one wrote this down\" when nobody did.";

export const metadata: Metadata = {
  metadataBase: new URL("https://try-icarus.vercel.app"),
  title: "Icarus — answers why your codebase is the way it is",
  description: DESCRIPTION,
  openGraph: {
    title: "Icarus — the engineering brain that won't bluff",
    description: DESCRIPTION,
    url: "https://try-icarus.vercel.app",
    siteName: "Icarus",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Icarus — the engineering brain that won't bluff",
    description: DESCRIPTION,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
