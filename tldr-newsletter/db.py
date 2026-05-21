import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = "data/users.db"
os.makedirs("data", exist_ok=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            topics TEXT NOT NULL,
            frequency TEXT NOT NULL,
            created_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    # Article feedback table
    conn.execute("""
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
    """)

    # Admin review queue — holds AI-ranked candidates awaiting editorial approval
    conn.execute("""
        CREATE TABLE IF NOT EXISTS review_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,          -- groups articles from the same pipeline run
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT,
            topic TEXT,
            description TEXT,
            summary TEXT,
            reading_time INTEGER,
            relevance_score REAL,
            status TEXT DEFAULT 'pending', -- 'pending' | 'approved' | 'rejected'
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(run_id, url)
        )
    """)

    conn.commit()
    conn.close()


# ── User functions ────────────────────────────────────────────────────────────

def add_user(name: str, email: str, topics: list[str], frequency: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, topics, frequency, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, ",".join(topics), frequency, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return True, "Subscribed successfully!"
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE users SET name=?, topics=?, frequency=?, active=1 WHERE email=?",
            (name, ",".join(topics), frequency, email),
        )
        conn.commit()
        return True, "Preferences updated!"
    finally:
        conn.close()


def get_all_active_users(frequency_filter: str | None = None) -> list[dict]:
    conn = get_connection()
    if frequency_filter:
        rows = conn.execute(
            "SELECT * FROM users WHERE active=1 AND frequency=?",
            (frequency_filter,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users WHERE active=1").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def unsubscribe(email: str):
    conn = get_connection()
    conn.execute("UPDATE users SET active=0 WHERE email=?", (email,))
    conn.commit()
    conn.close()


# ── Feedback functions ────────────────────────────────────────────────────────

def log_feedback(email: str, article_url: str, article_source: str, article_topic: str, signal: int):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO article_feedback (email, article_url, article_source, article_topic, signal, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(email, article_url) DO UPDATE SET signal=excluded.signal, created_at=excluded.created_at""",
            (email, article_url, article_source, article_topic, signal, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_feedback_boost(email: str) -> dict[str, float]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT article_source, SUM(signal) as net_signal
           FROM article_feedback
           WHERE email=?
           GROUP BY article_source""",
        (email,),
    ).fetchall()
    conn.close()

    boost = {}
    for row in rows:
        source = row["article_source"]
        net = row["net_signal"] or 0
        if net != 0 and source:
            boost[source] = max(-0.15, min(0.15, net * 0.05))
    return boost


# ── Review queue functions ────────────────────────────────────────────────────

def save_review_queue(run_id: str, articles: list[dict]):
    """Save AI-ranked candidate articles to the review queue for admin approval."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    for a in articles:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO review_queue
                   (run_id, title, url, source, topic, description, summary, reading_time, relevance_score, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    run_id,
                    a.get("title", ""),
                    a.get("url", ""),
                    a.get("source", ""),
                    a.get("topic", ""),
                    a.get("description", ""),
                    a.get("summary", ""),
                    a.get("reading_time", 1),
                    a.get("relevance_score", 0.0),
                    now,
                ),
            )
        except Exception as e:
            print(f"[DB] Error saving article to queue: {e}")
    conn.commit()
    conn.close()


def get_review_queue(run_id: str | None = None, status: str | None = None) -> list[dict]:
    """Fetch articles from the review queue, optionally filtered by run_id and/or status."""
    conn = get_connection()
    query = "SELECT * FROM review_queue WHERE 1=1"
    params: list = []
    if run_id:
        query += " AND run_id=?"
        params.append(run_id)
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY relevance_score DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_run_id() -> str | None:
    """Return the run_id of the most recent review queue batch."""
    conn = get_connection()
    row = conn.execute(
        "SELECT run_id FROM review_queue ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["run_id"] if row else None


def update_article_status(run_id: str, url: str, status: str):
    """Approve or reject a single article in the queue."""
    conn = get_connection()
    conn.execute(
        "UPDATE review_queue SET status=?, reviewed_at=? WHERE run_id=? AND url=?",
        (status, datetime.now(timezone.utc).isoformat(), run_id, url),
    )
    conn.commit()
    conn.close()


def get_approved_articles(run_id: str) -> list[dict]:
    """Return approved articles for a given run, sorted by relevance score."""
    return get_review_queue(run_id=run_id, status="approved")


def clear_old_queues(keep_latest: int = 5):
    """Keep only the N most recent run batches to avoid unbounded DB growth."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT run_id FROM review_queue ORDER BY created_at DESC"
    ).fetchall()
    run_ids = [r["run_id"] for r in rows]
    to_delete = run_ids[keep_latest:]
    for rid in to_delete:
        conn.execute("DELETE FROM review_queue WHERE run_id=?", (rid,))
    conn.commit()
    conn.close()
