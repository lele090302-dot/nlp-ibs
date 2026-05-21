# TL;DR Newsletter — Landing Page

Next.js 14 landing page for subscriber signup. Shares a SQLite database with the Python backend so new subscribers are immediately available to the pipeline.

## Quick Start

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Features

- **Subscriber signup** with name, email, topic selection, and daily/weekly cadence
- **Live stock ticker** showing S&P 500 top holdings via Twelve Data API (60-min server-side cache)
- **Responsive design** with Tailwind CSS editorial theme
- **Shared database** — writes directly to the Python backend's SQLite DB

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/subscribe` | POST | Create/update subscriber in shared SQLite DB |
| `/api/stocks` | GET | Fetch live SPY holdings + sector weights |

## Tech

- Next.js 14 (App Router)
- React 18 + TypeScript
- Tailwind CSS
- `better-sqlite3` for direct DB access
- Twelve Data API for market data

## Environment Variables

Create `.env.local`:

```
TWELVE_DATA_API_KEY=your_key_here
```

The stock ticker works without this key (falls back to placeholder data), but live prices require a free API key from [twelvedata.com](https://twelvedata.com).
