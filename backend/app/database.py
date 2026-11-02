import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEFAULT_DATABASE_URL = "postgresql+psycopg://vamshij@localhost:5432/dealnest_db"


def get_database_url() -> str:
    """Return the configured PostgreSQL URL, falling back to local development."""
    return os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,      # Automatically reconnects dropped connections
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine
)

Base = declarative_base()

def get_db():
    """Dependency injection helper for FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
