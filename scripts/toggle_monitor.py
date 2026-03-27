#!/usr/bin/env python3
"""
Toggle Position Monitor Cron Job via file-based signaling
"""
import os
import sys
import json

SIGNAL_FILE = "/data/.openclaw/workspace/projects/apex-trading/data/monitor_signal.json"

def set_signal(action: str):
    """Write signal file for main agent to process"""
    os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)
    
    signal = {
        "action": action,  # "enable" or "disable"
        "timestamp": "now"
    }
    
    with open(SIGNAL_FILE, 'w') as f:
        json.dump(signal, f)
    
    state = "aktiviert" if action == "enable" else "deaktiviert"
    print(f"   ✅ Position Monitor {state} (Signal gesetzt)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: toggle_monitor.py <on|off>")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action in ["on", "true", "1", "enable"]:
        set_signal("enable")
    elif action in ["off", "false", "0", "disable"]:
        set_signal("disable")
    else:
        print(f"Invalid action: {action}")
        sys.exit(1)
