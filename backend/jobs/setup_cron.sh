#!/bin/bash
# Setup cron job to expire subscriptions every hour

CRON_JOB="0 * * * * cd /app/backend && /usr/bin/python3 jobs/expire_subscriptions.py >> /var/log/expire_subscriptions.log 2>&1"

# Add cron job if not exists
(crontab -l 2>/dev/null | grep -v expire_subscriptions; echo "$CRON_JOB") | crontab -

echo "✅ Cron job installed: runs every hour"
crontab -l | grep expire_subscriptions
