"use client";

import { useState } from "react";

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "Choose your topics", href: "#form" },
  { label: "Stories", href: "#stories" },
  { label: "Market Pulse", href: "#market-pulse" },
];

type FooterStatus = "idle" | "loading" | "success" | "error";

export default function Footer() {
  const [email, setEmail]   = useState("");
  const [status, setStatus] = useState<FooterStatus>("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !email.includes("@")) return;

    setStatus("loading");
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: email.split("@")[0],
          email: email.trim(),
          topics: ["Generative AI", "Fintech", "Tech", "Startups", "Crypto"],
          frequency: "daily",
        }),
      });
      setStatus(res.ok ? "success" : "error");
    } catch {
      setStatus("error");
    }
  };

  return (
    <footer className="bg-terracotta text-white">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid md:grid-cols-3 gap-12">

          {/* Brand */}
          <div className="flex flex-col gap-4">
            <div>
              <span className="font-serif font-bold text-2xl tracking-tight">TL;DR</span>
              <span className="block text-white/60 font-sans text-xs uppercase tracking-widest mt-0.5">
                Newsletter
              </span>
            </div>
            <p className="font-sans text-sm text-white/70 leading-relaxed max-w-xs">
              AI-curated. Human-readable. The top stories in tech, GenAI, and
              fintech, startups and crypto - delivered daily.
            </p>
          </div>

          {/* Nav links - matching header */}
          <div>
            <p className="font-sans text-xs font-semibold uppercase tracking-widest text-white/50 mb-5">
              Navigation
            </p>
            <ul className="flex flex-col gap-3">
              {navLinks.map(({ label, href }) => (
                <li key={label}>
                  <a
                    href={href}
                    className="font-sans text-sm text-white/80 hover:text-white transition-colors duration-150"
                  >
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Quick subscribe */}
          <div>
            <p className="font-sans text-xs font-semibold uppercase tracking-widest text-white/50 mb-2">
              Don&apos;t miss a beat
            </p>
            <p className="font-sans text-sm text-white/70 mb-4">
              Subscribe to all topics instantly.
            </p>
            {status === "success" ? (
              <p className="font-sans text-sm text-white/90">
                You&apos;re in. See you tomorrow morning.
              </p>
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="bg-white/10 border border-white/20 rounded-full px-5 py-3 text-sm font-sans
                             text-white placeholder:text-white/40 focus:outline-none focus:ring-2
                             focus:ring-white/30 transition"
                />
                {status === "error" && (
                  <p className="text-xs font-sans text-white/70">Something went wrong. Try again.</p>
                )}
                <button
                  type="submit"
                  disabled={status === "loading"}
                  className="bg-white text-terracotta font-sans font-semibold text-sm rounded-full
                             px-6 py-3 hover:bg-cream transition-colors duration-150 active:scale-95
                             disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {status === "loading" ? "Subscribing..." : "Subscribe Free"}
                </button>
              </form>
            )}
          </div>

        </div>

        {/* Bottom bar */}
        <div className="border-t border-white/20 mt-12 pt-6 flex flex-col sm:flex-row justify-between gap-2">
          <p className="font-sans text-xs text-white/40">
            © {new Date().getFullYear()} TL;DR Newsletter. All rights reserved.
          </p>
          <p className="font-sans text-xs text-white/40">
            Transforms raw news streams into personalized intelligence.
          </p>
        </div>
      </div>
    </footer>
  );
}
