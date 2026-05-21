# Deploying the TL;DR scheduler to AWS EC2

This guide walks through a minimal, low-cost EC2 setup to run `scheduler.py` continuously and send emails via Amazon SES. It includes IAM role recommendations, a sample `user-data` script to bootstrap the instance, and a `systemd` service unit to keep the scheduler running across reboots.

### Overview and assumptions
- Region: `us-east-1` (match the SES region you use in `.env` / `sender.py`)
- This guide assumes the repository is accessible (via GitHub) from the EC2 instance, or that you will `scp` the project there.
- The instance will run the scheduler only (the Streamlit UI can be run elsewhere if you want).
- We'll attach an IAM role with SES send permissions so no long-lived AWS keys are stored on the instance.

### 1) Choose instance type
- For development or modest volumes: `t3.small` or `t3.micro` (t3.micro may be eligible for free tier). If your pipeline uses heavy NLP models (torch/transformers), pick a larger instance with more memory (e.g., `t3.medium` or a compute-optimized instance).

### 2) Security group
- Allow SSH (port 22) from your IP only.
- No inbound ports are required for the scheduler service.

### 3) IAM role & policy (recommended)
Create an IAM role for EC2 and attach a policy allowing SES SendEmail (and optional SNS for bounce/complaint notifications).

Example minimal inline policy (attach to the EC2 role):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish",
        "sns:CreateTopic",
        "sns:Subscribe"
      ],
      "Resource": "*"
    }
  ]
}
```

Notes:
- Using an IAM role avoids embedding AWS credentials on the instance; boto3 will pick up temporary credentials automatically.

### 4) User-data script (Ubuntu 22.04 example)
Paste this into the EC2 launch `user-data` field. It will install Python, git, clone your repo, create a venv, install requirements, and install a `systemd` unit that runs the scheduler at boot.

Replace `GIT_REPO` and `GIT_BRANCH` with your repository URL and branch. Example using your repository:

```bash
GIT_REPO="https://github.com/lele090302-dot/nlp-ibs.git"
BRANCH="main"
```

```bash
#!/bin/bash
set -e

# Variables
GIT_REPO="https://github.com/youruser/yourrepo.git"
GIT_DIR="/opt/tldr-newsletter"
BRANCH="main"

# Update and install packages
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip git build-essential

# Clone repo
if [ ! -d "$GIT_DIR" ]; then
  git clone --depth 1 -b "$BRANCH" "$GIT_REPO" "$GIT_DIR"
else
  cd "$GIT_DIR" && git fetch origin && git reset --hard origin/$BRANCH
fi

# Create virtualenv and install requirements
python3 -m venv $GIT_DIR/.venv
source $GIT_DIR/.venv/bin/activate
pip install --upgrade pip
pip install -r $GIT_DIR/requirements.txt

# Copy example .env if provided
if [ ! -f $GIT_DIR/.env ]; then
  cat > $GIT_DIR/.env <<'ENV'
# Example .env - replace with your values or use instance IAM role
SES_SENDER_EMAIL=newsletter@example.com
AWS_REGION=us-east-1
ENV
fi

# Create systemd service to run scheduler
cat > /etc/systemd/system/tldr-scheduler.service <<'SERVICE'
[Unit]
Description=TLDR Newsletter Scheduler
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$GIT_DIR
Environment=PATH=$GIT_DIR/.venv/bin:/usr/bin
ExecStart=$GIT_DIR/.venv/bin/python $GIT_DIR/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable tldr-scheduler.service
systemctl start tldr-scheduler.service

```

Notes:
- The `ExecStart` runs `scheduler.py` from the virtualenv. Modify paths if you keep repo in a different location.
- If your pipeline requires GPU or heavy CPU, choose an appropriate instance family.

### 5) SES setup reminders
- Verify your `SES_SENDER_EMAIL` or sending domain in the SES console for the region you're using.
- If you are in the SES sandbox and want to test with arbitrary recipients, either verify those recipient addresses or request production access.
- If you attach the EC2 IAM role with SendEmail permissions and your instance is in the same region as SES, boto3 will use the role credentials automatically.

### 6) Monitoring & logs
- Systemd logs: `journalctl -u tldr-scheduler.service -f`
- The `scheduler.py` prints to stdout; systemd captures it in journalctl.
- Consider rotating logs or writing scheduler output to a log file if you want persistent file logs.

### 7) Optional: Auto-update on new commits
- Add a small cron or systemd timer that pulls latest changes and restarts the service. Example simple cron:

```cron
# Runs every hour
0 * * * * cd /opt/tldr-newsletter && git pull origin main && systemctl restart tldr-scheduler.service
```

### 8) Costs and sizing advice
- t3.micro/t3.small are inexpensive. If using the EC2 free tier you may get some hours for free for the first 12 months.
- SES has per-message pricing; sending from EC2 to external recipients can use the SES EC2 free allowance (62k/month) if conditions are met — read AWS docs to confirm eligibility.

---

If you want, I can also:
- Generate a ready-to-use `user-data` with your Git repo URL inserted.
- Create a `tldr-newsletter.service` file in the repo and a short `deploy_ec2.sh` helper script for manual setup.
