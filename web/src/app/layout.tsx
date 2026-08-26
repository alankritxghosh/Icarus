import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Icarus — answers why your codebase is the way it is",
  description:
    "Ask why your code is the way it is. Icarus answers from your repository's own pull requests and issues, with citations, and says \"no one wrote this down\" when nobody did.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
