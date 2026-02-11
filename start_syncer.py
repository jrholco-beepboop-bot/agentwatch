#!/usr/bin/env python3
"""
Start the OpenClaw → AgentWatch Syncer

This polls OpenClaw's live session data and pushes it to AgentWatch.
Run this alongside the API and dashboard servers.
"""

from src.integrations.polling_daemon import PollingDaemon
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

if __name__ == "__main__":
    daemon = PollingDaemon(
        openclaw_url="http://127.0.0.1:18789",
        agentwatch_url="http://localhost:8765",
        poll_interval_s=30,
    )
    daemon.run()
