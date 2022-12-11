#!/usr/bin/env bash
ENV_VAR="$(printenv)"
CRON_FILE="$(sed 's/$/ 2>&1 | while read -r line; do echo \"$line\"; echo \"[$(date)] $line\" >> \/var\/log\/cron.log; done/' /etc/cron.d/crontab)"

echo "${ENV_VAR}
${CRON_FILE}" | crontab - && cron -f
