from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Numeric, TIMESTAMP,
    ForeignKey, ARRAY, BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    source = Column(String(50), nullable=False)       # azure_devops | github | sonarqube
    external_id = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)      # code_quality | process | devops
    source = Column(String(50), nullable=False)
    unit = Column(String(50))
    higher_is_better = Column(Boolean, default=True)
    description = Column(Text)


class MetricValue(Base):
    __tablename__ = "metric_values"

    id = Column(BigInteger, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    metric_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=False)
    value = Column(Numeric, nullable=False)
    recorded_at = Column(TIMESTAMP, nullable=False)
    collected_at = Column(TIMESTAMP, server_default=func.now())
    raw_payload = Column(JSONB)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(BigInteger, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=False)
    priority_score = Column(Numeric, nullable=False)
    related_metrics = Column(ARRAY(Integer))
    status = Column(String(50), default="open")        # open | acknowledged | actioned | dismissed
    created_at = Column(TIMESTAMP, server_default=func.now())
    resolved_at = Column(TIMESTAMP, nullable=True)


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(BigInteger, ForeignKey("recommendations.id"), nullable=False)
    was_helpful = Column(Boolean)
    user_comment = Column(Text)
    outcome_metric_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=True)
    outcome_delta = Column(Numeric, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
