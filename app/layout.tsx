import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Procurement Copilot | L1 AI Helpdesk",
  description: "Multi-agent GenAI helpdesk over procurement policy docs and spend/PO data",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
