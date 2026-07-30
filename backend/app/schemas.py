from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any


# ---------- Projects ----------

class ProjectCreate(BaseModel):
    name: str
    source: str
    external_id: str


class ProjectResponse(ProjectCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- Metric Definitions ----------

class MetricDefinitionResponse(BaseModel):
    id: int
    key: str
    display_name: str
    category: str
    source: str
    unit: Optional[str] = None
    higher_is_better: bool
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Metric Values ----------

class MetricValueCreate(BaseModel):
    project_id: int
    metric_id: int
    value: float
    recorded_at: datetime
    raw_payload: Optional[Any] = None


class MetricValueResponse(BaseModel):
    id: int
    project_id: int
    metric_id: int
    value: float
    recorded_at: datetime
    collected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# A metric value enriched with its definition, for dashboard display
class MetricValueWithDefinition(BaseModel):
    id: int
    metric_key: str
    display_name: str
    category: str
    unit: Optional[str] = None
    higher_is_better: bool
    value: float
    recorded_at: datetime

    class Config:
        from_attributes = True


# ---------- Recommendations ----------

class RecommendationResponse(BaseModel):
    id: int
    project_id: int
    title: str
    explanation: str
    priority_score: float
    related_metrics: Optional[List[int]] = None
    status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RecommendationStatusUpdate(BaseModel):
    status: str  # open | acknowledged | actioned | dismissed


# ---------- Feedback ----------

class FeedbackCreate(BaseModel):
    recommendation_id: int
    was_helpful: bool
    user_comment: Optional[str] = None
    outcome_metric_id: Optional[int] = None
    outcome_delta: Optional[float] = None


class FeedbackResponse(FeedbackCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
