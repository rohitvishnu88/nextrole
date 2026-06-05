#!/usr/bin/env python3
"""
Start the Resume Builder A2A server.

Usage:
  python3 run_a2a_server.py
  A2A_BASE_URL=https://your-domain.com python3 run_a2a_server.py

The server exposes:
  GET  /.well-known/agent.json   Agent card (discovery)
  POST /                         JSON-RPC 2.0 task handler (sync + SSE streaming)
  GET  /docs                     Auto-generated API docs
"""
import os
import uvicorn

HOST = os.environ.get("A2A_HOST", "0.0.0.0")
PORT = int(os.environ.get("A2A_PORT", "8000"))

if __name__ == "__main__":
    print(f"\n  Resume Builder A2A Agent")
    print(f"  Agent card: http://{HOST}:{PORT}/.well-known/agent.json")
    print(f"  Docs:       http://{HOST}:{PORT}/docs\n")
    uvicorn.run("a2a.server:app", host=HOST, port=PORT, reload=True)
