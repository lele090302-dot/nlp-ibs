import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TL;DR Newsletter - AI-Curated. Human-Readable.",
  description:
    "The top 10 stories in tech, GenAI, and fintech - summarized by AI, delivered daily.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
      </head>
      <body>{children}</body>
    </html>
  );
}
