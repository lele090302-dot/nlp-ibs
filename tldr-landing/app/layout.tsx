import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TL;DR Newsletter - AI-Curated. Human-Readable.",
  description:
    "The top 10 stories in tech, GenAI, and fintech - summarized by AI, delivered daily.",
  icons: {
    icon: { url: "/favicon.svg", type: "image/svg+xml" },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
