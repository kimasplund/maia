from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment variable or use SQLite as default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///data/maia.db"
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    # Enable SQLite foreign key support
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    # Enable connection pooling
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for declarative models
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database tables
def init_db():
    Base.metadata.create_all(bind=engine) 