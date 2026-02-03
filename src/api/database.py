"""
AgentWatch Database Connection

Async SQLAlchemy setup for SQLite (MVP) with easy migration to PostgreSQL.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from .models import Base

# Database URL - SQLite for MVP, easy to swap to PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentwatch.db")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "").lower() == "true",
    future=True
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get a database session."""
    async with async_session_factory() as session:
        yield session


# Dependency for FastAPI
async def get_db():
    """FastAPI dependency for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
