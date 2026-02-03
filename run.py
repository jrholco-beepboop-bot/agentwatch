#!/usr/bin/env python3
"""
AgentWatch Quick Start

Run this to start both the API and dashboard servers.
"""

import subprocess
import sys
import os
import time
import threading
import webbrowser

def run_api():
    """Run the API server."""
    subprocess.run([sys.executable, "-m", "src.api.main"], cwd=os.path.dirname(__file__))

def run_dashboard():
    """Run the dashboard server."""
    subprocess.run([sys.executable, "-m", "src.dashboard.serve"], cwd=os.path.dirname(__file__))

def main():
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     🔍 AgentWatch - AI Agent Observability Platform      ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Initialize database first
    print("📦 Initializing database...")
    subprocess.run([sys.executable, "-m", "src.api.init_db"], cwd=os.path.dirname(__file__))
    
    print("\n🚀 Starting servers...")
    print("   API:       http://localhost:8765")
    print("   Dashboard: http://localhost:8766")
    print("   API Docs:  http://localhost:8765/docs")
    print("\n   Press Ctrl+C to stop\n")
    
    # Start API in background thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    
    # Wait for API to start
    time.sleep(2)
    
    # Start dashboard in background thread
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    
    # Wait a moment then open browser
    time.sleep(2)
    try:
        webbrowser.open("http://localhost:8766")
    except:
        pass
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down AgentWatch...")
        sys.exit(0)

if __name__ == "__main__":
    main()
