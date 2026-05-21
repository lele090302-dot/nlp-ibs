import { NextRequest, NextResponse } from "next/server";
import path from "path";

// Map landing page topic labels to the values the Python backend expects
const TOPIC_MAP: Record<string, string> = {
  "Generative AI": "GenAI",
  "GenAI":         "GenAI",
  "Fintech":       "Fintech",
  "Tech":          "Tech",
  "Startups":      "Startups",
  "Crypto":        "Crypto",
};

// Path to the shared SQLite DB — relative to the monorepo root
// Adjust if your folder structure differs
const DB_PATH = path.resolve(
  process.cwd(),
  "../tldr-newsletter/data/users.db"
);

export async function POST(req: NextRequest) {
  let body: { name?: string; email?: string; topics?: string[]; frequency?: string };

  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { name, email, topics, frequency } = body;

  // Validate
  if (!name?.trim()) {
    return NextResponse.json({ error: "Name is required" }, { status: 400 });
  }
  if (!email || !email.includes("@")) {
    return NextResponse.json({ error: "Valid email is required" }, { status: 400 });
  }
  if (!topics || topics.length === 0) {
    return NextResponse.json({ error: "Select at least one topic" }, { status: 400 });
  }

  // Normalise topics to Python backend values
  const normalisedTopics = topics
    .map((t) => TOPIC_MAP[t] ?? t)
    .filter(Boolean);

  const freq = frequency === "weekly" ? "weekly" : "daily";
  const createdAt = new Date().toISOString();

  try {
    // Dynamic import so the module only loads server-side
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(DB_PATH);

    // Ensure table exists (mirrors Python init_db)
    db.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        topics TEXT NOT NULL,
        frequency TEXT NOT NULL,
        created_at TEXT NOT NULL,
        active INTEGER DEFAULT 1
      )
    `);

    const existing = db
      .prepare("SELECT id FROM users WHERE email = ?")
      .get(email);

    if (existing) {
      // Update preferences for returning subscriber
      db.prepare(
        "UPDATE users SET name=?, topics=?, frequency=?, active=1 WHERE email=?"
      ).run(name.trim(), normalisedTopics.join(","), freq, email.trim());
      db.close();
      return NextResponse.json({ message: "Preferences updated!" });
    }

    db.prepare(
      "INSERT INTO users (name, email, topics, frequency, created_at) VALUES (?, ?, ?, ?, ?)"
    ).run(name.trim(), email.trim(), normalisedTopics.join(","), freq, createdAt);

    db.close();
    return NextResponse.json({ message: "Subscribed successfully!" }, { status: 201 });

  } catch (err) {
    console.error("[/api/subscribe] DB error:", err);
    return NextResponse.json(
      { error: "Could not save subscription. Please try again." },
      { status: 500 }
    );
  }
}
