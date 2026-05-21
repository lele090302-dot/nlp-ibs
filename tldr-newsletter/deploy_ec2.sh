#!/usr/bin/env bash
set -euo pipefail

# deploy_ec2.sh
# Manual bootstrap script to run on an Ubuntu EC2 instance (run as root or via sudo)

GIT_REPO="https://github.com/lele090302-dot/nlp-ibs.git"
GIT_DIR="/opt/tldr-newsletter"
BRANCH="main"

echo "Starting deploy..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip git build-essential

if [ ! -d "$GIT_DIR" ]; then
  git clone --depth 1 -b "$BRANCH" "$GIT_REPO" "$GIT_DIR"
else
  cd "$GIT_DIR" && git fetch origin && git reset --hard origin/$BRANCH
fi

python3 -m venv $GIT_DIR/.venv
source $GIT_DIR/.venv/bin/activate
pip install --upgrade pip
pip install -r $GIT_DIR/requirements.txt

if [ ! -f $GIT_DIR/.env ]; then
  cat > $GIT_DIR/.env <<'ENV'
SES_SENDER_EMAIL=newsletter@example.com
AWS_REGION=us-east-1
ENV
fi

cp $GIT_DIR/tldr-scheduler.service /etc/systemd/system/tldr-scheduler.service
systemctl daemon-reload
systemctl enable tldr-scheduler.service
systemctl start tldr-scheduler.service

echo "Deploy complete. Check service logs with: journalctl -u tldr-scheduler.service -f"
