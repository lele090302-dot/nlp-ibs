"use client";

import { useEffect, useState } from "react";
import type { StocksResponse } from "@/app/api/stocks/route";

type Tab = "holdings" | "sectors";

// Shown while loading or if the API call fails entirely
const FALLBACK_HOLDINGS = [
  { ticker: "NVDA",  name: "Nvidia",     weight: 7.78, price: "1,208.42", changePercent: "+3.21%", up: true  },
  { ticker: "AAPL",  name: "Apple",      weight: 6.64, price:   "213.07", changePercent: "-0.38%", up: false },
  { ticker: "MSFT",  name: "Microsoft",  weight: 4.97, price:   "427.15", changePercent: "+1.04%", up: true  },
  { ticker: "AMZN",  name: "Amazon",     weight: 4.23, price:   "198.63", changePercent: "+0.87%", up: true  },
  { ticker: "GOOGL", name: "Alphabet",   weight: 3.62, price:   "178.22", changePercent: "+1.55%", up: true  },
  { ticker: "META",  name: "Meta",       weight: 3.10, price:   "521.40", changePercent: "+2.10%", up: true  },
  { ticker: "TSLA",  name: "Tesla",      weight: 1.97, price:   "172.83", changePercent: "-1.44%", up: false },
  { ticker: "BRKB",  name: "Berkshire",  weight: 1.74, price:   "448.90", changePercent: "+0.33%", up: true  },
  { ticker: "AVGO",  name: "Broadcom",   weight: 1.72, price: "1,842.10", changePercent: "+1.78%", up: true  },
  { ticker: "JPM",   name: "JPMorgan",   weight: 1.38, price:   "238.55", changePercent: "-0.22%", up: false },
];

const FALLBACK_SECTORS = [
  { sector: "Information Technology", weight: 31.4 },
  { sector: "Financials",             weight: 13.7 },
  { sector: "Health Care",            weight: 11.6 },
  { sector: "Consumer Discretionary", weight: 10.5 },
  { sector: "Communication Services", weight:  9.1 },
  { sector: "Industrials",            weight:  8.3 },
  { sector: "Consumer Staples",       weight:  5.8 },
  { sector: "Energy",                 weight:  3.4 },
  { sector: "Real Estate",            weight:  2.3 },
  { sector: "Materials",              weight:  2.2 },
  { sector: "Utilities",              weight:  2.1 },
];

export default function StockTicker() {
  const [data, setData]       = useState<StocksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]         = useState<Tab>("holdings");

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);

    fetch("/api/stocks", { signal: controller.signal })
      .then((r) => r.json())
      .then((d: StocksResponse) => setData(d))
      .catch(() => {/* silently fall through to fallback */})
      .finally(() => { clearTimeout(timer); setLoading(false); });

    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  const isLive     = data?.source === "Twelve Data";
  const marketOpen = data?.marketOpen ?? false;
  const holdings   = data?.holdings ?? FALLBACK_HOLDINGS;
  const sectors    = data?.sectors  ?? FALLBACK_SECTORS;

  const formatPct = (pct: string, up: boolean) => {
    if (pct === "N/A") return "-";
    // Strip any existing + then re-add based on direction
    const clean = pct.replace(/^[+-]/, "");
    return up ? `+${clean}` : `-${clean}`;
  };

  return (
    <div className="rounded-2xl border border-border bg-white shadow-card overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-5 pb-3 flex items-start justify-between gap-2">
        <div>
          <p className="font-sans text-xs font-semibold uppercase tracking-widest text-terracotta">
            SPY Market Pulse
          </p>
          <p className="font-serif text-base text-charcoal mt-0.5">S&amp;P 500 ETF</p>
        </div>

        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-1.5">
            {isLive && (
              <span className={`w-1.5 h-1.5 rounded-full ${
                marketOpen ? "bg-emerald-500 animate-pulse" : "bg-amber-400"
              }`} />
            )}
            <span className={`text-xs font-sans px-2 py-0.5 rounded-full border ${
              isLive
                ? marketOpen
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
                : "bg-blush text-muted border-border"
            }`}>
              {isLive
                ? marketOpen ? "Market Open" : "Market Closed"
                : loading ? "Loading..." : "Indicative"}
            </span>
          </div>
          {data?.lastUpdated && (
            <span className="text-[10px] font-sans text-muted">
              Updated {new Date(data.lastUpdated).toLocaleTimeString([], {
                hour: "2-digit", minute: "2-digit",
              })}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border mx-5">
        {(["holdings", "sectors"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`text-xs font-sans font-medium pb-2 mr-5 border-b-2 transition-colors duration-150
              ${tab === t
                ? "border-terracotta text-terracotta"
                : "border-transparent text-muted hover:text-charcoal"
              }`}
          >
            {t === "holdings" ? "Top 10 Holdings" : "Sector Weights"}
          </button>
        ))}
      </div>

      {/* Loading skeleton */}
      {loading && (
        <ul className="divide-y divide-border">
          {Array.from({ length: 5 }).map((_, i) => (
            <li key={i} className="flex items-center justify-between px-5 py-3">
              <div className="flex items-center gap-2.5">
                <div className="w-11 h-5 bg-blush rounded-md animate-pulse" />
                <div className="w-20 h-3 bg-blush rounded animate-pulse" />
              </div>
              <div className="w-14 h-4 bg-blush rounded animate-pulse" />
            </li>
          ))}
        </ul>
      )}

      {/* Holdings tab */}
      {!loading && tab === "holdings" && (
        <ul className="divide-y divide-border">
          {holdings.map(({ ticker, name, weight, price, changePercent, up }) => (
            <li
              key={ticker}
              className="flex items-center justify-between px-5 py-2.5 hover:bg-blush/30 transition-colors duration-100"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="w-11 shrink-0 text-center text-[11px] font-sans font-bold text-charcoal bg-blush rounded-md py-0.5">
                  {ticker}
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-sans text-charcoal truncate">{name}</p>
                  <p className="text-[10px] font-sans text-muted">{weight}% of SPY</p>
                </div>
              </div>
              <div className="text-right shrink-0 ml-2">
                <p className="text-sm font-sans font-medium text-charcoal tabular-nums">
                  {price !== "N/A" ? `$${price}` : "-"}
                </p>
                <p className={`text-[11px] font-sans font-semibold tabular-nums ${
                  up ? "text-emerald-600" : "text-terracotta"
                }`}>
                  {formatPct(changePercent, up)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Sectors tab */}
      {!loading && tab === "sectors" && (
        <ul className="divide-y divide-border">
          {sectors.map(({ sector, weight }) => (
            <li key={sector} className="px-5 py-2.5 hover:bg-blush/30 transition-colors duration-100">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-sans text-charcoal">{sector}</span>
                <span className="text-xs font-sans font-semibold text-charcoal tabular-nums">{weight}%</span>
              </div>
              <div className="h-1 bg-blush rounded-full overflow-hidden">
                <div
                  className="h-full bg-terracotta rounded-full transition-all duration-500"
                  style={{ width: `${(weight / 35) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Footer note */}
      <div className="px-5 py-3 border-t border-border">
        <p className="text-[10px] font-sans text-muted">
          {isLive
            ? marketOpen
              ? "Live prices via Twelve Data. Refreshed hourly."
              : "Market closed. Showing last closing prices via Twelve Data."
            : "Indicative prices. Live data loads when market is open."}
        </p>
      </div>

    </div>
  );
}
