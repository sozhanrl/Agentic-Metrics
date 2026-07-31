from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in .env file")

# Neon serverless Postgres uses a connection pooler that can have slow cold
# starts.  Strip the channel_binding=require query param (psycopg2 doesn't
# support it and it causes indefinite hangs) and tune the pool so connections
# are validated before use and idle ones are recycled promptly.
_clean_url = DATABASE_URL
for param in ("channel_binding=require", "channel_binding=prefer"):
    _clean_url = _clean_url.replace("&" + param, "").replace(param + "&", "").replace(param, "")
# Remove trailing ? or & if stripping left them bare
_clean_url = _clean_url.rstrip("?&")

engine = create_engine(
    _clean_url,
    pool_pre_ping=True,          # discard stale connections automatically
    pool_recycle=300,            # recycle connections every 5 min
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": 30,   # seconds — gives Neon time to wake up
        # NOTE: do NOT pass "options" with statement_timeout here —
        # Neon's pooler endpoint rejects unsupported startup parameters.
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

