import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Claim to Fame — live",
  description: "Insurance capital, opponents, and what the pipeline is doing right now",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body className="antialiased">{children}</body></html>;
}
