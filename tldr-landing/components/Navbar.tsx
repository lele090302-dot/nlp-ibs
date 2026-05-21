"use client";

import { useState } from "react";

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-cream/90 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <a href="#" className="flex items-center gap-2 group">
          <span className="text-terracotta font-serif font-bold text-xl tracking-tight">
            TL;DR
          </span>
          <span className="text-muted font-sans text-xs uppercase tracking-widest mt-0.5">
            Newsletter
          </span>
        </a>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          {["Features", "Topics", "Stories"].map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase()}`}
              className="text-sm font-sans text-muted hover:text-charcoal transition-colors duration-150"
            >
              {item}
            </a>
          ))}
        </div>

        {/* CTA */}
        <div className="hidden md:block">
          <a href="#hero-form" className="btn-primary text-sm py-2 px-5">
            Subscribe Free
          </a>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-charcoal"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {menuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden bg-cream border-t border-border px-6 py-4 flex flex-col gap-4">
          {["Features", "Topics", "Stories"].map((item) => (
            <a
              key={item}
              href={`#${item.toLowerCase()}`}
              className="text-sm font-sans text-charcoal"
              onClick={() => setMenuOpen(false)}
            >
              {item}
            </a>
          ))}
          <a href="#hero-form" className="btn-primary text-sm text-center" onClick={() => setMenuOpen(false)}>
            Subscribe Free
          </a>
        </div>
      )}
    </nav>
  );
}
