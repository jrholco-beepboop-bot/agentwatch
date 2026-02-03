"""
Initialize AgentWatch Database

Run this to create all tables.
"""

import asyncio
from .database import init_db


async def main():
    print("Initializing AgentWatch database...")
    await init_db()
    print("[OK] Database initialized successfully!")
    print("     Tables created in: agentwatch.db")


if __name__ == "__main__":
    asyncio.run(main())
