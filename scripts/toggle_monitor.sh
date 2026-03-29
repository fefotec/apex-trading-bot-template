#!/bin/bash
# Toggle Position Monitor Cron via OpenClaw Gateway API

CRON_ID="58dc090d-2bb6-4375-afd3-e07836793bc6"
ACTION="$1"

if [ "$ACTION" = "on" ] || [ "$ACTION" = "enable" ]; then
    ENABLED="true"
    STATE="aktiviert"
elif [ "$ACTION" = "off" ] || [ "$ACTION" = "disable" ]; then
    ENABLED="false"
    STATE="deaktiviert"
else
    echo "Usage: $0 <on|off>"
    exit 1
fi

# Use openclaw CLI (gateway restart method)
echo "   ⏳ ${STATE}..."

# Direct file manipulation (hack but works)
CONFIG_FILE="/data/.openclaw/cron-state.json"

if [ -f "$CONFIG_FILE" ]; then
    # Update enabled field in JSON
    python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    data = json.load(f)

for job in data.get('jobs', []):
    if job.get('id') == '$CRON_ID':
        job['enabled'] = $ENABLED
        break

with open('$CONFIG_FILE', 'w') as f:
    json.dump(data, f, indent=2)
    
print('   ✅ Position Monitor $STATE')
"
else
    echo "   ⚠️  Config file not found"
    exit 1
fi
