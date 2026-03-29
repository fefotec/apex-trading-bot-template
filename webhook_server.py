#!/usr/bin/env python3
"""
Simple Webhook Server für Git Pull
Lauscht auf Port 8888 und führt git pull bei POST Request aus.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
import os
from datetime import datetime

# Security Token aus ENV laden (kein hardcoded Secret!)
SECRET_TOKEN = os.environ.get("WEBHOOK_SECRET", "")
REPO_PATH = "/data/.openclaw/workspace/projects/apex-trading"

if not SECRET_TOKEN:
    # Fallback: aus .env Datei im Projektverzeichnis
    env_path = os.path.join(REPO_PATH, ".env.webhook")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    if key == 'WEBHOOK_SECRET':
                        SECRET_TOKEN = value

SERVER_START = datetime.now()

class WebhookHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Health-Check Endpoint"""
        uptime = (datetime.now() - SERVER_START).total_seconds()
        response = {
            "status": "ok",
            "uptime_seconds": int(uptime),
            "repo": REPO_PATH,
            "token_set": bool(SECRET_TOKEN)
        }
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        # Check Token
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != SECRET_TOKEN:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error": "Unauthorized"}')
            return
        
        # Execute git pull
        try:
            os.chdir(REPO_PATH)
            result = subprocess.run(
                ['git', 'pull', 'origin', 'main'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            response = {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
            print(f"[{datetime.now()}] Git pull executed: {result.stdout}")
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def log_message(self, format, *args):
        print(f"[{datetime.now()}] {format % args}")

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8888), WebhookHandler)
    print(f"🚀 Webhook server running on port 8888")
    print(f"📁 Repo: {REPO_PATH}")
    print(f"🔐 Token: {'***' + SECRET_TOKEN[-4:] if SECRET_TOKEN else 'NICHT GESETZT!'}")
    server.serve_forever()
