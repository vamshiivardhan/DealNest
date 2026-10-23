import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Uses DATABASE_URL from .env if defined, otherwise defaults to local Postgres
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://vamshij@localhost:5432/dealnest_db"
)

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
