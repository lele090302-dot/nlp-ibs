import { NextResponse } from "next/server";

// SPY top 10 holdings (Yahoo Finance / stockanalysis.com, May 2025)
const SPY_HOLDINGS = [
  { ticker: "NVDA",  name: "Nvidia",     weight: 7.78 },
  { ticker: "AAPL",  name: "Apple",      weight: 6.64 },
  { ticker: "MSFT",  name: "Microsoft",  weight: 4.97 },
  { ticker: "AMZN",  name: "Amazon",     weight: 4.23 },
  { ticker: "GOOGL", name: "Alphabet",   weight: 3.62 },
  { ticker: "META",  name: "Meta",       weight: 3.10 },
  { ticker: "TSLA",  name: "Tesla",      weight: 1.97 },
  { ticker: "BRKB",  name: "Berkshire",  weight: 1.74 },
  { ticker: "AVGO",  name: "Broadcom",   weight: 1.72 },
  { ticker: "JPM",   name: "JPMorgan",   weight: 1.38 },
];

const SPY_SECTORS = [
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

export interface StockQuote {
  ticker: string;
  name: string;
  weight: number;
  price: string;
  change: string;
  changePercent: string;
  up: boolean;
}

export interface StocksResponse {
  holdings: StockQuote[];
  sectors: typeof SPY_SECTORS;
  lastUpdated: string;
  source: string;
  marketOpen: boolean;
}

// ── Server-side in-memory cache ───────────────────────────────────────────────
// One fetch per CACHE_TTL_MS regardless of how many visitors hit the page.
// With 60-min TTL: max 24 API credits/day during market hours.
const CACHE_TTL_MS = 60 * 60 * 1000; // 60 minutes

let cachedData: StocksResponse | null = null;
let cacheTimestamp = 0;

// ── Market hours check (US Eastern) ──────────────────────────────────────────
// Outside market hours prices don't change — no point fetching.
function isMarketOpen(): boolean {
  const now = new Date();
  // Convert to US/Eastern (UTC-4 EDT / UTC-5 EST)
  const etOffset = isDST(now) ? -4 : -5;
  const etHour = (now.getUTCHours() + etOffset + 24) % 24;
  const etMinute = now.getUTCMinutes();
  const dayOfWeek = now.getUTCDay(); // 0=Sun, 6=Sat

  if (dayOfWeek === 0 || dayOfWeek === 6) return false; // weekend

  const minutesSinceMidnight = etHour * 60 + etMinute;
  return minutesSinceMidnight >= 9 * 60 + 30   // 9:30am ET
      && minutesSinceMidnight < 16 * 60;         // 4:00pm ET
}

function isDST(date: Date): boolean {
  // Rough DST check for US Eastern (second Sunday March - first Sunday November)
  const jan = new Date(date.getFullYear(), 0, 1).getTimezoneOffset();
  const jul = new Date(date.getFullYear(), 6, 1).getTimezoneOffset();
  return date.getTimezoneOffset() < Math.max(jan, jul);
}

// ── Route handler ─────────────────────────────────────────────────────────────
export async function GET() {
  const now = Date.now();
  const cacheAge = now - cacheTimestamp;
  const marketOpen = isMarketOpen();

  // During Next.js static build, skip the live fetch entirely
  if (process.env.NEXT_PHASE === "phase-production-build") {
    return NextResponse.json(buildPlaceholder(false), {
      headers: { "Cache-Control": "public, max-age=3600" },
    });
  }

  // Serve from cache if:
  // - cache is fresh (< 60 min old), OR
  // - market is closed (prices haven't changed since last fetch)
  if (cachedData && (cacheAge < CACHE_TTL_MS || !marketOpen)) {
    return NextResponse.json(
      { ...cachedData, marketOpen },
      {
        headers: {
          // Tell browsers: cache for 60 min, allow stale while revalidating
          "Cache-Control": "public, max-age=3600, stale-while-revalidate=300",
        },
      }
    );
  }

  const apiKey = process.env.TWELVE_DATA_API_KEY;
  if (!apiKey) {
    const placeholder = buildPlaceholder(marketOpen);
    cachedData = placeholder;
    cacheTimestamp = now;
    return NextResponse.json(placeholder, {
      headers: { "Cache-Control": "public, max-age=3600" },
    });
  }

  try {
    const symbols = SPY_HOLDINGS.map((h) => h.ticker).join(",");
    const url = `https://api.twelvedata.com/quote?symbol=${symbols}&apikey=${apiKey}`;

    const res = await fetch(url, {
      // Next.js ISR cache — revalidate every 60 min at the CDN level too
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) throw new Error(`Twelve Data HTTP ${res.status}`);

    const data = await res.json();

    // Check for API-level errors (e.g. invalid key, rate limit)
    if (data.status === "error") {
      throw new Error(`Twelve Data API error: ${data.message}`);
    }

    const holdings: StockQuote[] = SPY_HOLDINGS.map((holding) => {
      const q = data[holding.ticker];

      if (!q || q.status === "error" || !q.close) {
        return { ...holding, price: "N/A", change: "N/A", changePercent: "N/A", up: true };
      }

      const close    = parseFloat(q.close);
      const prevClose = parseFloat(q.previous_close);
      const diff     = close - prevClose;
      const pct      = (diff / prevClose) * 100;
      const up       = diff >= 0;

      return {
        ...holding,
        price: close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        change: `${up ? "+" : ""}${diff.toFixed(2)}`,
        changePercent: `${up ? "+" : ""}${pct.toFixed(2)}%`,
        up,
      };
    });

    const result: StocksResponse = {
      holdings,
      sectors: SPY_SECTORS,
      lastUpdated: new Date().toISOString(),
      source: "Twelve Data",
      marketOpen,
    };

    // Store in server-side cache
    cachedData = result;
    cacheTimestamp = now;

    return NextResponse.json(result, {
      headers: { "Cache-Control": "public, max-age=3600, stale-while-revalidate=300" },
    });

  } catch (err) {
    console.error("[/api/stocks] Fetch error:", err);

    // On error: serve stale cache if available, otherwise placeholder
    if (cachedData) {
      console.log("[/api/stocks] Serving stale cache after error.");
      return NextResponse.json(
        { ...cachedData, marketOpen },
        { headers: { "Cache-Control": "public, max-age=300" } }
      );
    }

    const placeholder = buildPlaceholder(marketOpen);
    return NextResponse.json(placeholder, {
      headers: { "Cache-Control": "public, max-age=300" },
    });
  }
}

function buildPlaceholder(marketOpen = false): StocksResponse {
  const prices: Record<string, [string, string, boolean]> = {
    NVDA:  ["1,208.42", "+3.21%", true ],
    AAPL:  [  "213.07", "-0.38%", false],
    MSFT:  [  "427.15", "+1.04%", true ],
    AMZN:  [  "198.63", "+0.87%", true ],
    GOOGL: [  "178.22", "+1.55%", true ],
    META:  [  "521.40", "+2.10%", true ],
    TSLA:  [  "172.83", "-1.44%", false],
    BRKB:  [  "448.90", "+0.33%", true ],
    AVGO:  ["1,842.10", "+1.78%", true ],
    JPM:   [  "238.55", "-0.22%", false],
  };

  return {
    holdings: SPY_HOLDINGS.map((h) => {
      const [price, changePercent, up] = prices[h.ticker] ?? ["N/A", "N/A", true];
      return { ...h, price, change: "N/A", changePercent, up };
    }),
    sectors: SPY_SECTORS,
    lastUpdated: new Date().toISOString(),
    source: "placeholder",
    marketOpen,
  };
}
