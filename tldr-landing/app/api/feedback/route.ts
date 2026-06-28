import { NextRequest, NextResponse } from "next/server";
import path from "path";

// Path to the shared SQLite DB
// Use DB_PATH env var in production, fall back to relative path for local dev
const DB_PATH = process.env.DB_PATH
  ? path.resolve(process.env.DB_PATH)
  : path.resolve(process.cwd(), "../tldr-newsletter/data/users.db");

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);

  const email = searchParams.get("email") || "";
  const articleUrl = searchParams.get("url") || "";
  const source = searchParams.get("source") || "";
  const topic = searchParams.get("topic") || "";
  const signalRaw = searchParams.get("signal") || "0";
  const signal = parseInt(signalRaw, 10);

  if (!email || !articleUrl || ![1, -1].includes(signal)) {
    return new NextResponse(thankYouHtml("Invalid feedback link."), {
      status: 400,
      headers: { "Content-Type": "text/html" },
    });
  }

  try {
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(DB_PATH);

    db.exec(`
      CREATE TABLE IF NOT EXISTS article_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        article_url TEXT NOT NULL,
        article_source TEXT,
        article_topic TEXT,
        signal INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(email, article_url)
      )
    `);

    const now = new Date().toISOString();
    db.prepare(`
      INSERT INTO article_feedback (email, article_url, article_source, article_topic, signal, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(email, article_url) DO UPDATE SET signal=excluded.signal, created_at=excluded.created_at
    `).run(email, articleUrl, source, topic, signal, now);

    db.close();

    const message = signal === 1
      ? "Thanks for your feedback! We'll show you more stories like\u00a0this."
      : "Got it. We'll adjust your future newsletters accordingly.";

    return new NextResponse(thankYouHtml(message), {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
  } catch (err) {
    console.error("[/api/feedback] DB error:", err);
    return new NextResponse(thankYouHtml("Thanks for your feedback!"), {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
  }
}

function thankYouHtml(message: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>TL;DR Newsletter - Feedback</title>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
  <style>
    body { font-family: 'Inter', sans-serif; background: #FFF8F3; margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .card { background: #fff; border-radius: 16px; padding: 48px; max-width: 440px; text-align: center; box-shadow: 0 2px 20px rgba(30,27,24,0.07); border: 1px solid #EAD9D3; }
    .card h1 { font-family: 'Playfair Display', serif; color: #C83A2A; font-size: 24px; margin: 0 0 16px; }
    .card p { color: #1E1B18; font-size: 15px; line-height: 1.6; margin: 0 0 24px; }
    .card a { color: #C83A2A; text-decoration: none; font-weight: 600; font-size: 14px; }
    .card a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <h1>TL;DR Newsletter</h1>
    <p>${message}</p>
    <a href="https://codesonline.rocks">Back to TL;DR Newsletter</a>
  </div>
</body>
</html>`;
}
