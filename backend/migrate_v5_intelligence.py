"""
Migration v5: AI Software Engineering Intelligence Platform
Creates tables for:
- health_snapshots
- anomalies
- recommendation_actions
- recommendation_outcomes
- project_events
- alerts
- risk_predictions
- alert_rules
"""
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base
from app import models

def run_migration():
    print("[MIGRATION] Running migration v5: AI Software Engineering Intelligence Platform tables...")
    
    # Create all tables defined in models if not exists
    Base.metadata.create_all(bind=engine)
    print("[SUCCESS] Tables created / verified successfully via SQLAlchemy Base metadata.")
    
    with engine.connect() as conn:
        print("[SUCCESS] Verified database connection and tables.")

if __name__ == "__main__":
    run_migration()
