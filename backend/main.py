from fastapi import FastAPI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

app = FastAPI(
    title="AI Metrics Prioritization API",
    version="1.0.0"
)

@app.get("/")
def home():
    return {
        "message": "AI Metrics Prioritization API is running!"
    }

@app.get("/database")
def database_test():
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).fetchone()[0]

    return {
        "status": "Connected",
        "database": version
    }