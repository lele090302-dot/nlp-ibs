"use client";

import { useState } from "react";

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "Topics",   href: "#topics"   },
  { label: "Stories",  href: "#stories"  },
];

type FooterStatus = "idle" | "loading" | "success" | "error";

export default function Footer() {
  const [email, setEmail]   = useState("");
  const [status, setStatus] = useState<FooterStatus>("idle");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: email.split("@")[0], // use email prefix as name fallback
          email: email.trim(),
          topics: ["GenAI", "Fintech", "Tech", "Startups", "Crypto"],
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
              AI-curated. Human-readable. The top 10 stories in tech, GenAI, and
              fintech - delivered daily.
            </p>

            {/* Social icons */}
            <div className="flex gap-4 mt-2">
              {[
                { label: "Twitter/X", path: "M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.737-8.835L2.25 2.25h6.844l4.262 5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z" },
                { label: "LinkedIn",  path: "M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-2-2 2 2 0 00-2 2v7h-4v-7a6 6 0 016-6zM2 9h4v12H2z M4 6a2 2 0 100-4 2 2 0 000 4z" },
              ].map(({ label, path }) => (
                <a
                  key={label}
                  href="#"
                  aria-label={label}
                  className="w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors duration-150"
                >
                  <svg className="w-4 h-4 fill-white" viewBox="0 0 24 24">
                    <path d={path} />
                  </svg>
                </a>
              ))}
            </div>
          </div>

          {/* Nav links */}
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

          {/* Email signup */}
          <div>
            <p className="font-sans text-xs font-semibold uppercase tracking-widest text-white/50 mb-5">
              Stay in the loop
            </p>
            {status === "success" ? (
              <p className="font-sans text-sm text-white/80">
                ✓ You&apos;re subscribed. See you tomorrow morning.
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
            Built with AI. Curated for humans.
          </p>
        </div>
      </div>
    </footer>
  );
}
