# EC2 Operations Guide

All commands assume you're SSH'd into the EC2 instance. The project lives at `/opt/tldr-newsletter`.

## Connect to EC2

```bash
ssh -i nlpkey.pem ubuntu@<your-ec2-public-ip>
```

## Activate the virtual environment

```bash
cd /opt/tldr-newsletter
source .venv/bin/activate
```

---

## Pipeline Commands

```bash
# Stage only (fetch → rank → summarize → save to review queue → notify admin)
python pipeline.py --stage

# Send only (uses admin-approved articles, or AI fallback if none approved)
python pipeline.py --send

# Force both stages back-to-back (skips admin review, AI picks only)
python pipeline.py --force-both
```

---

## Scheduler Service

```bash
# Check if the scheduler is running
sudo systemctl status tldr-scheduler.service

# View live logs
sudo journalctl -u tldr-scheduler.service -f

# Restart after a code update
sudo systemctl restart tldr-scheduler.service

# Stop the scheduler
sudo systemctl stop tldr-scheduler.service
```

---

## Query the Database (SQLite)

### Option A: Using the sqlite3 CLI directly

```bash
cd /opt/tldr-newsletter
sqlite3 data/users.db
```

Then inside the SQLite shell:

```sql
-- List all users
SELECT id, name, email, topics, frequency, active FROM users;

-- Active subscribers only
SELECT name, email, topics, frequency FROM users WHERE active=1;

-- How many newsletters each user has received
SELECT email, COUNT(*) as total_sent FROM send_log GROUP BY email ORDER BY total_sent DESC;

-- Send history for a specific user
SELECT * FROM send_log WHERE email='user@example.com' ORDER BY sent_at DESC;

-- Total sends per run
SELECT run_id, COUNT(*) as emails_sent, MIN(sent_at) as sent_at FROM send_log GROUP BY run_id ORDER BY sent_at DESC;

-- Check the review queue (latest run)
SELECT title, source, topic, relevance_score, status FROM review_queue ORDER BY created_at DESC LIMIT 15;

-- Exit sqlite3
.quit
```

### Option B: Using Python one-liners

```bash
cd /opt/tldr-newsletter
source .venv/bin/activate

# Total newsletters received by each user
python -c "from db import get_connection; rows = get_connection().execute('SELECT email, COUNT(*) as cnt FROM send_log GROUP BY email').fetchall(); [print(f\"{r['email']}: {r['cnt']}\") for r in rows]"

# Send count for a specific user
python -c "from db import get_send_count; print(get_send_count('user@example.com'))"

# Full send history for a user
python -c "from db import get_send_history; [print(r) for r in get_send_history('user@example.com')]"

# List all active subscribers
python -c "from db import get_all_active_users; [print(f\"{u['name']} - {u['email']}\") for u in get_all_active_users()]"
```

---

## Deploy Code Updates

```bash
cd /opt/tldr-newsletter
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt   # only if deps changed
python -c "from db import init_db; init_db()"  # creates any new tables
sudo systemctl restart tldr-scheduler.service
```

---

## Quick Reference

| Task | Command |
|------|---------|
| SSH in | `ssh -i nlpkey.pem ubuntu@<ip>` |
| Stage articles | `python pipeline.py --stage` |
| Send newsletters | `python pipeline.py --send` |
| Full run (no review) | `python pipeline.py --force-both` |
| Check scheduler | `sudo systemctl status tldr-scheduler.service` |
| Live logs | `sudo journalctl -u tldr-scheduler.service -f` |
| Open DB | `sqlite3 data/users.db` |
| Count sends per user | `SELECT email, COUNT(*) FROM send_log GROUP BY email;` |
