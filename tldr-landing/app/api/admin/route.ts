import { NextRequest, NextResponse } from "next/server";
import path from "path";

// Path to the shared SQLite DB
// Use DB_PATH env var in production, fall back to relative path for local dev
const DB_PATH = process.env.DB_PATH
  ? path.resolve(process.env.DB_PATH)
  : path.resolve(process.cwd(), "../tldr-newsletter/data/users.db");

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);

  const action = searchParams.get("admin_action");
  const runId = searchParams.get("run_id") || "";
  const url = searchParams.get("url") || "";

  if (!action || !["approve", "reject"].includes(action) || !runId || !url) {
    return new NextResponse(pageHtml("Invalid admin action link.", false), {
      status: 400,
      headers: { "Content-Type": "text/html" },
    });
  }

  try {
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(DB_PATH);

    const now = new Date().toISOString();
    db.prepare(
      "UPDATE review_queue SET status=?, reviewed_at=? WHERE run_id=? AND url=?"
    ).run(action === "approve" ? "approved" : "rejected", now, runId, url);

    db.close();

    const message = action === "approve"
      ? "Article approved. It will be included in the next newsletter send."
      : "Article rejected. It will be excluded from newsletters.";

    return new NextResponse(pageHtml(message, true), {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
  } catch (err) {
    console.error("[/api/admin] DB error:", err);
    return new NextResponse(pageHtml("Something went wrong. Please try again.", false), {
      status: 500,
      headers: { "Content-Type": "text/html" },
    });
  }
}

function pageHtml(message: string, success: boolean): string {
  const icon = success ? "✓" : "✗";
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>TL;DR Admin</title>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
  <style>
    body { font-family: 'Inter', sans-serif; background: #FFF8F3; margin: 0; padding: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .card { background: #fff; border-radius: 16px; padding: 48px; max-width: 440px; text-align: center; box-shadow: 0 2px 20px rgba(30,27,24,0.07); border: 1px solid #EAD9D3; }
    .icon { font-size: 36px; color: ${success ? "#C83A2A" : "#7A6F68"}; margin-bottom: 16px; }
    .card h1 { font-family: 'Playfair Display', serif; color: #C83A2A; font-size: 22px; margin: 0 0 16px; }
    .card p { color: #1E1B18; font-size: 15px; line-height: 1.6; margin: 0; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">${icon}</div>
    <h1>TL;DR Admin</h1>
    <p>${message}</p>
  </div>
</body>
</html>`;
}
